#!/usr/bin/env python3
"""Import NFHS-5 state-level indicators into SQLite.

Source: ~/Downloads/finer_data/nfhs5/NFHS-5-States.csv
Columns: state, state_code, indicator, nfhs5_urban, nfhs5_rural, nfhs5_total, nfhs4_total

Imports ALL 132 state-level indicators including the two key financial inclusion
indicators that are not available at district level:
  - 122. Women having a bank or savings account that they themselves use (%)
  - 123. Women having a mobile phone that they themselves use (%)
"""

import csv
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
NFHS_STATES_FILE = os.path.expanduser('~/Downloads/finer_data/nfhs5/NFHS-5-States.csv')


def parse_num(val):
    if not val or str(val).strip() in ('', '-', 'na', 'NA', '*'):
        return None
    try:
        return float(str(val).strip().replace(',', '').replace('%', ''))
    except (ValueError, TypeError):
        return None


# Map NFHS state names to DB state names
STATE_NAME_MAP = {
    'India': None,  # skip - national aggregate
    'Andaman & Nicobar Islands': 'Andaman and Nicobar Islands',
    'Andhra Pradesh': 'Andhra Pradesh',
    'Arunachal Pradesh': 'Arunachal Pradesh',
    'Assam': 'Assam',
    'Bihar': 'Bihar',
    'Chandigarh': 'Chandigarh',
    'Chhattisgarh': 'Chhattisgarh',
    'Dadra & Nagar Haveli and Daman & Diu': 'The Dadra and Nagar Haveli and Daman and Diu',
    'NCT Delhi': 'Delhi',
    'Goa': 'Goa',
    'Gujarat': 'Gujarat',
    'Himachal Pradesh': 'Himachal Pradesh',
    'Haryana': 'Haryana',
    'Jharkhand': 'Jharkhand',
    'Jammu & Kashmir': 'Jammu and Kashmir',
    'Karnataka': 'Karnataka',
    'Kerala': 'Kerala',
    'Lakshadweep': 'Lakshadweep',
    'Ladakh': 'Ladakh',
    'Maharashtra': 'Maharashtra',
    'Meghalaya': 'Meghalaya',
    'Manipur': 'Manipur',
    'Madhya Pradesh': 'Madhya Pradesh',
    'Mizoram': 'Mizoram',
    'Nagaland': 'Nagaland',
    'Odisha': 'Odisha',
    'Punjab': 'Punjab',
    'Puducherry': 'Puducherry',
    'Rajasthan': 'Rajasthan',
    'Sikkim': 'Sikkim',
    'Telangana': 'Telangana',
    'Tamil Nadu': 'Tamil Nadu',
    'Tripura': 'Tripura',
    'Uttar Pradesh': 'Uttar Pradesh',
    'Uttarakhand': 'Uttarakhand',
    'West Bengal': 'West Bengal',
}


def clean_indicator_name(raw_name):
    """Strip leading indicator number (e.g. '122. Women having...') -> 'Women having...'"""
    name = raw_name.strip()
    # Remove footnote superscripts after text (e.g. '16, 17  (%)')
    import re
    # Remove leading number + period
    name = re.sub(r'^\d+\.\s*', '', name)
    # Normalize whitespace
    name = ' '.join(name.split())
    return name


