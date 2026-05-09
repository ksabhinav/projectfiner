#!/usr/bin/env python3
"""
Extract district-wise tables from West Bengal SLBC meeting PDFs.

Produces:
  - west-bengal_complete.json   (master JSON with all quarters and indicators)
  - west-bengal_fi_timeseries.json (timeseries for FI map)
  - west-bengal_fi_timeseries.csv  (wide-format CSV)
  - quarterly/{YYYY-MM}/         (per-quarter CSVs)
  - raw-csv/                     (flat CSVs by category)

Usage: python3 extract_wb.py
"""

import pdfplumber
import json
import csv
import os
import re
import sys
from collections import defaultdict

# ── West Bengal Districts (23 districts) ──
WB_DISTRICTS = [
    "Alipurduar", "Bankura", "Birbhum", "Cooch Behar", "Dakshin Dinajpur",
    "Darjeeling", "Hooghly", "Howrah", "Jalpaiguri", "Jhargram", "Kalimpong",
    "Kolkata", "Malda", "Murshidabad", "Nadia", "North 24 Parganas",
    "Paschim Bardhaman", "Paschim Medinipur", "Purba Bardhaman",
    "Purba Medinipur", "Purulia", "South 24 Parganas", "Uttar Dinajpur"
]

# Canonical lowercase lookup
DISTRICT_CANONICAL = {d.lower(): d for d in WB_DISTRICTS}

# Common aliases found in PDFs
DISTRICT_ALIASES = {
    "coochbehar": "Cooch Behar",
    "cooch-behar": "Cooch Behar",
    "koch behar": "Cooch Behar",
    "dakshindinajpur": "Dakshin Dinajpur",
    "d. dinajpur": "Dakshin Dinajpur",
    "s. dinajpur": "Dakshin Dinajpur",
    "south dinajpur": "Dakshin Dinajpur",
    "uttardinajpur": "Uttar Dinajpur",
    "u. dinajpur": "Uttar Dinajpur",
    "north dinajpur": "Uttar Dinajpur",
    "n. 24 parganas": "North 24 Parganas",
    "n.24 parganas": "North 24 Parganas",
    "north 24parganas": "North 24 Parganas",
    "north24 parganas": "North 24 Parganas",
    "n. 24 pgs": "North 24 Parganas",
    "north 24 pgs": "North 24 Parganas",
    "s. 24 parganas": "South 24 Parganas",
    "s.24 parganas": "South 24 Parganas",
    "south 24parganas": "South 24 Parganas",
    "south24 parganas": "South 24 Parganas",
    "s. 24 pgs": "South 24 Parganas",
    "south 24 pgs": "South 24 Parganas",
    "paschimbardhaman": "Paschim Bardhaman",
    "p. bardhaman": "Paschim Bardhaman",
    "paschim burdwan": "Paschim Bardhaman",
    "west burdwan": "Paschim Bardhaman",
    "burdwan (w)": "Paschim Bardhaman",
    "purbabardhaman": "Purba Bardhaman",
    "p. bardhaman (e)": "Purba Bardhaman",
    "purba burdwan": "Purba Bardhaman",
    "east burdwan": "Purba Bardhaman",
    "burdwan (e)": "Purba Bardhaman",
    "paschimmedinipur": "Paschim Medinipur",
    "p. medinipur": "Paschim Medinipur",
    "west medinipur": "Paschim Medinipur",
    "paschim midnapore": "Paschim Medinipur",
    "west midnapore": "Paschim Medinipur",
    "purbamedinipur": "Purba Medinipur",
    "purba midnapore": "Purba Medinipur",
    "east medinipur": "Purba Medinipur",
    "east midnapore": "Purba Medinipur",
    "e. medinipur": "Purba Medinipur",
    "midnapore (w)": "Paschim Medinipur",
    "midnapore (e)": "Purba Medinipur",
    "medinipur (w)": "Paschim Medinipur",
    "medinipur (e)": "Purba Medinipur",
    "barddhaman": "Purba Bardhaman",  # old undivided name
    "burdwan": "Purba Bardhaman",
    "midnapore": "Paschim Medinipur",  # old undivided name
    "medinipur": "Paschim Medinipur",
    # Variants found in 171st SLBC
    "24 paraganas north": "North 24 Parganas",
    "24 paraganas south": "South 24 Parganas",
    "24 pgs. (n)": "North 24 Parganas",
    "24 pgs. (s)": "South 24 Parganas",
    "24 pgs (n)": "North 24 Parganas",
    "24 pgs (s)": "South 24 Parganas",
    "n-24 parganas": "North 24 Parganas",
    "s-24 parganas": "South 24 Parganas",
    "n.24 pgs": "North 24 Parganas",
    "s.24 pgs": "South 24 Parganas",
    "dinajpur dakshin": "Dakshin Dinajpur",
    "dinajpur uttar": "Uttar Dinajpur",
    "dakshin dinajpur": "Dakshin Dinajpur",
    "medinipur east": "Purba Medinipur",
    "medinipur west": "Paschim Medinipur",
    "paschim bardhaman": "Paschim Bardhaman",
    "purba bardhaman": "Purba Bardhaman",
    "purba burdwan": "Purba Bardhaman",
    "paschim burdwan": "Paschim Bardhaman",
    "coochbehar": "Cooch Behar",
    "cooch behar": "Cooch Behar",
    "24 parganas north": "North 24 Parganas",
    "24 parganas south": "South 24 Parganas",
}

