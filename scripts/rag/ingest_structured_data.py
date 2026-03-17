#!/usr/bin/env python3
"""
Convert structured SLBC table data (_complete.json) into text files
for the RAG index. Creates human-readable text representations of
each category's district-level data per quarter.

Output: data/rag/text/{state}/tables/*.txt
These get picked up by build_index.py alongside the PDF-extracted text.
"""

import os
import json
import re

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SLBC_DIR = os.path.join(BASE_DIR, "public", "slbc-data")
TEXT_DIR = os.path.join(BASE_DIR, "data", "rag", "text")

# Human-readable category names
CATEGORY_NAMES = {
    "credit_deposit_ratio": "Credit-Deposit Ratio",
    "branch_network": "Branch Network",
    "branch_network_p2": "Branch Network (Part 2)",
    "kcc": "Kisan Credit Card (KCC)",
    "fi_kcc": "Financial Inclusion - KCC",
    "kcc_animal_husbandry": "KCC - Animal Husbandry",
    "kcc_fishery": "KCC - Fishery",
    "kcc_outstanding": "KCC - Outstanding",
    "pmjdy": "Pradhan Mantri Jan Dhan Yojana (PMJDY)",
    "pmjdy_p2": "PMJDY (Part 2)",
    "pmjdy_p3": "PMJDY (Part 3)",
    "pmjdy_2": "PMJDY District Enrolment",
    "pmjdy_3": "PMJDY District Enrolment (Part 2)",
    "shg": "Self Help Groups (SHG)",
    "shg_nrlm": "SHG - NRLM",
    "shg_p2": "SHG (Part 2)",
    "shg_p3": "SHG (Part 3)",
    "digital_transactions": "Digital Transactions",
    "aadhaar_authentication": "Aadhaar Authentication & Seeding",
    "education_loan": "Education Loan",
    "housing_loan": "Housing Loan",
    "msme": "MSME Lending",
    "npa": "Non-Performing Assets (NPA)",
    "social_security_schemes": "Social Security Schemes",
    "mudra": "MUDRA Loans",
    "stand_up_india": "Stand Up India Scheme",
    "acp_disbursement_agri": "Annual Credit Plan - Agriculture Disbursement",
    "acp_disbursement_msme": "Annual Credit Plan - MSME Disbursement",
    "acp_disbursement_non_ps": "Annual Credit Plan - Non Priority Sector",
    "acp_disbursement_other_ps": "Annual Credit Plan - Other Priority Sector",
    "acp_npa": "Annual Credit Plan - NPA",
    "acp_os_npa_summary": "Annual Credit Plan - Outstanding NPA Summary",
    "acp_nps_os_npa_summary": "Annual Credit Plan - NPS Outstanding NPA Summary",
    "cd_ratio": "Credit-Deposit Ratio",
    "kcc_progress": "KCC Progress",
    "jlg": "Joint Liability Groups (JLG)",
    "nrlm": "National Rural Livelihoods Mission (NRLM)",
}

# Quarter key (e.g. "2024-09") to human-readable (e.g. "September 2024")
MONTH_MAP = {
    "03": "March", "06": "June", "09": "September", "12": "December",
    "01": "January", "02": "February", "04": "April", "05": "May",
    "07": "July", "08": "August", "10": "October", "11": "November",
}

# State slug to human name
STATE_NAMES = {
    "assam": "Assam",
    "meghalaya": "Meghalaya",
    "manipur": "Manipur",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "arunachal-pradesh": "Arunachal Pradesh",
    "tripura": "Tripura",
    "sikkim": "Sikkim",
    "bihar": "Bihar",
    "west-bengal": "West Bengal",
    "jharkhand": "Jharkhand",
    "odisha": "Odisha",
    "chhattisgarh": "Chhattisgarh",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "tamil-nadu": "Tamil Nadu",
}


def quarter_key_to_name(key):
    """Convert '2024-09' to 'September 2024'."""
    # Handle snake_case keys like 'sept_2025', 'june_2020'
    if re.match(r'[a-z]+_\d{4}', key):
        parts = key.split('_')
        month_names = {
            'march': 'March', 'mar': 'March',
            'june': 'June', 'jun': 'June',
            'sept': 'September', 'sep': 'September', 'september': 'September',
            'dec': 'December', 'december': 'December',
        }
        month = month_names.get(parts[0].lower(), parts[0].title())
        return f"{month} {parts[1]}"
    # Handle YYYY-MM keys
    if re.match(r'\d{4}-\d{2}', key):
        year, month = key.split('-')
        month_name = MONTH_MAP.get(month, month)
        return f"{month_name} {year}"
    return key


def format_value(val):
    """Format a value for display."""
    if val is None or val == '' or val == 'None':
        return 'N/A'
    # Try to format as number
    try:
        num = float(str(val).replace(',', ''))
        if num == int(num) and abs(num) < 1e15:
            return f"{int(num):,}"
        return f"{num:,.2f}"
    except (ValueError, TypeError):
        return str(val)


