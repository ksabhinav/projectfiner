#!/usr/bin/env python3
"""
Bihar SLBC Agenda Book Extractor
Extracts district-wise banking data from Bihar SLBC agenda PDF booklets.
Outputs quarterly CSVs and a combined complete.json matching the Project FINER format.
"""

import pdfplumber
import json
import csv
import os
import re
import sys
from pathlib import Path

# Bihar's 38 districts (canonical names)
BIHAR_DISTRICTS = [
    "Araria", "Arwal", "Aurangabad", "Banka", "Begusarai", "Bhagalpur",
    "Bhojpur", "Buxar", "Darbhanga", "Gaya", "Gopalganj", "Jamui",
    "Jehanabad", "Kaimur (Bhabua)", "Katihar", "Khagaria", "Kishanganj",
    "Lakhisarai", "Madhepura", "Madhubani", "Munger", "Muzaffarpur",
    "Nalanda", "Nawada", "Pashchim Champaran", "Patna", "Purbi Champaran",
    "Purnia", "Rohtas", "Saharsa", "Samastipur", "Saran", "Sheikhpura",
    "Sheohar", "Sitamarhi", "Siwan", "Supaul", "Vaishali"
]

# Fuzzy matching for district names
DISTRICT_ALIASES = {
    "ARARIA": "Araria", "ARWAL": "Arwal", "AURANGABAD": "Aurangabad",
    "BANKA": "Banka", "BEGUSARAI": "Begusarai", "BHAGALPUR": "Bhagalpur",
    "BHOJPUR": "Bhojpur", "BUXAR": "Buxar", "DARBHANGA": "Darbhanga",
    "GAYA": "Gaya", "GOPALGANJ": "Gopalganj", "JAMUI": "Jamui",
    "JEHANABAD": "Jehanabad", "KAIMUR (BHABUA)": "Kaimur (Bhabua)",
    "KAIMUR(BHABUA)": "Kaimur (Bhabua)", "KAIMUR": "Kaimur (Bhabua)",
    "KATIHAR": "Katihar", "KHAGARIA": "Khagaria", "KISHANGANJ": "Kishanganj",
    "LAKHISARAI": "Lakhisarai", "MADHEPURA": "Madhepura", "MADHUBANI": "Madhubani",
    "MUNGER": "Munger", "MUZAFFARPUR": "Muzaffarpur", "NALANDA": "Nalanda",
    "NAWADA": "Nawada", "PASHCHIM CHAMPARAN": "Pashchim Champaran",
    "PASCHIM CHAMPARAN": "Pashchim Champaran", "WEST CHAMPARAN": "Pashchim Champaran",
    "P. CHAMPARAN": "Pashchim Champaran", "PATNA": "Patna",
    "PURBI CHAMPARAN": "Purbi Champaran", "EAST CHAMPARAN": "Purbi Champaran",
    "E. CHAMPARAN": "Purbi Champaran", "PURNIA": "Purnia", "PURNEA": "Purnia",
    "ROHTAS": "Rohtas", "SAHARSA": "Saharsa", "SAMASTIPUR": "Samastipur",
    "SARAN": "Saran", "SHEIKHPURA": "Sheikhpura", "SHEOHAR": "Sheohar",
    "SITAMARHI": "Sitamarhi", "SIWAN": "Siwan", "SUPAUL": "Supaul",
    "VAISHALI": "Vaishali",
    # Title case variants
    "Araria": "Araria", "Arwal": "Arwal", "Aurangabad": "Aurangabad",
    "Banka": "Banka", "Begusarai": "Begusarai", "Bhagalpur": "Bhagalpur",
    "Bhojpur": "Bhojpur", "Buxar": "Buxar", "Darbhanga": "Darbhanga",
    "Gaya": "Gaya", "Gopalganj": "Gopalganj", "Jamui": "Jamui",
    "Jehanabad": "Jehanabad", "Kaimur (Bhabua)": "Kaimur (Bhabua)",
    "Katihar": "Katihar", "Khagaria": "Khagaria", "Kishanganj": "Kishanganj",
    "Lakhisarai": "Lakhisarai", "Madhepura": "Madhepura", "Madhubani": "Madhubani",
    "Munger": "Munger", "Muzaffarpur": "Muzaffarpur", "Nalanda": "Nalanda",
    "Nawada": "Nawada", "Pashchim Champaran": "Pashchim Champaran",
    "Patna": "Patna", "Purbi Champaran": "Purbi Champaran",
    "Purnia": "Purnia", "Rohtas": "Rohtas", "Saharsa": "Saharsa",
    "Samastipur": "Samastipur", "Saran": "Saran", "Sheikhpura": "Sheikhpura",
    "Sheohar": "Sheohar", "Sitamarhi": "Sitamarhi", "Siwan": "Siwan",
    "Supaul": "Supaul", "Vaishali": "Vaishali",
}

