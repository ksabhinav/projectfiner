#!/usr/bin/env python3
"""
Extract district-wise data from Kerala SLBC annexure PDFs.
Produces kerala_complete.json in the project's standard format.
"""

import os, json, re, glob
import pdfplumber

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE_DIR, "kerala/pdfs")
OUT_JSON = os.path.join(BASE_DIR, "kerala/kerala_complete.json")

# Kerala districts (14)
KERALA_DISTRICTS = [
    "TRIVANDRUM", "KOLLAM", "PATHANAMTHITTA", "ALAPPUZHA", "KOTTAYAM",
    "IDUKKI", "ERNAKULAM", "THRISSUR", "PALAKKAD", "MALAPPURAM",
    "KOZHIKODE", "WAYANAD", "KANNUR", "KASARGOD"
]

def quarter_metadata(qkey):
    year, month = qkey.split("-")
    year = int(year)
    month_num = int(month)
    month_names = {3: "March", 6: "June", 9: "September", 12: "December"}
    last_days = {3: 31, 6: 30, 9: 30, 12: 31}
    if month_num <= 3:
        fy = f"{year-1}-{str(year)[2:]}"
    else:
        fy = f"{year}-{str(year+1)[2:]}"
    return {
        "period": f"{month_names[month_num]} {year}",
        "as_on_date": f"{last_days[month_num]:02d}-{month_num:02d}-{year}",
        "fy": fy,
    }


def is_district_row(row):
    """Check if a table row contains a district name."""
    if not row or len(row) < 2:
        return False
    for cell in row[:3]:
        if cell:
            cell_upper = cell.strip().upper()
            for d in KERALA_DISTRICTS:
                if d in cell_upper:
                    return True
    return False


def get_district_name(row):
    """Extract district name from a row."""
    for cell in row[:3]:
        if cell:
            cell_upper = cell.strip().upper()
            for d in KERALA_DISTRICTS:
                if d in cell_upper:
                    return d.title()
    return None


def extract_tables_from_pdf(pdf_path):
    """Extract all tables from a PDF, returning list of (title, headers, rows)."""
    pdf = pdfplumber.open(pdf_path)
    results = []

    current_title = ""
    current_headers = []
    current_rows = []
    current_page_title = ""

    for page_num, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        lines = text.split("\n")

        # Get page title (first line with annexure number)
        page_title = ""
        for line in lines[:3]:
            line = line.strip()
            if re.match(r'^\d+\.\d+', line) or "DISTRICT" in line.upper():
                page_title = line
                break

        # Extract tables
        tables = page.extract_tables()
        if not tables:
            continue

        for table in tables:
            if not table or len(table) < 2:
                continue

            # Check if any row has district data
            has_district = any(is_district_row(row) for row in table)
            if not has_district:
                continue

            # Find header row (row before first district row)
            header_idx = 0
            for i, row in enumerate(table):
                if is_district_row(row):
                    header_idx = max(0, i - 1)
                    break

            headers = [str(c).strip() if c else "" for c in table[header_idx]]

            # Extract district rows
            for row in table[header_idx + 1:]:
                if not row:
                    continue
                clean_row = [str(c).strip() if c else "" for c in row]
                district = get_district_name(clean_row)
                if district:
                    results.append((page_title or current_page_title, headers, district, clean_row))

        if page_title:
            current_page_title = page_title

    pdf.close()
    return results


