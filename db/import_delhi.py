#!/usr/bin/env python3
"""Import Delhi SLBC timeseries into SQLite (slbc_data table).

Uses the same INSERT OR REPLACE pattern as the unified SLBC importer.
Source file: public/slbc-data/delhi/delhi_fi_timeseries.json

State LGD code: 7 (NCT of Delhi).
13 quarters (Dec 2022 → Dec 2025) × 11 districts × 4 fields:
  credit_deposit_ratio__total_deposit  (₹ Lakhs)
  credit_deposit_ratio__total_advance  (₹ Lakhs)
  credit_deposit_ratio__cd_ratio       (%)
  branch_network__total_branch         (count)
"""

import json
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT = os.path.dirname(os.path.dirname(__file__))
SRC_JSON = os.path.join(PROJECT, 'public', 'slbc-data', 'delhi', 'delhi_fi_timeseries.json')

sys.path.insert(0, os.path.dirname(__file__))
from match_districts import DistrictMatcher

# Re-use parse_numeric + get_or_create_field + get_period_id from import_slbc.
from import_slbc import (
    parse_numeric,
    get_or_create_field,
    get_period_id,
    normalize_period,
)


def import_delhi(verbose: bool = True) -> int:
    if not os.path.exists(SRC_JSON):
        print(f"ERROR: {SRC_JSON} not found.  Run "
              f"slbc-data/delhi/extract_delhi.py first.")
        return 0

    with open(SRC_JSON) as f:
        data = json.load(f)

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=NORMAL")

    matcher = DistrictMatcher(DB_PATH)
    field_cache: dict[str, int] = {}
    period_cache: dict[str, int] = {}

    state_lgd = 7  # NCT of Delhi
    slug = "delhi"
    rows = 0
    batch = []

    # Wipe any pre-existing delhi rows so re-runs are idempotent.
    db.execute("DELETE FROM slbc_data WHERE source_file=?", (slug,))

    for period_obj in data.get("periods", []):
        for district_rec in period_obj.get("districts", []):
            period_label = district_rec.get("period", period_obj.get("period", ""))
            district_name = district_rec.get("district", "")
            if not period_label or not district_name:
                continue

            period_id = get_period_id(db, period_label, period_cache)
            district_lgd = matcher.resolve(district_name, state_lgd=state_lgd, source=slug)
            if not period_id or not district_lgd:
                if verbose:
                    print(f"  [skip] period={period_label} district={district_name} "
                          f"(period_id={period_id}, district_lgd={district_lgd})")
                continue

            for key, val in district_rec.items():
                if key in ("district", "period") or "__" not in key:
                    continue
                if val is None or str(val).strip() == "":
                    continue

                field_id = get_or_create_field(db, key, field_cache)
                text, numeric = parse_numeric(val)
                batch.append((state_lgd, district_lgd, period_id, field_id,
                              text, numeric, slug))
                rows += 1

                if len(batch) >= 5000:
                    db.executemany(
                        "INSERT OR REPLACE INTO slbc_data "
                        "(state_lgd_code, district_lgd, period_id, field_id, "
                        "value_text, value_numeric, source_file) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        batch,
                    )
                    batch = []

    if batch:
        db.executemany(
            "INSERT OR REPLACE INTO slbc_data "
            "(state_lgd_code, district_lgd, period_id, field_id, "
            "value_text, value_numeric, source_file) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
    db.commit()

    if verbose:
        cur = db.execute(
            "SELECT COUNT(*) FROM slbc_data WHERE source_file=?", (slug,)
        )
        total = cur.fetchone()[0]
        print(f"Delhi import complete: {rows} new rows, total in DB: {total}")

    db.close()
    return rows


if __name__ == "__main__":
    import_delhi()