# Category mapping: keywords in title -> standardized category name
CATEGORY_MAP = [
    # Order matters — first match wins
    (["BRANCH NETWORK"], "branch_network"),
    (["BANKING OUTLET"], "banking_outlet"),
    (["ATM", "NETWORK"], "atm_network"),
    (["POINT OF SALE", "POS"], "pos_network"),
    (["DIGITAL TRANSACTION"], "digital_transactions"),
    (["AADHAAR", "AUTHENTICATION"], "aadhaar_authentication"),
    (["PMJDY"], "pmjdy"),
    (["SURAKSHA BIMA"], "pmsby"),
    (["SOCIAL SECURITY CLAIM"], "social_security_claims"),
    (["PERFORMANCE", "ANNUAL CREDIT PLAN"], "acp_performance"),
    (["OUTSTANDING", "PRIORITY", "SECTOR", "DISBURSEMENT"], "acp_priority_sector_disbursement"),
    (["DISBURSEMENT", "ANNUAL CREDIT PLAN", "PRIORITY"], "acp_priority_sector_disbursement"),
    (["DISBURSEMENT", "ANNUAL CREDIT PLAN", "NON PRIORITY"], "acp_non_priority_sector_disbursement"),
    (["MICRO ENTERPRISES"], "msme_micro_disbursement"),
    (["SMALL ENTERPRISES"], "msme_small_disbursement"),
    (["MIDIUM ENTERPRISES", "MEDIUM ENTERPRISES"], "msme_medium_disbursement"),
    (["OTHER FINANCE TO MSME"], "msme_other_disbursement"),
    (["ACP", "MSME", "DISBURSEMENT"], "acp_msme_disbursement"),
    (["MSME", "NPA", "OUTSTANDING"], "msme_npa_outstanding"),
    (["MSME", "OUTSTANDING"], "msme_outstanding"),
    (["AGRICULTURE", "NPA", "OUTSTANDING"], "agriculture_npa_outstanding"),
    (["AGRICULTURE", "OUTSTANDING"], "agriculture_outstanding"),
    (["AGRICULTURE", "DISBURSEMENT"], "agriculture_disbursement"),
    (["KCC", "ANIMAL HUSBANDRY", "OUTSTANDING"], "kcc_ah_outstanding_npa"),
    (["KCC", "ANIMAL HUSBANDRY", "PROGRESS"], "kcc_ah_progress"),
    (["KCC", "FISHERIES", "OUTSTANDING"], "kcc_fisheries_outstanding_npa"),
    (["KCC", "FISHERIES", "PROGRESS"], "kcc_fisheries_progress"),
    (["KCC", "OUTSTANDING", "NPA"], "kcc_outstanding_npa"),
    (["KCC", "PROGRESS"], "kcc_progress"),
    (["DAIRY"], "dairy"),
    (["POULTRY"], "poultry"),
    (["FISHERIES"], "fisheries"),
    (["AGRI TERM LOAN"], "agri_term_loan"),
    (["CROP LOAN"], "crop_loan"),
    (["AGRI INFRASTRUCTURE"], "agri_infrastructure"),
    (["ANCILLARY ACTIVITIES"], "agri_ancillary"),
    (["JLG"], "jlg"),
    (["OTHER", "DISBURSEMENT"], "other_disbursement"),
    (["OTHER", "NPA", "OUTSTANDING"], "other_npa_outstanding"),
    (["OTHER", "OUTSTANDING"], "other_outstanding"),
    (["NON PRIORITY", "NPA"], "non_priority_npa_outstanding"),
    (["NON PRIORITY", "OUTSTANDING"], "non_priority_outstanding"),
    (["NON PRIORITY", "DISBURSEMENT"], "non_priority_disbursement"),
    (["EDUCATION LOAN"], "education_loan"),
    (["HOUSING LOAN"], "housing_loan"),
    (["WEAKER SECTION", "DISBURSEMENT"], "weaker_section_disbursement"),
    (["WEAKER SECTION", "OUTSTANDING"], "weaker_section_outstanding"),
    (["SC/ST"], "sc_st_disbursement"),
    (["MINORITY", "DISBURSEMENT"], "minority_disbursement"),
    (["MINORITY", "OUTSTANDING"], "minority_outstanding"),
    (["FINANCE TO WOMEN"], "women_finance"),
    (["PMMY", "DISBURSEMENT"], "pmmy_disbursement"),
    (["PMMY", "OUTSTANDING", "NPA"], "pmmy_outstanding_npa"),
    (["MUDRA", "OUTSTANDING", "NPA"], "pmmy_outstanding_npa"),
    (["PMEGP", "1ST LOAN", "FIRST"], "pmegp_first_loan"),
    (["PMEGP", "2ND LOAN", "SECOND"], "pmegp_second_loan"),
    (["PMFME"], "pmfme"),
    (["VISHWAKARMA"], "pm_vishwakarma"),
    (["SURYA GHAR", "FY"], "pm_surya_ghar"),
    (["SURYA GHAR", "INCEPTION"], "pm_surya_ghar_cumulative"),
    (["CD RATIO"], "cd_ratio"),
    (["NON PERFORMING ASSETS", "VARIOUS SECTOR"], "npa_all_sectors"),
    (["CERTIFICATE CASES"], "certificate_cases"),
    (["SARFAESI"], "sarfaesi"),
    (["RSETI"], "rseti"),
    (["DCC", "MEETING"], "dcc_meeting"),
    (["BLBC", "MEETING"], "blbc_meeting"),
    (["KCC", "AH", "SATURATION"], "kcc_ah_saturation"),
    (["KCC", "FISHERIES", "SATURATION"], "kcc_fisheries_saturation"),
    (["SATURATION CAMPAIGN"], "fi_saturation_campaign"),
    (["DEAF", "DEPOSITOR"], "deaf_claims"),
    (["FL CAMPS", "FINANCIAL LITERACY"], "fl_camps"),
    (["OUTSTANDING"], "outstanding_advances"),
    (["PMEGP"], "pmegp"),
]


