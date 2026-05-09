"""
Extract district-level banking data from Maharashtra SLBC agenda PDFs.
Produces maharashtra_complete.json and maharashtra_fi_timeseries.json.

Source: https://bankofmaharashtra.bank.in/slbc-meetings
Covers 19 district-wise annexure tables across 3 PDFs (168th-170th meetings).
Note: Amounts in Crores (converted to Lakhs for consistency with other states).
       KCC amounts in Lakhs (no conversion needed).
       NWR amounts in Rs Lakhs (168th) or Rs Crore (169th).
"""

import json
import os
import re
import pdfplumber

# 1 Crore = 100 Lakhs
CRORE_TO_LAKH = 100.0

# PDF metadata
PDFS = [
    {
        "file": "168th_sep2025.pdf",
        "quarter_key": "2025-06",
        "period": "June 2025",
        "as_on_date": "30-06-2025",
        "fy": "2025-26",
        "meeting": 168,
    },
    {
        "file": "169th_dec2025.pdf",
        "quarter_key": "2025-09",
        "period": "September 2025",
        "as_on_date": "30-09-2025",
        "fy": "2025-26",
        "meeting": 169,
    },
    {
        "file": "170th_mar2026.pdf",
        "quarter_key": "2025-12",
        "period": "December 2025",
        "as_on_date": "31-12-2025",
        "fy": "2025-26",
        "meeting": 170,
    },
]

# Canonical 36 Maharashtra districts
CANONICAL_DISTRICTS = [
    "Ahmednagar", "Akola", "Amravati", "Beed", "Bhandara", "Buldhana",
    "Chandrapur", "Chhatrapati Sambhajinagar", "Dhule", "Gadchiroli",
    "Gondia", "Hingoli", "Jalgaon", "Jalna", "Kolhapur", "Latur",
    "Mumbai", "Mumbai Suburban", "Nagpur", "Nanded", "Nandurbar",
    "Nashik", "Dharashiv", "Palghar", "Parbhani", "Pune", "Raigad",
    "Ratnagiri", "Sangli", "Satara", "Sindhudurg", "Solapur", "Thane",
    "Wardha", "Washim", "Yavatmal",
]

# District name aliases/fixes
DISTRICT_ALIASES = {
    "MUMBAI SUBURBA": "Mumbai Suburban",
    "MUMBAI SUBURBAN": "Mumbai Suburban",
    "MUMBAI SUB": "Mumbai Suburban",
    "CHHATRAPATI\nSAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "CHHATRAPATI SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "CHHATRAPATI\n SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "CH.SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "CHH.SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "CHHATRAPATI S": "Chhatrapati Sambhajinagar",
    "ALGAON": "Jalgaon",
    "ALNA": "Jalna",
    "AURANGABAD": "Chhatrapati Sambhajinagar",
    "OSMANABAD": "Dharashiv",
    "AHILYANAGAR": "Ahmednagar",
    "AHMEDNAGAR": "Ahmednagar",
    # Truncated names from problematic PDF extraction
    "MEDNAGAR": "Ahmednagar",
    "HMEDNAGAR": "Ahmednagar",
    "OLA": "Akola",
    "KOLA": "Akola",
    "RAVATI": "Amravati",
    "MRAVATI": "Amravati",
    "EED": "Beed",
    "ANDARA": "Bhandara",
    "HANDARA": "Bhandara",
    "LDHANA": "Buldhana",
    "ULDHANA": "Buldhana",
    "NDRAPUR": "Chandrapur",
    "HANDRAPUR": "Chandrapur",
    "ANGABAD": "Chhatrapati Sambhajinagar",
    "RANGABAD": "Chhatrapati Sambhajinagar",
    "HH.SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "ULE": "Dhule",
    "HULE": "Dhule",
    "DCHIROLI": "Gadchiroli",
    "ADCHIROLI": "Gadchiroli",
    "CHIROLI": "Gadchiroli",
    "NDIA": "Gondia",
    "ONDIA": "Gondia",
    "NGOLI": "Hingoli",
    "INGOLI": "Hingoli",
    "LGAON": "Jalgaon",
    "ALGAON": "Jalgaon",
    "LNA": "Jalna",
    "ALNA": "Jalna",
    "LHAPUR": "Kolhapur",
    "OLHAPUR": "Kolhapur",
    "TUR": "Latur",
    "ATUR": "Latur",
    "MBAI": "Mumbai",
    "UMBAI": "Mumbai",
    "MBAI SUBURBAN": "Mumbai Suburban",
    "UMBAI SUBURBAN": "Mumbai Suburban",
    "GPUR": "Nagpur",
    "AGPUR": "Nagpur",
    "NDED": "Nanded",
    "ANDED": "Nanded",
    "NDURBAR": "Nandurbar",
    "ANDURBAR": "Nandurbar",
    "SHIK": "Nashik",
    "ASHIK": "Nashik",
    "NASIK": "Nashik",
    "MANABAD": "Dharashiv",
    "SMANABAD": "Dharashiv",
    "DHARASHIV": "Dharashiv",
    "LGHAR": "Palghar",
    "ALGHAR": "Palghar",
    "RBHANI": "Parbhani",
    "ARBHANI": "Parbhani",
    "NE": "Pune",
    "UNE": "Pune",
    "IGAD": "Raigad",
    "AIGAD": "Raigad",
    "TNAGIRI": "Ratnagiri",
    "ATNAGIRI": "Ratnagiri",
    "NGLI": "Sangli",
    "ANGLI": "Sangli",
    "TARA": "Satara",
    "ATARA": "Satara",
    "NDHUDURG": "Sindhudurg",
    "INDHUDURG": "Sindhudurg",
    "LAPUR": "Solapur",
    "OLAPUR": "Solapur",
    "ANE": "Thane",
    "HANE": "Thane",
    "RDHA": "Wardha",
    "ARDHA": "Wardha",
    "SHIM": "Washim",
    "ASHIM": "Washim",
    "VATMAL": "Yavatmal",
    "AVATMAL": "Yavatmal",
    # With leading SN stripped
    "P ALGHAR": "Palghar",
    # Short truncations from split cells (NWR/BCA tables where SN+Name are in one cell)
    "EDNAGAR": "Ahmednagar",
    "ILYANAGAR": "Ahmednagar",
    "HILYANAGAR": "Ahmednagar",
    "LYANAGAR": "Ahmednagar",
    "HATRAPATI SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "ATRAPATI SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "CHH SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "CHH. SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "CHH. SAMBHAJINAQAR": "Chhatrapati Sambhajinagar",
    "HH SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "CHA.SAM.NAGA": "Chhatrapati Sambhajinagar",
    "CHA.SAM.NAGAR": "Chhatrapati Sambhajinagar",
    "ARASHIV": "Dharashiv",
    "DARASHIV": "Dharashiv",
    "UMBAI CITY": "Mumbai",
    "UMBAI": "Mumbai",
    # OCR artifacts: q instead of g
    "HINQOLI": "Hingoli",
    "JALQAON": "Jalgaon",
    "PALQHAR": "Palghar",
    "RAIQAD": "Raigad",
    "RATNAQIRI": "Ratnagiri",
    "SANQLI": "Sangli",
    "SINDHUDURQ": "Sindhudurg",
    "NAQPUR": "Nagpur",
}

