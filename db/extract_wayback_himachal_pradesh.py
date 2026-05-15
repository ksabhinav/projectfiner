#!/usr/bin/env python3
"""
Extract district-wise tables from the Himachal Pradesh Wayback PDF haul.

Mirror of db/extract_wayback_kerala.py for HP's 12 districts. Same shape
of output JSON; downstream normalization is per-PDF curation.

Run AFTER db/fetch_wayback_pdfs.py himachal-pradesh slbchp.com:
    python3 db/extract_wayback_himachal_pradesh.py

Note: HP source is already in Rs. Lakhs (CLAUDE.md gotcha #74) — values
flow through unchanged. Downstream normalization should NOT apply the
Crore→Lakh ×100 conversion that some other states need.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'himachal-pradesh'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback'
OUT_DIR = WAYBACK_DIR / 'extracted'

import pdfplumber  # noqa: E402


# HP's 12 districts with common spelling variants.
HP_DISTRICT_ALIASES = {
    'bilaspur': 'Bilaspur',
    'chamba': 'Chamba',
    'hamirpur': 'Hamirpur',
    'kangra': 'Kangra',
    'kinnaur': 'Kinnaur',
    'kullu': 'Kullu',
    'kulu': 'Kullu',           # archaic spelling
    'lahaul': 'Lahaul & Spiti',
    'lahul': 'Lahaul & Spiti',
    'spiti': 'Lahaul & Spiti',
    'lahaulspiti': 'Lahaul & Spiti',
    'lahulspiti': 'Lahaul & Spiti',
    'lahaulandspiti': 'Lahaul & Spiti',
    'lahulandspiti': 'Lahaul & Spiti',
    'mandi': 'Mandi',
    'shimla': 'Shimla',
    'simla': 'Shimla',         # pre-1980 spelling
    'sirmaur': 'Sirmaur',
    'sirmour': 'Sirmaur',
    'solan': 'Solan',
    'una': 'Una',
}


def canon_district(s: str | None) -> str | None:
    if not s:
        return None
    key = re.sub(r'[^a-z]', '', s.lower())
    if not key:
        return None
    if key in HP_DISTRICT_ALIASES:
        return HP_DISTRICT_ALIASES[key]
    for alias, canon in HP_DISTRICT_ALIASES.items():
        if alias in key and len(alias) >= 4:
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


def infer_period(text: str, snapshot_ts: str) -> str | None:
    m = re.search(r'(\d{1,2}\.\d{2}\.\d{4})', text)
    if m:
        d, mo, y = m.group(1).split('.')
        return f'{y}-{mo}'
    m = re.search(r'(?:as\s+(?:on|at)\s+)?([A-Za-z]+)[,\s]+(\d{4})', text, re.IGNORECASE)
    if m:
        mo = MONTHS.get(m.group(1).lower()[:3]) or MONTHS.get(m.group(1).lower())
        if mo:
            return f'{m.group(2)}-{mo}'
    m = re.search(r'(\d{4})-(\d{2})\b', text)
    if m:
        return f'{m.group(1)[:2]}{m.group(2)}-03'
    return None


def cell_text(c) -> str:
    return ('' if c is None else str(c)).strip().replace('\n', ' ')


def extract_one(pdf_path: Path, snapshot_ts: str) -> dict | None:
    with pdfplumber.open(pdf_path) as pdf:
        all_text = ''
        for page in pdf.pages:
            t = page.extract_text() or ''
            all_text += t + '\n'

        chosen = None
        for pi, page in enumerate(pdf.pages):
            for t in page.extract_tables() or []:
                if not t or len(t) < 4:
                    continue
                ncols = max(len(r) for r in t)
                for col in range(min(4, ncols)):
                    districts = []
                    for r in t:
                        if col < len(r):
                            d = canon_district(cell_text(r[col]))
                            if d:
                                districts.append(d)
                    unique = list(dict.fromkeys(districts))
                    # HP has 12 districts; require ≥6 for a match.
                    if len(unique) >= 6:
                        chosen = (t, col, unique, pi)
                        break
                if chosen:
                    break
            if chosen:
                break

        if not chosen:
            return None

        t, district_col, district_names, page_idx = chosen

        # Title = rows before the first district-bearing row
        title_lines = []
        header_end = 0
        for ri, r in enumerate(t):
            if any(canon_district(cell_text(c)) for c in r):
                header_end = ri
                break
            joined = ' | '.join(cell_text(c) for c in r if cell_text(c))
            if joined:
                title_lines.append(joined)
        title = ' '.join(title_lines).strip() or pdf_path.stem.replace('_', ' ')
        headers = [[cell_text(c) for c in row] for row in t[:header_end]]
        rows = [[cell_text(c) for c in row] for row in t[header_end:]]
        period = infer_period(title + ' ' + all_text[:500], snapshot_ts)

        return {
            'title': title[:200],
            'inferredPeriod': period,
            'districtColumn': district_col,
            'districts': district_names,
            'pageIndex': page_idx,
            'headers': headers,
            'rows': rows,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only-district-wise', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    manifest_path = WAYBACK_DIR / 'manifest.json'
    if not manifest_path.exists():
        print(f'ERROR: {manifest_path} missing', file=sys.stderr); sys.exit(1)
    manifest = json.loads(manifest_path.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cands = []
    for e in manifest['files']:
        local = ROOT / e.get('localPath', '')
        if not local.exists():
            continue
        if args.only_district_wise and not any(k in local.name.lower()
                                               for k in ('district', 'dw_', 'cdr', 'acp')):
            continue
        cands.append(e)
    if args.limit:
        cands = cands[: args.limit]

    print(f'examining {len(cands)} PDF(s)')
    out_n = 0
    skip_n = 0
    err_n = 0
    for e in cands:
        local = ROOT / e['localPath']
        try:
            r = extract_one(local, e.get('snapshotTimestamp', ''))
        except Exception as ex:
            print(f'  ERR {local.name[:80]}: {ex}', file=sys.stderr)
            err_n += 1
            continue
        if r is None:
            skip_n += 1
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
              f'{len(r["rows"])} rows, period={r["inferredPeriod"]}')
        out_n += 1

    print(f'\nextracted {out_n} files; skipped {skip_n}; errored {err_n}')
    print(f'output: {OUT_DIR.relative_to(ROOT)}/')


if __name__ == '__main__':
    main()
