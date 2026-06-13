#!/usr/bin/env python3
"""
Normalize the Madhya Pradesh Wayback haul into FINER canonical schema.

Mirrors db/normalize_wayback_telangana.py / _rajasthan.py. Reads raw extracts
at slbc-data/madhya-pradesh/wayback/extracted/ (from
db/extract_wayback_madhya_pradesh.py) and merges historical CD-ratio quarters
into:

  public/slbc-data/madhya-pradesh/madhya-pradesh_fi_timeseries.json
  public/slbc-data/madhya-pradesh/madhya-pradesh_complete.json
      (MP shape: quarters['YYYY-MM'] = {period, as_on_date, fy,
       tables{credit_deposit_ratio:{fields, districts:{NAME:{District,
       cd_ratio, total_advance, total_deposit}}}}})
  public/slbc-data/madhya-pradesh/madhya-pradesh_fi_timeseries.csv  (rebuilt)
  public/slbc-data/madhya-pradesh/madhya-pradesh_fi_slim.json       (rebuilt)

SCOPE: MP publishes ONLY credit_deposit_ratio district-wise (everything else
is bank-wise — see CLAUDE.md). So this backfills CD ratio only. Live MP had 6
quarters (Mar 2020, Sep 2023, Mar/Jun 2024, Sep/Dec 2025); this adds the
historical CD-ratio quarters absent from the live data.

UNITS — canonical/live MP is Rs. LAKHS (verified: Anuppur ~561,611 lakh =
Rs.5,616 Cr; Crores would be absurd). Per-file unit decided from VERBATIM
in-file evidence cross-checked against the Lakhs series (Agar Malwa deposits
run ~150k-190k lakh in 2023-2025):
  * "Amount in lakh" verbatim                 -> stored as-is.
  * 2016-12 says "AMOUNT IN CRORES" verbatim  -> x100 to Lakhs.
  * 2021-12 (CDRatio_New) prints no unit; Agar-malwa dep 941 is Crores-scale
    (941 Cr = 94,100 lakh, continuous with 2023-03's 149,801 lakh) -> x100.
  * 2017-03 prints no unit; Agar Malwa dep 74,351 is Lakhs-scale
    (=Rs.743 Cr, between the 2016 and 2023 values) -> stored as-is.

cd_ratio (a %) is never scaled, and is cross-checked against
advances/deposits*100 within 5% (guards column misalignment); else the
derived value is stored when in [5, 1000]%. The 2019-09 "CDRatio" extract is
a bank x district matrix (not district totals) and is NOT used.

DEDUPE: live site wins (existing period+district+field kept untouched).

After this runs:
  python3 db/regenerate_indicator_files_from_states.py credit_deposit_ratio
  python3 validate_data.py --state madhya-pradesh
"""
from __future__ import annotations
import argparse
import calendar
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'madhya-pradesh'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback' / 'extracted'
PUB = ROOT / 'public/slbc-data' / STATE
TIMESERIES_PATH = PUB / f'{STATE}_fi_timeseries.json'
COMPLETE_PATH = PUB / f'{STATE}_complete.json'
CSV_PATH = PUB / f'{STATE}_fi_timeseries.csv'
SLIM_PATH = PUB / f'{STATE}_fi_slim.json'

# ---------------------------------------------------------------------------
# District resolver — canon = the 55 districts in the live MP data, plus
# rename/spelling aliases. Keys = lowercase with non-letters stripped (so
# "Agar-malwa"/"AGAR MALWA"/"Agar Malwa" all collapse to "agarmalwa").
# ---------------------------------------------------------------------------
MP_CANONICAL = [
    'Agar Malwa', 'Alirajpur', 'Anuppur', 'Ashoknagar', 'Balaghat', 'Barwani',
    'Betul', 'Bhind', 'Bhopal', 'Burhanpur', 'Chhatarpur', 'Chhindwara',
    'Damoh', 'Datia', 'Dewas', 'Dhar', 'Dindori', 'East Nimar', 'Guna',
    'Gwalior', 'Harda', 'Indore', 'Jabalpur', 'Jhabua', 'Katni', 'Khargone',
    'Maihar', 'Mandla', 'Mandsaur', 'Mauganj', 'Morena', 'Narmadapuram',
    'Narsinghpur', 'Neemuch', 'Niwari', 'Pandhurna', 'Panna', 'Raisen',
    'Rajgarh', 'Ratlam', 'Rewa', 'Sagar', 'Satna', 'Sehore', 'Seoni',
    'Shahdol', 'Shajapur', 'Sheopur', 'Shivpuri', 'Sidhi', 'Singrauli',
    'Tikamgarh', 'Ujjain', 'Umaria', 'Vidisha',
]