# Rows to skip
SKIP_PATTERNS = [
    "total", "grand total", "sr.", "sr. no", "s.n", "name of district",
    "maharashtra", "number of", "rural", "bank", "slbc", "state",
    "district", "semi-urban", "urban", "no.", "amt", "account",
    "annexure", "convener", "convenor", "pledge", "(no", "(a/c",
    "education", "target", "achievement", "priority", "during",
    "quarter", "current", "outstanding", "overdue", "npa",
    "disbursement", "cumulative", "", "aif", "scheme", "annual",
    "otal", "other", "nd total", "and total", "rand total",
    "grand", "sub total",
]


def parse_number(val):
    """Parse number, return as float or None."""
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace(" ", "").replace("%", "")
    # Handle percentage-like values
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def clean_district_name(name):
    """Normalize district name to canonical form."""
    if not name:
        return None
    name = str(name).strip()

    # Remove leading serial numbers like "1", "2", "1.1", "1A", "2A" etc
    # But be careful not to strip "24 Parganas" type names (not relevant for MH)
    cleaned = re.sub(r"^\d+\.?\d*\s*", "", name).strip()
    if not cleaned:
        cleaned = name.strip()

    # Remove leading SN+space patterns like "1 " or "1." but keep the rest
    # Also handle cases like "1AHMEDNAGAR" -> "AHMEDNAGAR"
    cleaned2 = re.sub(r"^\d+\s*", "", cleaned).strip()
    if cleaned2:
        cleaned = cleaned2

    upper = cleaned.upper().strip()

    # Check aliases first (exact match)
    if upper in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[upper]

    # Check aliases with original (before SN strip)
    name_upper = name.upper().strip()
    # Strip just the SN prefix for alias check
    name_stripped = re.sub(r"^\d+\.?\d*\s*", "", name_upper).strip()
    if name_stripped in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[name_stripped]

    # Check if it's a skip pattern
    lower = cleaned.lower()
    for skip in SKIP_PATTERNS:
        if lower == skip or lower.startswith("total") or lower.startswith("grand") or lower.endswith("total"):
            return None

    if len(cleaned) < 3:
        return None

    # Title case and verify it looks like a district name
    title = cleaned.title()

    # Final check: match against canonical districts (fuzzy)
    for canon in CANONICAL_DISTRICTS:
        if canon.upper() == upper or canon.upper() in upper or upper in canon.upper():
            return canon

    # Check if it contains a known district name
    for canon in CANONICAL_DISTRICTS:
        if canon.upper() in name_upper:
            return canon

    # If it looks reasonable, return title case
    # But reject if too long (likely not a district name)
    if len(cleaned) >= 4 and len(cleaned) <= 30 and not any(c.isdigit() for c in cleaned[:3]):
        # Reject if it has too many words (districts have max 3 words)
        if len(cleaned.split()) <= 3:
            return title

    return None


def find_pages_with_text(pdf, search_terms, exclude_terms=None):
    """Find pages containing all search terms."""
    results = []
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if all(term.lower() in text for term in search_terms):
            if exclude_terms and any(term.lower() in text for term in exclude_terms):
                continue
            results.append(i)
    return results


def extract_district_table(pdf, page_idx, name_col=None, data_cols=None,
                           has_sr_col=True, min_rows=10, check_next_page=False):
    """Generic extraction of district rows from a table on a given page.

    Args:
        pdf: pdfplumber PDF object
        page_idx: 0-based page index
        name_col: column index for district name (auto-detected if None)
        data_cols: list of (col_index, field_name) tuples
        has_sr_col: whether table has a serial number column
        min_rows: minimum rows to consider a table valid
        check_next_page: whether to check next page for continuation

    Returns:
        dict of {district_name: {field: value, ...}}
    """
    districts = {}
    pages_to_check = [page_idx]
    if check_next_page:
        pages_to_check.append(page_idx + 1)

    for pidx in pages_to_check:
        if pidx >= len(pdf.pages):
            break
        page = pdf.pages[pidx]
        tables = page.extract_tables()

        for table in tables:
            if len(table) < min_rows:
                continue

            for row in table:
                if not row or len(row) < 2:
                    continue

                # Try to find district name in the row
                dist = None
                dist_col_found = None

                if name_col is not None:
                    if name_col < len(row):
                        dist = clean_district_name(row[name_col])
                        dist_col_found = name_col
                else:
                    # Auto-detect: try first few columns
                    for ci in range(min(3, len(row))):
                        candidate = clean_district_name(row[ci])
                        if candidate:
                            dist = candidate
                            dist_col_found = ci
                            break

                if not dist:
                    continue

                if data_cols:
                    entry = {"District": dist}
                    for col_idx, field_name in data_cols:
                        if col_idx < len(row):
                            entry[field_name] = row[col_idx]
                    districts[dist] = entry

    return districts


# ============================================================================
# Table-specific extraction functions
# ============================================================================

def extract_branch_cd_ratio(pdf, meeting):
    """Annexure 5.4: Branch Network & CD Ratio"""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "annexure 5.4" in text or ("district wise branch network" in text and "cd ratio" in text):
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 10:
                    continue

                districts = {}
                # Detect layout from header rows
                # Layout A (168th): Name, Pop, Rural, Semi, Urban, Total, PrevTotal, Deposit, Advance, CD (10 cols)
                # Layout B (169th/170th): SR, Name, Rural, Semi, Urban, Total, PrevTotal, Deposit, Advance, CD
                has_pop = False
                has_sr = False
                for row in table[:5]:
                    row_text = " ".join(str(c or "").lower() for c in row)
                    if "population" in row_text:
                        has_pop = True
                    if any(str(row[0] or "").strip().lower() in ("sr.", "sr", "s.no") for _ in [1]):
                        has_sr = True

                for row in table:
                    if len(row) < 9:
                        continue

                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            # Deposit, Advance, CD are always the last 3 columns
                            dep = parse_number(row[-3])
                            adv = parse_number(row[-2])
                            cdr = parse_number(row[-1])

                            # Total branch: find it by looking for columns
                            # In all layouts, Total is at a fixed position after name
                            # Find the column where deposit starts (large number > 1000)
                            total_br = None
                            for bci in range(ci + 1, len(row) - 3):
                                val = parse_number(row[bci])
                                if val and 100 < val < 5000:
                                    # Check if next col is also similar (prev total) and following is large (deposit)
                                    next_val = parse_number(row[bci + 1]) if bci + 1 < len(row) else None
                                    dep_val = parse_number(row[bci + 2]) if bci + 2 < len(row) else None
                                    if next_val and 100 < next_val < 5000 and dep_val and dep_val > 1000:
                                        total_br = val
                                        break

                            if dep is not None and dep > 100:  # Crores, should be > 100
                                dep_lakh = round(dep * CRORE_TO_LAKH, 2)
                                adv_lakh = round(adv * CRORE_TO_LAKH, 2) if adv else 0
                                entry = {
                                    "District": dist,
                                    "Total Deposit": str(dep_lakh),
                                    "Total Advances": str(adv_lakh),
                                    "Overall CD Ratio": str(round(cdr, 2)) if cdr else "0",
                                }
                                if total_br:
                                    entry["Total Branch"] = str(int(total_br))
                                districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    Branch/CD Ratio: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    Branch/CD Ratio: NOT FOUND")
    return {}


