#!/usr/bin/env python3
"""
Comprehensive data quality fix for all 8 NE states' SLBC data.
Fixes:
1. Comma-formatted numbers
2. NPA % vs Amount disambiguation
3. Empty timeseries columns removal
4. Long field name shortening
5. Garbled concatenated field names
6. Bank-name columns in uncategorized tables
Then regenerates all quarterly CSVs, timeseries CSVs and JSONs.
"""

import json
import csv
import os
import re
import shutil
from pathlib import Path
from collections import defaultdict, OrderedDict

BASE = Path("/Users/abhinav/Downloads/projectfiner/public/slbc-data")

STATES = [
    "arunachal-pradesh", "assam", "manipur", "meghalaya",
    "mizoram", "nagaland", "sikkim", "tripura",
]

STATE_SLUGS = {
    "arunachal-pradesh": "arunachal_pradesh",
    "assam": "assam",
    "manipur": "manipur",
    "meghalaya": "meghalaya",
    "mizoram": "mizoram",
    "nagaland": "nagaland",
    "sikkim": "sikkim",
    "tripura": "tripura",
}

# ── Bank name patterns for Issue #6 ──
BANK_NAMES = {
    'SBI', 'BOB', 'BOI', 'PNB', 'HDFC', 'ICICI', 'CANARA', 'UCO', 'AXIS',
    'BANDHAN', 'IDBI', 'IOB', 'UNION', 'CENTRAL', 'INDIAN', 'BARODA',
    'CBI', 'CAN', 'IND', 'APRB', 'NESFB', 'APSCAB', 'RBI', 'NABARD',
    'YES', 'KOTAK', 'FEDERAL', 'SOUTH', 'KARNATAKA', 'ANDHRA', 'ALLAHABAD',
    'SYNDICATE', 'VIJAYA', 'DENA', 'ORIENTAL', 'CORPORATION', 'UNITED',
    'NAINITAL', 'FINO', 'PAYTM', 'AIRTEL', 'UJJIVAN', 'EQUITAS',
    'SURYODAY', 'ESAF', 'AU', 'RBL', 'DCB', 'KARUR', 'TMB', 'CSB',
    'LAKSHMI', 'DHANLAXMI', 'JAMMU', 'JK', 'SAPTAGIRI', 'UTKARSH',
}

# ── Comma number pattern (including Indian lakh format) ──
COMMA_NUM_RE = re.compile(r'^-?[\d,]+\.?\d*$')

# ── Stats tracking ──
stats = defaultdict(lambda: defaultdict(int))

# ═══════════════════════════════════════════════════════════════════════════════
# Issue #1: Fix comma-formatted numbers
# ═══════════════════════════════════════════════════════════════════════════════
def fix_comma_numbers(value):
    """Strip commas from number strings like '1,234' or '1,08,114'."""
    if isinstance(value, str) and ',' in value and COMMA_NUM_RE.match(value.strip()):
        return value.replace(',', '')
    return value


