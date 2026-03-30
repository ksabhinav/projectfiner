#!/usr/bin/env python3
"""Export district-level RBI BSR-1 summary to JSON.

Output: public/rbi/bsr_district_summary.json

For each district, for years 2025 and 2020, computes:
  - total_accounts, total_credit_lakhs
  - agri_accounts, agri_credit_lakhs
  - personal_loan_accounts
  - rural_accounts, urban_accounts (metro + urban + semi-urban)
"""

import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'public', 'rbi')
OUT_FILE = os.path.join(OUT_DIR, 'bsr_district_summary.json')

EXPORT_YEARS = [2025, 2020]

AGRI_GROUP = 'I. AGRICULTURE'
PERSONAL_GROUP = 'V. PERSONAL LOANS'
RURAL_POP = 'RURAL'
# Urban = everything except RURAL
URBAN_POP = ('URBAN', 'SEMI URBAN', 'METROPOLITAN')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    # Get distinct matched districts with their state names
    # Use the canonical district/state names from the districts table
    districts_q = db.execute("""
        SELECT DISTINCT
            d.lgd_code,
            d.name AS district_name,
            s.name AS state_name
        FROM rbi_bsr_credit r
        JOIN districts d ON d.lgd_code = r.district_lgd
        JOIN states s ON s.lgd_code = d.state_lgd_code
        WHERE r.district_lgd IS NOT NULL
        ORDER BY s.name, d.name
    """).fetchall()

    print(f"Found {len(districts_q):,} matched districts in rbi_bsr_credit")

    output_districts = []

    for dist_row in districts_q:
        lgd = dist_row['lgd_code']
        district_name = dist_row['district_name']
        state_name = dist_row['state_name']

        entry = {
            'lgd': str(lgd),
            'district': district_name,
            'state': state_name,
        }

        for year in EXPORT_YEARS:
            # Pull all rows for this district+year in one query
            rows = db.execute("""
                SELECT population_group, occupation_group,
                       no_of_accounts, credit_outstanding_lakhs
                FROM rbi_bsr_credit
                WHERE district_lgd = ? AND year = ?
            """, (lgd, year)).fetchall()

            if not rows:
                entry[str(year)] = None
                continue

            total_accounts = 0
            total_credit = 0.0
            agri_accounts = 0
            agri_credit = 0.0
            personal_accounts = 0
            rural_accounts = 0
            urban_accounts = 0

            for r in rows:
                pop = r['population_group']
                occ = r['occupation_group']
                accts = r['no_of_accounts'] or 0
                credit = r['credit_outstanding_lakhs'] or 0.0

                total_accounts += accts
                total_credit += credit

                if occ == AGRI_GROUP:
                    agri_accounts += accts
                    agri_credit += credit

                if occ == PERSONAL_GROUP:
                    personal_accounts += accts

                if pop == RURAL_POP:
                    rural_accounts += accts
                elif pop in URBAN_POP:
                    urban_accounts += accts

            entry[str(year)] = {
                'total_accounts': total_accounts,
                'total_credit_lakhs': round(total_credit, 2),
                'agri_accounts': agri_accounts,
                'agri_credit_lakhs': round(agri_credit, 2),
                'personal_loan_accounts': personal_accounts,
                'rural_accounts': rural_accounts,
                'urban_accounts': urban_accounts,
            }

        output_districts.append(entry)

    output = {
        'meta': {
            'source': 'RBI BSR-1',
            'unit_credit': 'Rs Lakhs',
            'years': EXPORT_YEARS,
            'description': (
                'District-level bank credit aggregated from RBI BSR-1 '
                '(Bank Group, Population Group, Occupation Group). '
                'total_accounts and total_credit_lakhs sum across all bank groups, '
                'population groups, and occupation groups for the district.'
            ),
        },
        'districts': output_districts,
    }

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = os.path.getsize(OUT_FILE) / 1024
    print(f"Exported {len(output_districts):,} districts to {OUT_FILE}")
    print(f"File size: {size_kb:.1f} KB")

    # Quick sanity check
    with_2025 = sum(1 for d in output_districts if d.get('2025') is not None)
    with_2020 = sum(1 for d in output_districts if d.get('2020') is not None)
    print(f"Districts with 2025 data: {with_2025:,}")
    print(f"Districts with 2020 data: {with_2020:,}")

    db.close()


if __name__ == '__main__':
    main()