# ── Meeting to Quarter mapping ──
# Each SLBC meeting reviews data for the quarter BEFORE the meeting date
MEETING_TO_QUARTER = {
    "171st": "December 2025",
    "170th": "September 2025",
    "169th": "June 2025",
    "168th": "March 2025",
    "167th": "December 2024",
    "166th": "September 2024",
    "165th": "June 2024",
    "164th": "March 2024",
    "163rd": "December 2023",
    # 162nd PDF not available
    "161st": "June 2023",
    "160th": "March 2023",
    "159th": "December 2022",
    "158th": "September 2022",
    "157th": "June 2022",
    "156th": "March 2022",
    "155th": "December 2021",
    "154th": "September 2021",
    "153rd": "June 2021",
    "152nd": "March 2021",
    "151st": "December 2020",
    "150th": "September 2020",
    "149th": "March 2020",
    "148th": "December 2019",
    "147th": "September 2019",
    "146th": "June 2019",
    "145th": "March 2019",
    "144th": "December 2018",
    "143rd": "September 2018",
    "142nd": "June 2018",
    "141st": "March 2018",
    "140th": "December 2017",
    "139th": "September 2017",
    "138th": "June 2017",
    "137th": "March 2017",
    "136th": "December 2016",
    "135th": "September 2016",
    "134th": "June 2016",
    "133rd": "March 2016",
    "132nd": "December 2015",
    "131st": "September 2015",
    "130th": "June 2015",
}