def import_nfhs_states():
    if not os.path.exists(NFHS_STATES_FILE):
        print(f"NFHS States file not found: {NFHS_STATES_FILE}")
        return

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    # Build state name -> LGD code lookup
    state_lgd_map = {}
    for lgd_code, name in db.execute("SELECT lgd_code, name FROM states").fetchall():
        state_lgd_map[name.lower().strip()] = lgd_code

    # Read CSV
    with open(NFHS_STATES_FILE, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"NFHS States: {len(rows)} rows from {NFHS_STATES_FILE}")

    # Check/create nfhs_state_data table
    db.execute("""
        CREATE TABLE IF NOT EXISTS nfhs_state_data (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            state_lgd       INTEGER REFERENCES states(lgd_code),
            state_raw       TEXT NOT NULL,
            indicator_id    INTEGER NOT NULL REFERENCES nfhs_indicators(id),
            nfhs5_urban     REAL,
            nfhs5_rural     REAL,
            nfhs5_total     REAL,
            nfhs4_total     REAL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_nfhs_state_lgd ON nfhs_state_data(state_lgd)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_nfhs_state_ind ON nfhs_state_data(indicator_id)")

    # Clear existing state data (for idempotent re-import)
    db.execute("DELETE FROM nfhs_state_data")

    indicator_cache = {}
    total = 0
    skipped_states = set()
    batch = []

    for row in rows:
        state_raw = row.get('state', '').strip()
        indicator_raw = row.get('indicator', '').strip()

        if not state_raw or not indicator_raw:
            continue

        # Skip national aggregate
        if state_raw == 'India':
            continue

        # Map state name
        db_state_name = STATE_NAME_MAP.get(state_raw)
        if db_state_name is None:
            if state_raw not in skipped_states:
                print(f"  Skipping unknown state: {state_raw!r}")
                skipped_states.add(state_raw)
            continue

        state_lgd = state_lgd_map.get(db_state_name.lower().strip())
        if state_lgd is None:
            if state_raw not in skipped_states:
                print(f"  Could not find LGD code for: {db_state_name!r}")
                skipped_states.add(state_raw)
            continue

        # Clean indicator name (remove leading number)
        indicator_name = clean_indicator_name(indicator_raw)

        # Get or create indicator
        if indicator_name not in indicator_cache:
            db.execute(
                "INSERT OR IGNORE INTO nfhs_indicators (name) VALUES (?)",
                (indicator_name,)
            )
            row_id = db.execute(
                "SELECT id FROM nfhs_indicators WHERE name=?", (indicator_name,)
            ).fetchone()
            indicator_cache[indicator_name] = row_id[0] if row_id else None

        indicator_id = indicator_cache[indicator_name]
        if not indicator_id:
            continue

        batch.append((
            state_lgd, state_raw, indicator_id,
            parse_num(row.get('nfhs5_urban', '')),
            parse_num(row.get('nfhs5_rural', '')),
            parse_num(row.get('nfhs5_total', '')),
            parse_num(row.get('nfhs4_total', '')),
        ))
        total += 1

        if len(batch) >= 2000:
            db.executemany(
                """INSERT INTO nfhs_state_data
                   (state_lgd, state_raw, indicator_id,
                    nfhs5_urban, nfhs5_rural, nfhs5_total, nfhs4_total)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                batch
            )
            batch = []

    if batch:
        db.executemany(
            """INSERT INTO nfhs_state_data
               (state_lgd, state_raw, indicator_id,
                nfhs5_urban, nfhs5_rural, nfhs5_total, nfhs4_total)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            batch
        )

    db.execute(
        "INSERT INTO import_log (source, file_path, rows_added) VALUES (?, ?, ?)",
        ('nfhs_states', NFHS_STATES_FILE, total)
    )
    db.commit()

    matched = db.execute(
        "SELECT COUNT(*) FROM nfhs_state_data WHERE state_lgd IS NOT NULL"
    ).fetchone()[0]
    print(f"NFHS States: {total:,} records ({matched:,} matched to LGD codes)")

    # Print the two key FI indicators
    fi_check = db.execute("""
        SELECT ni.name, nsd.state_raw, nsd.nfhs5_total
        FROM nfhs_state_data nsd
        JOIN nfhs_indicators ni ON nsd.indicator_id = ni.id
        WHERE ni.name LIKE '%bank%' OR ni.name LIKE '%mobile phone%'
        ORDER BY ni.name, nsd.state_raw
        LIMIT 10
    """).fetchall()
    print()
    print("Key FI indicators imported (sample):")
    for row in fi_check:
        print(f"  [{row[0][:50]}] {row[1]}: {row[2]}%")

    db.close()


if __name__ == '__main__':
    import_nfhs_states()
