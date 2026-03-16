#!/usr/bin/env python3
"""
Integrate scraped portal data (MN/MZ/ME) into per-state JSON files.
Portal data takes precedence over PDF data where both exist.
"""

import csv, gzip, json, os
from collections import defaultdict

# ── Mapping: report_key → category name ──────────────────────────

REPORT_TO_CATEGORY = {
    "ACP_OS_D": "acp_outstanding",
    "ACP_OS_SUM_D": "acp_os_npa_summary",
    "ACP_DA_D": "acp_disbursement_agri",
    "ACP_DM_D": "acp_disbursement_msme",
    "ACP_DO_D": "acp_disbursement_other_ps",
    "ACP_DN_D": "acp_disbursement_non_ps",
    "ACP_NPA_D": "acp_npa",
    "ACP_PERF_D": "acp_target_achievement",
    "ACP_NPS_D": "acp_nps_os_npa_summary",
    "AGRI_OS_D": "agri_outstanding",
    "AGRI_NPA_D": "agri_npa",
    "MSME_OS_D": "msme_outstanding",
    "MSME_NPA_D": "msme_npa",
    "OTHER_OS_D": "other_ps_outstanding",
    "OTHER_NPA_D": "other_ps_npa",
    "NON_NPA_D": "non_ps_npa",
    "WEAKER_D": "weaker_section",
    "GOVT_NPA_D": "govt_sponsored_npa",
    "KCC_D": "kcc",
    "CROPS_KCC_D": "kcc_crops",
    "EDU_D": "education_loan",
    "SHG_D": "shg",
    "JLG_D": "jlg",
    "PMMY_DISB_D": "pmmy_mudra_disbursement",
    "PMMY_OS_D": "pmmy_mudra_os_npa",
    "MIN_D_D": "minority_disbursement",
    "MIN_O_D": "minority_outstanding",
    "SCST_D": "sc_st_finance",
    "WOMEN_D": "women_finance",
    "PMJDY_D": "pmjdy",
    "SBY_D": "social_security",
    "SUI_D": "sui",
    "AADHAAR_D": "aadhaar_authentication",
    "IC_DISB_D": "investment_credit_agri_disbursement",
    "IC_OUTS_D": "investment_credit_agri_outstanding",
    "FI_KCC_D": "fi_kcc",
    "DIGITAL_D": "digital_transactions",
    "PMEGP_D": "pmegp",
    "NULM_D": "nulm",
    "NRLM_D": "nrlm",
    "HOUSING_D": "housing_finance",
    "CDR_D": "cdr_details",
    "CDR_RATIO_D": "credit_deposit_ratio",
    "BRANCH_D": "branch_network",
    "CROPS_D": "crops",
}

# ── Quarter conversion ───────────────────────────────────────────

def to_quarter_key(quarter_label, fy_label):
    """Convert 'June' + 'FY2020-2021' → '2020-06'"""
    # FY2020-2021 → start_year=2020, end_year=2021
    parts = fy_label.replace("FY", "").split("-")
    start_year = int(parts[0])
    end_year = int(parts[1])

    month_map = {"June": "06", "September": "09", "December": "12", "March": "03"}
    month = month_map[quarter_label]

    # March belongs to end_year, others to start_year
    if quarter_label == "March":
        return f"{end_year}-{month}"
    else:
        return f"{start_year}-{month}"


def quarter_metadata(quarter_key):
    """Generate period, as_on_date, fy from quarter key like '2020-06'"""
    year, month = quarter_key.split("-")
    year = int(year)
    month_num = int(month)

    month_names = {3: "March", 6: "June", 9: "September", 12: "December"}
    month_name = month_names[month_num]

    last_days = {3: 31, 6: 30, 9: 30, 12: 31}
    last_day = last_days[month_num]

    # FY: April-March
    if month_num <= 3:
        fy = f"{year-1}-{str(year)[2:]}"
    else:
        fy = f"{year}-{str(year+1)[2:]}"

    return {
        "period": f"{month_name} {year}",
        "as_on_date": f"{last_day:02d}-{month_num:02d}-{year}",
        "fy": fy,
    }