# ═══════════════════════════════════════════════════════════════════════════════
# Issue #5: Fix garbled concatenated field names
# ═══════════════════════════════════════════════════════════════════════════════
GARBLED_FIXES = {
    # Known joined words
    r'Noof\b': 'No. of',
    r'Noofvillages': 'No. of villages',
    r'Noofaccounts': 'No. of accounts',
    r'Noofcases': 'No. of cases',
    r'Noofbeneficiaries': 'No. of beneficiaries',
    r'Noofbranches': 'No. of branches',
    r'Bankselected': 'Bank selected',
    r'Coveredby': 'Covered by',
    r'Outof\b': 'Out of',
    r'eligiblecases': 'Eligible cases',
    r'Roadmapprepared': 'Roadmap prepared',
    r'Nameof\b': 'Name of',
    r'Populationbetween': 'Population between',
    r'ofvillages': 'of villages',
    r'ofhouseholds?': 'of households',
    r'ofhouseholdscovered': 'of households covered',
    r'openingbankaccounts': 'opening bank accounts',
    r'inallottedvillages': 'in allotted villages',
    r'bankingoutlet': 'banking outlet',
    r'bankingoutletopeneduptotheendofthereporting': 'banking outlet opened upto end of reporting',
    r'villageswhere': 'villages where',
    r'wherebankingoutlet': 'where banking outlet',
    r'selectedfor': 'selected for',
    r'forallotment': 'for allotment',
    r'forallotmentofvillageswith': 'for allotment of villages with',
    r'ofvillageswith': 'of villages with',
    r'Bankbranch': 'Bank branch',
    r'IInnddeeppeennddeenntt': 'Independent',
    r'Sch\.\s*Comm\.': 'Sch. Comm.',
    r'foranimalhusbandary': 'for animal husbandary',
    r'Fishriesissuedduringquarter': 'Fishries issued during quarter',
    r'husbandaryissued': 'husbandary issued',
    r'issuedduringquarter': 'issued during quarter',
    r'preparedfor': 'prepared for',
    r'lessthan\b': 'less than',
    r'forlessthan': 'for less than',
    r'ofaccountsopened': 'of accounts opened',
    r'byopeningbankaccounts': 'by opening bank accounts',
    r'ofhouseholdscoveredbyopeningbankaccounts': 'of households covered by opening bank accounts',
    r'enabledbankingoutlet': 'enabled banking outlet',
    r'Cbsenabledbankingoutlet': 'CBS enabled banking outlet',
    r'(?<=[a-z])(?=[A-Z])': ' ',  # camelCase split - applied last
}

def fix_garbled_name(name):
    """Fix garbled concatenated field names."""
    if not name or not isinstance(name, str):
        return name
    s = name

    # Apply specific fixes first (longer patterns first to avoid partial matches)
    specific_fixes = sorted(
        [(k, v) for k, v in GARBLED_FIXES.items() if k != r'(?<=[a-z])(?=[A-Z])'],
        key=lambda x: len(x[0]), reverse=True
    )
    for pattern, replacement in specific_fixes:
        s = re.sub(pattern, replacement, s)

    # Insert space between lowercase-uppercase joins (camelCase split)
    # But not for known abbreviations
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)

    # Fix remaining common concatenations
    # lowercase followed by "No." with no space
    s = re.sub(r'([a-z])(No\.)', r'\1 \2', s)

    # Clean up multiple spaces
    s = re.sub(r'\s+', ' ', s).strip()

    return s