def extract_cd_ratio_detailed(pdf, meeting):
    """Annexure 5.2: District-wise CD Ratio with rural/urban split."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if ("annexure 5.2" in text or "district wise cd ratio" in text) and "rural" in text:
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 10:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 10:
                        continue

                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            # Layout: Branch, Dep_Rural, Dep_Semi, Dep_Urban, Dep_Total, Adv_Rural, Adv_Semi, Adv_Urban, Adv_Total
                            # Or with CD ratio at end
                            nums = [parse_number(v) for v in remaining]
                            valid = [n for n in nums if n is not None]
                            if len(valid) >= 8:
                                branch = parse_number(remaining[0])
                                dep_rural = parse_number(remaining[1])
                                dep_semi = parse_number(remaining[2])
                                dep_urban = parse_number(remaining[3])
                                dep_total = parse_number(remaining[4])
                                adv_rural = parse_number(remaining[5])
                                adv_semi = parse_number(remaining[6])
                                adv_urban = parse_number(remaining[7])
                                adv_total = parse_number(remaining[8]) if len(remaining) > 8 else None
                                cd_ratio = parse_number(remaining[9]) if len(remaining) > 9 else None

                                if dep_total and dep_total > 100:
                                    entry = {
                                        "District": dist,
                                        "Total Branch": str(int(branch)) if branch else "",
                                        "Deposit Rural": str(round(dep_rural * CRORE_TO_LAKH, 2)) if dep_rural else "",
                                        "Deposit Semi Urban": str(round(dep_semi * CRORE_TO_LAKH, 2)) if dep_semi else "",
                                        "Deposit Urban": str(round(dep_urban * CRORE_TO_LAKH, 2)) if dep_urban else "",
                                        "Total Deposit": str(round(dep_total * CRORE_TO_LAKH, 2)),
                                        "Advances Rural": str(round(adv_rural * CRORE_TO_LAKH, 2)) if adv_rural else "",
                                        "Advances Semi Urban": str(round(adv_semi * CRORE_TO_LAKH, 2)) if adv_semi else "",
                                        "Advances Urban": str(round(adv_urban * CRORE_TO_LAKH, 2)) if adv_urban else "",
                                        "Total Advances": str(round(adv_total * CRORE_TO_LAKH, 2)) if adv_total else "",
                                    }
                                    if cd_ratio and cd_ratio < 500:
                                        entry["Overall CD Ratio"] = str(round(cd_ratio, 2))
                                    districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    CD Ratio Detailed: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    CD Ratio Detailed: NOT FOUND")
    return {}


def extract_pmjdy(pdf, meeting):
    """Annexure 2.11/2.12: PMJDY District-wise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if ("pmjdy" in text and "dist" in text and ("lakh" in text or "actual" in text)):
            if "bankwise" in text or "bankw" in text:
                continue
            # Use raw text extraction since table extraction truncates names in some PDFs
            raw_text = page.extract_text() or ""
            lines = raw_text.split('\n')

            districts = {}

            if meeting == 170:
                # 170th: Numbers in actual (not lakhs), deposit in Rs Cr
                # Format: SL Name TotalAccounts TotalDeposit RupayCard AadharSeeded %Aadhar
                for line in lines:
                    # Try to match a district line
                    for canon in CANONICAL_DISTRICTS:
                        if canon in line or canon.lower() in line.lower():
                            # Extract numbers from the line
                            parts = line.split()
                            # Find where the district name ends and numbers begin
                            nums = []
                            name_end = 0
                            for pi, p in enumerate(parts):
                                val = parse_number(p)
                                if val is not None and pi > 0:
                                    if name_end == 0:
                                        name_end = pi
                                    nums.append(val)

                            if len(nums) >= 5:
                                total_acs = nums[0]  # actual number
                                total_dep = nums[1]  # Rs Cr
                                rupay = nums[2]  # actual
                                aadhaar = nums[3]  # actual
                                aadhaar_pct = nums[4]  # percentage

                                # Convert deposit from Crores to Lakhs
                                districts[canon] = {
                                    "District": canon,
                                    "PMJDY Total Accounts": str(int(total_acs)),
                                    "PMJDY Total Deposit": str(round(total_dep * CRORE_TO_LAKH, 2)),
                                    "PMJDY Rupay Card Issued": str(int(rupay)),
                                    "PMJDY Aadhaar Seeded": str(int(aadhaar)),
                                    "PMJDY Aadhaar Seeding Pct": str(round(aadhaar_pct, 2)),
                                }
                            break
            else:
                # 168th/169th: Numbers in Lakhs for accounts, deposit in Rs Cr
                # Format: SN District TotalA/Cs TotalDeposit RupayIssued AadhaarSeeded %AadhaarSeeding
                for line in lines:
                    for canon in CANONICAL_DISTRICTS:
                        if canon.lower() in line.lower() or canon in line:
                            parts = line.split()
                            nums = []
                            for p in parts:
                                val = parse_number(p)
                                if val is not None:
                                    nums.append(val)

                            if len(nums) >= 5:
                                # SN might be first number
                                # Values in lakhs (accounts) and Cr (deposit)
                                idx = 0
                                if nums[0] < 40:  # serial number
                                    idx = 1

                                if idx + 4 < len(nums):
                                    total_acs_lakh = nums[idx]
                                    total_dep_cr = nums[idx + 1]
                                    rupay_lakh = nums[idx + 2]
                                    aadhaar_lakh = nums[idx + 3]
                                    aadhaar_pct = nums[idx + 4]

                                    # 169th PDF bug: % column has same value as seeded count
                                    # Compute % ourselves if it looks wrong
                                    if aadhaar_pct > 100 or abs(aadhaar_pct - aadhaar_lakh) < 0.01:
                                        if total_acs_lakh > 0:
                                            aadhaar_pct = round(aadhaar_lakh / total_acs_lakh * 100, 2)

                                    # Convert lakh to actual (1 lakh = 100000)
                                    districts[canon] = {
                                        "District": canon,
                                        "PMJDY Total Accounts": str(round(total_acs_lakh * 100000)),
                                        "PMJDY Total Deposit": str(round(total_dep_cr * CRORE_TO_LAKH, 2)),
                                        "PMJDY Rupay Card Issued": str(round(rupay_lakh * 100000)),
                                        "PMJDY Aadhaar Seeded": str(round(aadhaar_lakh * 100000)),
                                        "PMJDY Aadhaar Seeding Pct": str(round(aadhaar_pct, 2)),
                                    }
                            break

            if len(districts) >= 20:
                print(f"    PMJDY: {len(districts)} districts from page {i + 1}")
                return districts

    print("    PMJDY: NOT FOUND")
    return {}


