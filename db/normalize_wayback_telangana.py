#!/usr/bin/env python3
"""
Normalize the Telangana Wayback haul into FINER canonical schema.

Mirrors db/normalize_wayback_rajasthan.py. Reads raw extracts at
slbc-data/telangana/wayback/extracted/ (produced by
db/extract_wayback_telangana.py) and merges historical CD-ratio quarters
into:

  public/slbc-data/telangana/telangana_fi_timeseries.json
  public/slbc-data/telangana/telangana_complete.json
      (TG shape: quarters['YYYY-MM'] = {period, tables{cat:{fields,
       districts: {NAME: {field: value}}}}})
  public/slbc-data/telangana/telangana_fi_timeseries.csv   (wide, rebuilt)
  public/slbc-data/telangana/telangana_fi_slim.json        (rebuilt)

SCOPE (decided 2026-06-13, see CLAUDE.md Telangana section / chat):
  * ONLY the `credit_deposit_ratio` category — total_deposit / total_advance
    / cd_ratio. The live data (extract_telangana_cqr.py) starts at Dec 2022;
    this backfills the 24 quarters Dec 2016 → Sep 2022 that are missing.
  * branch_network is NOT backfilled — the Wayback "No. of Branches" column
    runs 2-3x below the live Format-C counts and may be a different metric;
    held pending source-PDF review.
  * The pre-Oct-2016 reorg era (Dec 2015 → Sep 2016, the old 10 composite
    districts where "Adilabad" covered what are now 4 districts) is SKIPPED —
    those boundaries don't align with the live 33-district structure.
  * priority_sector / non_priority_sector are not backfilled.

UNITS — the live Telangana data stores deposits/advances in CRORES (source
ANNEXURE-4 title: "...Amount in Crore", and extract_telangana_cqr.py applies
no conversion). To keep Telangana's own time series internally continuous,
the Wayback CD tables — whose titles print "(amount in lacs)" — are converted
Lakhs -> Crores (x0.01). The Dec-2022+ Format-C Wayback tables that are
already in Crores (the 2022-06/09 backfill) use factor 1. cd_ratio is a
percentage — never scaled.

  NOTE: this is the EXISTING live convention (Crores), which deviates from
  FINER's nominal "Rs. Lakhs" canon. We match live rather than introduce a
  100x seam inside one state. Flagged for a possible future state-wide
  Crores->Lakhs harmonization.

COLUMN FAMILIES (verified against actual rows, see batch comments):
  narrow  width-5  : SlNo | District | Deposits | Advances | CD% (lacs)
  wide    width-10 : SlNo | District | Br R/SU/U/Metro/Total | Dep | Adv | CD%
                     (lacs; CD% sometimes blank -> derived)
  annex4  width-12 : SR | District | TotBr | Dep R/SU/U/Total | Adv R/SU/U/Total
                     | CD%  (Crores)

CD-ratio is taken from the printed % column when present AND it agrees with
advances/deposits*100 within 5% (guards against column misalignment); else
the derived value is stored when in [5, 1000]%. Disagreements and out-of-range
rows are logged, never silently written.

DEDUPE: live site wins (existing period+district+field kept untouched).

After this runs:
  python3 db/regenerate_indicator_files_from_states.py credit_deposit_ratio
  python3 validate_data.py --state telangana
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'telangana'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback' / 'extracted'
PUB = ROOT / 'public/slbc-data' / STATE
TIMESERIES_PATH = PUB / f'{STATE}_fi_timeseries.json'
COMPLETE_PATH = PUB / f'{STATE}_complete.json'
CSV_PATH = PUB / f'{STATE}_fi_timeseries.csv'
SLIM_PATH = PUB / f'{STATE}_fi_slim.json'

# ---------------------------------------------------------------------------
# District resolver — copied verbatim from slbc-data/telangana/
# extract_telangana_cqr.py so backfilled names align exactly with live data.
# ---------------------------------------------------------------------------
TG_CANONICAL = [
    'Adilabad', 'Bhadradri Kothagudem', 'Hanumakonda', 'Hyderabad', 'Jagitial',
    'Jangoan', 'Jayashankar Bhupalapally', 'Jogulamba Gadwal', 'Kamareddy',
    'Karimnagar', 'Khammam', 'Kumuram Bheem Asifabad', 'Mahabubabad',
    'Mahabubnagar', 'Mancherial', 'Medak', 'Medchal Malkajgiri', 'Mulugu',
    'Nagarkurnool', 'Nalgonda', 'Narayanpet', 'Nirmal', 'Nizamabad',
    'Peddapalli', 'Rajanna Sircilla', 'Ranga Reddy', 'Sangareddy', 'Siddipet',
    'Suryapet', 'Vikarabad', 'Wanaparthy', 'Warangal', 'Yadadri Bhuvanagiri',
]

SKIP_ROWS = {'total', 'grand total', 'state total', 'sub total', 'sub-total',
             's.no.', 'sno', 's no', 'sl.no', 'sr.', 'sr', 'name of district',
             'name of the district', 'district', '', None}

ALIASES: dict = {}
for _d in TG_CANONICAL:
    ALIASES[_d.upper()] = _d
    ALIASES[_d.lower()] = _d

ALT_NAMES = {
    'JAGTIAL': 'Jagitial', 'JAGTIYAL': 'Jagitial',
    'JANGAON': 'Jangoan',
    'JAYASHANKAR BHUPALAPALLE': 'Jayashankar Bhupalapally',
    'JAYASHANKAR': 'Jayashankar Bhupalapally',
    'BHUPALAPALLY': 'Jayashankar Bhupalapally',
    'JOGULAMBA': 'Jogulamba Gadwal', 'GADWAL': 'Jogulamba Gadwal',
    'KOMARAM BHEEM': 'Kumuram Bheem Asifabad',
    'KUMARAM BHEEM': 'Kumuram Bheem Asifabad',
    'KUMURAM BHEEM ASIFABAD': 'Kumuram Bheem Asifabad',
    'KUMARAM BHEEM ASIFABAD': 'Kumuram Bheem Asifabad',
    'ASIFABAD': 'Kumuram Bheem Asifabad',
    'MAHBUBNAGAR': 'Mahabubnagar', 'MAHABUB NAGAR': 'Mahabubnagar',
    'MEDCHAL': 'Medchal Malkajgiri', 'MEDCHAL MALKAJGIRI': 'Medchal Malkajgiri',
    'MEDCHAL-MALKAJGIRI': 'Medchal Malkajgiri',
    'RAJANNA': 'Rajanna Sircilla', 'SIRCILLA': 'Rajanna Sircilla',
    'RAJANNA SIRCILLA': 'Rajanna Sircilla',
    'RANGAREDDY': 'Ranga Reddy', 'R.R': 'Ranga Reddy', 'R.R.': 'Ranga Reddy',
    'RANGA REDDY': 'Ranga Reddy',
    'YADADRI': 'Yadadri Bhuvanagiri', 'BHUVANAGIRI': 'Yadadri Bhuvanagiri',
    'YADADRI BHUVANAGIRI': 'Yadadri Bhuvanagiri',
    'YADADRI BHONGIR': 'Yadadri Bhuvanagiri',
    'BHADRADRI': 'Bhadradri Kothagudem', 'KOTHAGUDEM': 'Bhadradri Kothagudem',
    'BHADRADRI KOTHAGUDEM': 'Bhadradri Kothagudem',
    'WARANGAL URBAN': 'Hanumakonda',   # post-2021 rename
    'HANAMKONDA': 'Hanumakonda',
    'WARANGAL RURAL': 'Warangal',
    'HYD': 'Hyderabad',
}
ALIASES.update(ALT_NAMES)


def normalize_district(name):
    if name is None:
        return None
    s = str(name).strip()
    s = re.sub(r'^\d+[\.\s]+', '', s)
    s = s.strip(' .,*')
    if not s or s.lower() in SKIP_ROWS:
        return None
    if s.upper() in ALIASES:
        return ALIASES[s.upper()]
    if s.lower() in ALIASES:
        return ALIASES[s.lower()]
    s_norm = re.sub(r'[^A-Z]', '', s.upper())
    for k, v in ALIASES.items():
        if re.sub(r'[^A-Z]', '', k.upper()) == s_norm:
            return v
    return None


# ---------------------------------------------------------------------------
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
        print(f'ERROR: {p} missing — run db/extract_wayback_telangana.py first',
              file=sys.stderr)
        sys.exit(1)
    d = json.loads(p.read_text())
    tables = [d] + d.get('moreTables', [])
    if ti >= len(tables):
        print(f'ERROR: {name} has no table #{ti}', file=sys.stderr)
        sys.exit(1)
    return tables[ti]


WARN: list[str] = []


def map_cd(tb, pk, *, dep_idx, adv_idx, cd_idx, factor, source):
    """Build {district: {credit_deposit_ratio: {total_deposit, total_advance,
    cd_ratio}}} from one table. Self-validating (see module docstring)."""
    out = {}
    dcol = tb.get('districtColumn', 1)
    for r in tb.get('rows', []):
        # locate district from the declared column, else scan the row
        d = normalize_district(r[dcol]) if dcol < len(r) else None
        if not d:
            for c in r:
                d = normalize_district(c)
                if d:
                    break
        if not d:
            continue
        dep = parse_num(r[dep_idx]) if dep_idx < len(r) else None
        adv = parse_num(r[adv_idx]) if adv_idx < len(r) else None
        if dep is None or adv is None:
            continue
        depf, advf = float(dep) * factor, float(adv) * factor
        if depf <= 0:
            continue
        derived = advf / depf * 100.0
        printed = None
        if cd_idx is not None and cd_idx < len(r):
            pv = parse_num(r[cd_idx])
            if pv is not None:
                printed = float(pv)
        # decide cd_ratio
        cd_val = None
        if printed is not None:
            if abs(printed - derived) <= max(0.5, 0.05 * derived):
                cd_val = printed
            else:
                WARN.append(f'{pk} {source} {d}: printed CD {printed:.2f} != '
                            f'derived {derived:.2f} (dep={depf:.2f} adv={advf:.2f}) '
                            f'-> using derived')
                cd_val = derived if 5 <= derived <= 1000 else None
        else:
            cd_val = derived if 5 <= derived <= 1000 else None
        if cd_val is not None and not (5 <= cd_val <= 1000):
            WARN.append(f'{pk} {source} {d}: CD {cd_val:.2f} out of range -> dropped')
            cd_val = None
        cat = out.setdefault(d, {}).setdefault('credit_deposit_ratio', {})
        cat['total_deposit'] = fmt(depf)
        cat['total_advance'] = fmt(advf)
        if cd_val is not None:
            cat['cd_ratio'] = fmt(cd_val)
    return out


# ---------------------------------------------------------------------------
# Batches — one per period. (source, ti) chosen as the table with the most
# resolved districts for that period (auto-discovery), column indices verified
# against actual rows. factor: 0.01 = lacs->crores, 1 = already crores.
# ---------------------------------------------------------------------------
LAC = 0.01
CR = 1.0
BATCHES = [
    # --- narrow width-5 (Dep|Adv|CD%), lacs --------------------------------
    dict(period='2016-12', source='Dec_2016_Annex', ti=1, dep=2, adv=3, cd=4, factor=LAC),
    dict(period='2017-03', source='March-2017-Annexure-1-44', ti=1, dep=2, adv=3, cd=4, factor=LAC),
    dict(period='2017-06', source='16th-Meeting-Annexures', ti=1, dep=2, adv=3, cd=4, factor=LAC),
    # --- wide width-10 (Branches | Dep@7 Adv@8 CD@9), lacs -----------------
    dict(period='2017-09', source='Sept_2017_Annex', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2017-12', source='CQR-ANNEX-1217-R', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2018-03', source='CQR-0318', ti=6, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2018-06', source='CQR-ANNEX-0618', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2018-09', source='CQR-ANNEX-0918-1', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2018-12', source='Dec_2018_Annex_1-44', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2019-03', source='CQR-ANNEX-0319', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2019-06', source='CQR-ANNEX-0619', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2019-09', source='CQR-ANNEX-0919', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2019-12', source='CQR-ANNEX-1219', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2020-03', source='CQR-ANNEX-032020', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2020-06', source='CQR-ANNEX-062020', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2020-09', source='CQR-092020', ti=7, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2020-12', source='CQR-122020', ti=7, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2021-03', source='CQR-032021', ti=7, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2021-06', source='CQR-062021', ti=7, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2021-09', source='CQR-092021', ti=7, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2021-12', source='CQR-122021', ti=7, dep=7, adv=8, cd=9, factor=LAC),
    dict(period='2022-03', source='CQR-ANNEX-032022', ti=0, dep=7, adv=8, cd=9, factor=LAC),
    # --- annex4 width-12 (Dep total@6 Adv total@10 CD@11), already Crores --
    dict(period='2022-06', source='CQR-ANNEX-062022', ti=1, dep=6, adv=10, cd=11, factor=CR),
    dict(period='2022-09', source='CQR_Annex_092022', ti=1, dep=6, adv=10, cd=11, factor=CR),
]

MONTH_NAMES = {1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May',
               6: 'June', 7: 'July', 8: 'August', 9: 'September',
               10: 'October', 11: 'November', 12: 'December'}


def period_label(pk: str) -> str:
    y, m = pk.split('-')
    return f'{MONTH_NAMES[int(m)]} {y}'


def period_sort_key(p: dict):
    m = re.match(r'([A-Za-z]+)\s+(\d{4})', p.get('period', ''))
    if not m:
        return ('0000', '00')
    months = {v: f'{k:02d}' for k, v in MONTH_NAMES.items()}
    return (m.group(2), months.get(m.group(1), '00'))


def build_period_entry(district_data: dict, label: str) -> dict:
    rows = []
    for d in sorted(district_data.keys()):
        flat = {'district': d, 'period': label}
        for cat in sorted(district_data[d].keys()):
            for f, v in district_data[d][cat].items():
                flat[f'{cat}__{f}'] = v
        rows.append(flat)
    return {'period': label, 'districts': rows}


def build_complete_entry(district_data: dict, pk: str) -> dict:
    by_cat: dict[str, dict] = {}
    for d in sorted(district_data.keys()):
        for cat, fields in district_data[d].items():
            by_cat.setdefault(cat, {})[d] = dict(fields)
    tables = {}
    for cat, dists in by_cat.items():
        fnames, seen = [], set()
        for row in dists.values():
            for k in row:
                if k not in seen:
                    fnames.append(k)
                    seen.add(k)
        tables[cat] = {'fields': fnames, 'districts': dists}
    return {'period': period_label(pk), 'tables': tables}


SLIM_PREFIXES = ('credit_deposit_ratio', 'pmjdy', 'branch_network', 'kcc',
                 'shg', 'digital_transactions', 'aadhaar_authentication',
                 'pmegp')
_SLIM_RE = re.compile(r'^(' + '|'.join(SLIM_PREFIXES) + r')(_p?\d+)?__')


def slim_row(flat: dict) -> dict:
    return {k: v for k, v in flat.items()
            if k in ('district', 'period') or _SLIM_RE.match(k)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    by_period: dict[str, dict] = {}
    for b in BATCHES:
        tb = get_table(b['source'], b['ti'])
        res = map_cd(tb, b['period'], dep_idx=b['dep'], adv_idx=b['adv'],
                     cd_idx=b['cd'], factor=b['factor'], source=b['source'])
        by_period[b['period']] = res
        title = (tb.get('title') or '')[:46]
        flag = '' if len(res) >= 15 else '  <-- LOW DISTRICT COUNT'
        print(f"  {b['period']}  {b['source'][:26]:26s}#{b['ti']} "
              f"-> {len(res):2d} dist  [{title}]{flag}")

    if WARN:
        print(f'\n--- {len(WARN)} sanity warnings ---')
        for w in WARN:
            print('  ' + w)

    if args.dry_run:
        print('\n(dry run) sample December 2016 Hyderabad:',
              by_period.get('2016-12', {}).get('Hyderabad'))
        print('(dry run) sample September 2022 Hyderabad:',
              by_period.get('2022-09', {}).get('Hyderabad'))
        return

    # ---- timeseries (live wins on conflict) ------------------------------
    fi = json.loads(TIMESERIES_PATH.read_text())
    existing = {p['period']: p for p in fi['periods']}
    for pk in sorted(by_period):
        label = period_label(pk)
        new_entry = build_period_entry(by_period[pk], label)
        if label in existing:
            live_by_d = {d['district']: d for d in existing[label]['districts']}
            for row in new_entry['districts']:
                tgt = live_by_d.get(row['district'])
                if tgt is None:
                    existing[label]['districts'].append(row)
                else:
                    for k, v in row.items():
                        tgt.setdefault(k, v)
            existing[label]['districts'].sort(key=lambda r: r['district'])
        else:
            fi['periods'].append(new_entry)
    fi['periods'].sort(key=period_sort_key)
    TIMESERIES_PATH.write_text(json.dumps(fi, ensure_ascii=False, indent=2))
    print(f'\nwrote {TIMESERIES_PATH.relative_to(ROOT)} '
          f'(total periods: {len(fi["periods"])})')

    # ---- complete --------------------------------------------------------
    comp = json.loads(COMPLETE_PATH.read_text())
    for pk in sorted(by_period):
        new_c = build_complete_entry(by_period[pk], pk)
        if pk in comp['quarters']:
            live_tables = comp['quarters'][pk]['tables']
            for cat, t in new_c['tables'].items():
                if cat not in live_tables:
                    live_tables[cat] = t
                else:
                    for d, row in t['districts'].items():
                        live_tables[cat]['districts'].setdefault(d, {})
                        for f, v in row.items():
                            live_tables[cat]['districts'][d].setdefault(f, v)
                    for f in t['fields']:
                        if f not in live_tables[cat]['fields']:
                            live_tables[cat]['fields'].append(f)
        else:
            comp['quarters'][pk] = new_c
    comp['quarters'] = dict(sorted(comp['quarters'].items()))
    COMPLETE_PATH.write_text(json.dumps(comp, ensure_ascii=False, indent=2))
    print(f'wrote {COMPLETE_PATH.relative_to(ROOT)} '
          f'(total quarters: {len(comp["quarters"])})')

    # ---- CSV (wide) ------------------------------------------------------
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
            vals = [str(row.get(f, '')) for f in all_fields]
            lines.append(f"{row['district']},{row['period']}," + ','.join(vals))
    CSV_PATH.write_text('\n'.join(lines) + '\n')
    print(f'wrote {CSV_PATH.relative_to(ROOT)} '
          f'({len(lines) - 1} rows x {len(all_fields)} fields)')

    # ---- slim ------------------------------------------------------------
    slim = json.loads(SLIM_PATH.read_text())
    slim['periods'] = [
        {'period': p['period'], 'districts': [slim_row(r) for r in p['districts']]}
        for p in fi['periods']
    ]
    SLIM_PATH.write_text(json.dumps(slim, ensure_ascii=False, indent=2))
    print(f'wrote {SLIM_PATH.relative_to(ROOT)} '
          f'(total periods: {len(slim["periods"])})')


if __name__ == '__main__':
    main()
