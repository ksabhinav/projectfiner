#!/usr/bin/env python3
"""
Normalize field names across ALL 8 NE states' SLBC data.

Fixes duplicate columns caused by inconsistent field naming:
- AC / Ac / ac / A/c / A/Cs → A/C
- Amt. / Amount → Amt
- No / Nos / No.s / Nos. → No.
- Trailing periods
- Spacing issues (A/ C → A/C)
- Multiple spaces → single space

Operates on {state}_complete.json, then regenerates:
- quarterly CSVs
- timeseries CSV and JSON
"""

import json
import csv
import os
import re
from pathlib import Path
from collections import OrderedDict

BASE = Path("/Users/abhinav/Downloads/projectfiner/public/slbc-data")

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

# Map state directory names to JSON slug names
STATE_SLUGS = {
    "assam": "assam",
    "meghalaya": "meghalaya",
    "manipur": "manipur",
    "arunachal-pradesh": "arunachal_pradesh",
    "mizoram": "mizoram",
    "tripura": "tripura",
    "nagaland": "nagaland",
    "sikkim": "sikkim",
}


def normalize_field_name(name):
    """
    Normalize a single field name to canonical form.

    Rules applied in order:
    1. Strip leading/trailing whitespace
    2. Normalize unicode characters
    3. Fix spacing around /  (A/ C → A/C, A /C → A/C)
    4. Multiple spaces → single space
    5. Strip trailing periods (but not from abbreviations like No.)
    6. Normalize account variants: AC, Ac, ac, A/c, A/Cs → A/C
    7. Normalize amount variants: Amt., Amount → Amt
    8. Normalize number variants: No, Nos, No.s, Nos. → No.
    """
    if not name or not isinstance(name, str):
        return name

    s = name.strip()

    # Normalize multiple spaces to single
    s = re.sub(r'\s+', ' ', s)

    # Fix spacing around slashes: "A/ C" → "A/C", "A /C" → "A/C"
    s = re.sub(r'\s*/\s*', '/', s)

    # Strip trailing period(s) — we'll add back for No. later
    s = re.sub(r'\.+$', '', s)

    # --- Normalize A/C variants ---
    # Match end of string or before space: AC, Ac, ac, A/c, A/Cs, A/cs
    # Word boundary at end: "Micro TL AC" → "Micro TL A/C"
    # Also handle "A/Cs" → "A/C"

    # First handle A/Cs, A/cs at word boundary
    s = re.sub(r'\bA/[Cc]s\b', 'A/C', s)
    s = re.sub(r'\ba/cs\b', 'A/C', s, flags=re.IGNORECASE)

    # Handle A/c → A/C (already has slash)
    s = re.sub(r'\bA/c\b', 'A/C', s)
    s = re.sub(r'\ba/c\b', 'A/C', s, flags=re.IGNORECASE)

    # Handle standalone AC, Ac, ac at end of string or as last word
    # Be careful not to match "AC" in middle of words like "ACHIEV"
    # Only match if AC/Ac/ac is at end of string or followed by space
    s = re.sub(r'\bAC$', 'A/C', s)
    s = re.sub(r'\bAc$', 'A/C', s)
    s = re.sub(r'\bac$', 'A/C', s)

    # Also handle when AC/Ac appears before a space (mid-field)
    # e.g., "Micro TL AC something" — but be conservative
    # Only do this for clear patterns where AC means "account"
    s = re.sub(r'\bAC\s', 'A/C ', s)
    s = re.sub(r'\bAc\s', 'A/C ', s)

    # Handle "A/ C" that might still exist after slash normalization
    # (already handled above with slash spacing fix)

    # --- Normalize Amt variants ---
    # Amt. → Amt (trailing period already stripped above)
    # "Amount" → "Amt" only at end of field
    s = re.sub(r'\bAmount$', 'Amt', s)

    # --- Normalize No. variants ---
    # No, Nos, No.s, Nos. → No.
    # Be careful: "No" at end could be "No." meaning "Number"
    # But also could be part of a word. Use word boundary.
    s = re.sub(r'\bNos?\.*s?\.?$', 'No.', s)
    s = re.sub(r'\bNo\.s$', 'No.', s)

    # Handle "No." in middle of string too (less common but possible)
    # "Tot MSME (PS) Disb No." is already correct
    # "Tot MSME (PS) Disb No" should become "Tot MSME (PS) Disb No."

    # Final cleanup: strip trailing/leading whitespace again
    s = s.strip()

    return s


