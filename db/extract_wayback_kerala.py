#!/usr/bin/env python3
"""
Extract district-wise tables from the Kerala Wayback PDF haul.

Walks slbc-data/kerala/wayback/manifest.json, identifies PDFs whose first
table column looks like Kerala district names, runs pdfplumber to extract
the table, and writes a raw JSON per file with the full table grid plus
inferred period + a list of detected districts.

Output: slbc-data/kerala/wayback/extracted/<sha256-prefix>.json with shape

    {
      "sourcePdf": "slbc-data/kerala/wayback/2013/9.13_SGSY_...pdf",
      "originalUrl": "http://slbckerala.com/...",
      "snapshotTimestamp": "20131207213134",
      "title": "9.13. SGSY 2011-12 - DISTRICT WISE PERFORMANCE...",
      "inferredPeriod": "2012-10",
      "districtColumn": 1,
      "districts": ["Trivandrum", "Kollam", ..., "Kasaragode"],
      "headers": [["Sl.No", "Name of the District", "Applications from SHGs", ...]],
      "rows": [["1", "Trivandrum", "", "", ...], ...]
    }

This is a RAW dump (not normalized to FINER canonical schema). Downstream
normalization can map per-PDF column names → canonical FINER fields.
That's a per-PDF curation task; the raw extraction here is what unblocks it.

Run:
    python3 db/extract_wayback_kerala.py
    python3 db/extract_wayback_kerala.py --only-district-wise
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'kerala'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback'
OUT_DIR = WAYBACK_DIR / 'extracted'

import pdfplumber  # noqa: E402


# Kerala's 14 districts in their commonly-printed forms.
# We match case-insensitive + a few aliases for SLBC quirks (Kannr vs Kannur,
# Kasaragode vs Kasaragod, Trivandrum vs Thiruvananthapuram).
KERALA_DISTRICTS_CANON = [
    'Thiruvananthapuram', 'Kollam', 'Pathanamthitta', 'Alappuzha',
    'Kottayam', 'Idukki', 'Ernakulam', 'Thrissur', 'Palakkad',
    'Malappuram', 'Kozhikode', 'Wayanad', 'Kannur', 'Kasaragod',
]
KERALA_DISTRICT_ALIASES = {
    'trivandrum': 'Thiruvananthapuram',
    'thiruvanantha': 'Thiruvananthapuram',
    'thiruvananthapuram': 'Thiruvananthapuram',
    'tvm': 'Thiruvananthapuram',
    'kollam': 'Kollam',
    'quilon': 'Kollam',
    'pathanamthitta': 'Pathanamthitta',
    'pta': 'Pathanamthitta',
    'alappuzha': 'Alappuzha',
    'alapuzha': 'Alappuzha',
    'kottayam': 'Kottayam',
    'idukki': 'Idukki',
    'ernakulam': 'Ernakulam',
    'thrissur': 'Thrissur',
    'trichur': 'Thrissur',
    'palakkad': 'Palakkad',
    'palghat': 'Palakkad',
    'malappuram': 'Malappuram',
    'kozhikode': 'Kozhikode',
    'calicut': 'Kozhikode',
    'wayanad': 'Wayanad',
    'kannur': 'Kannur',
    'kannr': 'Kannur',
    'cannanore': 'Kannur',
    'kasaragod': 'Kasaragod',
    'kasaragode': 'Kasaragod',
}


def canon_district(s: str | None) -> str | None:
    """Return canonical district name or None."""
    if not s:
        return None
    key = re.sub(r'[^a-z]', '', s.lower())
    if key in KERALA_DISTRICT_ALIASES:
        return KERALA_DISTRICT_ALIASES[key]
    # Sometimes printed with stray characters; loose contains check.
    for alias, canon in KERALA_DISTRICT_ALIASES.items():
        if alias in key:
            return canon
    return None


def infer_period(text: str, snapshot_ts: str) -> str | None:
    """Heuristic: pull 'as on <month> <year>' or 'as at <month> <year>'
    or 'YYYY-YY' fiscal-year markers from the title text. Falls back to
    snapshot year+quarter when nothing concrete is found.
    """
    months = {
        'jan': '01', 'january': '01', 'feb': '02', 'february': '02',
        'mar': '03', 'march': '03', 'apr': '04', 'april': '04',
        'may': '05', 'jun': '06', 'june': '06',
        'jul': '07', 'july': '07', 'aug': '08', 'august': '08',
        'sep': '09', 'sept': '09', 'september': '09', 'oct': '10',
        'october': '10', 'nov': '11', 'november': '11', 'dec': '12',
        'december': '12',
    }
    # 'as at <month> <year>', 'as on <month> <year>', '<month> <year>'
    m = re.search(r'(?:as\s+(?:on|at)\s+)?(\d{1,2}\.\d{2}\.\d{4})', text)
    if m:
        d, mo, y = m.group(1).split('.')
        return f'{y}-{mo}'
    m = re.search(r'(?:as\s+(?:on|at)\s+)?([A-Za-z]+)\s+(\d{4})', text, re.IGNORECASE)
    if m:
        mo = months.get(m.group(1).lower()[:3]) or months.get(m.group(1).lower())
        if mo:
            return f'{m.group(2)}-{mo}'
    # Fiscal-year markers like 2012-13 — assume Mar-end of latter year.
    m = re.search(r'(\d{4})-(\d{2})\b', text)
    if m:
        full_yr = m.group(1)[:2] + m.group(2)
        return f'{full_yr}-03'
    return None


def cell_text(c) -> str:
    if c is None:
        return ''
    return str(c).strip().replace('\n', ' ')


def extract_one(pdf_path: Path, snapshot_ts: str, original_url: str) -> dict | None:
    """Extract the first table that has Kerala districts in its first
    text column. Returns None if no qualifying table is found.
    """
    with pdfplumber.open(pdf_path) as pdf:
        all_text = ''
        for page in pdf.pages:
            t = page.extract_text() or ''
            all_text += t + '\n'

        # Walk pages, look for a table where a column contains ≥6 Kerala districts
        chosen_table = None
        chosen_district_col = None
        chosen_district_names: list[str] = []
        chosen_page_idx = None

        for pi, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for t in tables:
                if not t or len(t) < 4:
                    continue
                # Try each column as the district column
                ncols = max(len(r) for r in t)
                for col in range(min(4, ncols)):
                    districts_found: list[str] = []
                    for r in t:
                        if col < len(r):
                            d = canon_district(cell_text(r[col]))
                            if d:
                                districts_found.append(d)
                    # Unique districts in this column
                    unique = list(dict.fromkeys(districts_found))
                    if len(unique) >= 6:
                        chosen_table = t
                        chosen_district_col = col
                        chosen_district_names = unique
                        chosen_page_idx = pi
                        break
                if chosen_table:
                    break
            if chosen_table:
                break

        if not chosen_table:
            return None

        # Title = first non-empty row before the district column starts populating
        title_lines = []
        for r in chosen_table:
            joined = ' | '.join(cell_text(c) for c in r if cell_text(c))
            if not joined:
                continue
            has_district = any(canon_district(cell_text(c)) for c in r)
            if has_district:
                break
            title_lines.append(joined)
        title = ' '.join(title_lines).strip() or pdf_path.stem.replace('_', ' ')

        # Header rows = the rows that come before the first district row
        header_end = 0
        for ri, r in enumerate(chosen_table):
            if any(canon_district(cell_text(c)) for c in r):
                header_end = ri
                break
        headers = [[cell_text(c) for c in row] for row in chosen_table[:header_end]]
        rows = [[cell_text(c) for c in row] for row in chosen_table[header_end:]]

        period = infer_period(title + ' ' + all_text[:500], snapshot_ts)

        return {
            'title': title[:200],
            'inferredPeriod': period,
            'districtColumn': chosen_district_col,
            'districts': chosen_district_names,
            'pageIndex': chosen_page_idx,
            'headers': headers,
            'rows': rows,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only-district-wise', action='store_true',
                    help='Skip PDFs without "district" or "dw" in the filename '
                         '(faster, less likely to mis-classify state-level tables).')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    manifest_path = WAYBACK_DIR / 'manifest.json'
    if not manifest_path.exists():
        print(f'ERROR: {manifest_path} missing — run fetch_wayback_pdfs.py first',
              file=sys.stderr)
        sys.exit(1)
    manifest = json.loads(manifest_path.read_text())

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates = []
    for entry in manifest['files']:
        # Skip files Wayback truncated at capture — they're usually unparseable
        # past the first few pages (see CLAUDE.md gotcha #87).
        if entry.get('status') == 'truncated':
            continue
        local = ROOT / entry.get('localPath', '')
        if not local.exists():
            continue
        name_low = local.name.lower()
        if args.only_district_wise and not any(k in name_low for k in ('district', 'dw_', 'distt')):
            continue
        candidates.append(entry)
    if args.limit:
        candidates = candidates[: args.limit]

    print(f'examining {len(candidates)} PDF(s)')
    out_count = 0
    skipped = 0
    errors = 0
    for entry in candidates:
        local = ROOT / entry['localPath']
        try:
            result = extract_one(local, entry.get('snapshotTimestamp', ''),
                                 entry.get('originalUrl', ''))
        except Exception as e:
            print(f'  ERR {local.name[:80]}: {e}', file=sys.stderr)
            errors += 1
            continue
        if result is None:
            skipped += 1
            continue
        out_path = OUT_DIR / (local.stem + '.json')
        payload = {
            'sourcePdf': str(local.relative_to(ROOT)),
            'originalUrl': entry.get('originalUrl'),
            'snapshotTimestamp': entry.get('snapshotTimestamp'),
            **result,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f'  OK  {local.name[:70]:70} → {len(result["districts"])} districts, '
              f'{len(result["rows"])} rows, period={result["inferredPeriod"]}')
        out_count += 1

    print(f'\nextracted {out_count} files; skipped {skipped} (no district column); '
          f'errored {errors}')
    print(f'output: {OUT_DIR.relative_to(ROOT)}/')


if __name__ == '__main__':
    main()
