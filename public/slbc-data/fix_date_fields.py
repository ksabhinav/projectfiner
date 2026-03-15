#!/usr/bin/env python3
"""
Fix date-embedded field names in SLBC data for Tripura and Assam.

Problem: Some states have PDF tables that embed time-series data horizontally —
the same table shows values for multiple dates as separate columns. This creates
80+ date-specific columns instead of consistent field names across quarters.

Fix: For each quarter, keep only the field matching the current quarter date,
rename it generically, and drop historical columns (they belong in their own quarters).

Affected:
  - Tripura: credit_deposit_ratio, branch_network, bc_coverage, pmjdy
  - Assam: flc_report
"""

import json
import csv
import re
from pathlib import Path
from collections import defaultdict

BASE = Path("/Users/abhinav/Downloads/projectfiner/public/slbc-data")

# ── Month parsing utilities ──────────────────────────────────────────

MONTH_TO_NUM = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

NUM_TO_MONTH = {
    3: 'March', 6: 'June', 9: 'September', 12: 'December',
}


def quarter_to_month_year(quarter_key):
    """Convert '2024-12' to (12, 2024)."""
    parts = quarter_key.split('-')
    return int(parts[1]), int(parts[0])


def parse_date_from_field(field_name):
    """
    Extract (month_num, year) from a field name containing a date.
    Handles: 'Dec 2024', 'December 2024', "Dec'24", "March'2017",
             'June2024', 'Mar23', 'Mar24', 'Sept 2024', etc.
    Returns (month_num, year) or None.
    """
    # Pattern 1: "Month Year" or "Month'Year" — e.g., "Dec 2024", "March'2017", "June2024"
    m = re.search(
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"[\s'\u2018\u2019\u0027]*(\d{2,4})",
        field_name, re.IGNORECASE
    )
    if m:
        month_str = m.group(1).lower().rstrip("'\u2018\u2019")
        year_str = m.group(2)
        month_num = MONTH_TO_NUM.get(month_str)
        if month_num:
            year = int(year_str)
            if year < 100:
                year += 2000
            return (month_num, year)
    return None


def date_matches_quarter(field_date, quarter_key):
    """Check if a parsed (month, year) matches a quarter key like '2024-12'."""
    q_month, q_year = quarter_to_month_year(quarter_key)
    return field_date == (q_month, q_year)


def is_most_recent_date(field_date, all_dates):
    """Check if field_date is the most recent among all_dates."""
    if not all_dates:
        return False
    max_date = max(all_dates, key=lambda d: (d[1], d[0]))
    return field_date == max_date


# ── Tripura credit_deposit_ratio ─────────────────────────────────────