# ═══════════════════════════════════════════════════════════════════════════════
# Issue #4: Shorten long field names (>60 chars)
# ═══════════════════════════════════════════════════════════════════════════════
# Specific mappings for known long names
LONG_NAME_MAP = {
    "No. of Literacy Camps undertaken during the quarter as per Rbi guidelines using standardized financial literacy material of Rbi":
        "Literacy Camps (RBI Std Material)",
    "Eligible Operative Current/Business Accounts covered with at least one of facilities - Net Banking/Pos/QR/Mobile Banking No. of accounts covered":
        "Digital Coverage Current A/C",
    "eligible operative current/business accounts covered with at least one of facilities net banking/pos/qr/mobile banking no. of accounts covered":
        "Digital Coverage Current A/C",
    "Eligible Operative Current/Business Accounts covered with at least one of facilities Net Banking/Pos/QR/Mobile Banking No. of accounts covered":
        "Digital Coverage Current A/C",
    "Name of Sch. Comm. Bank selected for allotment of villages with < 2000 population":
        "Bank Allotted Villages <2000 Pop.",
    "Nameof Sch. Comm. Bankselectedforallotmentofvillageswith < 2000 population":
        "Bank Allotted Villages <2000 Pop.",
    "Name of Sch. Comm. Bank selected for allotment of villages with 2000 population":
        "Bank Allotted Villages >2000 Pop.",
    "No. of KCC for animal husbandary issued during quarter (Including renewal)":
        "KCC Animal Husbandry Issued (Incl Renewal)",
    "No. of KCC for Fishries issued during quarter (including renewal)":
        "KCC Fisheries Issued (Incl Renewal)",
    "No. of KCC foranimalhusbandaryissuedduringquarter (Including renewal)":
        "KCC Animal Husbandry Issued (Incl Renewal)",
    "No. of KCC for Fishriesissuedduringquarter (including renewal)":
        "KCC Fisheries Issued (Incl Renewal)",
    "No. and Date of Latest Letter sent to Dc for Issues related to Premises, Communication, Network etc":
        "Latest Letter to DC (Premises/Network)",
    "KCC for animal husbandary Outstanding Renewal amount. as on end of current quarter (Rs. in Lakhs)":
        "KCC AH Outstanding Renewal Amt",
    "KCC for Animal Husbandry NPA Amt at the end of current quarter (Since Inception) (Rs. in Lakhs)":
        "KCC AH NPA Amt (Since Inception)",
    "KCC for Animal Husbandry Total no. of Active KCC for animal husbandary (Since Inception)":
        "KCC AH Active Total (Since Inception)",
    "KCC for Fisheries NPA Amt at the end of current quarter (Since Inception) (Rs. in Lakhs)":
        "KCC Fisheries NPA Amt (Since Inception)",
    "Crops KCC NPA Amt at the end of current quarter (Since Inception) (Rs. in Lakhs)":
        "Crops KCC NPA Amt (Since Inception)",
    "KCC for Fishries No. of KCC Renewed During the quarter Amount (Rs. in Lakhs)":
        "KCC Fisheries Renewed Amt",
    "KCC for Fishries New KCC Amount disbursed during quarter (Rs. in Lakhs)":
        "KCC Fisheries New Disbursed Amt",
    "KCC for Fishries Total no. of Active KCC for fishries (Since Inception)":
        "KCC Fisheries Active Total (Since Inception)",
    "No. ofhouseholdscoveredbyopeningbankaccounts (inallottedvillages/area)":
        "Households Covered (Allotted Villages)",
    "No. of households covered by opening bank accounts (in allotted villages/area)":
        "Households Covered (Allotted Villages)",
    "No. ofhouseholdscoveredbyopeningbankaccounts (No. ofaccountsopened)":
        "Households Covered (Accounts Opened)",
    "No. of households covered by opening bank accounts (No. of accounts opened)":
        "Households Covered (Accounts Opened)",
    "Out of Roadmap prepared for less than 2000, No. of villages where banking outlet opened upto end of reporting Quarter":
        "Roadmap <2000 Villages with Banking Outlet",
    "Outof Roadmappreparedforlessthan 2000, No. ofvillageswherebankingoutletopeneduptotheendofthereporting Quarter":
        "Roadmap <2000 Villages with Banking Outlet",
    "Premises (Bankbranch, Ldm office, RSETI, IInnddeeppeennddeenntt))":
        "Premises (Branch/LDM/RSETI/Independent)",
    "Premises (Bank branch, Ldm office, RSETI, Independent))":
        "Premises (Branch/LDM/RSETI/Independent)",
    "Total No. of Operative Sb Accounts covered with at least one of the facilities - Debit/RuPay cards/Net Banking/Mobile Banking/UPI/USSD":
        "Digital Coverage SB A/C",
    "Total No. of Operative Current Accounts covered with at least one of facilities - Net Banking/Pos/QR etc":
        "Digital Coverage Current A/C",
    "Status of applications sanctioned under Pm Kisan KCC Saturation Scheme (cumulative since inception) Status of KCC applications Sanctioned":
        "PM Kisan KCC Sanctioned (Cumulative)",
    "Cummulative - Appplicant (i) not tracable (ii) Unwilling to avail (iii) Unaware about the submission of application":
        "Cumulative Applicants Not Traceable/Unwilling",
    "No. of Operative Current/Business Accounts ineligible for digital coveragee as per bank's Board approved policies":
        "Current A/C Ineligible for Digital Coverage",
    "Out of Persons participated, number of persons already having bank A/C at the time of attending the camp":
        "Camp Participants Already Having A/C",
    "Eligible Operative Current/Business Accounts covered with Mobile Banking etc. No. of accounts covered":
        "Current A/C Mobile Banking Coverage",
    "Eligible Operative Current/Business Accounts covered through Net Banking No. of accounts covered":
        "Current A/C Net Banking Coverage",
    "Eligible Operative Current/Business Accounts covered with Pos/QR No. of accounts covered":
        "Current A/C POS/QR Coverage",
    "Out of persons participated, no. of persons opened bank A/C after attending the camp":
        "Camp Participants Opened A/C After",
    "Revised target for additional ATM required to be installed in Phase I*":
        "Revised Target Addl ATM Phase I",
    "No. of KCC for animal husbandaryissued during quarter (Including renewal)":
        "KCC Animal Husbandry Issued (Incl Renewal)",
    "Name of Sch. Comm. Bank selectedfor allotment of villages with < 2000 Pop.":
        "Bank Allotted Villages <2000 Pop.",
    "Out of Roadmap preparedfor less than 2000, No. of villageswherebanking outlet opened upto end of reporting Quarter":
        "Roadmap <2000 Villages with Banking Outlet",
    "Total No. of Operative Sb Accounts covered with at least one of the facilities - Debit/Ru Pay cards/Net Banking/Mobile Banking/UPI/USSD":
        "Digital Coverage SB A/C",
    "Out of total no. of women accounts (G6), no of women accounts covered":
        "Women A/C Covered (of G6)",
    "Out of total no. of women accountse (G6), no of women accounts covered":
        "Women A/C Covered (of G6)",
    "Total no. of eligible PMJDY Accounts for PMSBY enrolment Male":
        "Eligible PMJDY A/C for PMSBY Male",
    # Post-garbled-fix versions (after spaces inserted but before shortening)
    "Out of Roadmap prepared for less than 2000, No. of villages wherebanking outlet opened upto end of reporting Quarter":
        "Roadmap <2000 Villages with Banking Outlet",
    "Name of Sch. Comm. Bank selected for allotment of villages with < 2000 population":
        "Bank Allotted Villages <2000 Pop.",
    "Name of Sch. Comm. Bank selected for allotment of villages with < 2000 Pop.":
        "Bank Allotted Villages <2000 Pop.",
    "Out of Roadmap prepared for less than 2000, No. of villages where banking outlet opened upto end of reporting Quarter":
        "Roadmap <2000 Villages with Banking Outlet",
    "Coverage percentage (%) of eligible current accounts":
        "Coverage % Eligible Current A/C",
    "Coverage percentage (%) of eligible current accounts through any one digital mode":
        "Coverage % Current A/C Digital",
    "Coverage percentage (%) of eligible savings accounts":
        "Coverage % Eligible Savings A/C",
    "Coverage percentage (%) of eligible savings accounts through any one digital mode":
        "Coverage % Savings A/C Digital",
    "% of such Accounts out of total Operative Current Accounts":
        "% of Operative Current A/C",
    "% of such Accounts out of total Operative Savings Accounts":
        "% of Operative Savings A/C",
    "Covered by Branch/BC (Cbs enabled banking outlet)":
        "Covered by Branch/BC (CBS)",
    "Coveredby Branch/BC (Cbsenabledbankingoutlet)":
        "Covered by Branch/BC (CBS)",
    "Covered by Branch/BC (CBS enabled banking outlet)":
        "Covered by Branch/BC (CBS)",
}

