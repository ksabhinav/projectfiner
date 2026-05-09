#!/usr/bin/env python3
"""
Jharkhand SLBC Agenda Book Extractor
Extracts district-wise banking data from Jharkhand SLBC agenda PDF booklets.
Uses pdfplumber's extract_tables() for reliable table extraction.
Outputs quarterly CSVs, jharkhand_complete.json, jharkhand_fi_timeseries.json/csv.
"""

import pdfplumber
import json
import csv
import os
import re
import sys
import glob
from pathlib import Path
from collections import OrderedDict

# Jharkhand's 24 districts (canonical names — title case)
JHARKHAND_DISTRICTS = [
    "Bokaro", "Chatra", "Deoghar", "Dhanbad", "Dumka",
    "East Singhbhum", "Garhwa", "Giridih", "Godda", "Gumla",
    "Hazaribagh", "Jamtara", "Khunti", "Koderma", "Latehar",
    "Lohardaga", "Pakur", "Palamu", "Ramgarh", "Ranchi",
    "Sahibganj", "Seraikela-Kharsawan", "Simdega", "West Singhbhum"
]

# Fuzzy matching for district names (uppercase -> canonical)
DISTRICT_ALIASES = {}
for d in JHARKHAND_DISTRICTS:
    DISTRICT_ALIASES[d.upper()] = d
    DISTRICT_ALIASES[d] = d
# Common variants
DISTRICT_ALIASES.update({
    "EAST SINGHBHUM": "East Singhbhum",
    "E.SINGHBHUM": "East Singhbhum",
    "E. SINGHBHUM": "East Singhbhum",
    "E SINGHBHUM": "East Singhbhum",
    "EAST SINGBHUM": "East Singhbhum",
    "WEST SINGHBHUM": "West Singhbhum",
    "W.SINGHBHUM": "West Singhbhum",
    "W. SINGHBHUM": "West Singhbhum",
    "W SINGHBHUM": "West Singhbhum",
    "WEST SINGBHUM": "West Singhbhum",
    "SERAIKELA-KHARSAWAN": "Seraikela-Kharsawan",
    "SERAIKELLA-KHARSAWAN": "Seraikela-Kharsawan",
    "SERAIKELA KHARSAWAN": "Seraikela-Kharsawan",
    "SERAIKELLA KHARSAWAN": "Seraikela-Kharsawan",
    "SERAIKELA -KHARSAWAN": "Seraikela-Kharsawan",
    "SERAIKELA- KHARSAWAN": "Seraikela-Kharsawan",
    "SERAIKELA - KHARSAWAN": "Seraikela-Kharsawan",
    "SERAIKELLA-KHARSWAN": "Seraikela-Kharsawan",
    "SARAIKELA-KHARSAWAN": "Seraikela-Kharsawan",
    "SARAIKELA KHARSAWAN": "Seraikela-Kharsawan",
    "SAHEBGANJ": "Sahibganj",
    "SAHIBGUNGE": "Sahibganj",
    "PALAMU": "Palamu",
    "PALAMAU": "Palamu",
    "HAZARIBAG": "Hazaribagh",
    "HAZARIBAG H": "Hazaribagh",
    "HAZARIBAGH": "Hazaribagh",
    "KODARMA": "Koderma",
    "LOHARDAGGA": "Lohardaga",
    "GIRIDIH": "Giridih",
    "GIRIDIIH": "Giridih",
    "DEOGHAR": "Deoghar",
    "DEOGARH": "Deoghar",
    "PAKUR": "Pakur",
    "PANKUR": "Pakur",
})

# Sort by length descending for matching
DISTRICT_PATTERNS = sorted(DISTRICT_ALIASES.keys(), key=len, reverse=True)