def detect_category(title):
    """Match a page title to a standardized category."""
    title_upper = title.upper()
    for keywords, category in CATEGORY_MAP:
        if all(kw in title_upper for kw in keywords):
            return category
    return None


def normalize_district(name):
    """Normalize a district name to canonical form."""
    name = name.strip()
    # Try exact match first
    if name in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[name]
    # Try upper case
    if name.upper() in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[name.upper()]
    # Try fuzzy: strip serial numbers, extra spaces
    clean = re.sub(r'^\d+\s*', '', name).strip()
    clean = re.sub(r'\s+', ' ', clean)
    if clean.upper() in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[clean.upper()]
    return None


def parse_number(val):
    """Clean a number string: remove commas, handle edge cases."""
    if not val or val.strip() in ('', '-', 'NA', 'N/A', 'NIL', '0.00'):
        return val.strip() if val else ''
    val = val.strip()
    # Remove commas
    val = val.replace(',', '')
    # Handle percentage
    val = val.replace('%', '')
    return val


def extract_district_table(page, page_num):
    """Extract a district-wise table from a single page.
    Returns (title, category, headers, rows_dict) or None.
    """
    text = page.extract_text()
    if not text or not text.strip():
        return None

    lines = text.strip().split('\n')

    # Check if it's a district-wise page
    upper_text = text.upper()[:800]
    if 'DISTRICT' not in upper_text:
        return None

    # Extract title (skip STATE LEVEL BANKERS and CONVENOR lines)
    title_parts = []
    header_start = 0
    for idx, line in enumerate(lines):
        line_clean = line.strip()
        upper_line = line_clean.upper()
        if any(skip in upper_line for skip in ['STATE LEVEL', 'CONVENOR', 'SLBC BIHAR']):
            continue
        if any(skip in upper_line for skip in ['NO. IN ACTUAL', 'AMOUNT IN', '( AMOUNT', '(AMOUNT']):
            header_start = idx + 1
            break
        if len(line_clean) > 10:
            title_parts.append(line_clean)
            if idx > 5:
                break

    title = ' '.join(title_parts).strip()
    if not title:
        return None

    category = detect_category(title)
    if not category:
        # Try with full text header
        full_header = ' '.join(lines[:6])
        category = detect_category(full_header)

    if not category:
        print(f"  [SKIP] P{page_num}: Unknown category: {title[:80]}")
        return None

    # Parse the data rows
    # Find where headers end and data begins (first line starting with a digit)
    data_start = 0
    header_lines = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        # Data rows start with a serial number
        if stripped and re.match(r'^\d+\s+[A-Z]', stripped):
            data_start = idx
            break
        if idx >= header_start:
            header_lines.append(stripped)

    if data_start == 0:
        # Try lowercase district names
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped and re.match(r'^\d+\s+[A-Za-z]', stripped):
                data_start = idx
                break

    if data_start == 0:
        print(f"  [SKIP] P{page_num}: No data rows found for {category}")
        return None

    # Extract column headers from header_lines
    # These are tricky because they span multiple lines
    # We'll use the raw text headers
    raw_headers = ' '.join(header_lines)

    # Build a lookup of district name patterns for matching
    # Sort by longest first so "PASHCHIM CHAMPARAN" matches before "CHAMPARAN"
    district_patterns = sorted(DISTRICT_ALIASES.keys(), key=len, reverse=True)

    # Parse data rows
    rows = {}
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped:
            continue

        # Stop at total/footer rows
        upper_stripped = stripped.upper()
        if any(stop in upper_stripped for stop in ['TOTAL', 'GRAND', 'STATE TOTAL',
               'ADVANCE GRANTED', 'SOURCE:', 'NOTE:', 'OUTSIDE THE STATE']):
            break

        # Strip leading serial number
        m_serial = re.match(r'^(\d+)\s+', stripped)
        if not m_serial:
            continue

        after_serial = stripped[m_serial.end():]

        # Try to match a known district name at the start of after_serial
        district = None
        values_str = None
        after_upper = after_serial.upper()

        for pattern in district_patterns:
            if after_upper.startswith(pattern):
                # Check that the match is followed by a space or end
                rest = after_serial[len(pattern):]
                if rest and not rest[0].isspace() and rest[0] != ')':
                    continue
                # For patterns like "KAIMUR" that need "(BHABUA)" too
                if pattern == "KAIMUR" and "(BHABUA)" in after_upper:
                    # Skip — the longer pattern "KAIMUR (BHABUA)" should match
                    continue
                district = DISTRICT_ALIASES[pattern]
                values_str = rest.strip()
                # Handle case where pattern is "KAIMUR (BHABUA)" and rest starts after ")"
                if not values_str and ')' in after_serial:
                    idx = after_serial.index(')') + 1
                    values_str = after_serial[idx:].strip()
                break

        if not district or not values_str:
            continue

        # Split values by whitespace
        values = re.split(r'\s+', values_str)
        values = [parse_number(v) for v in values]

        rows[district] = values

    return (title, category, raw_headers, rows)


