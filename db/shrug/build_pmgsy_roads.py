"""
Build PMGSY rural roads indicator from SHRUG v2.1.

Source: ~/Downloads/finer_data/shrug/pmgsy/pmgsy_2015_shrid.csv

PMGSY (Pradhan Mantri Gram Sadak Yojana) is the central rural road scheme.
SHRUG provides one row per village shrid with road award/completion dates,
length, and cost. Most rural shrids appear with all-empty fields (no road
yet built); only ~42k of 589k shrids have a completed road as of the SHRUG cut-off.

We aggregate to district level:
  - count of completed roads (new + upgraded)
  - total km built
  - total cost (₹ Lakhs)

shrid2 format: "XX-YY-ZZZ-VVVVV-NNNNNN" where YY = pc11 state, ZZZ = pc11 district.

Output: public/indicators/pmgsy_roads/2015-12.json
"""
import csv, json, sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = Path.home() / 'Downloads/finer_data/shrug/pmgsy/pmgsy_2015_shrid.csv'
OUT = ROOT / 'public/indicators/pmgsy_roads/2015-12.json'


def parse_float(s):
    if not s or not s.strip():
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main():
    # Shared lookup with Telangana + Ladakh PC11 aliases
    import sys as _sys; _sys.path.insert(0, str(Path(__file__).parent))
    from _shared import build_finer_lookup  # type: ignore
    finer = build_finer_lookup(ROOT / 'db/finer.db')

    # Aggregate per (pc11_state, pc11_dist)
    agg = defaultdict(lambda: {
        'roads_new': 0, 'roads_upg': 0,
        'km_new': 0.0, 'km_upg': 0.0,
        'cost_new_lakhs': 0.0, 'cost_upg_lakhs': 0.0,
    })

    n_total, n_aggregated = 0, 0
    with open(SRC) as f:
        for row in csv.DictReader(f):
            n_total += 1
            shrid = row.get('shrid2', '')
            parts = shrid.split('-')
            if len(parts) < 3:
                continue
            key = (parts[1], parts[2])  # (pc11_state, pc11_dist)
            comp_new = row.get('road_comp_date_new', '').strip()
            comp_upg = row.get('road_comp_date_upg', '').strip()
            len_new = parse_float(row.get('road_length_new', ''))
            len_upg = parse_float(row.get('road_length_upg', ''))
            cost_new = parse_float(row.get('road_cost_new', ''))
            cost_upg = parse_float(row.get('road_cost_upg', ''))
            # Only count rows with at least one completed road
            if not (comp_new or comp_upg or len_new or len_upg):
                continue
            n_aggregated += 1
            d = agg[key]
            if comp_new or len_new:
                d['roads_new'] += 1
                if len_new: d['km_new'] += len_new
                if cost_new: d['cost_new_lakhs'] += cost_new
            if comp_upg or len_upg:
                d['roads_upg'] += 1
                if len_upg: d['km_upg'] += len_upg
                if cost_upg: d['cost_upg_lakhs'] += cost_upg

    print(f"PMGSY rows total: {n_total}, aggregated (had a road): {n_aggregated}")
    print(f"Distinct districts with PMGSY data: {len(agg)}")

    districts = []
    unmatched = 0
    for key, d in agg.items():
        if key not in finer:
            unmatched += 1
            continue
        lgd, dname, sname = finer[key]
        roads_total = d['roads_new'] + d['roads_upg']
        km_total = d['km_new'] + d['km_upg']
        cost_total = d['cost_new_lakhs'] + d['cost_upg_lakhs']
        districts.append({
            'district_lgd': lgd,
            'district': dname,
            'state': sname,
            'roads_total': roads_total,
            'roads_new': d['roads_new'],
            'roads_upg': d['roads_upg'],
            'km_total': round(km_total, 1),
            'km_new': round(d['km_new'], 1),
            'km_upg': round(d['km_upg'], 1),
            'cost_total_lakhs': round(cost_total, 1),
        })

    print(f"FINER districts matched: {len(districts)} (unmatched: {unmatched})")

    out = {
        'indicator': 'pmgsy_roads',
        'period': '2015-12',
        'period_label': 'PMGSY (cumulative through 2015)',
        'source': 'SHRUG v2.1 (Development Data Lab) — PMGSY 2015 cumulative shrid-level data',
        'license': 'CC BY-NC-SA 4.0',
        'districts': districts,
    }
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"  wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size/1024:.1f} KB)")


if __name__ == '__main__':
    main()
