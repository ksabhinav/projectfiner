#!/usr/bin/env python3
"""
Merge scraped CDR/branch/ATM/BC portal data into Meghalaya timeseries JSON.

The scraped JSON (ne_cdr_full_playwright.json) contains data labeled for 6 NE states
but all entries contain identical Meghalaya district data (scraping bug).
This script only processes ME (Meghalaya).
"""

import json
import copy
import os
import shutil

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRAPED_PATH = os.path.join(REPO_ROOT, "slbc-data", "ne_cdr_full_playwright.json")
PUBLIC_TS_PATH = os.path.join(REPO_ROOT, "public", "slbc-data", "meghalaya", "meghalaya_fi_timeseries.json")

# Column index -> target field name mapping
COLUMN_MAP = {
    2:  "credit_deposit_ratio__dep_rural",
    3:  "credit_deposit_ratio__dep_semi_urban",
    4:  "credit_deposit_ratio__dep_urban",
    5:  "credit_deposit_ratio__total_deposit",
    6:  "credit_deposit_ratio__adv_rural",
    7:  "credit_deposit_ratio__adv_semi_urban",
    8:  "credit_deposit_ratio__adv_urban",
    9:  "credit_deposit_ratio__total_advance",
    10: "credit_deposit_ratio__cd_ratio_rural",
    11: "credit_deposit_ratio__cd_ratio_semi_urban",
    12: "credit_deposit_ratio__cd_ratio_urban",
    13: "branch_network__atm_rural",
    14: "branch_network__atm_semi_urban",
    15: "branch_network__atm_urban",
    16: "branch_network__total_atm",
    17: "branch_network__branch_rural",
    18: "branch_network__branch_semi_urban",
    19: "branch_network__branch_urban",
    20: "branch_network__total_branch",
    21: "branch_network__bc_total",
    22: "branch_network__bc_fixed",
    23: "branch_network__bc_other",
}


def normalize_name(name):
    """Normalize district name for matching: uppercase, strip spaces/hyphens."""
    return name.upper().replace(" ", "").replace("-", "")


def parse_value(val):
    """Parse a scraped value string. Return as string (matching existing format)."""
    if val is None or val == "" or val == "-":
        return ""
    val = val.strip().replace(",", "")
    try:
        float(val)
        return val
    except ValueError:
        return val


def period_sort_key(period_str):
    """Convert period string like 'June 2020' to sortable tuple."""
    month_order = {
        "March": 3, "June": 6, "September": 9, "December": 12
    }
    parts = period_str.split()
    if len(parts) == 2 and parts[0] in month_order:
        return (int(parts[1]), month_order[parts[0]])
    return (9999, 0)


