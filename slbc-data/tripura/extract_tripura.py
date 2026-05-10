#!/usr/bin/env python3
"""
Tripura SLBC Agenda Book Extractor
==================================
Extracts district-wise tables from Tripura SLBC agenda PDFs (125th to 154th
meetings, June 2018 to December 2025).

Distinguishing features:
  - Many tables (esp. recent ones) carry MULTIPLE QUARTERS side-by-side as
    columns (e.g. "Dec 2024 | Mar 2025 | Jun 2025 | Sep 2025 | Dec 2025").
  - Earlier tables typically have a single quarter implied by the meeting.
  - Same quarter often appears in multiple PDFs — we keep the value from the
    most-recent PDF.

Outputs (all in slbc-data/tripura/):
    tripura_complete.json
    tripura_fi_timeseries.json
    tripura_fi_timeseries.csv
    quarterly/{YYYY-MM}/*.csv
"""

import pdfplumber
import json
import csv
import os
import re
import sys
from pathlib import Path
from collections import defaultdict, OrderedDict

HERE = Path(__file__).parent
DIR = HERE

# ─── 8 canonical Tripura districts ───
TR_DISTRICTS = [
    "Dhalai", "Gomati", "Khowai", "North Tripura",
    "Sepahijala", "South Tripura", "Unakoti", "West Tripura",
]

DISTRICT_ALIASES = {}
for d in TR_DISTRICTS:
    DISTRICT_ALIASES[d.upper()] = d
    DISTRICT_ALIASES[d] = d

_extra = {
    # Spelling variants
    "SIPAHIJALA": "Sepahijala",
    "SIPAHIJOLA": "Sepahijala",
    "SEPAHIJOLA": "Sepahijala",
    "SEPHAIJALA": "Sepahijala",
    "SEPHAIJOLA": "Sepahijala",
    "GOMTI": "Gomati",
    "UNNAKOTI": "Unakoti",
    "UNOKOTI": "Unakoti",
    "UNAKOTI TRIPURA": "Unakoti",
    # Short forms used in horizontal headers
    "WEST": "West Tripura",
    "NORTH": "North Tripura",
    "SOUTH": "South Tripura",
    "WEST TRIPURA TOTAL": "West Tripura",
    "NORTH TRIPURA TOTAL": "North Tripura",
    "SOUTH TRIPURA TOTAL": "South Tripura",
    "DHALAI TOTAL": "Dhalai",
    "GOMATI TOTAL": "Gomati",
    "KHOWAI TOTAL": "Khowai",
    "SEPAHIJALA TOTAL": "Sepahijala",
    "SIPAHIJALA TOTAL": "Sepahijala",
    "UNAKOTI TOTAL": "Unakoti",
}
for k, v in list(_extra.items()):
    DISTRICT_ALIASES[k] = v
    DISTRICT_ALIASES[k.replace("  ", " ")] = v


# Rows to skip (treat as totals/aggregates, NOT districts)
SKIP_ROWS = {
    "total", "state total", "state average", "grand total", "grand_total",
    "g.total", "g. total", "gtotal", "tripura state total",
    "tripura total", "all districts", "total a", "total(a)", "total (a)",
    "total b", "total(b)", "total (b)", "subtotal", "sub total",
    "districts", "district", "name of district", "names of the districts",
    "all", "average",
}


# ─── Per-PDF metadata: meeting number, primary quarter, priority ───
PDF_META = [
    # (filename, meeting_num, primary_quarter)
    ("125th_jun2018.pdf", 125, "2018-06"),
    ("126th_sep2018.pdf", 126, "2018-09"),
    ("127th_dec2018.pdf", 127, "2018-12"),
    ("128th_mar2019.pdf", 128, "2019-03"),
    ("129th_jun2019.pdf", 129, "2019-06"),
    ("130th_sep2019.pdf", 130, "2019-09"),
    ("131st_dec2019.pdf", 131, "2019-12"),
    ("132nd_mar2020.pdf", 132, "2020-03"),
    ("133rd_sep2020.pdf", 133, "2020-09"),
    ("134th_dec2020.pdf", 134, "2020-12"),
    ("135th_mar2021.pdf", 135, "2021-03"),
    ("136th_jun2021.pdf", 136, "2021-06"),
    ("137th_sep2021.pdf", 137, "2021-09"),
    ("138th_dec2021.pdf", 138, "2021-12"),
    ("139th_mar2022.pdf", 139, "2022-03"),
    ("140th_jun2022.pdf", 140, "2022-06"),
    ("141st_sep2022.pdf", 141, "2022-09"),
    ("142nd_dec2022.pdf", 142, "2022-12"),
    ("143rd_mar2023b.pdf", 143, "2023-03"),
    ("144th_mar2023.pdf", 144, "2023-03"),
    ("145th_jun2023.pdf", 145, "2023-06"),
    ("146th_sep2023.pdf", 146, "2023-09"),
    ("147th_dec2023.pdf", 147, "2023-12"),
    ("148th_jun2024.pdf", 148, "2024-06"),
    ("149th_sep2024.pdf", 149, "2024-09"),
    ("150th_dec2024.pdf", 150, "2024-12"),
    ("151st_mar2025.pdf", 151, "2025-03"),
    ("152nd_jun2025.pdf", 152, "2025-06"),
    ("153rd_sep2025.pdf", 153, "2025-09"),
    ("154th_dec2025_agenda.pdf", 154, "2025-12"),
]