def normalize_fields_in_table(table):
    """
    Normalize field names in a table dict (has 'fields' list and 'districts' dict).
    If normalization causes two fields to merge, prefer non-null/non-empty values.
    Returns (normalized_table, num_merges).
    """
    merges = 0

    # Normalize the fields list
    raw_fields = table.get("fields", [])
    # Build mapping: raw_field → normalized_field
    field_map = {}
    normalized_fields_ordered = []
    seen_normalized = set()

    for raw_f in raw_fields:
        norm_f = normalize_field_name(raw_f)
        field_map[raw_f] = norm_f
        if norm_f not in seen_normalized:
            normalized_fields_ordered.append(norm_f)
            seen_normalized.add(norm_f)
        else:
            merges += 1

    table["fields"] = normalized_fields_ordered

    # Normalize district data
    districts = table.get("districts", {})
    for dist_name, dist_data in districts.items():
        new_data = {}
        for raw_f, val in dist_data.items():
            norm_f = normalize_field_name(raw_f)
            if norm_f in new_data:
                # Merge: prefer non-null, non-empty value
                existing = new_data[norm_f]
                if (existing is None or existing == "" or existing == "0") and val and val != "" and val != "0":
                    new_data[norm_f] = val
            else:
                new_data[norm_f] = val
        districts[dist_name] = new_data

    # Also make sure fields list includes any fields from district data
    # that weren't in the original fields list
    for dist_data in districts.values():
        for f in dist_data.keys():
            if f not in seen_normalized:
                normalized_fields_ordered.append(f)
                seen_normalized.add(f)
    table["fields"] = normalized_fields_ordered

    return table, merges


def process_state(state_dir_name):
    """Process one state: normalize fields in complete.json, regenerate CSVs."""
    slug = STATE_SLUGS[state_dir_name]
    state_dir = BASE / state_dir_name
    json_path = state_dir / f"{slug}_complete.json"

    if not json_path.exists():
        print(f"  SKIP: {json_path} not found")
        return 0, 0

    with open(json_path) as f:
        data = json.load(f)

    total_merges = 0
    total_fields_normalized = 0

    quarters = data.get("quarters", {})
    for qname, quarter in quarters.items():
        tables = quarter.get("tables", {})
        for tname, table in tables.items():
            # Count fields before
            before_count = len(table.get("fields", []))

            table, merges = normalize_fields_in_table(table)
            tables[tname] = table

            after_count = len(table.get("fields", []))
            total_merges += merges
            if before_count != after_count:
                total_fields_normalized += (before_count - after_count)

    # Write back the normalized JSON
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Regenerate quarterly CSVs
    regenerate_quarterly_csvs(data, state_dir / "quarterly")

    # Regenerate timeseries
    regenerate_timeseries(data, state_dir, slug)

    return total_merges, total_fields_normalized


def regenerate_quarterly_csvs(data, quarterly_dir):
    """Regenerate all quarterly CSVs from the normalized JSON."""
    quarters = data.get("quarters", {})

    for qname, quarter in quarters.items():
        # Determine folder name - qname is already YYYY-MM format
        folder_name = qname  # e.g., "2020-06"

        # Verify it looks like YYYY-MM
        if not re.match(r'^\d{4}-\d{2}$', folder_name):
            # Try to parse from period/as_on_date
            as_on = quarter.get("as_on_date", "")
            if as_on:
                parts = as_on.split("-")
                if len(parts) == 3:
                    folder_name = f"{parts[2]}-{parts[1]}"
            if not re.match(r'^\d{4}-\d{2}$', folder_name):
                print(f"    WARNING: Cannot determine folder for quarter '{qname}', skipping")
                continue

        folder_path = quarterly_dir / folder_name

        # Delete existing CSVs
        if folder_path.exists():
            for f in folder_path.glob("*.csv"):
                f.unlink()
        else:
            folder_path.mkdir(parents=True, exist_ok=True)

        # Write one CSV per category
        tables = quarter.get("tables", {})
        for tname, table in tables.items():
            districts = table.get("districts", {})
            if not districts:
                continue

            fields = table.get("fields", [])
            if not fields:
                first_dist = next(iter(districts.values()))
                fields = list(first_dist.keys())

            csv_path = folder_path / f"{tname}.csv"
            with open(csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["District"] + fields)
                for dist_name in sorted(districts.keys()):
                    dist_data = districts[dist_name]
                    row = [dist_name] + [dist_data.get(fld, "") for fld in fields]
                    writer.writerow(row)


