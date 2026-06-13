#!/usr/bin/env python3
"""
Extract district-wise tables from the Madhya Pradesh Wayback PDF haul.

Mirror of db/extract_wayback_kerala.py for MP's 55 districts (post-2023;
older PDFs use 50-52 districts and pre-rename names). Same shape of output
JSON; downstream normalization is per-PDF curation.

Run AFTER db/fetch_wayback_pdfs.py madhya-pradesh slbcmadhyapradesh.in:
    python3 db/extract_wayback_madhya_pradesh.py

MP specifics vs the Kerala template:
- 55-district canon list with the 2022-24 renames/carves aliased:
  Hoshangabad → Narmadapuram (2022 rename), Khandwa (East Nimar),
  Khargone (West Nimar), Maihar / Mauganj / Pandhurna (2023-24 carves),
  Narsimhapur / Narsinghpur, Umariya / Umaria, Sheopur Kala / Sheopur.
- District tables for 50+ districts spill across PDF pages; continuation
  pages (mostly-new districts, e.g. rows 33-51) are appended to the chosen
  table so the full district list survives in one raw dump.
- Per-PDF wall-clock timeout via a multiprocessing worker (the haul has a
  70 MB StateFocus PDF and several 100+ page agendas) — pattern borrowed
  from slbc-data/uttar-pradesh/extract_uttar_pradesh.py.
- Wayback-truncated captures (status == 'truncated', gotcha #87) skipped.

This is a RAW dump (not normalized to FINER canonical schema): every cell
comes verbatim from the PDF — no unit conversion, no invented values.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'madhya-pradesh'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback'
OUT_DIR = WAYBACK_DIR / 'extracted'

PDF_TIME_BUDGET_S = 120     # hard wall-clock cap per PDF
MAX_SCAN_PAGES = 80         # pages scanned for the qualifying table
MIN_DISTRICTS = 10          # unique resolved districts to qualify


# MP's districts in their commonly-printed forms. 55 post-2023 (incl.
# Maihar, Mauganj, Pandhurna); older PDFs print 50-52. This list is a
# FILTER for identifying district-wise tables — it never fabricates data.
MP_DISTRICT_ALIASES = {
    'agarmalwa': 'Agar Malwa',
    'agar': 'Agar Malwa',            # some lists print just "AGAR"
    'alirajpur': 'Alirajpur',
    'anuppur': 'Anuppur',
    'anooppur': 'Anuppur',
    'ashoknagar': 'Ashoknagar',      # also printed "ASHOK NAGAR"
    'balaghat': 'Balaghat',
    'barwani': 'Barwani',
    'badwani': 'Barwani',
    'betul': 'Betul',
    'bhind': 'Bhind',
    'bhopal': 'Bhopal',
    'burhanpur': 'Burhanpur',
    'chhatarpur': 'Chhatarpur',
    'chatarpur': 'Chhatarpur',
    'chhindwara': 'Chhindwara',
    'chindwara': 'Chhindwara',
    'damoh': 'Damoh',
    'datia': 'Datia',
    'dewas': 'Dewas',
    'dhar': 'Dhar',
    'dindori': 'Dindori',
    'guna': 'Guna',
    'gwalior': 'Gwalior',
    'harda': 'Harda',
    'indore': 'Indore',
    'jabalpur': 'Jabalpur',
    'jhabua': 'Jhabua',
    'katni': 'Katni',
    'khandwa': 'Khandwa',
    'eastnimar': 'Khandwa',          # pre-rename official name
    'khandwaeastnimar': 'Khandwa',
    'khargone': 'Khargone',
    'khargon': 'Khargone',
    'westnimar': 'Khargone',         # pre-rename official name
    'khargonewestnimar': 'Khargone',
    'maihar': 'Maihar',              # carved from Satna 2023
    'mandla': 'Mandla',
    'mandsaur': 'Mandsaur',
    'mandsour': 'Mandsaur',
    'mauganj': 'Mauganj',            # carved from Rewa 2024
    'morena': 'Morena',
    'narmadapuram': 'Narmadapuram',
    'hoshangabad': 'Narmadapuram',   # renamed Feb 2022
    'hosangabad': 'Narmadapuram',
    'hoshangabadnarmadapuram': 'Narmadapuram',
    'narsinghpur': 'Narsinghpur',
    'narsimhapur': 'Narsinghpur',
    'narsingpur': 'Narsinghpur',
    'neemuch': 'Neemuch',
    'neemach': 'Neemuch',
    'nimach': 'Neemuch',
    'niwari': 'Niwari',              # carved from Tikamgarh 2018
    'pandhurna': 'Pandhurna',        # carved from Chhindwara 2023
    'panna': 'Panna',
    'raisen': 'Raisen',
    'rajgarh': 'Rajgarh',
    'ratlam': 'Ratlam',
    'rewa': 'Rewa',
    'sagar': 'Sagar',
    'satna': 'Satna',
    'sehore': 'Sehore',
    'seoni': 'Seoni',
    'shahdol': 'Shahdol',
    'shajapur': 'Shajapur',
    'sheopur': 'Sheopur',
    'sheopurkala': 'Sheopur',        # older printed form
    'shivpuri': 'Shivpuri',
    'sidhi': 'Sidhi',
    'singrauli': 'Singrauli',
    'singrouli': 'Singrauli',
    'tikamgarh': 'Tikamgarh',
    'tikamgargh': 'Tikamgarh',
    'ujjain': 'Ujjain',
    'umaria': 'Umaria',
    'umariya': 'Umaria',
    'vidisha': 'Vidisha',
}

# Aliases safe for loose 'alias in key' containment matching: only
# unambiguous names ≥6 chars. Short keys are exact-match only — 'agar' sits
# inside 'sagar', 'rewa' inside collision-prone keys, etc. Containment
# catches forms like "KHANDWA (EAST NIMAR)" → 'khandwaeastnimar'.
_SUBSTRING_SAFE = sorted((a for a in MP_DISTRICT_ALIASES if len(a) >= 6),
                         key=len, reverse=True)


def canon_district(s: str | None) -> str | None:
    """Return canonical MP district name or None. Filter only."""
    if not s:
        return None
    key = re.sub(r'[^a-z]', '', s.lower())
    if not key or len(key) > 40:
        return None
    if key in MP_DISTRICT_ALIASES:
        return MP_DISTRICT_ALIASES[key]
    # Strip common suffixes like "TOTAL" ("INDORE TOTAL") before giving up.
    stripped = re.sub(r'(total|distt|district)$', '', key)
    if stripped in MP_DISTRICT_ALIASES:
        return MP_DISTRICT_ALIASES[stripped]
    for alias in _SUBSTRING_SAFE:
        if alias in key:
            return MP_DISTRICT_ALIASES[alias]
    return None


MONTHS = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05',
    'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10',
    'nov': '11', 'dec': '12',
}


def _month_no(word: str) -> str | None:
    return MONTHS.get(word.lower()[:3])


def infer_period(title: str, body: str) -> str | None:
    """Pull the reporting period from title text first, then nearby body
    text. Patterns seen in the MP haul:
      "AS ON 31.12.2016", "AS ON JUNE 30, 2018", "AS ON 31ST DECEMBER 2016",
      "Quarter ended June 2015", "March 2019", "Q-1 FY 2018-19", "ACP 2018-19".
    Returns 'YYYY-MM' or None (never guesses).
    """
    for text in (title, body):
        if not text:
            continue
        # dd.mm.yyyy  (also dd-mm-yyyy / dd/mm/yyyy)
        m = re.search(r'\b(\d{1,2})[./-](\d{2})[./-](\d{4})\b', text)
        if m and 1 <= int(m.group(2)) <= 12:
            return f'{m.group(3)}-{m.group(2)}'
        # Month dd, yyyy  ("JUNE 30, 2018")
        m = re.search(r'\b([A-Za-z]{3,9})\s+\d{1,2}\s*,\s*(\d{4})\b', text)
        if m:
            mo = _month_no(m.group(1))
            if mo:
                return f'{m.group(2)}-{mo}'
        # ddth Month yyyy  ("31ST DECEMBER 2016")
        m = re.search(r'\b\d{1,2}\s*(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})[,\s]+(\d{4})\b',
                      text, re.IGNORECASE)
        if m and _month_no(m.group(1)):
            return f'{m.group(2)}-{_month_no(m.group(1))}'
        # Month yyyy  ("March 2019", "quarter ended June 2015")
        m = re.search(r'\b([A-Za-z]{3,9})[-,\s]+(\d{4})\b', text)
        if m and _month_no(m.group(1)) and m.group(1).lower()[:3] in MONTHS:
            return f'{m.group(2)}-{_month_no(m.group(1))}'
        # Q-n FY 2018-19 → quarter-end month of the right FY year
        m = re.search(r'\bQ[\s-]?([1-4])\b.{0,12}?(\d{4})\s*-\s*(\d{2})\b', text,
                      re.IGNORECASE)
        if m:
            q = int(m.group(1))
            y1 = int(m.group(2))
            if q <= 3:
                return f'{y1}-{["06", "09", "12"][q - 1]}'
            return f'{m.group(2)[:2]}{m.group(3)}-03'
        # Fiscal-year marker 2018-19 → Mar-end of the latter year
        m = re.search(r'\b(\d{4})\s*-\s*(\d{2})\b', text)
        if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
            return f'{m.group(1)[:2]}{m.group(2)}-03'
    return None


def cell_text(c) -> str:
    return ('' if c is None else str(c)).strip().replace('\n', ' ')


def _find_district_col(t: list, max_cols: int = 5) -> tuple[int, list[str]] | None:
    """Return (col, unique_districts) for the best district column, or None."""
    ncols = max(len(r) for r in t)
    best = None
    for col in range(min(max_cols, ncols)):
        found = []
        for r in t:
            if col < len(r):
                d = canon_district(cell_text(r[col]))
                if d:
                    found.append(d)
        unique = list(dict.fromkeys(found))
        if best is None or len(unique) > len(best[1]):
            best = (col, unique)
    if best and best[1]:
        return best
    return None


def _page_title(page_text: str) -> str:
    """First meaningful line of the page — MP annexures print the table
    title as the first text line ("DISTRICTS WISE CD RATIO AS ON …")."""
    keywords = ('district', 'ratio', 'acp', 'plan', 'pmjdy', 'branch',
                'as on', 'achievement', 'target', 'kcc', 'shg', 'mudra',
                'deposit', 'advance', 'credit', 'recovery', 'annexure')
    lines = [ln.strip() for ln in (page_text or '').splitlines() if ln.strip()]
    for ln in lines[:4]:
        low = ln.lower()
        if len(ln) >= 12 and any(k in low for k in keywords):
            return ln
    return lines[0] if lines else ''


def extract_one(pdf_path: Path) -> dict | None:
    """Extract the first table whose early column holds ≥10 unique MP
    districts; append continuation pages (mostly-new districts). Raw dump.
    """
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        # Choose the qualifying table with the MOST resolved districts —
        # MP PDFs often print a small subset table first ("districts with
        # CD ratio below 40%") and the full 50+ district annexure later.
        chosen = None
        for pi, page in enumerate(pdf.pages[:MAX_SCAN_PAGES]):
            for t in page.extract_tables() or []:
                if not t or len(t) < 4:
                    continue
                hit = _find_district_col(t)
                if hit and len(hit[1]) >= MIN_DISTRICTS:
                    if chosen is None or len(hit[1]) > len(chosen[2]):
                        chosen = (t, hit[0], hit[1], pi)
            if chosen and len(chosen[2]) >= 50:
                break  # already a full district list; stop scanning

        if not chosen:
            return None

        t, district_col, district_names, page_idx = chosen
        chosen_page_text = pdf.pages[page_idx].extract_text() or ''

        # Title/header split: rows before the first district-bearing row.
        title_lines = []
        header_end = 0
        for ri, r in enumerate(t):
            if any(canon_district(cell_text(c)) for c in r):
                header_end = ri
                break
            joined = ' | '.join(cell_text(c) for c in r if cell_text(c))
            if joined:
                title_lines.append(joined)
        table_title = ' '.join(title_lines).strip()
        page_title = _page_title(chosen_page_text)
        title = page_title or table_title or pdf_path.stem.replace('_', ' ')

        headers = [[cell_text(c) for c in row] for row in t[:header_end]]
        rows = [[cell_text(c) for c in row] for row in t[header_end:]]

        # Continuation pages: MP's 50+ district tables spill over. A next
        # page qualifies when its first table has a district column whose
        # names are mostly NEW (the rest of the alphabet), not a re-listing
        # of the same districts (which would be a different annexure).
        have = set(district_names)
        cont_page = page_idx + 1
        while cont_page < min(len(pdf.pages), page_idx + 6):
            tables = pdf.pages[cont_page].extract_tables() or []
            appended = False
            if tables:
                ct = tables[0]
                hit = _find_district_col(ct) if ct and len(ct) >= 2 else None
                if hit:
                    _, cu = hit
                    new = [d for d in cu if d not in have]
                    if len(new) >= 3 and len(new) >= 0.6 * len(cu):
                        rows.extend([cell_text(c) for c in row] for row in ct)
                        district_names.extend(new)
                        have.update(new)
                        appended = True
            if not appended:
                break
            cont_page += 1

        # Period: title → chosen page text head → first page text head.
        first_page_text = (pdf.pages[0].extract_text() or '') if pdf.pages else ''
        period = infer_period(title + ' ' + table_title,
                              chosen_page_text[:400] + '\n' + first_page_text[:400])

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
# Timeout guard (pattern from slbc-data/uttar-pradesh/extract_uttar_pradesh.py)
# ---------------------------------------------------------------------------

def _extract_worker(conn, pdf_path_str: str):
    try:
        result = extract_one(Path(pdf_path_str))
        conn.send(('ok', result))
    except Exception as e:
        conn.send(('error', f'{type(e).__name__}: {e}'))
    finally:
        conn.close()


def _run_extract_with_timeout(pdf_path: Path, timeout_s: float):
    """Run extract_one in a worker process with a hard wall-clock timeout.
    Returns (status, result): status 'ok' | 'timeout' | 'error'."""
    import multiprocessing as mp
    ctx = mp.get_context('spawn')  # safe on macOS
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    p = ctx.Process(target=_extract_worker, args=(child_conn, str(pdf_path)))
    p.start()
    child_conn.close()
    deadline = time.time() + timeout_s
    payload = None
    while time.time() < deadline:
        remaining = max(0.0, deadline - time.time())
        if parent_conn.poll(min(remaining, 1.0)):
            try:
                payload = parent_conn.recv()
            except EOFError:
                payload = None
            break
        if not p.is_alive():
            if parent_conn.poll(0.1):
                try:
                    payload = parent_conn.recv()
                except EOFError:
                    pass
            break
    parent_conn.close()
    if p.is_alive():
        p.terminate()
        p.join(5)
        if p.is_alive():
            p.kill()
        if payload is None:
            return ('timeout', None)
    p.join(5)
    if payload is None:
        return ('error', 'worker died without result')
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only-district-wise', action='store_true',
                    help='Skip PDFs without district-ish keywords in the filename.')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--timeout', type=float, default=PDF_TIME_BUDGET_S)
    args = ap.parse_args()

    manifest_path = WAYBACK_DIR / 'manifest.json'
    if not manifest_path.exists():
        print(f'ERROR: {manifest_path} missing — run fetch_wayback_pdfs.py first',
              file=sys.stderr)
        sys.exit(1)
    manifest = json.loads(manifest_path.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    skipped_truncated = 0
    missing_local = 0
    by_path: dict[str, dict] = {}
    for e in manifest['files']:
        # Skip Wayback-capture-truncated files (gotcha #87) — incomplete PDFs.
        if e.get('status') == 'truncated':
            skipped_truncated += 1
            continue
        local = ROOT / e.get('localPath', '')
        if not e.get('localPath') or not local.exists():
            missing_local += 1
            continue
        # Dedupe by localPath, keep the latest snapshot's metadata.
        prev = by_path.get(e['localPath'])
        if prev is None or (e.get('snapshotTimestamp') or '') > (prev.get('snapshotTimestamp') or ''):
            by_path[e['localPath']] = e

    cands = list(by_path.values())
    if args.only_district_wise:
        cands = [e for e in cands
                 if any(k in Path(e['localPath']).name.lower()
                        for k in ('district', 'dw_', 'distt', 'cdr', 'cd_ratio',
                                  'cdratio', 'acp'))]
    if args.limit:
        cands = cands[: args.limit]

    print(f'examining {len(cands)} PDF(s) '
          f'(skipped {skipped_truncated} truncated, {missing_local} missing)')
    out_n = no_table_n = err_n = timeout_n = 0
    for e in cands:
        local = ROOT / e['localPath']
        status, r = _run_extract_with_timeout(local, args.timeout)
        if status == 'timeout':
            print(f'  TIMEOUT {local.name[:75]} (budget {args.timeout:.0f}s)',
                  file=sys.stderr, flush=True)
            timeout_n += 1
            continue
        if status == 'error':
            print(f'  ERR {local.name[:75]}: {r}', file=sys.stderr, flush=True)
            err_n += 1
            continue
        if r is None:
            no_table_n += 1
            continue
        out = {
            'sourcePdf': str(local.relative_to(ROOT)),
            'originalUrl': e.get('originalUrl'),
            'snapshotTimestamp': e.get('snapshotTimestamp'),
            **r,
        }
        (OUT_DIR / (local.stem + '.json')).write_text(
            json.dumps(out, ensure_ascii=False, indent=2))
        print(f'  OK  {local.name[:65]:65} → {len(r["districts"])} districts, '
              f'{len(r["rows"])} rows, period={r["inferredPeriod"]}', flush=True)
        out_n += 1

    print(f'\nextracted {out_n} files; no-table {no_table_n}; '
          f'errored {err_n}; timed out {timeout_n}; '
          f'skipped {skipped_truncated} truncated')
    print(f'output: {OUT_DIR.relative_to(ROOT)}/')


if __name__ == '__main__':
    main()