def fix_tripura_cdr(table, quarter_key):
    """
    Fix credit_deposit_ratio fields for a single quarter.

    Rules:
    - 'CD Ratio [Date]' or 'C D Ratio [Date]' or bare '[Month Year]' →
      keep only the one matching current quarter → rename to 'CD Ratio'
    - 'CD Ratio Since [Date]' → drop (YoY change captures this)
    - 'CD Ratio Q-O-Q change' / 'Q-o-Q change' → rename to 'CD Ratio QoQ Change'
    - 'CD Ratio Y-O-Y change' / 'Y-o-Y change' → rename to 'CD Ratio YoY Change'
    - 'No. of Brs', 'Total Deposit', 'Total Advance', 'CD Ratio' → leave as-is
    """
    fields = table.get('fields', [])
    districts = table.get('districts', {})

    # Check if this quarter already has clean field names
    clean_names = {'CD Ratio', 'No. of Brs', 'Total Deposit', 'Total Advance'}
    if set(fields) <= clean_names | {'CD Ratio QoQ Change', 'CD Ratio YoY Change'}:
        return  # Already clean

    # If fields are exactly clean (like 2022-09, 2023-06, 2024-06), skip
    if all(f in clean_names for f in fields):
        return

    q_month, q_year = quarter_to_month_year(quarter_key)

    # Build rename map
    rename_map = {}  # old_field -> new_field or None (drop)

    # Collect all date-bearing CD Ratio fields to find which matches current quarter
    cd_ratio_date_fields = {}  # field_name -> (month, year)
    bare_date_fields = {}  # field_name -> (month, year) for bare date fields like "June 2024"

    for f in fields:
        # "CD Ratio Since ..." → drop
        if re.match(r'(?:CD|C D) Ratio Since\b', f, re.IGNORECASE):
            rename_map[f] = None
            continue

        # "CD Ratio Q-O-Q change" or "Q-o-Q change"
        if re.search(r'Q-?[oO]-?Q\s*change', f, re.IGNORECASE):
            rename_map[f] = 'CD Ratio QoQ Change'
            continue

        # "CD Ratio Y-O-Y change" or "Y-o-Y change"
        if re.search(r'Y-?[oO]-?Y\s*change', f, re.IGNORECASE):
            rename_map[f] = 'CD Ratio YoY Change'
            continue

        # "CD Ratio [Date]" or "C D Ratio [Date]"
        cd_match = re.match(r'(?:CD|C D) Ratio\s+(.+)', f, re.IGNORECASE)
        if cd_match:
            date_part = cd_match.group(1)
            # Skip "Since", "Q-O-Q", "Y-O-Y" (handled above)
            if re.match(r'(Since|Q-|Y-)', date_part, re.IGNORECASE):
                continue
            parsed = parse_date_from_field(date_part)
            if parsed:
                cd_ratio_date_fields[f] = parsed
                continue

        # Bare date fields like "June 2024", "Dec 2024", "March 2025"
        # These appear in later quarters (2025-03, 2025-06, 2025-09)
        parsed = parse_date_from_field(f)
        if parsed and f.strip() == f and not f.startswith('CD') and not f.startswith('C D'):
            # Check it's just a month/year, not something else
            # These are bare columns: "June 2024", "Sept 2024", "Dec 2024", "March 2025", etc.
            cleaned = re.sub(r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
                            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
                            r"Dec(?:ember)?)[\s']*\d{2,4}", '', f, flags=re.IGNORECASE).strip()
            if cleaned == '':
                bare_date_fields[f] = parsed
                continue

    # For CD Ratio date fields: keep only the one matching current quarter
    for f, date in cd_ratio_date_fields.items():
        if date_matches_quarter(date, quarter_key):
            rename_map[f] = 'CD Ratio'
        else:
            rename_map[f] = None  # Drop historical

    # For bare date fields: keep only the one matching current quarter
    for f, date in bare_date_fields.items():
        if date_matches_quarter(date, quarter_key):
            rename_map[f] = 'CD Ratio'
        else:
            rename_map[f] = None  # Drop historical

    # Apply renames
    _apply_renames(table, rename_map)


# ── Tripura branch_network ───────────────────────────────────────────