# Category mapping: keywords in title -> standardized category name
# Order matters — first match wins
CATEGORY_MAP = [
    # KCC variants
    (["KCC", "ANIMAL HUSBANDRY"], "kcc_animal_husbandry"),
    (["KCC", "FISHRI"], "kcc_fishery"),
    (["KCC", "FISHER"], "kcc_fishery"),
    (["KISAN CREDIT CARD", "ANIMAL"], "kcc_animal_husbandry"),
    (["KISAN CREDIT CARD", "FISH"], "kcc_fishery"),
    (["KISAN CREDIT CARD", "CROP"], "kcc"),
    (["KCC", "CROP"], "kcc"),
    (["KISAN CREDIT CARD"], "kcc"),

    # ACP disbursement categories
    (["ANNUAL CREDIT PLAN", "AGRICULTURE"], "acp_disbursement_agri"),
    (["ACP", "AGRICULTURE"], "acp_disbursement_agri"),
    (["ANNUAL CREDIT PLAN", "MSME"], "acp_disbursement_msme"),
    (["ACP", "MSME"], "acp_disbursement_msme"),
    (["ANNUAL CREDIT PLAN", "NON-PRIORITY"], "acp_disbursement_non_ps"),
    (["ANNUAL CREDIT PLAN", "NON PRIORITY"], "acp_disbursement_non_ps"),
    (["ACP", "NON-PRIORITY"], "acp_disbursement_non_ps"),
    (["ACP", "NON PRIORITY"], "acp_disbursement_non_ps"),
    (["ANNUAL CREDIT PLAN", "PRIORITY SECTOR"], "acp_disbursement_other_ps"),
    (["ACP", "PRIORITY SECTOR"], "acp_disbursement_other_ps"),
    (["ANNUAL CREDIT PLAN", "TOTAL ADVANCE"], "acp_target_achievement"),
    (["ACP", "TOTAL ADVANCE"], "acp_target_achievement"),

    # Outstanding categories
    (["AGRICULTURE", "NPA", "OUTSTANDING"], "agri_npa"),
    (["AGRICULTURE", "NPA"], "agri_npa"),
    (["MSME", "NPA", "OUTSTANDING"], "msme_npa"),
    (["MSME", "NPA"], "msme_npa"),
    (["OTHER PRIORITY", "NPA"], "other_ps_npa"),
    (["NON PRIORITY", "NPA"], "non_ps_npa"),
    (["NON-PRIORITY", "NPA"], "non_ps_npa"),
    (["TOTAL PRIORITY", "NPA"], "priority_sector_npa"),
    (["TOTAL NPA OUTSTANDING"], "npa_recovery"),
    (["TOTAL NPA"], "npa_recovery"),

    (["AGRICULTURE OUTSTANDING"], "agri_outstanding"),
    (["MSME", "OUTSTANDING"], "msme_outstanding"),
    (["NON-PRIORITY SECTOR OUTSTANDING"], "non_ps_outstanding"),
    (["NON PRIORITY SECTOR OUTSTANDING"], "non_ps_outstanding"),
    (["NON-PRIORITY", "OUTSTANDING"], "non_ps_outstanding"),
    (["NON PRIORITY", "OUTSTANDING"], "non_ps_outstanding"),
    (["PRIORITY SECTOR OUTSTANDING"], "priority_sector_outstanding"),
    (["WEAKER SECTION OUTSTANDING"], "weaker_section_os"),
    (["WEAKER SECTION", "OUTSTANDING"], "weaker_section_os"),

    # CD Ratio
    (["DEPOSIT", "ADVANCES", "CD RATIO"], "credit_deposit_ratio"),
    (["C.D RATIO"], "credit_deposit_ratio"),
    (["CD RATIO"], "credit_deposit_ratio"),

    # Branch network
    (["BRANCH DETAIL"], "branch_network"),
    (["BRANCH NETWORK"], "branch_network"),

    # Education
    (["EDUCATION LOAN"], "education_loan"),
    (["HIGHER EDUCATION"], "education_loan"),
    (["VIDYA LAKSHMI"], "education_loan_vlp"),

    # Housing
    (["HOUSING LOAN"], "housing_pmay"),
    (["HOUSING", "PMAY"], "housing_pmay"),

    # PMEGP
    (["PMEGP"], "pmegp"),

    # SHG
    (["SHG BANK LINKAGE"], "shg"),
    (["SHG", "LINKAGE"], "shg"),
    (["SHG", "DISBURSEMENT"], "shg"),
    (["SHG", "OUTSTANDING"], "shg"),
    (["TOTAL SHG"], "shg"),

    # NPA / Recovery
    (["CERTIFICATE CASE"], "recovery_certificate"),
    (["DRT CASE"], "recovery_drt"),
    (["SARFAESI"], "sarfaesi"),

    # Investment credit
    (["INVESTMENT CREDIT", "AGRICULTURE"], "investment_credit_agri_disbursement"),
    (["INVESTMENT CREDIT", "AGRI"], "investment_credit_agri_disbursement"),

    # Minority
    (["MINORITY", "DISBURS"], "minority_disbursement"),
    (["MINORITY", "OUTSTANDING"], "minority_outstanding"),
    (["MINORITY", "LOAN"], "minority_disbursement"),

    # SC/ST - must come after Stand Up India to avoid matching SC/ST in SUI tables
    (["SC/ST", "OUTSTANDING", "DISBURS"], "sc_st_finance"),
    (["SC/ST", "DISTRICT"], "sc_st_finance"),
    (["SC/ST", "LOAN"], "sc_st_finance"),
    (["SC ST", "LOAN"], "sc_st_finance"),
    (["LOANS OUTSTANDING", "SC/ST"], "sc_st_finance"),
    (["LOANS DISBURSED", "SC/ST"], "sc_st_finance"),

    # Women
    (["WOMEN", "DISTRICT"], "women_finance"),
    (["ADVANCES TO WOMEN"], "women_finance"),
    (["FINANCE TO WOMEN"], "women_finance"),

    # Aadhaar / CASA
    (["AADHAAR", "AUTHENTICATION"], "aadhaar_authentication"),
    (["AADHAAR", "CASA"], "aadhaar_authentication"),
    (["CASA", "AADHAAR"], "aadhaar_authentication"),

    # PMJDY
    (["PMJDY"], "pmjdy"),
    (["JAN DHAN"], "pmjdy"),

    # Social Security
    (["SOCIAL SECURITY"], "social_security"),
    (["PMJJBY"], "social_security"),
    (["PMSBY"], "social_security"),

    # MUDRA
    (["MUDRA", "OUTSTANDING", "NPA"], "pmmy_mudra_os_npa"),
    (["MUDRA", "NPA"], "pmmy_mudra_os_npa"),
    (["MUDRA LOAN", "PROGRESS"], "pmmy_mudra_disbursement"),
    (["MUDRA LOAN"], "pmmy_mudra_disbursement"),

    # Stand Up India
    (["STAND UP INDIA"], "sui"),

    # Business Correspondents
    (["BUSINESS CORRESPONDENT"], "business_correspondents"),

    # PM SVANidhi
    (["SVANIDHI"], "pm_svanidhi"),
    (["PM SVA"], "pm_svanidhi"),

    # Government sponsored NPA
    (["GOVT", "SPONSORED", "NPA"], "govt_sponsored_npa"),
    (["GOVERNMENT", "SPONSORED", "NPA"], "govt_sponsored_npa"),

    # RSETI
    (["RSETI", "TRAINING"], "rseti"),
    (["RSETI", "MIS"], "rseti"),
    (["RSETI", "REPORT"], "rseti"),

    # Financial Literacy
    (["FLC", "DATABASE"], "flc_report"),
    (["FINANCIAL LITERACY"], "flc_report"),

    # PM Vishwakarma
    (["VISHWAKARMA"], "pm_vishwakarma"),

    # Guruji Credit Card
    (["GURUJI"], "guruji_credit_card"),

    # PMFME
    (["PMFME"], "pmfme"),

    # Doubling Farmers Income
    (["DOUBLING", "FARMER"], "doubling_farmers_income"),

    # ADS
    (["PROGRESS FOR IMPLEMENTATION OF ADS"], "ads_progress"),

    # Investment / Place of Utilization
    (["INVESTMENT", "PLACE OF UTIL"], "investment_utilization"),
    (["PLACE OF UTIL"], "investment_utilization"),

    # Rural Branch Camps
    (["RURAL", "BRANCH", "CAMP"], "rural_branch_camps"),

    # Digital transactions
    (["DIGITAL TRANSACTION"], "digital_transactions"),
]