PDF_FILES = [m[0] for m in PDF_META]
MEETING_PRIMARY_QUARTER = {m[0]: m[2] for m in PDF_META}
PDF_PRIORITY = {m[0]: m[1] for m in PDF_META}  # higher = more recent

# ─── Valid quarters set for filtering noise from misread dates ───
VALID_QUARTERS = set()
for yr in range(2017, 2027):
    for mn in (3, 6, 9, 12):
        VALID_QUARTERS.add(f"{yr:04d}-{mn:02d}")

# ─── Quarter parsing ───
MONTH_NAMES = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def parse_quarter_from_text(text):
    """Return YYYY-MM or None. Recognizes many SLBC date formats."""
    if not text:
        return None
    s = re.sub(r"\s+", " ", str(text).strip())
    s_low = s.lower()
    # Reject crop-season / fiscal-year labels — they're not specific quarters
    if any(tok in s_low for tok in ("kharif", "rabi", "khariff")):
        return None

    # 1) "March, 2021", "March 2021", "Mar. 2021", "March'2021", "Mar-2025", "Sept-25"
    m = re.search(
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch|\.)?|apr(?:il)?|may|jun(?:e|\.)?|jul(?:y|\.)?|"
        r"aug(?:ust)?|sep(?:t|tember|\.)?|oct(?:ober|\.)?|nov(?:ember|\.)?|dec(?:ember|\.)?)"
        r"['’\.,\s\-]*(\d{2,4})",
        s_low,
    )
    if m:
        mon = re.sub(r"[.,]", "", m.group(1)).strip()
        mon_num = MONTH_NAMES.get(mon[:3]) or MONTH_NAMES.get(mon)
        yr_raw = int(m.group(2))
        if mon_num:
            yr = yr_raw if yr_raw > 100 else 2000 + yr_raw
            if 2017 <= yr <= 2026:
                return f"{yr:04d}-{mon_num:02d}"

    # 2) "Mar 21", "Dec 23"
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[\.,\s]*(\d{2})(?!\d)", s_low)
    if m:
        mon_num = MONTH_NAMES.get(m.group(1))
        yr2 = int(m.group(2))
        if mon_num and 17 <= yr2 <= 26:
            return f"20{yr2:02d}-{mon_num:02d}"

    # 3) "31.03.2021", "31/03/2021", "31-03-2021"
    m = re.search(r"(\d{1,2})[\./\-](\d{1,2})[\./\-](\d{2,4})", s)
    if m:
        mon = int(m.group(2)); yr = int(m.group(3))
        if yr < 100:
            yr = 2000 + yr
        if 1 <= mon <= 12 and 2017 <= yr <= 2026:
            return f"{yr:04d}-{mon:02d}"

    # 4) "FY 2019-20" -> March of end year
    m = re.search(r"fy\s*(\d{4})[\-\s](\d{2,4})", s_low)
    if m:
        end = m.group(2)
        end_yr = int(end) if len(end) == 4 else 2000 + int(end)
        if 2018 <= end_yr <= 2026:
            return f"{end_yr:04d}-03"

    # 5) "2019-20" year-range
    m = re.search(r"\b(\d{4})\-(\d{2,4})\b", s)
    if m:
        y1 = int(m.group(1)); end = m.group(2)
        y2 = int(end) if len(end) == 4 else 2000 + int(end)
        if 2017 <= y1 <= 2026 and y2 == y1 + 1:
            return f"{y2:04d}-03"

    return None


def quarter_label(code):
    if not code:
        return None
    yr, mon = code.split("-")
    names = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May",
             6: "June", 7: "July", 8: "August", 9: "September",
             10: "October", 11: "November", 12: "December"}
    return f"{names[int(mon)]} {yr}"


