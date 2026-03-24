#!/usr/bin/env python3
"""Import NFHS-5 district-level data into SQLite."""

import csv
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
NFHS_FILE = os.path.expanduser('~/Downloads/finer_data/nfhs5/India.csv')

sys.path.insert(0, os.path.dirname(__file__))
from match_districts import DistrictMatcher


def parse_num(val):
    if not val or val.strip() in ('', '-', 'na', 'NA', '*'):
        return None
    try:
        return float(val.strip().replace(',', '').replace('%', ''))
    except (ValueError, TypeError):
        return None


def import_nfhs():
    if not os.path.exists(NFHS_FILE):
        print(f"NFHS file not found: {NFHS_FILE}")
        return

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    matcher = DistrictMatcher(DB_PATH)

    # Read CSV
    with open(NFHS_FILE, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"NFHS-5: {len(rows)} rows from {NFHS_FILE}")

    # Build indicator cache
    indicator_cache = {}
    total = 0
    batch = []

    for row in rows:
        state = row.get('State', '').strip()
        district = row.get('District', row.get('DISTRICT', '')).strip()
        state_code = row.get('ST_CEN_CD', '').strip()
        indicator_text = row.get('Indicator', row.get('Category', '')).strip()
        nfhs5_val = row.get('NFHS 5', row.get('NFHS-5', '')).strip()
        nfhs4_val = row.get('NFHS 4', row.get('NFHS-4', '')).strip()

        if not indicator_text or not district:
            continue

        # Get or create indicator
        if indicator_text not in indicator_cache:
            db.execute(
                "INSERT OR IGNORE INTO nfhs_indicators (name) VALUES (?)",
                (indicator_text,)
            )
            iid = db.execute("SELECT id FROM nfhs_indicators WHERE name=?", (indicator_text,)).fetchone()
            indicator_cache[indicator_text] = iid[0] if iid else None

        indicator_id = indicator_cache[indicator_text]
        if not indicator_id:
            continue

        # Match district
        # Use state name to help matching
        state_slug = state.lower().replace(' ', '-')
        district_lgd = matcher.resolve(district, state_slug=state_slug, source='nfhs')

        batch.append((
            district_lgd, district, state, state_code,
            indicator_id, nfhs5_val, parse_num(nfhs5_val),
            nfhs4_val, parse_num(nfhs4_val)
        ))
        total += 1

        if len(batch) >= 5000:
            db.executemany(
                """INSERT INTO nfhs_data
                (district_lgd, district_raw, state_raw, state_code, indicator_id,
                 nfhs5_value, nfhs5_numeric, nfhs4_value, nfhs4_numeric)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                batch
            )
            batch = []

    if batch:
        db.executemany(
            """INSERT INTO nfhs_data
            (district_lgd, district_raw, state_raw, state_code, indicator_id,
             nfhs5_value, nfhs5_numeric, nfhs4_value, nfhs4_numeric)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            batch
        )

    db.execute(
        "INSERT INTO import_log (source, file_path, rows_added) VALUES (?, ?, ?)",
        ('nfhs', NFHS_FILE, total)
    )
    db.commit()

    matched = db.execute("SELECT COUNT(*) FROM nfhs_data WHERE district_lgd IS NOT NULL").fetchone()[0]
    print(f"NFHS-5: {total:,} records ({matched:,} matched)")
    print(f"Indicators: {db.execute('SELECT COUNT(*) FROM nfhs_indicators').fetchone()[0]}")
    matcher.report_unmatched()
    matcher.close()
    db.close()


if __name__ == '__main__':
    import_nfhs()
