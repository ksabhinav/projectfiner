#!/usr/bin/env python3
"""
Bulk-download every PDF (and optionally XLSX/DOC) ever archived for a given
SLBC site, from the Wayback Machine. Saves under

    slbc-data/<state>/wayback/<year>/<filename>

plus a manifest JSON listing original URL, snapshot timestamp, snapshot URL,
content-length, sha256, and the local file path.

Use cases:
- Backfill years of district-level data that the upstream portal no longer
  serves (or never served reliably).
- Build a permanent local archive of meeting agendas, minutes, annexures
  that the SLBC site may rotate or overwrite.

Walks Wayback CDX with `url=<host>/*&filter=urlkey:.*\\.pdf`, dedupes by
canonical URL (keeps the LATEST snapshot of each unique file), downloads
through `https://web.archive.org/web/<ts>id_/<orig>` (the `id_` modifier
serves the raw bytes instead of a wrapped HTML page).

Run:
    python3 db/fetch_wayback_pdfs.py kerala slbckerala.com
    python3 db/fetch_wayback_pdfs.py kerala slbckerala.com --ext pdf,xlsx
    python3 db/fetch_wayback_pdfs.py kerala slbckerala.com --dry-run

Idempotent: skips files that already exist locally with the expected size.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = 'projectfiner-wayback-fetcher/1.0 (https://projectfiner.com)'
CDX_BASE = 'https://web.archive.org/cdx/search/cdx'
WAYBACK_RAW = 'https://web.archive.org/web/{ts}id_/{orig}'
INTER_DOWNLOAD_DELAY_S = 4.0   # polite throttle; Wayback throttles bursts
                               # of >15 req/min by refusing the connection.
DOWNLOAD_TIMEOUT_S = 90
DOWNLOAD_RETRIES = 3           # transient connection refusals are common —
                               # retry with exponential backoff before giving up.
RETRY_BACKOFF_S = 10           # base delay; multiplied by attempt number

EXT_FILTER = {
    'pdf':  r'.*\.pdf',
    'xlsx': r'.*\.xlsx?',
    'doc':  r'.*\.docx?',
    'zip':  r'.*\.zip',
}


def cdx_pdf_inventory(host_pattern: str, exts: list[str]) -> list[dict]:
    """Return [{ts, orig, mime}] for every <ext> snapshot ever archived
    under the host pattern. Dedupes by canonical URL keeping the latest.

    CDX's server-side regex filter on urlkey is sometimes flaky and slow —
    we fetch the full 200-status snapshot list once and filter client-side.
    For a typical SLBC site this is ~1-5 MB of JSON, well worth the
    reliability win.
    """
    qs = parse.urlencode({
        'url': f'{host_pattern}/*',
        'output': 'json',
        'filter': 'statuscode:200',
        'fl': 'timestamp,original,mimetype',
    })
    cdx_url = f'{CDX_BASE}?{qs}'
    print(f'querying CDX → {cdx_url}', file=sys.stderr)
    # Retry CDX once on transient failure (503s and timeouts are common).
    payload = ''
    for attempt in (1, 2, 3):
        try:
            payload = _curl_get(cdx_url, timeout=180)
            if payload and not payload.lstrip().startswith('<'):
                break
            payload = ''
        except Exception as e:
            print(f'  CDX attempt {attempt} failed: {e}', file=sys.stderr)
        if attempt < 3:
            time.sleep(5 * attempt)
    if not payload:
        raise RuntimeError('CDX exhausted retries; site may be temporarily unavailable')
    rows = json.loads(payload)
    rows = rows[1:] if rows else []

    # Build ext predicate
    ext_set = set(exts)
    def matches(orig: str, mime: str) -> bool:
        low = orig.lower().split('?')[0]
        for e in ext_set:
            if low.endswith('.' + e) or (e == 'xlsx' and low.endswith('.xls')):
                return True
        if 'pdf' in ext_set and mime == 'application/pdf':
            return True
        return False
    rows = [r for r in rows if matches(r[1], r[2])]
    # Dedupe by canonical URL (drop scheme + www., percent-decode minimal)
    def canon(u: str) -> str:
        u = u.lower()
        u = re.sub(r'^https?://(www\.)?', '', u)
        u = re.sub(r':80/', '/', u)
        return u
    by_key: dict[str, dict] = {}
    for ts, orig, mime in rows:
        key = canon(orig)
        if key not in by_key or ts > by_key[key]['ts']:
            by_key[key] = {'ts': ts, 'orig': orig, 'mime': mime, 'key': key}
    return sorted(by_key.values(), key=lambda r: r['ts'])


def _curl_get(url: str, timeout: int = 60) -> str:
    """Use curl for HTTPS calls — sidesteps Python 3.14 macOS cert issues."""
    if not shutil.which('curl'):
        # Fallback to urllib (works on Linux runners)
        req = request.Request(url, headers={'User-Agent': USER_AGENT})
        with request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    p = subprocess.run(
        ['curl', '-sS', '-L', '-A', USER_AGENT, '--max-time', str(timeout), url],
        capture_output=True, text=True, check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f'curl exit {p.returncode}: {p.stderr.strip()[:200]}')
    return p.stdout


def _curl_download(url: str, dest: Path, timeout: int = DOWNLOAD_TIMEOUT_S) -> tuple[int, bool]:
    """Stream a single file to disk. Returns (bytes_written, truncated_at_capture).

    truncated_at_capture is True when Wayback's response header includes
    `warning: 299 wayback content truncated` — meaning the crawler capped
    the file at 1 MB when capturing it. There is no way to recover a fuller
    copy from the same snapshot timestamp. We still save the partial file
    (sometimes the head bytes are enough for downstream extraction) but
    flag it so the caller can mark it as `truncated` and avoid retrying.

    Retries on transient curl failures (connection refused, timeout, recv
    failure) with exponential backoff.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.part')
    headers_path = dest.with_suffix(dest.suffix + '.hdrs')
    last_err = ''
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        p = subprocess.run(
            ['curl', '-sS', '-L', '-A', USER_AGENT, '--max-time', str(timeout),
             '--connect-timeout', '30',
             '-D', str(headers_path),
             '-o', str(tmp), '-w', '%{http_code}', url],
            capture_output=True, text=True, check=False,
        )
        if p.returncode == 0:
            code = (p.stdout or '').strip()
            if code.startswith('2'):
                size = tmp.stat().st_size if tmp.exists() else 0
                # Wayback occasionally serves an HTML "snapshot doesn't exist" stub
                if size < 256:
                    head = tmp.read_bytes()[:200] if tmp.exists() else b''
                    if b'<html' in head.lower() or b'<!doctype' in head.lower():
                        tmp.unlink(missing_ok=True)
                        headers_path.unlink(missing_ok=True)
                        raise RuntimeError('HTML stub (Wayback returned a 200-wrapped error page)')
                # Check Wayback's "content truncated by length" warning header
                truncated = False
                try:
                    hdrs = headers_path.read_text(errors='replace').lower()
                    if 'wayback content truncated' in hdrs or 'truncated by "length"' in hdrs:
                        truncated = True
                except Exception:
                    pass
                headers_path.unlink(missing_ok=True)
                tmp.rename(dest)
                return size, truncated
            last_err = f'http {code}'
        else:
            last_err = f'curl exit {p.returncode}: {p.stderr.strip()[:160]}'
        if tmp.exists():
            tmp.unlink()
        if headers_path.exists():
            headers_path.unlink()
        if attempt < DOWNLOAD_RETRIES:
            time.sleep(RETRY_BACKOFF_S * attempt)
    raise RuntimeError(last_err)