def categorize_table(title):
    """Map a table title to a category name."""
    title_upper = title.upper()
    mappings = [
        ("ANNUAL CREDIT PLAN", "acp_achievement"),
        ("CROP LOAN", "crop_loan"),
        ("TERM LOAN", "term_loan"),
        ("MINORITIES", "minority_credit"),
        ("KISAN CREDIT", "kcc"),
        ("KCC", "kcc"),
        ("EDUCATION LOAN", "education_loan"),
        ("WOMEN", "women_finance"),
        ("SHG", "shg"),
        ("JLG", "jlg"),
        ("MICRO FINANCE", "micro_finance"),
        ("MUDRA", "pmmy_mudra"),
        ("PMMY", "pmmy_mudra"),
        ("PMEGP", "pmegp"),
        ("NRLM", "nrlm"),
        ("NULM", "nulm"),
        ("PMAY", "pmay"),
        ("HOUSING", "housing"),
        ("ATM", "atm_network"),
        ("BRANCH", "branch_network"),
        ("DEPOSIT", "deposits"),
        ("ADVANCE", "advances"),
        ("CD RATIO", "cd_ratio"),
        ("PRIORITY SECTOR", "priority_sector"),
        ("AGRICULTURE", "agriculture"),
        ("MSME", "msme"),
        ("SC/ST", "sc_st"),
        ("GOLD LOAN", "gold_loan"),
        ("NPA", "npa"),
        ("RECOVERY", "recovery"),
        ("RSETI", "rseti"),
        ("STAND UP", "stand_up_india"),
        ("JAN SURAKSHA", "jan_suraksha"),
        ("PMJDY", "pmjdy"),
        ("AADHAAR", "aadhaar"),
        ("CDM", "cdm"),
        ("FOREIGN EXCHANGE", "forex"),
    ]
    for keyword, category in mappings:
        if keyword in title_upper:
            return category
    return "uncategorized"


def process_pdf(pdf_path, quarter_key):
    """Process a single PDF and return category → district → {field: value} data."""
    print(f"  Processing {os.path.basename(pdf_path)} ({quarter_key})...")

    try:
        rows = extract_tables_from_pdf(pdf_path)
    except Exception as e:
        print(f"    ERROR: {e}")
        return {}

    if not rows:
        print(f"    No district-level data found")
        return {}

    # Group by category
    categories = {}
    for title, headers, district, row_data in rows:
        category = categorize_table(title)

        if category not in categories:
            categories[category] = {"fields": [], "districts": {}}

        # Store headers if not set
        if not categories[category]["fields"]:
            categories[category]["fields"] = headers

        # Store district data
        dist_dict = {}
        for h, v in zip(headers, row_data):
            if h:
                dist_dict[h] = v
        dist_dict["District"] = district
        categories[category]["districts"][district] = dist_dict

    # Finalize
    for cat in categories:
        categories[cat]["num_districts"] = len(categories[cat]["districts"])
        if "District" not in categories[cat]["fields"]:
            categories[cat]["fields"] = ["District"] + categories[cat]["fields"]

    districts_found = set()
    for cat_data in categories.values():
        districts_found.update(cat_data["districts"].keys())

    print(f"    Found {len(categories)} categories, {len(districts_found)} districts")
    return categories


def main():
    # Find all PDFs
    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    if not pdfs:
        print("No PDFs found!")
        return

    print(f"Found {len(pdfs)} PDFs")

    # Build complete JSON
    data = {
        "source": "SLBC Kerala (State Level Bankers' Committee, Kerala)",
        "state": "Kerala",
        "amount_unit": "Rs. Lakhs",
        "quarters": {},
    }

    for pdf_path in pdfs:
        fname = os.path.basename(pdf_path)
        # Extract quarter key from filename (format: 2024-12_SLBC145_Dec2024.pdf)
        match = re.match(r'(\d{4}-\d{2})_', fname)
        if not match:
            print(f"  Skipping {fname} (no quarter key)")
            continue
        qkey = match.group(1)

        categories = process_pdf(pdf_path, qkey)
        if not categories:
            continue

        meta = quarter_metadata(qkey)
        data["quarters"][qkey] = {
            "period": meta["period"],
            "as_on_date": meta["as_on_date"],
            "fy": meta["fy"],
            "tables": categories,
        }

    # Sort quarters
    data["quarters"] = dict(sorted(data["quarters"].items()))

    # Write JSON
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total_cats = sum(len(q["tables"]) for q in data["quarters"].values())
    print(f"\nDone! {len(data['quarters'])} quarters, {total_cats} category-quarter combos")
    print(f"Output: {OUT_JSON}")


if __name__ == "__main__":
    main()
