#!/usr/bin/env python3
"""
Build public/sources/wayback.json — a mapping from state slug to the most
recent Wayback Machine snapshot of that state's SLBC portal URL.

Used by the district page Sources & methods block to render a permanent
"archive copy" link next to each live source URL. Even when the upstream
portal goes 404, moves, or overwrites in place (J&K Bank, etc.), the
Wayback URL remains valid forever.

How it works:

- Parses SLBC_STATE_URLS out of src/lib/indicator-sources.ts (same regex
  as scripts/wayback_save.py — keep the two in sync).
- For each URL, queries the Wayback CDX API for the latest snapshot with
  HTTP 200. CDX is occasionally flaky (503, timeout); failures are
  recorded as `null` snapshots so the live URL still works.
- Always emits a `snapshotCalendar` URL (https://web.archive.org/web/*/<host>)
  which is guaranteed to work even when CDX is down — it's just a UI
  redirect to the latest snapshot.
- Writes public/sources/wayback.json (small, committed). Re-run weekly
  via the daily cron (wayback-daily.yml).

Output shape:

  {
    "generatedAt": "2026-05-14T17:35:00Z",
    "states": {
      "punjab": {
        "stateUrl": "https://slbcpunjab.pnb.bank.in",
        "snapshotCalendar": "https://web.archive.org/web/*/slbcpunjab.pnb.bank.in",
        "latest": {
          "timestamp": "20260512083322",
          "date": "2026-05-12",
          "url": "https://web.archive.org/web/20260512083322/https://slbcpunjab.pnb.bank.in/"
        }
      },
      ...
    }
  }
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error, parse

ROOT = Path(__file__).resolve().parent.parent
SLBC_SOURCES_TS = ROOT / 'src/lib/indicator-sources.ts'
OUT_PATH = ROOT / 'public/sources/wayback.json'

CDX_BASE = 'https://web.archive.org/cdx/search/cdx'
USER_AGENT = 'projectfiner-wayback-manifest/1.0 (https://projectfiner.com)'

# CDX is hosted on the Internet Archive which occasionally 503s under load.
# Retry with backoff so the cron doesn't red on flake.
RETRIES = 2
RETRY_BACKOFF_S = 4
REQUEST_TIMEOUT_S = 30  # CDX is slower for `cdx_overview` (returns the full
                        # snapshot list) than `cdx_latest` (single row).
                        # 30s is enough for the deepest sites; tighter
                        # rejects e.g. slbcchhattisgarh.com which can take
                        # 20s+ to start streaming.
INTER_REQUEST_DELAY_S = 3  # be polite, ~20req/min ceiling


def parse_slbc_urls() -> dict[str, dict]:
    """Return {state_slug: {url, aliasUrls}} from indicator-sources.ts.

    Picks up the optional `aliasUrls: ['...', '...']` field so the manifest
    builder can crawl both the current and legacy domains per state. Used
    to navigate the .bank.in migration window — see indicator-sources.ts
    header comment for context.
    """
    text = SLBC_SOURCES_TS.read_text()
    m = re.search(r'SLBC_STATE_URLS[^=]*=\s*\{(.+?)\n\};', text, re.DOTALL)
    if not m:
        print('ERROR: SLBC_STATE_URLS block not found', file=sys.stderr)
        sys.exit(1)
    block = m.group(1)
    out: dict[str, dict] = {}
    # Match each entry's full body { ... } so we can pull primary url AND
    # the optional aliasUrls array. A simpler line-by-line approach misses
    # multi-line aliasUrls literals.
    for entry in re.finditer(
        r"'([^']+)':\s*\{\s*name:\s*'[^']+',\s*url:\s*'([^']+)'([^}]*)\}",
        block,
    ):
        slug = entry.group(1)
        url = entry.group(2)
        rest = entry.group(3) or ''
        aliases: list[str] = []
        m_alias = re.search(r"aliasUrls:\s*\[(.*?)\]", rest, re.DOTALL)
        if m_alias:
            aliases = re.findall(r"'([^']+)'", m_alias.group(1))
        out[slug] = {'url': url, 'aliasUrls': aliases}
    return out


def host_only(url: str) -> str:
    """slbcpunjab.pnb.bank.in / from https://slbcpunjab.pnb.bank.in/..."""
    p = parse.urlparse(url)
    return p.netloc or url


