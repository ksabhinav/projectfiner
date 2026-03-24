#!/usr/bin/env python3
"""Import SLBC timeseries data from all state JSON files into SQLite."""

import json
import os
import re
import sqlite3
import sys
import time

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT = os.path.dirname(os.path.dirname(__file__))
SLBC_DIR = os.path.join(PROJECT, 'public', 'slbc-data')

# Add db/ to path for match_districts
sys.path.insert(0, os.path.dirname(__file__))
from match_districts import DistrictMatcher

MONTHS = {'january': '01', 'february': '02', 'march': '03', 'april': '04',
          'may': '05', 'june': '06', 'july': '07', 'august': '08',
          'september': '09', 'october': '10', 'november': '11', 'december': '12'}

# States with SLBC timeseries data
SLBC_STATES = [
    'arunachal-pradesh', 'assam', 'bihar', 'chhattisgarh', 'gujarat',
    'haryana', 'jharkhand', 'karnataka', 'kerala', 'maharashtra',
    'manipur', 'meghalaya', 'mizoram', 'nagaland', 'odisha',
    'rajasthan', 'sikkim', 'tamil-nadu', 'telangana', 'tripura',
    'uttarakhand', 'west-bengal',
]


def normalize_period(label):
    """Convert 'June 2020' → '2020-06'."""
    parts = label.strip().split()
    if len(parts) == 2:
        month = MONTHS.get(parts[0].lower())
        year = parts[1]
        if month and year.isdigit():
            return f"{year}-{month}"
    return None


def parse_numeric(val):
    """Try to parse a string value as a float. Returns (text, numeric_or_None)."""
    if val is None:
        return (None, None)
    text = str(val).strip()
    if not text or text in ('0', '0.0', '0.00', '-', 'NA', 'N/A', 'nil', 'Nil', 'NIL'):
        if text in ('0', '0.0', '0.00'):
            return (text, 0.0)
        return (text, None)
    # Strip commas, percentage signs, currency symbols
    cleaned = text.replace(',', '').replace('%', '').replace('₹', '').strip()
    try:
        return (text, float(cleaned))
    except (ValueError, TypeError):
        return (text, None)


def get_or_create_field(db, field_key, field_cache):
    """Get field_id from cache or insert into slbc_fields."""
    if field_key in field_cache:
        return field_cache[field_key]

    parts = field_key.split('__', 1)
    if len(parts) == 2:
        category, field_name = parts
    else:
        category, field_name = 'uncategorized', parts[0]

    # Determine unit from field name
    unit = None
    if '_amt' in field_name or 'amount' in field_name or 'deposit' in field_name or 'advance' in field_name:
        if '_pct' not in field_name and 'ratio' not in field_name:
            unit = 'lakhs'
    elif '_pct' in field_name or 'ratio' in field_name or 'percentage' in field_name:
        unit = 'percent'
    elif '_no' in field_name or '_a_c' in field_name or '_number' in field_name or 'branch' in field_name:
        unit = 'count'

    db.execute(
        "INSERT OR IGNORE INTO slbc_fields (field_key, category, field_name, unit) VALUES (?, ?, ?, ?)",
        (field_key, category, field_name, unit)
    )
    row = db.execute("SELECT id FROM slbc_fields WHERE field_key=?", (field_key,)).fetchone()
    field_cache[field_key] = row[0]
    return row[0]


def get_period_id(db, label, period_cache):
    """Get period_id from cache or lookup."""
    if label in period_cache:
        return period_cache[label]
    row = db.execute("SELECT id FROM periods WHERE label=?", (label,)).fetchone()
    if row:
        period_cache[label] = row[0]
        return row[0]
    # Try creating it
    code = normalize_period(label)
    if code:
        db.execute(
            "INSERT OR IGNORE INTO periods (label, code) VALUES (?, ?)",
            (label, code)
        )
        db.commit()
        row = db.execute("SELECT id FROM periods WHERE label=?", (label,)).fetchone()
        if row:
            period_cache[label] = row[0]
            return row[0]
    return None