def extract_all_tables(pdf_path):
    """Extract all district-wise tables from a Bihar SLBC PDF."""
    pdf = pdfplumber.open(pdf_path)
    print(f"Opened {pdf_path}: {len(pdf.pages)} pages")

    tables = []

    for i in range(len(pdf.pages)):
        page = pdf.pages[i]
        result = extract_district_table(page, i + 1)
        if result:
            title, category, headers, rows = result
            if len(rows) >= 20:  # At least 20 districts to be valid
                tables.append({
                    'page': i + 1,
                    'title': title,
                    'category': category,
                    'headers': headers,
                    'districts': rows
                })
                print(f"  [OK] P{i+1}: {category} ({len(rows)} districts)")
            else:
                print(f"  [FEW] P{i+1}: {category} only {len(rows)} districts, skipping")

    pdf.close()
    return tables


def detect_quarter(pdf_path, tables):
    """Detect the quarter from the PDF filename or table titles."""
    # Try from title
    for t in tables:
        title = t['title'].upper()
        # Look for date patterns like "30.09.2025" or "AS ON 30.09.2025"
        m = re.search(r'(?:AS ON|UPTO)\s*(\d{2})\.(\d{2})\.(\d{4})', title)
        if m:
            day, month, year = m.groups()
            month = int(month)
            year = int(year)
            if month <= 3:
                return f"{year}-03", f"March {year}", f"31-03-{year}"
            elif month <= 6:
                return f"{year}-06", f"June {year}", f"30-06-{year}"
            elif month <= 9:
                return f"{year}-09", f"September {year}", f"30-09-{year}"
            else:
                return f"{year}-12", f"December {year}", f"31-12-{year}"

    return None, None, None


