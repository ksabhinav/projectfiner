#!/usr/bin/env python3
"""
Normalize selected HP Wayback batches into FINER canonical schema.

Mirrors db/normalize_wayback_bihar_2016.py for Himachal Pradesh. Adds
three new historical periods to the live HP data:

  Mar 2020 (FY 2019-20 end) — CD ratio from CD_Ratio_2019-20.pdf
  Nov 2023                  — branches + ATMs from 170th SLBC Meeting Agenda
  Jun 2013                  — branches from 129th SLBC Meeting Agenda

HP existing _fi_timeseries.json only had Dec 2025 before this commit.

HP values are in Lakhs already (CLAUDE.md gotcha #74) — values flow
through unchanged.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'himachal-pradesh'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback' / 'extracted'
TIMESERIES_PATH = ROOT / 'public/slbc-data' / STATE / f'{STATE}_fi_timeseries.json'
COMPLETE_PATH = ROOT / 'public/slbc-data' / STATE / f'{STATE}_complete.json'

# HP's 12 districts.
CANON = {
    'bilaspur': 'Bilaspur', 'chamba': 'Chamba', 'hamirpur': 'Hamirpur',
    'kangra': 'Kangra', 'kinnaur': 'Kinnaur', 'kinnour': 'Kinnaur',
    'kullu': 'Kullu', 'kulu': 'Kullu',
    'lahaulspiti': 'Lahaul & Spiti', 'lahaul': 'Lahaul & Spiti',
    'lahaulandspiti': 'Lahaul & Spiti', 'lahul': 'Lahaul & Spiti',
    'mandi': 'Mandi', 'shimla': 'Shimla', 'simla': 'Shimla',
    'sirmaur': 'Sirmaur', 'sirmour': 'Sirmaur',
    'solan': 'Solan', 'una': 'Una',
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
        if alias in key and len(alias) >= 4:
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


def find_data_rows(rows, dc):
    return [r for r in rows if dc < len(r) and canon_district(r[dc])]


def load_raw(name):
    p = WAYBACK_DIR / f'{name}.json'
    if not p.exists():
        print(f'ERROR: {p} missing', file=sys.stderr); sys.exit(1)
    return json.loads(p.read_text())


# (period_label, period_key) — sortable
# All "branches_atm_5col" sources share the same shape:
#   S.No. | District | NUMBER OF BRANCHES | NUMBER OF ATMs | LEAD BANK
BATCHES = [
    # Original batch (March 2020 CD ratio, June 2013 branches)
    {
        'period_label': 'March 2020',
        'period_key': '2020-03',
        'source': 'CD_Ratio_2019-20',
        'map': 'cd_ratio_2020',
    },
    {
        'period_label': 'June 2013',
        'period_key': '2013-06',
        'source': '129TH_SLBC_AGENDA_FINAL',
        'map': 'branches_7col_2013',
    },
    # Sep 2013 (130th) — 8-col PSB/RRB/Pvt/Coop/Total breakdown, take Total (col 6)
    {
        'period_label': 'September 2013',
        'period_key': '2013-09',
        'source': '130TH_SLBC_AGENDA_FINAL',
        'map': 'branches_7col_2013',
    },
    # Sep 2014 (134th) — 10-col with branches + ATM Totals.
    {
        'period_label': 'September 2014',
        'period_key': '2014-09',
        'source': '134_SLBC_AGENDA',
        'map': 'branches_atm_134',
    },
    # Sep 2018 (150th) — 9-col branches + ATMs
    {
        'period_label': 'September 2018',
        'period_key': '2018-09',
        'source': '150SLBC-Agenda_note_Index',
        'map': 'branches_atm_5col',
    },
    # 167th–175th (Apr 2023 → Mar 2025): all 5-col {SL, DIST, BR, ATM, LEAD}
    {
        'period_label': 'April 2023',
        'period_key': '2023-04',
        'source': '167th_SLBC_Meeting_Agenda_combined',
        'map': 'branches_atm_5col',
    },
    {
        'period_label': 'November 2023',
        'period_key': '2023-11',
        'source': '170th_SLBC_Meeting_Agenda',
        'map': 'branches_atm_5col',
    },
    {
        'period_label': 'February 2024',
        'period_key': '2024-02',
        'source': '171st_SLBC_Meeting_Agenda',
        'map': 'branches_atm_5col',
    },
    {
        'period_label': 'August 2024',
        'period_key': '2024-08',
        'source': '173rd_SLBC_Meeting_Agenda',
        'map': 'branches_atm_5col',
    },
    {
        'period_label': 'November 2024',
        'period_key': '2024-11',
        'source': '174th_SLBC_Meeting_Agenda',
        'map': 'branches_atm_5col',
    },
    {
        'period_label': 'March 2025',
        'period_key': '2025-03',
        'source': '175th_SLBC_Meeting_Agenda',
        'map': 'branches_atm_5col',
    },
]


def map_cd_ratio_2020(raw):
    """CD_Ratio_2019-20: 4 CD-ratio columns for FY 2019-20 quarters
    (Jun/Sep/Dec/Mar). Use col 5 = Mar 2020 FY-end value."""
    out = {}
    for r in find_data_rows(raw['rows'], raw['districtColumn']):
        d = canon_district(r[raw['districtColumn']])
        if not d: continue
        # cols: 0=SL, 1=DIST, 2=Jun, 3=Sep, 4=Dec, 5=Mar
        cd = parse_num(r[5]) if len(r) > 5 else None
        if cd:
            out.setdefault(d, {}).setdefault('credit_deposit_ratio', {})['cd_ratio'] = cd
    return out


def map_branches_atm_5col(raw):
    """5-col agenda: SL, DISTRICT, NUMBER OF BRANCHES, NUMBER OF ATMs, LEAD BANK"""
    out = {}
    for r in find_data_rows(raw['rows'], raw['districtColumn']):
        d = canon_district(r[raw['districtColumn']])
        if not d: continue
        br = parse_num(r[2]) if len(r) > 2 else None
        at = parse_num(r[3]) if len(r) > 3 else None
        if br:
            out.setdefault(d, {}).setdefault('branch_network', {})['branches_total'] = br
            out[d].setdefault('credit_deposit_ratio', {})['no_of_branches'] = br
        if at:
            out.setdefault(d, {}).setdefault('atm_network', {})['atm_total'] = at
    return out


def map_branches_7col_2013(raw):
    """129th/130th SLBC: SL, DIST, PSBs, RRBs, Pvt, Coop, Total, Lead.
       Total is col 6."""
    out = {}
    for r in find_data_rows(raw['rows'], raw['districtColumn']):
        d = canon_district(r[raw['districtColumn']])
        if not d: continue
        total = parse_num(r[6]) if len(r) > 6 else None
        if total:
            out.setdefault(d, {}).setdefault('branch_network', {})['branches_total'] = total
            out[d].setdefault('credit_deposit_ratio', {})['no_of_branches'] = total
    return out


def map_branches_atm_134(raw):
    """134th SLBC agenda (Sep 2014): 10 cols
       SL, DIST, [BR-PSB, BR-RRB, BR-Pvt, BR-Coop, BR-Total],
                [ATM-PSB, ATM-RRB, ATM-Total?]
       Pulls branch total (col 6) + ATM total (col 9)."""
    out = {}
    for r in find_data_rows(raw['rows'], raw['districtColumn']):
        d = canon_district(r[raw['districtColumn']])
        if not d: continue
        br = parse_num(r[6]) if len(r) > 6 else None
        at = parse_num(r[9]) if len(r) > 9 else None
        if br:
            out.setdefault(d, {}).setdefault('branch_network', {})['branches_total'] = br
            out[d].setdefault('credit_deposit_ratio', {})['no_of_branches'] = br
        if at:
            out.setdefault(d, {}).setdefault('atm_network', {})['atm_total'] = at
    return out


MAPPERS = {
    'cd_ratio_2020': map_cd_ratio_2020,
    'branches_atm_5col': map_branches_atm_5col,
    'branches_atm_134': map_branches_atm_134,
    'branches_7col_2013': map_branches_7col_2013,
}


def merge_district_data(into, addition):
    for district, cats in addition.items():
        into.setdefault(district, {})
        for cat, fields in cats.items():
            into[district].setdefault(cat, {})
            into[district][cat].update(fields)


def build_period_entry(district_data, period_label):
    rows = []
    for d in sorted(district_data.keys()):
        flat = {'district': d, 'period': period_label}
        for cat, fields in district_data[d].items():
            for f, v in fields.items():
                flat[f'{cat}__{f}'] = v
        rows.append(flat)
    return {'period': period_label, 'districts': rows}


def build_complete_period_entry(district_data, period_label):
    by_cat = {}
    for d in sorted(district_data.keys()):
        for cat, fields in district_data[d].items():
            row = {'district': d, **fields}
            by_cat.setdefault(cat, []).append(row)
    tables = {}
    for cat, rows in by_cat.items():
        fields, seen = [], set()
        for r in rows:
            for k in r:
                if k != 'district' and k not in seen:
                    fields.append(k); seen.add(k)
        tables[cat] = {'fields': fields, 'num_districts': len(rows), 'districts': rows}
    return {'period': period_label, 'tables': tables}


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

    all_periods = []
    for batch in BATCHES:
        print(f'\n=== {batch["period_label"]} from {batch["source"]} ===')
        raw = load_raw(batch['source'])
        mapper = MAPPERS[batch['map']]
        result = mapper(raw)
        print(f'  districts mapped: {len(result)}')
        all_periods.append((batch['period_label'], batch['period_key'], result))

    if args.dry_run:
        for label, key, data in all_periods:
            if 'Shimla' in data:
                print(f'\n{label} Shimla: {json.dumps(data["Shimla"], indent=2)}')
        return

    # Write to timeseries
    fi = json.loads(TIMESERIES_PATH.read_text())
    existing_labels = {p.get('period') for p in fi['periods']}
    for label, key, data in all_periods:
        if label in existing_labels:
            fi['periods'] = [p for p in fi['periods'] if p.get('period') != label]
        fi['periods'].append(build_period_entry(data, label))
    fi['periods'].sort(key=period_key_sort)
    TIMESERIES_PATH.write_text(json.dumps(fi, ensure_ascii=False, indent=2))
    print(f'\nwrote {TIMESERIES_PATH.relative_to(ROOT)} (total periods: {len(fi["periods"])})')

    # Write to complete
    comp = json.loads(COMPLETE_PATH.read_text())
    if 'quarters' not in comp:
        comp['quarters'] = {}
    for label, key, data in all_periods:
        comp['quarters'][key] = build_complete_period_entry(data, label)
    comp['quarters'] = dict(sorted(comp['quarters'].items()))
    COMPLETE_PATH.write_text(json.dumps(comp, ensure_ascii=False, indent=2))
    print(f'wrote {COMPLETE_PATH.relative_to(ROOT)} (total quarters: {len(comp["quarters"])})')


if __name__ == '__main__':
    main()
