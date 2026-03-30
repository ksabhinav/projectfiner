#!/usr/bin/env python3
"""Import RBI BSR-1 and Detailed Occupation credit data into SQLite.

Two tables created:
  rbi_bsr_credit   — district × year × population_group × occupation_group
  rbi_bsr_detailed — district × year × major_sector × sub_sector × occupation_activity
"""

import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')

BSR1_FILE = os.path.expanduser(
    '~/Downloads/_Bank Credit of SCBs - Bank Group, Population Group, Occupation (Sector), District Wise - Annual.txt'
)
DETAILED_FILE = os.path.expanduser(
    '~/Downloads/DISTRICT-WISE CLASSIFICATION OF OUTSTANDING CREDIT OF SCHEDULED COMMERCIAL BANKS ACCORDING TO DETAILED OCCUPATION .txt'
)

sys.path.insert(0, os.path.dirname(__file__))
from match_districts import DistrictMatcher

# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS rbi_bsr_credit (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    district_lgd        INTEGER REFERENCES districts(lgd_code),
    district_raw        TEXT NOT NULL,
    state_raw           TEXT NOT NULL,
    year                INTEGER NOT NULL,
    population_group    TEXT NOT NULL,
    occupation_group    TEXT NOT NULL,
    no_of_accounts      INTEGER,
    credit_outstanding_lakhs REAL
);

CREATE INDEX IF NOT EXISTS idx_rbi_bsr_district_year
    ON rbi_bsr_credit(district_lgd, year);
CREATE INDEX IF NOT EXISTS idx_rbi_bsr_year
    ON rbi_bsr_credit(year);
CREATE INDEX IF NOT EXISTS idx_rbi_bsr_occ
    ON rbi_bsr_credit(occupation_group);

CREATE TABLE IF NOT EXISTS rbi_bsr_detailed (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    district_lgd        INTEGER REFERENCES districts(lgd_code),
    district_raw        TEXT NOT NULL,
    state_raw           TEXT NOT NULL,
    year                INTEGER NOT NULL,
    major_sector        TEXT NOT NULL,
    sub_sector          TEXT,
    detailed_sector     TEXT,
    occupation_activity TEXT NOT NULL,
    outstanding_lakhs   REAL
);

CREATE INDEX IF NOT EXISTS idx_rbi_det_district_year
    ON rbi_bsr_detailed(district_lgd, year);
CREATE INDEX IF NOT EXISTS idx_rbi_det_year
    ON rbi_bsr_detailed(year);
CREATE INDEX IF NOT EXISTS idx_rbi_det_sector
    ON rbi_bsr_detailed(major_sector);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_int(val):
    """Parse integer, removing commas. Returns None for empty/dash."""
    if not val or val.strip() in ('', '-', 'NA', 'na'):
        return None
    try:
        return int(val.strip().replace(',', ''))
    except (ValueError, TypeError):
        return None


def parse_float(val):
    """Parse float. Returns None for empty/dash."""
    if not val or val.strip() in ('', '-', 'NA', 'na'):
        return None
    try:
        return float(val.strip().replace(',', ''))
    except (ValueError, TypeError):
        return None


def make_state_slug(state_name):
    """Convert state name to slug for DistrictMatcher."""
    return state_name.strip().lower().replace(' & ', '-').replace(' ', '-').replace('/', '-')


# ---------------------------------------------------------------------------
# Import BSR-1
# ---------------------------------------------------------------------------