# Phrases to remove for shortening
REMOVE_PHRASES = [
    r'\s*during the quarter\s*',
    r'\s*as per Rbi guidelines\s*',
    r'\s*using standardized financial literacy material of Rbi\s*',
    r'\s*at the end of current quarter\s*',
    r'\s*as on end of current quarter\s*',
    r'\s*\(Rs\.?\s*in\s*Lakhs?\)\s*',
    r'\s*During the quarter\s*',
]

def shorten_field_name(name):
    """Shorten field names that are >60 characters."""
    if not name or len(name) <= 60:
        return name

    # Check explicit mapping first
    if name in LONG_NAME_MAP:
        return LONG_NAME_MAP[name]

    s = name
    # Remove redundant phrases
    for phrase in REMOVE_PHRASES:
        s = re.sub(phrase, ' ', s, flags=re.IGNORECASE)

    # Abbreviations
    s = re.sub(r'\bNumber of\b', 'No. of', s, flags=re.IGNORECASE)
    s = re.sub(r'\bpercentage\b', '%', s, flags=re.IGNORECASE)
    s = re.sub(r'\bpopulation\b', 'Pop.', s, flags=re.IGNORECASE)
    s = re.sub(r'\bApplications?\b', 'Appln', s)
    s = re.sub(r'\bSanctioned\b', 'Sanctd', s)
    s = re.sub(r'\bOutstanding\b', 'O/S', s)
    s = re.sub(r'\bRenewal\b', 'Renewal', s)
    s = re.sub(r'\bcumulative\b', 'Cumul.', s, flags=re.IGNORECASE)
    s = re.sub(r'\bSince Inception\b', 'Inception', s, flags=re.IGNORECASE)
    s = re.sub(r'\banimal husbandary\b', 'AH', s, flags=re.IGNORECASE)
    s = re.sub(r'\banimal husbandry\b', 'AH', s, flags=re.IGNORECASE)
    s = re.sub(r'\bFishries\b', 'Fisheries', s, flags=re.IGNORECASE)

    # Clean up spaces
    s = re.sub(r'\s+', ' ', s).strip()

    return s


