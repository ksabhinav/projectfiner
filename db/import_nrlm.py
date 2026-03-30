#!/usr/bin/env python3
"""Import NRLM SHG district-level data (G1 report) into SQLite.

Source CSV: ~/Downloads/finer_data/nrlm/shg_district_g1.csv
Table: nrlm_shg
"""

import csv
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
NRLM_CSV = os.path.expanduser('~/Downloads/finer_data/nrlm/shg_district_g1.csv')

sys.path.insert(0, os.path.dirname(__file__))
from match_districts import DistrictMatcher

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS nrlm_shg (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lgd_code        INTEGER REFERENCES districts(lgd_code),
    district_raw    TEXT NOT NULL,
    state_raw       TEXT NOT NULL,
    state_code      TEXT,
    shg_new         INTEGER,
    shg_revived     INTEGER,
    shg_prenrlm     INTEGER,
    shg_total       INTEGER,
    members_total   INTEGER,
    scraped_date    TEXT
);

CREATE INDEX IF NOT EXISTS idx_nrlm_lgd ON nrlm_shg(lgd_code);
CREATE INDEX IF NOT EXISTS idx_nrlm_state ON nrlm_shg(state_raw);
"""

# Map NRLM state names to state slugs used in the FINER DB
# Slugs verified against actual states.slug column in finer.db
NRLM_STATE_SLUG_MAP = {
    'ANDAMAN AND NICOBAR': 'andaman-nicobar',
    'ANDHRA PRADESH': 'andhra-pradesh',
    'ARUNACHAL PRADESH': 'arunachal-pradesh',
    'ASSAM': 'assam',
    'BIHAR': 'bihar',
    'CHHATTISGARH': 'chhattisgarh',
    'GOA': 'goa',
    'GUJARAT': 'gujarat',
    'HARYANA': 'haryana',
    'HIMACHAL PRADESH': 'himachal-pradesh',
    'JAMMU AND KASHMIR': 'jammu-kashmir',
    'JHARKHAND': 'jharkhand',
    'KARNATAKA': 'karnataka',
    'KERALA': 'kerala',
    'LADAKH': 'ladakh',
    'LAKSHADWEEP': 'lakshadweep',
    'MADHYA PRADESH': 'madhya-pradesh',
    'MAHARASHTRA': 'maharashtra',
    'MANIPUR': 'manipur',
    'MEGHALAYA': 'meghalaya',
    'MIZORAM': 'mizoram',
    'NAGALAND': 'nagaland',
    'ODISHA': 'odisha',
    'PUDUCHERRY': 'puducherry',
    'PUNJAB': 'punjab',
    'RAJASTHAN': 'rajasthan',
    'SIKKIM': 'sikkim',
    'TAMIL NADU': 'tamil-nadu',
    'TELANGANA': 'telangana',
    'TRIPURA': 'tripura',
    'UTTAR PRADESH': 'uttar-pradesh',
    'UTTARAKHAND': 'uttarakhand',
    'WEST BENGAL': 'west-bengal',
    'THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU': 'the-dadra-and-nagar-haveli-and-daman-and-diu',
}


def parse_int_or_none(val):
    if val is None or str(val).strip() in ('', 'None', 'NA', '-'):
        return None
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


def import_nrlm():
    if not os.path.exists(NRLM_CSV):
        print(f"ERROR: NRLM CSV not found: {NRLM_CSV}")
        sys.exit(1)

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    # Create table if not exists
    db.executescript(CREATE_TABLE)
    db.commit()

    # Clear any previous import
    existing = db.execute("SELECT COUNT(*) FROM nrlm_shg").fetchone()[0]
    if existing > 0:
        print(f"Clearing {existing} existing rows from nrlm_shg...")
        db.execute("DELETE FROM nrlm_shg")
        db.commit()

    matcher = DistrictMatcher(DB_PATH)

    with open(NRLM_CSV, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"NRLM: {len(rows)} rows from {NRLM_CSV}")

    batch = []
    total = 0
    matched = 0

    for row in rows:
        state_name = row['state_name'].strip()
        state_code = row['state_code'].strip()
        district_name = row['district_name'].strip()

        state_slug = NRLM_STATE_SLUG_MAP.get(state_name)
        lgd_code = matcher.resolve(
            district_name,
            state_slug=state_slug,
            source='nrlm'
        )

        if lgd_code:
            matched += 1

        batch.append((
            lgd_code,
            district_name,
            state_name,
            state_code,
            parse_int_or_none(row['shg_new']),
            parse_int_or_none(row['shg_revived']),
            parse_int_or_none(row['shg_prenrlm']),
            parse_int_or_none(row['shg_total']),
            parse_int_or_none(row['members_total']),
            row['scraped_date'],
        ))
        total += 1

    db.executemany(
        """INSERT INTO nrlm_shg
           (lgd_code, district_raw, state_raw, state_code,
            shg_new, shg_revived, shg_prenrlm, shg_total,
            members_total, scraped_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        batch
    )

    db.execute(
        "INSERT INTO import_log (source, file_path, rows_added) VALUES (?, ?, ?)",
        ('nrlm_shg', NRLM_CSV, total)
    )
    db.commit()

    print(f"Imported: {total:,} rows | LGD-matched: {matched:,} | Unmatched: {total - matched:,}")
    matcher.report_unmatched()
    matcher.close()
    db.close()
    print("Done.")


if __name__ == '__main__':
    import_nrlm()
