#!/usr/bin/env python3
"""
Odisha SLBC Agenda Book Extractor
Extracts district-wise banking data from Odisha SLBC agenda PDF booklets.
Uses pdfplumber's extract_tables() for reliable table extraction.
Outputs quarterly CSVs, odisha_complete.json, odisha_fi_timeseries.json/csv.

Odisha has 30 districts. PDFs are from slbcorissa.com.
Data is NOT reversed (unlike NE states) — normal text orientation.
Amount unit: Rs. Crore (most tables) or Rs. Lakh (some annexures).
"""

import pdfplumber
import json
import csv
import os
import re
import sys
import glob
from pathlib import Path
from collections import OrderedDict, Counter

# Odisha's 30 districts (canonical names — title case)
ODISHA_DISTRICTS = [
    "Angul", "Balangir", "Balasore", "Bargarh", "Bhadrak",
    "Boudh", "Cuttack", "Deogarh", "Dhenkanal", "Gajapati",
    "Ganjam", "Jagatsinghpur", "Jajpur", "Jharsuguda", "Kalahandi",
    "Kandhamal", "Kendrapara", "Keonjhar", "Khordha", "Koraput",
    "Malkangiri", "Mayurbhanj", "Nabarangpur", "Nayagarh", "Nuapada",
    "Puri", "Rayagada", "Sambalpur", "Subarnapur", "Sundargarh"
]

# Fuzzy matching for district names (various spellings -> canonical)
DISTRICT_ALIASES = {}
for d in ODISHA_DISTRICTS:
    DISTRICT_ALIASES[d.upper()] = d
    DISTRICT_ALIASES[d] = d

DISTRICT_ALIASES.update({
    # Common alternate spellings in PDFs
    "BOLANGIR": "Balangir",
    "BALANGIR": "Balangir",
    "BALESWAR": "Balasore",
    "BALESORE": "Balasore",
    "BALESHWAR": "Balasore",
    "BARGAIH": "Bargarh",
    "BARGARH": "Bargarh",
    "BARAGARH": "Bargarh",
    "BAUDH": "Boudh",
    "BOUDH": "Boudh",
    "DEOGARH": "Deogarh",
    "DEBAGARH": "Deogarh",
    "DEVAGARH": "Deogarh",
    "JAGATSINGHPUR": "Jagatsinghpur",
    "JAGATSINGHPUR ": "Jagatsinghpur",
    "JAJPUR": "Jajpur",
    "JAJPUR ": "Jajpur",
    "JHARSUGUDA": "Jharsuguda",
    "JHARSUGDA": "Jharsuguda",
    "KALAHANDI": "Kalahandi",
    "KANDHAMAL": "Kandhamal",
    "KANDHAMAAL": "Kandhamal",
    "KANDHMAL": "Kandhamal",
    "PHULBANI": "Kandhamal",  # old name
    "KENDRAPARA": "Kendrapara",
    "KENDRAPADA": "Kendrapara",
    "KEONJHAR": "Keonjhar",
    "KENDUJHAR": "Keonjhar",
    "KEONJAR": "Keonjhar",
    "KHORDHA": "Khordha",
    "KHURDA": "Khordha",
    "KHORDA": "Khordha",
    "MALKANGIRI": "Malkangiri",
    "MALKANAGIRI": "Malkangiri",
    "MALKANGIR": "Malkangiri",
    "MAYURBHANJ": "Mayurbhanj",
    "MAYURABHANJ": "Mayurbhanj",
    "NABRANGPUR": "Nabarangpur",
    "NABARANGAPUR": "Nabarangpur",
    "NABARANGPUR": "Nabarangpur",
    "NAWARANGPUR": "Nabarangpur",
    "NAYAGARH": "Nayagarh",
    "NUAPADA": "Nuapada",
    "NUAPARA": "Nuapada",
    "RAYAGADA": "Rayagada",
    "SONEPUR": "Subarnapur",
    "SONAPUR": "Subarnapur",
    "SUBARNAPUR": "Subarnapur",
    "SUNDERGARH": "Sundargarh",
    "SUNDARGARH": "Sundargarh",
    "SUNDARGAH": "Sundargarh",
    # With district suffix
    "ANGUL DISTRICT": "Angul",
    "ANUGUL": "Angul",
})