def main():
    # Load scraped data
    with open(SCRAPED_PATH) as f:
        scraped = json.load(f)

    # Use ME (Meghalaya) data only - all states have identical Meghalaya data
    me_data = scraped["ME"]

    # Load existing timeseries
    with open(PUBLIC_TS_PATH) as f:
        ts = json.load(f)

    # Build lookup of existing districts by normalized name for each period
    existing_periods = {p["period"]: p for p in ts["periods"]}

    # Build master list of canonical district names from existing data
    canonical_names = {}
    for p in ts["periods"]:
        for d in p["districts"]:
            if not d["district"].isdigit():
                norm = normalize_name(d["district"])
                if norm not in canonical_names:
                    canonical_names[norm] = d["district"]

    # Also add scraped names that might be new
    for period_name, period_data in me_data.items():
        for row in period_data["districts"]:
            scraped_name = row[1]
            norm = normalize_name(scraped_name)
            if norm not in canonical_names:
                # Convert to title case with spaces
                # e.g. EASTERNWESTKHASIHILLS -> Eastern West Khasi Hills
                # We need manual mapping for these
                name_map = {
                    "EASTERNWESTKHASIHILLS": "Eastern West Khasi Hills",
                    "EASTGAROHILLS": "East Garo Hills",
                    "EASTJAINTIAHILLS": "East Jaintia Hills",
                    "EASTKHASIHILLS": "East Khasi Hills",
                    "NORTHGAROHILLS": "North Garo Hills",
                    "RIBHOI": "Ri Bhoi",
                    "SOUTHGAROHILLS": "South Garo Hills",
                    "SOUTHWESTGAROHILLS": "South West Garo Hills",
                    "SOUTHWESTKHASIHILLS": "South West Khasi Hills",
                    "WESTGAROHILLS": "West Garo Hills",
                    "WESTJAINTIAHILLS": "West Jaintia Hills",
                    "WESTKHASIHILLS": "West Khasi Hills",
                }
                if scraped_name in name_map:
                    canonical_names[norm] = name_map[scraped_name]
                else:
                    print(f"WARNING: No canonical name for {scraped_name}")
                    canonical_names[norm] = scraped_name

    stats = {"periods_updated": 0, "periods_created": 0, "districts_updated": 0, "districts_created": 0}

    for period_name, period_data in me_data.items():
        if period_name in existing_periods:
            # Period exists - update/add districts
            period = existing_periods[period_name]
            # Build district lookup by normalized name
            district_lookup = {}
            for d in period["districts"]:
                if not d["district"].isdigit():
                    norm = normalize_name(d["district"])
                    district_lookup[norm] = d

            updated_any = False
            for row in period_data["districts"]:
                scraped_name = row[1]
                norm = normalize_name(scraped_name)
                canonical = canonical_names.get(norm, scraped_name)

                if norm in district_lookup:
                    # District exists - add/update fields
                    d = district_lookup[norm]
                    for col_idx, field_name in COLUMN_MAP.items():
                        val = parse_value(row[col_idx])
                        if val != "":
                            d[field_name] = val
                    # Also set district field for each category
                    d["credit_deposit_ratio__district"] = canonical
                    d["branch_network__district"] = canonical
                    # Compute overall CDR
                    try:
                        total_dep = float(row[5].replace(",", ""))
                        total_adv = float(row[9].replace(",", ""))
                        if total_dep > 0:
                            d["credit_deposit_ratio__overall_cd_ratio"] = f"{total_adv / total_dep * 100:.2f}"
                    except (ValueError, ZeroDivisionError):
                        pass
                    stats["districts_updated"] += 1
                    updated_any = True
                else:
                    # District doesn't exist in this period - add it
                    new_d = {
                        "district": canonical,
                        "period": period_name,
                    }
                    for col_idx, field_name in COLUMN_MAP.items():
                        val = parse_value(row[col_idx])
                        if val != "":
                            new_d[field_name] = val
                    new_d["credit_deposit_ratio__district"] = canonical
                    new_d["branch_network__district"] = canonical
                    try:
                        total_dep = float(row[5].replace(",", ""))
                        total_adv = float(row[9].replace(",", ""))
                        if total_dep > 0:
                            new_d["credit_deposit_ratio__overall_cd_ratio"] = f"{total_adv / total_dep * 100:.2f}"
                    except (ValueError, ZeroDivisionError):
                        pass
                    period["districts"].append(new_d)
                    stats["districts_created"] += 1
                    updated_any = True

            if updated_any:
                stats["periods_updated"] += 1
        else:
            # Period doesn't exist - create it
            new_period = {"period": period_name, "districts": []}
            for row in period_data["districts"]:
                scraped_name = row[1]
                norm = normalize_name(scraped_name)
                canonical = canonical_names.get(norm, scraped_name)

                new_d = {
                    "district": canonical,
                    "period": period_name,
                }
                for col_idx, field_name in COLUMN_MAP.items():
                    val = parse_value(row[col_idx])
                    if val != "":
                        new_d[field_name] = val
                new_d["credit_deposit_ratio__district"] = canonical
                new_d["branch_network__district"] = canonical
                try:
                    total_dep = float(row[5].replace(",", ""))
                    total_adv = float(row[9].replace(",", ""))
                    if total_dep > 0:
                        new_d["credit_deposit_ratio__overall_cd_ratio"] = f"{total_adv / total_dep * 100:.2f}"
                except (ValueError, ZeroDivisionError):
                    pass
                new_period["districts"].append(new_d)
                stats["districts_created"] += 1

            ts["periods"].append(new_period)
            stats["periods_created"] += 1

    # Sort periods chronologically
    ts["periods"].sort(key=lambda p: period_sort_key(p["period"]))

    # Update metadata
    ts["num_periods"] = len(ts["periods"])
    total_records = sum(len(p["districts"]) for p in ts["periods"])
    ts["total_records"] = total_records
    # Count unique field names
    all_fields = set()
    for p in ts["periods"]:
        for d in p["districts"]:
            all_fields.update(k for k in d.keys() if "__" in k)
    ts["total_fields"] = len(all_fields)

    # Write back
    with open(PUBLIC_TS_PATH, "w") as f:
        json.dump(ts, f, indent=2, ensure_ascii=False)

    print(f"Meghalaya timeseries updated:")
    print(f"  Periods updated: {stats['periods_updated']}")
    print(f"  Periods created: {stats['periods_created']}")
    print(f"  Districts updated: {stats['districts_updated']}")
    print(f"  Districts created: {stats['districts_created']}")
    print(f"  Total periods: {ts['num_periods']}")
    print(f"  Total records: {ts['total_records']}")
    print(f"  Total fields: {ts['total_fields']}")
    print(f"  Written to: {PUBLIC_TS_PATH}")


if __name__ == "__main__":
    main()