# ═══════════════════════════════════════════════════════════════════════════════
# Issue #2: NPA % vs Amount disambiguation
# ═══════════════════════════════════════════════════════════════════════════════
def fix_pct_field_name(name):
    """Rename fields ending in 'Amt. %' or 'Amt %' to use 'Pct'."""
    if not name or not isinstance(name, str):
        return name

    s = name
    # Pattern: "X NPA Amt. %" -> "X NPA Pct"
    s = re.sub(r'\bAmt\.?\s*%\s*$', 'Pct', s)
    # Pattern: "X Settled %" -> "X Settled Pct"
    s = re.sub(r'\bSettled\s*%\s*$', 'Settled Pct', s)
    # Pattern: "X Achv% Amt" -> "X Achv Pct Amt" (keep Amt since it's the amount of achievement %)
    s = re.sub(r'\bAchv%\s', 'Achv% ', s)
    # Pattern: "Overdues %" -> "Overdues Pct"
    s = re.sub(r'\bOverdues\s*%\s*$', 'Overdues Pct', s)
    # Pattern: "Recovery %" -> "Recovery Pct"
    s = re.sub(r'\bRecovery\s*%\s*$', 'Recovery Pct', s)
    # Pattern: "Gross NPA %" or "GrossNPA %" -> "Gross NPA Pct"
    s = re.sub(r'\bNPA\s*%\s*$', 'NPA Pct', s)
    s = re.sub(r'\bN-Pa\s*%\s*$', 'NPA Pct', s)
    # Pattern: "Cdr %" -> "Cdr Pct"
    s = re.sub(r'\bCdr\s*%\s*$', 'Cdr Pct', s)
    # Pattern: "% coveragee" -> "Coverage Pct"
    s = re.sub(r'^%\s*coveragee?\b', 'Coverage Pct', s, flags=re.IGNORECASE)
    # Pattern: "% coveragee for women accounts" -> "Coverage Pct Women A/C"
    s = re.sub(r'^%\s*coveragee?\s+for\s+women\s+accounts?\b', 'Coverage Pct Women A/C', s, flags=re.IGNORECASE)
    # Pattern: "% of Agri. Adv to Nbc 18%" -> keep as is (contextual %)
    # Pattern: "CD ratio Norm 60%" -> keep as is (the % is part of the norm value)
    # Pattern: "Ach % Amt" -> "Ach Pct Amt"
    s = re.sub(r'\bAch\s*%\s*Amt\b', 'Ach Pct Amt', s)
    # Pattern: "Disb %" -> "Disb Pct"
    s = re.sub(r'\bDisb\s*%\s*$', 'Disb Pct', s)
    # Pattern ending with standalone "%" that's not part of a number
    # "Amt. % MUDRA" type patterns (Meghalaya reversed field names)
    s = re.sub(r'\bAmt\.?\s*%\s', 'Pct ', s)

    # Handle tripura's garbled "% " in middle of field names
    # "Total No. of % Accounts covered" -> leave these alone, they're garbled
    # "Total No. of Accou % nts covered" -> leave alone
    # "Total No. of Accounts % covered" -> leave alone
    # These are OCR artifacts - the % is not meaningful

    # "% ofhouseholdcovered" -> "Household Coverage Pct"
    s = re.sub(r'^%\s*ofhouseholdcovered$', 'Household Coverage Pct', s, flags=re.IGNORECASE)
    s = re.sub(r'^%\s*of\s*household\s*covered$', 'Household Coverage Pct', s, flags=re.IGNORECASE)

    return s


