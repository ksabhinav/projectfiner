#!/usr/bin/env python3
"""
Snapshot Project FINER URLs to the Wayback Machine via Save Page Now (SPN2).

Reads public/sitemap.xml, extracts URLs, and POSTs each to
https://web.archive.org/save with a polite delay between calls. Anonymous
SPN tolerates ~4-15 requests/minute, so we throttle to 1 every 8 seconds
(~7/min) by default.

Two run modes:

  --mode high-value       Snapshot only top-of-funnel pages: homepage, /about,
                          /ask, /analysis/*, /downloads, /slbc-data, plus every
                          state download page (~40 URLs). ≈5 min runtime.

  --mode districts-cohort Snapshot a 1/7th rotation of /district/<state>/<d>/
                          pages so every district gets refreshed roughly once
                          a week. The cohort is selected deterministically by
                          (day_of_year mod 7) so re-runs hit the same set.
                          ≈15-20 min runtime on ~120 URLs.

  --mode upstream-slbc    Snapshot the *upstream* SLBC state portals
                          (slbcpunjab.pnb.bank.in, jkslbc.com, slbchp.com,
                          slbckerala.com, …) parsed out of
                          src/lib/indicator-sources.ts. The high-leverage
                          run — it protects data we don't control. ~31 URLs,
                          ≈5 min runtime.

  --mode all              Everything. Used for a manual catch-up; the daily
                          cron runs the three other modes separately so
                          rate-limit issues in one don't block the others.

Environment:
  WAYBACK_ACCESS_KEY / WAYBACK_SECRET     Optional IA S3 keys. If set, sent
                                          as `Authorization: LOW <k>:<s>`
                                          which raises the rate limit and
                                          surfaces the snapshot job ID.

The script is best-effort: a single SPN failure logs a line and moves on
rather than failing the whole cron. Wayback returns 429 when rate-limited
and we back off for 30s, then continue.
"""
from __future__ import annotations
import argparse
import os
import re
import sys
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parent.parent
SITEMAP = ROOT / 'public/sitemap.xml'
SLBC_SOURCES_TS = ROOT / 'src/lib/indicator-sources.ts'

SPN_URL = 'https://web.archive.org/save'
USER_AGENT = 'projectfiner-wayback/1.0 (https://projectfiner.com)'
DEFAULT_DELAY_S = 8.0  # ~7 requests/min — under anonymous SPN ceiling


def load_sitemap_urls() -> list[str]:
    """Pull every <loc> URL from the sitemap."""
    if not SITEMAP.exists():
        print(f'ERROR: {SITEMAP} not found', file=sys.stderr)
        sys.exit(1)
    text = SITEMAP.read_text()
    return re.findall(r'<loc>([^<]+)</loc>', text)


def load_upstream_slbc_urls() -> list[str]:
    """Parse SLBC_STATE_URLS out of src/lib/indicator-sources.ts.

    Format is a const map with `'<slug>': { name: '...', url: '...' },`
    entries. We extract every URL literal and dedupe — several NE states
    share onlineslbcne.nic.in so we only ping it once.
    """
    if not SLBC_SOURCES_TS.exists():
        print(f'ERROR: {SLBC_SOURCES_TS} not found', file=sys.stderr)
        sys.exit(1)
    text = SLBC_SOURCES_TS.read_text()
    # Scope to the SLBC_STATE_URLS map so we don't accidentally grab unrelated
    # URLs from the file (e.g. PhonePe Pulse, RBI, NFHS — those have their
    # own pan-India archive lifecycles and aren't worth daily snapshots).
    m = re.search(r'SLBC_STATE_URLS[^=]*=\s*\{(.+?)\n\};', text, re.DOTALL)
    if not m:
        print('ERROR: SLBC_STATE_URLS block not found in indicator-sources.ts',
              file=sys.stderr)
        sys.exit(1)
    block = m.group(1)
    urls = re.findall(r"url:\s*'([^']+)'", block)
    # Dedupe in input order — Python 3.7+ dict preserves insertion order.
    return list(dict.fromkeys(urls))