def get_fy(quarter_key):
    """Get financial year from quarter key like '2025-09'."""
    year, month = quarter_key.split('-')
    year = int(year)
    month = int(month)
    if month <= 3:
        return f"{year-1}-{str(year)[2:]}"
    else:
        return f"{year}-{str(year+1)[2:]}"


def build_field_names(category, text_page, page_num, pdf):
    """Build proper field names for a category by examining the actual page."""
    page = pdf.pages[page_num - 1]
    text = page.extract_text() or ''
    lines = text.strip().split('\n')

    # Find header lines (between the title/unit line and first data row)
    header_lines = []
    collecting = False
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()

        # Start collecting after unit line
        if any(u in upper for u in ['NO. IN ACTUAL', 'AMOUNT IN', '( AMOUNT', '(AMOUNT']):
            collecting = True
            continue

        if collecting:
            # Stop when we hit data (starts with digit + district name)
            if re.match(r'^\d+\s+[A-Z]', stripped, re.IGNORECASE):
                break
            if stripped:
                header_lines.append(stripped)

    return header_lines


def save_quarterly_csvs(tables, quarter_key, output_dir):
    """Save extracted tables as quarterly CSVs."""
    quarter_dir = os.path.join(output_dir, 'quarterly', quarter_key)
    os.makedirs(quarter_dir, exist_ok=True)

    saved = 0
    for table in tables:
        category = table['category']
        districts = table['districts']

        if not districts:
            continue

        # Get number of value columns from first district
        first_district = list(districts.values())[0]
        num_cols = len(first_district)

        # Build CSV
        csv_path = os.path.join(quarter_dir, f"{category}.csv")

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header row: District + value columns (numbered for now)
            # We'll refine headers later
            header = ['District'] + [f'Col_{i+1}' for i in range(num_cols)]
            writer.writerow(header)

            # Data rows
            for district in BIHAR_DISTRICTS:
                if district in districts:
                    writer.writerow([district] + districts[district])
                # Skip districts not in data

        saved += 1

    print(f"\nSaved {saved} CSVs to {quarter_dir}")
    return quarter_dir


def save_complete_json(tables, quarter_key, period_name, as_on_date, output_dir):
    """Save as complete.json matching the Project FINER format."""
    fy = get_fy(quarter_key)

    complete = {
        "source": "SLBC Bihar",
        "state": "Bihar",
        "description": "Complete district-wise banking & financial inclusion data",
        "amount_unit": "Rs. Crore",
        "quarters": {
            quarter_key: {
                "period": period_name,
                "as_on_date": as_on_date,
                "fy": fy,
                "tables": {}
            }
        }
    }

    for table in tables:
        category = table['category']
        districts = table['districts']

        if not districts:
            continue

        first_vals = list(districts.values())[0]
        fields = ['District'] + [f'Col_{i+1}' for i in range(len(first_vals))]

        table_data = {
            "fields": fields,
            "num_districts": len(districts),
            "districts": {}
        }

        for district, values in districts.items():
            row = {"District": district}
            for i, v in enumerate(values):
                row[f'Col_{i+1}'] = v
            table_data["districts"][district] = row

        complete["quarters"][quarter_key]["tables"][category] = table_data

    json_path = os.path.join(output_dir, 'bihar_complete.json')
    with open(json_path, 'w') as f:
        json.dump(complete, f, indent=2)

    print(f"Saved complete.json to {json_path}")


