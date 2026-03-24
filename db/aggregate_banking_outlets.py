#!/usr/bin/env python3
"""Aggregate raw banking outlet JSON files into district-level counts.

Input: public/banking-outlets/{state}.json (raw per-outlet records)
Output: public/banking-outlets/district_counts.json (small, for map choropleth)
        public/banking-outlets/state_counts.json (summary)
"""

import json
import os
import glob
from collections import defaultdict

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT, 'public', 'banking-outlets')


def aggregate():
    # district → {type → count}
    district_data = defaultdict(lambda: defaultdict(int))
    # state → {type → count}
    state_data = defaultdict(lambda: defaultdict(int))
    # district → state
    district_state = {}

    total_outlets = 0
    files_processed = 0

    for fpath in sorted(glob.glob(os.path.join(RAW_DIR, '*.json'))):
        fname = os.path.basename(fpath)
        if fname in ('district_counts.json', 'state_counts.json', 'summary.json'):
            continue

        try:
            with open(fpath) as f:
                records = json.load(f)
        except Exception as e:
            print(f"  Error reading {fname}: {e}")
            continue

        files_processed += 1
        state_slug = fname.replace('.json', '')

        for rec in records:
            state = rec.get('state', '').strip()
            district = rec.get('district', '').strip()
            outlet_type = rec.get('type', 'UNKNOWN').strip()
            pop_group = rec.get('populationGroup', '').strip()

            if not district:
                continue

            key = f"{state}|{district}"
            district_state[key] = state

            # Count by type
            district_data[key][outlet_type] += 1
            district_data[key]['TOTAL'] += 1

            # Count by population group
            if pop_group:
                district_data[key][f'pop_{pop_group.lower().replace(" ", "_")}'] += 1

            # State-level
            state_data[state][outlet_type] += 1
            state_data[state]['TOTAL'] += 1

            total_outlets += 1

        print(f"  {state_slug}: {len(records):,} outlets")

    # Build district-level output
    districts_out = []
    for key in sorted(district_data.keys()):
        state = district_state[key]
        district = key.split('|', 1)[1]
        counts = dict(district_data[key])
        districts_out.append({
            'state': state,
            'district': district,
            'total': counts.get('TOTAL', 0),
            'branch': counts.get('BRANCH', 0),
            'bc': counts.get('BC', 0),
            'csp': counts.get('CSP', 0),
            'atm': counts.get('ATM', 0),
            'office': counts.get('OFFICE', 0),
            'dbu': counts.get('DBU', 0),
            'rural': counts.get('pop_rural', 0),
            'semi_urban': counts.get('pop_semi_urban', 0),
            'urban': counts.get('pop_urban', 0),
            'metro': counts.get('pop_metropolitan', 0),
        })

    # Write district counts (small file for map)
    district_out = {
        'source': 'RBI DBIE Banking Outlet & ATM Locator',
        'url': 'https://data.rbi.org.in/DBIE/',
        'total_outlets': total_outlets,
        'total_districts': len(districts_out),
        'districts': districts_out,
    }
    out_path = os.path.join(RAW_DIR, 'district_counts.json')
    with open(out_path, 'w') as f:
        json.dump(district_out, f, separators=(',', ':'))
    size = os.path.getsize(out_path) / 1024
    print(f"\nDistrict counts: {len(districts_out)} districts → {size:.0f} KB")

    # Write state counts (summary)
    states_out = []
    for state in sorted(state_data.keys()):
        counts = dict(state_data[state])
        states_out.append({
            'state': state,
            'total': counts.get('TOTAL', 0),
            'branch': counts.get('BRANCH', 0),
            'bc': counts.get('BC', 0),
            'csp': counts.get('CSP', 0),
            'atm': counts.get('ATM', 0),
            'office': counts.get('OFFICE', 0),
            'dbu': counts.get('DBU', 0),
        })

    state_out_path = os.path.join(RAW_DIR, 'state_counts.json')
    with open(state_out_path, 'w') as f:
        json.dump({'states': states_out, 'total': total_outlets}, f, indent=2)
    print(f"State counts: {len(states_out)} states")
    print(f"\nTotal: {total_outlets:,} outlets across {files_processed} states")


if __name__ == '__main__':
    aggregate()