SKIP_ROWS = {'total', 'grand total', 'state total', 'sub total', 'sub-total',
             'mp total', 'm.p. total', 'm p total', 'sr.', 'sr', 's.no.',
             'sno', 'district', 'districts', 'district name', 'name of district',
             '', None}

CANON = {re.sub(r'[^a-z]', '', d.lower()): d for d in MP_CANONICAL}
CANON.update({
    'khandwa': 'East Nimar', 'eastnimarkhandwa': 'East Nimar',
    'westnimar': 'Khargone', 'khargonewestnimar': 'Khargone',
    'hoshangabad': 'Narmadapuram',
    'narsimhapur': 'Narsinghpur',
    'umariya': 'Umaria',
    'sheopurkala': 'Sheopur', 'shyopurkala': 'Sheopur',
    'singaruli': 'Singrauli',
    'agarmalwaagar': 'Agar Malwa', 'agar': 'Agar Malwa',
    'ashok nagar'.replace(' ', ''): 'Ashoknagar',
})

UNRESOLVED: dict[str, set] = {}


def canon_district(s, pk=None):
    if s is None:
        return None
    t = str(s).strip()
    t = re.sub(r'^\d+[\.\s]+', '', t).strip(' .,*')
    if not t or t.lower() in SKIP_ROWS:
        return None
    key = re.sub(r'[^a-z]', '', t.lower())
    if not key:
        return None
    if key in CANON:
        return CANON[key]
    if pk is not None:
        UNRESOLVED.setdefault(pk, set()).add(t)
    return None


def parse_num(s):
    if s is None:
        return None
    s = str(s).strip().replace(',', '').replace('%', '').replace('₹', '')
    if not s or s.upper() in {'NA', 'N/A', '-', '—', 'NIL'}:
        return None
    try:
        float(s)
        return s
    except ValueError:
        return None


def fmt(v: float) -> str:
    return f'{v:.2f}'.rstrip('0').rstrip('.')


def get_table(name: str, ti: int) -> dict:
    p = WAYBACK_DIR / f'{name}.json'
    if not p.exists():
        print(f'ERROR: {p} missing', file=sys.stderr)
        sys.exit(1)
    d = json.loads(p.read_text())
    tables = [d] + d.get('moreTables', [])
    return tables[ti]


WARN: list[str] = []


def map_cd(tb, pk, *, dcol, dep_idx, adv_idx, cd_idx, factor, source, sparse=False):
    """sparse=True: old padded annexures whose column positions drift row to
    row. Locate the district by canon scan, then take the next 3 numeric cells
    as (deposits, advances, cd) — robust to the shifting blank columns.
    sparse=False: clean modern tables with fixed dep/adv/cd indices."""
    out = {}
    for r in tb.get('rows', []):
        if sparse:
            di = next((i for i, c in enumerate(r) if canon_district(c)), None)
            if di is None:
                for c in r:        # log genuine misses (skip-rows stay silent)
                    canon_district(c, pk)
                continue
            d = canon_district(r[di])
            nums = [n for n in (parse_num(c) for c in r[di + 1:]) if n is not None]
            dep = nums[0] if len(nums) >= 1 else None
            adv = nums[1] if len(nums) >= 2 else None
            printed = float(nums[2]) if len(nums) >= 3 else None
        else:
            d = canon_district(r[dcol], pk) if dcol < len(r) else None
            if not d:
                continue
            dep = parse_num(r[dep_idx]) if dep_idx < len(r) else None
            adv = parse_num(r[adv_idx]) if adv_idx < len(r) else None
            pv = (parse_num(r[cd_idx])
                  if cd_idx is not None and cd_idx < len(r) else None)
            printed = float(pv) if pv is not None else None
        if not d or dep is None or adv is None:
            continue
        depf, advf = float(dep) * factor, float(adv) * factor
        if depf <= 0:
            continue
        derived = advf / depf * 100.0
        cd_val = None
        if printed is not None:
            if abs(printed - derived) <= max(0.5, 0.05 * derived):
                cd_val = printed
            else:
                WARN.append(f'{pk} {source} {d}: printed CD {printed:.2f} != '
                            f'derived {derived:.2f} (dep={depf:.0f} adv={advf:.0f})')
                cd_val = derived if 5 <= derived <= 1000 else None
        else:
            cd_val = derived if 5 <= derived <= 1000 else None
        rec = {'District': d, 'total_deposit': fmt(depf), 'total_advance': fmt(advf)}
        if cd_val is not None and 5 <= cd_val <= 1000:
            rec['cd_ratio'] = fmt(cd_val)
        out[d] = {'credit_deposit_ratio': rec}
    return out