# ─── Category classification ───
CATEGORY_RULES = [
    {"kw": ["ATM ALLOCATION"], "cat": "branch_network"},
    {"kw": ["DEPLOYMENT OF ATM"], "cat": "branch_network"},
    {"kw": ["BANK BRANCHES PER"], "cat": "branch_network"},
    {"kw": ["NETWORK OF BANK"], "cat": "branch_network"},
    {"kw": ["BANK BRANCH"], "cat": "branch_network"},
    {"kw": ["DISTRICT WISE DISTRIBUTION OF BANK"], "cat": "branch_network"},
    {"kw": ["BC OUTLET"], "cat": "branch_network"},
    {"kw": ["BC/CSP"], "cat": "branch_network"},
    {"kw": ["BUSINESS CORRESPONDENT"], "cat": "branch_network"},
    {"kw": ["BANKWISE POSITION OF ATM"], "cat": "branch_network"},
    {"kw": ["CD RATIO"], "cat": "credit_deposit_ratio"},
    {"kw": ["C D RATIO"], "cat": "credit_deposit_ratio"},
    {"kw": ["C.D. RATIO"], "cat": "credit_deposit_ratio"},
    {"kw": ["C.D RATIO"], "cat": "credit_deposit_ratio"},
    {"kw": ["CREDIT DEPOSIT RATIO"], "cat": "credit_deposit_ratio"},
    {"kw": ["CDR"], "cat": "credit_deposit_ratio"},
    {"kw": ["TOTAL DEPOSIT", "TOTAL ADVANCE"], "cat": "credit_deposit_ratio"},
    {"kw": ["VITAL BANKING"], "cat": "credit_deposit_ratio"},
    {"kw": ["DEBIT", "RUPAY"], "cat": "digital_transactions"},
    {"kw": ["INTERNET BANKING"], "cat": "digital_transactions"},
    {"kw": ["MOBILE BANKING"], "cat": "digital_transactions"},
    {"kw": ["AEPS"], "cat": "digital_transactions"},
    {"kw": ["DIGITAL"], "cat": "digital_transactions"},
    {"kw": ["BHIM"], "cat": "digital_transactions"},
    {"kw": ["UPI"], "cat": "digital_transactions"},
    {"kw": ["POS", "QR"], "cat": "digital_transactions"},
    {"kw": ["COVERAGE PERCENTAGE", "ELIGIBLE"], "cat": "digital_transactions"},
    {"kw": ["BSBDA"], "cat": "pmjdy"},
    {"kw": ["PMJDY"], "cat": "pmjdy"},
    {"kw": ["PM JDY"], "cat": "pmjdy"},
    {"kw": ["PM-JDY"], "cat": "pmjdy"},
    {"kw": ["JAN DHAN"], "cat": "pmjdy"},
    {"kw": ["KCC"], "cat": "kcc"},
    {"kw": ["KISAN CREDIT"], "cat": "kcc"},
    {"kw": ["SHG"], "cat": "shg"},
    {"kw": ["SELF HELP GROUP"], "cat": "shg"},
    {"kw": ["NRLM"], "cat": "shg"},
    {"kw": ["NERLP"], "cat": "shg"},
    {"kw": ["JLG"], "cat": "shg"},
    {"kw": ["PMJJBY"], "cat": "social_security"},
    {"kw": ["PMSBY"], "cat": "social_security"},
    {"kw": ["APY"], "cat": "social_security"},
    {"kw": ["ATAL PENSION"], "cat": "social_security"},
    {"kw": ["SOCIAL SECURITY"], "cat": "social_security"},
    {"kw": ["PMAY"], "cat": "housing_pmay"},
    {"kw": ["HOUSING"], "cat": "housing_pmay"},
    {"kw": ["EDUCATION LOAN"], "cat": "education_loan"},
    {"kw": ["MUDRA"], "cat": "mudra"},
    {"kw": ["PMMY"], "cat": "mudra"},
    {"kw": ["PMEGP"], "cat": "pmegp"},
    {"kw": ["NPS"], "cat": "nps"},
    {"kw": ["NATIONAL PENSION"], "cat": "nps"},
    {"kw": ["WOMEN", "FEMALE"], "cat": "women_finance"},
    {"kw": ["WOMEN ACCOUNTS"], "cat": "women_finance"},
    {"kw": ["SC/ST"], "cat": "sc_st_finance"},
    {"kw": ["WEAKER SECTION"], "cat": "sc_st_finance"},
    {"kw": ["MINORITY"], "cat": "minority_finance"},
    {"kw": ["AADHAAR SEED"], "cat": "aadhaar_authentication"},
    {"kw": ["AADHAAR AUTH"], "cat": "aadhaar_authentication"},
    {"kw": ["AADHAAR"], "cat": "aadhaar_authentication"},
    {"kw": ["FINANCIAL LITERACY"], "cat": "financial_literacy"},
    {"kw": ["FLC"], "cat": "financial_literacy"},
    {"kw": ["RSETI"], "cat": "rseti"},
    {"kw": ["NULM"], "cat": "nulm"},
    {"kw": ["SEP"], "cat": "nulm"},
    {"kw": ["STAND UP INDIA"], "cat": "stand_up_india"},
    {"kw": ["RECOVERY"], "cat": "recovery"},
    {"kw": ["NPA"], "cat": "npa"},
    {"kw": ["ACP"], "cat": "acp"},
    {"kw": ["ANNUAL CREDIT PLAN"], "cat": "acp"},
    {"kw": ["PRIORITY SECTOR"], "cat": "priority_sector"},
    {"kw": ["GRAM SWARAJ"], "cat": "gram_swaraj"},
    {"kw": ["BRANCH OPENING"], "cat": "branch_opening"},
    {"kw": ["UNBANKED"], "cat": "branch_opening"},
]


def classify_category(*title_texts):
    combined = " ".join([t for t in title_texts if t])
    if not combined:
        return "misc"
    normalized = re.sub(r"\s+", " ", combined).upper()
    for rule in CATEGORY_RULES:
        if all(kw in normalized for kw in rule["kw"]):
            return rule["cat"]
    # fallback: snake_case from first English words
    words = re.findall(r"[A-Za-z]+", combined.lower())
    noise = {"district", "sr", "no", "amt", "rs", "source", "annex", "i", "ii",
             "iii", "iv", "tripura", "state", "total", "table", "as", "on",
             "the", "of", "in", "for", "and", "name", "wise"}
    words = [w for w in words if w not in noise and len(w) > 1]
    if words:
        return "_".join(words[:3])[:40] or "misc"
    return "misc"


