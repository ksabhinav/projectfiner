#!/usr/bin/env python3
"""
Ingest public/indicators/ files into RAG text format.

Each indicator+quarter+state combination becomes one text chunk,
giving the RAG access to all 20 indicators across 800+ districts.

Output: data/rag/text/indicators/{state}/tables/{indicator}_{quarter}.txt
Run this, then rebuild the index with: python3 scripts/rag/build_index.py
"""

import os
import json
import glob
import re
from collections import defaultdict

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
INDICATORS_DIR = os.path.join(BASE_DIR, "public", "indicators")
TEXT_DIR = os.path.join(BASE_DIR, "data", "rag", "text")

MONTH_MAP = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}

INDICATOR_LABELS = {
    "credit_deposit_ratio":       "Credit-Deposit Ratio",
    "pmjdy":                      "PM Jan Dhan Yojana (PMJDY)",
    "branch_network":             "Branch Network",
    "kcc":                        "Kisan Credit Card (KCC)",
    "shg":                        "Self Help Groups (SHG)",
    "digital_transactions":       "Digital Transactions",
    "aadhaar_authentication":     "Aadhaar Authentication & Seeding",
    "social_security":            "Social Security Schemes (PMSBY/PMJJBY/APY)",
    "pmegp":                      "PM Employment Generation Programme (PMEGP)",
    "housing_pmay":               "Housing / PMAY",
    "sui":                        "Stand Up India",
    "sc_st_finance":              "SC/ST Lending",
    "women_finance":              "Women's Credit",
    "education_loan":             "Education Loans",
    "pmmy_mudra_disbursement":    "MUDRA / PMMY Disbursement",
    "rbi_banking_outlets":        "Banking Infrastructure (RBI Outlets)",
    "nrlm_shg":                   "Self-Help Groups (NRLM)",
    "rbi_bsr_credit":             "Bank Credit (RBI BSR-1)",
    "nfhs_health_insurance":      "Health Insurance Coverage (NFHS)",
    "capital_markets_access":     "Capital Markets Access Points",
}

FIELD_LABELS = {
    # Credit deposit ratio
    "overall_cd_ratio": "CD Ratio (%)",
    "total_advance": "Total Advance (₹ Lakhs)",
    # Digital transactions
    "coverage_sb_pct": "Digital Coverage of SB Accounts (%)",
    "digital_coverage_sb_a_c": "Digitally Covered SB Accounts (No.)",
    # RBI banking outlets
    "rbi_outlets__total": "Total Banking Outlets",
    "rbi_outlets__branch": "Bank Branches",
    "rbi_outlets__bc": "Business Correspondents (BCs)",
    "rbi_outlets__csp": "Customer Service Points (CSPs)",
    "rbi_outlets__rural": "Rural Outlets",
    "rbi_outlets__semi_urban": "Semi-Urban Outlets",
    "rbi_outlets__urban": "Urban Outlets",
    "rbi_outlets__metro": "Metro Outlets",
    # Capital markets
    "cap_total": "Total Capital Market Access Points",
    "cap_cdsl": "CDSL Service Centres",
    "cap_nsdl": "NSDL Service Centres",
    "cap_mfdi": "MFD Individual",
    "cap_mfdc": "MFD Corporate",
    # NFHS
    "pct": "Health Insurance Coverage (%)",
    # Generic patterns
}


def quarter_to_label(q):
    """Convert '2025-12' to 'December 2025', 'static' to 'Static Snapshot'."""
    if q == "static":
        return "Static Snapshot"
    if q in ("2021-03",):
        labels = {"2021-03": "NFHS-5 (2019-21)", "2016-03": "NFHS-4 (2015-16)"}
        return labels.get(q, q)
    if re.match(r"\d{4}-\d{2}", q):
        year, month = q.split("-")
        return f"{MONTH_MAP.get(month, month)} {year}"
    return q


def fmt_val(v):
    """Format a numeric value for display."""
    if v is None or v == "":
        return "N/A"
    try:
        n = float(str(v).replace(",", ""))
        if abs(n) >= 1e7:
            return f"{n/1e7:.2f} Cr"
        if abs(n) >= 1e5:
            return f"{n/1e5:.2f} L"
        if abs(n) >= 1000:
            return f"{n:,.0f}"
        if n != int(n):
            return f"{n:.2f}"
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(v)


def field_label(field):
    """Get human-readable label for a field name."""
    if field in FIELD_LABELS:
        return FIELD_LABELS[field]
    # Generic: snake_case → Title Case
    name = field.replace("__", " → ").replace("_", " ")
    abbrevs = {"pct": "%", "amt": "Amount", "no": "Number", "cd": "CD",
               "kcc": "KCC", "shg": "SHG", "pmjdy": "PMJDY", "npa": "NPA",
               "upi": "UPI", "bc": "BC", "atm": "ATM", "casa": "CASA"}
    words = name.split()
    return " ".join(abbrevs.get(w.lower(), w.title()) for w in words)


def state_slug(raw):
    """Normalize state name to a filesystem-safe slug."""
    return re.sub(r"[^\w]", "_", raw.strip().lower()).strip("_")


