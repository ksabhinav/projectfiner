#!/usr/bin/env python3
"""Import Bihar 95th SLBC Agenda Reference Book data (Sep 2025 quarter).

Reads slbc-data/bihar/bihar_95th_reference_2025-09.json and inserts new
(district, field) combinations into slbc_data using INSERT OR IGNORE so any
overlap with already-imported Bihar Sep 2025 rows is skipped.
"""

import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "finer.db")
SRC_JSON = os.path.join(ROOT, "slbc-data", "bihar", "bihar_95th_reference_2025-09.json")

BIHAR_STATE_LGD = 10  # confirmed via SELECT FROM states WHERE name='Bihar'
PERIOD_CODE = "2025-09"
SOURCE_FILE = "bihar_95th_reference"


def parse_value(v):
    """Return (value_text, value_numeric)."""
    if v is None or v == "":
        return None, None
    s = str(v).strip().replace(",", "")
    if s in ("-", "NA", "N/A", "NIL", "--", "*", "."):
        return s, None
    try:
        return s, float(s)
    except ValueError:
        return s, None


def main():
    if not os.path.exists(SRC_JSON):
        print(f"ERROR: source JSON not found at {SRC_JSON}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(DB_PATH):
        print(f"ERROR: db not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    data = json.load(open(SRC_JSON))
    tables = data["tables"]
    print(f"Loaded {len(tables)} tables from {os.path.basename(SRC_JSON)}")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Get period_id
    cur.execute("SELECT id FROM periods WHERE code = ?", (PERIOD_CODE,))
    row = cur.fetchone()
    if not row:
        print(f"ERROR: period {PERIOD_CODE} not found in DB", file=sys.stderr)
        sys.exit(1)
    period_id = row[0]
    print(f"period_id for {PERIOD_CODE} = {period_id}")

    # Get district name → lgd_code (Bihar only). Match canonical names from JSON.
    cur.execute(
        "SELECT lgd_code, name FROM districts WHERE state_lgd_code = ?",
        (BIHAR_STATE_LGD,),
    )
    dist_by_name = {}
    for lgd, name in cur.fetchall():
        dist_by_name[name.lower()] = lgd
    # Aliases for canonical title-case used in JSON
    alias_map = {
        "kaimur (bhabua)": "kaimur (bhabua)",
    }

    def resolve_district(d):
        key = d.strip().lower()
        if key in dist_by_name:
            return dist_by_name[key]
        if key in alias_map and alias_map[key] in dist_by_name:
            return dist_by_name[alias_map[key]]
        return None

    # Stats trackers
    new_field_count = 0
    inserted_rows = 0
    skipped_existing = 0
    skipped_no_value = 0
    unresolved_districts = set()

    # Pre-count: existing (district, field) combos for Bihar 2025-09 so we can
    # report "new vs existing" later.
    cur.execute(
        """
        SELECT COUNT(*) FROM slbc_data
        WHERE state_lgd_code = ? AND period_id = ?
        """,
        (BIHAR_STATE_LGD, period_id),
    )
    pre_count = cur.fetchone()[0]
    print(f"Existing rows for Bihar {PERIOD_CODE} before import: {pre_count}")

    for cat_key, tbl in tables.items():
        category = tbl.get("category") or cat_key
        # Use the subcategory as part of the field_key when it differs from category
        # so we don't collide with existing fields. Existing Bihar fields use
        # `{category}__{field}` only. We append subcategory if it differs.
        subcat = tbl.get("subcategory") or cat_key
        # If subcategory equals the category, use category; else append subcategory
        # as a prefix to the field name to avoid collisions.
        field_prefix_extra = ""
        if subcat and subcat != category:
            field_prefix_extra = f"{subcat}_"

        fields = tbl.get("fields") or []
        districts = tbl.get("districts") or {}
        # Skip empty/auto-only tables that have only col_N placeholders
        # — actually, we still want to import them since they contain real
        # numbers under generic field names.
        for raw_district, row_dict in districts.items():
            dlgd = resolve_district(raw_district)
            if dlgd is None:
                unresolved_districts.add(raw_district)
                continue
            for f in fields:
                if f not in row_dict:
                    continue
                raw_val = row_dict[f]
                vt, vn = parse_value(raw_val)
                if vt is None:
                    skipped_no_value += 1
                    continue
                # Build canonical field_key
                field_name = (field_prefix_extra + f) if field_prefix_extra else f
                # Sanitize: snake_case, no double underscores, no leading/trailing _
                field_name = re.sub(r"_+", "_", field_name).strip("_")
                if not field_name:
                    continue
                field_key = f"{category}__{field_name}"

                # Ensure slbc_fields row exists
                cur.execute("SELECT id FROM slbc_fields WHERE field_key = ?", (field_key,))
                r = cur.fetchone()
                if r:
                    field_id = r[0]
                else:
                    cur.execute(
                        """
                        INSERT INTO slbc_fields
                          (field_key, category, field_name, display_name, unit)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (field_key, category, field_name, field_name, None),
                    )
                    field_id = cur.lastrowid
                    new_field_count += 1

                # INSERT OR IGNORE the data row
                cur.execute(
                    """
                    INSERT OR IGNORE INTO slbc_data
                      (state_lgd_code, district_lgd, period_id, field_id,
                       value_text, value_numeric, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (BIHAR_STATE_LGD, dlgd, period_id, field_id, vt, vn, SOURCE_FILE),
                )
                if cur.rowcount == 1:
                    inserted_rows += 1
                else:
                    skipped_existing += 1

    con.commit()

    # Post-count
    cur.execute(
        """
        SELECT COUNT(*) FROM slbc_data
        WHERE state_lgd_code = ? AND period_id = ?
        """,
        (BIHAR_STATE_LGD, period_id),
    )
    post_count = cur.fetchone()[0]

    # Distinct field count after
    cur.execute(
        """
        SELECT COUNT(DISTINCT field_id) FROM slbc_data
        WHERE state_lgd_code = ? AND period_id = ?
        """,
        (BIHAR_STATE_LGD, period_id),
    )
    distinct_fields_after = cur.fetchone()[0]

    con.close()

    print()
    print("=" * 60)
    print(f"  Inserted new rows           : {inserted_rows}")
    print(f"  Skipped (already existed)   : {skipped_existing}")
    print(f"  Skipped (no value / blank)  : {skipped_no_value}")
    print(f"  New field definitions added : {new_field_count}")
    print(f"  Unresolved districts        : {len(unresolved_districts)}")
    if unresolved_districts:
        print("    " + ", ".join(sorted(unresolved_districts)))
    print()
    print(f"  Bihar {PERIOD_CODE} rows before  : {pre_count}")
    print(f"  Bihar {PERIOD_CODE} rows after   : {post_count}")
    print(f"  Bihar {PERIOD_CODE} distinct fields after : {distinct_fields_after}")


if __name__ == "__main__":
    main()