def field_to_readable(field_name):
    """Convert snake_case field to readable name."""
    name = field_name.replace('_', ' ').strip()
    # Capitalize common abbreviations
    abbrevs = {
        'npa': 'NPA', 'kcc': 'KCC', 'shg': 'SHG', 'pmjdy': 'PMJDY',
        'cd': 'CD', 'casa': 'CASA', 'msme': 'MSME', 'atm': 'ATM',
        'bc': 'BC', 'nrlm': 'NRLM', 'mudra': 'MUDRA', 'upi': 'UPI',
        'acp': 'ACP', 'tl': 'Term Loan', 'pct': '%', 'amt': 'Amount',
        'no': 'Number', 'os': 'Outstanding',
    }
    words = name.split()
    result = []
    for w in words:
        if w.lower() in abbrevs:
            result.append(abbrevs[w.lower()])
        else:
            result.append(w.title())
    return ' '.join(result)


def generate_table_text(state_name, quarter_name, category, cat_name, table_data):
    """Generate a natural language text representation of a data table."""
    fields = table_data.get('fields', [])
    districts = table_data.get('districts', {})

    if not districts:
        return None

    # Skip 'District' from fields list (it's the key)
    data_fields = [f for f in fields if f.lower() != 'district']
    if not data_fields:
        return None

    lines = []
    lines.append(f"SLBC Data: {cat_name} for {state_name}, {quarter_name}")
    lines.append(f"Category: {category}")
    lines.append(f"State: {state_name}")
    lines.append(f"Quarter: {quarter_name}")
    lines.append(f"Number of districts: {len(districts)}")
    lines.append(f"Indicators: {', '.join(field_to_readable(f) for f in data_fields[:15])}")
    lines.append("")

    # District-level data
    for district, values in sorted(districts.items()):
        district_line = f"{district}:"
        field_parts = []
        for field in data_fields:
            val = values.get(field)
            if val is not None and val != '' and val != 'None':
                readable_field = field_to_readable(field)
                formatted_val = format_value(val)
                field_parts.append(f"{readable_field} = {formatted_val}")
        if field_parts:
            lines.append(f"  {district_line} {'; '.join(field_parts)}")

    # Summary statistics for key numeric fields
    lines.append("")
    lines.append("Summary statistics:")
    for field in data_fields[:8]:  # Top 8 fields
        nums = []
        for values in districts.values():
            try:
                v = float(str(values.get(field, '')).replace(',', ''))
                nums.append(v)
            except (ValueError, TypeError):
                pass
        if nums:
            readable = field_to_readable(field)
            total = sum(nums)
            avg = total / len(nums)
            lines.append(f"  {readable}: Total = {format_value(total)}, Average = {format_value(avg)}, "
                        f"Min = {format_value(min(nums))}, Max = {format_value(max(nums))}, "
                        f"Districts with data = {len(nums)}")

    return '\n'.join(lines)


def process_state(state_slug):
    """Process a single state's complete JSON into text files."""
    state_name = STATE_NAMES.get(state_slug, state_slug.replace('-', ' ').title())

    # Find complete JSON
    json_path = os.path.join(SLBC_DIR, state_slug, f"{state_slug}_complete.json")
    if not os.path.exists(json_path):
        # Try without hyphen variants
        return 0

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    quarters = data.get('quarters', {})
    if not quarters:
        return 0

    # Output directory
    out_dir = os.path.join(TEXT_DIR, state_slug, "tables")
    os.makedirs(out_dir, exist_ok=True)

    count = 0
    for qkey, qdata in quarters.items():
        quarter_name = qdata.get('period', quarter_key_to_name(qkey))
        tables = qdata.get('tables', {})

        for category, table_data in tables.items():
            cat_name = CATEGORY_NAMES.get(category, category.replace('_', ' ').title())

            text = generate_table_text(state_name, quarter_name, category, cat_name, table_data)
            if not text or len(text) < 100:
                continue

            # Write text file with metadata header
            safe_cat = re.sub(r'[^\w\-]', '_', category)
            safe_q = re.sub(r'[^\w\-]', '_', qkey)
            fname = f"{safe_q}_{safe_cat}.txt"
            fpath = os.path.join(out_dir, fname)

            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(f"---\n")
                f.write(f"state: {state_name}\n")
                f.write(f"type: table\n")
                f.write(f"quarter: {quarter_name}\n")
                f.write(f"filename: {state_slug}_{safe_q}_{safe_cat}\n")
                f.write(f"pages: 0\n")
                f.write(f"---\n\n")
                f.write(text)

            count += 1

    return count


def main():
    print("Ingesting structured SLBC data into RAG text format...")
    print(f"Source: {SLBC_DIR}")
    print(f"Output: {TEXT_DIR}")
    print()

    total = 0
    states = sorted(os.listdir(SLBC_DIR))
    for state_slug in states:
        state_dir = os.path.join(SLBC_DIR, state_slug)
        if not os.path.isdir(state_dir):
            continue
        json_path = os.path.join(state_dir, f"{state_slug}_complete.json")
        if not os.path.exists(json_path):
            continue

        count = process_state(state_slug)
        state_name = STATE_NAMES.get(state_slug, state_slug)
        if count > 0:
            print(f"  {state_name}: {count} table text files")
        total += count

    print(f"\nTotal: {total} table text files created")
    print(f"\nNow run: python3 scripts/rag/build_index.py")


if __name__ == "__main__":
    main()