def fix_tripura_branch_network(table, quarter_key):
    """
    Fix branch_network fields for a single quarter.

    Rules:
    - 'No. of ATM as on [Date]' → keep most recent → 'No. of ATM'
    - 'No. of Branches as on [Date]' → keep most recent → 'No. of Branches'
    - 'ATM per one lakh population as on [Date] (Census 2011)' → 'ATM Per Lakh Population'
    - 'Branch per one lakh population as on [Date] (Census 2011)' → 'Branches Per Lakh Population'
    - 'Population (Census 2011)' → 'Population'
    - 'S.No.' → drop
    - 'No of Gp's/Vc's' → keep as-is
    """
    fields = table.get('fields', [])
    rename_map = {}

    # Group ATM and Branches fields by their dates
    atm_fields = {}  # field -> (month, year)
    branch_fields = {}

    for f in fields:
        if f == 'S.No.':
            rename_map[f] = None
            continue
        if f == 'Population (Census 2011)':
            rename_map[f] = 'Population'
            continue

        # ATM per lakh
        if re.match(r'ATM per one lakh population', f, re.IGNORECASE):
            rename_map[f] = 'ATM Per Lakh Population'
            continue

        # Branch per lakh
        if re.match(r'Branch per one lakh population', f, re.IGNORECASE):
            rename_map[f] = 'Branches Per Lakh Population'
            continue

        # No. of ATM as on [Date]
        m = re.match(r'No\.\s*of\s+ATM\s+as\s+on\s+(.+)', f, re.IGNORECASE)
        if m:
            parsed = parse_date_from_field(m.group(1))
            if parsed:
                atm_fields[f] = parsed
            continue

        # No. of Branches as on [Date]
        m = re.match(r'No\.\s*of\s+Branch(?:es)?\s+as\s+on\s+(.+)', f, re.IGNORECASE)
        if m:
            parsed = parse_date_from_field(m.group(1))
            if parsed:
                branch_fields[f] = parsed
            continue

    # Keep only most recent ATM date
    if atm_fields:
        all_dates = list(atm_fields.values())
        for f, date in atm_fields.items():
            if is_most_recent_date(date, all_dates):
                rename_map[f] = 'No. of ATM'
            else:
                rename_map[f] = None

    # Keep only most recent Branches date
    if branch_fields:
        all_dates = list(branch_fields.values())
        for f, date in branch_fields.items():
            if is_most_recent_date(date, all_dates):
                rename_map[f] = 'No. of Branches'
            else:
                rename_map[f] = None

    _apply_renames(table, rename_map)


# ── Tripura bc_coverage ──────────────────────────────────────────────

def fix_tripura_bc_coverage(table, quarter_key):
    """
    Fix bc_coverage fields for a single quarter.

    Rules:
    - 'No. of BC/CSP as on [Date]' → keep most recent → 'No. of BC/CSP'
    - 'BC/CSP per one lakh population as on [Date] (Census 2011)' → 'BC/CSP Per Lakh Population'
    - 'Population (Census 2011)' → 'Population'
    """
    fields = table.get('fields', [])
    rename_map = {}

    bc_fields = {}  # field -> (month, year)

    for f in fields:
        if f == 'Population (Census 2011)':
            rename_map[f] = 'Population'
            continue

        # BC/CSP per lakh
        if re.match(r'BC/CSP per one lakh population', f, re.IGNORECASE):
            rename_map[f] = 'BC/CSP Per Lakh Population'
            continue

        # No. of BC/CSP as on [Date]
        m = re.match(r'No\.\s*of\s+BC/CSP\s+as\s+on\s+(.+)', f, re.IGNORECASE)
        if m:
            parsed = parse_date_from_field(m.group(1))
            if parsed:
                bc_fields[f] = parsed
            continue

    # Keep only most recent BC/CSP date
    if bc_fields:
        all_dates = list(bc_fields.values())
        for f, date in bc_fields.items():
            if is_most_recent_date(date, all_dates):
                rename_map[f] = 'No. of BC/CSP'
            else:
                rename_map[f] = None

    _apply_renames(table, rename_map)


# ── Tripura pmjdy ────────────────────────────────────────────────────