def detect_category(title):
    """Match a page title to a standardized category."""
    title_upper = title.upper()
    # Remove extra spaces from OCR artifacts
    title_upper = re.sub(r'\s+', ' ', title_upper)
    for keywords, category in CATEGORY_MAP:
        if all(kw.upper() in title_upper for kw in keywords):
            return category
    return None


def normalize_district(name):
    """Normalize a district name to canonical form."""
    if not name:
        return None
    name = str(name).strip()
    # Remove serial number prefix
    name = re.sub(r'^\d+[\.\s]*', '', name).strip()
    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name)

    # Try exact match
    if name in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[name]
    if name.upper() in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[name.upper()]

    # Try fuzzy
    clean = name.upper().strip()
    for pattern in DISTRICT_PATTERNS:
        if clean == pattern or clean.startswith(pattern + ' ') or clean.startswith(pattern + '-'):
            return DISTRICT_ALIASES[pattern]

    return None


def parse_number(val):
    """Clean a number string: handle spaces before commas, remove commas, percentages."""
    if val is None:
        return ''
    val = str(val).strip()
    if val in ('', '-', 'NA', 'N/A', 'NIL', 'Nil', 'nil', '--', '---'):
        return ''

    # Handle "1 ,44,456" -> "144456" (spaces before commas)
    val = re.sub(r'\s+,', ',', val)
    # Handle "1, 44, 456" -> "144456" (spaces after commas)
    val = re.sub(r',\s+', ',', val)
    # Remove commas
    val = val.replace(',', '')
    # Handle percentage
    val = val.replace('%', '').strip()
    # Remove any remaining spaces in numbers like "3 0,885" -> "30885"
    # But be careful: "30 885" could be a number with space as thousands separator
    if re.match(r'^[\d\s\.\-]+$', val):
        val = val.replace(' ', '')
    return val


