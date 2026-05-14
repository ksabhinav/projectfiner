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
REQUEST_TIMEOUT_S = 20  # CDX usually responds in <5s; slow lookups can
                        # wait until the daily cron refreshes the manifest.
INTER_REQUEST_DELAY_S = 3  # be polite, ~20req/min ceiling


def parse_slbc_urls() -> dict[str, str]:
    """Return {state_slug: portal_url} from indicator-sources.ts."""
    text = SLBC_SOURCES_TS.read_text()
    m = re.search(r'SLBC_STATE_URLS[^=]*=\s*\{(.+?)\n\};', text, re.DOTALL)
    if not m:
        print('ERROR: SLBC_STATE_URLS block not found', file=sys.stderr)
        sys.exit(1)
    block = m.group(1)
    # Each line: 'slug': { name: '...', url: '...' },
    out: dict[str, str] = {}
    for line in block.splitlines():
        m = re.search(r"'([^']+)':\s*\{\s*name:\s*'[^']+',\s*url:\s*'([^']+)'", line)
        if m:
            out[m.group(1)] = m.group(2)
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

    if args.stub:
        print(f'stub mode: generating snapshotCalendar for {len(items)} states (no CDX)…')
    else:
        print(f'querying CDX for {len(items)} state portals…')
    states_out: dict[str, dict] = {}
    for i, (slug, url) in enumerate(items, 1):
        upstream = upstream_of(url)
        host = host_only(upstream)
        calendar = f'https://web.archive.org/web/*/{host}'
        if args.stub:
            # Preserve existing latest snapshot if any
            existing_latest = existing.get(slug, {}).get('latest') if args.merge else None
            result = None
            cache_hit = False
        else:
            cache_hit = upstream in cache
            if cache_hit:
                result = cache[upstream]
            else:
                result = cdx_latest(upstream)
                cache[upstream] = result
        latest = None
        if result:
            ts = result['timestamp']
            try:
                date_pretty = f'{ts[0:4]}-{ts[4:6]}-{ts[6:8]}'
            except Exception:
                date_pretty = ts
            latest = {
                'timestamp': ts,
                'date': date_pretty,
                'url': f'https://web.archive.org/web/{ts}/{result["original"]}',
            }
        elif (args.merge or args.stub) and slug in existing and existing[slug].get('latest'):
            # Keep previous good entry rather than nulling it out
            latest = existing[slug]['latest']

        states_out[slug] = {
            'stateUrl': url,
            'snapshotCalendar': calendar,
            'latest': latest,
        }
        marker = latest['date'] if latest else '—'
        cached_tag = ' (cached)' if cache_hit else ''
        print(f'  [{i:2d}/{len(items)}] {slug:22} {marker}{cached_tag}')
        if not args.stub and i < len(items) and not cache_hit:
            time.sleep(INTER_REQUEST_DELAY_S)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {
        'generatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'states': states_out,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f'wrote {OUT_PATH.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
