#!/usr/bin/env python3
"""Initialize the FINER SQLite database schema."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')

SCHEMA = """
-- ============================================================
-- REFERENCE TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS states (
    lgd_code      INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    slug          TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS districts (
    lgd_code        INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    state_lgd_code  INTEGER NOT NULL REFERENCES states(lgd_code),
    census_2011_code TEXT,
    UNIQUE(name, state_lgd_code)
);

CREATE TABLE IF NOT EXISTS district_aliases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    district_lgd INTEGER NOT NULL REFERENCES districts(lgd_code),
    alias        TEXT NOT NULL,
    source       TEXT,
    UNIQUE(alias, district_lgd)
);

CREATE TABLE IF NOT EXISTS periods (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    label      TEXT NOT NULL UNIQUE,
    code       TEXT NOT NULL UNIQUE,
    fy         TEXT
);

-- ============================================================
-- SLBC DATA (EAV model)
-- ============================================================

CREATE TABLE IF NOT EXISTS slbc_fields (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    field_key     TEXT NOT NULL UNIQUE,
    category      TEXT NOT NULL,
    field_name    TEXT NOT NULL,
    display_name  TEXT,
    unit          TEXT
);

CREATE TABLE IF NOT EXISTS slbc_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    state_lgd_code  INTEGER NOT NULL REFERENCES states(lgd_code),
    district_lgd    INTEGER NOT NULL REFERENCES districts(lgd_code),
    period_id       INTEGER NOT NULL REFERENCES periods(id),
    field_id        INTEGER NOT NULL REFERENCES slbc_fields(id),
    value_text      TEXT,
    value_numeric   REAL,
    source_file     TEXT
);

CREATE INDEX IF NOT EXISTS idx_slbc_state_period ON slbc_data(state_lgd_code, period_id);
CREATE INDEX IF NOT EXISTS idx_slbc_district_period ON slbc_data(district_lgd, period_id);
CREATE INDEX IF NOT EXISTS idx_slbc_field ON slbc_data(field_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_slbc_unique ON slbc_data(district_lgd, period_id, field_id);

-- ============================================================
-- PHONEPE UPI DATA
-- ============================================================

CREATE TABLE IF NOT EXISTS phonepe_data (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    district_lgd      INTEGER REFERENCES districts(lgd_code),
    district_name_raw TEXT NOT NULL,
    state_slug        TEXT NOT NULL,
    period_id         INTEGER NOT NULL REFERENCES periods(id),
    transaction_count INTEGER,
    transaction_amount REAL
);

CREATE INDEX IF NOT EXISTS idx_phonepe_period ON phonepe_data(period_id);
CREATE INDEX IF NOT EXISTS idx_phonepe_district ON phonepe_data(district_lgd);

-- ============================================================
-- NFHS-5 DATA
-- ============================================================

CREATE TABLE IF NOT EXISTS nfhs_indicators (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    category   TEXT
);

CREATE TABLE IF NOT EXISTS nfhs_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    district_lgd    INTEGER REFERENCES districts(lgd_code),
    district_raw    TEXT NOT NULL,
    state_raw       TEXT NOT NULL,
    state_code      TEXT,
    indicator_id    INTEGER NOT NULL REFERENCES nfhs_indicators(id),
    nfhs5_value     TEXT,
    nfhs5_numeric   REAL,
    nfhs4_value     TEXT,
    nfhs4_numeric   REAL
);

CREATE INDEX IF NOT EXISTS idx_nfhs_district ON nfhs_data(district_lgd);
CREATE INDEX IF NOT EXISTS idx_nfhs_indicator ON nfhs_data(indicator_id);

-- ============================================================
-- AADHAAR ENROLLMENT DATA
-- ============================================================

CREATE TABLE IF NOT EXISTS aadhaar_enrollment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    district_lgd    INTEGER REFERENCES districts(lgd_code),
    state_raw       TEXT NOT NULL,
    district_raw    TEXT NOT NULL,
    pincode         TEXT,
    date            TEXT,
    age_0_5         INTEGER,
    age_5_17        INTEGER,
    age_18_plus     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_aadhaar_district ON aadhaar_enrollment(district_lgd);
CREATE INDEX IF NOT EXISTS idx_aadhaar_date ON aadhaar_enrollment(date);

-- ============================================================
-- IMPORT LOG
-- ============================================================

CREATE TABLE IF NOT EXISTS import_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    file_path   TEXT,
    imported_at TEXT DEFAULT (datetime('now')),
    rows_added  INTEGER,
    notes       TEXT
);
"""

def init_db():
    """Create the database and all tables."""
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.commit()

    # Verify
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    print(f"Database created at {DB_PATH}")
    print(f"Tables: {', '.join(tables)}")
    db.close()

if __name__ == '__main__':
    init_db()