def extract_bca(pdf, meeting):
    """Annexure 2.9/2.10: Business Correspondent Agents districtwise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if ("bca" in text or "business correspond" in text) and "district" in text:
            if "male" in text and "female" in text and "total" in text:
                tables = page.extract_tables()
                for table in tables:
                    if len(table) < 20:
                        continue

                    districts = {}
                    for row in table:
                        if len(row) < 5:
                            continue
                        dist = None
                        for ci in range(min(3, len(row))):
                            dist = clean_district_name(row[ci])
                            if dist:
                                remaining = row[ci + 1:]
                                male = parse_number(remaining[0]) if len(remaining) > 0 else None
                                female = parse_number(remaining[1]) if len(remaining) > 1 else None
                                trans = parse_number(remaining[2]) if len(remaining) > 2 else None
                                total = parse_number(remaining[3]) if len(remaining) > 3 else None
                                active = parse_number(remaining[4]) if len(remaining) > 4 else None
                                inactive = parse_number(remaining[5]) if len(remaining) > 5 else None

                                if total and total > 100:
                                    entry = {
                                        "District": dist,
                                        "BCA Male": str(int(male)) if male else "",
                                        "BCA Female": str(int(female)) if female else "",
                                        "BCA Total": str(int(total)),
                                        "BCA Active": str(int(active)) if active else "",
                                        "BCA Inactive": str(int(inactive)) if inactive else "",
                                    }
                                    districts[dist] = entry
                                break

                    if len(districts) >= 20:
                        print(f"    BCA: {len(districts)} districts from page {i + 1}")
                        return districts

    print("    BCA: NOT FOUND")
    return {}


def extract_apy(pdf, meeting):
    """Annexure 2.19/2.20: Atal Pension Yojana districtwise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "apy" in text and "dist" in text and ("report" in text or "target" in text):
            if "bankwise" in text or "bank wise" in text:
                continue
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 5:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            nums = [parse_number(v) for v in remaining]
                            valid = [n for n in nums if n is not None]

                            if len(valid) >= 4:
                                branches = parse_number(remaining[0])
                                annual_target = parse_number(remaining[1])
                                opened_fy = parse_number(remaining[2])
                                # Next might be % or gap
                                cumulative = None
                                for v in remaining[3:]:
                                    n = parse_number(v)
                                    if n and n > 10000:  # cumulative is large
                                        cumulative = n
                                        break

                                if annual_target and annual_target > 100:
                                    entry = {
                                        "District": dist,
                                        "APY Branches": str(int(branches)) if branches else "",
                                        "APY Annual Target": str(int(annual_target)),
                                        "APY Opened FY": str(int(opened_fy)) if opened_fy else "",
                                    }
                                    if cumulative:
                                        entry["APY Cumulative"] = str(int(cumulative))
                                    districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    APY: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    APY: NOT FOUND")
    return {}


def extract_agriculture_npa(pdf, meeting):
    """Annexure 3.9/3.10: Agriculture O/S vs NPA."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "agriculture" in text and "npa" in text and "district" in text:
            if "annexure 3." in text and "crore" in text:
                tables = page.extract_tables()
                for table in tables:
                    if len(table) < 20:
                        continue

                    districts = {}
                    for row in table:
                        if len(row) < 7:
                            continue
                        dist = None
                        for ci in range(min(3, len(row))):
                            dist = clean_district_name(row[ci])
                            if dist:
                                remaining = row[ci + 1:]
                                # Layout: Agri_OS_Accounts, Agri_OS_Amt, NPA_Accounts, NPA_Amt, NPA%_Ac, NPA%_Amt
                                agri_os_ac = parse_number(remaining[0]) if len(remaining) > 0 else None
                                agri_os_amt = parse_number(remaining[1]) if len(remaining) > 1 else None
                                npa_ac = parse_number(remaining[2]) if len(remaining) > 2 else None
                                npa_amt = parse_number(remaining[3]) if len(remaining) > 3 else None

                                if agri_os_ac and agri_os_ac > 1000:
                                    entry = {
                                        "District": dist,
                                        "Agri OS Accounts": str(int(agri_os_ac)),
                                        "Agri OS Amount": str(round(agri_os_amt * CRORE_TO_LAKH, 2)) if agri_os_amt else "",
                                        "Agri NPA Accounts": str(int(npa_ac)) if npa_ac else "",
                                        "Agri NPA Amount": str(round(npa_amt * CRORE_TO_LAKH, 2)) if npa_amt else "",
                                    }
                                    # Parse NPA percentages
                                    for ri in range(4, min(len(remaining), 7)):
                                        val = remaining[ri]
                                        if val and "%" in str(val):
                                            pct = parse_number(val)
                                            if pct and ri == 4:
                                                entry["Agri NPA Pct Accounts"] = str(round(pct, 2))
                                            elif pct and ri == 5:
                                                entry["Agri NPA Pct Amount"] = str(round(pct, 2))

                                    districts[dist] = entry
                                break

                    if len(districts) >= 20:
                        print(f"    Agriculture NPA: {len(districts)} districts from page {i + 1}")
                        return districts

    print("    Agriculture NPA: NOT FOUND")
    return {}


def extract_sc_st_loans(pdf, meeting):
    """Annexure 3.28-3.30: SC/ST Loan Disbursement."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "sc/st" in text and "district" in text and "disbursement" in text:
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 8:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            # SC: Disb_Acs, Disb_Amt, OS_Acs, OS_Amt
                            # ST: Disb_Acs, Disb_Amt, OS_Acs, OS_Amt
                            sc_disb_ac = parse_number(remaining[0]) if len(remaining) > 0 else None
                            sc_disb_amt = parse_number(remaining[1]) if len(remaining) > 1 else None
                            sc_os_ac = parse_number(remaining[2]) if len(remaining) > 2 else None
                            sc_os_amt = parse_number(remaining[3]) if len(remaining) > 3 else None
                            st_disb_ac = parse_number(remaining[4]) if len(remaining) > 4 else None
                            st_disb_amt = parse_number(remaining[5]) if len(remaining) > 5 else None
                            st_os_ac = parse_number(remaining[6]) if len(remaining) > 6 else None
                            st_os_amt = parse_number(remaining[7]) if len(remaining) > 7 else None

                            if sc_disb_ac and sc_disb_ac > 10:
                                entry = {
                                    "District": dist,
                                    "SC Disb Accounts": str(int(sc_disb_ac)),
                                    "SC Disb Amount": str(round(sc_disb_amt * CRORE_TO_LAKH, 2)) if sc_disb_amt else "",
                                    "SC OS Accounts": str(int(sc_os_ac)) if sc_os_ac else "",
                                    "SC OS Amount": str(round(sc_os_amt * CRORE_TO_LAKH, 2)) if sc_os_amt else "",
                                    "ST Disb Accounts": str(int(st_disb_ac)) if st_disb_ac else "",
                                    "ST Disb Amount": str(round(st_disb_amt * CRORE_TO_LAKH, 2)) if st_disb_amt else "",
                                    "ST OS Accounts": str(int(st_os_ac)) if st_os_ac else "",
                                    "ST OS Amount": str(round(st_os_amt * CRORE_TO_LAKH, 2)) if st_os_amt else "",
                                }
                                districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    SC/ST Loans: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    SC/ST Loans: NOT FOUND")
    return {}


