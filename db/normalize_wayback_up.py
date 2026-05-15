#!/usr/bin/env python3
"""
Normalize UP Wayback text-mode extractions into FINER canonical schema.

Reads slbc-data/uttar-pradesh/wayback/extracted/*.json (produced by
db/extract_wayback_up_textmode.py) and writes/merges into the live
data:

  public/slbc-data/uttar-pradesh/uttar-pradesh_fi_timeseries.json
  public/slbc-data/uttar-pradesh/uttar-pradesh_complete.json

Mappings:
  atms_per_district  → atm_network.atm_total
                        branch_network.total_atm  (alias for headline)
  bcs_per_district   → branch_network.total_bc
                        branch_network.total_csp  (alias)
                        business_correspondents.bc_total

Each extracted JSON represents one SLBC booklet (= one quarter / period).
Period comes from the filename (e.g. 'SLBC_Booklet_March_2020.pdf' →
2020-03) or from "AS ON DD.MM.YYYY" in the first few pages' text.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'uttar-pradesh'
EXTRACT_DIR = ROOT / 'slbc-data' / STATE / 'wayback' / 'extracted'
TIMESERIES_PATH = ROOT / 'public/slbc-data' / STATE / f'{STATE}_fi_timeseries.json'
COMPLETE_PATH = ROOT / 'public/slbc-data' / STATE / f'{STATE}_complete.json'


MONTH_LABEL = {
    '01': 'January', '02': 'February', '03': 'March', '04': 'April',
    '05': 'May', '06': 'June', '07': 'July', '08': 'August',
    '09': 'September', '10': 'October', '11': 'November', '12': 'December',
}


def period_label(key: str) -> str:
    """'2020-03' → 'March 2020'."""
    m = re.match(r'^(\d{4})-(\d{2})$', key)
    if not m:
        return key
    return f'{MONTH_LABEL[m.group(2)]} {m.group(1)}'


def period_key_sort(p: dict) -> tuple:
    m = re.match(r'([A-Za-z]+)\s+(\d{4})', p.get('period', ''))
    if not m:
        return ('0000', '00')
    months = {v: k for k, v in MONTH_LABEL.items()}
    return (m.group(2), months.get(m.group(1), '00'))


def parse_num(s):
    if s is None:
        return None
    s = str(s).strip().replace(',', '')
    if not s:
        return None
    try:
        float(s); return s
    except ValueError:
        return None


def merge_district_data(into, addition):
    for d, cats in addition.items():
        into.setdefault(d, {})
        for cat, fields in cats.items():
            into[d].setdefault(cat, {}).update(fields)


def map_extracted(extract: dict) -> dict[str, dict]:
    """Convert one extracted JSON's tables[] into the per-district shape."""
    out: dict[str, dict] = {}
    for t in extract.get('tables', []):
        ttype = t.get('tableType')
        for row in t.get('rows', []):
            d = row.get('district')
            val = parse_num(row.get('value'))
            if not d or val is None:
                continue
            if ttype == 'atms_per_district':
                out.setdefault(d, {}).setdefault('atm_network', {})['atm_total'] = val
                out.setdefault(d, {}).setdefault('branch_network', {})['total_atm'] = val
            elif ttype == 'bcs_per_district':
                out.setdefault(d, {}).setdefault('business_correspondents', {})['bc_total'] = val
                out.setdefault(d, {}).setdefault('branch_network', {})['total_bc'] = val
                out.setdefault(d, {}).setdefault('branch_network', {})['total_csp'] = val
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
            by_cat.setdefault(cat, []).append({'district': d, **fields})
    tables = {}
    for cat, rows in by_cat.items():
        fnames, seen = [], set()
        for r in rows:
            for k in r:
                if k != 'district' and k not in seen:
                    fnames.append(k); seen.add(k)
        tables[cat] = {'fields': fnames, 'num_districts': len(rows), 'districts': rows}
    return {'period': label, 'tables': tables}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if not EXTRACT_DIR.exists():
        print(f'ERROR: {EXTRACT_DIR} missing — run extract_wayback_up_textmode.py first',
              file=sys.stderr)
        sys.exit(1)

    # Bucket all extracts by inferred period; multiple sources for same period
    # merge into one (preferring tables with more districts).
    by_period: dict[str, dict] = {}
    source_counts: dict[str, int] = {}
    for path in sorted(EXTRACT_DIR.iterdir()):
        if path.suffix != '.json':
            continue
        ext = json.loads(path.read_text())
        period_key = ext.get('inferredPeriod')
        if not period_key or not re.match(r'^\d{4}-\d{2}$', period_key):
            continue
        district_data = map_extracted(ext)
        if not district_data:
            continue
        existing = by_period.setdefault(period_key, {})
        merge_district_data(existing, district_data)
        source_counts[period_key] = source_counts.get(period_key, 0) + 1

    if not by_period:
        print('no extracts with usable period — nothing to write')
        return

    print(f'unique periods: {len(by_period)}')
    for key in sorted(by_period.keys()):
        n_districts = len(by_period[key])
        # Count distinct fields
        all_fields = set()
        for cats in by_period[key].values():
            for cat, fields in cats.items():
                for f in fields:
                    all_fields.add(f'{cat}.{f}')
        print(f'  {key} ({period_label(key)}): {n_districts:2}d, '
              f'{len(all_fields)} fields, from {source_counts[key]} source(s)')

    if args.dry_run:
        print('\n--dry-run: not writing')
        return

    # Merge into _fi_timeseries.json
    fi = json.loads(TIMESERIES_PATH.read_text()) if TIMESERIES_PATH.exists() else \
         {'periods': []}
    existing_labels = {p.get('period') for p in fi['periods']}
    for key in sorted(by_period.keys()):
        label = period_label(key)
        if label in existing_labels:
            fi['periods'] = [p for p in fi['periods'] if p.get('period') != label]
        fi['periods'].append(build_period_entry(by_period[key], label))
    fi['periods'].sort(key=period_key_sort)
    TIMESERIES_PATH.write_text(json.dumps(fi, ensure_ascii=False, indent=2))
    print(f'\nwrote {TIMESERIES_PATH.relative_to(ROOT)} (total periods: {len(fi["periods"])})')

    # Merge into _complete.json
    comp = json.loads(COMPLETE_PATH.read_text()) if COMPLETE_PATH.exists() else \
           {'source': 'SLBC Uttar Pradesh', 'state': 'uttar-pradesh', 'quarters': {}}
    if 'quarters' not in comp:
        comp['quarters'] = {}
    for key in sorted(by_period.keys()):
        comp['quarters'][key] = build_complete_period_entry(by_period[key], period_label(key))
    comp['quarters'] = dict(sorted(comp['quarters'].items()))
    COMPLETE_PATH.write_text(json.dumps(comp, ensure_ascii=False, indent=2))
    print(f'wrote {COMPLETE_PATH.relative_to(ROOT)} (total quarters: {len(comp["quarters"])})')


if __name__ == '__main__':
    main()