def fix_tripura_pmjdy(table, quarter_key):
    """
    Fix pmjdy fields for a single quarter.

    Rules:
    - 'No. of PMJDY accounts as on [Date]' → keep most recent → 'No. of PMJDY Accounts'
    - 'No. of Women PMJDY accounts as on [Date]' → keep most recent → 'No. of Women PMJDY Accounts'
    - 'PMJDY accounts per one lakh population as on [Date] (Census 2011)' → 'PMJDY Accounts Per Lakh Population'
    - 'Women PMJDY accounts per one lakh population as on [Date] (Census 2011)' → 'Women PMJDY Accounts Per Lakh Population'
    - 'Population (Census 2011)' → 'Population'
    - 'Women Population (Census 2011)' → 'Women Population'
    - 'PMJDY', 'PMJJBY', 'PMSBY' → leave as-is
    """
    fields = table.get('fields', [])
    rename_map = {}

    pmjdy_fields = {}  # field -> (month, year)
    women_pmjdy_fields = {}

    for f in fields:
        if f == 'Population (Census 2011)':
            rename_map[f] = 'Population'
            continue
        if f == 'Women Population (Census 2011)':
            rename_map[f] = 'Women Population'
            continue

        # PMJDY accounts per lakh
        if re.match(r'PMJDY accounts per one lakh population', f, re.IGNORECASE):
            rename_map[f] = 'PMJDY Accounts Per Lakh Population'
            continue

        # Women PMJDY accounts per lakh
        if re.match(r'Women PMJDY accounts per one lakh population', f, re.IGNORECASE):
            rename_map[f] = 'Women PMJDY Accounts Per Lakh Population'
            continue

        # No. of Women PMJDY accounts as on [Date]
        m = re.match(r'No\.\s*of\s+Women\s+PMJDY\s+accounts?\s+as\s+on\s+(.+)', f, re.IGNORECASE)
        if m:
            parsed = parse_date_from_field(m.group(1))
            if parsed:
                women_pmjdy_fields[f] = parsed
            continue

        # No. of PMJDY accounts as on [Date]
        m = re.match(r'No\.\s*of\s+PMJDY\s+accounts?\s+as\s+on\s+(.+)', f, re.IGNORECASE)
        if m:
            parsed = parse_date_from_field(m.group(1))
            if parsed:
                pmjdy_fields[f] = parsed
            continue

    # Keep only most recent PMJDY date
    if pmjdy_fields:
        all_dates = list(pmjdy_fields.values())
        for f, date in pmjdy_fields.items():
            if is_most_recent_date(date, all_dates):
                rename_map[f] = 'No. of PMJDY Accounts'
            else:
                rename_map[f] = None

    # Keep only most recent Women PMJDY date
    if women_pmjdy_fields:
        all_dates = list(women_pmjdy_fields.values())
        for f, date in women_pmjdy_fields.items():
            if is_most_recent_date(date, all_dates):
                rename_map[f] = 'No. of Women PMJDY Accounts'
            else:
                rename_map[f] = None

    _apply_renames(table, rename_map)


# ── Assam flc_report ─────────────────────────────────────────────────