def safe_filename(url: str) -> str:
    """Convert a URL's final path component into a safe filename. Decodes
    %-escapes but keeps the visible Latin/ASCII characters."""
    last = url.rstrip('/').split('/')[-1]
    last = parse.unquote(last)
    # Replace path-unsafe chars
    last = re.sub(r'[^A-Za-z0-9._\- -￿]+', '_', last)
    return last[:200]  # filesystem cap


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            chunk = f.read(1 << 16)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('state', help='State slug, e.g. "kerala"')
    ap.add_argument('host', help='Host pattern, e.g. "slbckerala.com" (no scheme)')
    ap.add_argument('--ext', default='pdf',
                    help='Comma-separated extensions to fetch (pdf,xlsx,doc,zip). Default pdf.')
    ap.add_argument('--limit', type=int, default=0,
                    help='Cap downloads (debug).')
    ap.add_argument('--dry-run', action='store_true',
                    help='Inventory only; do not download anything.')
    ap.add_argument('--inventory-only', action='store_true',
                    help='Same as --dry-run; emit the manifest with planned downloads only.')
    ap.add_argument('--skip-existing', action='store_true', default=True,
                    help='Skip files already present locally (default on).')
    ap.add_argument('--reuse-inventory', action='store_true',
                    help='Skip the CDX query; read the planned URL list from '
                         'the existing manifest.json. Useful when CDX is flaky '
                         'and you just want to resume downloading.')
    ap.add_argument('--inter-delay', type=float, default=None,
                    help='Override INTER_DOWNLOAD_DELAY_S seconds between downloads. '
                         'Default 4.0; bump to 8-12 when re-fetching after burst-truncation.')
    args = ap.parse_args()
    if args.inter_delay is not None:
        global INTER_DOWNLOAD_DELAY_S
        INTER_DOWNLOAD_DELAY_S = args.inter_delay

    exts = [e.strip().lower() for e in args.ext.split(',') if e.strip()]
    bad = [e for e in exts if e not in EXT_FILTER]
    if bad:
        print(f'unknown extension(s): {bad}; valid: {list(EXT_FILTER)}', file=sys.stderr)
        sys.exit(2)

    dest_root = ROOT / 'slbc-data' / args.state / 'wayback'
    manifest_path = dest_root / 'manifest.json'
    dest_root.mkdir(parents=True, exist_ok=True)

    if args.reuse_inventory and manifest_path.exists():
        prev = json.loads(manifest_path.read_text())
        inv = [{'ts': e['snapshotTimestamp'], 'orig': e['originalUrl'],
                'mime': '', 'key': e['canonicalUrl']}
               for e in prev.get('files', [])]
        print(f'reusing inventory from {manifest_path.relative_to(ROOT)} '
              f'({len(inv)} files)', file=sys.stderr)
    else:
        inv = cdx_pdf_inventory(args.host, exts)
    if args.limit:
        inv = inv[: args.limit]
    print(f'\n{len(inv)} unique file(s) to consider', file=sys.stderr)

    # Existing manifest entries (for resume)
    existing: dict[str, dict] = {}
    if manifest_path.exists():
        try:
            existing = {e['canonicalUrl']: e
                        for e in json.loads(manifest_path.read_text()).get('files', [])}
        except Exception:
            existing = {}

    results: list[dict] = []
    downloaded = 0
    skipped = 0
    errored = 0
    dry = args.dry_run or args.inventory_only

    for i, rec in enumerate(inv, 1):
        ts, orig, key = rec['ts'], rec['orig'], rec['key']
        year = ts[:4]
        fname = safe_filename(orig)
        local_dir = dest_root / year
        local_path = local_dir / fname
        snap_url = WAYBACK_RAW.format(ts=ts, orig=orig)

        if dry:
            results.append({
                'canonicalUrl': key,
                'originalUrl': orig,
                'snapshotTimestamp': ts,
                'snapshotUrl': snap_url,
                'localPath': str(local_path.relative_to(ROOT)),
                'status': 'planned',
            })
            continue

        if args.skip_existing and local_path.exists() and local_path.stat().st_size > 256:
            sz = local_path.stat().st_size
            existing_rec = existing.get(key)
            # If the previous run flagged this as Wayback-capture-truncated,
            # don't re-attempt — the truncation is server-side and permanent.
            if existing_rec and existing_rec.get('status') == 'truncated':
                results.append({**existing_rec, 'localPath': str(local_path.relative_to(ROOT))})
                skipped += 1
                print(f'  [{i:4d}/{len(inv)}] skip {fname[:75]} (Wayback-truncated at capture)')
                continue
            # 1MB-exact and not yet flagged → re-check headers once.
            if sz == 1048576 and not (existing_rec and existing_rec.get('status') == 'truncated'):
                print(f'  [{i:4d}/{len(inv)}] check {fname[:75]} (1MB; verifying truncation)')
                local_path.unlink()
            else:
                results.append({
                    'canonicalUrl': key,
                    'originalUrl': orig,
                    'snapshotTimestamp': ts,
                    'snapshotUrl': snap_url,
                    'localPath': str(local_path.relative_to(ROOT)),
                    'sizeBytes': sz,
                    'sha256': existing_rec.get('sha256') if existing_rec else None,
                    'status': 'cached',
                })
                skipped += 1
                print(f'  [{i:4d}/{len(inv)}] skip {fname[:80]} (already on disk)')
                continue

        try:
            size, was_truncated = _curl_download(snap_url, local_path)
            digest = file_sha256(local_path)
            status = 'truncated' if was_truncated else 'downloaded'
            results.append({
                'canonicalUrl': key,
                'originalUrl': orig,
                'snapshotTimestamp': ts,
                'snapshotUrl': snap_url,
                'localPath': str(local_path.relative_to(ROOT)),
                'sizeBytes': size,
                'sha256': digest,
                'status': status,
                **({'note': 'Wayback truncated at capture; full file unrecoverable from this snapshot'}
                   if was_truncated else {}),
            })
            if was_truncated:
                downloaded += 1
                print(f'  [{i:4d}/{len(inv)}] TRNC {year}/{fname[:75]:75} ({size//1024} KB, capped at capture)')
            else:
                downloaded += 1
                print(f'  [{i:4d}/{len(inv)}] OK   {year}/{fname[:80]:80} ({size//1024} KB)')
        except Exception as e:
            results.append({
                'canonicalUrl': key,
                'originalUrl': orig,
                'snapshotTimestamp': ts,
                'snapshotUrl': snap_url,
                'localPath': str(local_path.relative_to(ROOT)),
                'status': 'error',
                'error': str(e)[:200],
            })
            errored += 1
            print(f'  [{i:4d}/{len(inv)}] FAIL {fname[:80]} — {e}', file=sys.stderr)
        if i < len(inv):
            time.sleep(INTER_DOWNLOAD_DELAY_S)

    manifest = {
        'state': args.state,
        'host': args.host,
        'extensions': exts,
        'generatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'counts': {
            'planned': sum(1 for r in results if r['status'] == 'planned'),
            'downloaded': downloaded,
            'cached': skipped,
            'errored': errored,
        },
        'files': results,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f'\nwrote {manifest_path.relative_to(ROOT)} '
          f'({manifest["counts"]})', file=sys.stderr)


if __name__ == '__main__':
    main()
