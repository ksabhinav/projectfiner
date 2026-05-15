#!/usr/bin/env python3
"""
Batch-normalize Kerala Wayback SLBC books that share the same clean
"Sl. No. | District | Deposits | Advances | CD Ratio (%)" 5-column structure.

Each book corresponds to one SLBC meeting (#101 through #110 + SLRM
2010/2011/2012/2017 etc), giving us a different reporting period per file.
Mapping: deposits → credit_deposit_ratio.deposit
         advances → credit_deposit_ratio.advances
         CD ratio → credit_deposit_ratio.cd_ratio

Run AFTER db/extract_wayback_kerala.py. Re-run after normalization:
  python3 db/regenerate_indicator_files_from_states.py
  python3 db/build_district_pages.py
  python3 db/build_district_polygons.py
  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python3 scripts/build_og_district_images.py

Values are in Rs. Lakhs (per SLBC Kerala convention).
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'kerala'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback' / 'extracted'
TIMESERIES_PATH = ROOT / 'public/slbc-data' / STATE / f'{STATE}_fi_timeseries.json'
COMPLETE_PATH = ROOT / 'public/slbc-data' / STATE / f'{STATE}_complete.json'


CANON = {
    'trivandrum': 'Thiruvananthapuram', 'thiruvananthapuram': 'Thiruvananthapuram',
    'thiruvanantha': 'Thiruvananthapuram',
    'kollam': 'Kollam', 'quilon': 'Kollam',
    'pathanamthitta': 'Pathanamthitta',
    'alappuzha': 'Alappuzha', 'alapuzha': 'Alappuzha',
    'kottayam': 'Kottayam', 'idukki': 'Idukki',
    'ernakulam': 'Ernakulam',
    'thrissur': 'Thrissur', 'trichur': 'Thrissur',
    'palakkad': 'Palakkad', 'palghat': 'Palakkad',
    'malappuram': 'Malappuram',
    'kozhikode': 'Kozhikode', 'calicut': 'Kozhikode',
    'wayanad': 'Wayanad',
    'kannur': 'Kannur', 'kannr': 'Kannur', 'cannanore': 'Kannur',
    'kasaragod': 'Kasaragod', 'kasaragode': 'Kasaragod',
}


def canon_district(s: str) -> str | None:
    if not s:
        return None
    key = re.sub(r'[^a-z]', '', s.lower())
    if not key:
        return None
    if key in CANON:
        return CANON[key]
    for alias, c in CANON.items():
        if alias in key and len(alias) >= 5:
            return c
    return None


def parse_num(s):
    if s is None: return None
    s = str(s).strip().replace(',', '').replace('%', '').replace('₹', '')
    if not s or s.upper() in {'NA', 'N/A', '-', '—'}: return None
    try:
        float(s); return s
    except ValueError:
        return None


# Map each source file to a period (label, key). Order matters for sort-stability.
# All have title "Sl. No. | District | Deposits | Advances | CD Ratio (%)" — same 5-col schema.
SOURCES = [
    # (source basename without .json, period_label, period_key)
    ('19dd529a-ff9c-44d1-9586-44cba549d000-103_SLBC', 'December 2010', '2010-12'),
    ('0e1c3365-7243-4d1f-a463-c8fa0efc4b4d-102_SLBC', 'October 2010', '2010-10'),
    ('adcb46b4-88c5-4976-b227-d937e08ba19a-104_SLBC', 'September 2011', '2011-09'),
    ('791dbd1a-cc1f-4ab9-8d8f-3ccbd299e7af-SLRM_2011', 'March 2011', '2011-03'),
    ('eea127fa-56bd-45b9-bb2f-f856e81ec8f9-SLRM_2012', 'April 2012', '2012-04'),
    ('acbc2ac2-bc58-4606-85b1-cb0253170398-107_SLBC', 'September 2012', '2012-09'),
    ('16e474b3-ea81-44b3-98a9-b8f9ddd7ff27-108_SLBC', 'January 2013', '2013-01'),
    ('agenda_108', 'January 2013', '2013-01'),  # duplicate of 108 — same period, will dedupe
    ('032ec727-8d97-485c-be6e-25a79fb0c5c3-109_SLBC', 'March 2013', '2013-03'),
    ('ef80772e-f707-4ead-b147-54830f657146-110_SLBC', 'September 2013', '2013-09'),
]


def load_raw(name):
    p = WAYBACK_DIR / f'{name}.json'
    if not p.exists():
        print(f'  skip (missing): {name}', file=sys.stderr)
        return None
    return json.loads(p.read_text())


def map_cdratio_5col(raw):
    """Cols: 0=SL, 1=DIST, 2=DEPOSITS, 3=ADVANCES, 4=CD RATIO"""
    out = {}
    dc = raw['districtColumn']
    for r in raw['rows']:
        if dc >= len(r):
            continue
        d = canon_district(r[dc])
        if not d:
            continue
        deposits = parse_num(r[2]) if len(r) > 2 else None
        advances = parse_num(r[3]) if len(r) > 3 else None
        cd_ratio = parse_num(r[4]) if len(r) > 4 else None
        if not (deposits or advances or cd_ratio):
            continue
        cat = out.setdefault(d, {}).setdefault('credit_deposit_ratio', {})
        if deposits: cat['deposit']   = deposits
        if advances: cat['advances']  = advances
        if cd_ratio: cat['cd_ratio']  = cd_ratio
    return out


def build_period_entry(district_data, label):
    rows = []
    for d in sorted(district_data.keys()):
        flat = {'district': d, 'period': label}
        for cat, fields in district_data[d].items():
            for f, v in fields.items():
                flat[f'{cat}__{f}'] = v
        rows.append(flat)
    return {'period': label, 'districts': rows}


def build_complete_period_entry(district_data, label):
    by_cat = {}
    for d in sorted(district_data.keys()):
        for cat, fields in district_data[d].items():
            row = {'district': d, **fields}
            by_cat.setdefault(cat, []).append(row)
    tables = {}
    for cat, rows in by_cat.items():
        fnames, seen = [], set()
        for r in rows:
            for k in r:
                if k != 'district' and k not in seen:
                    fnames.append(k); seen.add(k)
        tables[cat] = {'fields': fnames, 'num_districts': len(rows), 'districts': rows}
    return {'period': label, 'tables': tables}


def period_key_sort(p):
    m = re.match(r'([A-Za-z]+)\s+(\d{4})', p.get('period', ''))
    if not m: return ('0000', '00')
    months = {'January':'01','February':'02','March':'03','April':'04','May':'05','June':'06',
              'July':'07','August':'08','September':'09','October':'10','November':'11','December':'12'}
    return (m.group(2), months.get(m.group(1), '00'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    by_period: dict[str, dict] = {}  # period_key → district_data
    period_labels: dict[str, str] = {}  # period_key → period_label
    for source, label, key in SOURCES:
        raw = load_raw(source)
        if raw is None:
            continue
        result = map_cdratio_5col(raw)
        if not result:
            print(f'  empty mapping: {source}')
            continue
        # Merge into existing period if multiple sources cover same period
        existing = by_period.setdefault(key, {})
        for d, cats in result.items():
            existing.setdefault(d, {})
            for cat, fields in cats.items():
                existing[d].setdefault(cat, {}).update(fields)
        period_labels[key] = label
        print(f'  {key} ({label}): {len(result)} districts mapped from {source[:55]}')

    if args.dry_run:
        for key in sorted(by_period.keys()):
            d0 = next(iter(by_period[key].values()), {})
            print(f'  {key}: sample = {d0}')
        return

    # Apply to timeseries
    fi = json.loads(TIMESERIES_PATH.read_text())
    existing_labels = {p.get('period') for p in fi['periods']}
    for key in sorted(by_period.keys()):
        label = period_labels[key]
        if label in existing_labels:
            fi['periods'] = [p for p in fi['periods'] if p.get('period') != label]
        fi['periods'].append(build_period_entry(by_period[key], label))
    fi['periods'].sort(key=period_key_sort)
    TIMESERIES_PATH.write_text(json.dumps(fi, ensure_ascii=False, indent=2))
    print(f'\nwrote {TIMESERIES_PATH.relative_to(ROOT)} (total periods: {len(fi["periods"])})')

    # Apply to complete
    comp = json.loads(COMPLETE_PATH.read_text())
    if 'quarters' not in comp:
        comp['quarters'] = {}
    for key in sorted(by_period.keys()):
        comp['quarters'][key] = build_complete_period_entry(by_period[key], period_labels[key])
    comp['quarters'] = dict(sorted(comp['quarters'].items()))
    COMPLETE_PATH.write_text(json.dumps(comp, ensure_ascii=False, indent=2))
    print(f'wrote {COMPLETE_PATH.relative_to(ROOT)} (total quarters: {len(comp["quarters"])})')


if __name__ == '__main__':
    main()