def import_bsr1(db, matcher):
    if not os.path.exists(BSR1_FILE):
        print(f"BSR-1 file not found: {BSR1_FILE}")
        return 0

    print(f"Importing BSR-1 from: {BSR1_FILE}")

    batch = []
    total = 0
    skipped = 0
    BATCH_SIZE = 10000

    with open(BSR1_FILE, encoding='utf-8-sig') as f:
        for line_no, line in enumerate(f):
            # Skip header block (first 7 lines: lines 0-6, data starts line 7)
            if line_no < 7:
                continue

            line = line.rstrip('\n')
            if not line.strip():
                continue

            parts = line.split('\t')
            if len(parts) < 11:
                skipped += 1
                continue

            year_str    = parts[0].strip()
            # parts[1] = Region, parts[2] = State, parts[3] = District
            state_raw   = parts[2].strip()
            district_raw = parts[3].strip()
            pop_group   = parts[4].strip()
            # parts[5] = Bank Group (not stored in aggregated table)
            occ_group   = parts[6].strip()
            # parts[7] = Occupation Sub-Group (not stored)
            accounts_str = parts[8].strip()
            # parts[9] = Credit Limit (not used)
            outstanding_str = parts[10].strip()

            if not year_str.isdigit():
                skipped += 1
                continue

            year = int(year_str)

            # Amount is in Rs Crores → multiply by 100 to get Lakhs
            outstanding_crores = parse_float(outstanding_str)
            outstanding_lakhs = (outstanding_crores * 100.0) if outstanding_crores is not None else None

            accounts = parse_int(accounts_str)

            state_slug = make_state_slug(state_raw)
            district_lgd = matcher.resolve(district_raw, state_slug=state_slug, source='rbi_bsr1')

            batch.append((
                district_lgd, district_raw, state_raw,
                year, pop_group, occ_group,
                accounts, outstanding_lakhs
            ))
            total += 1

            if len(batch) >= BATCH_SIZE:
                db.executemany(
                    """INSERT INTO rbi_bsr_credit
                    (district_lgd, district_raw, state_raw,
                     year, population_group, occupation_group,
                     no_of_accounts, credit_outstanding_lakhs)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    batch
                )
                db.commit()
                batch = []
                if total % 200000 == 0:
                    print(f"  BSR-1: {total:,} rows inserted...")

    if batch:
        db.executemany(
            """INSERT INTO rbi_bsr_credit
            (district_lgd, district_raw, state_raw,
             year, population_group, occupation_group,
             no_of_accounts, credit_outstanding_lakhs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            batch
        )
        db.commit()

    print(f"BSR-1: {total:,} rows imported ({skipped} skipped)")
    db.execute(
        "INSERT INTO import_log (source, file_path, rows_added, notes) VALUES (?, ?, ?, ?)",
        ('rbi_bsr1', BSR1_FILE, total, 'Bank credit by district/year/pop-group/occupation; amounts in Rs Lakhs')
    )
    db.commit()
    return total


# ---------------------------------------------------------------------------
# Import Detailed Occupation
# ---------------------------------------------------------------------------

# The year columns in header: Mar-25 → 2025, Mar-24 → 2024, etc.
YEAR_COL_MAP = {
    'Mar-25': 2025, 'Mar-24': 2024, 'Mar-23': 2023, 'Mar-22': 2022,
    'Mar-21': 2021, 'Mar-20': 2020, 'Mar-19': 2019, 'Mar-18': 2018,
    'Mar-17': 2017, 'Mar-16': 2016, 'Mar-15': 2015, 'Mar-14': 2014,
}


def import_detailed(db, matcher):
    if not os.path.exists(DETAILED_FILE):
        print(f"Detailed Occupation file not found: {DETAILED_FILE}")
        return 0

    print(f"Importing Detailed Occupation from: {DETAILED_FILE}")

    batch = []
    total = 0
    skipped = 0
    BATCH_SIZE = 10000
    year_cols = []  # list of (col_index, year)

    with open(DETAILED_FILE, encoding='utf-8-sig') as f:
        for line_no, line in enumerate(f):
            # Skip header block: lines 0-4 (5 lines), data starts line 5
            if line_no < 5:
                # Parse header row (line 4, 0-indexed) to get year column positions
                if line_no == 4:
                    parts = line.rstrip('\n').split('\t')
                    for idx, col in enumerate(parts):
                        col = col.strip()
                        if col in YEAR_COL_MAP:
                            year_cols.append((idx, YEAR_COL_MAP[col]))
                continue

            line = line.rstrip('\n')
            if not line.strip():
                continue

            parts = line.split('\t')
            if len(parts) < 6:
                skipped += 1
                continue

            state_raw        = parts[0].strip()
            district_raw     = parts[1].strip()
            major_sector     = parts[2].strip()
            sub_sector       = parts[3].strip() or None
            detailed_sector  = parts[4].strip() or None
            occ_activity     = parts[5].strip()

            if not state_raw or not district_raw or not occ_activity:
                skipped += 1
                continue

            state_slug = make_state_slug(state_raw)
            district_lgd = matcher.resolve(district_raw, state_slug=state_slug, source='rbi_detailed')

            for col_idx, year in year_cols:
                if col_idx >= len(parts):
                    continue
                val_str = parts[col_idx].strip()
                # Amount is in Rs Thousands → divide by 100 to get Lakhs
                val_thousands = parse_float(val_str)
                outstanding_lakhs = (val_thousands / 100.0) if val_thousands is not None else None

                batch.append((
                    district_lgd, district_raw, state_raw,
                    year, major_sector, sub_sector, detailed_sector, occ_activity,
                    outstanding_lakhs
                ))
                total += 1

                if len(batch) >= BATCH_SIZE:
                    db.executemany(
                        """INSERT INTO rbi_bsr_detailed
                        (district_lgd, district_raw, state_raw,
                         year, major_sector, sub_sector, detailed_sector, occupation_activity,
                         outstanding_lakhs)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        batch
                    )
                    db.commit()
                    batch = []
                    if total % 500000 == 0:
                        print(f"  Detailed: {total:,} rows inserted...")

    if batch:
        db.executemany(
            """INSERT INTO rbi_bsr_detailed
            (district_lgd, district_raw, state_raw,
             year, major_sector, sub_sector, detailed_sector, occupation_activity,
             outstanding_lakhs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            batch
        )
        db.commit()

    print(f"Detailed Occupation: {total:,} rows imported ({skipped} skipped)")
    db.execute(
        "INSERT INTO import_log (source, file_path, rows_added, notes) VALUES (?, ?, ?, ?)",
        ('rbi_detailed', DETAILED_FILE, total, 'Detailed occupation credit 2014-2025; amounts in Rs Lakhs')
    )
    db.commit()
    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA cache_size=-131072")  # 128 MB cache

    # Create tables
    db.executescript(CREATE_TABLES)
    db.commit()

    matcher = DistrictMatcher(DB_PATH)

    # Import BSR-1
    bsr1_count = import_bsr1(db, matcher)

    print()
    matched_bsr1 = db.execute(
        "SELECT COUNT(*) FROM rbi_bsr_credit WHERE district_lgd IS NOT NULL"
    ).fetchone()[0]
    total_bsr1 = db.execute("SELECT COUNT(*) FROM rbi_bsr_credit").fetchone()[0]
    print(f"BSR-1 match rate: {matched_bsr1:,}/{total_bsr1:,} rows have LGD code "
          f"({100*matched_bsr1/total_bsr1:.1f}%)")

    print()
    print("=== BSR-1 Unmatched Districts ===")
    matcher.report_unmatched()

    # Reset unmatched log for second import
    matcher.unmatched = []

    # Import Detailed Occupation
    det_count = import_detailed(db, matcher)

    print()
    matched_det = db.execute(
        "SELECT COUNT(*) FROM rbi_bsr_detailed WHERE district_lgd IS NOT NULL"
    ).fetchone()[0]
    total_det = db.execute("SELECT COUNT(*) FROM rbi_bsr_detailed").fetchone()[0]
    print(f"Detailed match rate: {matched_det:,}/{total_det:,} rows have LGD code "
          f"({100*matched_det/total_det:.1f}%)")

    print()
    print("=== Detailed Occupation Unmatched Districts ===")
    matcher.report_unmatched()

    matcher.close()
    db.close()

    print()
    print(f"=== Import complete ===")
    print(f"  rbi_bsr_credit:   {total_bsr1:,} rows")
    print(f"  rbi_bsr_detailed: {total_det:,} rows")


if __name__ == '__main__':
    main()