def normalize_timeseries_key(key):
    """
    Normalize a timeseries column key (category__field format, already lowercased).
    Apply the same normalization rules but for the lowercased/underscored version.
    """
    # Strip trailing periods/dots
    key = re.sub(r'\.+$', '', key)

    # Normalize a/c variants at end or before underscore
    # _ac$ → _a/c
    key = re.sub(r'_ac$', '_a/c', key)
    key = re.sub(r'_acs$', '_a/c', key)
    key = re.sub(r'_a/cs$', '_a/c', key)

    # _amt.$ → _amt (trailing dot already stripped)
    # _amount$ → _amt
    key = re.sub(r'_amount$', '_amt', key)
    key = re.sub(r'_amt\.$', '_amt', key)

    # _no$ → _no. , _nos$ → _no. , _nos.$ → _no. , _no.s$ → _no.
    key = re.sub(r'_nos?\.?s?\.?$', '_no.', key)
    key = re.sub(r'_no\.s$', '_no.', key)
    # But make sure _no. stays as _no.
    if key.endswith('_no'):
        key = key + '.'

    # Fix double underscores
    key = re.sub(r'_+', '_', key)
    key = key.strip('_')

    return key


def regenerate_timeseries(data, state_dir, state_slug):
    """Regenerate timeseries CSV and JSON from normalized data."""
    all_records = []
    all_field_keys = set()

    quarters = data.get("quarters", {})

    # First pass: collect all normalized field keys
    for qname, q in quarters.items():
        for tname, table in q.get("tables", {}).items():
            for dist_name, fields in table.get("districts", {}).items():
                for fld in fields.keys():
                    key = f"{tname}__{fld}"
                    # Normalize to lowercase with underscores
                    norm_key = re.sub(r'[^a-z0-9_/()&.,%]+', '_',
                                      key.lower().replace(' ', '_'))
                    norm_key = re.sub(r'_+', '_', norm_key).strip('_')
                    # Apply additional normalization
                    norm_key = normalize_timeseries_key(norm_key)
                    all_field_keys.add(norm_key)

    sorted_fields = sorted(all_field_keys)

    # Second pass: build records
    periods_data = {}

    for qname, q in quarters.items():
        period = q.get("period", qname)
        as_on = q.get("as_on_date", "")
        fy = q.get("fy", "")

        quarter_districts = {}
        for tname, table in q.get("tables", {}).items():
            for dist_name, fields in table.get("districts", {}).items():
                if dist_name not in quarter_districts:
                    quarter_districts[dist_name] = {
                        "district": dist_name,
                        "period": period,
                        "as_on_date": as_on,
                        "fy": fy,
                    }
                for fld, val in fields.items():
                    key = f"{tname}__{fld}"
                    norm_key = re.sub(r'[^a-z0-9_/()&.,%]+', '_',
                                      key.lower().replace(' ', '_'))
                    norm_key = re.sub(r'_+', '_', norm_key).strip('_')
                    norm_key = normalize_timeseries_key(norm_key)

                    # Merge: prefer non-null
                    existing = quarter_districts[dist_name].get(norm_key)
                    if existing is None or existing == "" or existing == "0":
                        quarter_districts[dist_name][norm_key] = val
                    elif val and val != "" and val != "0" and (existing is None or existing == ""):
                        quarter_districts[dist_name][norm_key] = val

        for dist_name, record in sorted(quarter_districts.items()):
            all_records.append(record)

        if period not in periods_data:
            periods_data[period] = {
                "period": period,
                "num_districts": len(quarter_districts),
                "districts": [],
            }
        periods_data[period]["districts"] = [
            quarter_districts[d] for d in sorted(quarter_districts.keys())
        ]

    # Write CSV
    csv_path = state_dir / f"{state_slug}_fi_timeseries.csv"
    csv_columns = ["district", "period", "as_on_date", "fy"] + sorted_fields

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction='ignore')
        writer.writeheader()
        for record in all_records:
            writer.writerow(record)

    # Write JSON
    json_path = state_dir / f"{state_slug}_fi_timeseries.json"

    # Sort periods by date
    period_dates = {}
    for r in all_records:
        if r["period"] not in period_dates and r.get("as_on_date"):
            period_dates[r["period"]] = r["as_on_date"]

    def parse_date(d):
        try:
            parts = d.split("-")
            return (int(parts[2]), int(parts[1]), int(parts[0]))
        except:
            return (0, 0, 0)

    sorted_periods = sorted(periods_data.keys(),
                           key=lambda p: parse_date(period_dates.get(p, "01-01-1900")))

    ts_json = {
        "source": data.get("source", "SLBC NE"),
        "state": data.get("state", ""),
        "description": "Complete district-wise FI time-series",
        "num_periods": len(periods_data),
        "total_records": len(all_records),
        "total_fields": len(sorted_fields),
        "periods": [periods_data[p] for p in sorted_periods],
    }

    with open(json_path, "w") as f:
        json.dump(ts_json, f, indent=2, ensure_ascii=False)

    print(f"    Timeseries: {len(all_records)} records, {len(sorted_fields)} fields, {len(periods_data)} periods")