def get_page_title(page):
    """Extract the title from page text, cleaning OCR artifacts."""
    text = page.extract_text()
    if not text:
        return ''

    lines = text.strip().split('\n')
    title_parts = []
    for line in lines[:10]:
        line = line.strip()
        upper = line.upper()
        # Skip boilerplate
        if any(skip in upper for skip in [
            'STATE LEVEL', 'CONVENOR', 'BANK OF INDIA', 'STAT E', 'STA TE',
            'STATE LEV', 'STATE LE VEL', 'STATE L EVE', 'STATE LEVE'
        ]):
            continue
        # Skip empty or very short
        if len(line) < 5:
            continue
        # Skip lines that are just numbers or page identifiers
        if re.match(r'^[\d\s\.\-]+$', line):
            continue
        # Skip annexure-only lines
        if re.match(r'^(A\s*n\s*n\s*e\s*x\s*u\s*r\s*e|Annexure)', line, re.IGNORECASE):
            continue
        title_parts.append(line)
        if len(title_parts) >= 3:
            break

    title = ' '.join(title_parts)
    # Clean OCR spacing artifacts
    title = re.sub(r'\s+', ' ', title)
    return title.strip()


def extract_table_from_page(page, page_num):
    """Extract district-wise table from a single page using pdfplumber's extract_tables().
    Returns (category, headers_list, district_data_dict, as_on_date) or None.
    """
    tables = page.extract_tables()
    if not tables:
        return None

    title = get_page_title(page)
    if not title:
        return None

    # Find the largest table on the page
    table = max(tables, key=lambda t: len(t))
    if len(table) < 5:
        return None

    # Check if this table has district data
    has_districts = False
    for row in table:
        if len(row) >= 2 and row[1]:
            cell = str(row[1]).strip().upper()
            if normalize_district(cell):
                has_districts = True
                break
        # Also check first column (some tables use col 0 for district)
        if len(row) >= 1 and row[0]:
            cell = str(row[0]).strip().upper()
            if normalize_district(cell):
                has_districts = True
                break

    if not has_districts:
        return None

    # Detect category
    category = detect_category(title)
    if not category:
        # Try with full text from the first few table rows merged
        header_text = ' '.join(str(cell or '') for row in table[:4] for cell in row)
        category = detect_category(title + ' ' + header_text)

    if not category:
        print(f"  [SKIP] P{page_num}: Unknown category: {title[:100]}")
        return None

    # Detect as_on date from title or table content
    as_on_date = None
    full_text = (page.extract_text() or '').upper()
    # Look for date patterns
    date_patterns = [
        r'(?:AS\s*ON|UPTO|UP\s*TO)\s*(\d{1,2})\s*(?:ST|ND|RD|TH)?\s*(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*(\d{4})',
        r'(?:AS\s*ON|UPTO|UP\s*TO)\s*(\d{1,2})[\./-](\d{1,2})[\./-](\d{4})',
        r'(\d{1,2})[\./-](\d{1,2})[\./-](\d{4})',
        r'(?:AS\s*ON)\s*(\d{1,2})\s*(?:ST|ND|RD|TH)?\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\w*\s*(\d{4})',
    ]

    month_names = {
        'JANUARY': '01', 'FEBRUARY': '02', 'MARCH': '03', 'APRIL': '04',
        'MAY': '05', 'JUNE': '06', 'JULY': '07', 'AUGUST': '08',
        'SEPTEMBER': '09', 'OCTOBER': '10', 'NOVEMBER': '11', 'DECEMBER': '12',
        'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
        'JUN': '06', 'JUL': '07', 'AUG': '08', 'SEP': '09',
        'OCT': '10', 'NOV': '11', 'DEC': '12',
    }

    for pat in date_patterns:
        m = re.search(pat, full_text)
        if m:
            groups = m.groups()
            if groups[1] in month_names:
                day, month_str, year = groups
                month = month_names[month_str]
            else:
                day, month, year = groups
                if len(month) > 2:
                    continue
            as_on_date = f"{day.zfill(2)}-{month.zfill(2)}-{year}"
            break

    # Separate header rows from data rows
    header_rows = []
    data_rows = []
    district_col_idx = None  # Which column has district names

    for row in table:
        # Check if this row has a district name
        is_data = False
        for ci in range(min(3, len(row))):
            if row[ci] and normalize_district(str(row[ci]).strip()):
                is_data = True
                district_col_idx = ci
                break
            # Also check if first col is a serial number and second is district
            if ci == 0 and row[ci] and str(row[ci]).strip().isdigit() and len(row) > 1 and row[1]:
                if normalize_district(str(row[1]).strip()):
                    is_data = True
                    district_col_idx = 1
                    break

        if is_data:
            data_rows.append(row)
        elif not data_rows:
            # Only add to headers if we haven't seen data yet
            header_rows.append(row)

    if not data_rows:
        return None

    if district_col_idx is None:
        district_col_idx = 1

    # Build composite header names from multi-row headers
    num_cols = max(len(r) for r in table)
    composite_headers = build_composite_headers(header_rows, num_cols)

    # Extract district data
    districts = {}
    value_start = district_col_idx + 1

    for row in data_rows:
        dist_name = str(row[district_col_idx] or '').strip()
        district = normalize_district(dist_name)
        if not district:
            continue
        if district in districts:
            continue  # Skip duplicates

        values = []
        for ci in range(value_start, len(row)):
            values.append(parse_number(row[ci]))

        # Pad to consistent length
        districts[district] = values

    if len(districts) < 15:
        print(f"  [FEW] P{page_num}: {category} only {len(districts)} districts, skipping")
        return None

    # Get headers for value columns only
    value_headers = composite_headers[value_start:] if len(composite_headers) > value_start else []

    # Ensure value_headers matches the max number of value columns
    max_vals = max(len(v) for v in districts.values()) if districts else 0
    while len(value_headers) < max_vals:
        value_headers.append(f'col_{len(value_headers)+1}')

    # Pad all district value lists to same length
    for d in districts:
        while len(districts[d]) < max_vals:
            districts[d].append('')

    return (category, value_headers[:max_vals], districts, as_on_date, title)