def parse_assam_flc_quarter(field_name):
    """
    Parse the quarter date from an Assam FLC field name.

    Examples:
    - "No. of camps conducted during the Dec'22 Quarter of FY(2022-23)" → (12, 2022)
    - "No. of camps conducted during the June'23 Quarter of FY(2023-24)" → (6, 2023)
    - "No. of camps conducted during the Mar23 Quarter of FY(2022-23)" → (3, 2023)
    - "No. of camps conducted during the Sept'24 Quarter of FY(2024-25)" → (9, 2024)
    - "Total No. of Camps during the FY(2022-23)" → returns FY tuple
    """
    # Match quarter-specific pattern
    m = re.search(
        r"(?:the\s+)(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"['\s]*(\d{2,4})\s+Quarter",
        field_name, re.IGNORECASE
    )
    if m:
        month_str = m.group(1).lower()
        year_str = m.group(2)
        month_num = MONTH_TO_NUM.get(month_str)
        if month_num:
            year = int(year_str)
            if year < 100:
                year += 2000
            return ('quarter', month_num, year)

    # Match FY total pattern: "Total No. of Camps during the FY(2022-23)" or "FY(2022- 23)"
    m = re.search(r'FY\((\d{4})-\s*(\d{2,4})\)', field_name)
    if m:
        fy_start = int(m.group(1))
        return ('fy_total', fy_start)

    return None


def quarter_key_to_assam_quarter(quarter_key):
    """Convert quarter key '2022-12' to (month, year) for Assam matching."""
    month, year = quarter_to_month_year(quarter_key)
    return (month, year)


def quarter_in_fy(quarter_key, fy_start):
    """Check if a quarter falls within a given FY starting year."""
    month, year = quarter_to_month_year(quarter_key)
    # FY 2022-23 runs from April 2022 to March 2023
    if month >= 4:  # Apr-Dec
        return year == fy_start
    else:  # Jan-Mar
        return year == fy_start + 1


def fix_assam_flc_report(table, quarter_key):
    """
    Fix flc_report fields for a single Assam quarter.

    Rules:
    - 'No. of camps conducted during the [Month'YY] Quarter of FY(YYYY-YY)'
      → Keep only the one matching current quarter → 'No. of Camps Conducted (Quarter)'
      → Rename non-matching to track which quarter they represent and decide:
        - If it matches the current quarter_key → 'No. of Camps Conducted (Quarter)'
        - If it's a different quarter within same FY → drop or rename generically
    - 'Total No. of Camps during the FY(YYYY-YY)' → 'Total No. of Camps (FY)'
    - 'No of rural branches in district' → keep as-is
    """
    fields = table.get('fields', [])
    rename_map = {}

    q_month, q_year = quarter_to_month_year(quarter_key)

    # Determine which FY quarter names refer to the current quarter
    # All quarters in the same period share the same FY table,
    # so each has fields for all 4 quarters of that FY.
    # We need to identify which field matches our current quarter.

    quarter_fields = {}  # field -> parsed info

    for f in fields:
        if f == 'No of rural branches in district':
            continue  # Keep as-is

        parsed = parse_assam_flc_quarter(f)
        if parsed is None:
            continue

        if parsed[0] == 'quarter':
            _, f_month, f_year = parsed
            if f_month == q_month and f_year == q_year:
                rename_map[f] = 'No. of Camps Conducted (Quarter)'
            else:
                # Determine which quarter label this is
                # Map to generic name based on quarter position
                if f_month in (4, 5, 6):
                    rename_map[f] = 'No. of Camps Conducted (Q1 Apr-Jun)'
                elif f_month in (7, 8, 9):
                    rename_map[f] = 'No. of Camps Conducted (Q2 Jul-Sep)'
                elif f_month in (10, 11, 12):
                    rename_map[f] = 'No. of Camps Conducted (Q3 Oct-Dec)'
                elif f_month in (1, 2, 3):
                    rename_map[f] = 'No. of Camps Conducted (Q4 Jan-Mar)'

        elif parsed[0] == 'fy_total':
            rename_map[f] = 'Total No. of Camps (FY)'

    _apply_renames(table, rename_map)


# ── Common rename/drop utility ───────────────────────────────────────

def _apply_renames(table, rename_map):
    """
    Apply a rename_map to a table's fields and district data.
    rename_map: {old_field: new_field_or_None}
    None means drop the field.
    """
    if not rename_map:
        return

    fields = table.get('fields', [])
    districts = table.get('districts', {})

    # Build new fields list
    new_fields = []
    seen = set()
    for f in fields:
        new_f = rename_map.get(f, f)  # Default: keep as-is
        if new_f is None:
            continue  # Drop
        if new_f not in seen:
            new_fields.append(new_f)
            seen.add(new_f)

    # Rename in district data
    for dist_name, dist_data in districts.items():
        new_data = {}
        for old_f in list(dist_data.keys()):
            new_f = rename_map.get(old_f, old_f)
            if new_f is None:
                continue  # Drop
            val = dist_data[old_f]
            if new_f in new_data:
                # Merge: prefer non-empty value
                existing = new_data[new_f]
                if (existing is None or existing == "" or existing == "0") and val and val != "" and val != "0":
                    new_data[new_f] = val
            else:
                new_data[new_f] = val
        districts[dist_name] = new_data

    # Ensure fields list includes any fields from district data not yet seen
    for dist_data in districts.values():
        for f in dist_data.keys():
            if f not in seen:
                new_fields.append(f)
                seen.add(f)

    table['fields'] = new_fields
    table['districts'] = districts


# ── Timeseries / CSV regeneration (reuse from normalize_fields_v2) ───

def normalize_timeseries_key(key):
    """Normalize a timeseries column key."""
    key = re.sub(r'\.+$', '', key)
    key = re.sub(r'_ac$', '_a/c', key)
    key = re.sub(r'_acs$', '_a/c', key)
    key = re.sub(r'_a/cs$', '_a/c', key)
    key = re.sub(r'_amount$', '_amt', key)
    key = re.sub(r'_amt\.$', '_amt', key)
    key = re.sub(r'_nos?\.?s?\.?$', '_no.', key)
    key = re.sub(r'_no\.s$', '_no.', key)
    if key.endswith('_no'):
        key = key + '.'
    key = re.sub(r'semi[\s_-]+urban', 'semi-urban', key)
    key = re.sub(r'_deposits_', '_deposit_', key)
    key = re.sub(r'_deposits$', '_deposit', key)
    key = re.sub(r'_advances_', '_advance_', key)
    key = re.sub(r'_advances$', '_advance', key)
    key = re.sub(r'_ratios_', '_ratio_', key)
    key = re.sub(r'_ratios$', '_ratio', key)
    key = re.sub(r'_branches_', '_branch_', key)
    key = re.sub(r'_branches$', '_branch', key)
    key = re.sub(r'_atms_', '_atm_', key)
    key = re.sub(r'_atms$', '_atm', key)
    key = re.sub(r'_others_', '_other_', key)
    key = re.sub(r'_others$', '_other', key)
    key = re.sub(r'_csps_', '_csp_', key)
    key = re.sub(r'_csps$', '_csp', key)
    key = re.sub(r'_bcs_', '_bc_', key)
    key = re.sub(r'_bcs$', '_bc', key)
    key = re.sub(r'_br\(s\)', '_br', key)
    key = re.sub(r'_br\.$', '_br', key)
    key = re.sub(r'renew-?\s*able', 'renewable', key)
    key = re.sub(r'_+', '_', key)
    key = key.strip('_')
    return key


def regenerate_quarterly_csvs(data, quarterly_dir):
    """Regenerate all quarterly CSVs from the JSON."""
    quarters = data.get("quarters", {})
    for qname, quarter in quarters.items():
        folder_name = qname
        if not re.match(r'^\d{4}-\d{2}$', folder_name):
            as_on = quarter.get("as_on_date", "")
            if as_on:
                parts = as_on.split("-")
                if len(parts) == 3:
                    folder_name = f"{parts[2]}-{parts[1]}"
            if not re.match(r'^\d{4}-\d{2}$', folder_name):
                continue

        folder_path = quarterly_dir / folder_name
        if folder_path.exists():
            for f in folder_path.glob("*.csv"):
                f.unlink()
        else:
            folder_path.mkdir(parents=True, exist_ok=True)

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


def regenerate_timeseries(data, state_dir, state_slug):
    """Regenerate timeseries CSV and JSON from data."""
    all_records = []
    all_field_keys = set()
    quarters = data.get("quarters", {})

    def make_ts_key(tname, fld):
        key = f"{tname}__{fld}"
        norm_key = re.sub(r'[^a-z0-9_/()&.,%]+', '_', key.lower().replace(' ', '_'))
        norm_key = re.sub(r'_+', '_', norm_key).strip('_')
        norm_key = normalize_timeseries_key(norm_key)
        return norm_key

    for qname, q in quarters.items():
        for tname, table in q.get("tables", {}).items():
            for dist_name, fields in table.get("districts", {}).items():
                for fld in fields.keys():
                    all_field_keys.add(make_ts_key(tname, fld))

    sorted_fields = sorted(all_field_keys)
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
                        "district": dist_name, "period": period,
                        "as_on_date": as_on, "fy": fy,
                    }
                for fld, val in fields.items():
                    norm_key = make_ts_key(tname, fld)
                    existing = quarter_districts[dist_name].get(norm_key)
                    if existing is None or existing == "" or existing == "0":
                        quarter_districts[dist_name][norm_key] = val
                    elif val and val != "" and val != "0" and (existing is None or existing == ""):
                        quarter_districts[dist_name][norm_key] = val

        for dist_name, record in sorted(quarter_districts.items()):
            all_records.append(record)
        if period not in periods_data:
            periods_data[period] = {
                "period": period, "num_districts": len(quarter_districts), "districts": [],
            }
        periods_data[period]["districts"] = [
            quarter_districts[d] for d in sorted(quarter_districts.keys())
        ]

    csv_path = state_dir / f"{state_slug}_fi_timeseries.csv"
    csv_columns = ["district", "period", "as_on_date", "fy"] + sorted_fields
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction='ignore')
        writer.writeheader()
        for record in all_records:
            writer.writerow(record)

    json_path = state_dir / f"{state_slug}_fi_timeseries.json"
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

    return len(sorted_fields)