# Sort by length descending for matching
DISTRICT_PATTERNS = sorted(DISTRICT_ALIASES.keys(), key=len, reverse=True)

# Category mapping: keywords in title/header text -> standardized category name
# Order matters — first match wins
CATEGORY_MAP = [
    # ACP district-wise (multi-page tables)
    (["ACP", "DISTRICT", "CROP LOAN"], "acp_district_agri"),
    (["ACP", "DISTRICT", "FISHERY"], "acp_district_agri_allied"),
    (["ACP", "DISTRICT", "FARM CREDIT"], "acp_district_farm_credit"),
    (["ACP", "DISTRICT", "ANCILLARY"], "acp_district_ancillary"),
    (["ACP", "DISTRICT", "TOTAL AGRI"], "acp_district_total_agri"),
    (["ACP", "DISTRICT", "MSME"], "acp_district_msme"),
    (["ACP", "DISTRICT", "SMALL - SERVICE"], "acp_district_msme_services"),
    (["ACP", "DISTRICT", "EXPORT"], "acp_district_total"),
    (["ACP", "DISTRICT", "TOTAL"], "acp_district_total"),
    (["ACP", "QUARTER", "CROP LOAN", "DISTRICT"], "acp_district_agri"),
    (["ACP", "QUARTER", "FISHERY", "DISTRICT"], "acp_district_agri_allied"),
    (["ACP", "QUARTER", "FARM CREDIT", "DISTRICT"], "acp_district_farm_credit"),
    (["ACP", "QUARTER", "ANCILLARY", "DISTRICT"], "acp_district_ancillary"),
    (["ACP", "QUARTER", "TOTAL AGRI", "DISTRICT"], "acp_district_total_agri"),
    (["ACP", "QUARTER", "MSME", "DISTRICT"], "acp_district_msme"),
    (["ACP", "QUARTER", "EXPORT", "DISTRICT"], "acp_district_total"),

    # ACP bank-wise (skip these, we only want district)
    # But detect them to skip properly

    # Branch/BC/ATM Network
    (["DISTRICT", "BRANCH", "BC", "ATM"], "branch_network"),
    (["DISTRCIT", "BRANCH", "BC", "ATM"], "branch_network"),  # typo in PDFs
    (["DISTRICT WISE BRANCH"], "branch_network"),
    (["DISTRCIT WISE BRANCH"], "branch_network"),

    # Branch density
    (["DISTRICT", "BRANCH", "BC", "NETWORK PER"], "branch_density"),
    (["DISTRCIT", "BRANCH", "BC", "NETWORK PER"], "branch_density"),

    # Education Loan
    (["EDUCATION LOAN", "DISTRICT"], "education_loan"),
    (["PROGRESS UNDER EDUCATION LOAN"], "education_loan"),

    # Housing Loan
    (["HOUSING LOAN", "DISTRICT"], "housing_loan"),
    (["PERFORMANCE UNDER HOUSING LOAN"], "housing_loan"),

    # PMAY
    (["PMAY", "DISTRICT"], "housing_pmay"),
    (["PRADHAN MANTRI AWAS"], "housing_pmay"),

    # Key Indicators
    (["KEY INDICATOR"], "key_indicators"),
    (["BANKING KEY INDICATOR"], "key_indicators"),

    # PMJDY
    (["PMJDY", "DISTRICT"], "pmjdy"),
    (["JAN DHAN", "DISTRICT"], "pmjdy"),
    (["PMJDY STATUS"], "pmjdy"),

    # APY
    (["APY", "DISTRICT"], "apy"),

    # PMJJBY/PMSBY claims district
    (["PMJJBY", "CLAIM", "DISTRICT"], "social_security_claims"),
    (["PMJJBY", "DISTRICT"], "social_security_claims"),
    (["CLAIM SETTLEMENT", "DISTRICT"], "social_security_claims"),

    # Social Security (bank-wise - skip by not matching 'DISTRICT')

    # Digital coverage (Review Format)
    (["DIGITAL COVERAGE", "DISTRICT", "SAVINGS"], "digital_coverage_savings"),
    (["REVIEW FORMAT", "DISTRICT", "SAVINGS"], "digital_coverage_savings"),
    (["REVIEW FORMAT", "DISTRICT", "DEBIT"], "digital_coverage_savings"),
    (["DIGITAL COVERAGE", "DISTRICT", "CURRENT"], "digital_coverage_business"),
    (["REVIEW FORMAT", "DISTRICT", "CURRENT"], "digital_coverage_business"),
    (["REVIEW FORMAT", "DISTRICT", "MOBILE"], "digital_coverage_mobile"),
    (["DIGITAL COVERAGE", "INDIVIDUAL"], "digital_coverage_savings"),
    (["DIGITAL COVERAGE", "BUSINESS"], "digital_coverage_business"),

    # KCC (various)
    (["KCC", "DISTRICT"], "kcc"),
    (["KISSAN CREDIT CARD", "DISTRICT"], "kcc"),
    (["KISAN CREDIT CARD", "DISTRICT"], "kcc"),

    # AH KCC Camp district
    (["AH KCC CAMP", "DISTRICT"], "kcc_animal_husbandry"),
    (["DISTRICTWISE AH KCC"], "kcc_animal_husbandry"),

    # Fisheries KCC Camp district
    (["FISHERIES KCC", "DISTRICT"], "kcc_fishery"),
    (["DISTRICTWISE FISHERIES KCC"], "kcc_fishery"),

    # PMEGP district
    (["PMEGP", "DISTRICT"], "pmegp"),
    (["DISTRICT WISE PMEGP"], "pmegp"),
    (["DISTRICT", "PMEGP"], "pmegp"),

    # PMEGP verification
    (["PMEGP", "VERIFICATION", "DISTRICT"], "pmegp_verification"),
    (["PHYSICAL VERIFICATION", "PMEGP"], "pmegp_verification"),

    # PMFME district
    (["PMFME", "DISTRICT"], "pmfme"),
    (["DISTRICT", "PMFME"], "pmfme"),

    # MUDRA district
    (["MUDRA", "DISTRICT"], "mudra"),
    (["DISTRICTWISE", "MUDRA"], "mudra"),

    # Stand Up India district
    (["STAND UP INDIA", "DISTRICT"], "stand_up_india"),
    (["DISTRICT WISE", "STAND UP INDIA"], "stand_up_india"),

    # CGTMSE district
    (["CGTMSE", "DISTRICT"], "cgtmse"),

    # PM Vishwakarma
    (["VISHWAKARMA", "DISTRICT"], "pm_vishwakarma"),

    # CM-SRIM district
    (["CM-SRIM", "DISTRICT"], "cm_srim"),
    (["CM SRIM", "DISTRICT"], "cm_srim"),
    (["SRIM", "DISTRICT"], "cm_srim"),

    # SUY district
    (["SUY", "DISTRICT"], "suy"),
    (["DISTRICT WISE", "SUY"], "suy"),

    # SHG district
    (["SHG", "DISTRICT", "LINKAGE"], "shg"),
    (["DISTRICT WISE SHG"], "shg"),
    (["SHG BANK LINKAGE", "DISTRICT"], "shg"),

    # PM Surya Ghar district
    (["SURYA GHAR", "DISTRICT"], "pm_surya_ghar"),
    (["PM-SURYA GHAR", "DISTRICT"], "pm_surya_ghar"),
    (["PMSG", "DISTRICT"], "pm_surya_ghar"),

    # RSETI district
    (["RSETI", "DISTRICT"], "rseti"),
    (["RSETI", "PERFORMANCE"], "rseti"),

    # SARFAESI
    (["SARFAESI", "DISTRICT"], "sarfaesi"),
    (["SECTION 14", "DISTRICT"], "sarfaesi"),

    # Minority
    (["MINORITY", "DISTRICT"], "minority"),

    # NPA
    (["NPA", "DISTRICT"], "npa"),

    # Town Hall MSME
    (["TOWN HALL", "DISTRICT"], "town_hall_msme"),
    (["TOWN HALL", "MSME"], "town_hall_msme"),

    # BharatNet district
    (["BHARATNET", "DISTRICT"], "bharatnet"),

    # Non-priority sector
    (["NON-PRIORITY", "DISTRICT"], "acp_non_priority"),
    (["NON PRIORITY", "DISTRICT"], "acp_non_priority"),

    # Fallback ACP patterns (more generic)
    (["ACP", "QUARTER", "DISTRICT"], "acp_district"),

    # Generic district-wise tables
    (["DISTRICT WISE"], "district_misc"),
    (["DISTRICTWISE"], "district_misc"),
]


