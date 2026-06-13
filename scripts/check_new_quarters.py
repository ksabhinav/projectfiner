#!/usr/bin/env python3
"""
New-quarter detector — watch SLBC state portals for newly published
meeting documents.

The failure mode this kills: a state silently falls 4 quarters behind
because nobody notices the SLBC portal published a new agenda booklet
(staleness queue as of Jun 2026: Uttarakhand 24 months, AP 18 months,
Karnataka ~1 year).

How it works:

- Parses SLBC_STATE_URLS out of src/lib/indicator-sources.ts (same regex
  as scripts/wayback_save.py and db/build_wayback_manifest.py — keep the
  three in sync). That TS map is the single source of truth for portal
  URLs; this script only carries per-state *watch path* overrides for the
  known meeting-list pages (documented in WATCH_OVERRIDES below).
- Fetches each unique watch URL once (states sharing a portal — the 9
  NE-portal states on onlineslbcne.nic.in — cost one fetch total).
- Extracts a normalized fingerprint: every <a href> ending in
  .pdf/.xlsx/.xls/.zip/.doc/.docx/.rar, absolute-ized, query strings
  stripped, plus the link text, sorted. Portals with no document links
  (JS-only listings) fall back to a content hash of the normalized HTML
  and are flagged low-signal.
- Compares against the committed snapshot
  public/sources/portal-snapshots.json and prints a per-state diff:
  NEW links (the interesting event — likely a new quarter), REMOVED
  links (jkslbc.com-style in-place overwrites — also interesting, see
  CLAUDE.md gotcha #73), and unreachable portals (transient — tracked
  via consecutiveFailures, never alerted on).

Run modes:

  python3 scripts/check_new_quarters.py                 # report only
  python3 scripts/check_new_quarters.py --update        # also refresh snapshot
  python3 scripts/check_new_quarters.py --report-md F   # write the alert
                                                        # markdown to F (file
                                                        # only created when
                                                        # there is something
                                                        # to alert on — the
                                                        # weekly workflow keys
                                                        # the gh-issue step
                                                        # off its existence)

Politeness: one fetch per URL, 2s delay between portals, 20s timeout.
Network errors never crash the run — per-portal try/except, like the
wayback scripts. Stdlib only. urllib first with a curl fallback for the
macOS Python 3.14 broken-SSL-store case (same pattern as
db/build_wayback_manifest.py).
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import json
import re
import shutil
import ssl
import subprocess
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parent.parent
SLBC_SOURCES_TS = ROOT / 'src/lib/indicator-sources.ts'
SNAPSHOT_PATH = ROOT / 'public/sources/portal-snapshots.json'

USER_AGENT = 'projectfiner-quarter-watch/1.0 (https://projectfiner.com)'
REQUEST_TIMEOUT_S = 20
INTER_PORTAL_DELAY_S = 2.0
DOC_EXTS = ('.pdf', '.xlsx', '.xls', '.zip', '.doc', '.docx', '.rar')

# ── Per-state watch configuration ──────────────────────────────────────────
#
# The SLBC_STATE_URLS entry is usually the portal homepage. Where we know a
# better meeting-list page, override it here. Where the portal is dead,
# mark skip: true. All overrides verified by live probe on 2026-06-10.
#
# Keys:
#   watchUrl  — fetch this instead of the TS map's primary URL
#   skip      — don't fetch at all (portal dead); still recorded in snapshot
#   insecure  — fetch with certificate verification disabled (curl -sk
#               equivalent); for portals with broken SSL chains
#   note      — human-readable reason, surfaced in the report
WATCH_OVERRIDES: dict[str, dict] = {
    # slbcap.nic.in is dead/unreachable (DNS does not resolve; probe
    # 2026-06-10 curl exit 6). The TS map's "url" for AP is itself a
    # Wayback calendar link, not a live portal. AP data comes from the
    # Wayback backfill pipeline — nothing live to watch.
    'andhra-pradesh': {
        'skip': True,
        'note': 'slbcap.nic.in dead (DNS unresolvable); AP sourced from Wayback backfill only',
    },
    # slbcbihar.com serves a broken SSL chain — needs `curl -sk`
    # (CLAUDE.md, Bihar pipeline). Watch URL in the TS map is already the
    # meeting-list page (SlBCHeldMeeting.aspx, 91 doc links on probe).
    'bihar': {'insecure': True, 'note': 'broken SSL chain — verification disabled'},
    # slbctripura.pnb.bank.in serves a self-signed certificate (probe
    # 2026-06-10). Watch URL in the TS map is already the quarterly
    # back-papers page.
    'tripura': {'insecure': True, 'note': 'self-signed certificate — verification disabled'},
    # bankofmaharashtra.in (the TS primary, where SLBC content lives) times
    # out / fails DNS from probe environments; the RBI-mandated alias
    # bankofmaharashtra.bank.in responds and carries ~42 static doc links.
    'maharashtra': {
        'watchUrl': 'https://bankofmaharashtra.bank.in',
        'note': 'apex .in domain unreachable from runners — watching the .bank.in alias',
    },
    # Homepage has 24 doc links but the real meeting-document feed is the
    # CQR reports page (164 doc links; FINER's Telangana pipeline extracts
    # from these CQR Annexure PDFs — see CLAUDE.md Telangana section).
    'telangana': {
        'watchUrl': 'https://telanganaslbc.com/reports.aspx',
        'note': 'watching CQR reports page (the per-quarter annexure feed)',
    },
    # HTTPS handshake is broken on slbcup.com (curl exit 35, even with -k);
    # plain HTTP serves the agenda-PDF listing fine (11 doc links on probe).
    'uttar-pradesh': {
        'watchUrl': 'http://slbcup.com',
        'note': 'HTTPS handshake broken — watching plain-HTTP homepage',
    },
    # slbcwb.com does not resolve (probe 2026-06-10, curl exit 6 on apex,
    # www, http and https — no A/NS records). The domain appears to have
    # lapsed. Needs manual follow-up to find WB SLBC's new home.
    'west-bengal': {
        'skip': True,
        'note': 'slbcwb.com DNS dead as of 2026-06-10 — portal may have moved, needs manual follow-up',
    },
}

# Portals known to render their listings via JS or behind forms, where the
# static HTML carries few/no document links. We still watch them, but a
# fingerprint change there is the content hash flipping, not link diffs —
# treat as a low-confidence hint, not a confirmed new quarter.
LOW_SIGNAL_NOTES = {
    'https://onlineslbcne.nic.in':
        'form-driven portal (quarter/year POST) — homepage hash is the only static signal',
}


# ── SLBC_STATE_URLS parsing (single source of truth) ───────────────────────

def parse_slbc_urls() -> dict[str, dict]:
    """Return {state_slug: {name, url, aliasUrls}} from indicator-sources.ts.

    Same regex family as db/build_wayback_manifest.py:parse_slbc_urls and
    scripts/wayback_save.py:load_upstream_slbc_urls — keep in sync.
    """
    if not SLBC_SOURCES_TS.exists():
        print(f'ERROR: {SLBC_SOURCES_TS} not found', file=sys.stderr)
        sys.exit(1)
    text = SLBC_SOURCES_TS.read_text()
    m = re.search(r'SLBC_STATE_URLS[^=]*=\s*\{(.+?)\n\};', text, re.DOTALL)
    if not m:
        print('ERROR: SLBC_STATE_URLS block not found', file=sys.stderr)
        sys.exit(1)
    block = m.group(1)
    out: dict[str, dict] = {}
    for entry in re.finditer(
        r"'([^']+)':\s*\{\s*name:\s*'([^']+)',\s*url:\s*'([^']+)'([^}]*)\}",
        block,
    ):
        slug, name, url, rest = entry.group(1), entry.group(2), entry.group(3), entry.group(4) or ''
        aliases: list[str] = []
        m_alias = re.search(r"aliasUrls:\s*\[(.*?)\]", rest, re.DOTALL)
        if m_alias:
            aliases = re.findall(r"'([^']+)'", m_alias.group(1))
        out[slug] = {'name': name, 'url': url, 'aliasUrls': aliases}
    return out


def build_watchlist() -> dict[str, dict]:
    """Group states by their effective watch URL.

    Returns {watch_url: {states: [...], stateNames: [...], insecure: bool,
                         skip: bool, note: str}}.
    States sharing a portal (the 9 NE-portal states) collapse into one
    entry so we fetch each URL exactly once per run.
    """
    slbc = parse_slbc_urls()
    portals: dict[str, dict] = {}
    for slug, info in slbc.items():
        ov = WATCH_OVERRIDES.get(slug, {})
        url = ov.get('watchUrl') or info['url']
        skip = bool(ov.get('skip'))
        entry = portals.setdefault(url, {
            'states': [], 'stateNames': [],
            'insecure': False, 'skip': skip, 'notes': [],
        })
        entry['states'].append(slug)
        entry['stateNames'].append(info['name'])
        entry['insecure'] = entry['insecure'] or bool(ov.get('insecure'))
        entry['skip'] = entry['skip'] or skip  # any state marked skip → portal skipped
        if ov.get('note'):
            entry['notes'].append(ov['note'])
        if url in LOW_SIGNAL_NOTES and LOW_SIGNAL_NOTES[url] not in entry['notes']:
            entry['notes'].append(LOW_SIGNAL_NOTES[url])
    return portals


# ── Fetching (urllib, curl fallback) ───────────────────────────────────────

def _fetch_via_urllib(url: str, insecure: bool) -> str:
    req = request.Request(url, headers={'User-Agent': USER_AGENT})
    ctx = None
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with request.urlopen(req, timeout=REQUEST_TIMEOUT_S, context=ctx) as resp:
        if resp.status != 200:
            raise error.HTTPError(url, resp.status, 'non-200', resp.headers, None)
        return resp.read().decode('utf-8', errors='replace')


def _fetch_via_curl(url: str, insecure: bool) -> str:
    """Fallback for broken Python SSL stores (macOS Python 3.14) and for
    portals whose TLS stack urllib refuses (same pattern as
    db/build_wayback_manifest.py:_fetch_via_curl)."""
    if not shutil.which('curl'):
        raise RuntimeError('curl not available')
    cmd = ['curl', '-sS', '-L', '-A', USER_AGENT,
           '--max-time', str(REQUEST_TIMEOUT_S), url]
    if insecure:
        cmd.insert(1, '-k')
    # capture bytes, not text — some portals serve non-UTF8 pages
    # (slbctripura) that would crash subprocess's implicit decode
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        err = result.stderr.decode('utf-8', errors='replace').strip()[:120]
        raise RuntimeError(f'curl exit {result.returncode}: {err}')
    return result.stdout.decode('utf-8', errors='replace')


def fetch_page(url: str, insecure: bool) -> str:
    try:
        return _fetch_via_urllib(url, insecure)
    except Exception as e:
        err = str(e)
        # SSL trouble (or anything urllib chokes on that curl might not):
        # try curl before giving up. Cheap and covers the macOS 3.14 case.
        try:
            return _fetch_via_curl(url, insecure or 'SSL' in err.upper()
                                   or 'CERTIFICATE' in err.upper())
        except Exception as ce:
            raise RuntimeError(f'urllib: {err[:120]} / curl: {ce}') from None


# ── Fingerprinting ─────────────────────────────────────────────────────────

class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href')
            self._href = href
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self._href is not None:
            text = ' '.join(''.join(self._text).split())
            self.links.append((self._href, text))
            self._href = None


def extract_doc_links(page: str, base_url: str) -> list[dict]:
    """Normalized fingerprint: all hrefs ending in a document extension,
    absolute-ized against base_url, query strings + fragments stripped,
    deduped, sorted by URL."""
    parser = _LinkParser()
    try:
        parser.feed(page)
    except Exception:
        pass  # malformed HTML — keep whatever we got
    seen: dict[str, str] = {}
    for href, text in parser.links:
        if not href:
            continue
        href = html_mod.unescape(href).strip()
        absolute = parse.urljoin(base_url, href)
        split = parse.urlsplit(absolute)
        path = split.path
        if not path.lower().endswith(DOC_EXTS):
            continue
        clean = parse.urlunsplit((split.scheme, split.netloc, path, '', ''))
        if clean not in seen or (not seen[clean] and text):
            seen[clean] = text
    return [{'url': u, 'text': seen[u]} for u in sorted(seen)]


_SCRIPT_RE = re.compile(r'<script\b.*?</script>', re.DOTALL | re.IGNORECASE)
_STYLE_RE = re.compile(r'<style\b.*?</style>', re.DOTALL | re.IGNORECASE)
_COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)
_INPUT_RE = re.compile(r'<input\b[^>]*>', re.IGNORECASE)  # __VIEWSTATE, CSRF tokens
_META_RE = re.compile(r'<meta\b[^>]*>', re.IGNORECASE)


def content_hash(page: str) -> str:
    """Stable-ish hash of the page body. Strips scripts, styles, comments,
    <input> (ASP.NET __VIEWSTATE / CSRF tokens churn per request) and
    <meta>, then collapses whitespace, so only real content changes flip
    the hash."""
    body = _SCRIPT_RE.sub('', page)
    body = _STYLE_RE.sub('', body)
    body = _COMMENT_RE.sub('', body)
    body = _INPUT_RE.sub('', body)
    body = _META_RE.sub('', body)
    body = ' '.join(body.split())
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


# ── Snapshot I/O + diff ────────────────────────────────────────────────────

def load_snapshot() -> dict:
    if SNAPSHOT_PATH.exists():
        try:
            return json.loads(SNAPSHOT_PATH.read_text())
        except json.JSONDecodeError:
            print(f'WARN: {SNAPSHOT_PATH} unparseable — treating as empty', file=sys.stderr)
    return {'generatedAt': None, 'portals': {}}


def run_checks(portals: dict[str, dict]) -> dict[str, dict]:
    """Fetch every non-skipped portal once. Returns
    {url: {ok, error?, docLinks?, contentHash?}}."""
    results: dict[str, dict] = {}
    todo = [(u, cfg) for u, cfg in portals.items() if not cfg['skip']]
    total = len(todo)
    for i, (url, cfg) in enumerate(todo, 1):
        label = ', '.join(cfg['stateNames'])
        try:
            page = fetch_page(url, cfg['insecure'])
            links = extract_doc_links(page, url)
            results[url] = {
                'ok': True,
                'docLinks': links,
                'contentHash': content_hash(page),
            }
            print(f'  [{i:2d}/{total}] ok    {url}  ({len(links)} doc links) — {label}', flush=True)
        except Exception as e:
            results[url] = {'ok': False, 'error': str(e)[:200]}
            print(f'  [{i:2d}/{total}] FAIL  {url}  ({str(e)[:100]}) — {label}', flush=True)
        if i < total:
            time.sleep(INTER_PORTAL_DELAY_S)
    return results


def diff_portal(old: dict | None, new: dict) -> dict:
    """Compare a portal's previous snapshot entry with a fresh result.
    Returns {newLinks, removedLinks, hashChanged}."""
    old_links = {l['url']: l.get('text', '') for l in (old or {}).get('docLinks', [])}
    new_links = {l['url']: l.get('text', '') for l in new.get('docLinks', [])}
    added = [{'url': u, 'text': new_links[u]} for u in sorted(new_links.keys() - old_links.keys())]
    removed = [{'url': u, 'text': old_links[u]} for u in sorted(old_links.keys() - new_links.keys())]
    hash_changed = bool(old) and old.get('contentHash') and \
        old['contentHash'] != new.get('contentHash')
    return {'newLinks': added, 'removedLinks': removed, 'hashChanged': hash_changed}


def build_report(portals: dict[str, dict], results: dict[str, dict],
                 prev: dict, first_run: bool) -> tuple[str, list[str]]:
    """Returns (alert_markdown, affected_state_names). alert_markdown is ''
    when there is nothing issue-worthy."""
    sections: list[str] = []
    affected: list[str] = []

    for url, cfg in portals.items():
        if cfg['skip']:
            continue
        res = results.get(url)
        if not res or not res['ok']:
            continue  # unreachable — tracked, never alerted
        old = prev.get('portals', {}).get(url)
        if first_run or old is None:
            continue  # baseline — nothing to diff against
        d = diff_portal(old, res)
        had_links = bool(old.get('docLinks')) or bool(res.get('docLinks'))
        lines: list[str] = []
        if d['newLinks']:
            lines.append(f"**{len(d['newLinks'])} NEW document link(s):**")
            for l in d['newLinks'][:40]:
                lines.append(f"- [{l['text'] or l['url'].rsplit('/', 1)[-1]}]({l['url']})")
            if len(d['newLinks']) > 40:
                lines.append(f"- … and {len(d['newLinks']) - 40} more")
        if d['removedLinks']:
            lines.append(f"**{len(d['removedLinks'])} REMOVED document link(s)** "
                         "(possible in-place overwrite — jkslbc.com pattern, "
                         "snapshot to Wayback before it's gone):")
            for l in d['removedLinks'][:40]:
                lines.append(f"- ~~{l['text'] or l['url'].rsplit('/', 1)[-1]}~~ `{l['url']}`")
            if len(d['removedLinks']) > 40:
                lines.append(f"- … and {len(d['removedLinks']) - 40} more")
        # Hash flip only matters as a signal on portals with no static doc
        # links OR portals explicitly flagged as form/JS-driven (the NE
        # portal serves 9 states behind a quarter/year POST form — its one
        # static link never changes, the page hash is the only signal).
        # Everywhere else a hash flip is churn noise.
        if d['hashChanged'] and (not had_links or url in LOW_SIGNAL_NOTES):
            lines.append('**Page content changed** (low-signal: JS/form-driven portal '
                         'with no static document links — verify manually).')
        if lines:
            names = ', '.join(cfg['stateNames'])
            note = f"  \n_({'; '.join(cfg['notes'])})_" if cfg['notes'] else ''
            sections.append(f"### {names}\nPortal: {url}{note}\n\n" + '\n'.join(lines))
            affected.extend(cfg['stateNames'])

    if not sections:
        return '', []
    title_states = ', '.join(affected[:6]) + (' …' if len(affected) > 6 else '')
    md = (f"# New SLBC documents detected: {title_states}\n\n"
          f"Weekly portal check ({datetime.now(timezone.utc).strftime('%Y-%m-%d')}) "
          f"found changes on the portals below. Likely a new quarterly meeting "
          f"was published — check whether FINER's extraction pipeline needs a run.\n\n"
          + '\n\n'.join(sections) + '\n')
    return md, affected


def build_new_snapshot(portals: dict[str, dict], results: dict[str, dict],
                       prev: dict) -> dict:
    out = {'generatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
           'portals': {}}
    prev_portals = prev.get('portals', {})
    for url, cfg in portals.items():
        old = prev_portals.get(url, {})
        entry = {
            'states': cfg['states'],
            'skip': cfg['skip'],
            'notes': cfg['notes'],
            'consecutiveFailures': 0,
            'lastSuccess': old.get('lastSuccess'),
            'contentHash': old.get('contentHash'),
            'docLinks': old.get('docLinks', []),
        }
        if cfg['skip']:
            entry['consecutiveFailures'] = old.get('consecutiveFailures', 0)
        else:
            res = results.get(url, {})
            if res.get('ok'):
                entry['lastSuccess'] = out['generatedAt']
                entry['contentHash'] = res['contentHash']
                entry['docLinks'] = res['docLinks']
                entry['lowSignal'] = not res['docLinks']
            else:
                # transient failure: keep the old fingerprint so the next
                # successful run diffs against real data, not a hole
                entry['consecutiveFailures'] = old.get('consecutiveFailures', 0) + 1
                entry['lastError'] = res.get('error')
                entry['lowSignal'] = old.get('lowSignal', False)
        out['portals'][url] = entry
    return out


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Check SLBC portals for new meeting documents.')
    ap.add_argument('--update', action='store_true',
                    help='Write the refreshed snapshot to public/sources/portal-snapshots.json')
    ap.add_argument('--report-md', metavar='PATH',
                    help='Write the alert markdown here (file only created when '
                         'there are new/removed links — workflow keys off existence)')
    args = ap.parse_args()

    portals = build_watchlist()
    prev = load_snapshot()
    first_run = not prev.get('portals')

    n_watch = sum(1 for c in portals.values() if not c['skip'])
    n_skip = len(portals) - n_watch
    print(f'checking {n_watch} portal(s) ({n_skip} skipped as dead) '
          f'covering {sum(len(c["states"]) for c in portals.values())} states')
    for url, cfg in portals.items():
        if cfg['skip']:
            print(f'  [skip ] {url} — {", ".join(cfg["stateNames"])}'
                  f' ({"; ".join(cfg["notes"])})')

    results = run_checks(portals)

    report_md, affected = build_report(portals, results, prev, first_run)

    # Console summary
    ok = sum(1 for r in results.values() if r['ok'])
    fail = len(results) - ok
    print(f'\ndone: {ok} reachable, {fail} unreachable, {n_skip} skipped')
    if first_run:
        print('first run — baseline only, no diff to report')
    elif report_md:
        print(f'CHANGES DETECTED for: {", ".join(affected)}')
        print(report_md)
    else:
        print('no new or removed document links since last snapshot')

    for url, r in results.items():
        if not r['ok']:
            prior = prev.get('portals', {}).get(url, {}).get('consecutiveFailures', 0)
            print(f'  unreachable ({prior + 1} consecutive): {url} — {r["error"]}')

    if args.report_md and report_md:
        Path(args.report_md).write_text(report_md)
        print(f'alert report written to {args.report_md}')

    if args.update:
        snap = build_new_snapshot(portals, results, prev)
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + '\n')
        n_links = sum(len(p['docLinks']) for p in snap['portals'].values())
        print(f'snapshot updated: {SNAPSHOT_PATH} '
              f'({len(snap["portals"])} portals, {n_links} doc links)')


if __name__ == '__main__':
    main()