# ── Category detection rules ──
# (keyword_in_title, category_name, priority)
# Higher priority wins when multiple rules match
CATEGORY_RULES = [
    # CD Ratio
    (r'cd\s*ratio', 'credit_deposit_ratio', 10),
    (r'credit.deposit\s*ratio', 'credit_deposit_ratio', 10),
    (r'advance.*deposit.*trend', 'credit_deposit_ratio', 8),

    # Branch Network
    (r'branch\s*network', 'branch_network', 10),
    (r'brick.*mortar.*branch', 'branch_network', 8),
    (r'atm\s*network', 'branch_network', 7),

    # KCC (Kisan Credit Card)
    (r'kcc\s*position', 'kcc', 10),
    (r'kisan\s*credit\s*card', 'kcc', 10),
    (r'progress\s*in\s*kcc', 'kcc', 9),
    (r'kcc\s*disburs', 'kcc', 9),
    (r'kcc.*animal\s*husbandry', 'kcc_animal_husbandry', 11),
    (r'kcc.*fishery', 'kcc_fishery', 11),

    # Priority Sector / ACP
    (r'priority\s*sector.*acp', 'acp_priority_sector', 10),
    (r'acp\s*target.*achievement', 'acp_priority_sector', 9),
    (r'annual\s*credit\s*plan', 'acp_priority_sector', 9),
    (r'achievement.*acp', 'acp_priority_sector', 8),

    # AIF (Agriculture Infrastructure Fund)
    (r'agriculture\s*infrastructure\s*fund', 'aif', 10),
    (r'aif\s*district', 'aif', 10),

    # MUDRA
    (r'mudra\s*loan', 'mudra', 10),
    (r'mudra', 'mudra', 7),

    # MSME
    (r'msme\s*cluster', 'msme', 10),
    (r'msme\s*credit', 'msme', 9),

    # PMEGP
    (r'pmegp', 'pmegp', 10),

    # SHG / NRLM
    (r'shg.*nrlm|nrlm.*shg', 'shg_nrlm', 10),
    (r'shg\s*credit\s*linkage', 'shg_nrlm', 9),
    (r'self\s*help\s*group', 'shg_nrlm', 8),
    (r'nrlm', 'shg_nrlm', 8),
    (r'day.*nrlm', 'shg_nrlm', 9),

    # NULM
    (r'nulm', 'shg_nulm', 10),

    # JLG
    (r'joint\s*liability\s*group|jlg', 'jlg', 10),

    # PMFME
    (r'pmfme', 'pmfme', 10),

    # Education Loan
    (r'education\s*loan', 'education_loan', 10),

    # Housing Loan
    (r'housing\s*loan', 'housing_loan', 10),

    # NPA & Recovery
    (r'npa.*recovery|recovery.*npa', 'npa_recovery', 10),
    (r'sarfaesi', 'sarfaesi', 10),

    # Digital Payments / Digital Transactions
    (r'digital\s*payment', 'digital_transactions', 10),
    (r'digital\s*transaction', 'digital_transactions', 9),
    (r'payment\s*ecosystem', 'digital_transactions', 8),
    (r'digital\s*coverage', 'digital_transactions', 9),

    # PMJDY
    (r'pmjdy', 'pmjdy', 10),
    (r'jan\s*dhan\s*yojana', 'pmjdy', 10),

    # Social Security Schemes
    (r'social\s*security', 'social_security_schemes', 10),
    (r'pmjjby|pmsby', 'social_security_schemes', 9),

    # APY (Atal Pension Yojana)
    (r'atal\s*pension|apy', 'apy', 10),

    # Financial Inclusion / FLC
    (r'financial\s*inclusion', 'financial_inclusion', 7),
    (r'financial\s*literacy', 'financial_literacy', 10),
    (r'flc\s*camp|camp.*flc', 'financial_literacy', 9),

    # RSETI
    (r'rseti', 'rseti', 10),

    # SVSKP / Livelihood
    (r'svskp|swarnajaynti', 'svskp', 10),

    # PMMY (PM Mudra Yojana)
    (r'pmmy', 'mudra', 8),

    # Weaker Section
    (r'weaker\s*section', 'weaker_section', 10),

    # Farm sector / Non-farm
    (r'farm\s*sector', 'farm_sector', 8),
    (r'non.farm', 'non_farm_sector', 8),

    # NLM (National Livestock Mission)
    (r'national\s*livestock|nlm', 'nlm', 10),
]