def detect_category(title, header_text=""):
    """Match a page title + header text to a standardized category."""
    combined = (title + ' ' + header_text).upper()
    combined = re.sub(r'\s+', ' ', combined)
    for keywords, category in CATEGORY_MAP:
        if all(kw.upper() in combined for kw in keywords):
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
    # Remove trailing period
    name = name.rstrip('.')

    # Try exact match
    if name in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[name]
    if name.upper() in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[name.upper()]

    # Try fuzzy - startswith
    clean = name.upper().strip()
    for pattern in DISTRICT_PATTERNS:
        if clean == pattern or clean.startswith(pattern + ' ') or clean.startswith(pattern + '-'):
            return DISTRICT_ALIASES[pattern]

    return None


def parse_number(val):
    """Clean a number string: handle commas, percentages, #DIV/0!, etc."""
    if val is None:
        return ''
    val = str(val).strip()
    if val in ('', '-', 'NA', 'N/A', 'NIL', 'Nil', 'nil', '--', '---', '#DIV/0!', '#REF!', '#VALUE!'):
        return ''

    # Handle "1 ,44,456" -> "144456"
    val = re.sub(r'\s+,', ',', val)
    val = re.sub(r',\s+', ',', val)
    val = val.replace(',', '')
    # Handle percentage
    val = val.replace('%', '').strip()
    # Remove any remaining spaces in numbers
    if re.match(r'^[\d\s\.\-]+$', val):
        val = val.replace(' ', '')
    return val


