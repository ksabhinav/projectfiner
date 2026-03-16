#!/usr/bin/env python3
"""
Extract district-wise data from Tamil Nadu SLBC agenda PDFs.
Produces tamil-nadu/tamilnadu_complete.json in the project's standard format.
"""

import os, json, re, glob
import pdfplumber

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE_DIR, "tamil-nadu/pdfs")
OUT_JSON = os.path.join(BASE_DIR, "tamil-nadu/tamilnadu_complete.json")

# Tamil Nadu districts (38)
TN_DISTRICTS = [
    "ARIYALUR", "CHENGALPATTU", "CHENNAI", "COIMBATORE", "CUDDALORE",
    "DHARMAPURI", "DINDIGUL", "ERODE", "KALLAKURICHI", "KANCHIPURAM",
    "KANNIYAKUMARI", "KARUR", "KRISHNAGIRI", "MADURAI", "MAYILADUTHURAI",
    "NAGAPATTINAM", "NAMAKKAL", "PERAMBALUR", "PUDUKKOTTAI", "RAMANATHAPURAM",
    "RANIPET", "SALEM", "SIVAGANGA", "TENKASI", "THANJAVUR",
    "THE NILGIRIS", "THENI", "THIRUVALLUR", "THIRUVARUR", "TIRUCHIRAPPALLI",
    "TIRUNELVELI", "TIRUPATTUR", "TIRUPPUR", "TIRUVANNAMALAI", "TOOTHUKUDI",
    "VELLORE", "VILLUPURAM", "VIRUDHUNAGAR",
    # Alternate spellings
    "NILGIRIS", "THOOTHUKUDI", "KANYAKUMARI", "TRICHY",
    "TRICHIRAPPALLI", "TIRUCHCHIRAPALLI",
]

DIST_NORMALIZE = {
    "NILGIRIS": "THE NILGIRIS",
    "THOOTHUKUDI": "TOOTHUKUDI",
    "KANYAKUMARI": "KANNIYAKUMARI",
    "TRICHY": "TIRUCHIRAPPALLI",
    "TRICHIRAPPALLI": "TIRUCHIRAPPALLI",
    "TIRUCHCHIRAPALLI": "TIRUCHIRAPPALLI",
}


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
    if not row or len(row) < 2:
        return False
    for cell in row[:3]:
        if cell:
            cell_upper = cell.strip().upper()
            for d in TN_DISTRICTS:
                if d == cell_upper or cell_upper.startswith(d):
                    return True
    return False


def get_district_name(row):
    for cell in row[:3]:
        if cell:
            cell_upper = cell.strip().upper()
            for d in TN_DISTRICTS:
                if d == cell_upper or cell_upper.startswith(d):
                    normalized = DIST_NORMALIZE.get(d, d)
                    return normalized.title()
    return None


def categorize_table(title):
    title_upper = title.upper()
    mappings = [
        ("PRIORITY SECTOR TARGET", "acp_target_achievement"),
        ("ACP", "acp_achievement"),
        ("CD RATIO.*DISTRICT", "cd_ratio"),
        ("CD RATIO", "cd_ratio"),
        ("KCC.*ANIMAL", "kcc_animal_husbandry"),
        ("KCC.*FISH", "kcc_fisheries"),
        ("KCC", "kcc"),
        ("EDUCATION", "education_loan"),
        ("HOUSING", "housing_loan"),
        ("EXPORT CREDIT", "export_credit"),
        ("SHG", "shg"),
        ("PLF.*BULK", "plf_bulk_loan"),
        ("NULM", "nulm"),
        ("NEEDS", "needs"),
        ("UYEGP", "uyegp"),
        ("AABCS", "aabcs"),
        ("PMEGP", "pmegp"),
        ("PMSVANIDHI", "pmsvanidhi"),
        ("PM.*SVANI", "pmsvanidhi"),
        ("TAHDCO", "tahdco"),
        ("CM.*ARAISE", "cm_araise"),
        ("PMMY", "pmmy_mudra"),
        ("MUDRA", "pmmy_mudra"),
        ("PMFME", "pmfme"),
        ("STAND.*UP", "stand_up_india"),
        ("VAZHNDHU", "vazhndhu_kattuvom"),
        ("CGTMSE", "cgtmse"),
        ("RSETI", "rseti"),
        ("PMJDY", "pmjdy"),
        ("JAN.*SURAKSHA", "jan_suraksha"),
        ("APY", "apy"),
        ("SURYA.*GHAR", "pm_surya_ghar"),
        ("BRANCH", "branch_network"),
        ("BANKING NETWORK", "branch_network"),
        ("AGRICULTURE", "agriculture"),
        ("MSME", "msme"),
        ("MINORITY", "minority"),
        ("NPA", "npa"),
    ]
    for keyword, category in mappings:
        if re.search(keyword, title_upper):
            return category
    return "uncategorized"


