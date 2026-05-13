#!/usr/bin/env python3
"""
Import Goa SLBC timeseries data into SQLite.

Goa publishes only `branch_network__total_branch` per district (North/South Goa)
quarterly — see slbc-data/goa/meetings_audit.txt for the granularity finding.
"""

import json
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT = os.path.dirname(os.path.dirname(__file__))
TS_PATH = os.path.join(PROJECT, 'public', 'slbc-data', 'goa', 'goa_fi_timeseries.json')

sys.path.insert(0, os.path.dirname(__file__))
from import_slbc import (
    get_or_create_field, get_period_id, parse_numeric, normalize_period,
)
from match_districts import DistrictMatcher


def main() -> int:
    if not os.path.exists(TS_PATH):
        print(f"ERROR: {TS_PATH} not found. Run extract_goa.py first.", file=sys.stderr)
        return 1

    with open(TS_PATH) as fh:
        data = json.load(fh)

    db = sqlite3.connect(DB_PATH)
    matcher = DistrictMatcher(DB_PATH)
    field_cache: dict = {}
    period_cache: dict = {}

    # State lgd
    state_lgd = matcher.state_lgd_from_slug('goa')
    if not state_lgd:
        # Fallback by name lookup
        row = db.execute("SELECT lgd_code FROM states WHERE slug='goa'").fetchone()
        if not row:
            print("ERROR: state 'goa' not in states table", file=sys.stderr)
            return 1
        state_lgd = row[0]
    print(f"Goa state_lgd_code={state_lgd}")

    # Clear any prior Goa rows (idempotent re-import)
    db.execute("DELETE FROM slbc_data WHERE state_lgd_code=? AND source_file='goa'", (state_lgd,))
    db.commit()

    rows = 0
    for period_obj in data.get('periods', []):
        period_label = period_obj.get('period', '')
        if not period_label:
            continue
        period_id = get_period_id(db, period_label, period_cache)
        if not period_id:
            print(f"  [warn] could not resolve period '{period_label}'", file=sys.stderr)
            continue
        for d in period_obj.get('districts', []):
            district_name = d.get('district', '')
            district_lgd = matcher.resolve(district_name, state_lgd=state_lgd, source='goa')
            if not district_lgd:
                print(f"  [warn] unresolved district '{district_name}'", file=sys.stderr)
                continue
            for key, val in d.items():
                if key in ('district', 'period') or '__' not in key:
                    continue
                if val is None or str(val).strip() == '':
                    continue
                field_id = get_or_create_field(db, key, field_cache)
                text, numeric = parse_numeric(val)
                db.execute(
                    "INSERT OR REPLACE INTO slbc_data "
                    "(state_lgd_code, district_lgd, period_id, field_id, value_text, value_numeric, source_file) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (state_lgd, district_lgd, period_id, field_id, text, numeric, 'goa'),
                )
                rows += 1
    db.commit()
    print(f"Inserted {rows} rows for Goa")

    # Sanity
    count = db.execute(
        "SELECT COUNT(*) FROM slbc_data WHERE state_lgd_code=?",
        (state_lgd,)
    ).fetchone()[0]
    print(f"Total Goa rows in slbc_data: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