def get_page_title(page):
    """Extract the title from page text."""
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
            'UCO BANK', 'CONVENOR', 'GOUTAM PATRA',
            'BHUBANESWAR', 'भारतीय', 'गौतम', 'एसएलबीसी',
        ]):
            continue
        if len(line) < 5:
            continue
        if re.match(r'^[\d\s\.\-]+$', line):
            continue
        # Skip "Annexure-N" prefix lines but keep rest
        if re.match(r'^Annexure[\s\-]*\d+\s*$', line, re.IGNORECASE):
            continue
        title_parts.append(line)
        if len(title_parts) >= 4:
            break

    title = ' '.join(title_parts)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()


def extract_table_from_page(page, page_num):
    """Extract district-wise table from a single page."""
    tables = page.extract_tables()
    if not tables:
        return None

    title = get_page_title(page)
    if not title:
        return None

    # Find the largest table
    table = max(tables, key=lambda t: len(t))
    if len(table) < 5:
        return None

    # Check if this table has district data
    has_districts = False
    district_col_idx = None
    for row in table:
        for ci in range(min(4, len(row))):
            if row[ci]:
                cell = str(row[ci]).strip()
                if normalize_district(cell):
                    has_districts = True
                    district_col_idx = ci
                    break
        if has_districts:
            break

    if not has_districts:
        return None

    # Build header text from first rows of table
    header_text = ' '.join(str(cell or '') for row in table[:5] for cell in row)

    # Detect category
    category = detect_category(title, header_text)
    if not category:
        # Try with annexure text
        full_text = (page.extract_text() or '')[:500]
        category = detect_category(full_text, header_text)

    if not category:
        print(f"  [SKIP] P{page_num}: Unknown category: {title[:100]}")
        return None

    # Skip bank-wise tables (not district)
    if 'BANK' in header_text.upper() and 'DISTRICT' not in header_text.upper():
        # Check if first data column actually has district names (not bank names)
        bank_names = ['BANK OF BARODA', 'BANK OF INDIA', 'SBI', 'STATE BANK', 'CANARA',
                       'PNB', 'PUNJAB', 'UNION BANK', 'UCO BANK', 'INDIAN BANK',
                       'AXIS', 'HDFC', 'ICICI', 'IDBI', 'GRAMEEN', 'GRAMYA']
        first_data_vals = []
        for row in table[3:8]:
            if district_col_idx is not None and district_col_idx < len(row) and row[district_col_idx]:
                first_data_vals.append(str(row[district_col_idx]).upper())
        is_bank_table = any(any(bn in v for bn in bank_names) for v in first_data_vals)
        if is_bank_table:
            return None

    # Detect as_on date
    as_on_date = None
    full_text = (page.extract_text() or '').upper()

    date_patterns = [
        r'(?:AS\s*ON|UPTO|UP\s*TO|AS\s*OF)\s*(\d{1,2})\s*(?:ST|ND|RD|TH)?\s*(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*[\',]?\s*(\d{4})',
        r'(?:AS\s*ON|UPTO|UP\s*TO|AS\s*OF)\s*(\d{1,2})[\./-](\d{1,2})[\./-](\d{4})',
        r'(?:AS\s*ON|AS\s*OF)\s*(\d{1,2})[\.\s](\d{1,2})[\.\s](\d{4})',
        r'QUARTER\s*ENDED\s*(MARCH|JUNE|SEPTEMBER|DECEMBER)\s*[\',]?\s*(\d{2,4})',
    ]

    month_names = {
        'JANUARY': '01', 'FEBRUARY': '02', 'MARCH': '03', 'APRIL': '04',
        'MAY': '05', 'JUNE': '06', 'JULY': '07', 'AUGUST': '08',
        'SEPTEMBER': '09', 'OCTOBER': '10', 'NOVEMBER': '11', 'DECEMBER': '12',
        'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
        'JUN': '06', 'JUL': '07', 'AUG': '08', 'SEP': '09',
        'OCT': '10', 'NOV': '11', 'DEC': '12',
    }

    quarter_end_days = {
        'MARCH': '31', 'JUNE': '30', 'SEPTEMBER': '30', 'DECEMBER': '31',
        '03': '31', '06': '30', '09': '30', '12': '31',
    }

    for pat in date_patterns:
        m = re.search(pat, full_text)
        if m:
            groups = m.groups()
            if len(groups) == 2:
                # Quarter ended pattern
                month_str, year_str = groups
                month = month_names.get(month_str)
                if month:
                    year = year_str if len(year_str) == 4 else '20' + year_str
                    day = quarter_end_days.get(month_str, '30')
                    as_on_date = f"{day}-{month}-{year}"
                    break
            elif len(groups) == 3:
                if groups[1] in month_names:
                    day, month_str, year = groups
                    month = month_names[month_str]
                else:
                    day, month, year = groups
                    if len(month) > 2:
                        continue
                as_on_date = f"{day.zfill(2)}-{month.zfill(2)}-{year}"
                break

    # Also try to get quarter from title
    if not as_on_date:
        title_upper = title.upper()
        for pat in date_patterns:
            m = re.search(pat, title_upper)
            if m:
                groups = m.groups()
                if len(groups) == 2:
                    month_str, year_str = groups
                    month = month_names.get(month_str)
                    if month:
                        year = year_str if len(year_str) == 4 else '20' + year_str
                        day = quarter_end_days.get(month_str, '30')
                        as_on_date = f"{day}-{month}-{year}"
                        break

    # Separate header rows from data rows
    header_rows = []
    data_rows = []

    for row in table:
        is_data = False
        for ci in range(min(4, len(row))):
            if row[ci] and normalize_district(str(row[ci]).strip()):
                is_data = True
                if district_col_idx is None:
                    district_col_idx = ci
                break
            if ci == 0 and row[ci] and str(row[ci]).strip().isdigit() and len(row) > 1 and row[1]:
                if normalize_district(str(row[1]).strip()):
                    is_data = True
                    district_col_idx = 1
                    break

        if is_data:
            data_rows.append(row)
        elif not data_rows:
            header_rows.append(row)
        # Also capture TOTAL row
        elif row and any(str(c or '').strip().upper() == 'TOTAL' for c in row[:3]):
            pass  # Skip total rows

    if not data_rows:
        return None

    if district_col_idx is None:
        district_col_idx = 1

    # Build composite headers
    num_cols = max(len(r) for r in table)
    composite_headers = build_composite_headers(header_rows, num_cols)

    # Extract district data
    districts = {}
    value_start = district_col_idx + 1

    for row in data_rows:
        if district_col_idx >= len(row):
            continue
        dist_name = str(row[district_col_idx] or '').strip()
        district = normalize_district(dist_name)
        if not district:
            continue
        if district in districts:
            continue

        values = []
        for ci in range(value_start, len(row)):
            values.append(parse_number(row[ci]))

        districts[district] = values

    if len(districts) < 15:
        # For Odisha we expect ~30 districts
        print(f"  [FEW] P{page_num}: {category} only {len(districts)} districts, skipping")
        return None

    # Get headers for value columns
    value_headers = composite_headers[value_start:] if len(composite_headers) > value_start else []

    max_vals = max(len(v) for v in districts.values()) if districts else 0
    while len(value_headers) < max_vals:
        value_headers.append(f'col_{len(value_headers)+1}')

    for d in districts:
        while len(districts[d]) < max_vals:
            districts[d].append('')

    return (category, value_headers[:max_vals], districts, as_on_date, title)