def extract_with_proper_headers(pdf_path, tables):
    """Re-extract tables with proper column headers using pdfplumber table extraction."""
    pdf = pdfplumber.open(pdf_path)

    for table in tables:
        page_num = table['page']
        page = pdf.pages[page_num - 1]

        # Try pdfplumber table extraction for headers
        extracted = page.extract_tables()
        if extracted and len(extracted) > 0:
            raw_table = extracted[0]
            # Find header rows (before first data row)
            header_rows = []
            for row in raw_table:
                # Check if this row has a district name or serial number as first cell
                first_cell = str(row[0] or '').strip()
                if first_cell and re.match(r'^\d+$', first_cell):
                    break
                header_rows.append(row)

            if len(header_rows) >= 2:
                # Build composite headers from multi-row header
                num_cols = max(len(r) for r in header_rows)
                headers = []
                for col_idx in range(num_cols):
                    parts = []
                    for hr in header_rows:
                        if col_idx < len(hr) and hr[col_idx]:
                            parts.append(str(hr[col_idx]).strip())
                    headers.append(' '.join(parts).strip())

                # Skip first 2 cols (SR.NO., District Name) and assign to values
                value_headers = [h for h in headers[2:] if h]

                if value_headers and len(value_headers) >= len(list(table['districts'].values())[0]):
                    table['field_names'] = value_headers[:len(list(table['districts'].values())[0])]
                elif value_headers:
                    table['field_names'] = value_headers

    pdf.close()
    return tables


def save_quarterly_csvs_with_headers(tables, quarter_key, output_dir):
    """Save CSVs with proper headers."""
    quarter_dir = os.path.join(output_dir, 'quarterly', quarter_key)
    os.makedirs(quarter_dir, exist_ok=True)

    saved = 0
    for table in tables:
        category = table['category']
        districts = table['districts']

        if not districts:
            continue

        first_vals = list(districts.values())[0]
        num_cols = len(first_vals)

        # Use extracted field names if available
        if 'field_names' in table and len(table['field_names']) == num_cols:
            headers = ['District'] + table['field_names']
        else:
            headers = ['District'] + [f'Col_{i+1}' for i in range(num_cols)]

        csv_path = os.path.join(quarter_dir, f"{category}.csv")

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for district in BIHAR_DISTRICTS:
                if district in districts:
                    row = [district] + districts[district]
                    # Pad if needed
                    while len(row) < len(headers):
                        row.append('')
                    writer.writerow(row[:len(headers)])

        saved += 1

    print(f"Saved {saved} CSVs to {quarter_dir}")
    return quarter_dir


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_bihar.py <pdf_path> [output_dir]")
        print("Example: python extract_bihar.py 95th_agenda.pdf ../../public/slbc-data/bihar")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else '../../public/slbc-data/bihar'

    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        sys.exit(1)

    print(f"Extracting Bihar SLBC data from: {pdf_path}")
    print(f"Output directory: {output_dir}")
    print()

    # Step 1: Extract all district-wise tables
    tables = extract_all_tables(pdf_path)
    print(f"\nExtracted {len(tables)} district-wise tables")

    # Step 2: Detect quarter
    quarter_key, period_name, as_on_date = detect_quarter(pdf_path, tables)
    if not quarter_key:
        print("Could not detect quarter from PDF. Please specify manually.")
        sys.exit(1)
    print(f"Quarter: {period_name} (as on {as_on_date})")

    # Step 3: Try to extract proper column headers
    print("\nExtracting column headers...")
    tables = extract_with_proper_headers(pdf_path, tables)

    # Step 4: Save quarterly CSVs
    print()
    save_quarterly_csvs_with_headers(tables, quarter_key, output_dir)

    # Step 5: Save complete.json
    save_complete_json(tables, quarter_key, period_name, as_on_date, output_dir)

    # Summary
    print(f"\n{'='*60}")
    print(f"Extraction complete!")
    print(f"  Tables: {len(tables)}")
    print(f"  Quarter: {period_name}")
    print(f"  Districts: 38")
    categories = [t['category'] for t in tables]
    print(f"  Categories: {', '.join(sorted(set(categories)))}")


if __name__ == '__main__':
    main()