def extract_pmsvanidhi(pdf, meeting):
    """Annexure 3.30-3.32: PMSVANidhi districtwise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "pmsvanidhi" in text and "district" in text:
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 4:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            total_apps = parse_number(remaining[0]) if len(remaining) > 0 else None

                            if total_apps and total_apps > 100:
                                entry = {"District": dist}

                                if meeting == 170:
                                    # 170th: Received, Sanctioned, Returned, Pending, Disbursed
                                    entry["PMSVANidhi Applications"] = str(int(total_apps))
                                    if len(remaining) > 1:
                                        sanc = parse_number(remaining[1])
                                        if sanc:
                                            entry["PMSVANidhi Sanctioned"] = str(int(sanc))
                                    if len(remaining) > 4:
                                        disb = parse_number(remaining[4])
                                        if disb:
                                            entry["PMSVANidhi Disbursed"] = str(int(disb))
                                    elif len(remaining) > 3:
                                        disb = parse_number(remaining[3])
                                        if disb:
                                            entry["PMSVANidhi Disbursed"] = str(int(disb))
                                else:
                                    # 168th/169th: Received, Returned, Pending, Disbursed
                                    entry["PMSVANidhi Applications"] = str(int(total_apps))
                                    disb_idx = len(remaining) - 1
                                    disb = parse_number(remaining[disb_idx])
                                    if disb:
                                        entry["PMSVANidhi Disbursed"] = str(int(disb))

                                districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    PMSVANidhi: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    PMSVANidhi: NOT FOUND")
    return {}


def extract_shg(pdf, meeting):
    """Annexure 3.38-3.40: SHG districtwise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "shg" in text and "district" in text and ("quarter" in text or "fy" in text or "f.y" in text):
            if "crore" in text:
                tables = page.extract_tables()
                for table in tables:
                    if len(table) < 20:
                        continue

                    districts = {}
                    for row in table:
                        if len(row) < 8:
                            continue
                        dist = None
                        for ci in range(min(3, len(row))):
                            dist = clean_district_name(row[ci])
                            if dist:
                                remaining = row[ci + 1:]
                                # Layout: Q_Savings_No, Q_Savings_Amt, Q_Credit_No, Q_Credit_Amt,
                                #         FY_Savings_No, FY_Savings_Amt, FY_Credit_No, FY_Credit_Amt
                                q_sav_no = parse_number(remaining[0]) if len(remaining) > 0 else None
                                q_sav_amt = parse_number(remaining[1]) if len(remaining) > 1 else None
                                q_cred_no = parse_number(remaining[2]) if len(remaining) > 2 else None
                                q_cred_amt = parse_number(remaining[3]) if len(remaining) > 3 else None
                                fy_sav_no = parse_number(remaining[4]) if len(remaining) > 4 else None
                                fy_sav_amt = parse_number(remaining[5]) if len(remaining) > 5 else None
                                fy_cred_no = parse_number(remaining[6]) if len(remaining) > 6 else None
                                fy_cred_amt = parse_number(remaining[7]) if len(remaining) > 7 else None

                                if q_sav_no is not None or fy_sav_no is not None:
                                    entry = {
                                        "District": dist,
                                        "SHG Savings Linked No Quarter": str(int(q_sav_no)) if q_sav_no else "",
                                        "SHG Savings Linked Amt Quarter": str(round(q_sav_amt * CRORE_TO_LAKH, 2)) if q_sav_amt else "",
                                        "SHG Credit Linked No Quarter": str(int(q_cred_no)) if q_cred_no else "",
                                        "SHG Credit Linked Amt Quarter": str(round(q_cred_amt * CRORE_TO_LAKH, 2)) if q_cred_amt else "",
                                        "SHG Savings Linked No FY": str(int(fy_sav_no)) if fy_sav_no else "",
                                        "SHG Savings Linked Amt FY": str(round(fy_sav_amt * CRORE_TO_LAKH, 2)) if fy_sav_amt else "",
                                        "SHG Credit Linked No FY": str(int(fy_cred_no)) if fy_cred_no else "",
                                        "SHG Credit Linked Amt FY": str(round(fy_cred_amt * CRORE_TO_LAKH, 2)) if fy_cred_amt else "",
                                    }
                                    districts[dist] = entry
                                break

                    if len(districts) >= 20:
                        print(f"    SHG: {len(districts)} districts from page {i + 1}")
                        return districts

    print("    SHG: NOT FOUND")
    return {}


def extract_pm_kisan_kcc(pdf, meeting):
    """Annexure 3.14/3.15: PM Kisan Saturation + KCC."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "pm kisan" in text and ("kcc" in text or "saturation" in text) and "actual" in text:
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 3:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            pm_kisan = parse_number(remaining[0]) if len(remaining) > 0 else None
                            kcc_ac = parse_number(remaining[1]) if len(remaining) > 1 else None
                            kcc_amt = parse_number(remaining[2]) if len(remaining) > 2 else None

                            if pm_kisan and pm_kisan > 1000:
                                entry = {
                                    "District": dist,
                                    "PM Kisan Beneficiaries": str(int(pm_kisan)),
                                    "KCC Accounts": str(int(kcc_ac)) if kcc_ac else "",
                                    "KCC Amount": str(round(kcc_amt * CRORE_TO_LAKH, 2)) if kcc_amt else "",
                                }
                                districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    PM Kisan/KCC: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    PM Kisan/KCC: NOT FOUND")
    return {}


def extract_mudra(pdf, meeting):
    """Annexure 2.14/2.15: MUDRA Loans districtwise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "mudra" in text and "district" in text and "crore" in text:
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 10:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            # Shishu(3), Kishore(3), Tarun(3), TarunPlus(3), Total(3)
                            # Each: NoOfAcs, SanctAmt, DisbAmt
                            # Total cols are at the end: TotalAcs, TotalSanct, TotalDisb
                            nums = [parse_number(v) for v in remaining]
                            valid = [n for n in nums if n is not None]

                            if len(valid) >= 6:
                                # Get total columns (last 3 values that are reasonable)
                                # The total Acs should be > 1000
                                total_acs = None
                                total_sanct = None
                                total_disb = None

                                # Try last 3 columns
                                if len(remaining) >= 3:
                                    total_acs = parse_number(remaining[-3])
                                    total_sanct = parse_number(remaining[-2])
                                    total_disb = parse_number(remaining[-1])

                                if total_acs and total_acs > 100:
                                    # Shishu
                                    shishu_acs = parse_number(remaining[0]) if len(remaining) > 0 else None
                                    shishu_amt = parse_number(remaining[1]) if len(remaining) > 1 else None
                                    # Kishore
                                    ki_acs = parse_number(remaining[3]) if len(remaining) > 3 else None
                                    ki_amt = parse_number(remaining[4]) if len(remaining) > 4 else None
                                    # Tarun
                                    ta_acs = parse_number(remaining[6]) if len(remaining) > 6 else None
                                    ta_amt = parse_number(remaining[7]) if len(remaining) > 7 else None

                                    entry = {
                                        "District": dist,
                                        "MUDRA Shishu Accounts": str(int(shishu_acs)) if shishu_acs else "",
                                        "MUDRA Shishu Amount": str(round(shishu_amt * CRORE_TO_LAKH, 2)) if shishu_amt else "",
                                        "MUDRA Kishore Accounts": str(int(ki_acs)) if ki_acs else "",
                                        "MUDRA Kishore Amount": str(round(ki_amt * CRORE_TO_LAKH, 2)) if ki_amt else "",
                                        "MUDRA Tarun Accounts": str(int(ta_acs)) if ta_acs else "",
                                        "MUDRA Tarun Amount": str(round(ta_amt * CRORE_TO_LAKH, 2)) if ta_amt else "",
                                        "MUDRA Total Accounts": str(int(total_acs)),
                                        "MUDRA Total Sanctioned": str(round(total_sanct * CRORE_TO_LAKH, 2)) if total_sanct else "",
                                        "MUDRA Total Disbursed": str(round(total_disb * CRORE_TO_LAKH, 2)) if total_disb else "",
                                    }
                                    districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    MUDRA: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    MUDRA: NOT FOUND")
    return {}