def import_state_timeseries(db, matcher, slug, field_cache, period_cache):
    """Import a single state's timeseries JSON."""
    fpath = os.path.join(SLBC_DIR, slug, f'{slug}_fi_timeseries.json')
    if not os.path.exists(fpath):
        return 0

    with open(fpath) as f:
        data = json.load(f)

    state_lgd = matcher.state_lgd_from_slug(slug)
    if not state_lgd:
        print(f"  WARNING: No state LGD code for slug '{slug}'")
        return 0

    rows = 0
    batch = []

    if 'periods' in data:
        # Format A: periods → districts (21 states)
        for period_obj in data['periods']:
            for district_rec in period_obj.get('districts', []):
                period_label = district_rec.get('period', period_obj.get('period', ''))
                district_name = district_rec.get('district', '')

                if not period_label or not district_name:
                    continue

                period_id = get_period_id(db, period_label, period_cache)
                district_lgd = matcher.resolve(district_name, state_lgd=state_lgd, source=slug)

                if not period_id or not district_lgd:
                    continue

                for key, val in district_rec.items():
                    if key in ('district', 'period') or '__' not in key:
                        continue
                    if val is None or str(val).strip() == '':
                        continue

                    field_id = get_or_create_field(db, key, field_cache)
                    text, numeric = parse_numeric(val)

                    batch.append((state_lgd, district_lgd, period_id, field_id, text, numeric, slug))
                    rows += 1

                    if len(batch) >= 10000:
                        db.executemany(
                            "INSERT OR REPLACE INTO slbc_data (state_lgd_code, district_lgd, period_id, field_id, value_text, value_numeric, source_file) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            batch
                        )
                        batch = []
    else:
        # Format B: Haryana — flat dict {DISTRICT_NAME: [{field: value, ...}]}
        for district_name, records in data.items():
            if not isinstance(records, list):
                continue
            for rec in records:
                period_label = rec.get('period', '')
                if not period_label:
                    continue

                period_id = get_period_id(db, period_label, period_cache)
                district_lgd = matcher.resolve(district_name, state_lgd=state_lgd, source=slug)

                if not period_id or not district_lgd:
                    continue

                for key, val in rec.items():
                    if key in ('district', 'period', 'meeting', 'quarter', 'date') or '__' not in key:
                        continue
                    if val is None or str(val).strip() == '':
                        continue

                    field_id = get_or_create_field(db, key, field_cache)
                    text, numeric = parse_numeric(val)

                    batch.append((state_lgd, district_lgd, period_id, field_id, text, numeric, slug))
                    rows += 1

                    if len(batch) >= 10000:
                        db.executemany(
                            "INSERT OR REPLACE INTO slbc_data (state_lgd_code, district_lgd, period_id, field_id, value_text, value_numeric, source_file) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            batch
                        )
                        batch = []

    # Flush remaining
    if batch:
        db.executemany(
            "INSERT OR REPLACE INTO slbc_data (state_lgd_code, district_lgd, period_id, field_id, value_text, value_numeric, source_file) VALUES (?, ?, ?, ?, ?, ?, ?)",
            batch
        )

    return rows


def import_all():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=NORMAL")

    matcher = DistrictMatcher(DB_PATH)
    field_cache = {}
    period_cache = {}

    total_rows = 0
    t0 = time.time()

    for slug in SLBC_STATES:
        rows = import_state_timeseries(db, matcher, slug, field_cache, period_cache)
        db.commit()
        total_rows += rows
        print(f"  {slug}: {rows:,} data points")

    elapsed = time.time() - t0

    # Log import
    db.execute(
        "INSERT INTO import_log (source, rows_added, notes) VALUES (?, ?, ?)",
        ('slbc', total_rows, f"{len(SLBC_STATES)} states in {elapsed:.1f}s")
    )
    db.commit()

    print(f"\nTotal: {total_rows:,} SLBC data points in {elapsed:.1f}s")
    print(f"Fields: {db.execute('SELECT COUNT(*) FROM slbc_fields').fetchone()[0]}")
    print(f"slbc_data rows: {db.execute('SELECT COUNT(*) FROM slbc_data').fetchone()[0]:,}")

    matcher.report_unmatched()
    matcher.close()
    db.close()


if __name__ == '__main__':
    import_all()