LAC = 1.0    # already Lakhs
CR = 100.0   # Crores -> Lakhs
# Old sparse layout (dcol=4, padded). Clean modern layout (dcol=1, dep2/adv3/cd4).
BATCHES = [
    # 2016-12: "AMOUNT IN CRORES"; sparse padded layout (columns drift) ->
    # positional parse (district, then dep/adv/cd).
    dict(period='2016-12', source='CREDIT_DEPOST_RATIO', ti=0,
         dcol=4, dep=7, adv=10, cd=13, factor=CR, sparse=True),
    # 2017-03: no unit, Lakhs by magnitude; same drifting sparse layout.
    dict(period='2017-03', source='CdRatio17062017', ti=0,
         dcol=4, dep=6, adv=9, cd=13, factor=LAC, sparse=True),
    # 2021-12: no unit, Crores by magnitude; clean dcol1 dep2 adv3 cd4
    dict(period='2021-12', source='CDRatio_New', ti=0,
         dcol=1, dep=2, adv=3, cd=4, factor=CR),
    # 2023-03 onward: "Amount in lakh"; clean dcol1 dep2 adv3 cd4
    dict(period='2023-03', source='516c249f-3c97-4aed-acf4-53ddd2baea54-SLBC_Data_Table_Mar23',
         ti=0, dcol=1, dep=2, adv=3, cd=4, factor=LAC),
    dict(period='2023-12', source='bank_wise__district_wise_cd_ratio_december_2023',
         ti=0, dcol=1, dep=2, adv=3, cd=4, factor=LAC),
    dict(period='2024-09', source='CD_RATIO', ti=0, dcol=1, dep=2, adv=3, cd=4, factor=LAC),
    dict(period='2024-12', source='slbc_datatable_dec24', ti=0, dcol=1, dep=2, adv=3, cd=4, factor=LAC),
    dict(period='2025-03', source='Slbc-Data-Table-March-25', ti=0, dcol=1, dep=2, adv=3, cd=4, factor=LAC),
    dict(period='2025-06', source='cd-ratio-bank-district', ti=0, dcol=1, dep=2, adv=3, cd=4, factor=LAC),
]

MONTH_NAMES = {1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May',
               6: 'June', 7: 'July', 8: 'August', 9: 'September',
               10: 'October', 11: 'November', 12: 'December'}


def period_label(pk):
    y, m = pk.split('-')
    return f'{MONTH_NAMES[int(m)]} {y}'


def as_on_date(pk):
    y, m = int(pk[:4]), int(pk[5:7])
    return f'{calendar.monthrange(y, m)[1]:02d}-{m:02d}-{y}'


def fy_of(pk):
    y, m = int(pk[:4]), int(pk[5:7])
    start = y if m >= 4 else y - 1
    return f'{start}-{str(start + 1)[-2:]}'


def period_sort_key(p):
    m = re.match(r'([A-Za-z]+)\s+(\d{4})', p.get('period', ''))
    if not m:
        return ('0000', '00')
    months = {v: f'{k:02d}' for k, v in MONTH_NAMES.items()}
    return (m.group(2), months.get(m.group(1), '00'))


def build_period_entry(dd, label):
    rows = []
    for d in sorted(dd):
        flat = {'district': d, 'period': label}
        for f, v in dd[d]['credit_deposit_ratio'].items():
            if f == 'District':
                continue
            flat[f'credit_deposit_ratio__{f}'] = v
        rows.append(flat)
    return {'period': label, 'districts': rows}


def build_complete_entry(dd, pk):
    dists = {d: dict(dd[d]['credit_deposit_ratio']) for d in sorted(dd)}
    fields, seen = [], set()
    for row in dists.values():
        for k in row:
            if k not in seen:
                fields.append(k)
                seen.add(k)
    return {'period': period_label(pk), 'as_on_date': as_on_date(pk), 'fy': fy_of(pk),
            'tables': {'credit_deposit_ratio': {'fields': fields, 'districts': dists}}}