# ═══════════════════════════════════════════════════════════════════════════════
# Issue #6: Remove bank-name uncategorized tables
# ═══════════════════════════════════════════════════════════════════════════════
def is_bank_name_table(table_data):
    """Check if >50% of field names in a table are bank names."""
    fields = table_data.get('fields', [])
    if not fields:
        return False

    bank_count = 0
    for f in fields:
        fname = f.upper().strip().replace('.', '').replace(' ', '')
        if fname in BANK_NAMES or fname == 'TOTAL':
            bank_count += 1

    # >50% of fields are bank names (excluding TOTAL)
    non_total = [f for f in fields if f.upper().strip() != 'TOTAL']
    if not non_total:
        return False
    bank_non_total = sum(1 for f in non_total if f.upper().strip().replace('.', '').replace(' ', '') in BANK_NAMES)
    return bank_non_total > len(non_total) * 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# Apply all field name transformations
# ═══════════════════════════════════════════════════════════════════════════════
def transform_field_name(name):
    """Apply all field name fixes in order."""
    s = name
    # 1. Fix garbled concatenations first
    s = fix_garbled_name(s)
    # 2. Fix NPA % disambiguation
    s = fix_pct_field_name(s)
    # 3. Shorten long names
    s = shorten_field_name(s)
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# Regeneration helpers
# ═══════════════════════════════════════════════════════════════════════════════
def make_col_key(table_name, field_name):
    """Create a timeseries column key from table + field."""
    return f"{table_name}_{field_name}".lower().replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '').replace(',', '').replace('.', '').replace('-', '_').replace('&', 'and').replace('%', 'pct').replace("'", '').replace('"', '').replace('__', '_').rstrip('_')


def generate_quarterly_csvs(state, state_slug, data):
    """Regenerate all quarterly CSVs from the complete.json data."""
    quarterly_dir = BASE / state / "quarterly"

    for qk, qv in data['quarters'].items():
        q_dir = quarterly_dir / qk
        # Remove old CSVs
        if q_dir.exists():
            for f in q_dir.glob("*.csv"):
                f.unlink()
        else:
            q_dir.mkdir(parents=True, exist_ok=True)

        for table_name, table_data in qv['tables'].items():
            fields = table_data.get('fields', [])
            districts = table_data.get('districts', {})
            if not districts:
                continue

            # Build CSV rows
            rows = []
            for district_name, district_values in districts.items():
                row = OrderedDict()
                row['District'] = district_name
                for field in fields:
                    row[field] = district_values.get(field, '')
                rows.append(row)

            if not rows:
                continue

            csv_path = q_dir / f"{table_name}.csv"
            all_fields = ['District'] + fields
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(rows)