def count_timeseries_columns(state_dir_name):
    """Count columns in a state's timeseries CSV."""
    slug = STATE_SLUGS[state_dir_name]
    csv_path = BASE / state_dir_name / f"{slug}_fi_timeseries.csv"
    if not csv_path.exists():
        return 0
    with open(csv_path) as f:
        header = next(csv.reader(f))
        return len(header)


def verify_assam_msme(state_dir_name="assam"):
    """Verify that Assam acp_disbursement_msme no longer has duplicate columns."""
    slug = STATE_SLUGS[state_dir_name]
    csv_path = BASE / state_dir_name / f"{slug}_fi_timeseries.csv"
    if not csv_path.exists():
        return

    with open(csv_path) as f:
        header = next(csv.reader(f))

    # Find MSME-related columns
    msme_cols = [c for c in header if 'acp_disbursement_msme' in c]

    # Check for duplicates
    from collections import Counter
    counts = Counter(msme_cols)
    dups = {k: v for k, v in counts.items() if v > 1}

    if dups:
        print(f"  WARNING: Still have duplicate MSME columns: {dups}")
    else:
        print(f"  OK: No duplicate MSME columns ({len(msme_cols)} unique MSME fields)")

    # Check specific fields
    micro_tl_ac = [c for c in header if 'micro_tl_a/c' in c]
    micro_tl_ac_old = [c for c in header if 'micro_tl_ac' in c]
    print(f"  'micro_tl_a/c' columns: {micro_tl_ac}")
    if micro_tl_ac_old:
        print(f"  WARNING: Old 'micro_tl_ac' still present: {micro_tl_ac_old}")

    # Check for NaN holes in Micro TL A/C
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    target_col = 'acp_disbursement_msme_micro_tl_a/c'
    if target_col in header:
        non_null = sum(1 for r in rows if r.get(target_col, '') != '')
        total = len(rows)
        print(f"  '{target_col}': {non_null}/{total} non-empty values")


def main():
    print("=" * 70)
    print("FIELD NAME NORMALIZATION — ALL 8 NE STATES")
    print("=" * 70)

    # Record before counts
    print("\n--- BEFORE: Timeseries column counts ---")
    before_counts = {}
    for state in STATES:
        count = count_timeseries_columns(state)
        before_counts[state] = count
        print(f"  {state}: {count} columns")

    # Process each state
    for state in STATES:
        print(f"\n--- Processing: {state} ---")
        merges, fields_normalized = process_state(state)
        print(f"    Field merges (in JSON): {merges}")

    # Record after counts
    print("\n--- AFTER: Timeseries column counts ---")
    after_counts = {}
    for state in STATES:
        count = count_timeseries_columns(state)
        after_counts[state] = count
        print(f"  {state}: {count} columns")

    # Summary
    print("\n--- SUMMARY: Column count changes ---")
    print(f"  {'State':<25} {'Before':>8} {'After':>8} {'Reduced':>8}")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8}")
    for state in STATES:
        before = before_counts[state]
        after = after_counts[state]
        reduced = before - after
        print(f"  {state:<25} {before:>8} {after:>8} {reduced:>8}")

    # Verify Assam MSME
    print("\n--- VERIFICATION: Assam acp_disbursement_msme ---")
    verify_assam_msme()

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