def slim_row(flat):
    return dict(flat)   # MP slim == timeseries (CD-only state)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    by_period = {}
    for b in BATCHES:
        tb = get_table(b['source'], b['ti'])
        res = map_cd(tb, b['period'], dcol=b['dcol'], dep_idx=b['dep'],
                     adv_idx=b['adv'], cd_idx=b['cd'], factor=b['factor'],
                     source=b['source'], sparse=b.get('sparse', False))
        by_period[b['period']] = res
        unit = 'Cr->Lakh' if b['factor'] == CR else 'Lakh'
        flag = '' if len(res) >= 40 else '  <-- LOW'
        print(f"  {b['period']}  {b['source'][:30]:30s} -> {len(res):2d} dist [{unit}]{flag}")

    if WARN:
        print(f'\n--- {len(WARN)} CD sanity warnings ---')
        for w in WARN:
            print('  ' + w)
    if UNRESOLVED:
        print('\n--- unresolved district names (dropped) ---')
        for pk, names in sorted(UNRESOLVED.items()):
            print(f'  {pk}: {sorted(names)}')

    if args.dry_run:
        print('\n(dry) 2021-12 Indore:', by_period.get('2021-12', {}).get('Indore'))
        print('(dry) 2025-06 Indore:', by_period.get('2025-06', {}).get('Indore'))
        return

    # ---- timeseries (live wins) -----------------------------------------
    fi = json.loads(TIMESERIES_PATH.read_text())
    existing = {p['period']: p for p in fi['periods']}
    for pk in sorted(by_period):
        label = period_label(pk)
        entry = build_period_entry(by_period[pk], label)
        if label in existing:
            live_by_d = {d['district']: d for d in existing[label]['districts']}
            for row in entry['districts']:
                tgt = live_by_d.get(row['district'])
                if tgt is None:
                    existing[label]['districts'].append(row)
                else:
                    for k, v in row.items():
                        tgt.setdefault(k, v)
            existing[label]['districts'].sort(key=lambda r: r['district'])
        else:
            fi['periods'].append(entry)
    fi['periods'].sort(key=period_sort_key)
    TIMESERIES_PATH.write_text(json.dumps(fi, ensure_ascii=False, indent=2))
    print(f'\nwrote {TIMESERIES_PATH.relative_to(ROOT)} ({len(fi["periods"])} periods)')

    # ---- complete -------------------------------------------------------
    comp = json.loads(COMPLETE_PATH.read_text())
    for pk in sorted(by_period):
        new_c = build_complete_entry(by_period[pk], pk)
        if pk in comp['quarters']:
            lt = comp['quarters'][pk]['tables']
            if 'credit_deposit_ratio' not in lt:
                lt['credit_deposit_ratio'] = new_c['tables']['credit_deposit_ratio']
            else:
                ld = lt['credit_deposit_ratio']['districts']
                for d, row in new_c['tables']['credit_deposit_ratio']['districts'].items():
                    ld.setdefault(d, {})
                    for f, v in row.items():
                        ld[d].setdefault(f, v)
        else:
            comp['quarters'][pk] = new_c
    comp['quarters'] = dict(sorted(comp['quarters'].items()))
    COMPLETE_PATH.write_text(json.dumps(comp, ensure_ascii=False, indent=2))
    print(f'wrote {COMPLETE_PATH.relative_to(ROOT)} ({len(comp["quarters"])} quarters)')

    # ---- CSV ------------------------------------------------------------
    all_fields, seen = [], set()
    for p in fi['periods']:
        for row in p['districts']:
            for k in row:
                if k not in ('district', 'period') and k not in seen:
                    all_fields.append(k)
                    seen.add(k)
    all_fields.sort()
    lines = ['district,period,' + ','.join(all_fields)]
    for p in fi['periods']:
        for row in p['districts']:
            lines.append(f"{row['district']},{row['period']}," +
                         ','.join(str(row.get(f, '')) for f in all_fields))
    CSV_PATH.write_text('\n'.join(lines) + '\n')
    print(f'wrote {CSV_PATH.relative_to(ROOT)} ({len(lines) - 1} rows)')

    # ---- slim -----------------------------------------------------------
    slim = json.loads(SLIM_PATH.read_text())
    slim['periods'] = [{'period': p['period'],
                        'districts': [slim_row(r) for r in p['districts']]}
                       for p in fi['periods']]
    SLIM_PATH.write_text(json.dumps(slim, ensure_ascii=False, indent=2))
    print(f'wrote {SLIM_PATH.relative_to(ROOT)} ({len(slim["periods"])} periods)')


if __name__ == '__main__':
    main()
