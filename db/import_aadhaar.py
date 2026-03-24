#!/usr/bin/env python3
"""Import Aadhaar enrollment data into SQLite."""

import csv
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
AADHAAR_FILE = os.path.expanduser('~/Downloads/finer_data/aadhaar/aadhaar_enrolment_2025_combined.csv')

sys.path.insert(0, os.path.dirname(__file__))
from match_districts import DistrictMatcher


def import_aadhaar():
    if not os.path.exists(AADHAAR_FILE):
        print(f"Aadhaar file not found: {AADHAAR_FILE}")
        return

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=NORMAL")

    matcher = DistrictMatcher(DB_PATH)

    total = 0
    batch = []
    district_lgd_cache = {}

    with open(AADHAAR_FILE, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            state = row.get('state', '').strip()
            district = row.get('district', '').strip()
            pincode = row.get('pincode', '').strip()
            date = row.get('date', '').strip()

            if not district or not state:
                continue

            # Cache district LGD lookup
            cache_key = (district, state)
            if cache_key not in district_lgd_cache:
                state_slug = state.lower().replace(' ', '-').replace('&', 'and')
                district_lgd_cache[cache_key] = matcher.resolve(
                    district, state_slug=state_slug, source='aadhaar'
                )
            district_lgd = district_lgd_cache[cache_key]

            try:
                age_0_5 = int(row.get('age_0_5', 0) or 0)
                age_5_17 = int(row.get('age_5_17', 0) or 0)
                age_18 = int(row.get('age_18_greater', row.get('age_18_plus', 0)) or 0)
            except (ValueError, TypeError):
                age_0_5 = age_5_17 = age_18 = 0

            batch.append((district_lgd, state, district, pincode, date, age_0_5, age_5_17, age_18))
            total += 1

            if len(batch) >= 50000:
                db.executemany(
                    """INSERT INTO aadhaar_enrollment
                    (district_lgd, state_raw, district_raw, pincode, date, age_0_5, age_5_17, age_18_plus)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    batch
                )
                db.commit()
                batch = []
                print(f"  ... {total:,} rows", end='\r')

    if batch:
        db.executemany(
            """INSERT INTO aadhaar_enrollment
            (district_lgd, state_raw, district_raw, pincode, date, age_0_5, age_5_17, age_18_plus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            batch
        )

    db.execute(
        "INSERT INTO import_log (source, file_path, rows_added) VALUES (?, ?, ?)",
        ('aadhaar', AADHAAR_FILE, total)
    )
    db.commit()

    matched = db.execute("SELECT COUNT(*) FROM aadhaar_enrollment WHERE district_lgd IS NOT NULL").fetchone()[0]
    print(f"Aadhaar: {total:,} records ({matched:,} matched)")
    matcher.report_unmatched()
    matcher.close()
    db.close()


if __name__ == '__main__':
    import_aadhaar()
