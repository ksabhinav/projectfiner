#!/usr/bin/env python3
"""
Haryana SLBC v2 importer.

Clears every existing slbc_data row for Haryana, then re-imports from
public/slbc-data/haryana/haryana_fi_timeseries.json (which now contains the
extended 131st-175th coverage with Crore->Lakh conversion applied).

This wraps the import_slbc.py logic so the canonical pipeline keeps using
import_slbc.py for everything; this script is a targeted re-import for HR.
"""

import os
import sqlite3
import sys
import time

HERE = os.path.dirname(__file__)
DB_PATH = os.path.join(HERE, 'finer.db')

sys.path.insert(0, HERE)
from import_slbc import import_state_timeseries  # noqa: E402
from match_districts import DistrictMatcher  # noqa: E402


def main():
    db = sqlite3.connect(DB_PATH)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA synchronous=NORMAL')

    state_lgd = db.execute(
        "SELECT lgd_code FROM states WHERE name='Haryana'"
    ).fetchone()[0]

    # 1. Clear all Haryana rows.
    before = db.execute(
        "SELECT COUNT(*) FROM slbc_data WHERE state_lgd_code=?",
        (state_lgd,)
    ).fetchone()[0]
    db.execute("DELETE FROM slbc_data WHERE state_lgd_code=?", (state_lgd,))
    db.commit()
    print(f"Cleared {before:,} existing Haryana rows.")

    # 2. Re-import from the v2 JSON.
    matcher = DistrictMatcher(DB_PATH)
    t0 = time.time()
    rows = import_state_timeseries(db, matcher, 'haryana', {}, {})
    db.commit()
    elapsed = time.time() - t0

    db.execute(
        "INSERT INTO import_log (source, rows_added, notes) VALUES (?, ?, ?)",
        ('slbc-haryana-v2', rows,
         f"131st-175th, Crore->Lakh conversion applied, {elapsed:.1f}s"),
    )
    db.commit()
    after = db.execute(
        "SELECT COUNT(*) FROM slbc_data WHERE state_lgd_code=?",
        (state_lgd,)
    ).fetchone()[0]
    print(f"Imported {rows:,} rows in {elapsed:.1f}s. "
          f"Haryana total: {after:,}.")
    matcher.report_unmatched()
    matcher.close()
    db.close()


if __name__ == '__main__':
    main()
