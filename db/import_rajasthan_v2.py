#!/usr/bin/env python3
"""Re-import Rajasthan SLBC data into SQLite.

Clears all existing rows for state_lgd_code=8 (Rajasthan) and re-inserts
from public/slbc-data/rajasthan/rajasthan_fi_timeseries.json using the
shared import_slbc machinery. This guarantees stale fields from prior
extractor runs are dropped (plain INSERT OR REPLACE on key columns
would leave orphaned (district, period, field) tuples behind).

Rajasthan-specific cleanup: the 8 districts created in the 2023 reorg
(Balotra, Beawar, Deeg, Didwana-Kuchaman, Khairthal-Tijara,
Kotputli-Behror, Phalodi, Salumbar) were dissolved in 2024-25 by the
Bhupendra Bhati commission and are NOT in our 33-district canonical
DB schema. SLBC continues to report them through Dec 2025 (the source
hasn't caught up to the rollback). We strip those rows from the
timeseries BEFORE handing it to the importer, because:
  (a) Adding aliases new -> parent silently overwrites parent values
      via INSERT OR REPLACE (e.g. Balotra would clobber Barmer).
  (b) The shared matcher's cross-state fuzzy fallback otherwise picks
      up similarly-named AP districts (e.g. Kotputli-Behror -> Palnadu,
      Didwana-Kuchaman -> Sri Sathya Sai) — silent cross-state pollution.

Usage:  python3 db/import_rajasthan_v2.py
"""

import json
import os
import shutil
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from import_slbc import import_state_timeseries  # noqa: E402
from match_districts import DistrictMatcher  # noqa: E402

DB_PATH = os.path.join(HERE, "finer.db")
STATE_LGD = 8  # Rajasthan
SLUG = "rajasthan"

# 2023-reorg districts (dissolved 2024-25 by Bhati commission, not in our DB)
DROPPED_NEW_DISTRICTS = {
    "Balotra", "Beawar", "Deeg", "Didwana-Kuchaman",
    "Khairthal-Tijara", "Kotputli-Behror", "Phalodi", "Salumbar",
}

PROJECT_ROOT = os.path.dirname(HERE)
TIMESERIES_PATH = os.path.join(
    PROJECT_ROOT, "public", "slbc-data", "rajasthan",
    "rajasthan_fi_timeseries.json"
)


def strip_new_districts(path):
    """Remove DROPPED_NEW_DISTRICTS rows from the timeseries JSON in place,
    leaving a .bak copy alongside the original."""
    if not os.path.exists(path):
        return 0
    with open(path) as f:
        data = json.load(f)
    removed = 0
    for period in data.get("periods", []):
        before = len(period.get("districts", []))
        period["districts"] = [
            d for d in period.get("districts", [])
            if d.get("district") not in DROPPED_NEW_DISTRICTS
        ]
        removed += before - len(period["districts"])
    if removed:
        shutil.copy(path, path + ".bak")
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    return removed


def main():
    print(f"Stripping post-2023 reorg districts from {os.path.basename(TIMESERIES_PATH)}...")
    stripped = strip_new_districts(TIMESERIES_PATH)
    print(f"  Removed {stripped} district-period rows for new-reorg districts.")

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=NORMAL")

    before = db.execute(
        "SELECT COUNT(*) FROM slbc_data WHERE state_lgd_code=?", (STATE_LGD,)
    ).fetchone()[0]
    print(f"Before: {before:,} rows for state_lgd_code={STATE_LGD}")

    print("Clearing existing Rajasthan rows...")
    db.execute("DELETE FROM slbc_data WHERE state_lgd_code=?", (STATE_LGD,))
    db.commit()

    matcher = DistrictMatcher(DB_PATH)
    field_cache = {}
    period_cache = {}

    t0 = time.time()
    rows = import_state_timeseries(db, matcher, SLUG, field_cache, period_cache)
    db.commit()
    elapsed = time.time() - t0

    after = db.execute(
        "SELECT COUNT(*) FROM slbc_data WHERE state_lgd_code=?", (STATE_LGD,)
    ).fetchone()[0]

    db.execute(
        "INSERT INTO import_log (source, rows_added, notes) VALUES (?, ?, ?)",
        ("slbc-rajasthan-v2", after, f"reimport in {elapsed:.1f}s, before={before}"),
    )
    db.commit()

    print(f"After:  {after:,} rows for state_lgd_code={STATE_LGD}")
    print(f"Imported {rows:,} data points in {elapsed:.1f}s")

    # Coverage summary
    print("\nCoverage by period:")
    for row in db.execute(
        """SELECT p.code, COUNT(DISTINCT s.district_lgd), COUNT(DISTINCT s.field_id), COUNT(*)
           FROM slbc_data s JOIN periods p ON p.id=s.period_id
           WHERE s.state_lgd_code=? GROUP BY p.code ORDER BY p.code""",
        (STATE_LGD,),
    ):
        print(f"  {row[0]}: {row[1]} districts, {row[2]} fields, {row[3]:,} rows")

    matcher.report_unmatched()
    matcher.close()
    db.close()


if __name__ == "__main__":
    main()