def normalize_district(name):
    """Normalize district name to canonical form."""
    if not name:
        return None
    name = name.strip()

    low = name.lower().strip()

    # Try matching BEFORE stripping serial numbers (e.g. "24 Paraganas North" has "24" as part of name)
    if low in DISTRICT_CANONICAL:
        return DISTRICT_CANONICAL[low]
    if low in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[low]
    compressed = re.sub(r'\s+', ' ', low)
    if compressed in DISTRICT_CANONICAL:
        return DISTRICT_CANONICAL[compressed]
    if compressed in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[compressed]

    # Remove leading serial number like "1.", "23)", "1 " etc.
    stripped = re.sub(r'^\d+[\.\)\s]+', '', name).strip()
    if stripped and stripped != name:
        low2 = stripped.lower().strip()
        if low2 in DISTRICT_CANONICAL:
            return DISTRICT_CANONICAL[low2]
        if low2 in DISTRICT_ALIASES:
            return DISTRICT_ALIASES[low2]
        compressed2 = re.sub(r'\s+', ' ', low2)
        if compressed2 in DISTRICT_CANONICAL:
            return DISTRICT_CANONICAL[compressed2]
        if compressed2 in DISTRICT_ALIASES:
            return DISTRICT_ALIASES[compressed2]

    # Try partial match (for truncated names in narrow columns)
    check_low = stripped.lower().strip() if stripped else low
    for canon_low, canon in DISTRICT_CANONICAL.items():
        if len(check_low) >= 5 and (canon_low.startswith(check_low) or check_low.startswith(canon_low)):
            return canon

    return None


def to_snake(s):
    """Convert header text to snake_case field name."""
    if not s:
        return ''
    s = s.strip()
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\s+', '_', s.strip())
    s = s.lower()
    s = re.sub(r'_+', '_', s).strip('_')
    return s


def parse_number(val):
    """Parse a number from a table cell, handling commas and parentheses."""
    if not val:
        return None
    val = str(val).strip()
    if not val or val in ('-', '--', 'NA', 'N/A', 'nil', 'NIL', '*', ''):
        return None

    # Handle negative in parentheses: (123) → -123
    neg = False
    if val.startswith('(') and val.endswith(')'):
        val = val[1:-1]
        neg = True

    # Remove commas
    val = val.replace(',', '')

    # Remove % sign
    val = val.replace('%', '').strip()

    # Handle + and - prefixes
    val = val.strip('+').strip()

    try:
        num = float(val)
        return -num if neg else num
    except ValueError:
        return None


def classify_table(title_text, fields=None):
    """Classify a table into a category based on title and fields."""
    if not title_text:
        return 'unknown'

    title_low = title_text.lower()

    best_cat = 'unknown'
    best_priority = -1

    for pattern, category, priority in CATEGORY_RULES:
        if re.search(pattern, title_low) and priority > best_priority:
            best_cat = category
            best_priority = priority

    return best_cat