def build_composite_headers(header_rows, num_cols):
    """Build composite header names from multi-row spanning headers."""
    if not header_rows:
        return [f'col_{i}' for i in range(num_cols)]

    # For each column, collect non-empty values from all header rows
    headers = []
    # Track spanning: if a cell is None, it may be part of a merged cell
    prev_vals = [''] * num_cols

    for ci in range(num_cols):
        parts = []
        for ri, row in enumerate(header_rows):
            if ci < len(row) and row[ci]:
                val = str(row[ci]).strip()
                # Clean newlines
                val = val.replace('\n', ' ')
                val = re.sub(r'\s+', ' ', val)
                if val and val not in parts:
                    parts.append(val)
        headers.append(' '.join(parts) if parts else f'col_{ci}')

    return headers


def to_snake_case(name):
    """Convert a header name to snake_case."""
    if not name:
        return ''
    # Replace special chars
    name = name.replace('%', 'pct').replace('/', '_').replace('-', '_')
    name = name.replace('(', '').replace(')', '').replace('.', '')
    name = name.replace("'", '').replace('"', '').replace(':', '')
    name = name.replace('&', 'and')
    # Replace spaces and multiple underscores
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_').lower()
    # Truncate very long names
    if len(name) > 80:
        name = name[:80].rstrip('_')
    return name