# ── Main ─────────────────────────────────────────────────────────────

def process_tripura():
    """Process Tripura: fix date-embedded fields."""
    state_dir = BASE / "tripura"
    json_path = state_dir / "tripura_complete.json"

    with open(json_path) as f:
        data = json.load(f)

    quarters = data['quarters']
    stats = defaultdict(int)

    for qk in sorted(quarters.keys()):
        q = quarters[qk]
        tables = q.get('tables', {})

        if 'credit_deposit_ratio' in tables:
            before = len(tables['credit_deposit_ratio'].get('fields', []))
            fix_tripura_cdr(tables['credit_deposit_ratio'], qk)
            after = len(tables['credit_deposit_ratio'].get('fields', []))
            if before != after:
                stats['cdr_fields_removed'] += before - after
                stats['cdr_quarters_fixed'] += 1

        if 'branch_network' in tables:
            before = len(tables['branch_network'].get('fields', []))
            fix_tripura_branch_network(tables['branch_network'], qk)
            after = len(tables['branch_network'].get('fields', []))
            if before != after:
                stats['bn_fields_removed'] += before - after
                stats['bn_quarters_fixed'] += 1

        if 'bc_coverage' in tables:
            before = len(tables['bc_coverage'].get('fields', []))
            fix_tripura_bc_coverage(tables['bc_coverage'], qk)
            after = len(tables['bc_coverage'].get('fields', []))
            if before != after:
                stats['bc_fields_removed'] += before - after
                stats['bc_quarters_fixed'] += 1

        if 'pmjdy' in tables:
            before = len(tables['pmjdy'].get('fields', []))
            fix_tripura_pmjdy(tables['pmjdy'], qk)
            after = len(tables['pmjdy'].get('fields', []))
            if before != after:
                stats['pmjdy_fields_removed'] += before - after
                stats['pmjdy_quarters_fixed'] += 1

    # Write back
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Regenerate CSVs and timeseries
    regenerate_quarterly_csvs(data, state_dir / "quarterly")
    ts_cols = regenerate_timeseries(data, state_dir, "tripura")

    return stats, ts_cols


