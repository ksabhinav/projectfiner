#!/usr/bin/env python3
"""
Normalize the Bihar Mar 2016 Wayback batch into FINER canonical schema.

Reads the per-PDF raw JSONs at slbc-data/bihar/wayback/extracted/ for the
2016-03 batch and merges them into both:
  - public/slbc-data/bihar/bihar_fi_timeseries.json  (district page / analysis)
  - public/slbc-data/bihar/bihar_complete.json       (master schema)

After this runs, re-run:
  python3 db/regenerate_indicator_files_from_states.py
  python3 db/build_district_pages.py
  python3 db/build_district_polygons.py
  python3 scripts/build_og_district_images.py

…to get the new period onto the homepage choropleth + district pages.

Mar 2016 batch processed here:
  CDDW31032016.pdf           → credit_deposit_ratio + branches total
  BranchNetworkATM_POSDW.pdf → branch_network (rural/SU/urban breakdown)
  BCBCADW31032016.pdf        → business_correspondents
  NoFrillDistrictwise.pdf    → pmjdy (No Frills = pre-PMJDY same scheme)

Source amount unit per the CDDW title: "(Rs. in Lakh)" — already in lakhs.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'bihar'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback' / 'extracted'
TIMESERIES_PATH = ROOT / 'public/slbc-data' / STATE / f'{STATE}_fi_timeseries.json'
COMPLETE_PATH = ROOT / 'public/slbc-data' / STATE / f'{STATE}_complete.json'
PERIOD_LABEL = 'March 2016'
PERIOD_KEY = '2016-03'

# Canonical district names (38 Bihar districts).
# Matches `district` values in the existing _fi_timeseries / _complete.
CANON = {
    'araria': 'Araria', 'arwal': 'Arwal', 'aurangabad': 'Aurangabad',
    'banka': 'Banka', 'begusarai': 'Begusarai', 'bhagalpur': 'Bhagalpur',
    'bhojpur': 'Bhojpur', 'buxar': 'Buxar', 'darbhanga': 'Darbhanga',
    'gaya': 'Gaya', 'gopalganj': 'Gopalganj', 'jamui': 'Jamui',
    'jehanabad': 'Jehanabad', 'kaimur': 'Kaimur',
    'katihar': 'Katihar', 'khagaria': 'Khagaria', 'kishanganj': 'Kishanganj',
    'lakhisarai': 'Lakhisarai', 'madhepura': 'Madhepura', 'madhubani': 'Madhubani',
    'munger': 'Munger', 'muzaffarpur': 'Muzaffarpur', 'nalanda': 'Nalanda',
    'nawada': 'Nawada', 'patna': 'Patna',
    'purnea': 'Purnia', 'purnia': 'Purnia',
    'rohtas': 'Rohtas', 'saharsa': 'Saharsa', 'samastipur': 'Samastipur',
    'saran': 'Saran', 'sheikhpura': 'Sheikhpura', 'sheohar': 'Sheohar',
    'sitamarhi': 'Sitamarhi', 'siwan': 'Siwan', 'supaul': 'Supaul',
    'vaishali': 'Vaishali',
    'eastchamparan': 'Purbi Champaran',
    'purbichamparan': 'Purbi Champaran',
    'westchamparan': 'Pashchimi Champaran',
    'pashchimichamparan': 'Pashchimi Champaran',
}


def canon_district(s: str) -> str | None:
    if not s:
        return None
    key = re.sub(r'[^a-z]', '', s.lower())
    return CANON.get(key)


def parse_num(s: str) -> str | None:
    """Return cleaned numeric string or None.

    - Strips commas, percent signs, whitespace.
    - Preserves the original numeric precision (no parseFloat → str loss).
    - Returns None for empty / NA / non-numeric cells.
    """
    if s is None:
        return None
    s = str(s).strip().replace(',', '').replace('%', '').replace('₹', '').replace('Rs.', '').replace('Rs', '')
    if not s or s.upper() in {'NA', 'N/A', '-', '—'}:
        return None
    # Validate it's numeric
    try:
        float(s)
        return s
    except ValueError:
        return None


def find_data_rows(raw_rows: list[list[str]], district_col: int) -> list[list[str]]:
    """Return only the rows whose district_col contains a canonical district."""
    out = []
    for r in raw_rows:
        if district_col < len(r) and canon_district(r[district_col]):
            out.append(r)
    return out


def load_raw(name: str) -> dict:
    path = WAYBACK_DIR / f'{name}.json'
    if not path.exists():
        print(f'ERROR: {path} missing — did you run db/extract_wayback_bihar.py?', file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


# Per-PDF column → (category, field) mappings.
# Column indexes match the raw JSON's `rows[].headers[]`. The district column
# is the same as `districtColumn` in the raw JSON.

def map_cddw(raw: dict) -> dict[str, dict[str, dict[str, str]]]:
    """CDDW31032016: SL, DIST, BRANCHES, DEPOSITS, ADVANCES, C:D Ratio"""
    out: dict[str, dict[str, dict[str, str]]] = {}
    for r in find_data_rows(raw['rows'], raw['districtColumn']):
        d = canon_district(r[raw['districtColumn']])
        if not d:
            continue
        # Columns: 0=SL.NO, 1=DISTRICT, 2=NO. OF BRANCHES, 3=DEPOSITS, 4=ADVANCES, 5=C:D Rat
        branches  = parse_num(r[2]) if len(r) > 2 else None
        deposits  = parse_num(r[3]) if len(r) > 3 else None
        advances  = parse_num(r[4]) if len(r) > 4 else None
        cd_ratio  = parse_num(r[5]) if len(r) > 5 else None
        out.setdefault(d, {}).setdefault('credit_deposit_ratio', {})
        if branches: out[d]['credit_deposit_ratio']['no_of_branches'] = branches
        if deposits: out[d]['credit_deposit_ratio']['deposit']        = deposits
        if advances: out[d]['credit_deposit_ratio']['advances']       = advances
        if cd_ratio: out[d]['credit_deposit_ratio']['cd_ratio']       = cd_ratio
    return out


def map_branch_network(raw: dict) -> dict[str, dict[str, dict[str, str]]]:
    """BranchNetworkATM_POSDW: SL, DIST, BRANCH×{R,SU,U,T}, ATM×{R,SU,U,T}, ATM_CARD, POS"""
    out: dict[str, dict[str, dict[str, str]]] = {}
    for r in find_data_rows(raw['rows'], raw['districtColumn']):
        d = canon_district(r[raw['districtColumn']])
        if not d:
            continue
        rural = parse_num(r[2]) if len(r) > 2 else None
        su    = parse_num(r[3]) if len(r) > 3 else None
        urban = parse_num(r[4]) if len(r) > 4 else None
        total = parse_num(r[5]) if len(r) > 5 else None
        atm_total = parse_num(r[9]) if len(r) > 9 else None
        out.setdefault(d, {}).setdefault('branch_network', {})
        if rural: out[d]['branch_network']['branches_rural']      = rural
        if su:    out[d]['branch_network']['branches_semi_urban'] = su
        if urban: out[d]['branch_network']['branches_urban']      = urban
        if total: out[d]['branch_network']['branches_total']      = total
        if atm_total:
            out[d].setdefault('atm_network', {})['atm_total'] = atm_total
    return out


def map_bc(raw: dict) -> dict[str, dict[str, dict[str, str]]]:
    """BCBCADW31032016: SL, DIST, BC engaged, BCA engaged, accounts opened,
       amount, debit/credit txn count, txn amount."""
    out: dict[str, dict[str, dict[str, str]]] = {}
    for r in find_data_rows(raw['rows'], raw['districtColumn']):
        d = canon_district(r[raw['districtColumn']])
        if not d:
            continue
        bc_count  = parse_num(r[2]) if len(r) > 2 else None
        bca_count = parse_num(r[3]) if len(r) > 3 else None
        out.setdefault(d, {}).setdefault('business_correspondents', {})
        if bc_count:  out[d]['business_correspondents']['bc_total']       = bc_count
        if bca_count: out[d]['business_correspondents']['bc_fixed_point'] = bca_count
    return out


def map_pmjdy_nofrill(raw: dict) -> dict[str, dict[str, dict[str, str]]]:
    """NoFrillDistrictwise31032016: SL, DIST,
       No Frills A/C Opened PSU (A/c, Amt),
       No Frills A/C Opened Pvt (A/c, Amt),
       No Frills A/C Opened RRB (A/c, Amt),
       Cumulative Achievement (A/c, Amt),
       Total Operative A/c (A/c, Amt)
       — 12 columns total. Cumulative # is at col 8."""
    out: dict[str, dict[str, dict[str, str]]] = {}
    for r in find_data_rows(raw['rows'], raw['districtColumn']):
        d = canon_district(r[raw['districtColumn']])
        if not d:
            continue
        cumulative_no = parse_num(r[8]) if len(r) > 8 else None
        operative_no  = parse_num(r[10]) if len(r) > 10 else None
        out.setdefault(d, {}).setdefault('pmjdy', {})
        # `total_pmjdy_no` is the canonical field the indicator regenerator
        # expects for PMJDY headline. Keep both old + new names for legacy
        # consumers / future fallbacks. "No Frills A/C cumulative" in 2016 is
        # the pre-rebrand name for the same metric.
        if cumulative_no:
            out[d]['pmjdy']['total_pmjdy_no'] = cumulative_no
            out[d]['pmjdy']['total_pmjdy']    = cumulative_no  # alias
        if operative_no:
            out[d]['pmjdy']['operative_a_c_no'] = operative_no
    return out