def extract_district_tables(pdf_path):
    """Extract district-wise tables from a TN agenda PDF."""
    pdf = pdfplumber.open(pdf_path)
    results = []
    in_annexures = False

    for page_num, page in enumerate(pdf.pages):
        text = page.extract_text() or ""

        # Check if we've reached annexures section
        if "ANNEXURE" in text[:200].upper():
            in_annexures = True

        # Get page title
        lines = text.split("\n")
        page_title = ""
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 10 and not line.startswith("Page "):
                page_title = line
                break

        # Only look for district data in annexure pages (or any page with "DISTRICT" in title)
        if not in_annexures and "DISTRICT" not in text[:500].upper():
            continue

        tables = page.extract_tables()
        if not tables:
            continue

        for table in tables:
            if not table or len(table) < 3:
                continue

            has_district = any(is_district_row(row) for row in table)
            if not has_district:
                continue

            # Find header row
            header_idx = 0
            for i, row in enumerate(table):
                if is_district_row(row):
                    header_idx = max(0, i - 1)
                    break

            headers = [str(c).strip() if c else f"col_{j}" for j, c in enumerate(table[header_idx])]

            for row in table[header_idx + 1:]:
                if not row:
                    continue
                clean_row = [str(c).strip() if c else "" for c in row]
                district = get_district_name(clean_row)
                if district:
                    results.append((page_title, headers, district, clean_row))

    pdf.close()
    return results


def process_pdf(pdf_path, quarter_key):
    print(f"  Processing {os.path.basename(pdf_path)} ({quarter_key})...")

    try:
        rows = extract_district_tables(pdf_path)
    except Exception as e:
        print(f"    ERROR: {e}")
        return {}

    if not rows:
        print(f"    No district-level data found")
        return {}

    categories = {}
    for title, headers, district, row_data in rows:
        category = categorize_table(title)

        if category not in categories:
            categories[category] = {"fields": [], "districts": {}}

        if not categories[category]["fields"]:
            categories[category]["fields"] = headers

        dist_dict = {}
        for h, v in zip(headers, row_data):
            if h:
                dist_dict[h] = v
        dist_dict["District"] = district
        categories[category]["districts"][district] = dist_dict

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
    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    if not pdfs:
        print("No PDFs found!")
        return

    print(f"Found {len(pdfs)} PDFs")

    data = {
        "source": "SLBC Tamil Nadu (State Level Bankers' Committee, Tamil Nadu)",
        "state": "Tamil Nadu",
        "amount_unit": "Rs. Crores",
        "quarters": {},
    }

    for pdf_path in pdfs:
        fname = os.path.basename(pdf_path)
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

    data["quarters"] = dict(sorted(data["quarters"].items()))

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total_cats = sum(len(q["tables"]) for q in data["quarters"].values())
    print(f"\nDone! {len(data['quarters'])} quarters, {total_cats} category-quarter combos")
    print(f"Output: {OUT_JSON}")


if __name__ == "__main__":
    main()
