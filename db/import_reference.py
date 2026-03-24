#!/usr/bin/env python3
"""Import reference data: states, districts, aliases from district_lgd_codes.json."""

import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT = os.path.dirname(os.path.dirname(__file__))
LGD_FILE = os.path.join(PROJECT, 'public', 'district_lgd_codes.json')

# Map state names to slugs (filesystem format)
STATE_SLUGS = {
    'Andaman and Nicobar Islands': 'andaman-nicobar',
    'Andhra Pradesh': 'andhra-pradesh',
    'Arunachal Pradesh': 'arunachal-pradesh',
    'Assam': 'assam',
    'Bihar': 'bihar',
    'Chandigarh': 'chandigarh',
    'Chhattisgarh': 'chhattisgarh',
    'Dadra and Nagar Haveli and Daman and Diu': 'dadra-nagar-haveli',
    'Delhi': 'delhi',
    'Goa': 'goa',
    'Gujarat': 'gujarat',
    'Haryana': 'haryana',
    'Himachal Pradesh': 'himachal-pradesh',
    'Jammu and Kashmir': 'jammu-kashmir',
    'Jharkhand': 'jharkhand',
    'Karnataka': 'karnataka',
    'Kerala': 'kerala',
    'Ladakh': 'ladakh',
    'Lakshadweep': 'lakshadweep',
    'Madhya Pradesh': 'madhya-pradesh',
    'Maharashtra': 'maharashtra',
    'Manipur': 'manipur',
    'Meghalaya': 'meghalaya',
    'Mizoram': 'mizoram',
    'Nagaland': 'nagaland',
    'Odisha': 'odisha',
    'Puducherry': 'puducherry',
    'Punjab': 'punjab',
    'Rajasthan': 'rajasthan',
    'Sikkim': 'sikkim',
    'Tamil Nadu': 'tamil-nadu',
    'Telangana': 'telangana',
    'Tripura': 'tripura',
    'Uttar Pradesh': 'uttar-pradesh',
    'Uttarakhand': 'uttarakhand',
    'West Bengal': 'west-bengal',
}


def import_reference():
    with open(LGD_FILE) as f:
        data = json.load(f)

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys=ON")

    # Collect unique states
    states_seen = {}
    for d in data['districts']:
        state_name = d['state']
        state_lgd = d['state_lgd_code']
        if state_lgd not in states_seen:
            states_seen[state_lgd] = state_name

    # Insert states
    for lgd, name in sorted(states_seen.items()):
        slug = STATE_SLUGS.get(name, name.lower().replace(' ', '-'))
        db.execute(
            "INSERT OR IGNORE INTO states (lgd_code, name, slug) VALUES (?, ?, ?)",
            (lgd, name, slug)
        )
    db.commit()
    print(f"States: {db.execute('SELECT COUNT(*) FROM states').fetchone()[0]}")

    # Insert districts
    for d in data['districts']:
        db.execute(
            "INSERT OR IGNORE INTO districts (lgd_code, name, state_lgd_code, census_2011_code) VALUES (?, ?, ?, ?)",
            (d['lgd_code'], d['district'], d['state_lgd_code'], d.get('census_2011_code'))
        )
    db.commit()
    print(f"Districts: {db.execute('SELECT COUNT(*) FROM districts').fetchone()[0]}")

    # Insert aliases
    alias_count = 0
    for d in data['districts']:
        for alias in d.get('aliases', []):
            if alias and alias != d['district']:
                try:
                    db.execute(
                        "INSERT OR IGNORE INTO district_aliases (district_lgd, alias, source) VALUES (?, ?, ?)",
                        (d['lgd_code'], alias, 'lgd')
                    )
                    alias_count += 1
                except Exception:
                    pass
    db.commit()
    print(f"Aliases: {db.execute('SELECT COUNT(*) FROM district_aliases').fetchone()[0]}")

    # Also seed periods from known range
    import re
    MONTHS = {'January': '01', 'February': '02', 'March': '03', 'April': '04',
              'May': '05', 'June': '06', 'July': '07', 'August': '08',
              'September': '09', 'October': '10', 'November': '11', 'December': '12'}

    # Generate periods from June 2017 to March 2026
    for year in range(2017, 2027):
        for month_name, month_num in MONTHS.items():
            if month_name in ('March', 'June', 'September', 'December'):
                label = f"{month_name} {year}"
                code = f"{year}-{month_num}"
                # Determine FY
                if int(month_num) >= 4:
                    fy = f"{year}-{str(year+1)[-2:]}"
                else:
                    fy = f"{year-1}-{str(year)[-2:]}"
                db.execute(
                    "INSERT OR IGNORE INTO periods (label, code, fy) VALUES (?, ?, ?)",
                    (label, code, fy)
                )
    db.commit()
    print(f"Periods: {db.execute('SELECT COUNT(*) FROM periods').fetchone()[0]}")

    # Log import
    db.execute(
        "INSERT INTO import_log (source, file_path, rows_added, notes) VALUES (?, ?, ?, ?)",
        ('reference', LGD_FILE, len(data['districts']), f"{len(states_seen)} states, {len(data['districts'])} districts")
    )
    db.commit()
    db.close()


if __name__ == '__main__':
    import_reference()
