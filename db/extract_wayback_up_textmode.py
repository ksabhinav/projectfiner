#!/usr/bin/env python3
"""
UP-specific Wayback extractor that uses TEXT-line parsing instead of
pdfplumber's `extract_tables()`.

Why: UP SLBC booklets render district-wise tables as positioned text
without table borders, so pdfplumber's heuristic table-detection misses
them. But the text layout is consistent — every district-wise table is
a block of lines matching `<sr_no> <district_name> <numbers...>`.

This script walks `slbc-data/uttar-pradesh/wayback/manifest.json`,
opens each PDF, scans page text for runs of UP-district lines, and
emits raw extracted JSONs at
`slbc-data/uttar-pradesh/wayback/extracted/<basename>.json` — same
shape as the table-mode extractors. Downstream normalization (which
maps to FINER canonical fields) is per-table-type.

Detected table types per UP booklet (see SLBC_Booklet_March_2020 as
reference):
  - District-wise ATMs (page ~7)              → atm_network.atm_total
  - District-wise BCs (page ~29)              → branch_network.bc_total
  - District-wise PMJDY                       → pmjdy.*
  - District-wise Jansuraksha PMJJBY/PMSBY    → social_security.*
  - District-wise PMJJBY/PMSBY Claims         → social_security.* (new fields)

This first pass focuses on ATMs + BCs (single-number tables, very
high signal-to-noise). PMJDY/Jansuraksha can follow in a second pass.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'uttar-pradesh'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback'
OUT_DIR = WAYBACK_DIR / 'extracted'

import pdfplumber  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
from extract_wayback_uttar_pradesh import UP_DISTRICT_CANON, canon_district  # noqa: E402


# Header signatures that identify which table type we're scanning.
# Each entry is a list of regex patterns that ALL must match in the page's
# top 600 chars for the page to be classified as that table.
TABLE_SIGNATURES = {
    'atms_per_district': [
        re.compile(r'district[-\s]*wise\s*atms', re.IGNORECASE),
        re.compile(r'no\.?\s*of\s*atms?', re.IGNORECASE),
    ],
    'bcs_per_district': [
        re.compile(r'district\s*wise\s*BCs', re.IGNORECASE),
        re.compile(r'no\.?\s*of\s*BCs', re.IGNORECASE),
    ],
    # 14-col table: SR, DIST, RURAL, URBAN, MALE, FEMALE, TOTAL, ACTIVE,
    #               ZERO_BAL, DEPOSITS, RUPAY_ISSUED, AADHAAR_SEEDED,
    #               %AADHAAR, %RUPAY
    'pmjdy_per_district': [
        re.compile(r'district[-\s]*wise\s*pmjdy\s*report', re.IGNORECASE),
    ],
    # 5-col: SR, DIST, PMJJBY, PMSBY, TOTAL (Jansuraksha enrolment)
    'jansuraksha_per_district': [
        re.compile(r'district\s*wise\s*jansuraksha', re.IGNORECASE),
    ],
    # 7-col PMJJBY claims breakdown
    'pmjjby_claims_per_district': [
        re.compile(r'district[-\s]*wise\s*pmjjby\s*claim', re.IGNORECASE),
    ],
    # 7-col PMSBY claims breakdown
    'pmsby_claims_per_district': [
        re.compile(r'district[-\s]*wise\s*pmsby\s*claim', re.IGNORECASE),
    ],
}

# Row-parse regex per table type. Group 1 = sr_no; Group 2 = district;
# Group 3...N = numeric columns. We constrain by column count so a noisy
# adjacent paragraph doesn't accidentally match.
ROW_PATTERNS = {
    # 3-col tables: sr, dist, single-number
    'atms_per_district':           re.compile(r'^(\d{1,2})\s+(.+?)\s+(\d[\d,]*)$'),
    'bcs_per_district':            re.compile(r'^(\d{1,2})\s+(.+?)\s+(\d[\d,]*)$'),
    # PMJDY 14-col: sr, dist, then 12 numerics. Any column may be decimal —
    # deposits is in Cr (414.61), % cols are decimal, but the order varies
    # by booklet so we allow optional .nn on every numeric capture.
    'pmjdy_per_district':          re.compile(
        r'^(\d{1,2})\s+(.+?)\s+' +
        r'(\d[\d,]*\.?\d*)\s+' * 11 +
        r'(\d[\d,]*\.?\d*)$'
    ),
    # Jansuraksha 5-col: sr, dist, pmjjby, pmsby, total
    'jansuraksha_per_district':    re.compile(
        r'^(\d{1,2})\s+(.+?)\s+(\d[\d,~]*)\s+(\d[\d,~]*)\s+(\d[\d,]*)$'
    ),
    # PMJJBY claims 7-col: sr, dist, paid, with_process, rejected, pending_insurer, total, claim_paid_amt
    'pmjjby_claims_per_district':  re.compile(
        r'^(\d{1,2})\s+(.+?)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)$'
    ),
    'pmsby_claims_per_district':   re.compile(
        r'^(\d{1,2})\s+(.+?)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)?\s*(\d[\d,]*)?\s*(\d[\d,]*)?$'
    ),
}


def detect_table_signal(page_text: str) -> str | None:
    """Return the table type if the page header text signals one we care
    about. Heuristic — requires both a 'District' / 'wise' keyword AND
    the data column keyword (ATMs / BCs)."""
    head = page_text[:600]
    for tbl, patterns in TABLE_SIGNATURES.items():
        if all(p.search(head) for p in patterns):
            return tbl
    return None


def parse_district_rows(page_text: str, table_type: str) -> list[dict]:
    """Pull a list of {district, values: [...]} from a tabular text block.

    Each table_type has its own regex (ROW_PATTERNS) describing the
    expected column count + signature. The returned `values` list has
    the same number of elements as numeric capture groups in the regex.
    """
    pattern = ROW_PATTERNS.get(table_type)
    if pattern is None:
        return []
    out: list[dict] = []
    for line in page_text.splitlines():
        line = re.sub(r'\s+', ' ', line.strip())
        if not line:
            continue
        m = pattern.match(line)
        if not m:
            continue
        sr = int(m.group(1))
        if sr < 1 or sr > 80:
            continue
        district_text = m.group(2)
        canon = canon_district(district_text)
        if not canon:
            continue
        # Capture groups 3..N are numeric columns. Strip commas + tilde noise.
        values = []
        for i in range(3, m.lastindex + 1):
            v = m.group(i) or ''
            v = v.replace(',', '').replace('~', '').strip()
            values.append(v if v else None)
        out.append({'district': canon, 'values': values})
    return out


def detect_period(filename: str, text_head: str) -> str | None:
    """Infer (year, month) from filename or 'AS ON DD.MM.YYYY' in page text."""
    # Look in filename first
    name = filename.upper()
    months = {
        'JAN': '01', 'JANUARY': '01', 'FEB': '02', 'FEBRUARY': '02',
        'MAR': '03', 'MARCH': '03', 'APR': '04', 'APRIL': '04',
        'MAY': '05', 'JUN': '06', 'JUNE': '06', 'JUL': '07',
        'JULY': '07', 'AUG': '08', 'AUGUST': '08', 'SEP': '09',
        'SEPT': '09', 'SEPTEMBER': '09', 'OCT': '10', 'OCTOBER': '10',
        'NOV': '11', 'NOVEMBER': '11', 'DEC': '12', 'DECEMBER': '12',
    }
    m = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)'
                  r'(?:UARY|RUARY|CH|IL|E|Y|UST|TEMBER|OBER|EMBER)?[\s_-]*'
                  r'(\d{4})', name)
    if m:
        return f'{m.group(2)}-{months[m.group(1)]}'
    # Then in page text — "AS ON DD.MM.YYYY"
    m = re.search(r'as\s+on\s+(\d{1,2})\.(\d{2})\.(\d{4})', text_head, re.IGNORECASE)
    if m:
        return f'{m.group(3)}-{m.group(2)}'
    return None


def process_one(pdf_path: Path) -> dict | None:
    """Walk a UP booklet's pages, harvest every district-wise table block.
    Returns a dict { 'tables': [...], 'inferredPeriod': ..., 'sourcePdf': ... }
    or None if no district tables found.
    """
    tables: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        first_pages_text = ''
        for pi, page in enumerate(pdf.pages):
            try:
                text = page.extract_text() or ''
            except Exception:
                continue
            if pi < 3:
                first_pages_text += text + '\n'
            sig = detect_table_signal(text)
            if not sig:
                continue
            rows = parse_district_rows(text, sig)
            unique_districts = list(dict.fromkeys(r['district'] for r in rows))
            # ATM/BC tables are usually complete; PMJDY/Jansuraksha may have
            # a few rows split across pages. Threshold is 25/75 across the
            # board; if a table type is consistently missing, the page just
            # gets skipped.
            if len(unique_districts) < 25:
                continue
            tables.append({
                'tableType': sig,
                'pageIndex': pi,
                'districts': unique_districts,
                'rows': rows,
            })
    if not tables:
        return None
    period = detect_period(pdf_path.name, first_pages_text)
    return {
        'sourcePdf': str(pdf_path.relative_to(ROOT)),
        'inferredPeriod': period,
        'tables': tables,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    manifest = json.loads((WAYBACK_DIR / 'manifest.json').read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cands = []
    for e in manifest['files']:
        if e.get('status') == 'truncated':
            continue
        local = ROOT / e.get('localPath', '')
        if not local.exists():
            continue
        cands.append(e)
    if args.limit:
        cands = cands[: args.limit]

    print(f'examining {len(cands)} UP PDFs (text-mode)')
    out_n = skip_n = err_n = 0
    for e in cands:
        local = ROOT / e['localPath']
        try:
            r = process_one(local)
        except Exception as ex:
            print(f'  ERR {local.name[:80]}: {ex}', file=sys.stderr)
            err_n += 1
            continue
        if r is None:
            skip_n += 1
            continue
        out = {
            'originalUrl': e.get('originalUrl'),
            'snapshotTimestamp': e.get('snapshotTimestamp'),
            **r,
        }
        out_path = OUT_DIR / (local.stem + '.json')
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        table_types = [t['tableType'] for t in r['tables']]
        max_d = max((len(t['districts']) for t in r['tables']), default=0)
        print(f'  OK  {local.name[:50]:50} period={r["inferredPeriod"]} '
              f'tables={table_types} max_d={max_d}')
        out_n += 1

    print(f'\nextracted {out_n} files; skipped {skip_n}; errored {err_n}')
    print(f'output: {OUT_DIR.relative_to(ROOT)}/')


if __name__ == '__main__':
    main()
