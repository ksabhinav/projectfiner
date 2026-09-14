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
from import_safety import ImportAudit, upsert_slbc_data


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
    audit = ImportAudit("goa")

    state_lgd = matcher.state_lgd_from_slug('goa')
    if not state_lgd:
        row = db.execute("SELECT lgd_code FROM states WHERE slug='goa'").fetchone()
        if not row:
            print("ERROR: state 'goa' not in states table", file=sys.stderr)
            return 1
        state_lgd = row[0]
    print(f"Goa state_lgd_code={state_lgd}")

    rows = 0
    for period_obj in data.get('periods', []):
        period_label = period_obj.get('period', '')
        districts = period_obj.get('districts', [])
        if not period_label:
            for district in districts or [{}]:
                audit.reject(
                    "missing_period",
                    state_slug="goa",
                    district_raw=district.get("district") or None,
                )
            continue
        period_id = get_period_id(db, period_label, period_cache)
        if not period_id:
            for district in districts or [{}]:
                audit.reject(
                    "unresolved_period",
                    state_slug="goa",
                    period_label=period_label,
                    district_raw=district.get("district") or None,
                )
            continue
        for district in districts:
            district_name = district.get('district', '')
            district_lgd = matcher.resolve(
                district_name, state_lgd=state_lgd, source='goa'
            )
            if not district_lgd:
                audit.reject(
                    "unresolved_district",
                    state_slug="goa",
                    period_label=period_label,
                    district_raw=district_name or None,
                )
                continue
            record_rows = 0
            for key, val in district.items():
                if key in ('district', 'period') or '__' not in key:
                    continue
                if val is None or str(val).strip() == '':
                    continue
                field_id = get_or_create_field(db, key, field_cache)
                text, numeric = parse_numeric(val)
                upsert_slbc_data(db, [
                    (state_lgd, district_lgd, period_id, field_id, text, numeric, 'goa')
                ])
                rows += 1
                record_rows += 1
            if record_rows:
                audit.accept()
            else:
                audit.reject(
                    "no_importable_values",
                    state_slug="goa",
                    period_label=period_label,
                    district_raw=district_name,
                )

    db.commit()
    ledger_path, summary_path = audit.write()
    summary = audit.summary()
    print(f"Loaded {rows} rows for Goa")
    print(
        f"Source records: {summary['records_observed']} observed; "
        f"{summary['records_accepted']} accepted; "
        f"{summary['records_rejected']} rejected"
    )
    print(f"Reject ledger: {ledger_path}")
    print(f"Audit summary: {summary_path}")

    count = db.execute(
        "SELECT COUNT(*) FROM slbc_data WHERE state_lgd_code=?",
        (state_lgd,)
    ).fetchone()[0]
    print(f"Total Goa rows in slbc_data: {count}")
    matcher.close()
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