# ─── District normalization ───
def normalize_district(name):
    if not name:
        return None
    name = str(name).strip()
    if not name:
        return None
    # Replace newlines and excessive whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Strip leading numeric serial like "1.", "01", "1)", "1 "
    name_stripped = re.sub(r"^\s*\d+[\.\)\s]+", "", name).strip()
    # Strip trailing markers like "*"
    name_stripped = name_stripped.rstrip("*").strip()

    # Direct lookup using both stripped and original
    for cand in (name_stripped, name):
        upper = cand.upper().strip(".,:;*(){}[] ")
        if upper in DISTRICT_ALIASES:
            return DISTRICT_ALIASES[upper]
    # Skip obvious non-district rows
    lower = name_stripped.lower().strip(".,:;*(){}[] ")
    if not lower or lower in SKIP_ROWS:
        return None
    # Strip trailing " Total" suffix and retry
    if lower.endswith(" total"):
        base = name_stripped[:-len(" Total")].strip().upper()
        if base in DISTRICT_ALIASES:
            return DISTRICT_ALIASES[base]
    # Strip parentheses contents and retry
    no_paren = re.sub(r"\s*\([^)]*\)\s*", "", name_stripped).strip()
    upper2 = no_paren.upper().strip(".,:;*(){}[] ")
    if upper2 in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[upper2]
    # Substring match — only if the alias is reasonably long (5+ chars)
    upper_full = name.upper()
    for alias, canon in DISTRICT_ALIASES.items():
        if len(alias) >= 6 and alias in upper_full:
            return canon
    return None