def extract_aif(pdf, meeting):
    """Annexure 9.2: AIF District-wise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "aif" in text and "district" in text and "target" in text:
            if "bank wise" in text or "bankwise" in text:
                continue
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 10:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            # Annual Target No, Amt, ... Cumulative Sanctions No, Amt, ... % Achv
                            target_no = parse_number(remaining[0]) if len(remaining) > 0 else None
                            target_amt = parse_number(remaining[1]) if len(remaining) > 1 else None

                            if target_no and target_no >= 1:
                                # Get cumulative sanctions (latest period)
                                cum_sanc_no = parse_number(remaining[6]) if len(remaining) > 6 else None
                                cum_sanc_amt = parse_number(remaining[7]) if len(remaining) > 7 else None
                                cum_disb_no = parse_number(remaining[8]) if len(remaining) > 8 else None
                                cum_disb_amt = parse_number(remaining[9]) if len(remaining) > 9 else None
                                pct_ach = parse_number(remaining[-1]) if len(remaining) > 10 else None

                                entry = {
                                    "District": dist,
                                    "AIF Target No": str(int(target_no)),
                                    "AIF Target Amount": str(round(target_amt * CRORE_TO_LAKH, 2)) if target_amt else "",
                                    "AIF Cumulative Sanctions No": str(int(cum_sanc_no)) if cum_sanc_no else "",
                                    "AIF Cumulative Sanctions Amount": str(round(cum_sanc_amt * CRORE_TO_LAKH, 2)) if cum_sanc_amt else "",
                                    "AIF Cumulative Disbursed No": str(int(cum_disb_no)) if cum_disb_no else "",
                                    "AIF Cumulative Disbursed Amount": str(round(cum_disb_amt * CRORE_TO_LAKH, 2)) if cum_disb_amt else "",
                                }
                                if pct_ach:
                                    entry["AIF Achievement Pct"] = str(round(pct_ach, 2))
                                districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    AIF: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    AIF: NOT FOUND")
    return {}


def extract_apamvm(pdf, meeting):
    """Annexure 3.26-3.28: APAMVM districtwise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "apamvm" in text and "district" in text:
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 4:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            # 168th/169th: Pending, Rejected, (maybe Sanction)
                            # 170th: Targets, Sanction, Pending, Rejected
                            nums = [parse_number(v) for v in remaining]
                            valid = [n for n in nums if n is not None]

                            if len(valid) >= 2:
                                entry = {"District": dist}
                                if meeting == 170:
                                    if len(remaining) >= 4:
                                        entry["APAMVM Targets"] = str(int(parse_number(remaining[0]))) if parse_number(remaining[0]) else ""
                                        entry["APAMVM Sanctioned"] = str(int(parse_number(remaining[1]))) if parse_number(remaining[1]) else ""
                                        entry["APAMVM Pending"] = str(int(parse_number(remaining[2]))) if parse_number(remaining[2]) else ""
                                        entry["APAMVM Rejected"] = str(int(parse_number(remaining[3]))) if parse_number(remaining[3]) else ""
                                else:
                                    # Pending, Rejected, ...
                                    entry["APAMVM Pending"] = str(int(parse_number(remaining[0]))) if parse_number(remaining[0]) else ""
                                    entry["APAMVM Rejected"] = str(int(parse_number(remaining[1]))) if parse_number(remaining[1]) else ""
                                districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    APAMVM: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    APAMVM: NOT FOUND")
    return {}


def extract_msme_npa(pdf, meeting):
    """Annexure 6.4: MSME NPA districtwise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "msme" in text and "npa" in text and "district" in text:
            if "crore" in text:
                tables = page.extract_tables()
                for table in tables:
                    if len(table) < 20:
                        continue

                    districts = {}
                    for row in table:
                        if len(row) < 5:
                            continue
                        dist = None
                        for ci in range(min(3, len(row))):
                            dist = clean_district_name(row[ci])
                            if dist:
                                remaining = row[ci + 1:]
                                os_ac = parse_number(remaining[0]) if len(remaining) > 0 else None
                                os_amt = parse_number(remaining[1]) if len(remaining) > 1 else None
                                npa_ac = parse_number(remaining[2]) if len(remaining) > 2 else None
                                npa_amt = parse_number(remaining[3]) if len(remaining) > 3 else None
                                npa_pct = parse_number(remaining[4]) if len(remaining) > 4 else None

                                if os_ac and os_ac > 100:
                                    entry = {
                                        "District": dist,
                                        "MSME OS Accounts": str(int(os_ac)),
                                        "MSME OS Amount": str(round(os_amt * CRORE_TO_LAKH, 2)) if os_amt else "",
                                        "MSME NPA Accounts": str(int(npa_ac)) if npa_ac else "",
                                        "MSME NPA Amount": str(round(npa_amt * CRORE_TO_LAKH, 2)) if npa_amt else "",
                                        "MSME NPA Pct": str(round(npa_pct, 2)) if npa_pct else "",
                                    }
                                    districts[dist] = entry
                                break

                    if len(districts) >= 20:
                        print(f"    MSME NPA: {len(districts)} districts from page {i + 1}")
                        return districts

    print("    MSME NPA: NOT FOUND")
    return {}


def extract_education_loan(pdf, meeting):
    """Annexure 3.36/3.37: Education Loan districtwise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "education" in text and "loan" in text and "district" in text and "target" in text:
            if "crore" in text:
                tables = page.extract_tables()
                for table in tables:
                    if len(table) < 20:
                        continue

                    districts = {}
                    for row in table:
                        if len(row) < 10:
                            continue
                        dist = None
                        for ci in range(min(3, len(row))):
                            dist = clean_district_name(row[ci])
                            if dist:
                                remaining = row[ci + 1:]
                                # Priority: Target_Ac, Target_Amt, Ach_Ac, Ach_Amt, %Ach
                                # Non-Priority: Target_Ac, Target_Amt, Ach_Ac, Ach_Amt, %Ach
                                # Total: Target_Ac, Target_Amt, Ach_Ac, Ach_Amt, %Ach
                                nums = [parse_number(v) for v in remaining]
                                valid = [n for n in nums if n is not None]

                                if len(valid) >= 10:
                                    # Total priority + non-priority columns are at end
                                    # Total target Ac, Amt, Ach Ac, Ach Amt, %
                                    total_target_ac = parse_number(remaining[-5]) if len(remaining) >= 5 else None
                                    total_target_amt = parse_number(remaining[-4]) if len(remaining) >= 4 else None
                                    total_ach_ac = parse_number(remaining[-3]) if len(remaining) >= 3 else None
                                    total_ach_amt = parse_number(remaining[-2]) if len(remaining) >= 2 else None
                                    total_pct = parse_number(remaining[-1]) if len(remaining) >= 1 else None

                                    # Priority section
                                    pri_target_ac = parse_number(remaining[0]) if len(remaining) > 0 else None
                                    pri_target_amt = parse_number(remaining[1]) if len(remaining) > 1 else None
                                    pri_ach_ac = parse_number(remaining[2]) if len(remaining) > 2 else None
                                    pri_ach_amt = parse_number(remaining[3]) if len(remaining) > 3 else None

                                    if pri_target_ac and pri_target_ac > 10:
                                        entry = {
                                            "District": dist,
                                            "EduLoan Priority Target Accounts": str(int(pri_target_ac)),
                                            "EduLoan Priority Target Amount": str(round(pri_target_amt * CRORE_TO_LAKH, 2)) if pri_target_amt else "",
                                            "EduLoan Priority Ach Accounts": str(int(pri_ach_ac)) if pri_ach_ac else "",
                                            "EduLoan Priority Ach Amount": str(round(pri_ach_amt * CRORE_TO_LAKH, 2)) if pri_ach_amt else "",
                                            "EduLoan Total Target Accounts": str(int(total_target_ac)) if total_target_ac else "",
                                            "EduLoan Total Target Amount": str(round(total_target_amt * CRORE_TO_LAKH, 2)) if total_target_amt else "",
                                            "EduLoan Total Ach Accounts": str(int(total_ach_ac)) if total_ach_ac else "",
                                            "EduLoan Total Ach Amount": str(round(total_ach_amt * CRORE_TO_LAKH, 2)) if total_ach_amt else "",
                                        }
                                        if total_pct:
                                            entry["EduLoan Achievement Pct"] = str(round(total_pct, 2))
                                        districts[dist] = entry
                                break

                    if len(districts) >= 20:
                        print(f"    Education Loan: {len(districts)} districts from page {i + 1}")
                        return districts

    print("    Education Loan: NOT FOUND")
    return {}