def detect_quarter_from_date(as_on_date):
    """Convert as_on_date like '30-09-2025' to quarter info."""
    if not as_on_date:
        return None, None, None

    parts = as_on_date.split('-')
    if len(parts) != 3:
        return None, None, None

    day, month, year = parts
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


def get_fy(quarter_key):
    """Get financial year from quarter key like '2025-09'."""
    year, month = quarter_key.split('-')
    year = int(year)
    month = int(month)
    if month <= 3:
        return f"{year-1}-{str(year)[2:]}"
    else:
        return f"{year}-{str(year+1)[2:]}"


def extract_all_tables(pdf_path):
    """Extract all district-wise tables from a Jharkhand SLBC PDF."""
    pdf = pdfplumber.open(pdf_path)
    print(f"Opened {pdf_path}: {len(pdf.pages)} pages")

    results = []
    seen_categories = {}

    for i in range(len(pdf.pages)):
        page = pdf.pages[i]
        result = extract_table_from_page(page, i + 1)
        if result:
            category, headers, districts, as_on_date, title = result

            # Handle duplicate categories with different sub-tables (like ACP agri page 1 vs page 2)
            # by appending a suffix
            cat_key = category
            if category in seen_categories:
                # Check if headers are different (different sub-table)
                prev = seen_categories[category]
                if prev['headers'] != headers:
                    # Different sub-table — merge or keep separate with suffix
                    suffix = seen_categories[category].get('count', 1)
                    cat_key = f"{category}_p{suffix + 1}"
                    seen_categories[category]['count'] = suffix + 1
                else:
                    # Same headers, likely a continuation — skip
                    print(f"  [DUP] P{i+1}: {category} already extracted, skipping")
                    continue

            seen_categories[category] = {'headers': headers, 'count': seen_categories.get(category, {}).get('count', 1)}

            results.append({
                'page': i + 1,
                'title': title,
                'category': cat_key,
                'headers': headers,
                'districts': districts,
                'as_on_date': as_on_date,
            })
            print(f"  [OK] P{i+1}: {cat_key} ({len(districts)} districts, {len(headers)} cols)")

    pdf.close()
    return results


def detect_quarter(pdf_path, tables):
    """Detect the quarter from the PDF tables' as_on_date fields."""
    # Collect all dates
    dates = []
    for t in tables:
        if t.get('as_on_date'):
            dates.append(t['as_on_date'])

    if not dates:
        # Try from filename
        basename = os.path.basename(pdf_path).lower()
        # Try to extract meeting number for rough dating
        return None, None, None

    # Use the most common date
    from collections import Counter
    date_counts = Counter(dates)
    most_common_date = date_counts.most_common(1)[0][0]

    return detect_quarter_from_date(most_common_date)


def save_quarterly_csvs(tables, quarter_key, output_dir):
    """Save extracted tables as quarterly CSVs with proper headers."""
    quarter_dir = os.path.join(output_dir, 'quarterly', quarter_key)
    os.makedirs(quarter_dir, exist_ok=True)

    saved = 0
    for table in tables:
        category = table['category']
        districts = table['districts']
        headers = table['headers']

        if not districts:
            continue

        # Build snake_case headers
        snake_headers = [to_snake_case(h) for h in headers]

        csv_path = os.path.join(quarter_dir, f"{category}.csv")

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['district'] + snake_headers)

            for district in JHARKHAND_DISTRICTS:
                if district in districts:
                    row = [district] + districts[district]
                    # Pad if needed
                    while len(row) < len(snake_headers) + 1:
                        row.append('')
                    writer.writerow(row[:len(snake_headers) + 1])

        saved += 1

    print(f"  Saved {saved} CSVs to {quarter_dir}")
    return quarter_dir


