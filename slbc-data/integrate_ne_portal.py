#!/usr/bin/env python3
"""
Integrate scraped NE portal data (ne_full_scrape.json) into per-state
timeseries JSONs at public/slbc-data/{state}/{state}_fi_timeseries.json.

Maps portal report columns to standard field names matching the existing
timeseries structure.
"""

import json
import os
import copy

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRAPED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ne_full_scrape.json")

STATE_CODE_TO_DIR = {
    "AS": "assam",
    "ME": "meghalaya",
    "MN": "manipur",
    "MZ": "mizoram",
    "NL": "nagaland",
    "AP": "arunachal-pradesh",
}

# ── Column index → field name mappings for each report ──────────────

# CDR report (24 cols) - maps to credit_deposit_ratio + branch_network
CDR_MAP = {
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

# PMJDY report (12 cols)
PMJDY_MAP = {
    2:  "pmjdy__rural_no",
    3:  "pmjdy__urban_no",
    4:  "pmjdy__male_no",
    5:  "pmjdy__female_no",
    6:  "pmjdy__total_pmjdy_no",
    7:  "pmjdy__no_of_zero_balance_a_c",
    8:  "pmjdy__deposits_held_in_a_c_amt",
    9:  "pmjdy__no_of_rupay_card_issued",
    10: "pmjdy__rupay_card_activated",
    11: "pmjdy__no_of_aadhaar_seeded",
}

# FI & KCC report (7 cols)
FI_KCC_MAP = {
    2: "fi_kcc__inactive_csps",
    3: "fi_kcc__rupay_card_active_in_pmjdy",
    4: "fi_kcc__first_time_active_rupay_card",
    5: "fi_kcc__aadhaar_authenticated_sb_accounts",
    6: "fi_kcc__rupay_card_issued_in_kcc",
}

# Digital transactions (14 cols)
DIGITAL_MAP = {
    2:  "digital_transactions__bhim_upi_a_c",
    3:  "digital_transactions__bhim_upi_amt",
    4:  "digital_transactions__bhim_aadhaar_a_c",
    5:  "digital_transactions__bhim_aadhaar_amt",
    6:  "digital_transactions__bharat_qr_code_a_c",
    7:  "digital_transactions__bharat_qr_code_amt",
    8:  "digital_transactions__imps_a_c",
    9:  "digital_transactions__imps_amt",
    10: "digital_transactions__debit_credit_cards_a_c",
    11: "digital_transactions__debit_credit_cards_amt",
    12: "digital_transactions__ussd_a_c",
    13: "digital_transactions__ussd_amt",
}

# NRLM/SHG report (11 cols)
NRLM_MAP = {
    2:  "nrlm__cy_shg_no",
    3:  "nrlm__cy_shg_amt",
    4:  "nrlm__os_no",
    5:  "nrlm__os_amt",
    6:  "nrlm__irregular_no",
    7:  "nrlm__irregular_amt",
    8:  "nrlm__npa_no",
    9:  "nrlm__npa_amt",
    10: "nrlm__npa_pct",
}

# PMEGP report (11 cols)
PMEGP_MAP = {
    2:  "pmegp__cy_sanction_no",
    3:  "pmegp__cy_sanction_amt",
    4:  "pmegp__cy_disbursed_no",
    5:  "pmegp__cy_disbursed_amt",
    6:  "pmegp__os_no",
    7:  "pmegp__os_amt",
    8:  "pmegp__npa_no",
    9:  "pmegp__npa_amt",
    10: "pmegp__npa_pct",
}

# Aadhaar report (5 cols)
AADHAAR_MAP = {
    2: "aadhaar_authentication__no_of_operative_casa",
    3: "aadhaar_authentication__no_of_aadhaar_seeded_casa",
    4: "aadhaar_authentication__no_of_authenticated_casa",
}

# SHG report (15 cols)
SHG_MAP = {
    2:  "shg__savings_linked_no_cy",
    3:  "shg__cy_savings_linked_amt",
    4:  "shg__credit_linked_no_cy",
    5:  "shg__cy_credit_linked_amt",
    6:  "shg__savings_linked_no",
    7:  "shg__savings_linked_amt",
    8:  "shg__credit_linked_no",
    9:  "shg__credit_linked_amt",
    10: "shg__os_no",
    11: "shg__os_amt",
    12: "shg__npa_no",
    13: "shg__npa_amt",
    14: "shg__npa_pct",
}

# Minority disbursement (16 cols)
MINORITY_MAP = {
    2:  "minority_disbursement__christians_no",
    3:  "minority_disbursement__christians_amt",
    4:  "minority_disbursement__muslims_no",
    5:  "minority_disbursement__muslims_amt",
    6:  "minority_disbursement__buddhists_no",
    7:  "minority_disbursement__buddhists_amt",
    8:  "minority_disbursement__sikhs_no",
    9:  "minority_disbursement__sikhs_amt",
    10: "minority_disbursement__zorastrians_no",
    11: "minority_disbursement__zorastrians_amt",
    12: "minority_disbursement__jains_no",
    13: "minority_disbursement__jains_amt",
    14: "minority_disbursement__total_no",
    15: "minority_disbursement__total_amt",
}

# SC/ST finance (10 cols)
SC_ST_MAP = {
    2: "sc_st_finance__sc_disbursement_no",
    3: "sc_st_finance__sc_disbursement_amt",
    4: "sc_st_finance__sc_outstanding_no",
    5: "sc_st_finance__sc_outstanding_amt",
    6: "sc_st_finance__st_disbursement_no",
    7: "sc_st_finance__st_disbursement_amt",
    8: "sc_st_finance__st_outstanding_no",
    9: "sc_st_finance__st_outstanding_amt",
}

REPORT_COLUMN_MAPS = {
    "credit_deposit_ratio": CDR_MAP,
    "pmjdy": PMJDY_MAP,
    "fi_kcc": FI_KCC_MAP,
    "digital_transactions": DIGITAL_MAP,
    "nrlm": NRLM_MAP,
    "pmegp": PMEGP_MAP,
    "aadhaar_authentication": AADHAAR_MAP,
    "shg": SHG_MAP,
    "minority_disbursement": MINORITY_MAP,
    "sc_st_finance": SC_ST_MAP,
}

# Categories that get a __district field
REPORT_CATEGORIES = {
    "credit_deposit_ratio": ["credit_deposit_ratio", "branch_network"],
    "pmjdy": ["pmjdy"],
    "fi_kcc": ["fi_kcc"],
    "digital_transactions": ["digital_transactions"],
    "nrlm": ["nrlm"],
    "pmegp": ["pmegp"],
    "aadhaar_authentication": ["aadhaar_authentication"],
    "shg": ["shg"],
    "minority_disbursement": ["minority_disbursement"],
    "sc_st_finance": ["sc_st_finance"],
}


def normalize_name(name):
    """Normalize district name for matching."""
    return name.upper().replace(" ", "").replace("-", "").replace(".", "")


def parse_value(val):
    """Parse a scraped value string. Return as string."""
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
    month_order = {"March": 3, "June": 6, "September": 9, "December": 12}
    parts = period_str.split()
    if len(parts) == 2 and parts[0] in month_order:
        return (int(parts[1]), month_order[parts[0]])
    return (9999, 0)


def build_canonical_names(ts):
    """Build map of normalized name -> canonical district name from existing timeseries."""
    canonical = {}
    for p in ts.get("periods", []):
        for d in p.get("districts", []):
            name = d.get("district", "")
            if name and not name.isdigit():
                norm = normalize_name(name)
                if norm not in canonical:
                    canonical[norm] = name
    return canonical


# Common name mappings for NE states
DISTRICT_NAME_MAP = {
    # Meghalaya
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
    # Assam
    "KARBIANGLONG": "Karbi Anglong",
    "SOUTHSALMARAMANKACHAR": "South Salmara-Mankachar",
    "WESTKARBIANGLONG": "West Karbi Anglong",
    "DIMALHASAO": "Dima Hasao",
    "KAMRUPMETRO": "Kamrup Metro",
    "KAMRUPMETROPOLITAN": "Kamrup Metro",
    # Manipur
    "IMPHALEAST": "Imphal East",
    "IMPHALWEST": "Imphal West",
    "CHURACHANDPUR": "Churachandpur",
    # Arunachal Pradesh
    "DIBANGVALLEY": "Dibang Valley",
    "EASTKAMELNG": "East Kameng",
    "EASTKAMENG": "East Kameng",
    "EASTSIANG": "East Siang",
    "KRADAADI": "Kra Daadi",
    "KURUNQKUMEY": "Kurung Kumey",
    "KURUNGKUMEY": "Kurung Kumey",
    "LOWERDIBANGVALLEY": "Lower Dibang Valley",
    "LOWERSUBANSIRI": "Lower Subansiri",
    "PAKEKESSANG": "Pake Kessang",
    "PAKEKESANG": "Pake Kessang",
    "PAPUMPARE": "Papum Pare",
    "UPPERSUBANSIRI": "Upper Subansiri",
    "UPPERSIANG": "Upper Siang",
    "WESTKAMENG": "West Kameng",
    "WESTSIANG": "West Siang",
    "CAPITALCOMPLEX": "Capital Complex",
    "KEYIPANYOR": "Keyi Panyor",
    "KAMLE": "Kamle",
    "LEPARADA": "Lepa Rada",
    "SHIYOMI": "Shi Yomi",
    "LOWERSIANG": "Lower Siang",
}


def resolve_district_name(scraped_name, canonical_names):
    """Resolve a scraped district name to its canonical form."""
    norm = normalize_name(scraped_name)

    # Check canonical names from existing timeseries
    if norm in canonical_names:
        return canonical_names[norm]

    # Check our manual mapping
    if norm in DISTRICT_NAME_MAP:
        return DISTRICT_NAME_MAP[norm]

    # Title case fallback
    return scraped_name.strip().title()


def main():
    print("Loading scraped data...")
    with open(SCRAPED_PATH) as f:
        scraped = json.load(f)

    for state_code, state_dir in STATE_CODE_TO_DIR.items():
        ts_path = os.path.join(REPO_ROOT, "public", "slbc-data", state_dir, f"{state_dir}_fi_timeseries.json")

        if not os.path.exists(ts_path):
            print(f"\nSkipping {state_code} - no timeseries file at {ts_path}")
            continue

        print(f"\n{'='*60}")
        print(f"  {state_code} ({state_dir})")
        print(f"{'='*60}")

        with open(ts_path) as f:
            ts = json.load(f)

        canonical_names = build_canonical_names(ts)
        existing_periods = {p["period"]: p for p in ts["periods"]}

        state_data = scraped.get(state_code, {})
        if not state_data:
            print("  No scraped data")
            continue

        stats = {
            "periods_updated": 0,
            "periods_created": 0,
            "districts_updated": 0,
            "districts_created": 0,
            "fields_added": 0,
        }

        # Collect all portal data organized by period -> district -> fields
        portal_by_period = {}  # {period: {norm_name: {field: value}}}

        for report_key, report_data in state_data.items():
            col_map = REPORT_COLUMN_MAPS.get(report_key)
            if not col_map:
                print(f"  WARNING: No column map for {report_key}")
                continue

            categories = REPORT_CATEGORIES.get(report_key, [report_key])

            for period_name, period_data in report_data.items():
                if period_name not in portal_by_period:
                    portal_by_period[period_name] = {}

                for row in period_data["districts"]:
                    if len(row) < 2:
                        continue

                    scraped_name = row[1].strip()
                    if not scraped_name:
                        continue

                    norm = normalize_name(scraped_name)
                    canonical = resolve_district_name(scraped_name, canonical_names)

                    # Add to canonical names if new
                    if norm not in canonical_names:
                        canonical_names[norm] = canonical

                    if norm not in portal_by_period[period_name]:
                        portal_by_period[period_name][norm] = {"district": canonical, "period": period_name}

                    d = portal_by_period[period_name][norm]

                    # Set category district fields
                    for cat in categories:
                        d[f"{cat}__district"] = canonical

                    # Map column values
                    for col_idx, field_name in col_map.items():
                        if col_idx < len(row):
                            val = parse_value(row[col_idx])
                            if val != "":
                                d[field_name] = val

                    # Compute overall CDR for credit_deposit_ratio report
                    if report_key == "credit_deposit_ratio":
                        try:
                            total_dep = float(row[5].replace(",", ""))
                            total_adv = float(row[9].replace(",", ""))
                            if total_dep > 0:
                                d["credit_deposit_ratio__overall_cd_ratio"] = f"{total_adv / total_dep * 100:.2f}"
                        except (ValueError, ZeroDivisionError, IndexError):
                            pass

        # Now merge portal data into timeseries
        for period_name in sorted(portal_by_period.keys(), key=period_sort_key):
            portal_districts = portal_by_period[period_name]

            if period_name in existing_periods:
                # Update existing period
                period = existing_periods[period_name]
                district_lookup = {}
                for d in period["districts"]:
                    if not d.get("district", "").isdigit():
                        norm = normalize_name(d["district"])
                        district_lookup[norm] = d

                updated_any = False
                for norm, portal_d in portal_districts.items():
                    if norm in district_lookup:
                        # Update existing district
                        existing_d = district_lookup[norm]
                        for field, val in portal_d.items():
                            if field in ("district", "period"):
                                continue
                            if field not in existing_d or existing_d[field] in ("", "0", None):
                                existing_d[field] = val
                                stats["fields_added"] += 1
                            else:
                                # Portal data takes precedence for portal-sourced fields
                                existing_d[field] = val
                        stats["districts_updated"] += 1
                        updated_any = True
                    else:
                        # New district for this period
                        period["districts"].append(portal_d)
                        stats["districts_created"] += 1
                        updated_any = True

                if updated_any:
                    stats["periods_updated"] += 1
            else:
                # Create new period
                new_period = {
                    "period": period_name,
                    "districts": list(portal_districts.values()),
                }
                ts["periods"].append(new_period)
                existing_periods[period_name] = new_period
                stats["periods_created"] += 1
                stats["districts_created"] += len(portal_districts)

        # Sort periods chronologically
        ts["periods"].sort(key=lambda p: period_sort_key(p["period"]))

        # Update metadata
        ts["num_periods"] = len(ts["periods"])
        total_records = sum(len(p["districts"]) for p in ts["periods"])
        ts["total_records"] = total_records
        all_fields = set()
        for p in ts["periods"]:
            for d in p["districts"]:
                all_fields.update(k for k in d.keys() if "__" in k)
        ts["total_fields"] = len(all_fields)

        # Write back
        with open(ts_path, "w") as f:
            json.dump(ts, f, indent=2, ensure_ascii=False)

        print(f"  Periods updated: {stats['periods_updated']}")
        print(f"  Periods created: {stats['periods_created']}")
        print(f"  Districts updated: {stats['districts_updated']}")
        print(f"  Districts created: {stats['districts_created']}")
        print(f"  Fields added: {stats['fields_added']}")
        print(f"  Total periods: {ts['num_periods']}")
        print(f"  Total records: {ts['total_records']}")
        print(f"  Total fields: {ts['total_fields']}")
        print(f"  Written to: {ts_path}")


if __name__ == "__main__":
    main()
