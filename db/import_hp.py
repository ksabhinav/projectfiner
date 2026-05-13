#!/usr/bin/env python3
"""
Himachal Pradesh SLBC importer.

Clears any existing slbc_data rows for HP, then re-imports from
public/slbc-data/himachal-pradesh/himachal-pradesh_fi_timeseries.json
(extracted via slbc-data/himachal-pradesh/extract_hp.py).

Source: 179th SLBC HP Meeting Agenda — Dec 2025 quarter (slbchp.com).
Units: already in Rs. Lakhs (per source headers). NO ×100 conversion.

Pattern mirrors db/import_haryana_v2.py.
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
        "SELECT lgd_code FROM states WHERE name='Himachal Pradesh'"
    ).fetchone()[0]
    assert state_lgd == 2, f"Expected HP state_lgd=2, got {state_lgd}"

    # 1. Clear all HP rows.
    before = db.execute(
        "SELECT COUNT(*) FROM slbc_data WHERE state_lgd_code=?",
        (state_lgd,)
    ).fetchone()[0]
    db.execute("DELETE FROM slbc_data WHERE state_lgd_code=?", (state_lgd,))
    db.commit()
    print(f"Cleared {before:,} existing Himachal Pradesh rows.")

    # 2. Re-import from extractor output.
    matcher = DistrictMatcher(DB_PATH)
    t0 = time.time()
    rows = import_state_timeseries(db, matcher, 'himachal-pradesh', {}, {})
    db.commit()
    elapsed = time.time() - t0

    db.execute(
        "INSERT INTO import_log (source, rows_added, notes) VALUES (?, ?, ?)",
        ('slbc-himachal-pradesh',
         rows,
         f"179th SLBC HP - Dec 2025 (Rs. Lakhs, no conversion), "
         f"{elapsed:.1f}s"),
    )
    db.commit()
    after = db.execute(
        "SELECT COUNT(*) FROM slbc_data WHERE state_lgd_code=?",
        (state_lgd,)
    ).fetchone()[0]
    print(f"Imported {rows:,} rows in {elapsed:.1f}s. "
          f"Himachal Pradesh total: {after:,}.")
    matcher.report_unmatched()
    matcher.close()
    db.close()


if __name__ == '__main__':
    main()