def process_assam():
    """Process Assam: fix date-embedded fields in flc_report."""
    state_dir = BASE / "assam"
    json_path = state_dir / "assam_complete.json"

    with open(json_path) as f:
        data = json.load(f)

    quarters = data['quarters']
    stats = defaultdict(int)

    for qk in sorted(quarters.keys()):
        q = quarters[qk]
        tables = q.get('tables', {})

        if 'flc_report' in tables:
            before_fields = tables['flc_report'].get('fields', [])[:]
            fix_assam_flc_report(tables['flc_report'], qk)
            after_fields = tables['flc_report'].get('fields', [])
            renamed = sum(1 for b, a in zip(before_fields, after_fields) if b != a)
            if renamed or len(before_fields) != len(after_fields):
                stats['flc_fields_renamed'] += renamed
                stats['flc_quarters_fixed'] += 1

    # Write back
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Regenerate CSVs and timeseries
    regenerate_quarterly_csvs(data, state_dir / "quarterly")
    ts_cols = regenerate_timeseries(data, state_dir, "assam")

    return stats, ts_cols


def main():
    print("=" * 70)
    print("FIX DATE-EMBEDDED FIELD NAMES")
    print("=" * 70)

    # Record BEFORE column counts
    print("\n--- BEFORE ---")
    for state, slug in [('tripura', 'tripura'), ('assam', 'assam')]:
        csv_path = BASE / state / f"{slug}_fi_timeseries.csv"
        if csv_path.exists():
            with open(csv_path) as f:
                header = next(csv.reader(f))
            cdr_cols = [c for c in header if 'credit_deposit_ratio' in c]
            bn_cols = [c for c in header if 'branch_network' in c]
            bc_cols = [c for c in header if 'bc_coverage' in c]
            pmjdy_cols = [c for c in header if 'pmjdy' in c]
            flc_cols = [c for c in header if 'flc_report' in c]
            print(f"  {state}: {len(header)} total columns")
            print(f"    credit_deposit_ratio: {len(cdr_cols)}")
            print(f"    branch_network: {len(bn_cols)}")
            print(f"    bc_coverage: {len(bc_cols)}")
            print(f"    pmjdy: {len(pmjdy_cols)}")
            print(f"    flc_report: {len(flc_cols)}")

    # Process
    print("\n--- Processing Tripura ---")
    tri_stats, tri_cols = process_tripura()
    for k, v in sorted(tri_stats.items()):
        print(f"  {k}: {v}")

    print("\n--- Processing Assam ---")
    asm_stats, asm_cols = process_assam()
    for k, v in sorted(asm_stats.items()):
        print(f"  {k}: {v}")

    # Record AFTER column counts
    print("\n--- AFTER ---")
    for state, slug in [('tripura', 'tripura'), ('assam', 'assam')]:
        csv_path = BASE / state / f"{slug}_fi_timeseries.csv"
        if csv_path.exists():
            with open(csv_path) as f:
                header = next(csv.reader(f))
            cdr_cols = [c for c in header if 'credit_deposit_ratio' in c]
            bn_cols = [c for c in header if 'branch_network' in c]
            bc_cols = [c for c in header if 'bc_coverage' in c]
            pmjdy_cols = [c for c in header if 'pmjdy' in c]
            flc_cols = [c for c in header if 'flc_report' in c]
            print(f"  {state}: {len(header)} total columns")
            print(f"    credit_deposit_ratio: {len(cdr_cols)}")
            print(f"    branch_network: {len(bn_cols)}")
            print(f"    bc_coverage: {len(bc_cols)}")
            print(f"    pmjdy: {len(pmjdy_cols)}")
            print(f"    flc_report: {len(flc_cols)}")

    # Verification: check field consistency across quarters
    print("\n--- VERIFICATION ---")

    # Tripura credit_deposit_ratio
    with open(BASE / "tripura" / "tripura_complete.json") as f:
        data = json.load(f)
    print("\n  Tripura credit_deposit_ratio fields per quarter:")
    for qk in sorted(data['quarters'].keys()):
        qv = data['quarters'][qk]
        if 'credit_deposit_ratio' in qv.get('tables', {}):
            fields = qv['tables']['credit_deposit_ratio'].get('fields', [])
            print(f"    {qk}: {fields}")

    print("\n  Tripura branch_network fields per quarter:")
    for qk in sorted(data['quarters'].keys()):
        qv = data['quarters'][qk]
        if 'branch_network' in qv.get('tables', {}):
            fields = qv['tables']['branch_network'].get('fields', [])
            print(f"    {qk}: {fields}")

    print("\n  Tripura bc_coverage fields per quarter:")
    for qk in sorted(data['quarters'].keys()):
        qv = data['quarters'][qk]
        if 'bc_coverage' in qv.get('tables', {}):
            fields = qv['tables']['bc_coverage'].get('fields', [])
            print(f"    {qk}: {fields}")

    print("\n  Tripura pmjdy fields per quarter:")
    for qk in sorted(data['quarters'].keys()):
        qv = data['quarters'][qk]
        if 'pmjdy' in qv.get('tables', {}):
            fields = qv['tables']['pmjdy'].get('fields', [])
            print(f"    {qk}: {fields}")

    # Assam flc_report
    with open(BASE / "assam" / "assam_complete.json") as f:
        data = json.load(f)
    print("\n  Assam flc_report fields per quarter:")
    for qk in sorted(data['quarters'].keys()):
        qv = data['quarters'][qk]
        if 'flc_report' in qv.get('tables', {}):
            fields = qv['tables']['flc_report'].get('fields', [])
            print(f"    {qk}: {fields}")

    print(f"\n{'='*70}")
    print("DONE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