def extract_kcc_outstanding(pdf, meeting):
    """Annexure 3.13 B: KCC Outstanding/NPA districtwise (169th only)."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "kcc" in text and "dist" in text and "o/s" in text.lower() and "lakh" in text:
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 8:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            # Total OS No, Amt, Overdue No, Amt, NPA No, Amt, %Overdue No, %Overdue Amt, %NPA No, %NPA Amt
                            os_no = parse_number(remaining[0]) if len(remaining) > 0 else None
                            os_amt = parse_number(remaining[1]) if len(remaining) > 1 else None
                            overdue_no = parse_number(remaining[2]) if len(remaining) > 2 else None
                            overdue_amt = parse_number(remaining[3]) if len(remaining) > 3 else None
                            npa_no = parse_number(remaining[4]) if len(remaining) > 4 else None
                            npa_amt = parse_number(remaining[5]) if len(remaining) > 5 else None

                            if os_no and os_no > 1000:
                                entry = {
                                    "District": dist,
                                    "KCC OS No": str(int(os_no)),
                                    "KCC OS Amount": str(round(os_amt, 2)) if os_amt else "",  # Already in lakhs
                                    "KCC Overdue No": str(int(overdue_no)) if overdue_no else "",
                                    "KCC Overdue Amount": str(round(overdue_amt, 2)) if overdue_amt else "",
                                    "KCC NPA No": str(int(npa_no)) if npa_no else "",
                                    "KCC NPA Amount": str(round(npa_amt, 2)) if npa_amt else "",
                                }
                                # Percentages
                                if len(remaining) > 6:
                                    pct_overdue_no = parse_number(remaining[6])
                                    if pct_overdue_no:
                                        entry["KCC Overdue Pct No"] = str(round(pct_overdue_no, 2))
                                if len(remaining) > 8:
                                    pct_npa_no = parse_number(remaining[8])
                                    if pct_npa_no:
                                        entry["KCC NPA Pct No"] = str(round(pct_npa_no, 2))

                                districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    KCC Outstanding: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    KCC Outstanding: NOT FOUND")
    return {}


def extract_pmjjby(pdf, meeting):
    """Annexure 2.22: PMJJBY enrolment districtwise (170th only)."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "pmjjby" in text and "district" in text and "lakh" in text:
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 3:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            prev = parse_number(remaining[0]) if len(remaining) > 0 else None
                            current = parse_number(remaining[1]) if len(remaining) > 1 else None
                            increase = parse_number(remaining[2]) if len(remaining) > 2 else None

                            if current and current > 0:
                                entry = {
                                    "District": dist,
                                    "PMJJBY Enrolment Prev": str(round(prev * 100000)) if prev else "",
                                    "PMJJBY Enrolment Current": str(round(current * 100000)),
                                    "PMJJBY QoQ Increase": str(round(increase * 100000)) if increase else "",
                                }
                                districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    PMJJBY: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    PMJJBY: NOT FOUND")
    return {}


def extract_pmsby(pdf, meeting):
    """Annexure 2.24: PMSBY enrolment districtwise (170th only)."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "pmsby" in text and "district" in text and "lakh" in text:
            if "pmjjby" in text:
                continue  # Skip PMJJBY table
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 3:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            prev = parse_number(remaining[0]) if len(remaining) > 0 else None
                            current = parse_number(remaining[1]) if len(remaining) > 1 else None
                            increase = parse_number(remaining[2]) if len(remaining) > 2 else None

                            if current and current > 0:
                                entry = {
                                    "District": dist,
                                    "PMSBY Enrolment Prev": str(round(prev * 100000)) if prev else "",
                                    "PMSBY Enrolment Current": str(round(current * 100000)),
                                    "PMSBY QoQ Increase": str(round(increase * 100000)) if increase else "",
                                }
                                districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    PMSBY: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    PMSBY: NOT FOUND")
    return {}


def extract_nwr(pdf, meeting):
    """Annexure 3.40/3.42: NWR Pledge Financing districtwise."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "pledge" in text and ("nwr" in text or "warehouse" in text):
            if "bankwise" in text or "bank wise" in text:
                continue
            # Must contain annexure or SLBC marker to avoid index page
            if "annexure" not in text and "convenor" not in text and "convener" not in text:
                continue
            # Must say "district" to avoid bank-wise table
            if "district" not in text:
                continue
            tables = page.extract_tables()
            for table in tables:
                if len(table) < 20:
                    continue

                districts = {}
                for row in table:
                    if len(row) < 4:
                        continue
                    dist = None
                    for ci in range(min(3, len(row))):
                        dist = clean_district_name(row[ci])
                        if dist:
                            remaining = row[ci + 1:]
                            # Disb_Acs, Disb_Amt, OS_Acs, OS_Amt
                            disb_ac = parse_number(remaining[0]) if len(remaining) > 0 else None
                            disb_amt = parse_number(remaining[1]) if len(remaining) > 1 else None
                            os_ac = parse_number(remaining[2]) if len(remaining) > 2 else None
                            os_amt = parse_number(remaining[3]) if len(remaining) > 3 else None

                            entry = {"District": dist}
                            if disb_ac is not None:
                                entry["NWR Disb Accounts"] = str(int(disb_ac))
                            if disb_amt is not None:
                                # 168th is in Rs Lakh, 169th is in Rs Crore
                                if meeting == 168:
                                    entry["NWR Disb Amount"] = str(round(disb_amt, 2))
                                else:
                                    entry["NWR Disb Amount"] = str(round(disb_amt * CRORE_TO_LAKH, 2))
                            if os_ac is not None:
                                entry["NWR OS Accounts"] = str(int(os_ac))
                            if os_amt is not None:
                                if meeting == 168:
                                    entry["NWR OS Amount"] = str(round(os_amt, 2))
                                else:
                                    entry["NWR OS Amount"] = str(round(os_amt * CRORE_TO_LAKH, 2))

                            if len(entry) > 1:
                                districts[dist] = entry
                            break

                if len(districts) >= 20:
                    print(f"    NWR: {len(districts)} districts from page {i + 1}")
                    return districts

    print("    NWR: NOT FOUND")
    return {}