def build_composite_headers(header_rows, num_cols):
    """Build composite header names from multi-row spanning headers."""
    if not header_rows:
        return [f'col_{i}' for i in range(num_cols)]

    headers = []
    for ci in range(num_cols):
        parts = []
        for ri, row in enumerate(header_rows):
            if ci < len(row) and row[ci]:
                val = str(row[ci]).strip()
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
    name = name.replace('%', 'pct').replace('/', '_').replace('-', '_')
    name = name.replace('(', '').replace(')', '').replace('.', '')
    name = name.replace("'", '').replace('"', '').replace(':', '')
    name = name.replace('&', 'and')
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_').lower()
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
    """Extract all district-wise tables from an Odisha SLBC PDF."""
    pdf = pdfplumber.open(pdf_path)
    print(f"Opened {pdf_path}: {len(pdf.pages)} pages")

    results = []
    seen_categories = {}

    for i in range(len(pdf.pages)):
        page = pdf.pages[i]
        result = extract_table_from_page(page, i + 1)
        if result:
            category, headers, districts, as_on_date, title = result

            # Handle duplicate categories
            cat_key = category
            if category in seen_categories:
                prev = seen_categories[category]
                if prev['headers'] != headers:
                    suffix = seen_categories[category].get('count', 1)
                    cat_key = f"{category}_p{suffix + 1}"
                    seen_categories[category]['count'] = suffix + 1
                else:
                    print(f"  [DUP] P{i+1}: {category} already extracted, skipping")
                    continue

            seen_categories[category] = {
                'headers': headers,
                'count': seen_categories.get(category, {}).get('count', 1)
            }

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
    dates = []
    for t in tables:
        if t.get('as_on_date'):
            dates.append(t['as_on_date'])

    if not dates:
        # Try from filename
        basename = os.path.basename(pdf_path).lower()
        return None, None, None

    date_counts = Counter(dates)
    most_common_date = date_counts.most_common(1)[0][0]
    return detect_quarter_from_date(most_common_date)


