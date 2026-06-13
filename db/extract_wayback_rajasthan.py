#!/usr/bin/env python3
"""
Extract district-wise tables from the Rajasthan Wayback PDF haul.

Mirror of db/extract_wayback_kerala.py for Rajasthan's districts (33
pre-2023 canonical + the 2023 reorg names that appear in recent PDFs).
Same output shape; downstream normalization is per-PDF curation.

Run AFTER db/fetch_wayback_pdfs.py rajasthan slbcrajasthan.in:
    python3 db/extract_wayback_rajasthan.py

Notes:
- Most older Rajasthan SLBC PDFs are scanned images / Devanagari-encoded
  minutes that pdfplumber can't parse — those count as 'no district table'
  (no OCR in this pass). The text-native annexures (ACP achievement, KCC,
  Banking Network, deposits/advances) are the recoverable yield.
- RAW dump only: every cell verbatim from the PDF. NO unit conversion
  (Rajasthan annexures mix "Amt in Thousands" and "Amt in Rs. Lacs" —
  the headers are preserved so downstream curation can convert).
- Wayback-truncated captures (status == 'truncated', gotcha #87) are
  skipped: the snapshot itself was capped at 1 MB and is incomplete.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'rajasthan'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback'
OUT_DIR = WAYBACK_DIR / 'extracted'

PDF_TIME_BUDGET_S = 120  # per-PDF wall-clock cap (some agendas are 100+ pages)
MIN_UNIQUE_DISTRICTS = 10  # Rajasthan has 33+ districts; >=10 = district-wise


# ---------------------------------------------------------------------------
# Districts: 33 pre-2023 canonical + 2023-reorg names seen in recent PDFs.
# Keys are lowercase with all non-letters stripped.
# ---------------------------------------------------------------------------
RAJ_DISTRICT_ALIASES = {
    # 33 pre-2023 canonical
    'ajmer': 'Ajmer',
    'alwar': 'Alwar',
    'banswara': 'Banswara',
    'baran': 'Baran',
    'barmer': 'Barmer',
    'bharatpur': 'Bharatpur',
    'bhilwara': 'Bhilwara',
    'bikaner': 'Bikaner',
    'bundi': 'Bundi',
    'chittorgarh': 'Chittorgarh',
    'chittaurgarh': 'Chittorgarh',
    'chitorgarh': 'Chittorgarh',
    'churu': 'Churu',
    'dausa': 'Dausa',
    'dholpur': 'Dholpur',
    'dhaulpur': 'Dholpur',
    'dungarpur': 'Dungarpur',
    'hanumangarh': 'Hanumangarh',
    'jaipur': 'Jaipur',
    'jaisalmer': 'Jaisalmer',
    'jalore': 'Jalore',
    'jalor': 'Jalore',
    'jhalawar': 'Jhalawar',
    'jhunjhunu': 'Jhunjhunu',
    'jhunjhunun': 'Jhunjhunu',
    'jodhpur': 'Jodhpur',
    'karauli': 'Karauli',
    'kota': 'Kota',
    'nagaur': 'Nagaur',
    'nagour': 'Nagaur',
    'pali': 'Pali',
    'pratapgarh': 'Pratapgarh',
    'rajsamand': 'Rajsamand',
    'sawaimadhopur': 'Sawai Madhopur',
    'sikar': 'Sikar',
    'sirohi': 'Sirohi',
    'sriganganagar': 'Sri Ganganagar',
    'ganganagar': 'Sri Ganganagar',
    'tonk': 'Tonk',
    'udaipur': 'Udaipur',
    # 2023 reorg districts (may appear in recent PDFs)
    'phalodi': 'Phalodi',
    'balotra': 'Balotra',
    'beawar': 'Beawar',
    'deeg': 'Deeg',
    'didwanakuchaman': 'Didwana-Kuchaman',
    'kotputlibehror': 'Kotputli-Behror',
    'khairthaltijara': 'Khairthal-Tijara',
    'salumbar': 'Salumbar',
    'salumber': 'Salumbar',
    'sanchore': 'Sanchore',
    'anupgarh': 'Anupgarh',
    'dudu': 'Dudu',
    'gangapurcity': 'Gangapur City',
    'jaipurrural': 'Jaipur Rural',
    'jodhpurrural': 'Jodhpur Rural',
    'kekri': 'Kekri',
    'neemkathana': 'Neem Ka Thana',
    'shahpura': 'Shahpura',
}

# Aliases sorted longest-first so contains-matching prefers the most
# specific name (e.g. 'jaipurrural' before 'jaipur', 'kotputlibehror'
# before 'kota').
_ALIASES_BY_LEN = sorted(RAJ_DISTRICT_ALIASES.items(),
                         key=lambda kv: -len(kv[0]))


def canon_district(s: str | None) -> str | None:
    """Return canonical Rajasthan district name or None."""
    if not s:
        return None
    key = re.sub(r'[^a-z]', '', s.lower())
    if not key:
        return None
    if key in RAJ_DISTRICT_ALIASES:
        return RAJ_DISTRICT_ALIASES[key]
    # Loose contains for cells with stray characters ("1. Ajmer", "Ajmer*").
    # Require alias length >= 5 to avoid false hits from short names
    # (kota/pali/tonk/deeg/dudu must match exactly).
    for alias, canon in _ALIASES_BY_LEN:
        if len(alias) >= 5 and alias in key:
            return canon
    return None


MONTHS = {
    'jan': '01', 'january': '01', 'feb': '02', 'february': '02',
    'mar': '03', 'march': '03', 'apr': '04', 'april': '04',
    'may': '05', 'jun': '06', 'june': '06',
    'jul': '07', 'july': '07', 'aug': '08', 'august': '08',
    'sep': '09', 'sept': '09', 'september': '09', 'oct': '10',
    'october': '10', 'nov': '11', 'november': '11', 'dec': '12',
    'december': '12',
}


def _month_code(name: str) -> str | None:
    low = name.lower()
    return MONTHS.get(low) or MONTHS.get(low[:4]) or MONTHS.get(low[:3])


def infer_period(text: str) -> str | None:
    """Pull the reporting period from title/page text.

    Rajasthan annexure headings look like:
        "As On 31st December 2023" / "As On 31.12.2018"
        "Quarter ended --- Dec 2024" / "quarter ended September 2016"
    Returns 'YYYY-MM' or None when nothing concrete is found (no guessing).
    """
    # Date range "from 01-04-2024 to 31-12-2024" → take the period END.
    m = re.search(r'to\s+(\d{1,2})[./-](\d{2})[./-](\d{4})', text, re.IGNORECASE)
    if m and 1 <= int(m.group(2)) <= 12:
        return f'{m.group(3)}-{m.group(2)}'
    # dd.mm.yyyy or dd/mm/yyyy or dd-mm-yyyy
    m = re.search(r'(?:as\s+(?:on|at)\D{0,4})?(\d{1,2})[./-](\d{2})[./-](\d{4})', text, re.IGNORECASE)
    if m and 1 <= int(m.group(2)) <= 12:
        return f'{m.group(3)}-{m.group(2)}'
    # "as on 31st December 2023" / "as at March, 2019"
    m = re.search(r'as\s+(?:on|at)\s+(?:\d{1,2}\s*(?:st|nd|rd|th)?[,\s]+)?'
                  r'([A-Za-z]+)[,\s]+(\d{4})', text, re.IGNORECASE)
    if m:
        mo = _month_code(m.group(1))
        if mo:
            return f'{m.group(2)}-{mo}'
    # "quarter ended --- Dec 2024" / "quarter ended September 2016"
    m = re.search(r'quarter\s+ended\W{0,12}(?:\d{1,2}\s*(?:st|nd|rd|th)?[,\s]+)?'
                  r'([A-Za-z]+)[,\s]+(\d{4})', text, re.IGNORECASE)
    if m:
        mo = _month_code(m.group(1))
        if mo:
            return f'{m.group(2)}-{mo}'
    # Range "… April 2024 to December 2024" → take the period END.
    m = re.search(r'to\s+(?:\d{1,2}\s*(?:st|nd|rd|th)?[,\s]+)?([A-Za-z]+)[,\s]+(\d{4})\b',
                  text, re.IGNORECASE)
    if m and 2005 <= int(m.group(2)) <= 2026:
        mo = _month_code(m.group(1))
        if mo:
            return f'{m.group(2)}-{mo}'
    # Generic "<Month> <YYYY>" (e.g. filename-style "Banking Network
    # Summary Jun 2025"); only month words, sanity-bounded year.
    m = re.search(r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|'
                  r'Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|'
                  r'Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[,._\s]+(\d{4})\b',
                  text, re.IGNORECASE)
    if m and 2005 <= int(m.group(2)) <= 2026:
        mo = _month_code(m.group(1))
        if mo:
            return f'{m.group(2)}-{mo}'
    return None


def infer_period_from_stem(stem: str) -> str | None:
    """Filename-encoded periods, e.g. 'acpdec15' → 2015-12,
    'KCCOutsept23' → 2023-09, 'ACPachievementDec23' → 2023-12.

    Many Rajasthan annexures carry Hindi (Devanagari) headings whose month
    names pdfplumber mangles — the filename is the only machine-readable
    period marker for those. Month word must be directly followed by a
    2- or 4-digit year to avoid false hits.
    """
    m = re.search(r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|'
                  r'jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|'
                  r'oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
                  r'[._-]?(\d{2}|\d{4})(?!\d)', stem.lower())
    if not m:
        return None
    mo = _month_code(m.group(1))
    if not mo:
        return None
    y = m.group(2)
    if len(y) == 2:
        y = ('20' + y) if int(y) <= 26 else ('19' + y)
    if not (2005 <= int(y) <= 2026):
        return None
    return f'{y}-{mo}'


def cell_text(c) -> str:
    return ('' if c is None else str(c)).strip().replace('\n', ' ')


def extract_one(pdf_path: Path) -> dict | None:
    """Extract the first table with >= MIN_UNIQUE_DISTRICTS Rajasthan
    districts in an early column. Returns None when no table qualifies.
    """
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        chosen = None
        chosen_page_text = ''
        for pi, page in enumerate(pdf.pages):
            for t in page.extract_tables() or []:
                if not t or len(t) < MIN_UNIQUE_DISTRICTS:
                    continue
                ncols = max(len(r) for r in t)
                for col in range(min(5, ncols)):
                    districts = []
                    for r in t:
                        if col < len(r):
                            d = canon_district(cell_text(r[col]))
                            if d:
                                districts.append(d)
                    unique = list(dict.fromkeys(districts))
                    if len(unique) >= MIN_UNIQUE_DISTRICTS:
                        chosen = (t, col, unique, pi)
                        break
                if chosen:
                    break
            if chosen:
                chosen_page_text = page.extract_text() or ''
                break

        if not chosen:
            return None

        t, district_col, district_names, page_idx = chosen

        # Header rows = rows before the first district-bearing row.
        header_end = 0
        for ri, r in enumerate(t):
            if any(canon_district(cell_text(c)) for c in r):
                header_end = ri
                break
        headers = [[cell_text(c) for c in row] for row in t[:header_end]]
        rows = [[cell_text(c) for c in row] for row in t[header_end:]]

        # Title: Rajasthan annexure headings live in the page text above
        # the table grid (the grid itself starts at the column headers).
        # Take the first few non-empty page-text lines; fall back to any
        # non-district rows inside the table, then the filename.
        title_lines = [ln.strip() for ln in chosen_page_text.split('\n')
                       if ln.strip()][:5]
        title = ' '.join(title_lines).strip()
        if not title:
            title = ' '.join(' | '.join(cell_text(c) for c in r if cell_text(c))
                             for r in t[:header_end]).strip()
        if not title:
            title = pdf_path.stem.replace('_', ' ')

        period = (infer_period(title + ' ' + chosen_page_text[:800])
                  or infer_period_from_stem(pdf_path.stem))

        return {
            'title': title[:200],
            'inferredPeriod': period,
            'districtColumn': district_col,
            'districts': district_names,
            'pageIndex': page_idx,
            'headers': headers,
            'rows': rows,
        }


# ---------------------------------------------------------------------------
# Per-PDF wall-clock timeout (pattern from
# slbc-data/uttar-pradesh/extract_uttar_pradesh.py::_run_extract_with_timeout)
# ---------------------------------------------------------------------------
def _extract_worker(conn, pdf_path: str):
    try:
        result = extract_one(Path(pdf_path))
        conn.send(('ok', result))
    except Exception as e:
        try:
            conn.send(('error', f'{type(e).__name__}: {e}'))
        except Exception:
            pass
    finally:
        conn.close()


def _run_extract_with_timeout(pdf_path: Path, timeout_s: float):
    """Returns (status, result): status 'ok' | 'timeout' | 'error'."""
    import multiprocessing as mp
    ctx = mp.get_context('spawn')  # safe on macOS
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    p = ctx.Process(target=_extract_worker, args=(child_conn, str(pdf_path)))
    p.start()
    child_conn.close()
    deadline = time.time() + timeout_s
    msg = None
    while time.time() < deadline:
        remaining = max(0.0, deadline - time.time())
        if parent_conn.poll(min(remaining, 1.0)):
            try:
                msg = parent_conn.recv()
            except EOFError:
                msg = None
            break
        if not p.is_alive():
            if parent_conn.poll(0.1):
                try:
                    msg = parent_conn.recv()
                except EOFError:
                    pass
            break
    parent_conn.close()
    if p.is_alive():
        p.terminate()
        p.join(5)
        if p.is_alive():
            p.kill()
        if msg is None:
            return ('timeout', None)
    p.join(5)
    if msg is None:
        return ('error', 'worker died without result')
    return msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only-district-wise', action='store_true',
                    help='Skip PDFs without district-ish keywords in the '
                         'filename (faster).')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--timeout', type=float, default=PDF_TIME_BUDGET_S,
                    help='Per-PDF wall-clock budget in seconds.')
    args = ap.parse_args()

    manifest_path = WAYBACK_DIR / 'manifest.json'
    if not manifest_path.exists():
        print(f'ERROR: {manifest_path} missing — run fetch_wayback_pdfs.py first',
              file=sys.stderr)
        sys.exit(1)
    manifest = json.loads(manifest_path.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates = []
    skipped_truncated = 0
    missing = 0
    for entry in manifest['files']:
        # Skip Wayback-capture-truncated files (gotcha #87).
        if entry.get('status') == 'truncated':
            skipped_truncated += 1
            continue
        local = ROOT / entry.get('localPath', '')
        if not entry.get('localPath') or not local.exists():
            missing += 1
            continue
        if args.only_district_wise and not any(
                k in local.name.lower()
                for k in ('district', 'distt', 'dw_', 'acp', 'cdr', 'wise')):
            continue
        candidates.append(entry)
    if args.limit:
        candidates = candidates[: args.limit]

    print(f'examining {len(candidates)} PDF(s) '
          f'(skipped {skipped_truncated} truncated, {missing} missing)',
          flush=True)
    out_count = 0
    no_table = 0
    errors = 0
    timeouts = 0
    written: dict[str, str] = {}  # output stem -> sourcePdf (collision guard)
    for entry in candidates:
        local = ROOT / entry['localPath']
        t0 = time.time()
        status, result = _run_extract_with_timeout(local, args.timeout)
        elapsed = time.time() - t0
        if status == 'timeout':
            print(f'  TIMEOUT {local.name[:70]} after {elapsed:.0f}s — skipping',
                  file=sys.stderr, flush=True)
            timeouts += 1
            continue
        if status == 'error':
            print(f'  ERR {local.name[:70]}: {result}', file=sys.stderr,
                  flush=True)
            errors += 1
            continue
        if result is None:
            no_table += 1
            continue
        # Same basename can recur across snapshot years — disambiguate.
        stem = local.stem
        if stem in written and written[stem] != str(local):
            stem = f'{stem}__{local.parent.name}'
        written[stem] = str(local)
        out_path = OUT_DIR / (stem + '.json')
        payload = {
            'sourcePdf': str(local.relative_to(ROOT)),
            'originalUrl': entry.get('originalUrl'),
            'snapshotTimestamp': entry.get('snapshotTimestamp'),
            **result,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f'  OK  {local.name[:65]:65} → {len(result["districts"])} districts, '
              f'{len(result["rows"])} rows, period={result["inferredPeriod"]}',
              flush=True)
        out_count += 1

    print(f'\nextracted {out_count} files; {no_table} no district table '
          f'(scanned/minutes/bank-wise); {errors} errored; {timeouts} timed out; '
          f'{skipped_truncated} skipped (truncated); {missing} missing locally')
    print(f'output: {OUT_DIR.relative_to(ROOT)}/')


if __name__ == '__main__':
    main()