def _fetch_via_urllib(cdx_url: str) -> str:
    req = request.Request(cdx_url, headers={'User-Agent': USER_AGENT})
    with request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
        if resp.status != 200:
            raise error.HTTPError(cdx_url, resp.status, 'non-200', resp.headers, None)
        return resp.read().decode('utf-8', errors='replace')


def _fetch_via_curl(cdx_url: str) -> str:
    """Fallback for environments where Python's SSL store is broken
    (notably Python 3.14 on macOS before the Install Certificates step)."""
    if not shutil.which('curl'):
        raise RuntimeError('curl not available')
    result = subprocess.run(
        ['curl', '-sS', '-A', USER_AGENT, '--max-time', str(REQUEST_TIMEOUT_S), cdx_url],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f'curl exit {result.returncode}: {result.stderr.strip()[:120]}')
    return result.stdout


def _cdx_query(qs_params: dict) -> list | None:
    """Run a CDX query, returning the parsed JSON rows (sans header)
    or None on persistent failure."""
    qs = parse.urlencode(qs_params)
    cdx_url = f'{CDX_BASE}?{qs}'
    last_err = ''
    for attempt in range(1, RETRIES + 1):
        try:
            payload = _fetch_via_urllib(cdx_url)
        except Exception as e:
            err = str(e)
            if 'CERTIFICATE_VERIFY_FAILED' in err or 'SSL' in err.upper():
                try:
                    payload = _fetch_via_curl(cdx_url)
                except Exception as ce:
                    last_err = f'curl: {ce}'
                    payload = None
            else:
                last_err = err
                payload = None
        if payload is None:
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF_S * attempt)
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            last_err = f'json: {e}'
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF_S * attempt)
            continue
        if not data:
            return []  # success with no results
        return data[1:] if len(data) >= 1 else []  # drop header row
    print(f'  WARN: CDX failed for {qs_params.get("url")}: {last_err}', file=sys.stderr)
    return None


def cdx_overview(url: str) -> dict | None:
    """Return aggregate stats for a URL: count, oldest, newest snapshot.

    Single CDX query that returns timestamps for every 200 snapshot.
    For very-active domains this can be 100s of rows; for thin domains
    it'll be 0-10.
    """
    rows = _cdx_query({
        'url': url,
        'output': 'json',
        'filter': 'statuscode:200',
        'fl': 'timestamp,original',
    })
    if rows is None:
        return None
    if not rows:
        return {'count': 0, 'oldest': None, 'newest': None, 'newest_original': None}
    # Rows arrive newest-last per CDX default (sorted by timestamp asc).
    oldest = rows[0]
    newest = rows[-1]
    return {
        'count': len(rows),
        'oldest': oldest[0],
        'newest': newest[0],
        'newest_original': newest[1],
    }