def save_quarterly_csvs(tables, quarter_key, output_dir):
    """Save extracted tables as quarterly CSVs."""
    quarter_dir = os.path.join(output_dir, 'quarterly', quarter_key)
    os.makedirs(quarter_dir, exist_ok=True)

    saved = 0
    for table in tables:
        category = table['category']
        districts = table['districts']
        headers = table['headers']

        if not districts:
            continue

        # Same disambiguation as build_complete_json, so the quarterly CSV is
        # self-describing and future runs stay consistent with complete.json.
        snake_headers = disambiguate_headers([to_snake_case(h) for h in headers])
        csv_path = os.path.join(quarter_dir, f"{category}.csv")

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['district'] + snake_headers)

            for district in ODISHA_DISTRICTS:
                if district in districts:
                    row = [district] + districts[district]
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
        print(f"  No district-wise tables found in {pdf_path}")
        return None

    print(f"\n  Extracted {len(tables)} district-wise tables")

    quarter_key, period_name, as_on_date = detect_quarter(pdf_path, tables)
    if not quarter_key:
        print(f"  Could not detect quarter from {pdf_path}")
        return None

    print(f"  Quarter: {period_name} (as on {as_on_date})")

    save_quarterly_csvs(tables, quarter_key, output_dir)

    return (quarter_key, period_name, as_on_date, tables)


