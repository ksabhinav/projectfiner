#!/usr/bin/env python3
"""
fix_round2.py — Comprehensive data quality fixes for SLBC NE quarterly CSVs.

Fixes applied (in order):
  1. OCR-garbled merged-word column names
  2. Dash "-" used as null/zero
  3. Bare "%" column name
  4. Serial number columns removal
  5. Empty columns removal
  6. Duplicate "District" column
  7. Broken files with only "District" column (delete)
  8. Files where District column is all numbers (delete)
  9. Inconsistent percentage naming (Achv%, NPA %)
 10. Truncated/garbled short column names (AH, Fish, etc.)

After CSV fixes, regenerates:
  - {state_slug}_complete.json
  - {state_slug}_fi_timeseries.csv  and  {state_slug}_fi_timeseries.json

Idempotent: safe to run multiple times.
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent

STATES = [
    "assam",
    "meghalaya",
    "manipur",
    "arunachal-pradesh",
    "mizoram",
    "tripura",
    "nagaland",
    "sikkim",
]

STATE_DISPLAY = {
    "assam": "Assam",
    "meghalaya": "Meghalaya",
    "manipur": "Manipur",
    "arunachal-pradesh": "Arunachal Pradesh",
    "mizoram": "Mizoram",
    "tripura": "Tripura",
    "nagaland": "Nagaland",
    "sikkim": "Sikkim",
}

# --------------------------------------------------------------------------- #
#  Issue 1 helpers — OCR garbled column name fixes
# --------------------------------------------------------------------------- #

# Exact garbled → fixed mappings (applied first, case-sensitive)
GARBLED_MAP = {
    "Amountdisbursed": "Amount Disbursed",
    "ofrupaycard": "Of Rupay Card",
    "ofrupay": "Of Rupay",
    "Cardactivated": "Card Activated",
    "Cardacti-vated": "Card Activated",
    "Totalno": "Total No",
    "Totalno.": "Total No.",
    "duringquarter": "During Quarter",
    "Depositsheldinthe": "Deposits Held In The",
    "Firsttimeactive": "First Time Active",
    "Allottedto": "Allotted To",
    "Bankforopeningof": "Bank For Opening Of",
    "Branchdulyapprovedinthe": "Branch Duly Approved In The",
    "Christia Ns": "Christians",
    "Buddhis Ts": "Buddhists",
    "Zorastri Ans": "Zorastrians",
    "Zorast Rians": "Zorastrians",
    "Aadhaar Authenti-cated": "Aadhaar Authenticated",
    "Authenti-cated": "Authenticated",
    "Fish-ery": "Fishery",
    "S.Noofcamp": "S.No Of Camp",
    "Ru Paycard": "Rupay Card",
    "Ru Pay card": "Rupay Card",
    "Ru Pay Card": "Rupay Card",
    "Semi-uurrbbaannoorrrruurraall))": "Semi-Urban Or Rural)",
    "eaccounts": "Accounts",
}

# Serial number column names (case-insensitive match)
SERIAL_COL_PATTERNS = {
    "s", "sl", "sl.", "sr", "sr.", "s.no", "s.no.", "srl", "srl.", "s l",
    "s. no", "s. no.", "sl.no", "sl.no.",
}


def fix_garbled_column(col: str) -> str:
    """Fix a single column name through multiple strategies."""
    original = col

    # Strategy 1: exact substring replacements from known garbled map
    for garbled, fixed in GARBLED_MAP.items():
        if garbled in col:
            col = col.replace(garbled, fixed)

    # Strategy 2: fix mid-word hyphens (e.g., "Cardacti-vated" → "Cardactivated")
    # But preserve legitimate hyphens (e.g., "Semi-Urban", "non-PS")
    col = re.sub(r'(\w)-\s*(\w)', lambda m: m.group(1) + m.group(2)
                 if m.group(1)[-1].islower() and m.group(2)[0].islower()
                 else m.group(0), col)

    # Strategy 3: camelCase splitting — insert space between lowercase→uppercase
    # e.g. "Amountdisbursed" → "Amount disbursed"
    col = re.sub(r'([a-z])([A-Z])', r'\1 \2', col)

    # Strategy 4: fix mid-word spaces in known words
    # e.g. "Christia Ns" → "Christians"  (already handled by GARBLED_MAP)

    # Normalize multiple spaces
    col = re.sub(r'\s{2,}', ' ', col).strip()

    return col


def fix_percentage_column(col: str) -> str:
    """Issue 9: standardize percentage naming."""
    # Achv% → Achievement Pct
    col = re.sub(r'\bAchv\s*%', 'Achievement Pct', col)
    # NPA % or NPA% → NPA Pct
    col = re.sub(r'\bNPA\s*%', 'NPA Pct', col)
    # Trailing % that's part of a longer name (e.g., "% of householdscovered")
    # leave alone as they are descriptive
    return col


def fix_truncated_names(col: str, all_cols: list) -> str:
    """Issue 10: fix known truncations based on context."""
    stripped = col.strip()

    # AH in KCC context → Animal Husbandry
    # Only if it's exactly "AH" as a standalone column and file has KCC-related cols
    if stripped == "AH":
        kcc_context = any("KCC" in c or "kcc" in c.lower() for c in all_cols)
        if kcc_context:
            return "Animal Husbandry"

    # Fish / Fishe / Fis → Fishery  (standalone)
    if stripped in ("Fish", "Fishe", "Fis"):
        return "Fishery"

    return col


def is_serial_column(col_name: str, values: list) -> bool:
    """Check if a column is a serial number column."""
    name_lower = col_name.strip().lower()
    if name_lower not in SERIAL_COL_PATTERNS:
        return False

    # Verify values are sequential integers (or mostly so)
    nums = []
    for v in values:
        v = v.strip()
        if not v:
            continue
        try:
            nums.append(int(float(v)))
        except (ValueError, TypeError):
            return False

    if not nums:
        return True  # empty serial col, still remove

    # Check if roughly sequential (allowing gaps from missing rows)
    return nums == sorted(nums) and len(set(nums)) == len(nums)


def is_empty_column(values: list) -> bool:
    """Check if all values are empty/whitespace."""
    return all(not v or not v.strip() for v in values)


def district_all_numeric(values: list) -> bool:
    """Check if every non-empty value in District parses as a number."""
    non_empty = [v.strip() for v in values if v and v.strip()]
    if not non_empty:
        return False
    for v in non_empty:
        try:
            float(v)
        except ValueError:
            return False
    return True


# --------------------------------------------------------------------------- #
#  Quarter / date helpers
# --------------------------------------------------------------------------- #

MONTH_NAMES = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}

QUARTER_END_DAYS = {
    "03": "31", "06": "30", "09": "30", "12": "31",
    "01": "31", "02": "28", "04": "30", "05": "31",
    "07": "31", "08": "31", "10": "31", "11": "30",
}


def quarter_to_period(q: str) -> str:
    """'2024-03' → 'March 2024'"""
    parts = q.split("-")
    if len(parts) == 2:
        return f"{MONTH_NAMES.get(parts[1], parts[1])} {parts[0]}"
    return q


def quarter_to_as_on(q: str) -> str:
    """'2024-03' → '31-03-2024'"""
    parts = q.split("-")
    if len(parts) == 2:
        day = QUARTER_END_DAYS.get(parts[1], "30")
        return f"{day}-{parts[1]}-{parts[0]}"
    return q


def quarter_to_fy(q: str) -> str:
    """'2024-03' → '2023-24', '2024-06' → '2024-25'"""
    parts = q.split("-")
    if len(parts) != 2:
        return q
    year, month = int(parts[0]), int(parts[1])
    if month <= 3:
        start = year - 1
    else:
        start = year
    end = start + 1
    return f"{start}-{str(end)[-2:]}"


def slugify_field(field: str) -> str:
    """Convert a field name to a snake_case slug for timeseries columns."""
    s = field.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = s.strip('_')
    return s


# --------------------------------------------------------------------------- #
#  Main fix logic
# --------------------------------------------------------------------------- #

def process_csv(filepath: Path, stats: dict) -> str | None:
    """
    Process a single CSV file. Returns:
      - "fixed" if file was modified
      - "deleted" if file was removed
      - None if no changes
    """
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        print(f"  WARNING: Cannot read {filepath}: {e}")
        return None

    if not content.strip():
        return None

    try:
        reader = csv.reader(content.splitlines())
        rows = list(reader)
    except Exception as e:
        print(f"  WARNING: Cannot parse {filepath}: {e}")
        return None

    if not rows:
        return None

    header = rows[0]
    data_rows = rows[1:]

    # ----- Issue 7: single-column "District" only files → delete -----
    if len(header) == 1 and header[0].strip().lower() == "district":
        os.remove(filepath)
        stats["issue7_broken_single_col"] += 1
        return "deleted"

    # ----- Issue 8: District column all-numeric → delete -----
    if "District" in header:
        idx = header.index("District")
        dist_vals = [r[idx] for r in data_rows if len(r) > idx]
        if dist_vals and district_all_numeric(dist_vals):
            os.remove(filepath)
            stats["issue8_numeric_district"] += 1
            return "deleted"

    changed = False

    # ----- Issue 1: fix garbled column names -----
    new_header = []
    for col in header:
        fixed = fix_garbled_column(col)
        if fixed != col:
            stats["issue1_garbled_cols"] += 1
            changed = True
        new_header.append(fixed)
    header = new_header

    # ----- Issue 9: percentage naming -----
    new_header = []
    for col in header:
        fixed = fix_percentage_column(col)
        if fixed != col:
            stats["issue9_pct_naming"] += 1
            changed = True
        new_header.append(fixed)
    header = new_header

    # ----- Issue 10: truncated names -----
    new_header = []
    for col in header:
        fixed = fix_truncated_names(col, header)
        if fixed != col:
            stats["issue10_truncated"] += 1
            changed = True
        new_header.append(fixed)
    header = new_header

    # ----- Issue 3: bare "%" column -----
    new_header = []
    for i, col in enumerate(header):
        if col.strip() == "%":
            # Try to infer from previous column
            new_name = "Pct"
            if i > 0:
                prev = header[i - 1].lower()
                if any(kw in prev for kw in ["amount", "amt", "target", "achv", "achievement"]):
                    new_name = "Pct"
                else:
                    new_name = "Percentage"
            stats["issue3_bare_pct"] += 1
            changed = True
            new_header.append(new_name)
        else:
            new_header.append(col)
    header = new_header

    # Build column data for column-level checks
    num_cols = len(header)
    col_values = [[] for _ in range(num_cols)]
    for row in data_rows:
        for j in range(num_cols):
            if j < len(row):
                col_values[j].append(row[j])
            else:
                col_values[j].append("")

    # ----- Issue 4: serial number columns -----
    cols_to_remove = set()
    for j, col_name in enumerate(header):
        if is_serial_column(col_name, col_values[j] if j < len(col_values) else []):
            cols_to_remove.add(j)
            stats["issue4_serial_cols"] += 1
            changed = True

    # ----- Issue 5: empty columns -----
    for j, col_name in enumerate(header):
        if j not in cols_to_remove and is_empty_column(col_values[j] if j < len(col_values) else []):
            cols_to_remove.add(j)
            stats["issue5_empty_cols"] += 1
            changed = True

    # ----- Issue 6: duplicate District columns -----
    seen_district = False
    for j, col_name in enumerate(header):
        if col_name.strip().lower() == "district":
            if seen_district:
                cols_to_remove.add(j)
                stats["issue6_dup_district"] += 1
                changed = True
            else:
                seen_district = True

    # ----- Issue 2: dash as null -----
    new_data_rows = []
    for row in data_rows:
        new_row = list(row)
        for j in range(len(new_row)):
            val = new_row[j].strip()
            if val == "-":
                new_row[j] = ""
                stats["issue2_dash_null"] += 1
                changed = True
        new_data_rows.append(new_row)
    data_rows = new_data_rows

    if not changed:
        return None

    # Remove marked columns
    if cols_to_remove:
        keep = [j for j in range(num_cols) if j not in cols_to_remove]
        header = [header[j] for j in keep]
        data_rows = [[r[j] if j < len(r) else "" for j in keep] for r in data_rows]

    # Write back
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(data_rows)

    return "fixed"


def regenerate_complete_json(state_slug: str, state_dir: Path):
    """Regenerate {state_slug}_complete.json from all quarterly CSVs."""
    quarterly_dir = state_dir / "quarterly"
    if not quarterly_dir.exists():
        return

    quarters = {}
    for q_dir in sorted(quarterly_dir.iterdir()):
        if not q_dir.is_dir():
            continue
        q_name = q_dir.name  # e.g. "2024-03"
        tables = {}
        for csv_file in sorted(q_dir.glob("*.csv")):
            cat_name = csv_file.stem  # e.g. "fi_kcc"
            try:
                with open(csv_file, encoding="utf-8", errors="replace") as f:
                    reader = csv.DictReader(f)
                    fields = reader.fieldnames or []
                    districts = {}
                    for row in reader:
                        dist = row.get("District", "").strip()
                        if not dist:
                            # Try lowercase
                            dist = row.get("district", "").strip()
                        if not dist:
                            continue
                        districts[dist] = {k: v for k, v in row.items()}
                    tables[cat_name] = {
                        "fields": list(fields),
                        "num_districts": len(districts),
                        "districts": districts,
                    }
            except Exception as e:
                print(f"  WARNING: Cannot read {csv_file} for complete.json: {e}")

        if tables:
            quarters[q_name] = {
                "period": quarter_to_period(q_name),
                "as_on_date": quarter_to_as_on(q_name),
                "fy": quarter_to_fy(q_name),
                "tables": tables,
            }

    result = {
        "source": "SLBC NE (State Level Bankers Committee, North East Region)",
        "state": STATE_DISPLAY.get(state_slug, state_slug.replace("-", " ").title()),
        "description": "Complete district-wise banking & financial inclusion data",
        "amount_unit": "Rs. Lakhs",
        "quarters": quarters,
    }

    out_path = state_dir / f"{state_slug}_complete.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    print(f"  Regenerated {out_path.name} ({len(quarters)} quarters)")


def regenerate_timeseries(state_slug: str, state_dir: Path):
    """Regenerate {state_slug}_fi_timeseries.csv and .json from quarterly CSVs."""
    quarterly_dir = state_dir / "quarterly"
    if not quarterly_dir.exists():
        return

    # Collect all data: list of dicts with district, period, etc.
    all_records = []
    all_field_set = set()
    periods_meta = []

    for q_dir in sorted(quarterly_dir.iterdir()):
        if not q_dir.is_dir():
            continue
        q_name = q_dir.name
        period = quarter_to_period(q_name)
        as_on = quarter_to_as_on(q_name)
        fy = quarter_to_fy(q_name)

        # Gather per-district data across all CSVs in this quarter
        district_data = defaultdict(dict)

        for csv_file in sorted(q_dir.glob("*.csv")):
            cat_name = csv_file.stem
            try:
                with open(csv_file, encoding="utf-8", errors="replace") as f:
                    reader = csv.DictReader(f)
                    fields = reader.fieldnames or []
                    for row in reader:
                        dist = row.get("District", row.get("district", "")).strip()
                        if not dist:
                            continue
                        for field in fields:
                            if field.lower() == "district":
                                continue
                            col_key = f"{cat_name}__{slugify_field(field)}"
                            val = row.get(field, "").strip()
                            district_data[dist][col_key] = val
                            all_field_set.add(col_key)
            except Exception:
                pass

        period_districts = []
        for dist, data in sorted(district_data.items()):
            record = {
                "district": dist,
                "period": period,
                "as_on_date": as_on,
                "fy": fy,
            }
            record.update(data)
            all_records.append(record)
            period_districts.append(record)

        if period_districts:
            periods_meta.append({
                "period": period,
                "num_districts": len(period_districts),
                "districts": period_districts,
            })

    if not all_records:
        return

    # Sort field columns for consistent output
    sorted_fields = sorted(all_field_set)
    csv_columns = ["district", "period", "as_on_date", "fy"] + sorted_fields

    # Write CSV
    csv_path = state_dir / f"{state_slug}_fi_timeseries.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction="ignore")
        writer.writeheader()
        for rec in all_records:
            writer.writerow(rec)

    # Write JSON
    json_path = state_dir / f"{state_slug}_fi_timeseries.json"
    result = {
        "source": "SLBC NE (State Level Bankers Committee, North East Region)",
        "state": STATE_DISPLAY.get(state_slug, state_slug.replace("-", " ").title()),
        "description": "Complete district-wise FI time-series",
        "num_periods": len(periods_meta),
        "total_records": len(all_records),
        "total_fields": len(csv_columns),
        "periods": periods_meta,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    print(f"  Regenerated timeseries: {len(all_records)} records, {len(sorted_fields)} fields, {len(periods_meta)} periods")


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #

def main():
    print("=" * 70)
    print("fix_round2.py — SLBC NE Data Quality Fixes")
    print("=" * 70)
    print()

    grand_stats = defaultdict(lambda: defaultdict(int))
    total_files_fixed = 0
    total_files_deleted = 0
    total_files_scanned = 0

    for state_slug in STATES:
        state_dir = BASE_DIR / state_slug
        if not state_dir.exists():
            print(f"SKIP: {state_slug} (directory not found)")
            continue

        quarterly_dir = state_dir / "quarterly"
        if not quarterly_dir.exists():
            print(f"SKIP: {state_slug} (no quarterly directory)")
            continue

        print(f"Processing: {STATE_DISPLAY.get(state_slug, state_slug)}")

        stats = defaultdict(int)
        state_fixed = 0
        state_deleted = 0
        state_scanned = 0

        for q_dir in sorted(quarterly_dir.iterdir()):
            if not q_dir.is_dir():
                continue
            for csv_file in sorted(q_dir.glob("*.csv")):
                state_scanned += 1
                result = process_csv(csv_file, stats)
                if result == "fixed":
                    state_fixed += 1
                elif result == "deleted":
                    state_deleted += 1

        # Print per-state summary
        print(f"  Scanned: {state_scanned} files | Fixed: {state_fixed} | Deleted: {state_deleted}")
        for issue_key in sorted(stats.keys()):
            print(f"    {issue_key}: {stats[issue_key]}")
        grand_stats[state_slug] = dict(stats)
        total_files_fixed += state_fixed
        total_files_deleted += state_deleted
        total_files_scanned += state_scanned

        # Regenerate derived files
        print("  Regenerating complete.json ...")
        regenerate_complete_json(state_slug, state_dir)
        print("  Regenerating timeseries ...")
        regenerate_timeseries(state_slug, state_dir)
        print()

    # Grand summary
    print("=" * 70)
    print("GRAND SUMMARY")
    print("=" * 70)
    print(f"Total files scanned:  {total_files_scanned}")
    print(f"Total files fixed:    {total_files_fixed}")
    print(f"Total files deleted:  {total_files_deleted}")
    print()

    # Aggregate issue counts
    agg = defaultdict(int)
    for state_slug, stats in grand_stats.items():
        for k, v in stats.items():
            agg[k] += v

    print("Issue counts across all states:")
    for k in sorted(agg.keys()):
        label = {
            "issue1_garbled_cols": "Issue 1 - Garbled column names fixed",
            "issue2_dash_null": "Issue 2 - Dash-as-null values cleared",
            "issue3_bare_pct": "Issue 3 - Bare '%' columns renamed",
            "issue4_serial_cols": "Issue 4 - Serial number columns removed",
            "issue5_empty_cols": "Issue 5 - Empty columns removed",
            "issue6_dup_district": "Issue 6 - Duplicate District columns removed",
            "issue7_broken_single_col": "Issue 7 - Single-column broken files deleted",
            "issue8_numeric_district": "Issue 8 - Numeric-district files deleted",
            "issue9_pct_naming": "Issue 9 - Percentage naming standardized",
            "issue10_truncated": "Issue 10 - Truncated names fixed",
        }.get(k, k)
        print(f"  {label}: {agg[k]}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