# ─── Number parsing ───
def parse_number(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s or s in {"-", "--", "---", "NA", "N/A", "NIL", "Nil", "nil", "…", ".", "*", "—", "–"}:
        return None
    s = s.replace(",", "").replace("%", "").replace("₹", "").replace("`", "")
    s = re.sub(r"\*+$", "", s).strip()
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    m = re.match(r"^-?\d+\.?\d*$", s)
    if m:
        try:
            return float(s)
        except Exception:
            return None
    return None


# ─── Field name normalization ───
def snake_case(s):
    if not s:
        return ""
    s = str(s)
    s = s.replace("\n", " ").replace("\r", " ")
    # Remove unit parentheticals
    s = re.sub(
        r"\((?:amt\.?\s*in\s*cr\.?|amt\.?\s*in\s*rs\.?|rs\.?\s*in\s*cr\.?|"
        r"amt\.?\s*in\s*lacs?|no\.?\s*in\s*lacs?|in\s*lacs?|in\s*crores?|"
        r"amt\.?|no\.?|rs\.?|a|asp\.?)\)",
        "", s, flags=re.I,
    )
    s = s.replace("%", " pct ").replace("/", " ").replace("-", " ").replace("&", " and ")
    s = re.sub(r"\bno\.?\b", "no", s, flags=re.I)
    s = re.sub(r"\bamt\.?\b", "amt", s, flags=re.I)
    s = re.sub(r"\bo\/s\b", "os", s, flags=re.I)
    s = re.sub(r"\ba\/c\b", "ac", s, flags=re.I)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


# Strip leading digits / numeric tokens that shouldn't appear in field names.
def _strip_numeric_tokens(snake):
    if not snake:
        return snake
    parts = [p for p in snake.split("_") if p]
    out = []
    for p in parts:
        # If the token is purely numeric and longer than 1 char, drop it
        if re.match(r"^\d{1,}$", p) and len(p) >= 2:
            continue
        # Strip mixed numeric prefix like "31_57_805"
        out.append(p)
    return "_".join(out)


def make_field_name(category_hint, metric, subtype=None):
    metric_snake = snake_case(metric or "")
    out = metric_snake
    if subtype:
        sub_snake = snake_case(subtype)
        if sub_snake and sub_snake not in out:
            out = f"{out}_{sub_snake}" if out else sub_snake
    # remove sequential numeric tokens from anywhere in the field name
    # (e.g., a stray digit that came from a header cell)
    out = re.sub(r"_\d{2,}(?=_|$)", "", out)
    out = re.sub(r"^\d{2,}_", "", out)
    out = re.sub(r"_+", "_", out).strip("_")
    # deduplicate repeated tokens
    toks = out.split("_")
    dedup = []
    for t in toks:
        if not t:
            continue
        if dedup and dedup[-1] == t:
            continue
        dedup.append(t)
    out = "_".join(dedup)
    return out or "value"


# ─── Standardization for FI timeseries keys (per CLAUDE.md guidance) ───
FIELD_STANDARDIZE_MAP = {
    # CD Ratio
    "cd_ratio": "overall_cd_ratio",
    "c_d_ratio": "overall_cd_ratio",
    "c_d_ratio_pct": "overall_cd_ratio",
    "cd_ratio_pct": "overall_cd_ratio",
    "credit_deposit_ratio": "overall_cd_ratio",
    "total_deposite": "total_deposit",
    "deposit": "total_deposit",
    "deposits": "total_deposit",
    "total_deposits": "total_deposit",
    "advances": "total_advances",
    "total_advance": "total_advances",
    "advance": "total_advances",
    "no_of_branches": "total_branch",
    "no_of_branch": "total_branch",
    "no_of_brs": "total_branch",
    # PMJDY
    "no_of_pmjdy_accounts": "total_pmjdy_no",
    "no_of_pmjdy_ac": "total_pmjdy_no",
    "no_of_active_pmjdy_a_c": "total_pmjdy_no",
    "no_of_active_pmjdy_ac": "total_pmjdy_no",
    "total_pmjdy_a_c": "total_pmjdy_no",
    "total_pmjdy_ac": "total_pmjdy_no",
    "no_of_pmjdy_accounts_female": "female_no",
    "pmjdy_female_a_c": "female_no",
    "female_a_c": "female_no",
    "no_of_pmjdy_accounts_male": "male_no",
    "pmjdy_male_a_c": "male_no",
    "male_a_c": "male_no",
    # KCC
    "total_no_of_kcc_issued": "total_no_of_kcc",
    "total_no_of_kcc_issued_no": "total_no_of_kcc",
    "no_of_kcc": "total_no_of_kcc",
    # SHG
    "total_no_of_shg": "savings_linked_no",
    "no_of_shgs_savings_linked": "savings_linked_no",
    "shg_savings_linked_no": "savings_linked_no",
    "deposit_linkage_no_of_groups": "savings_linked_no",
    "deposit_linkage_no": "savings_linked_no",
    "no_of_shgs_credit_linked": "credit_linked_no",
    "shg_credit_linked_no": "credit_linked_no",
    "credit_linkage_no": "credit_linked_no",
    "credit_linked_no_no": "credit_linked_no",
}


def standardize_field(snake):
    if snake in FIELD_STANDARDIZE_MAP:
        return FIELD_STANDARDIZE_MAP[snake]
    return snake


# ─── Core: parsing pdfplumber tables ───

def cell_text(c):
    if c is None:
        return ""
    return re.sub(r"\s+", " ", str(c)).strip()


def find_district_col(rows, max_check=None):
    """Return the column index most likely to contain district names.

    Scans ALL rows by default (not just the first 30) since district-summary
    rows may appear at the END of bankwise+districtwise combined tables.
    """
    if not rows:
        return 0
    max_cols = max(len(r) for r in rows if r) if rows else 0
    best = 0
    best_score = -1
    for col in range(min(max_cols, 6)):
        score = 0
        rows_to_check = rows if max_check is None else rows[:max_check]
        for row in rows_to_check:
            if not row or len(row) <= col:
                continue
            if normalize_district(str(row[col])):
                score += 1
        if score > best_score:
            best_score = score
            best = col
    return best if best_score >= 3 else 0


# ─── Reject tables that aren't real district-wise data ───
TOC_HINT_PATTERNS = (
    "annexures", "agenda item", "page no.", "sr. no.", "sl. no.",
    "table of contents", "contents",
)


def is_toc_or_listing_table(table):
    """Detect table-of-contents / annexure-listing tables.

    These tables contain district names buried in descriptive sentences
    rather than as standalone first-column values.
    """
    if not table or len(table) < 3:
        return False
    # Inspect first 3 rows for TOC-ish keywords
    head_text = " ".join(
        str(c).lower() for r in table[:3] for c in (r or []) if c
    )
    toc_hits = sum(1 for p in TOC_HINT_PATTERNS if p in head_text)
    if toc_hits >= 2:
        return True
    # Page-letter column (A, B, C, ...) pattern
    if len(table[0] or []) <= 4:
        # Check if last column is mostly single letters
        last_vals = []
        for r in table[3:15]:
            if r and len(r) >= 1:
                last_vals.append(str(r[-1] or "").strip())
        single_letters = sum(1 for v in last_vals if re.match(r"^[A-Z]{1,2}$", v))
        if single_letters >= 5:
            return True
    return False


def is_bankwise_table(table, district_col):
    """Heuristic: a 'bank-wise' table repeats districts because each row is one bank.

    If any single district appears more than 2 times in the district column,
    it's almost certainly a bank-wise (within-district) table — skip it."""
    if not table:
        return False
    counts = defaultdict(int)
    for row in table:
        if not row or len(row) <= district_col:
            continue
        d = normalize_district(str(row[district_col]))
        if d:
            counts[d] += 1
    if any(c > 2 for c in counts.values()):
        return True
    return False


def get_header_rows(table, district_col, max_header_lookback=4):
    """Return (header_rows_above_data, data_start_index, data_end_index).

    Locate the FIRST district row; treat up to `max_header_lookback` rows
    immediately above it as headers. This avoids treating bank-wise rows
    above the district section as headers in combined tables.

    data_end is the index AFTER the last consecutive district-or-numeric row
    starting from data_start (used to terminate at "Total" or trailing junk).
    """
    # Find first district row
    first_dist = None
    for i, row in enumerate(table):
        if not row:
            continue
        if len(row) > district_col and normalize_district(str(row[district_col])):
            first_dist = i
            break
    if first_dist is None:
        return [], len(table), len(table)
    header_start = max(0, first_dist - max_header_lookback)
    header_rows = table[header_start:first_dist]
    # Find data_end: last contiguous district-row block (allowing blank rows)
    data_end = first_dist
    blank_streak = 0
    for j in range(first_dist, len(table)):
        row = table[j]
        if not row:
            blank_streak += 1
            if blank_streak > 1:
                break
            continue
        if len(row) > district_col and normalize_district(str(row[district_col])):
            data_end = j + 1
            blank_streak = 0
        else:
            # Allow one non-district row (could be totals) before stopping
            cell = row[district_col] if len(row) > district_col else ""
            cell_str = str(cell or "").strip().lower()
            if cell_str in {"total", "state total", "grand total", "all"}:
                break
            blank_streak += 1
            if blank_streak > 1:
                break
    return header_rows, first_dist, data_end


def forward_fill_row(row):
    filled = []
    last = ""
    for c in row or []:
        v = cell_text(c)
        if v:
            last = v
            filled.append(v)
        else:
            filled.append(last)
    return filled


SECTION_TITLE_RE = re.compile(r"^\s*\(\s*[a-z]\s*\)|^\s*[A-Z]\.\s|indicators?\s*:", re.I)


def _is_section_title_row(row):
    non_empty = [c for c in row if c and str(c).strip()]
    if len(non_empty) != 1:
        return False
    txt = str(non_empty[0]).strip()
    if len(txt) < 5:
        return False
    return bool(SECTION_TITLE_RE.search(txt))


def build_column_map(header_rows, total_cols, district_col):
    """
    Returns list of dicts per column index (or None for district_col):
      {'metric': str, 'quarter': 'YYYY-MM' or None, 'subtype': str or None,
       'is_delta': bool}
    """
    filtered_headers = [r for r in header_rows if not _is_section_title_row(r or [])]

    ffilled = []
    for r in filtered_headers:
        padded = list(r or []) + [None] * max(0, total_cols - len(r or []))
        ffilled.append(forward_fill_row(padded[:total_cols]))

    # Decide which rows are "quarter rows"
    row_is_quarter = []
    for row in ffilled:
        quarters = 0
        non_empty = 0
        for i, c in enumerate(row):
            if i == district_col:
                continue
            if c and str(c).strip():
                non_empty += 1
                if parse_quarter_from_text(c):
                    quarters += 1
        row_is_quarter.append(non_empty > 0 and quarters >= max(2, non_empty * 0.4))

    col_info = []
    for col in range(total_cols):
        if col == district_col:
            col_info.append(None)
            continue
        metric_parts = []
        subtype = None
        quarter = None
        is_delta = False
        for ri, row in enumerate(ffilled):
            c = row[col] if col < len(row) else ""
            c = cell_text(c)
            if not c:
                continue
            c_low = c.lower()
            # Detect Q-o-Q / Y-o-Y delta columns — we want to skip these
            if (
                "q o q" in c_low or "qoq" in c_low or "q-o-q" in c_low or
                "y o y" in c_low or "yoy" in c_low or "y-o-y" in c_low or
                "since " in c_low or "change" in c_low and ("q" in c_low or "y" in c_low)
            ):
                is_delta = True
            if row_is_quarter[ri]:
                q = parse_quarter_from_text(c)
                if q and not quarter:
                    quarter = q
                elif not q:
                    metric_parts.append(c)
            else:
                c_clean = re.sub(r"\s+", "", c).lower()
                if c_clean in {"no.", "no", "amt.", "amt", "amt.o/s", "amto/s",
                               "amtos", "(i)", "(ii)", "(iii)", "(iv)", "(v)",
                               "male", "female", "target", "achievement"}:
                    if subtype:
                        subtype = f"{subtype} {c}"
                    else:
                        subtype = c
                else:
                    metric_parts.append(c)

        ded_parts = []
        for p in metric_parts:
            if not ded_parts or ded_parts[-1] != p:
                ded_parts.append(p)
        metric = " ".join(ded_parts).strip()
        col_info.append({
            "metric": metric,
            "quarter": quarter,
            "subtype": subtype,
            "is_delta": is_delta,
        })
    return col_info


def detect_amount_unit(header_rows, title_text):
    """Return True if amounts are in Crores."""
    text = (title_text or "") + " "
    for r in header_rows:
        for c in (r or []):
            if c:
                text += str(c) + " "
    low = text.lower()
    indicators = (
        "amt. in cr", "amt in cr", "amount in cr", "amount rs. in cr",
        "rs. in cr", "rs in cr", "in crore", "in cr.", "(` in cr",
        "(`in cr", "(rs in cr", "(rs. in cr", "(amt rs. in cr",
        "amount rs. in crore",
    )
    for ind in indicators:
        if ind in low:
            return True
    return False


def page_title_text(page):
    """Extract leading non-empty lines from the page (above first district)."""
    text = page.extract_text() or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    out = []
    district_keywords = [d.lower() for d in TR_DISTRICTS] + ["sipahijala", "sepahijala"]
    for ln in lines[:12]:
        lnl = ln.lower()
        if any(d in lnl for d in district_keywords):
            break
        out.append(ln)
    return " | ".join(out)


def page_text_segments(page):
    """Return a list of prefix text-line lists, one per district block on the page.
    segs[i] = lines preceding the i-th district block."""
    text = page.extract_text() or ""
    lines = text.split("\n")
    segs = []
    current_prefix = []
    in_district_block = False
    district_keywords = (
        "dhalai", "gomati", "khowai", "north tripura", "sepahijala",
        "sipahijala", "south tripura", "unakoti", "west tripura",
    )
    for ln in lines:
        ll = ln.lower()
        is_dist = any(d in ll for d in district_keywords)
        if is_dist:
            if not in_district_block:
                segs.append(list(current_prefix))
                current_prefix = []
                in_district_block = True
        else:
            if in_district_block:
                in_district_block = False
            current_prefix.append(ln)
    return segs


def _looks_like_garbled_text(s):
    """Detect text that's been mangled by character-by-character extraction
    (e.g. rotated text with single-letter lines)."""
    if not s:
        return True
    # Heuristic: if the text has many short tokens (length 1-2) it's garbled
    tokens = re.findall(r"\S+", s)
    if not tokens:
        return True
    short = sum(1 for t in tokens if len(t) <= 2)
    if len(tokens) >= 8 and short / len(tokens) > 0.6:
        return True
    return False


def _title_to_metric_hint(lines):
    if not lines:
        return ""
    text_joined = " ".join(l.strip() for l in lines if l.strip())
    ascii_only = re.sub(r"[^\x20-\x7E]", " ", text_joined)
    ascii_only = re.sub(r"\s+", " ", ascii_only).strip()
    if _looks_like_garbled_text(ascii_only):
        return ""
    parts = re.split(r"[:\|]", ascii_only)
    if parts:
        for p in reversed(parts):
            p = p.strip()
            if _looks_like_garbled_text(p):
                continue
            if re.search(
                r"(?i)no\.\s*of|total|per\s+(one\s+)?lakh|c\.?d\.?\s*ratio|"
                r"deposit|advance|kcc|shg|pmjdy|coverage|atm|branch",
                p,
            ):
                return p[:120]
        # Take last non-garbled part
        for p in reversed(parts):
            p = p.strip()
            if not _looks_like_garbled_text(p):
                return p[:120]
    return ""


# ─── Per-PDF extraction ───

def extract_pdf(pdf_path):
    """Yield (category, quarter_code, district, field, value, pdf_name, page_num)."""
    pdf_name = pdf_path.name
    primary_q = MEETING_PRIMARY_QUARTER.get(pdf_name)

    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages):
            title = page_title_text(page)
            prefix_segs = page_text_segments(page)

            try:
                tables = page.extract_tables()
            except Exception:
                tables = []

            district_table_idx = 0
            for ti, table in enumerate(tables):
                if not table or len(table) < 3:
                    continue
                row_lens = [len(r) for r in table if r]
                if not row_lens:
                    continue
                max_cols = max(row_lens)
                if max_cols < 2:
                    continue

                # Skip TOC / annexure-listing tables (district names buried
                # inside descriptive sentences)
                if is_toc_or_listing_table(table):
                    continue

                district_col = find_district_col(table)
                d_count = 0
                for row in table:
                    if not row:
                        continue
                    if len(row) > district_col and normalize_district(str(row[district_col])):
                        d_count += 1
                if d_count < 4:
                    # Not a district-wise table
                    continue

                # Skip bank-wise tables that repeat districts
                if is_bankwise_table(table, district_col):
                    continue

                header_rows, data_start, data_end = get_header_rows(table, district_col)
                col_info = build_column_map(header_rows, max_cols, district_col)
                is_crore = detect_amount_unit(header_rows, title)

                header_text_blob = " ".join(
                    str(c) for r in header_rows for c in (r or []) if c
                )
                prefix_lines = (
                    prefix_segs[district_table_idx]
                    if district_table_idx < len(prefix_segs)
                    else []
                )
                prefix_blob = " ".join(l for l in prefix_lines if l.strip())
                category = classify_category(title, header_text_blob, prefix_blob)
                # Skip junk fallback categories that don't carry meaningful metrics
                if category in {"misc"} or category.startswith("sl_") or category.startswith("name_of_"):
                    continue
                metric_fallback = _title_to_metric_hint(prefix_lines)
                for ci, ci_info in enumerate(col_info):
                    if ci_info and not ci_info.get("metric") and ci_info.get("quarter"):
                        ci_info["metric"] = metric_fallback
                district_table_idx += 1

                for row in table[data_start:data_end]:
                    if not row:
                        continue
                    if len(row) <= district_col:
                        continue
                    dist = normalize_district(str(row[district_col]))
                    if not dist:
                        continue
                    for ci, ci_info in enumerate(col_info):
                        if ci_info is None or ci >= len(row):
                            continue
                        if ci_info.get("is_delta"):
                            # Skip Q-o-Q / Y-o-Y change columns
                            continue
                        val = parse_number(row[ci])
                        if val is None:
                            continue
                        metric = ci_info.get("metric") or ""
                        subtype = ci_info.get("subtype")
                        quarter = ci_info.get("quarter") or primary_q
                        if quarter not in VALID_QUARTERS:
                            continue
                        field = make_field_name(category, metric, subtype)
                        if not field or field == "value":
                            continue
                        # Skip suspicious fields with embedded long digit runs
                        if re.search(r"_\d{3,}", field):
                            continue
                        # Skip serial-number / page-letter columns
                        if field in {"sl", "sl_no", "s_no", "sr_no", "sr", "page",
                                     "page_no", "no", "s", "sl_block_bank",
                                     "name_of_district", "name_of_districts",
                                     "district_name", "particular", "particulars",
                                     "name", "i", "ii", "iii", "iv", "v",
                                     "total_sl", "sl_total", "sl_no_total"}:
                            continue
                        # Skip fields that end with "_sl" (likely serial-number leak)
                        if field.endswith("_sl") or field.startswith("sl_"):
                            continue
                        # Reject garbled fields (many single-character tokens)
                        toks = field.split("_")
                        if len(toks) >= 6:
                            short = sum(1 for t in toks if len(t) <= 2)
                            if short / len(toks) > 0.5:
                                continue
                        # Reject extremely long field names (likely a header leak)
                        if len(field) > 200:
                            continue
                        is_amount = any(
                            k in field for k in (
                                "amt", "deposit", "advance", "loan_os",
                                "outstanding", "amount", "disbursed", "sanctioned",
                            )
                        )
                        value_out = val
                        if is_crore and is_amount:
                            value_out = val * 100.0
                        yield (
                            category, quarter, dist, field, value_out,
                            pdf_name, pno + 1,
                        )