# Trailing segments on an anchor column that name a sub-measure rather than the
# category itself — stripped when forming the base for a repeated sub-column, so
# `branches_rural` -> base `branches` -> `branches_semi_urban` (and the base
# matches the fallback names db/regenerate_indicator_files_from_states.py expects).
_ANCHOR_SUFFIX_WORDS = {'t', 'a', 'no', 'amt', 'pct', 'rural', 'urban'}


def disambiguate_headers(headers):
    """Make a header list unique WITHOUT losing columns.

    SLBC merged-header tables repeat sub-column labels (`a`/`pct` for
    target/achievement/%, or `semi_urban`/`urban` under branches/BC/ATMs). Those
    bare repeats used to collapse in build_complete_json's per-district dict —
    every duplicate key overwrote the last, keeping only the final (grand-total)
    value and silently dropping every per-subcategory value (~20k cells for
    Odisha alone). Bind each repeat to the base of its nearest preceding UNIQUE
    column instead: [branches_rural, semi_urban, urban, total_branches, ...] ->
    [branches_rural, branches_semi_urban, branches_urban, total_branches, ...].
    Lossless, and the derived names match the indicator regenerator's fallbacks.
    """
    from collections import Counter
    cnt = Counter(h for h in headers if h)
    seen = Counter()
    out, used = [], set()
    for i, h in enumerate(headers):
        if not h or cnt[h] == 1:
            out.append(h)
            used.add(h)
            continue
        seen[h] += 1
        anchor = None
        for j in range(i - 1, -1, -1):
            if headers[j] and cnt[headers[j]] == 1:
                anchor = headers[j]
                break
        if anchor:
            segs = anchor.split('_')
            base = ('_'.join(segs[:-1])
                    if len(segs) > 1 and segs[-1] in _ANCHOR_SUFFIX_WORDS else anchor)
            name = f'{base}_{h}'
        else:
            # No category column to bind to (e.g. Odisha's sarfaesi CSV, which is
            # two side-by-side tables merged by the extractor). Suffix by
            # occurrence so NO bare name survives with a silently-flipped
            # meaning — both values are recovered under h_1, h_2, ...
            name = f'{h}_{seen[h]}'
        cand, k = name, 2
        while cand in used:
            cand = f'{name}_{k}'
            k += 1
        out.append(cand)
        used.add(cand)
    return out