def generate_timeseries(state, state_slug, data):
    """Regenerate timeseries CSV and JSON, excluding empty columns."""
    # Collect all data points: (district, period) -> {col_key: value}
    all_records = []
    all_col_keys = set()

    # Sort quarters chronologically
    quarters_sorted = sorted(data['quarters'].keys())

    for qk in quarters_sorted:
        qv = data['quarters'][qk]
        period = qv.get('period', qk)
        as_on_date = qv.get('as_on_date', '')
        fy = qv.get('fy', '')

        # Collect districts across all tables for this quarter
        district_data = defaultdict(dict)

        for table_name, table_data in qv['tables'].items():
            for district_name, district_values in table_data.get('districts', {}).items():
                for field_name, value in district_values.items():
                    col_key = make_col_key(table_name, field_name)
                    all_col_keys.add(col_key)
                    if value is not None and str(value).strip() != '':
                        district_data[district_name][col_key] = str(value)

        for district_name, cols in district_data.items():
            record = {
                'district': district_name,
                'period': period,
                'as_on_date': as_on_date,
                'fy': fy,
            }
            record.update(cols)
            all_records.append(record)

    # Find non-empty columns (Issue #3)
    non_empty_cols = set()
    for record in all_records:
        for k, v in record.items():
            if k not in ('district', 'period', 'as_on_date', 'fy') and v is not None and str(v).strip() != '':
                non_empty_cols.add(k)

    empty_cols_removed = all_col_keys - non_empty_cols

    # Sort column keys
    sorted_cols = sorted(non_empty_cols)
    all_csv_cols = ['district', 'period', 'as_on_date', 'fy'] + sorted_cols

    # Write CSV
    csv_path = BASE / state / f"{state_slug}_fi_timeseries.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=all_csv_cols, extrasaction='ignore')
        writer.writeheader()
        for record in all_records:
            row = {col: record.get(col, '') for col in all_csv_cols}
            writer.writerows([row])

    # Write JSON
    json_path = BASE / state / f"{state_slug}_fi_timeseries.json"

    # Group records by period for JSON
    periods_list = []
    period_groups = defaultdict(list)
    period_order = []
    for record in all_records:
        p = record['period']
        if p not in period_groups:
            period_order.append(p)
        period_groups[p].append(record)

    for p in period_order:
        records = period_groups[p]
        periods_list.append({
            'period': p,
            'num_districts': len(records),
            'districts': records,
        })

    ts_json = {
        'source': data.get('source', 'SLBC NE'),
        'state': data.get('state', state),
        'description': 'Complete district-wise FI time-series',
        'num_periods': len(periods_list),
        'total_records': len(all_records),
        'total_fields': len(sorted_cols),
        'periods': periods_list,
    }

    with open(json_path, 'w') as f:
        json.dump(ts_json, f, indent=2)

    return len(all_col_keys), len(non_empty_cols), len(empty_cols_removed)