def merge_district_data(into: dict, addition: dict):
    for district, cats in addition.items():
        into.setdefault(district, {})
        for cat, fields in cats.items():
            into[district].setdefault(cat, {})
            into[district][cat].update(fields)


def build_period_entry(district_data: dict[str, dict]) -> dict:
    """Flatten to bihar_fi_timeseries.json shape:
       districts = [{district, period, <cat>__<field>: value}]
    """
    districts_list = []
    for district in sorted(district_data.keys()):
        cats = district_data[district]
        flat = {'district': district, 'period': PERIOD_LABEL}
        for cat, fields in cats.items():
            for field, value in fields.items():
                flat[f'{cat}__{field}'] = value
        districts_list.append(flat)
    return {'period': PERIOD_LABEL, 'districts': districts_list}


def build_complete_period_entry(district_data: dict[str, dict]) -> dict:
    """bihar_complete.json shape:
       quarters['2016-03'] = {
         period: 'March 2016',
         tables: {
           <cat>: { fields: [...], num_districts: N, districts: [{district, ...fields}] },
           ...
         }
       }
    """
    # Invert by category
    by_cat: dict[str, list[dict]] = {}
    for district in sorted(district_data.keys()):
        for cat, fields in district_data[district].items():
            row = {'district': district, **fields}
            by_cat.setdefault(cat, []).append(row)
    tables = {}
    for cat, rows in by_cat.items():
        # Union of all field names seen across this category's rows
        all_fields = []
        seen = set()
        for r in rows:
            for k in r.keys():
                if k != 'district' and k not in seen:
                    all_fields.append(k)
                    seen.add(k)
        tables[cat] = {
            'fields': all_fields,
            'num_districts': len(rows),
            'districts': rows,
        }
    return {'period': PERIOD_LABEL, 'tables': tables}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    # Load + map each PDF
    print('mapping CDDW31032016 → credit_deposit_ratio')
    a = map_cddw(load_raw('CDDW31032016'))
    print(f'  districts mapped: {len(a)}')

    print('mapping BranchNetworkATM_POSDW → branch_network + atm_network')
    b = map_branch_network(load_raw('BranchNetworkATM_POSDW'))
    print(f'  districts mapped: {len(b)}')

    print('mapping BCBCADW31032016 → business_correspondents')
    c = map_bc(load_raw('BCBCADW31032016'))
    print(f'  districts mapped: {len(c)}')

    print('mapping NoFrillDistrictwise31032016 → pmjdy')
    e = map_pmjdy_nofrill(load_raw('NoFrillDistrictwise31032016'))
    print(f'  districts mapped: {len(e)}')

    # Merge per-district
    combined: dict[str, dict] = {}
    for partial in (a, b, c, e):
        merge_district_data(combined, partial)
    print(f'\ncombined districts: {len(combined)}')
    # Show Patna as a smoke test
    if 'Patna' in combined:
        print(f'Patna sample: {json.dumps(combined["Patna"], indent=2)}')

    # Build period entries for both target files
    fi_entry = build_period_entry(combined)
    complete_entry = build_complete_period_entry(combined)

    if args.dry_run:
        print('\n--dry-run: not writing files')
        return

    # Merge into _fi_timeseries.json (insert at chronologically correct position)
    fi = json.loads(TIMESERIES_PATH.read_text())
    # Insert at front if older than existing periods (existing start June 2024)
    # Simple approach: prepend then sort.
    fi['periods'] = [p for p in fi['periods'] if p.get('period') != PERIOD_LABEL]
    fi['periods'].insert(0, fi_entry)
    # Sort by (year, month) ascending so the older Mar 2016 sits first
    def period_key(p):
        m = re.match(r'([A-Za-z]+)\s+(\d{4})', p.get('period', ''))
        if not m:
            return ('0000', '00')
        months = {'January':'01','February':'02','March':'03','April':'04','May':'05','June':'06',
                  'July':'07','August':'08','September':'09','October':'10','November':'11','December':'12'}
        return (m.group(2), months.get(m.group(1), '00'))
    fi['periods'].sort(key=period_key)
    TIMESERIES_PATH.write_text(json.dumps(fi, ensure_ascii=False, indent=2))
    print(f'\nwrote {TIMESERIES_PATH.relative_to(ROOT)} '
          f'(period {PERIOD_LABEL} merged; total periods: {len(fi["periods"])})')

    # Merge into _complete.json
    comp = json.loads(COMPLETE_PATH.read_text())
    comp['quarters'][PERIOD_KEY] = complete_entry
    # Re-sort quarters keys by their sortable string
    sorted_quarters = dict(sorted(comp['quarters'].items()))
    comp['quarters'] = sorted_quarters
    COMPLETE_PATH.write_text(json.dumps(comp, ensure_ascii=False, indent=2))
    print(f'wrote {COMPLETE_PATH.relative_to(ROOT)} '
          f'(quarter {PERIOD_KEY} merged; total quarters: {len(comp["quarters"])})')


if __name__ == '__main__':
    main()