def process_single_pdf(pdf_path, output_dir):
    """Process a single PDF and return (quarter_key, period, as_on_date, tables)."""
    print(f"\n{'='*70}")
    print(f"Processing: {os.path.basename(pdf_path)}")
    print(f"{'='*70}")

    tables = extract_all_tables(pdf_path)
    if not tables:
        print(f"  No tables found in {pdf_path}")
        return None

    print(f"\n  Extracted {len(tables)} district-wise tables")

    quarter_key, period_name, as_on_date = detect_quarter(pdf_path, tables)
    if not quarter_key:
        print(f"  Could not detect quarter from {pdf_path}")
        return None

    print(f"  Quarter: {period_name} (as on {as_on_date})")

    # Save quarterly CSVs
    save_quarterly_csvs(tables, quarter_key, output_dir)

    return (quarter_key, period_name, as_on_date, tables)


def build_complete_json(all_quarters, output_dir):
    """Build and save jharkhand_complete.json from all extracted quarters."""
    complete = {
        "source": "SLBC Jharkhand",
        "state": "Jharkhand",
        "description": "Complete district-wise banking & financial inclusion data",
        "amount_unit": "Rs. Lakh",
        "quarters": {}
    }

    for qk in sorted(all_quarters.keys()):
        qdata = all_quarters[qk]
        period_name = qdata['period']
        as_on_date = qdata['as_on_date']
        fy = get_fy(qk)

        quarter_obj = {
            "period": period_name,
            "as_on_date": as_on_date,
            "fy": fy,
            "tables": {}
        }

        for table in qdata['tables']:
            category = table['category']
            districts = table['districts']
            headers = table['headers']
            snake_headers = [to_snake_case(h) for h in headers]

            table_data = {
                "fields": snake_headers,
                "num_districts": len(districts),
                "districts": {}
            }

            for district, values in districts.items():
                row = {}
                for i, h in enumerate(snake_headers):
                    row[h] = values[i] if i < len(values) else ''
                table_data["districts"][district] = row

            quarter_obj["tables"][category] = table_data

        complete["quarters"][qk] = quarter_obj

    json_path = os.path.join(output_dir, 'jharkhand_complete.json')
    with open(json_path, 'w') as f:
        json.dump(complete, f, indent=2)

    print(f"\nSaved jharkhand_complete.json ({len(complete['quarters'])} quarters)")
    return complete


