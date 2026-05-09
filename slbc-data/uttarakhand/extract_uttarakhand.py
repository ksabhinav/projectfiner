#!/usr/bin/env python3
"""
Uttarakhand SLBC Agenda Book Extractor
======================================
Extracts district-wise tables from 11 text-extractable UK SLBC agenda PDFs
(76th, 77th, 78th_spl, 79th, 82nd, 83rd, 84th_spl, 85th, 86th, 87th, 88th).

Distinguishing feature: UK tables contain MULTIPLE QUARTERS side-by-side as columns.
A single row for a district may hold 12+ (metric, quarter) cells. The parser emits
(quarter_code, district, category, field) -> value tuples.

Outputs (all in slbc-data/uttarakhand/):
    uttarakhand_complete.json
    uttarakhand_fi_timeseries.json
    uttarakhand_fi_timeseries.csv
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

# ─── 13 canonical Uttarakhand districts ───
UK_DISTRICTS = [
    "Almora", "Bageshwar", "Chamoli", "Champawat", "Dehradun", "Haridwar",
    "Nainital", "Pauri Garhwal", "Pithoragarh", "Rudraprayag", "Tehri Garhwal",
    "Udham Singh Nagar", "Uttarkashi",
]

DISTRICT_ALIASES = {}
for d in UK_DISTRICTS:
    DISTRICT_ALIASES[d.upper()] = d
    DISTRICT_ALIASES[d] = d

_extra = {
    "HARDWAR": "Haridwar", "HARDWAR (A)": "Haridwar", "HARDWAR (ASP.)": "Haridwar",
    "HARIDWAR (A)": "Haridwar", "HARIDWAR (ASP.)": "Haridwar",
    "HARDWAR(A)": "Haridwar", "HARIDWAR(A)": "Haridwar",
    "HARIDWAR(ASP.)": "Haridwar", "HARDWAR(ASP.)": "Haridwar",
    "U.S. NAGAR": "Udham Singh Nagar", "U.S.NAGAR": "Udham Singh Nagar",
    "US NAGAR": "Udham Singh Nagar", "U S NAGAR": "Udham Singh Nagar",
    "USNAGAR": "Udham Singh Nagar", "U.S. NAGAR (A)": "Udham Singh Nagar",
    "U.S. NAGAR(A)": "Udham Singh Nagar", "U.S. NAGAR (ASP.)": "Udham Singh Nagar",
    "U.S.NAGAR(ASP.)": "Udham Singh Nagar", "U.S.NAGAR (ASP.)": "Udham Singh Nagar",
    "UDHAM SINGH NAGAR(A)": "Udham Singh Nagar",
    "UDHAM SINGH NAGAR (A)": "Udham Singh Nagar",
    "UDHAM SINGH NAGAR (ASP.)": "Udham Singh Nagar",
    "TEHRI": "Tehri Garhwal", "NEW TEHRI": "Tehri Garhwal",
    "TEHRI GARHWAL": "Tehri Garhwal",
    "PAURI": "Pauri Garhwal", "PAURI GARHWAL": "Pauri Garhwal",
    "RUDRAPRAYAG": "Rudraprayag", "RUDRA PRAYAG": "Rudraprayag",
    "RUDRA-PRAYAG": "Rudraprayag",
}
for k, v in list(_extra.items()):
    DISTRICT_ALIASES[k] = v
    DISTRICT_ALIASES[k.replace("  ", " ")] = v

# Rows to skip
SKIP_ROWS = {
    "total", "state total", "state average", "grand total", "total g.m", "total k.m",
    "total garhwal mandal", "total kumaon mandal", "total (a+b)", "g.total", "g. total",
    "g.total", "total(a+b)", "a total g.m", "b total k.m", "c g. total", "c g.total",
    "total (a)", "total(a)", "total (b)", "total(b)",
}


# ─── Meeting → primary (most recent) quarter ordering for dedup priority ───
# higher number = more recent PDF = higher priority when merging
PDF_PRIORITY = {
    "76th_agenda.pdf": 1,
    "77th_agenda.pdf": 2,
    "78th_spl_agenda.pdf": 3,
    "79th_agenda.pdf": 4,
    "82nd_agenda.pdf": 5,
    "83rd_agenda.pdf": 6,
    "84th_spl_agenda.pdf": 7,
    "85th_agenda.pdf": 8,
    "86th_agenda.pdf": 9,
    "87th_agenda.pdf": 10,
    "88th_agenda.pdf": 11,
}

PDF_FILES = list(PDF_PRIORITY.keys())

# Meeting → primary data date; used as fallback for tables that lack explicit quarter labels
MEETING_PRIMARY_QUARTER = {
    "76th_agenda.pdf": "2020-12",   # CD ratio table references 31/12/20
    "77th_agenda.pdf": "2021-03",   # CD ratio as on 31/03/2021
    "78th_spl_agenda.pdf": "2021-06",   # tables labelled up to June 2021
    "79th_agenda.pdf": "2021-09",   # CD ratio as on 30.09.2021
    "82nd_agenda.pdf": "2022-06",   # FLC table as on 30.06.22
    "83rd_agenda.pdf": "2022-09",   # FLC table as on 30.09.2022
    "84th_spl_agenda.pdf": "2022-12",   # tables labelled up to Dec 2022
    "85th_agenda.pdf": "2023-03",   # CD ratio as on 31.03.23
    "86th_agenda.pdf": "2023-06",
    "87th_agenda.pdf": "2023-09",
    "88th_agenda.pdf": "2023-12",   # tables labelled up to Dec 2023
}

# ─── Valid quarters set for filtering noise ───
VALID_QUARTERS = {
    "2019-03", "2019-06", "2019-09", "2019-12",
    "2020-03", "2020-06", "2020-09", "2020-12",
    "2021-03", "2021-06", "2021-09", "2021-12",
    "2022-03", "2022-06", "2022-09", "2022-12",
    "2023-03", "2023-06", "2023-09", "2023-12",
}

# ─── Quarter parsing ───
MONTH_NAMES = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

def parse_quarter_from_text(text):
    """Return YYYY-MM or None. Recognizes many UK SLBC date formats."""
    if not text:
        return None
    s = re.sub(r"\s+", " ", str(text).strip())
    s_low = s.lower()
    # Patterns
    # 1) "March, 2021", "March 2021", "Mar. 2021"
    m = re.search(r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch|\.)?|apr(?:il)?|may|jun(?:e|\.)?|jul(?:y|\.)?|aug(?:ust)?|sep(?:t|tember|\.)?|oct(?:ober|\.)?|nov(?:ember|\.)?|dec(?:ember|\.)?)[\.,\s]+(\d{4})", s_low)
    if m:
        mon = re.sub(r"[.,]", "", m.group(1)).strip()
        mon_num = MONTH_NAMES.get(mon[:3]) or MONTH_NAMES.get(mon)
        if mon_num:
            yr = int(m.group(2))
            if 2018 <= yr <= 2024:
                return f"{yr:04d}-{mon_num:02d}"
    # 2) "Mar. 21", "Dec. 23", "Mar 21"
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[\.,\s]*(\d{2})(?!\d)", s_low)
    if m:
        mon_num = MONTH_NAMES.get(m.group(1))
        yr2 = int(m.group(2))
        if mon_num and 18 <= yr2 <= 24:
            return f"20{yr2:02d}-{mon_num:02d}"
    # 3) "31.03.2021", "31/03/2021", "31-03-2021"
    m = re.search(r"(\d{1,2})[\./\-](\d{1,2})[\./\-](\d{2,4})", s)
    if m:
        mon = int(m.group(2)); yr = int(m.group(3))
        if yr < 100:
            yr = 2000 + yr
        if 1 <= mon <= 12 and 2018 <= yr <= 2024:
            return f"{yr:04d}-{mon:02d}"
    # 4) "FY 2019-20" → interpret as March-of-end-year
    m = re.search(r"fy\s*(\d{4})[\-\s](\d{2,4})", s_low)
    if m:
        end = m.group(2)
        end_yr = int(end) if len(end) == 4 else 2000 + int(end)
        if 2019 <= end_yr <= 2024:
            return f"{end_yr:04d}-03"
    # 5) "2019-20" (year-range)
    m = re.search(r"(\d{4})[\-](\d{2,4})\b", s)
    if m:
        y1 = int(m.group(1)); end = m.group(2)
        y2 = int(end) if len(end) == 4 else 2000 + int(end)
        if 2018 <= y1 <= 2023 and y2 == y1 + 1:
            return f"{y2:04d}-03"
    return None


def quarter_label(code):
    """YYYY-MM -> 'Month YYYY'"""
    if not code:
        return None
    yr, mon = code.split("-")
    names = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
             7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}
    return f"{names[int(mon)]} {yr}"


# ─── Category classification ───
CATEGORY_RULES = [
    # (list of keyword-groups (all must match), category, has_amount_unit)
    # "NOT" matches exclude
    # First match wins.
    {"kw": ["BANK BRANCHES PER"], "cat": "branch_network"},
    {"kw": ["BC OUTLETS PER"], "cat": "branch_network"},
    {"kw": ["ATMS PER"], "cat": "branch_network"},
    {"kw": ["NO. OF BRANCHES", "DEPOSIT", "ADVANCE"], "cat": "credit_deposit_ratio"},
    {"kw": ["NO. OF BRANCH", "CD RATIO"], "cat": "credit_deposit_ratio"},
    {"kw": ["CREDIT DEPOSIT RATIO"], "cat": "credit_deposit_ratio"},
    {"kw": ["C.D. RATIO"], "cat": "credit_deposit_ratio"},
    {"kw": ["C D RATIO"], "cat": "credit_deposit_ratio"},
    {"kw": ["CDR"], "cat": "credit_deposit_ratio"},
    {"kw": ["TOTAL DEPOSIT", "TOTAL ADVANCE"], "cat": "credit_deposit_ratio"},
    {"kw": ["ATM CUM DEBIT"], "cat": "digital_transactions"},
    {"kw": ["INTERNET BANKING"], "cat": "digital_transactions"},
    {"kw": ["MOBILE BANKING"], "cat": "digital_transactions"},
    {"kw": ["AEPS"], "cat": "digital_transactions"},
    {"kw": ["DIGITAL"], "cat": "digital_transactions"},
    {"kw": ["BHIM"], "cat": "digital_transactions"},
    {"kw": ["UPI"], "cat": "digital_transactions"},
    {"kw": ["BSBDA"], "cat": "pmjdy"},
    {"kw": ["PMJDY"], "cat": "pmjdy"},
    {"kw": ["PM JDY"], "cat": "pmjdy"},
    {"kw": ["JAN DHAN"], "cat": "pmjdy"},
    {"kw": ["KCC"], "cat": "kcc"},
    {"kw": ["KISAN CREDIT"], "cat": "kcc"},
    {"kw": ["SHG"], "cat": "shg"},
    {"kw": ["SELF HELP GROUP"], "cat": "shg"},
    {"kw": ["JLG"], "cat": "shg"},
    {"kw": ["PMJJBY"], "cat": "social_security"},
    {"kw": ["PMSBY"], "cat": "social_security"},
    {"kw": ["APY"], "cat": "social_security"},
    {"kw": ["ATAL PENSION"], "cat": "social_security"},
    {"kw": ["PMAY"], "cat": "housing_pmay"},
    {"kw": ["HOUSING"], "cat": "housing_pmay"},
    {"kw": ["EDUCATION LOAN"], "cat": "education_loan"},
    {"kw": ["MUDRA"], "cat": "mudra"},
    {"kw": ["PMMY"], "cat": "mudra"},
    {"kw": ["PMEGP"], "cat": "pmegp"},
    {"kw": ["NPS"], "cat": "nps"},
    {"kw": ["NATIONAL PENSION"], "cat": "nps"},
    {"kw": ["WOMEN"], "cat": "women_finance"},
    {"kw": ["SC/ST"], "cat": "sc_st_finance"},
    {"kw": ["WEAKER SECTION"], "cat": "sc_st_finance"},
    {"kw": ["AADHAAR SEED"], "cat": "aadhaar_authentication"},
    {"kw": ["AADHAAR AUTH"], "cat": "aadhaar_authentication"},
    {"kw": ["AADHAAR"], "cat": "aadhaar_authentication"},
    {"kw": ["FINANCIAL LITERACY"], "cat": "financial_literacy"},
    {"kw": ["FLC"], "cat": "financial_literacy"},
    {"kw": ["RSETI"], "cat": "rseti"},
    {"kw": ["NRLM"], "cat": "shg"},
    {"kw": ["SRLM"], "cat": "shg"},
    {"kw": ["SEP"], "cat": "nulm"},
    {"kw": ["NULM"], "cat": "nulm"},
    {"kw": ["MSY"], "cat": "msy"},
    {"kw": ["STAND UP INDIA"], "cat": "stand_up_india"},
    {"kw": ["RECOVERY"], "cat": "recovery"},
    {"kw": ["ACP"], "cat": "acp"},
    {"kw": ["ANNUAL CREDIT PLAN"], "cat": "acp"},
]


def classify_category(*title_texts):
    """Return category name based on keyword matching in concatenated title text."""
    combined = " ".join([t for t in title_texts if t])
    if not combined:
        return "misc"
    # Normalize whitespace (including newlines) to single space for robust keyword match
    normalized = re.sub(r"\s+", " ", combined).upper()
    for rule in CATEGORY_RULES:
        if all(kw in normalized for kw in rule["kw"]):
            return rule["cat"]
    # Fallback: snake_case from first English words
    words = re.findall(r"[A-Za-z]+", combined.lower())
    # Strip common noise
    noise = {"district", "sr", "no", "amt", "rs", "source", "annex", "i", "ii", "iii", "iv"}
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
    # Strip leading serial number with dot/space
    name = re.sub(r"^[A-Za-z]?\d+[\.\s]*", "", name).strip()
    # strip trailing asterisks / markers
    name = name.rstrip("*")
    name = re.sub(r"\s+", " ", name).strip()
    # Check skips
    lower = name.lower().strip(".,:;*(){}[] ")
    if lower in SKIP_ROWS or lower == "" or lower == "district" or lower == "dsitrict":
        return None
    # direct lookup
    upper = name.upper()
    if upper in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[upper]
    # Strip parentheses contents and retry
    stripped = re.sub(r"\s*\([^)]*\)\s*", "", name).strip()
    upper2 = stripped.upper()
    if upper2 in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[upper2]
    # Try compressed whitespace
    comp = re.sub(r"\s+", " ", upper2)
    if comp in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[comp]
    # Substring match (e.g., "U.S. Nagar (A)")
    for alias, canon in DISTRICT_ALIASES.items():
        if alias in upper and len(alias) >= 5:
            return canon
    return None


# ─── Number parsing ───
def parse_number(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s or s in {"-", "--", "NA", "N/A", "NIL", "…", ".", "*"}:
        return None
    s = s.replace(",", "").replace("%", "").replace("₹", "").replace("`", "")
    s = re.sub(r"\*+$", "", s).strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    # handle values that are like "123 foo" where foo is garbage
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
    # Remove newlines
    s = s.replace("\n", " ").replace("\r", " ")
    # Remove unit parentheticals
    s = re.sub(r"\((?:amt\.?\s*in\s*cr\.?|amt\.?\s*in\s*rs\.?|rs\.?\s*in\s*cr\.?|amt\.?\s*in\s*lacs?|no\.?\s*in\s*lacs?|in\s*lacs?|in\s*crores?|amt\.?|no\.?|rs\.?|a|asp\.?)\)",
               "", s, flags=re.I)
    # Normalise common tokens
    s = s.replace("%", " pct ").replace("/", " ").replace("-", " ").replace("&", " and ")
    s = re.sub(r"\bno\.?\b", "no", s, flags=re.I)
    s = re.sub(r"\bamt\.?\b", "amt", s, flags=re.I)
    s = re.sub(r"\bo\/s\b", "os", s, flags=re.I)
    s = re.sub(r"\ba\/c\b", "ac", s, flags=re.I)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def make_field_name(category_hint, metric, subtype=None):
    """Combine a metric label (from group header) and optional subtype ('no', 'amt') into a field name."""
    metric_snake = snake_case(metric or "")
    out = metric_snake
    if subtype:
        sub_snake = snake_case(subtype)
        if sub_snake and sub_snake not in out:
            out = f"{out}_{sub_snake}" if out else sub_snake
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


# ─── Standardization for FI timeseries keys ───
FIELD_STANDARDIZE_MAP = {
    # branch network
    "no_of_bank_branches_per_one_lakh_population": "no_of_bank_branches_per_lakh",
    "no_of_bank_branches_per_lakh_population": "no_of_bank_branches_per_lakh",
    "no_of_bc_outlets_per_one_lakh_population": "no_of_bc_outlets_per_lakh",
    "no_of_bc_outlets_per_lakh_population": "no_of_bc_outlets_per_lakh",
    "no_of_atms_per_one_lakh_population": "no_of_atms_per_lakh",
    "no_of_atms_per_lakh_population": "no_of_atms_per_lakh",
    # CD ratio
    "total_deposit": "total_deposit",
    "total_deposite": "total_deposit",
    "deposit": "total_deposit",
    "total_advances": "total_advances",
    "advances": "total_advances",
    "total_advance": "total_advances",
    "total_advances_investment": "total_advances",
    "cd_ratio": "overall_cd_ratio",
    "c_d_ratio": "overall_cd_ratio",
    "c_d_ratio_pct": "overall_cd_ratio",
    "cd_ratio_pct": "overall_cd_ratio",
    "no_of_branches": "total_branch",
    "no_of_branch": "total_branch",
    # PMJDY
    "no_of_pmjdy_accounts": "total_pmjdy_no",
    "no_of_pmjdy_ac": "total_pmjdy_no",
    "no_of_pm_jdy_ac_per_one_lakh_population": "no_of_pmjdy_per_lakh",
    "no_of_pm_jdy_ac_per_lakh_population": "no_of_pmjdy_per_lakh",
    "no_of_pmjdy_per_one_lakh_population": "no_of_pmjdy_per_lakh",
    # KCC
    "total_no_of_kcc_issued_no": "total_no_of_kcc",
    "total_no_of_kcc_issued": "total_no_of_kcc",
    "total_no_of_kcc_issued_amt_os": "total_kcc_amt",
    # SHG
    "total_no_of_shg": "total_no_of_shg",
    "out_of_1_no_of_shgs_credit_linkage": "shg_credit_linked_no",
}


def standardize_field(snake):
    if snake in FIELD_STANDARDIZE_MAP:
        return FIELD_STANDARDIZE_MAP[snake]
    return snake


# ─── Core: parsing pdfplumber tables ───

def district_count_in_rows(rows, max_first_cols=3):
    """Count rows whose first few columns contain a canonical district name."""
    cnt = 0
    for row in rows:
        if not row:
            continue
        for cell in row[:max_first_cols]:
            if cell and normalize_district(str(cell)):
                cnt += 1
                break
    return cnt


def cell_text(c):
    if c is None:
        return ""
    return re.sub(r"\s+", " ", str(c)).strip()


def find_district_col(rows, max_check=30):
    """Return the column index most likely to contain district names."""
    max_cols = max(len(r) for r in rows if r) if rows else 0
    best = 0
    best_score = -1
    for col in range(min(max_cols, 5)):
        score = 0
        for row in rows[:max_check]:
            if not row or len(row) <= col:
                continue
            if normalize_district(str(row[col])):
                score += 1
        if score > best_score:
            best_score = score
            best = col
    return best if best_score >= 3 else 0


def get_header_rows(table, district_col):
    """Return the rows above the first data (district) row, and the index of first data row."""
    header_rows = []
    data_start = 0
    for i, row in enumerate(table):
        if not row:
            header_rows.append(row)
            continue
        cell = row[district_col] if len(row) > district_col else None
        if cell and normalize_district(str(cell)):
            data_start = i
            break
        header_rows.append(row)
    return header_rows, data_start


def forward_fill_row(row):
    """Forward-fill None cells with previous non-empty cell."""
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
    """Detect rows that are just a section title (single non-empty cell like '(a) Savings Account Indicators :')."""
    non_empty = [c for c in row if c and str(c).strip()]
    if len(non_empty) != 1:
        return False
    txt = str(non_empty[0]).strip()
    if len(txt) < 5:
        return False
    return bool(SECTION_TITLE_RE.search(txt))


def build_column_map(header_rows, total_cols, district_col):
    """
    Return list of dicts per column index (except district_col):
      { 'metric': str, 'quarter': 'YYYY-MM' or None, 'subtype': str or None }

    The header typically has 1-3 rows:
      - a group header spanning multiple data cols (e.g. "No. of Bank Branches per Lakh")
      - a quarter label per sub-col (e.g. "March 2021", "Dec 2023")
      - sometimes a sub-sub-label like "No." or "Amt. O/S"
    Strategy:
      - For each row, forward-fill blanks.
      - Examine each column: try to parse its text as a quarter; whichever row parses
        cleanly as a quarter is the 'quarter' row. Other rows are concatenated as 'metric'/'subtype'.
    """
    # Filter out section title rows (e.g. "(a) Savings Account Indicators :")
    filtered_headers = [r for r in header_rows if not _is_section_title_row(r or [])]

    # Forward-fill each header row
    ffilled = []
    for r in filtered_headers:
        padded = list(r or []) + [None] * max(0, total_cols - len(r or []))
        ffilled.append(forward_fill_row(padded[:total_cols]))

    # For each row decide if it's a quarter row
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

    # For each col, compose
    col_info = []
    for col in range(total_cols):
        if col == district_col:
            col_info.append(None)
            continue
        metric_parts = []
        subtype = None
        quarter = None
        for ri, row in enumerate(ffilled):
            c = row[col] if col < len(row) else ""
            c = cell_text(c)
            if not c:
                continue
            if row_is_quarter[ri]:
                q = parse_quarter_from_text(c)
                if q and not quarter:
                    quarter = q
                elif not quarter and not q:
                    metric_parts.append(c)
                elif not q:
                    metric_parts.append(c)
            else:
                # non-quarter row: possibly metric or subtype
                # "No." / "Amt. O/S" / "Male" / "Female" / "(I)" — short tokens are subtype
                c_clean = re.sub(r"\s+", "", c).lower()
                if c_clean in {"no.", "no", "amt.", "amt.o/s", "amto/s", "amt", "amtos", "(i)", "(ii)", "(iii)", "(iv)", "(v)", "male", "female"}:
                    if subtype:
                        subtype = f"{subtype} {c}"
                    else:
                        subtype = c
                else:
                    metric_parts.append(c)
        # Deduplicate contiguous repeats in metric_parts
        ded_parts = []
        for p in metric_parts:
            if not ded_parts or ded_parts[-1] != p:
                ded_parts.append(p)
        metric = " ".join(ded_parts).strip()
        col_info.append({"metric": metric, "quarter": quarter, "subtype": subtype})
    return col_info


def detect_amount_unit(header_rows, title_text):
    """Return True if the table amounts are in Crores (need to multiply by 100 to get Lakhs)."""
    text = (title_text or "") + " "
    for r in header_rows:
        for c in (r or []):
            if c:
                text += str(c) + " "
    low = text.lower()
    if "amt. in cr" in low or "amt in cr" in low or "rs. in cr" in low or "in crore" in low or "in cr." in low or "(` in cr" in low or "(`in cr" in low:
        return True
    return False


def page_title_text(page):
    """Extract first few non-empty lines above first district row to use as category hint."""
    text = page.extract_text() or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    out = []
    for ln in lines[:10]:
        lnl = ln.lower()
        if "dehradun" in lnl or "uttarkashi" in lnl or "almora" in lnl:
            break
        out.append(ln)
    return " | ".join(out)


def page_text_segments(page):
    """Split page text into segments separated by district lines.

    Returns a list of (prefix_lines, district_block_idx) so a caller can look up
    'the text just above district block N on this page'. Used as a per-table
    metric-label fallback when pdfplumber tables have empty metric headers.
    """
    text = page.extract_text() or ""
    lines = text.split("\n")
    segs = []
    current_prefix = []
    in_district_block = False
    for ln in lines:
        ll = ln.lower()
        is_dist = any(d in ll for d in ("dehradun", "uttarkashi", "almora", "nainital", "haridwar", "hardwar"))
        if is_dist:
            if not in_district_block:
                segs.append(list(current_prefix))
                current_prefix = []
                in_district_block = True
        else:
            if in_district_block:
                in_district_block = False
            current_prefix.append(ln)
    return segs  # segs[i] = text lines before the i-th district block


def _title_to_metric_hint(lines):
    """Given prefix text lines, extract a short metric hint."""
    if not lines:
        return ""
    text_joined = " ".join(l.strip() for l in lines if l.strip())
    # Remove Devanagari / non-ASCII
    ascii_only = re.sub(r"[^\x20-\x7E]", " ", text_joined)
    ascii_only = re.sub(r"\s+", " ", ascii_only).strip()
    # Keep last sentence (often the table header)
    parts = re.split(r"[:\|]", ascii_only)
    if parts:
        # Pick the part that contains "No. of" or "Total" or " per "
        for p in reversed(parts):
            p = p.strip()
            if re.search(r"(?i)no\.\s*of|total|per\s+(one\s+)?lakh|c\.?d\.?\s*ratio|deposit|advance", p):
                return p[:120]
        return parts[-1].strip()[:120]
    return ascii_only[:120]


# ─── Text-based table parsing (for PDFs where pdfplumber can't find tables) ───

TEXT_TABLE_DISTRICT_RE = re.compile(
    r"^\s*(?:\d+\s+)?(Dehradun|Uttarkashi|Hardwar|Haridwar|Tehri|New Tehri|Pauri|Chamoli|Rudra\s*Prayag|Rudraprayag|Almora|Bageshwar|Pithoragarh|Champawat|Nainital|U\s*S\s*Nagar|U\.S\.\s*Nagar|USNagar)",
    re.I,
)


def _parse_text_table_header(header_lines, n_cols):
    """Try to assign each of n_cols columns a (metric, quarter) label using header text.

    Simple heuristic: the last non-empty header line is the primary header;
    any preceding lines that have matching word count get concatenated as subheaders
    or quarter rows. For most old UK PDFs this is a single-row header.

    Returns list of (metric, quarter_or_None) of length n_cols.
    """
    # Filter header lines, ignore narrative/Devanagari-dominant lines
    candidates = []
    for ln in header_lines:
        ls = ln.strip()
        if not ls:
            continue
        # Skip Devanagari-heavy lines
        ascii_chars = sum(1 for c in ls if ord(c) < 128)
        if ascii_chars < len(ls) * 0.5:
            continue
        # Skip lines that look like narrative sentences (end with period-space, contain many lowercase words)
        if len(ls) > 100 and ls.count(" ") > 15 and not re.search(r"\b(No\.|Amt\.|Sr\.|District|Total|C\.?D\.?|Deposit|Advance|KCC|PMJDY|March|June|Sept|Dec|FY|As on)\b", ls, re.I):
            continue
        candidates.append(ls)

    # Pick last candidate that contains 'District' or 'Sr.' as the primary column-label row
    label_line = None
    for ln in reversed(candidates):
        if re.search(r"\b(district|sr\.?)\b", ln, re.I):
            label_line = ln
            break
    if not label_line and candidates:
        label_line = candidates[-1]
    if not label_line:
        return [(None, None)] * n_cols

    # Extract quarter from nearby text (all candidates joined)
    joined = " ".join(candidates)
    text_q = parse_quarter_from_text(joined)

    # Now break the label_line into column labels. The hard part: labels can be multi-word.
    # Rule of thumb: split on 2-3+ space runs first; if that yields fewer tokens than n_cols,
    # fall back to treating each space-separated token as a column.
    parts_2ws = re.split(r"\s{2,}", label_line)
    parts_2ws = [p.strip() for p in parts_2ws if p.strip()]
    # Strip "Sr." and "District" columns at start
    if parts_2ws and parts_2ws[0].lower() in ("sr.", "sr", "s.no.", "s. no.", "no.", "s.n.", "s.no"):
        parts_2ws = parts_2ws[1:]
    if parts_2ws and parts_2ws[0].lower() in ("district", "dsitrict"):
        parts_2ws = parts_2ws[1:]

    if len(parts_2ws) >= n_cols:
        labels = parts_2ws[:n_cols]
    else:
        # Fall back to splitting on single spaces, grouping multi-word metric names heuristically
        # If parts_2ws gives us fewer labels than n_cols, try a different split
        parts_1ws = label_line.split()
        # Strip leading "Sr. District" tokens
        start = 0
        while start < len(parts_1ws) and parts_1ws[start].lower() in ("sr.", "sr", "s.no.", "no.", "district", "dsitrict"):
            start += 1
        parts_1ws = parts_1ws[start:]
        if len(parts_1ws) == n_cols:
            labels = parts_1ws
        else:
            # Distribute: take as many distinct tokens as columns, then label the rest as col_N
            labels = (parts_2ws + [f"col_{i+1}" for i in range(n_cols)])[:n_cols]

    out = []
    for lbl in labels:
        out.append((lbl, text_q))
    # Pad to n_cols if short
    while len(out) < n_cols:
        out.append((None, text_q))
    return out


def _tokenize_data_line(line):
    """Tokenize a district line: first take serial number (optional), then district name
    (possibly multi-word), then numeric values.

    Returns: (serial_or_None, district_string, [numeric_tokens_as_strings])
    or None if tokenization fails.
    """
    line = line.strip()
    if not line:
        return None
    tokens = line.split()
    idx = 0
    # Optional serial number
    serial = None
    if re.match(r"^\d{1,3}$", tokens[idx]):
        serial = tokens[idx]
        idx += 1
    # Collect district name tokens until we hit a token that looks like a number
    dist_tokens = []
    while idx < len(tokens):
        tok = tokens[idx]
        if re.match(r"^-?\d[\d,\.]*$", tok) or tok in {"--", "---", "NA", "N/A"} or tok.startswith("("):
            break
        # Some district names contain "(A)", "(Asp.)" etc
        if tok.startswith("(") and dist_tokens:
            dist_tokens.append(tok)
            idx += 1
            continue
        dist_tokens.append(tok)
        idx += 1
    if not dist_tokens:
        return None
    district = " ".join(dist_tokens)
    values = tokens[idx:]
    return serial, district, values


def extract_text_tables(page):
    """
    For pages where pdfplumber doesn't see tables, parse text by lines.
    Returns list of (title_text, header_text, header_rows, data_rows) where:
      - header_rows = list of lines (as strings) above the district block
      - data_rows = list of (district_name, [value_tokens]) tuples
    """
    text = page.extract_text() or ""
    lines = text.split("\n")
    blocks = []
    current = []
    current_header = []
    for line in lines:
        if TEXT_TABLE_DISTRICT_RE.match(line):
            current.append(line)
        else:
            if current:
                blocks.append((list(current_header), current))
                current = []
                current_header = []
            current_header.append(line)
            if len(current_header) > 8:
                current_header = current_header[-8:]
    if current:
        blocks.append((list(current_header), current))

    tables = []
    for header_lines, dist_lines in blocks:
        # Tokenize district lines
        data_rows = []
        seen_districts = set()
        for ln in dist_lines:
            toks = _tokenize_data_line(ln)
            if not toks:
                continue
            serial, dist, values = toks
            d_norm = normalize_district(dist)
            if not d_norm:
                continue
            if d_norm in seen_districts:
                continue  # only first occurrence
            seen_districts.add(d_norm)
            if not values:
                continue
            data_rows.append((d_norm, values))
        if len(data_rows) < 5:
            continue
        tables.append(("\n".join(header_lines), header_lines, data_rows))
    return tables


# ─── Per-PDF extraction ───

def extract_pdf(pdf_path):
    """
    Yield (category, quarter_code, district, field, value, is_crore_amount_hint)
    for each cell successfully parsed.
    """
    pdf_name = pdf_path.name
    primary_q = MEETING_PRIMARY_QUARTER.get(pdf_name)

    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages):
            title = page_title_text(page)
            # Per-page prefix segments: prefix[i] is lines before the i-th district block
            prefix_segs = page_text_segments(page)
            # 1) Attempt pdfplumber tables
            try:
                tables = page.extract_tables()
            except Exception:
                tables = []

            # Only count tables that actually have districts (for indexing into prefix_segs)
            district_table_idx = 0
            used_pdfplumber = False
            for ti, table in enumerate(tables):
                if not table or len(table) < 3:
                    continue
                max_cols = max(len(r) for r in table if r)
                if max_cols < 3:
                    continue
                # Find district column
                district_col = find_district_col(table)
                # Verify enough districts
                d_count = 0
                for row in table:
                    if not row:
                        continue
                    if len(row) > district_col and normalize_district(str(row[district_col])):
                        d_count += 1
                if d_count < 5:
                    continue
                used_pdfplumber = True

                # Header rows
                header_rows, data_start = get_header_rows(table, district_col)
                col_info = build_column_map(header_rows, max_cols, district_col)
                is_crore = detect_amount_unit(header_rows, title)
                # Build category hint from title + header cells
                header_text_blob = " ".join(
                    str(c) for r in header_rows for c in (r or []) if c
                )
                # Also include text prefix for this table's district block
                prefix_lines = prefix_segs[district_table_idx] if district_table_idx < len(prefix_segs) else []
                prefix_blob = " ".join(l for l in prefix_lines if l.strip())
                category = classify_category(title, header_text_blob, prefix_blob)
                # Fallback metric hint from prefix for columns with empty metric
                metric_fallback = _title_to_metric_hint(prefix_lines)
                for ci, ci_info in enumerate(col_info):
                    if ci_info and not ci_info.get("metric") and ci_info.get("quarter"):
                        ci_info["metric"] = metric_fallback
                district_table_idx += 1

                # Data rows
                for row in table[data_start:]:
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
                        val = parse_number(row[ci])
                        if val is None:
                            continue
                        metric = ci_info["metric"] or ""
                        subtype = ci_info["subtype"]
                        quarter = ci_info["quarter"] or primary_q
                        if quarter not in VALID_QUARTERS:
                            continue
                        # Decide if value is amount (for crore conversion)
                        field = make_field_name(category, metric, subtype)
                        if not field:
                            continue
                        # amount conversion: if Crore unit AND field is amount-like
                        is_amount = False
                        for key in ("amt", "os", "deposit", "advance", "total_advances", "total_deposit", "loan_os"):
                            if key in field:
                                is_amount = True
                                break
                        value_out = val
                        if is_crore and is_amount:
                            value_out = val * 100.0
                        yield (category, quarter, dist, field, value_out, pdf_name, pno + 1)

            # 2) For pages where pdfplumber found nothing (or found non-district tables), try text approach
            if not used_pdfplumber:
                text_tables = extract_text_tables(page)
                for title_text, header_lines, data_rows in text_tables:
                    # data_rows = list of (district_name, [value_str, ...])
                    full_title = (title + " | " + title_text).strip(" |")
                    category = classify_category(full_title)
                    is_crore = detect_amount_unit([], full_title)
                    # Parse column headers from header_lines
                    n_cols = max(len(v) for _, v in data_rows) if data_rows else 0
                    col_headers = _parse_text_table_header(header_lines, n_cols)
                    # col_headers is list of (metric, quarter_or_None) of length n_cols
                    for dist, values in data_rows:
                        for ci, val_str in enumerate(values):
                            val = parse_number(val_str)
                            if val is None:
                                continue
                            metric, col_quarter = (None, None)
                            if ci < len(col_headers):
                                metric, col_quarter = col_headers[ci]
                            quarter = col_quarter or primary_q
                            if quarter not in VALID_QUARTERS:
                                continue
                            if not metric:
                                metric = f"col_{ci+1}"
                            field = make_field_name(category, metric, None)
                            if not field:
                                continue
                            is_amount = any(k in field for k in ("amt", "os", "deposit", "advance", "loan_os"))
                            value_out = val
                            if is_crore and is_amount:
                                value_out = val * 100.0
                            yield (category, quarter, dist, field, value_out, pdf_name, pno + 1)


# ─── Main ───

def main():
    all_records = []
    stats = defaultdict(int)
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

    # Dedup: prefer most recent PDF (highest PDF_PRIORITY)
    # Key: (quarter, district, category, field) -> (priority, value, pdf, page)
    best = {}
    for rec in all_records:
        category, quarter, district, field, value, pdf_name, pno = rec
        prio = PDF_PRIORITY.get(pdf_name, 0)
        key = (quarter, district, category, field)
        prev = best.get(key)
        if prev is None or prio > prev[0]:
            best[key] = (prio, value, pdf_name, pno)

    print(f"[INFO] Deduplicated: {len(best)} unique (quarter, district, category, field) tuples")

    # Build output structures
    # complete.json structure
    quarters_out = {}  # qcode -> {period, tables: { category: {fields: [...], districts: { dist: { field: str(value) } } } } }
    fi_timeseries = {}  # qcode -> { district -> { key: value } }

    for (qcode, district, category, field), (_prio, value, pdf_name, pno) in best.items():
        q = quarters_out.setdefault(qcode, {"period": quarter_label(qcode), "tables": {}})
        tbl = q["tables"].setdefault(category, {"fields": [], "districts": {}})
        if field not in tbl["fields"]:
            tbl["fields"].append(field)
        row = tbl["districts"].setdefault(district, {})
        row[field] = format_value(value)

        # FI timeseries
        standard_field = standardize_field(field)
        fkey = f"{category}__{standard_field}"
        fi_timeseries.setdefault(qcode, {}).setdefault(district, {"district": district, "period": quarter_label(qcode)})[fkey] = value

    # Sort quarters ascending for output
    qcodes_sorted = sorted(quarters_out.keys())

    # ─── uttarakhand_complete.json ───
    complete = {
        "state": "Uttarakhand",
        "quarters": OrderedDict()
    }
    for q in qcodes_sorted:
        complete["quarters"][q] = quarters_out[q]

    (DIR / "uttarakhand_complete.json").write_text(
        json.dumps(complete, indent=2, ensure_ascii=False)
    )
    print(f"[OK] wrote uttarakhand_complete.json ({len(qcodes_sorted)} quarters)")

    # ─── uttarakhand_fi_timeseries.json ───
    periods_list = []
    for q in qcodes_sorted:
        districts = sorted(fi_timeseries.get(q, {}).values(), key=lambda d: UK_DISTRICTS.index(d["district"]) if d["district"] in UK_DISTRICTS else 999)
        periods_list.append({
            "period": quarter_label(q),
            "districts": districts,
        })
    (DIR / "uttarakhand_fi_timeseries.json").write_text(
        json.dumps({"periods": periods_list}, indent=2, ensure_ascii=False, default=str)
    )
    print(f"[OK] wrote uttarakhand_fi_timeseries.json ({len(periods_list)} periods)")

    # ─── uttarakhand_fi_timeseries.csv ───
    all_keys = set()
    for q in fi_timeseries.values():
        for d in q.values():
            all_keys.update(k for k in d.keys() if k not in ("district", "period"))
    col_order = ["district", "period"] + sorted(all_keys)
    with open(DIR / "uttarakhand_fi_timeseries.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(col_order)
        for q in qcodes_sorted:
            for d in fi_timeseries.get(q, {}).values():
                w.writerow([d.get(k, "") for k in col_order])
    print(f"[OK] wrote uttarakhand_fi_timeseries.csv ({sum(len(v) for v in fi_timeseries.values())} rows, {len(col_order)} cols)")

    # ─── quarterly CSVs ───
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
                for dist in UK_DISTRICTS:
                    if dist in tbl["districts"]:
                        row = [dist] + [tbl["districts"][dist].get(fld, "") for fld in tbl["fields"]]
                        w.writerow(row)

    # ─── Summary ───
    print("\n=== SUMMARY ===")
    print(f"Quarters: {len(qcodes_sorted)}")
    for q in qcodes_sorted:
        districts = set()
        for tbl in quarters_out[q]["tables"].values():
            districts.update(tbl["districts"].keys())
        cats = list(quarters_out[q]["tables"].keys())
        print(f"  {q} ({quarter_label(q)}): {len(districts)}/13 districts, {len(cats)} cats")

    # Top 10 (category, field) populated combos
    combo_counts = defaultdict(int)
    for (qcode, district, category, field) in best.keys():
        combo_counts[(category, field)] += 1
    top10 = sorted(combo_counts.items(), key=lambda kv: -kv[1])[:10]
    print("\nTop 10 (category, field) by quarter-district count:")
    for (cat, fld), cnt in top10:
        print(f"  {cat}.{fld}: {cnt}")

    # FI fields per quarter
    print("\nFI indicator coverage per quarter:")
    fi_cats = ["credit_deposit_ratio", "pmjdy", "branch_network", "kcc", "shg", "digital_transactions", "aadhaar_authentication"]
    header = "Quarter     " + " ".join(f"{c[:10]:>10}" for c in fi_cats)
    print(header)
    for q in qcodes_sorted:
        row_counts = {}
        for cat in fi_cats:
            tbl = quarters_out[q]["tables"].get(cat, {})
            row_counts[cat] = len(tbl.get("districts", {}))
        print(f"{q}  " + " ".join(f"{row_counts[c]:>10d}" for c in fi_cats))


def format_value(v):
    """Format numeric values for JSON output: int-like → '123', float → '123.45'."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


if __name__ == "__main__":
    main()