def extract_table_from_page(pdf, page_idx):
    """Extract tables from a page, returning list of (title, headers, rows) tuples."""
    page = pdf.pages[page_idx]
    page_text = page.extract_text() or ''
    tables = page.extract_tables()

    results = []

    for table in tables:
        if not table or len(table) < 3:
            continue

        # Find title row(s) and header row(s)
        # Title rows typically have text in first cell, rest empty/None
        title_parts = []
        header_row_idx = None

        for ri, row in enumerate(table):
            non_empty = [c for c in row if c and str(c).strip()]
            if len(non_empty) <= 2 and ri < 4:
                # Likely a title/subtitle row
                title_parts.append(' '.join(str(c) for c in row if c and str(c).strip()))
            elif len(non_empty) >= 3:
                # This looks like a header or data row
                header_row_idx = ri
                break

        if header_row_idx is None:
            continue

        title = ' '.join(title_parts).strip()

        # Determine if header_row_idx is headers or if we need to merge
        header_row = table[header_row_idx]

        # Check if next row is also a sub-header (e.g., "No." "Amount" under merged cells)
        sub_header = None
        data_start = header_row_idx + 1
        if data_start < len(table):
            next_row = table[data_start]
            next_non_empty = [c for c in next_row if c and str(c).strip()]
            # If it looks like sub-headers (short labels, no district names)
            if next_non_empty and all(len(str(c).strip()) < 30 for c in next_non_empty if c):
                has_district = any(normalize_district(str(c)) for c in next_non_empty if c)
                if not has_district:
                    sub_header = next_row
                    data_start += 1

        # Build field names from headers
        fields = []
        for ci, cell in enumerate(header_row):
            h = str(cell).strip() if cell else ''
            # Replace newlines
            h = re.sub(r'\n+', ' ', h)
            if sub_header and ci < len(sub_header) and sub_header[ci]:
                sub = str(sub_header[ci]).strip()
                sub = re.sub(r'\n+', ' ', sub)
                if sub and sub != h:
                    h = f"{h} {sub}" if h else sub
            fields.append(to_snake(h))

        # Extract data rows — find district column
        district_col = None
        for ci, f in enumerate(fields):
            if 'district' in f or 'name' in f:
                district_col = ci
                break

        # If no obvious district column, check first few data rows
        if district_col is None:
            for ci in range(min(3, len(fields))):
                for ri in range(data_start, min(data_start + 5, len(table))):
                    cell = table[ri][ci] if ci < len(table[ri]) else None
                    if cell and normalize_district(str(cell)):
                        district_col = ci
                        break
                if district_col is not None:
                    break

        if district_col is None:
            continue

        # Extract district data
        district_data = {}
        for ri in range(data_start, len(table)):
            row = table[ri]
            if district_col >= len(row):
                continue

            raw_name = str(row[district_col]).strip() if row[district_col] else ''
            district = normalize_district(raw_name)
            if not district:
                # Check if it's a total/summary row
                if any(kw in raw_name.lower() for kw in ['total', 'state', 'west bengal', 'grand', 'all']):
                    district = 'STATE_TOTAL'
                else:
                    continue

            values = {}
            for ci, field in enumerate(fields):
                if ci == district_col or not field:
                    continue
                if ci >= len(row):
                    continue
                val = parse_number(row[ci])
                if val is not None:
                    values[field] = val

            if values:
                district_data[district] = values

        if len(district_data) >= 3:  # At least 3 districts
            category = classify_table(title, fields)
            # If title didn't classify, try page text
            if category == 'unknown' and page_text:
                category = classify_table(page_text[:500], fields)
            results.append({
                'title': title,
                'category': category,
                'fields': [f for f in fields if f and f != to_snake(str(header_row[district_col]) if header_row[district_col] else '')],
                'districts': district_data,
            })

    return results


def extract_meeting(pdf_path, meeting_num, quarter):
    """Extract all district-wise tables from a single meeting PDF."""
    print(f"  Extracting {meeting_num} ({quarter})...")

    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        print(f"    ERROR opening PDF: {e}")
        return {}

    all_tables = {}

    for page_idx in range(len(pdf.pages)):
        try:
            page_tables = extract_table_from_page(pdf, page_idx)
            for tbl in page_tables:
                cat = tbl['category']
                # If we already have this category, check if it's the same table continuing
                # or a genuinely different table
                if cat in all_tables:
                    existing = all_tables[cat]
                    # Check field overlap — if fields are very different, it's a new table
                    existing_fields = set(existing['fields'])
                    new_fields = set(tbl['fields'])
                    overlap = existing_fields & new_fields
                    # If >50% field overlap or one set is subset of other, merge (continuation)
                    if overlap and (len(overlap) >= 0.5 * min(len(existing_fields), len(new_fields))):
                        # Merge districts (continuation of same table)
                        for dist, vals in tbl['districts'].items():
                            if dist not in existing['districts']:
                                existing['districts'][dist] = vals
                            else:
                                existing['districts'][dist].update(vals)
                        for f in tbl['fields']:
                            if f not in existing['fields']:
                                existing['fields'].append(f)
                    else:
                        # Different table, same category — add with suffix
                        suffix = 2
                        new_cat = f"{cat}_{suffix}"
                        while new_cat in all_tables:
                            suffix += 1
                            new_cat = f"{cat}_{suffix}"
                        all_tables[new_cat] = {
                            'fields': tbl['fields'],
                            'districts': tbl['districts'],
                        }
                else:
                    all_tables[cat] = {
                        'fields': tbl['fields'],
                        'districts': tbl['districts'],
                    }
        except Exception as e:
            pass  # Skip problematic pages

    pdf.close()

    # Remove STATE_TOTAL from district data and unknown category
    for cat in list(all_tables.keys()):
        if cat == 'unknown':
            del all_tables[cat]
            continue
        all_tables[cat]['districts'].pop('STATE_TOTAL', None)
        # Remove serial number fields
        for field in ['sr_no', 'sl_no', 'sl', 'sr', 's_no', 'sno']:
            if field in all_tables[cat]['fields']:
                all_tables[cat]['fields'].remove(field)
            for dist in all_tables[cat]['districts']:
                all_tables[cat]['districts'][dist].pop(field, None)

    # Stats
    n_cats = len(all_tables)
    n_dists = max((len(t['districts']) for t in all_tables.values()), default=0)
    print(f"    → {n_cats} categories, up to {n_dists} districts")

    return all_tables