def build_timeseries(complete, output_dir):
    """Build and save jharkhand_fi_timeseries.json and .csv."""
    periods = []
    all_fields = set()

    for qk in sorted(complete['quarters'].keys()):
        qdata = complete['quarters'][qk]
        period_name = qdata['period']
        as_on_date = qdata['as_on_date']
        fy = qdata['fy']

        district_records = {}

        for category, table_data in qdata['tables'].items():
            fields = table_data['fields']
            for district, row in table_data['districts'].items():
                if district not in district_records:
                    district_records[district] = {
                        'district': district,
                        'period': period_name,
                    }
                for field_name, value in row.items():
                    key = f"{category}__{field_name}"
                    district_records[district][key] = value
                    all_fields.add(key)

        districts_list = []
        for d in JHARKHAND_DISTRICTS:
            if d in district_records:
                districts_list.append(district_records[d])

        if districts_list:
            periods.append({
                'period': period_name,
                'as_on_date': as_on_date,
                'fy': fy,
                'districts': districts_list,
            })

    timeseries = {
        "source": "SLBC Jharkhand",
        "state": "Jharkhand",
        "description": "Jharkhand district-wise financial inclusion timeseries data",
        "num_periods": len(periods),
        "total_records": sum(len(p['districts']) for p in periods),
        "periods": periods,
    }

    # Save JSON
    json_path = os.path.join(output_dir, 'jharkhand_fi_timeseries.json')
    with open(json_path, 'w') as f:
        json.dump(timeseries, f, indent=2)
    print(f"Saved jharkhand_fi_timeseries.json ({len(periods)} periods, {timeseries['total_records']} records)")

    # Save CSV (wide format)
    sorted_fields = sorted(all_fields)
    csv_path = os.path.join(output_dir, 'jharkhand_fi_timeseries.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['district', 'period', 'as_on_date', 'fy'] + sorted_fields)

        for period in periods:
            for rec in period['districts']:
                row = [
                    rec.get('district', ''),
                    rec.get('period', ''),
                    period.get('as_on_date', ''),
                    period.get('fy', ''),
                ]
                for field in sorted_fields:
                    row.append(rec.get(field, ''))
                writer.writerow(row)

    print(f"Saved jharkhand_fi_timeseries.csv")

    return timeseries


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python extract_jharkhand.py <pdf1> [pdf2] ... [--output-dir DIR]")
        print("  python extract_jharkhand.py --all  (process all PDFs in current dir)")
        print()
        print("Example:")
        print("  python extract_jharkhand.py 93Agenda.pdf 92Agenda.pdf 91Agenda.pdf")
        print("  python extract_jharkhand.py --all --output-dir ../../public/slbc-data/jharkhand")
        sys.exit(1)

    # Parse args
    pdf_paths = []
    output_dir = '../../public/slbc-data/jharkhand'
    process_all = False

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--output-dir' and i + 1 < len(sys.argv):
            output_dir = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--all':
            process_all = True
            i += 1
        else:
            pdf_paths.append(sys.argv[i])
            i += 1

    if process_all:
        # Find all PDFs in current directory
        pdf_paths = sorted(glob.glob('*.pdf') + glob.glob('*.PDF'))
        if not pdf_paths:
            print("No PDF files found in current directory")
            sys.exit(1)

    print(f"Processing {len(pdf_paths)} PDF(s)")
    print(f"Output directory: {output_dir}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'quarterly'), exist_ok=True)

    # Process each PDF
    all_quarters = {}

    for pdf_path in pdf_paths:
        if not os.path.exists(pdf_path):
            print(f"Warning: {pdf_path} not found, skipping")
            continue

        try:
            result = process_single_pdf(pdf_path, output_dir)
        except Exception as e:
            print(f"  ERROR processing {pdf_path}: {e}")
            result = None
        if result:
            quarter_key, period_name, as_on_date, tables = result
            if quarter_key in all_quarters:
                # Merge tables, preferring newer (later file)
                existing = all_quarters[quarter_key]['tables']
                existing_cats = {t['category'] for t in existing}
                for t in tables:
                    if t['category'] not in existing_cats:
                        existing.append(t)
                    else:
                        # Replace with newer data
                        existing = [x for x in existing if x['category'] != t['category']]
                        existing.append(t)
                all_quarters[quarter_key]['tables'] = existing
            else:
                all_quarters[quarter_key] = {
                    'period': period_name,
                    'as_on_date': as_on_date,
                    'tables': tables,
                }

    if not all_quarters:
        print("\nNo data extracted from any PDF!")
        sys.exit(1)

    # Build complete.json
    print(f"\n{'='*70}")
    print("Building combined output files")
    print(f"{'='*70}")

    complete = build_complete_json(all_quarters, output_dir)

    # Build timeseries
    timeseries = build_timeseries(complete, output_dir)

    # Summary
    print(f"\n{'='*70}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*70}")
    print(f"  PDFs processed: {len(pdf_paths)}")
    print(f"  Quarters: {len(all_quarters)}")
    for qk in sorted(all_quarters.keys()):
        qd = all_quarters[qk]
        cats = [t['category'] for t in qd['tables']]
        print(f"    {qk} ({qd['period']}): {len(cats)} tables")
    print(f"  Districts: {len(JHARKHAND_DISTRICTS)}")
    all_cats = set()
    for qd in all_quarters.values():
        for t in qd['tables']:
            all_cats.add(t['category'])
    print(f"  Total categories: {len(all_cats)}")
    print(f"  Categories: {', '.join(sorted(all_cats))}")
    print(f"\nOutput files:")
    print(f"  {output_dir}/jharkhand_complete.json")
    print(f"  {output_dir}/jharkhand_fi_timeseries.json")
    print(f"  {output_dir}/jharkhand_fi_timeseries.csv")
    print(f"  {output_dir}/quarterly/*/  (per-quarter CSVs)")


if __name__ == '__main__':
    main()
