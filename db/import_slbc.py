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
from import_safety import ImportAudit, upsert_slbc_data
from numeric_values import parse_number

MONTHS = {'january': '01', 'february': '02', 'march': '03', 'april': '04',
          'may': '05', 'june': '06', 'july': '07', 'august': '08',
          'september': '09', 'october': '10', 'november': '11', 'december': '12',
          # Abbreviated forms (Haryana uses "Dec 2022", "Mar 2023", etc.)
          'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
          'jun': '06', 'jul': '07', 'aug': '08',
          'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'}

# States with SLBC timeseries data
SLBC_STATES = [
    'andhra-pradesh', 'arunachal-pradesh', 'assam', 'bihar',
    'chhattisgarh', 'gujarat', 'haryana', 'himachal-pradesh',
    'jharkhand', 'karnataka', 'kerala', 'madhya-pradesh',
    'maharashtra', 'manipur', 'meghalaya', 'mizoram', 'nagaland',
    'odisha', 'punjab', 'rajasthan', 'sikkim', 'tamil-nadu', 'telangana',
    'tripura', 'uttar-pradesh', 'uttarakhand', 'west-bengal',
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
    """Retain source text and parse only a whole finite number with no unit inference."""
    if val is None:
        return (None, None)
    return (str(val).strip(), parse_number(val))


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


def import_state_timeseries(
    db, matcher, slug, field_cache, period_cache, audit=None
):
    """Import one state's timeseries and account for every source record."""
    owns_audit = audit is None
    audit = audit or ImportAudit(slug)
    fpath = os.path.join(SLBC_DIR, slug, f'{slug}_fi_timeseries.json')
    if not os.path.exists(fpath):
        if owns_audit:
            audit.write()
        return 0

    with open(fpath) as f:
        data = json.load(f)

    state_lgd = matcher.state_lgd_from_slug(slug)
    if not state_lgd:
        print(f"  WARNING: No state LGD code for slug '{slug}'")
        audit.reject("unresolved_state", state_slug=slug)
        if owns_audit:
            audit.write()
        return 0

    rows = 0
    batch = []

    def load_record(period_label, district_name, record, excluded_keys):
        nonlocal rows, batch
        if not period_label:
            audit.reject(
                "missing_period", state_slug=slug, district_raw=district_name or None
            )
            return
        if not district_name:
            audit.reject(
                "missing_district", state_slug=slug, period_label=period_label
            )
            return

        period_id = get_period_id(db, period_label, period_cache)
        if not period_id:
            audit.reject(
                "unresolved_period",
                state_slug=slug,
                period_label=period_label,
                district_raw=district_name,
            )
            return
        district_lgd = matcher.resolve(
            district_name, state_lgd=state_lgd, source=slug
        )
        if not district_lgd:
            audit.reject(
                "unresolved_district",
                state_slug=slug,
                period_label=period_label,
                district_raw=district_name,
            )
            return

        record_rows = 0
        for key, val in record.items():
            if key in excluded_keys or '__' not in key:
                continue
            if val is None or str(val).strip() == '':
                continue
            field_id = get_or_create_field(db, key, field_cache)
            text, numeric = parse_numeric(val)
            batch.append(
                (state_lgd, district_lgd, period_id, field_id, text, numeric, slug)
            )
            rows += 1
            record_rows += 1
            if len(batch) >= 10000:
                upsert_slbc_data(db, batch)
                batch = []

        if record_rows:
            audit.accept()
        else:
            audit.reject(
                "no_importable_values",
                state_slug=slug,
                period_label=period_label,
                district_raw=district_name,
            )

    if 'periods' in data:
        # Format A: periods -> districts.
        for period_obj in data['periods']:
            for district_rec in period_obj.get('districts', []):
                load_record(
                    district_rec.get('period', period_obj.get('period', '')),
                    district_rec.get('district', ''),
                    district_rec,
                    {'district', 'period'},
                )
    else:
        # Format B: Haryana flat dict {DISTRICT_NAME: [{field: value, ...}]}.
        for district_name, records in data.items():
            if not isinstance(records, list):
                audit.reject(
                    "invalid_record_container",
                    state_slug=slug,
                    district_raw=district_name,
                )
                continue
            for record in records:
                load_record(
                    record.get('period', record.get('quarter', '')),
                    district_name,
                    record,
                    {'district', 'period', 'meeting', 'quarter', 'date'},
                )

    if batch:
        upsert_slbc_data(db, batch)
    if owns_audit:
        audit.write()
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
    audit = ImportAudit('slbc')
    t0 = time.time()

    for slug in SLBC_STATES:
        rows = import_state_timeseries(
            db, matcher, slug, field_cache, period_cache, audit=audit
        )
        db.commit()
        total_rows += rows
        print(f"  {slug}: {rows:,} data points")

    elapsed = time.time() - t0
    ledger_path, summary_path = audit.write()

    # Log import
    db.execute(
        "INSERT INTO import_log (source, rows_added, notes) VALUES (?, ?, ?)",
        ('slbc', total_rows, f"{len(SLBC_STATES)} states in {elapsed:.1f}s")
    )
    db.commit()

    print(f"\nTotal: {total_rows:,} SLBC data points in {elapsed:.1f}s")
    summary = audit.summary()
    print(
        f"Source records: {summary['records_observed']:,} observed; "
        f"{summary['records_accepted']:,} accepted; "
        f"{summary['records_rejected']:,} rejected"
    )
    print(f"Reject ledger: {ledger_path}")
    print(f"Audit summary: {summary_path}")
    print(f"Fields: {db.execute('SELECT COUNT(*) FROM slbc_fields').fetchone()[0]}")
    print(f"slbc_data rows: {db.execute('SELECT COUNT(*) FROM slbc_data').fetchone()[0]:,}")

    matcher.report_unmatched()
    matcher.close()
    db.close()


if __name__ == '__main__':
    import_all()