def quarter_to_key(quarter):
    """Convert 'September 2025' to 'september_2025'."""
    return quarter.lower().replace(' ', '_')


def quarter_to_folder(quarter):
    """Convert 'September 2025' to '2025-09'."""
    months = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    parts = quarter.split()
    month = months.get(parts[0].lower(), '00')
    year = parts[1]
    return f"{year}-{month}"


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # ── Phase 1: Extract all tables from all PDFs ──
    print("Phase 1: Extracting tables from PDFs...")

    all_quarters = {}

    for meeting, quarter in sorted(MEETING_TO_QUARTER.items(), key=lambda x: x[1]):
        pdf_path = os.path.join(base_dir, f"{meeting}_agenda.pdf")
        if not os.path.exists(pdf_path):
            print(f"  SKIP {meeting} — PDF not found")
            continue

        tables = extract_meeting(pdf_path, meeting, quarter)
        if tables:
            qkey = quarter_to_key(quarter)
            all_quarters[qkey] = {
                'period': quarter,
                'tables': {}
            }
            for cat, data in tables.items():
                all_quarters[qkey]['tables'][cat] = {
                    'fields': data['fields'],
                    'districts': {d: {k: str(v) for k, v in vals.items()}
                                  for d, vals in data['districts'].items()}
                }

    print(f"\nExtracted {len(all_quarters)} quarters total")

    # ── Phase 2: Write _complete.json ──
    print("\nPhase 2: Writing west-bengal_complete.json...")
    complete = {'quarters': all_quarters}
    complete_path = os.path.join(base_dir, 'west-bengal_complete.json')
    with open(complete_path, 'w') as f:
        json.dump(complete, f, indent=2)
    print(f"  Written: {os.path.getsize(complete_path) / 1024:.0f} KB")

    # ── Phase 3: Write timeseries JSON ──
    print("\nPhase 3: Writing west-bengal_fi_timeseries.json...")

    periods = []
    for qkey in sorted(all_quarters.keys(), key=lambda k: quarter_to_folder(all_quarters[k]['period'])):
        q = all_quarters[qkey]
        districts_flat = {}

        for cat, data in q['tables'].items():
            for dist, vals in data['districts'].items():
                if dist not in districts_flat:
                    districts_flat[dist] = {
                        'district': dist,
                        'period': q['period'],
                    }
                for field, value in vals.items():
                    # Prefix field with category
                    key = f"{cat}__{field}"
                    districts_flat[dist][key] = value

        if districts_flat:
            periods.append({
                'period': q['period'],
                'districts': list(districts_flat.values())
            })

    ts_path = os.path.join(base_dir, 'west-bengal_fi_timeseries.json')
    with open(ts_path, 'w') as f:
        json.dump({'periods': periods}, f, indent=2)
    print(f"  Written: {os.path.getsize(ts_path) / 1024:.0f} KB")

    # ── Phase 4: Write quarterly CSVs ──
    print("\nPhase 4: Writing quarterly CSVs...")
    quarterly_dir = os.path.join(base_dir, 'quarterly')
    os.makedirs(quarterly_dir, exist_ok=True)

    csv_count = 0
    for qkey, q in all_quarters.items():
        folder = quarter_to_folder(q['period'])
        q_dir = os.path.join(quarterly_dir, folder)
        os.makedirs(q_dir, exist_ok=True)

        for cat, data in q['tables'].items():
            if not data['districts']:
                continue

            # Get all fields across districts
            all_fields = set()
            for vals in data['districts'].values():
                all_fields.update(vals.keys())
            all_fields = sorted(all_fields)

            csv_path = os.path.join(q_dir, f"{cat}.csv")
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['district'] + all_fields)
                for dist in sorted(data['districts'].keys()):
                    vals = data['districts'][dist]
                    row = [dist] + [vals.get(field, '') for field in all_fields]
                    writer.writerow(row)
            csv_count += 1

    print(f"  Written: {csv_count} CSV files")

    # ── Phase 5: Write raw-csv (flat CSVs by category across all quarters) ──
    print("\nPhase 5: Writing raw-csv...")
    raw_dir = os.path.join(base_dir, 'raw-csv')
    os.makedirs(raw_dir, exist_ok=True)

    # Collect all data by category
    cat_data = defaultdict(list)
    for qkey, q in all_quarters.items():
        for cat, data in q['tables'].items():
            for dist, vals in data['districts'].items():
                row = {'period': q['period'], 'district': dist}
                row.update(vals)
                cat_data[cat].append(row)

    raw_count = 0
    for cat, rows in cat_data.items():
        all_fields = set()
        for row in rows:
            all_fields.update(k for k in row.keys() if k not in ('period', 'district'))
        all_fields = sorted(all_fields)

        csv_path = os.path.join(raw_dir, f"{cat}.csv")
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['period', 'district'] + all_fields)
            for row in sorted(rows, key=lambda r: (r['period'], r['district'])):
                writer.writerow([row['period'], row['district']] + [row.get(f, '') for f in all_fields])
        raw_count += 1

    print(f"  Written: {raw_count} CSV files")

    # ── Phase 6: Write wide-format timeseries CSV ──
    print("\nPhase 6: Writing west-bengal_fi_timeseries.csv...")

    # Collect all (district, period, field) → value
    ts_rows = []
    all_ts_fields = set()
    for period_data in periods:
        for dist_data in period_data['districts']:
            fields = {k: v for k, v in dist_data.items() if k not in ('district', 'period')}
            all_ts_fields.update(fields.keys())
            ts_rows.append(dist_data)

    all_ts_fields = sorted(all_ts_fields)
    ts_csv_path = os.path.join(base_dir, 'west-bengal_fi_timeseries.csv')
    with open(ts_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['district', 'period'] + all_ts_fields)
        for row in sorted(ts_rows, key=lambda r: (r.get('district', ''), r.get('period', ''))):
            writer.writerow([row.get('district', ''), row.get('period', '')] +
                          [row.get(f, '') for f in all_ts_fields])

    print(f"  Written: {os.path.getsize(ts_csv_path) / 1024:.0f} KB")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print(f"  Quarters: {len(all_quarters)}")
    print(f"  Categories: {len(cat_data)}")
    print(f"  Quarterly CSVs: {csv_count}")
    print(f"  Raw CSVs: {raw_count}")

    # Show categories found
    print("\nCategories found:")
    for cat in sorted(cat_data.keys()):
        n_quarters = sum(1 for q in all_quarters.values() if cat in q['tables'])
        n_dists = max(len(q['tables'][cat]['districts']) for q in all_quarters.values() if cat in q['tables'])
        print(f"  {cat}: {n_quarters} quarters, up to {n_dists} districts")


if __name__ == '__main__':
    main()
