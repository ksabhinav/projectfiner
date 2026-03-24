#!/usr/bin/env python3
"""Import PhonePe Pulse district-level UPI data into SQLite."""

import json
import os
import sqlite3
import sys
import time

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT = os.path.dirname(os.path.dirname(__file__))
PP_FILE = os.path.join(PROJECT, 'public', 'digital-payments', 'phonepe_district_timeseries.json')

sys.path.insert(0, os.path.dirname(__file__))
from match_districts import DistrictMatcher


def import_phonepe():
    with open(PP_FILE) as f:
        data = json.load(f)

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    matcher = DistrictMatcher(DB_PATH)

    # Build period label → id cache
    period_cache = {}
    for pid, label in db.execute("SELECT id, label FROM periods"):
        period_cache[label] = pid

    total = 0
    batch = []

    for period_obj in data.get('periods', []):
        period_label = period_obj.get('period', '')
        period_id = period_cache.get(period_label)
        if not period_id:
            continue

        for rec in period_obj.get('districts', []):
            district_name = rec.get('district', '')
            state_slug = rec.get('phonepe_upi__state', '')
            count = rec.get('phonepe_upi__transaction_count', 0)
            amount = rec.get('phonepe_upi__transaction_amount', 0)

            district_lgd = matcher.resolve(
                district_name, state_slug=state_slug, source='phonepe'
            )

            batch.append((district_lgd, district_name, state_slug, period_id, count, amount))
            total += 1

            if len(batch) >= 5000:
                db.executemany(
                    "INSERT INTO phonepe_data (district_lgd, district_name_raw, state_slug, period_id, transaction_count, transaction_amount) VALUES (?, ?, ?, ?, ?, ?)",
                    batch
                )
                batch = []

    if batch:
        db.executemany(
            "INSERT INTO phonepe_data (district_lgd, district_name_raw, state_slug, period_id, transaction_count, transaction_amount) VALUES (?, ?, ?, ?, ?, ?)",
            batch
        )

    db.execute(
        "INSERT INTO import_log (source, file_path, rows_added) VALUES (?, ?, ?)",
        ('phonepe', PP_FILE, total)
    )
    db.commit()

    matched = db.execute("SELECT COUNT(*) FROM phonepe_data WHERE district_lgd IS NOT NULL").fetchone()[0]
    print(f"PhonePe: {total:,} records ({matched:,} matched to LGD codes)")
    matcher.report_unmatched()
    matcher.close()
    db.close()


if __name__ == '__main__':
    import_phonepe()