# ═══════════════════════════════════════════════════════════════════════════════
# Main processing
# ═══════════════════════════════════════════════════════════════════════════════
def process_state(state):
    """Process all fixes for a single state."""
    state_slug = STATE_SLUGS[state]
    json_path = BASE / state / f"{state_slug}_complete.json"

    with open(json_path) as f:
        data = json.load(f)

    state_stats = {
        'comma_numbers_fixed': 0,
        'pct_fields_renamed': 0,
        'garbled_names_fixed': 0,
        'long_names_shortened': 0,
        'bank_tables_removed': 0,
        'timeseries_cols_before': 0,
        'timeseries_cols_after': 0,
        'empty_cols_removed': 0,
    }

    quarters_to_process = list(data['quarters'].keys())

    for qk in quarters_to_process:
        qv = data['quarters'][qk]
        tables_to_remove = []

        for table_name in list(qv['tables'].keys()):
            table_data = qv['tables'][table_name]

            # Issue #6: Remove bank-name uncategorized tables
            if 'uncategorized' in table_name.lower() and is_bank_name_table(table_data):
                tables_to_remove.append(table_name)
                state_stats['bank_tables_removed'] += 1
                continue

            # Process fields list
            new_fields = []
            field_rename_map = {}
            for field in table_data.get('fields', []):
                new_name = transform_field_name(field)
                if new_name != field:
                    field_rename_map[field] = new_name
                    if ',' in field and COMMA_NUM_RE.match(field):
                        pass  # field name shouldn't be a number
                    # Track stats
                    orig_garbled = fix_garbled_name(field)
                    if orig_garbled != field:
                        state_stats['garbled_names_fixed'] += 1
                    orig_pct = fix_pct_field_name(field)
                    if orig_pct != field:
                        state_stats['pct_fields_renamed'] += 1
                    if len(field) > 60 and len(new_name) <= 60:
                        state_stats['long_names_shortened'] += 1
                new_fields.append(new_name)
            table_data['fields'] = new_fields

            # Process district data
            for district_name in list(table_data.get('districts', {}).keys()):
                district_values = table_data['districts'][district_name]
                new_district_values = {}

                for field_key, value in district_values.items():
                    # Rename field
                    new_key = field_rename_map.get(field_key, transform_field_name(field_key))

                    # Fix comma numbers (Issue #1)
                    new_value = fix_comma_numbers(value)
                    if new_value != value:
                        state_stats['comma_numbers_fixed'] += 1

                    new_district_values[new_key] = new_value

                table_data['districts'][district_name] = new_district_values

            qv['tables'][table_name] = table_data

        # Remove bank-name tables
        for tn in tables_to_remove:
            del qv['tables'][tn]

    # Save updated complete.json
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)

    # Regenerate quarterly CSVs
    generate_quarterly_csvs(state, state_slug, data)

    # Regenerate timeseries
    total_cols, non_empty_cols, empty_removed = generate_timeseries(state, state_slug, data)
    state_stats['timeseries_cols_before'] = total_cols
    state_stats['timeseries_cols_after'] = non_empty_cols
    state_stats['empty_cols_removed'] = empty_removed

    return state_stats


def main():
    print("=" * 80)
    print("SLBC Data Quality Fix - All 8 NE States")
    print("=" * 80)

    all_stats = {}
    for state in STATES:
        print(f"\nProcessing {state}...")
        try:
            state_stats = process_state(state)
            all_stats[state] = state_stats
            print(f"  Done.")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n{'State':<25} {'Comma#':>8} {'%Rename':>8} {'Garbled':>8} {'Long':>8} {'BankTbl':>8} {'TS Before':>10} {'TS After':>10} {'Empty':>8}")
    print("-" * 106)

    totals = defaultdict(int)
    for state in STATES:
        if state not in all_stats:
            continue
        s = all_stats[state]
        print(f"{state:<25} {s['comma_numbers_fixed']:>8} {s['pct_fields_renamed']:>8} {s['garbled_names_fixed']:>8} {s['long_names_shortened']:>8} {s['bank_tables_removed']:>8} {s['timeseries_cols_before']:>10} {s['timeseries_cols_after']:>10} {s['empty_cols_removed']:>8}")
        for k, v in s.items():
            totals[k] += v

    print("-" * 106)
    print(f"{'TOTAL':<25} {totals['comma_numbers_fixed']:>8} {totals['pct_fields_renamed']:>8} {totals['garbled_names_fixed']:>8} {totals['long_names_shortened']:>8} {totals['bank_tables_removed']:>8} {totals['timeseries_cols_before']:>10} {totals['timeseries_cols_after']:>10} {totals['empty_cols_removed']:>8}")

    print("\nColumn legend:")
    print("  Comma#   = Comma-formatted number values fixed")
    print("  %Rename  = NPA/percentage field names disambiguated")
    print("  Garbled  = Garbled concatenated field names fixed")
    print("  Long     = Long field names shortened (>60 chars)")
    print("  BankTbl  = Bank-name uncategorized tables removed")
    print("  TS Before/After = Timeseries column count before/after empty removal")
    print("  Empty    = Empty timeseries columns removed")


if __name__ == '__main__':
    main()