def cdx_latest(url: str) -> dict | None:
    """Hit CDX, return {timestamp, original} for the most recent 200 snapshot,
    or None on persistent failure / no snapshots."""
    qs = parse.urlencode({
        'url': url,
        'output': 'json',
        'limit': '-1',           # last row only
        'filter': 'statuscode:200',
        'fl': 'timestamp,original',
    })
    cdx_url = f'{CDX_BASE}?{qs}'
    last_err = ''
    for attempt in range(1, RETRIES + 1):
        # Try urllib first, fall back to curl on SSL/cert failures so the
        # script works locally on macOS Python 3.14 without "Install
        # Certificates.command" having been run.
        try:
            payload = _fetch_via_urllib(cdx_url)
        except Exception as e:
            err = str(e)
            if 'CERTIFICATE_VERIFY_FAILED' in err or 'SSL' in err.upper():
                try:
                    payload = _fetch_via_curl(cdx_url)
                except Exception as ce:
                    last_err = f'curl: {ce}'
                    payload = None
            else:
                last_err = err
                payload = None
        if payload is None:
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF_S * attempt)
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            last_err = f'json: {e}'
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF_S * attempt)
            continue
        # CDX returns [["timestamp","original"], ["YYYYMMDDhhmmss","..."]]
        if not data or len(data) < 2:
            return None  # No snapshots — not an error, just nothing yet
        ts, orig = data[-1][0], data[-1][1]
        return {'timestamp': ts, 'original': orig}
    print(f'  WARN: CDX failed for {url}: {last_err}', file=sys.stderr)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0,
                    help='Only query the first N states (debug).')
    ap.add_argument('--merge', action='store_true',
                    help='Preserve existing entries when CDX returns no result.')
    ap.add_argument('--stub', action='store_true',
                    help='Skip CDX calls. Write only the snapshotCalendar URLs '
                         '(zero network, <1s). Useful for an initial pass; the '
                         'daily cron then enriches with `latest` over time.')
    ap.add_argument('--audit', action='store_true',
                    help='Also emit public/sources/wayback-audit.json with '
                         'per-variant snapshot counts + oldest/newest. Slower '
                         '(one extra CDX call per variant) but gives a full '
                         'coverage map across primary + alias URLs.')
    args = ap.parse_args()

    state_urls = parse_slbc_urls()
    items = list(state_urls.items())
    if args.limit:
        items = items[: args.limit]

    # Merge mode: load the existing manifest so a transient CDX failure
    # doesn't wipe out yesterday's good snapshot URL.
    existing: dict = {}
    if args.merge and OUT_PATH.exists():
        try:
            existing = json.loads(OUT_PATH.read_text()).get('states', {})
        except Exception:
            existing = {}

    # Strip any wayback prefix from URLs — for upstream portals that we
    # only have an archive URL for (e.g. AP's slbcap.nic.in is dead, we
    # store a Wayback wildcard in indicator-sources.ts; CDX wants the bare
    # host instead).
    def upstream_of(u: str) -> str:
        m = re.match(r'https?://web\.archive\.org/web/[^/]+/(.+)', u)
        if m:
            inner = m.group(1)
            if not inner.startswith('http'):
                inner = 'https://' + inner.lstrip('/')
            return inner
        return u

    # Dedupe by upstream URL so the 8 NE states sharing onlineslbcne.nic.in
    # cost one CDX query instead of eight.
    cache: dict[str, dict | None] = {}

    overview_cache: dict[str, dict | None] = {}

    def ymd(ts: str) -> str:
        try:
            return f'{ts[0:4]}-{ts[4:6]}-{ts[6:8]}'
        except Exception:
            return ts

    if args.stub:
        print(f'stub mode: generating snapshotCalendar for {len(items)} states (no CDX)…')
    elif args.audit:
        print(f'auditing CDX for {len(items)} state portals (primary + aliases)…')
    else:
        print(f'querying CDX for {len(items)} state portals (primary + aliases)…')

    states_out: dict[str, dict] = {}
    for i, (slug, meta) in enumerate(items, 1):
        primary_url = meta['url']
        alias_urls = meta.get('aliasUrls', [])
        # Collect every candidate variant for this state. Order matters for
        # tiebreaks — primary first, then aliases in declaration order.
        variants = [primary_url] + list(alias_urls)

        # Primary citation always shows the canonical hostname.
        host = host_only(upstream_of(primary_url))
        calendar = f'https://web.archive.org/web/*/{host}'

        # Per-variant audit data so we can pick the deepest archive.
        variant_records: list[dict] = []
        for v in variants:
            upstream = upstream_of(v)
            if args.stub:
                variant_records.append({
                    'url': v,
                    'cdxUrl': upstream,
                    'host': host_only(upstream),
                    'count': None,
                    'oldest': None,
                    'newest': None,
                    'newestUrl': None,
                })
                continue
            cache_key = upstream
            if args.audit:
                if cache_key in overview_cache:
                    o = overview_cache[cache_key]
                    cache_hit = True
                else:
                    o = cdx_overview(upstream)
                    overview_cache[cache_key] = o
                    cache_hit = False
            else:
                # Lightweight mode: just `latest` per variant.
                if cache_key in cache:
                    r = cache[cache_key]
                    cache_hit = True
                else:
                    r = cdx_latest(upstream)
                    cache[cache_key] = r
                    cache_hit = False
                if r:
                    o = {'count': None, 'oldest': None,
                         'newest': r['timestamp'], 'newest_original': r['original']}
                else:
                    o = None
            # CDX failure: record an empty-but-typed entry so downstream
            # code doesn't trip on None.
            if o is None:
                o = {'count': 0, 'oldest': None, 'newest': None, 'newest_original': None}
            newest_ts = o.get('newest')
            newest_orig = o.get('newest_original') or upstream
            variant_records.append({
                'url': v,
                'cdxUrl': upstream,
                'host': host_only(upstream),
                'count': o.get('count'),
                'oldest': o.get('oldest'),
                'newest': newest_ts,
                'newestUrl': f'https://web.archive.org/web/{newest_ts}/{newest_orig}' if newest_ts else None,
            })
            if not args.stub and not cache_hit and i * len(variants) > 1:
                time.sleep(INTER_REQUEST_DELAY_S)

        # Pick the freshest-snapshot variant for `latest` (this drives the
        # district page's "Wayback snapshot 2026-MM-DD" link).
        freshest = None
        for vr in variant_records:
            if vr.get('newest') and (not freshest or vr['newest'] > freshest['newest']):
                freshest = vr
        # Pick the deepest-archive variant for the "history" link (the all-
        # snapshots calendar — point it at the host with the most snapshots
        # or, in the absence of counts, the host with the oldest snapshot).
        deepest = None
        for vr in variant_records:
            if args.audit:
                if vr.get('count'):
                    if not deepest or (vr['count'] or 0) > (deepest['count'] or 0):
                        deepest = vr
            else:
                if vr.get('oldest'):
                    if not deepest or (vr['oldest'] or '') < (deepest['oldest'] or 'z'):
                        deepest = vr

        latest = None
        if freshest:
            latest = {
                'timestamp': freshest['newest'],
                'date': ymd(freshest['newest']),
                'url': freshest['newestUrl'],
                'variantUrl': freshest['url'],
            }
        elif (args.merge or args.stub) and slug in existing and existing[slug].get('latest'):
            latest = existing[slug]['latest']

        out_entry = {
            'stateUrl': primary_url,
            'snapshotCalendar': calendar,
            'latest': latest,
        }
        if args.audit:
            out_entry['variants'] = [
                {
                    'url': vr['url'],
                    'host': vr['host'],
                    'snapshotCount': vr['count'],
                    'oldestDate': ymd(vr['oldest']) if vr['oldest'] else None,
                    'newestDate': ymd(vr['newest']) if vr['newest'] else None,
                    'snapshotCalendar': f'https://web.archive.org/web/*/{vr["host"]}',
                    'newestUrl': vr['newestUrl'],
                }
                for vr in variant_records
            ]
            if deepest:
                out_entry['deepestArchive'] = {
                    'host': deepest['host'],
                    'snapshotCount': deepest['count'],
                    'snapshotCalendar': f'https://web.archive.org/web/*/{deepest["host"]}',
                    'oldestDate': ymd(deepest['oldest']) if deepest.get('oldest') else None,
                }

        states_out[slug] = out_entry

        latest_marker = latest['date'] if latest else '—'
        if args.audit:
            counts = ' + '.join(str(vr.get('count') or 0) for vr in variant_records)
            print(f'  [{i:2d}/{len(items)}] {slug:22} latest={latest_marker:11} snapshots={counts}')
        else:
            print(f'  [{i:2d}/{len(items)}] {slug:22} latest={latest_marker}')

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {
        'generatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'states': states_out,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f'wrote {OUT_PATH.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