def partition(urls: list[str]) -> tuple[list[str], list[str]]:
    """Split URLs into (high-value, district-cohort) buckets."""
    high_value: list[str] = []
    districts: list[str] = []
    for u in urls:
        if '/district/' in u:
            districts.append(u)
        else:
            high_value.append(u)
    return high_value, districts


def pick_district_cohort(districts: list[str]) -> list[str]:
    """Return today's 1/7th rotation of district URLs.

    Deterministic on day-of-year so a re-run hits the same cohort and we
    cover every district once a week.
    """
    if not districts:
        return []
    day = time.gmtime().tm_yday  # 1..366
    cohort_idx = day % 7
    return [u for i, u in enumerate(sorted(districts)) if i % 7 == cohort_idx]


def save_one(url: str) -> str:
    """POST to SPN. Returns short status code ('ok', '429', 'err: …')."""
    data = f'url={url}&capture_all=1&skip_first_archive=1'.encode('utf-8')
    req = request.Request(SPN_URL, data=data, method='POST')
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req.add_header('Accept', 'application/json')

    access = os.environ.get('WAYBACK_ACCESS_KEY')
    secret = os.environ.get('WAYBACK_SECRET')
    if access and secret:
        req.add_header('Authorization', f'LOW {access}:{secret}')

    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read(2048).decode('utf-8', errors='replace')
            # SPN returns a small HTML/JSON snippet with the queued job-id
            # on success. We don't parse it; just check it's not an error.
            if resp.status == 200:
                return 'ok'
            return f'http {resp.status}: {body[:120]}'
    except error.HTTPError as e:
        if e.code == 429:
            return '429'
        return f'err {e.code}: {e.reason}'
    except Exception as e:
        return f'err: {e}'


def run(urls: list[str], delay_s: float = DEFAULT_DELAY_S) -> None:
    if not urls:
        print('no URLs to snapshot')
        return
    total = len(urls)
    print(f'snapshotting {total} URL(s) to Wayback (delay {delay_s:g}s/request)')
    ok = 0
    failed = 0
    for i, url in enumerate(urls, 1):
        status = save_one(url)
        if status == 'ok':
            ok += 1
            mark = 'ok '
        elif status == '429':
            failed += 1
            mark = '429'
            print(f'  [{i:3d}/{total}] {mark}  {url}  — backing off 30s', flush=True)
            time.sleep(30)
            continue
        else:
            failed += 1
            mark = 'FAIL'
            print(f'  [{i:3d}/{total}] {mark}  {url}  ({status})', flush=True)
            time.sleep(delay_s)
            continue
        print(f'  [{i:3d}/{total}] {mark}  {url}', flush=True)
        if i < total:
            time.sleep(delay_s)
    print(f'done: {ok} ok, {failed} failed (of {total})')


def main():
    ap = argparse.ArgumentParser(description='Snapshot Project FINER URLs to the Wayback Machine.')
    ap.add_argument('--mode',
                    choices=['high-value', 'districts-cohort', 'upstream-slbc', 'all'],
                    default='high-value')
    ap.add_argument('--delay', type=float, default=DEFAULT_DELAY_S,
                    help='Seconds between SPN POSTs (anonymous limit ≈ 8s).')
    ap.add_argument('--limit', type=int, default=0,
                    help='Cap the number of URLs (for quick local tests).')
    args = ap.parse_args()

    urls = load_sitemap_urls()
    high, districts = partition(urls)

    if args.mode == 'high-value':
        target = high
    elif args.mode == 'districts-cohort':
        target = pick_district_cohort(districts)
    elif args.mode == 'upstream-slbc':
        target = load_upstream_slbc_urls()
    else:  # all
        target = high + pick_district_cohort(districts) + load_upstream_slbc_urls()

    if args.limit:
        target = target[: args.limit]

    run(target, delay_s=args.delay)


if __name__ == '__main__':
    main()