# ── District name normalization ──────────────────────────────────

def title_case_district(name):
    """IMPHAL EAST → Imphal East, EAST GARO HILLS → East Garo Hills"""
    return name.title()


# ── State mapping ────────────────────────────────────────────────

STATE_CODE_TO_DIR = {
    "MN": "manipur",
    "MZ": "mizoram",
    "ME": "meghalaya",
}

STATE_CODE_TO_NAME = {
    "MN": "Manipur",
    "MZ": "Mizoram",
    "ME": "Meghalaya",
}

# ── Main ─────────────────────────────────────────────────────────

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "portal_scraped_mn_mz_me.csv.gz")

    # Read scraped data
    print("Reading scraped data...")
    with gzip.open(csv_path, 'rt', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"  {len(rows)} rows loaded")

    # Group by state
    by_state = defaultdict(list)
    for r in rows:
        by_state[r['state_code']].append(r)

    for state_code, state_rows in by_state.items():
        state_dir = STATE_CODE_TO_DIR[state_code]
        state_name = STATE_CODE_TO_NAME[state_code]
        json_path = os.path.join(base_dir, state_dir, f"{state_dir}_complete.json")

        print(f"\n{'='*50}")
        print(f"  {state_name} ({state_code})")
        print(f"{'='*50}")

        # Load existing JSON
        with open(json_path) as f:
            data = json.load(f)

        existing_quarters = set(data.get('quarters', {}).keys())
        print(f"  Existing: {len(existing_quarters)} quarters")

        # Group scraped rows by (quarter_key, category, district)
        # Structure: {quarter_key: {category: {district: {metric: value}}}}
        portal_data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

        for r in state_rows:
            qkey = to_quarter_key(r['quarter'], r['fiscal_year'])
            category = REPORT_TO_CATEGORY.get(r['report_key'])
            if not category:
                continue
            district = title_case_district(r['district'])
            metric = r['metric']
            value = r['value']
            portal_data[qkey][category][district][metric] = value

        new_quarters = 0
        new_categories = 0
        updated_categories = 0

        for qkey in sorted(portal_data.keys()):
            # Ensure quarter exists
            if qkey not in data['quarters']:
                meta = quarter_metadata(qkey)
                data['quarters'][qkey] = {
                    "period": meta["period"],
                    "as_on_date": meta["as_on_date"],
                    "fy": meta["fy"],
                    "tables": {},
                }
                new_quarters += 1

            tables = data['quarters'][qkey].setdefault('tables', {})

            for category in sorted(portal_data[qkey].keys()):
                districts_data = portal_data[qkey][category]

                if not districts_data:
                    continue

                # Build fields list from all districts' metrics
                all_fields = set()
                for d_data in districts_data.values():
                    all_fields.update(d_data.keys())

                # Order fields: District first, then alphabetical
                fields = ["District"] + sorted(all_fields)

                # Build districts dict
                districts_dict = {}
                for district_name, metrics in sorted(districts_data.items()):
                    d_entry = {"District": district_name}
                    d_entry.update(metrics)
                    districts_dict[district_name] = d_entry

                is_new = category not in tables
                # Portal data replaces existing (it's cleaner)
                tables[category] = {
                    "fields": fields,
                    "num_districts": len(districts_dict),
                    "districts": districts_dict,
                }

                if is_new:
                    new_categories += 1
                else:
                    updated_categories += 1

        # Write updated JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        total_quarters = len(data['quarters'])
        total_cats = sum(len(data['quarters'][q].get('tables', {})) for q in data['quarters'])
        print(f"  New quarters added: {new_quarters}")
        print(f"  New categories added: {new_categories}")
        print(f"  Existing categories updated: {updated_categories}")
        print(f"  Total now: {total_quarters} quarters, {total_cats} category-quarter combos")

    print(f"\nDone! Portal data integrated into all 3 state JSON files.")


if __name__ == "__main__":
    main()
