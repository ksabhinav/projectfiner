#!/usr/bin/env python3
"""Export NFHS-5 data to static JSON files for the FINER frontend.

Generates:
  public/nfhs/health_insurance_district.json  -- district-level health insurance (637 districts)
  public/nfhs/bank_accounts_state.json        -- state-level women bank account (36 states)
  public/nfhs/mobile_phones_state.json        -- state-level women mobile phone (36 states)
  public/nfhs/manifest.json                   -- metadata about available NFHS datasets

Each JSON file is a simple object suitable for map overlays and analysis pages.
"""

import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'public', 'nfhs')


def parse_num(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def export_health_insurance_district(db, out_dir):
    """Export health insurance coverage at district level."""
    rows = db.execute("""
        SELECT
            nd.district_lgd,
            nd.district_raw,
            nd.state_raw,
            nd.nfhs5_numeric,
            nd.nfhs4_numeric,
            d.name AS district_name,
            s.slug AS state_slug
        FROM nfhs_data nd
        JOIN nfhs_indicators ni ON nd.indicator_id = ni.id
        LEFT JOIN districts d ON nd.district_lgd = d.lgd_code
        LEFT JOIN states s ON d.state_lgd_code = s.lgd_code
        WHERE ni.name LIKE '%health insurance%'
        AND nd.district_lgd IS NOT NULL
        ORDER BY s.slug, d.name
    """).fetchall()

    districts = []
    for row in rows:
        district_lgd, district_raw, state_raw, nfhs5, nfhs4, district_name, state_slug = row
        districts.append({
            'lgd': district_lgd,
            'district': district_name or district_raw,
            'state': state_slug or state_raw,
            'nfhs5': nfhs5,
            'nfhs4': nfhs4,
        })

    result = {
        'indicator': 'health_insurance',
        'label': 'Health Insurance Coverage',
        'description': 'Households with any usual member covered under a health insurance/financing scheme (%)',
        'source': 'NFHS-5 (2019-21)',
        'unit': '%',
        'level': 'district',
        'districts': districts,
    }
    path = os.path.join(out_dir, 'health_insurance_district.json')
    with open(path, 'w') as f:
        json.dump(result, f, separators=(',', ':'))
    print(f"  {path}: {len(districts)} districts")
    return len(districts)


def export_state_indicator(db, out_dir, indicator_name_fragment, key, label, description):
    """Export a state-level NFHS indicator."""
    rows = db.execute("""
        SELECT
            nsd.state_lgd,
            nsd.state_raw,
            nsd.nfhs5_urban,
            nsd.nfhs5_rural,
            nsd.nfhs5_total,
            nsd.nfhs4_total,
            s.slug AS state_slug,
            s.name AS state_name
        FROM nfhs_state_data nsd
        JOIN nfhs_indicators ni ON nsd.indicator_id = ni.id
        LEFT JOIN states s ON nsd.state_lgd = s.lgd_code
        WHERE ni.name LIKE ?
        AND nsd.state_lgd IS NOT NULL
        ORDER BY s.name
    """, (f'%{indicator_name_fragment}%',)).fetchall()

    states = []
    for row in rows:
        state_lgd, state_raw, urban, rural, total, nfhs4, state_slug, state_name = row
        states.append({
            'lgd': state_lgd,
            'state': state_slug or state_raw,
            'state_name': state_name or state_raw,
            'nfhs5_urban': urban,
            'nfhs5_rural': rural,
            'nfhs5_total': total,
            'nfhs4_total': nfhs4,
        })

    result = {
        'indicator': key,
        'label': label,
        'description': description,
        'source': 'NFHS-5 (2019-21)',
        'unit': '%',
        'level': 'state',
        'note': 'District-level data not available for this indicator in NFHS-5',
        'states': states,
    }
    path = os.path.join(out_dir, f'{key}_state.json')
    with open(path, 'w') as f:
        json.dump(result, f, separators=(',', ':'))
    print(f"  {path}: {len(states)} states")
    return len(states)


def export_nfhs():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")

    # Check if nfhs_state_data table exists
    has_state_table = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='nfhs_state_data'"
    ).fetchone()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Exporting NFHS data to {OUTPUT_DIR}/")

    manifest = {
        'datasets': [],
        'generated_at': __import__('datetime').datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    # 1. District-level health insurance
    print()
    print("Exporting health insurance (district level)...")
    try:
        n = export_health_insurance_district(db, OUTPUT_DIR)
        manifest['datasets'].append({
            'key': 'health_insurance',
            'label': 'Health Insurance Coverage',
            'level': 'district',
            'districts': n,
            'file': 'health_insurance_district.json',
        })
    except Exception as e:
        print(f"  ERROR: {e}")

    # 2. State-level bank accounts (only if state table exists)
    if has_state_table:
        print()
        print("Exporting women bank accounts (state level)...")
        try:
            n = export_state_indicator(
                db, OUTPUT_DIR,
                'bank or savings account',
                'bank_accounts',
                'Women with Bank/Savings Account',
                'Women having a bank or savings account that they themselves use (%)',
            )
            manifest['datasets'].append({
                'key': 'bank_accounts',
                'label': 'Women with Bank/Savings Account',
                'level': 'state',
                'states': n,
                'file': 'bank_accounts_state.json',
            })
        except Exception as e:
            print(f"  ERROR: {e}")

        # 3. State-level mobile phones
        print()
        print("Exporting women mobile phones (state level)...")
        try:
            n = export_state_indicator(
                db, OUTPUT_DIR,
                'mobile phone',
                'mobile_phones',
                'Women with Mobile Phone',
                'Women having a mobile phone that they themselves use (%)',
            )
            manifest['datasets'].append({
                'key': 'mobile_phones',
                'label': 'Women with Mobile Phone',
                'level': 'state',
                'states': n,
                'file': 'mobile_phones_state.json',
            })
        except Exception as e:
            print(f"  ERROR: {e}")
    else:
        print()
        print("NOTE: nfhs_state_data table not found. Run import_nfhs_states.py first.")

    # Write manifest
    manifest_path = os.path.join(OUTPUT_DIR, 'manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print()
    print(f"Manifest: {manifest_path}")

    db.close()
    print()
    print("NFHS export complete.")


if __name__ == '__main__':
    export_nfhs()