# ============================================================================
# Main extraction pipeline
# ============================================================================

def extract_all_from_pdf(filepath, meeting):
    """Extract all district-wise tables from a Maharashtra SLBC agenda PDF."""
    try:
        pdf = pdfplumber.open(filepath)
    except Exception as e:
        print(f"  ERROR: Could not open PDF — {e}")
        return {}

    print(f"  Total pages: {len(pdf.pages)}")

    results = {}

    # 1. Branch Network & CD Ratio (Annexure 5.4)
    data = extract_branch_cd_ratio(pdf, meeting)
    if data:
        results["credit_deposit_ratio"] = data

    # 2. CD Ratio Detailed (Annexure 5.2) - 169th and 170th
    data = extract_cd_ratio_detailed(pdf, meeting)
    if data:
        results["cd_ratio_detailed"] = data

    # 3. PMJDY (Annexure 2.11/2.12)
    data = extract_pmjdy(pdf, meeting)
    if data:
        results["pmjdy"] = data

    # 4. BCA (Annexure 2.9/2.10)
    data = extract_bca(pdf, meeting)
    if data:
        results["bca"] = data

    # 5. APY (Annexure 2.19/2.20)
    data = extract_apy(pdf, meeting)
    if data:
        results["apy"] = data

    # 6. Agriculture NPA (Annexure 3.9/3.10)
    data = extract_agriculture_npa(pdf, meeting)
    if data:
        results["agriculture_npa"] = data

    # 7. SC/ST Loans (Annexure 3.28-3.30)
    data = extract_sc_st_loans(pdf, meeting)
    if data:
        results["sc_st_loans"] = data

    # 8. PMSVANidhi (Annexure 3.30-3.32)
    data = extract_pmsvanidhi(pdf, meeting)
    if data:
        results["pmsvanidhi"] = data

    # 9. SHG (Annexure 3.38-3.40)
    data = extract_shg(pdf, meeting)
    if data:
        results["shg"] = data

    # 10. PM Kisan / KCC Saturation (Annexure 3.14/3.15)
    data = extract_pm_kisan_kcc(pdf, meeting)
    if data:
        results["pm_kisan_kcc"] = data

    # 11. MUDRA (Annexure 2.14/2.15)
    data = extract_mudra(pdf, meeting)
    if data:
        results["mudra"] = data

    # 12. AIF (Annexure 9.2)
    data = extract_aif(pdf, meeting)
    if data:
        results["aif"] = data

    # 13. APAMVM (Annexure 3.26-3.28)
    data = extract_apamvm(pdf, meeting)
    if data:
        results["apamvm"] = data

    # 14. MSME NPA (Annexure 6.4)
    data = extract_msme_npa(pdf, meeting)
    if data:
        results["msme_npa"] = data

    # 15. Education Loan (Annexure 3.36/3.37) - 169th and 170th
    data = extract_education_loan(pdf, meeting)
    if data:
        results["education_loan"] = data

    # 16. KCC Outstanding (Annexure 3.13 B) - 169th only
    data = extract_kcc_outstanding(pdf, meeting)
    if data:
        results["kcc"] = data

    # 17. PMJJBY (Annexure 2.22) - 170th only
    data = extract_pmjjby(pdf, meeting)
    if data:
        results["pmjjby"] = data

    # 18. PMSBY (Annexure 2.24) - 170th only
    data = extract_pmsby(pdf, meeting)
    if data:
        results["pmsby"] = data

    # 19. NWR (Annexure 3.40/3.42)
    data = extract_nwr(pdf, meeting)
    if data:
        results["nwr"] = data

    pdf.close()
    return results


def build_complete_json(all_quarters):
    """Build maharashtra_complete.json."""
    result = {
        "source": "SLBC Maharashtra (State Level Bankers' Committee, Maharashtra)",
        "state": "Maharashtra",
        "amount_unit": "Rs. Lakhs",
        "quarters": {},
    }

    for q in all_quarters:
        tables = {}
        for table_name, table_data in q["tables"].items():
            fields = list(set(k for d in table_data.values() for k in d.keys()))
            # Order: District first, then sorted
            ordered = ["District"] + sorted([f for f in fields if f != "District"])
            tables[table_name] = {
                "fields": ordered,
                "districts": table_data,
            }

        result["quarters"][q["quarter_key"]] = {
            "period": q["period"],
            "as_on_date": q["as_on_date"],
            "fy": q["fy"],
            "tables": tables,
        }

    return result


def build_timeseries_json(all_quarters):
    """Build maharashtra_fi_timeseries.json."""
    periods = []

    for q in all_quarters:
        # Collect all districts across all tables
        all_districts = set()
        for table_data in q["tables"].values():
            all_districts.update(table_data.keys())

        district_rows = []
        for dist_name in sorted(all_districts):
            row = {
                "district": dist_name,
                "period": q["period"],
            }

            # Add fields from each table with category prefix
            for table_name, table_data in q["tables"].items():
                if dist_name in table_data:
                    for field, value in table_data[dist_name].items():
                        if field == "District":
                            continue
                        # Convert field name to snake_case
                        snake = field.lower().replace(" ", "_").replace("/", "_")
                        key = f"{table_name}__{snake}"
                        row[key] = value

            district_rows.append(row)

        periods.append({
            "period": q["period"],
            "districts": district_rows,
        })

    return {"periods": periods}


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    all_quarters = []

    for pinfo in PDFS:
        filepath = pinfo["file"]
        print(f"\n{'=' * 60}")
        print(f"Processing {filepath} → {pinfo['period']} (Meeting {pinfo['meeting']})")
        print(f"{'=' * 60}")

        if not os.path.exists(filepath):
            print(f"  MISSING: {filepath}")
            continue

        tables = extract_all_from_pdf(filepath, pinfo["meeting"])

        if tables:
            all_quarters.append({
                "quarter_key": pinfo["quarter_key"],
                "period": pinfo["period"],
                "as_on_date": pinfo["as_on_date"],
                "fy": pinfo["fy"],
                "tables": tables,
            })
            print(f"\n  SUMMARY: {len(tables)} tables extracted")
            for tname, tdata in tables.items():
                print(f"    {tname}: {len(tdata)} districts")

    all_quarters.sort(key=lambda q: q["quarter_key"])

    complete = build_complete_json(all_quarters)
    timeseries = build_timeseries_json(all_quarters)

    with open("maharashtra_complete.json", "w") as f:
        json.dump(complete, f, indent=2, ensure_ascii=False)
    print(f"\nWrote maharashtra_complete.json ({len(all_quarters)} quarters)")

    with open("maharashtra_fi_timeseries.json", "w") as f:
        json.dump(timeseries, f, indent=2, ensure_ascii=False)
    print(f"Wrote maharashtra_fi_timeseries.json")

    print(f"\n{'=' * 60}")
    print("EXTRACTION SUMMARY")
    print(f"{'=' * 60}")
    for q in all_quarters:
        print(f"\n{q['period']} ({q['quarter_key']}):")
        for tname, tdata in q["tables"].items():
            print(f"  {tname}: {len(tdata)} districts")


if __name__ == "__main__":
    main()