def title_case_state(raw):
    """Convert 'ANDHRA PRADESH' → 'Andhra Pradesh'."""
    specials = {
        "andaman & nicobar": "Andaman & Nicobar",
        "andaman and nicobar": "Andaman & Nicobar",
        "dadra & nagar haveli & daman & diu": "Dadra & Nagar Haveli & Daman & Diu",
        "jammu and kashmir": "Jammu & Kashmir",
        "jammu & kashmir": "Jammu & Kashmir",
    }
    lower = raw.strip().lower()
    if lower in specials:
        return specials[lower]
    return raw.strip().title()


def generate_indicator_chunk(indicator_key, quarter_key, state_name, districts):
    """
    Generate a text chunk for one (indicator, quarter, state) combination.
    districts = list of district dicts from the indicator file.
    """
    ind_label = INDICATOR_LABELS.get(indicator_key, indicator_key.replace("_", " ").title())
    q_label = quarter_to_label(quarter_key)
    data_fields = [k for k in districts[0].keys() if k not in ("district", "state")]

    lines = []
    lines.append(f"FINER Indicator: {ind_label} — {state_name}, {q_label}")
    lines.append(f"Indicator: {indicator_key}")
    lines.append(f"State: {state_name}")
    lines.append(f"Quarter: {q_label}")
    lines.append(f"Districts with data: {len(districts)}")
    lines.append(f"Metrics: {', '.join(field_label(f) for f in data_fields)}")
    lines.append("")

    # District rows
    lines.append("District-level data:")
    for row in sorted(districts, key=lambda x: x.get("district", "")):
        d = row.get("district", "Unknown")
        parts = []
        for f in data_fields:
            v = row.get(f)
            if v is not None and v != "":
                parts.append(f"{field_label(f)} = {fmt_val(v)}")
        if parts:
            lines.append(f"  {d}: {' | '.join(parts)}")

    # Summary stats for numeric fields
    lines.append("")
    lines.append("Summary statistics:")
    for f in data_fields:
        nums = []
        best_dist, worst_dist = None, None
        for row in districts:
            try:
                v = float(str(row.get(f, "")).replace(",", ""))
                nums.append((v, row.get("district", "")))
            except (ValueError, TypeError):
                pass
        if nums:
            vals = [n for n, _ in nums]
            best = max(nums, key=lambda x: x[0])
            worst = min(nums, key=lambda x: x[0])
            avg = sum(vals) / len(vals)
            lines.append(
                f"  {field_label(f)}: State avg = {fmt_val(avg)}, "
                f"Highest = {fmt_val(best[0])} ({best[1]}), "
                f"Lowest = {fmt_val(worst[0])} ({worst[1]}), "
                f"Districts = {len(nums)}"
            )

    return "\n".join(lines)


def process_indicator_file(fpath, indicator_key):
    """Process one indicator JSON file and write per-state text files."""
    with open(fpath, encoding="utf-8") as f:
        data = json.load(f)

    quarter_key = data.get("quarter", "unknown")
    districts_raw = data.get("districts", [])

    if not districts_raw:
        return 0

    # Group by state
    by_state = defaultdict(list)
    for row in districts_raw:
        raw_state = row.get("state", "Unknown")
        state = title_case_state(raw_state)
        by_state[state].append(row)

    count = 0
    for state_name, state_districts in by_state.items():
        slug = state_slug(state_name)
        out_dir = os.path.join(TEXT_DIR, slug, "tables")
        os.makedirs(out_dir, exist_ok=True)

        text = generate_indicator_chunk(indicator_key, quarter_key, state_name, state_districts)
        if not text or len(text) < 80:
            continue

        safe_q = re.sub(r"[^\w\-]", "_", quarter_key)
        fname = f"{indicator_key}_{safe_q}.txt"
        fpath_out = os.path.join(out_dir, fname)

        with open(fpath_out, "w", encoding="utf-8") as f:
            f.write(f"---\n")
            f.write(f"state: {state_name}\n")
            f.write(f"type: table\n")
            f.write(f"quarter: {quarter_to_label(quarter_key)}\n")
            f.write(f"filename: {indicator_key}_{slug}_{safe_q}\n")
            f.write(f"pages: 0\n")
            f.write(f"---\n\n")
            f.write(text)

        count += 1

    return count


def main():
    print("Ingesting FINER indicator files into RAG text format...")
    print(f"Source: {INDICATORS_DIR}")
    print(f"Output: {TEXT_DIR}")
    print()

    total_files = 0
    total_chunks = 0

    indicator_dirs = sorted(
        d for d in os.listdir(INDICATORS_DIR)
        if os.path.isdir(os.path.join(INDICATORS_DIR, d)) and d != "manifest.json"
    )

    for indicator_key in indicator_dirs:
        ind_dir = os.path.join(INDICATORS_DIR, indicator_key)
        json_files = sorted(glob.glob(os.path.join(ind_dir, "*.json")))
        if not json_files:
            continue

        ind_label = INDICATOR_LABELS.get(indicator_key, indicator_key)
        file_chunks = 0
        for jf in json_files:
            n = process_indicator_file(jf, indicator_key)
            file_chunks += n

        print(f"  {ind_label}: {len(json_files)} quarters → {file_chunks} state chunks")
        total_files += len(json_files)
        total_chunks += file_chunks

    print(f"\nTotal: {total_files} indicator files → {total_chunks} state-level text chunks")
    print(f"\nNow rebuild the index:")
    print(f"  python3 scripts/rag/build_index.py")


if __name__ == "__main__":
    main()