# ─── Main ───

def format_value(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def main():
    all_records = []
    per_pdf_stats = defaultdict(int)
    for pdf_name in PDF_FILES:
        p = DIR / pdf_name
        if not p.exists():
            print(f"[WARN] missing {p}")
            continue
        print(f"[INFO] extracting {pdf_name} ...", flush=True)
        count = 0
        try:
            for rec in extract_pdf(p):
                all_records.append(rec)
                count += 1
        except Exception as e:
            print(f"[ERR] {pdf_name}: {e}")
        per_pdf_stats[pdf_name] = count
        print(f"       {count} records", flush=True)

    print(f"\n[INFO] Total raw records: {len(all_records)}")

    # Dedup: prefer most recent PDF
    best = {}
    for rec in all_records:
        category, quarter, district, field, value, pdf_name, pno = rec
        prio = PDF_PRIORITY.get(pdf_name, 0)
        key = (quarter, district, category, field)
        prev = best.get(key)
        if prev is None or prio > prev[0]:
            best[key] = (prio, value, pdf_name, pno)

    print(f"[INFO] Unique (quarter, district, category, field): {len(best)}")

    # Build outputs
    quarters_out = {}
    fi_timeseries = {}

    for (qcode, district, category, field), (_prio, value, pdf_name, pno) in best.items():
        q = quarters_out.setdefault(qcode, {"period": quarter_label(qcode), "tables": {}})
        tbl = q["tables"].setdefault(category, {"fields": [], "districts": {}})
        if field not in tbl["fields"]:
            tbl["fields"].append(field)
        row = tbl["districts"].setdefault(district, {})
        row[field] = format_value(value)

        standard_field = standardize_field(field)
        fkey = f"{category}__{standard_field}"
        fi_timeseries.setdefault(qcode, {}).setdefault(
            district, {"district": district, "period": quarter_label(qcode)}
        )[fkey] = value

    qcodes_sorted = sorted(quarters_out.keys())

    # tripura_complete.json
    complete = {"state": "Tripura", "quarters": OrderedDict()}
    for q in qcodes_sorted:
        complete["quarters"][q] = quarters_out[q]
    (DIR / "tripura_complete.json").write_text(
        json.dumps(complete, indent=2, ensure_ascii=False)
    )
    print(f"[OK] wrote tripura_complete.json ({len(qcodes_sorted)} quarters)")

    # tripura_fi_timeseries.json
    periods_list = []
    for q in qcodes_sorted:
        districts = sorted(
            fi_timeseries.get(q, {}).values(),
            key=lambda d: (
                TR_DISTRICTS.index(d["district"]) if d["district"] in TR_DISTRICTS else 999
            ),
        )
        periods_list.append({"period": quarter_label(q), "districts": districts})
    (DIR / "tripura_fi_timeseries.json").write_text(
        json.dumps({"periods": periods_list}, indent=2, ensure_ascii=False, default=str)
    )
    print(f"[OK] wrote tripura_fi_timeseries.json ({len(periods_list)} periods)")

    # tripura_fi_timeseries.csv
    all_keys = set()
    for q in fi_timeseries.values():
        for d in q.values():
            all_keys.update(k for k in d.keys() if k not in ("district", "period"))
    col_order = ["district", "period"] + sorted(all_keys)
    with open(DIR / "tripura_fi_timeseries.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(col_order)
        for q in qcodes_sorted:
            for d in fi_timeseries.get(q, {}).values():
                w.writerow([d.get(k, "") for k in col_order])
    print(
        f"[OK] wrote tripura_fi_timeseries.csv "
        f"({sum(len(v) for v in fi_timeseries.values())} rows, {len(col_order)} cols)"
    )

    # quarterly CSVs
    quarterly_dir = DIR / "quarterly"
    if quarterly_dir.exists():
        import shutil
        shutil.rmtree(quarterly_dir)
    quarterly_dir.mkdir(exist_ok=True)
    for q in qcodes_sorted:
        qdir = quarterly_dir / q
        qdir.mkdir(exist_ok=True)
        for cat, tbl in quarters_out[q]["tables"].items():
            fpath = qdir / f"{cat}.csv"
            cols = ["district"] + tbl["fields"]
            with open(fpath, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for dist in TR_DISTRICTS:
                    if dist in tbl["districts"]:
                        row = [dist] + [tbl["districts"][dist].get(fld, "") for fld in tbl["fields"]]
                        w.writerow(row)

    # Summary
    print("\n=== SUMMARY ===")
    print(f"Quarters: {len(qcodes_sorted)}")
    for q in qcodes_sorted:
        districts = set()
        for tbl in quarters_out[q]["tables"].values():
            districts.update(tbl["districts"].keys())
        cats = list(quarters_out[q]["tables"].keys())
        print(f"  {q} ({quarter_label(q)}): {len(districts)}/8 districts, {len(cats)} cats")

    combo_counts = defaultdict(int)
    for (qcode, district, category, field) in best.keys():
        combo_counts[(category, field)] += 1
    top10 = sorted(combo_counts.items(), key=lambda kv: -kv[1])[:10]
    print("\nTop 10 (category, field) by quarter-district count:")
    for (cat, fld), cnt in top10:
        print(f"  {cat}.{fld}: {cnt}")

    print("\nFI indicator coverage per quarter:")
    fi_cats = [
        "credit_deposit_ratio", "pmjdy", "branch_network", "kcc", "shg",
        "digital_transactions", "women_finance",
    ]
    header = "Quarter      " + " ".join(f"{c[:14]:>14}" for c in fi_cats)
    print(header)
    for q in qcodes_sorted:
        row_counts = {}
        for cat in fi_cats:
            tbl = quarters_out[q]["tables"].get(cat, {})
            row_counts[cat] = len(tbl.get("districts", {}))
        print(f"{q}   " + " ".join(f"{row_counts[c]:>14d}" for c in fi_cats))


if __name__ == "__main__":
    main()