def build_complete_json(all_quarters, output_dir):
    """Build and save odisha_complete.json from all extracted quarters."""
    complete = {
        "source": "SLBC Odisha",
        "state": "Odisha",
        "convenor": "UCO Bank",
        "description": "Complete district-wise banking & financial inclusion data",
        "amount_unit": "Rs. Crore (ACP, advances) / Rs. Lakh (some schemes)",
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
            # Disambiguate BEFORE keying the per-district dict, or repeated
            # sub-column names collapse and drop every value but the last.
            snake_headers = disambiguate_headers([to_snake_case(h) for h in headers])

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

    json_path = os.path.join(output_dir, 'odisha_complete.json')
    with open(json_path, 'w') as f:
        json.dump(complete, f, indent=2)

    print(f"\nSaved odisha_complete.json ({len(complete['quarters'])} quarters)")
    return complete


def build_timeseries(complete, output_dir):
    """Build and save odisha_fi_timeseries.json and .csv."""
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
        for d in ODISHA_DISTRICTS:
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
        "source": "SLBC Odisha",
        "state": "Odisha",
        "description": "Odisha district-wise financial inclusion timeseries data",
        "num_periods": len(periods),
        "total_records": sum(len(p['districts']) for p in periods),
        "periods": periods,
    }

    json_path = os.path.join(output_dir, 'odisha_fi_timeseries.json')
    with open(json_path, 'w') as f:
        json.dump(timeseries, f, indent=2)
    print(f"Saved odisha_fi_timeseries.json ({len(periods)} periods, {timeseries['total_records']} records)")

    # Save CSV (wide format)
    sorted_fields = sorted(all_fields)
    csv_path = os.path.join(output_dir, 'odisha_fi_timeseries.csv')
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

    print(f"Saved odisha_fi_timeseries.csv")
    return timeseries


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python extract_odisha.py <pdf1> [pdf2] ... [--output-dir DIR]")
        print("  python extract_odisha.py --all  (process all PDFs in current dir)")
        print()
        print("Example:")
        print("  python extract_odisha.py Agenda-of-182nd-SLBC-Meeting.pdf")
        print("  python extract_odisha.py --all --output-dir ../../public/slbc-data/odisha")
        sys.exit(1)

    pdf_paths = []
    output_dir = '../../public/slbc-data/odisha'
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
        pdf_paths = sorted(glob.glob('*.pdf') + glob.glob('*.PDF'))
        if not pdf_paths:
            print("No PDF files found in current directory")
            sys.exit(1)

    print(f"Processing {len(pdf_paths)} PDF(s)")
    print(f"Output directory: {output_dir}")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'quarterly'), exist_ok=True)

    all_quarters = {}

    for pdf_path in pdf_paths:
        if not os.path.exists(pdf_path):
            print(f"Warning: {pdf_path} not found, skipping")
            continue

        try:
            result = process_single_pdf(pdf_path, output_dir)
        except Exception as e:
            print(f"  ERROR processing {pdf_path}: {e}")
            import traceback
            traceback.print_exc()
            result = None

        if result:
            quarter_key, period_name, as_on_date, tables = result
            if quarter_key in all_quarters:
                existing = all_quarters[quarter_key]['tables']
                existing_cats = {t['category'] for t in existing}
                for t in tables:
                    if t['category'] not in existing_cats:
                        existing.append(t)
                    else:
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

    print(f"\n{'='*70}")
    print("Building combined output files")
    print(f"{'='*70}")

    complete = build_complete_json(all_quarters, output_dir)
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
    print(f"  Districts: {len(ODISHA_DISTRICTS)}")
    all_cats = set()
    for qd in all_quarters.values():
        for t in qd['tables']:
            all_cats.add(t['category'])
    print(f"  Total categories: {len(all_cats)}")
    print(f"  Categories: {', '.join(sorted(all_cats))}")
    print(f"\nOutput files:")
    print(f"  {output_dir}/odisha_complete.json")
    print(f"  {output_dir}/odisha_fi_timeseries.json")
    print(f"  {output_dir}/odisha_fi_timeseries.csv")
    print(f"  {output_dir}/quarterly/*/  (per-quarter CSVs)")


if __name__ == '__main__':
    main()
