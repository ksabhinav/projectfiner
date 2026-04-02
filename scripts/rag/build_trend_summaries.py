#!/usr/bin/env python3
"""
Build per-(indicator, state) trend summary chunks for RAG.

For each indicator+state combination, creates ONE text chunk containing
state-average values across ALL available quarters — so a single BM25 hit
answers "how did X change in Y state" without needing to retrieve 20+
individual quarter chunks.

Output: data/rag/text/{state}/tables/{indicator}_trend_summary.txt
Run this, then rebuild the index with: python3 scripts/rag/build_index.py
"""

import os
import json
import glob
import re
from collections import defaultdict

BASE_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
IND_DIR    = os.path.join(BASE_DIR, "public", "indicators")
TEXT_DIR   = os.path.join(BASE_DIR, "data", "rag", "text")

MONTH_MAP = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May",     "06": "June",     "07": "July",  "08": "August",
    "09": "September","10": "October", "11": "November","12": "December",
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
    "overall_cd_ratio":            "CD Ratio (%)",
    "total_advance":               "Total Advance (₹ Lakhs)",
    "total_deposit":               "Total Deposit (₹ Lakhs)",
    "coverage_sb_pct":             "Digital Coverage of SB Accounts (%)",
    "digital_coverage_sb_a_c":     "Digitally Covered SB Accounts",
    "rbi_outlets__total":          "Total Banking Outlets",
    "rbi_outlets__branch":         "Bank Branches",
    "rbi_outlets__bc":             "Business Correspondents",
    "rbi_outlets__csp":            "Customer Service Points",
    "cap_total":                   "Total Capital Market Access Points",
    "cap_cdsl":                    "CDSL Centres",
    "cap_nsdl":                    "NSDL Centres",
    "pct":                         "Health Insurance Coverage (%)",
}

# Indicators with no quarterly time series (skip trend summary)
STATIC_INDICATORS = {"rbi_banking_outlets", "capital_markets_access"}
# NFHS only has 2 snapshot years — still worth a summary
SNAPSHOT_INDICATORS = {"nfhs_health_insurance"}


def quarter_label(q):
    """'2025-09' → 'September 2025', 'static' → 'Static Snapshot'"""
    if q == "static":
        return "Static Snapshot"
    m = re.match(r"(\d{4})-(\d{2})", q)
    if m:
        return f"{MONTH_MAP.get(m.group(2), m.group(2))} {m.group(1)}"
    return q


def field_label(f):
    if f in FIELD_LABELS:
        return FIELD_LABELS[f]
    name = f.replace("__", " → ").replace("_", " ")
    abbrevs = {"pct": "%", "amt": "Amount", "no": "Number", "cd": "CD",
               "kcc": "KCC", "shg": "SHG", "pmjdy": "PMJDY", "npa": "NPA",
               "upi": "UPI", "bc": "BC", "atm": "ATM", "casa": "CASA",
               "nrlm": "NRLM", "pmay": "PMAY", "pmegp": "PMEGP",
               "sui": "SUI", "sc": "SC", "st": "ST"}
    words = name.split()
    return " ".join(abbrevs.get(w.lower(), w.title()) for w in words)


def fmt_val(v):
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


def state_slug(raw):
    return re.sub(r"[^\w]", "_", raw.strip().lower()).strip("_")


def title_case_state(raw):
    specials = {
        "andaman & nicobar":  "Andaman & Nicobar",
        "jammu and kashmir":  "Jammu & Kashmir",
        "jammu & kashmir":    "Jammu & Kashmir",
    }
    lower = raw.strip().lower()
    return specials.get(lower, raw.strip().title())


def state_name_from_slug(slug):
    """Best-effort: 'west-bengal' → 'West Bengal'"""
    return slug.replace("-", " ").replace("_", " ").title()


# ── Main ─────────────────────────────────────────────────────────────────────

def collect_indicator_data(indicator_key):
    """
    Returns dict:
      state_name → { quarter_code → { field → [values] } }
    sorted by quarter_code ascending.
    Also returns the list of data fields (excluding district/state).
    """
    ind_path = os.path.join(IND_DIR, indicator_key)
    json_files = sorted(glob.glob(os.path.join(ind_path, "*.json")))
    if not json_files:
        return {}, []

    # state → quarter → field → [values]
    by_state = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    all_fields = []

    all_fields_set = []  # ordered list preserving first-seen order
    seen_fields = set()

    for fpath in json_files:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)

        quarter_code = data.get("quarter", "unknown")
        districts    = data.get("districts", [])
        if not districts:
            continue

        # Collect union of all fields across all files (field set can differ by era)
        sample_fields = [k for k in districts[0].keys() if k not in ("district", "state")]
        for sf in sample_fields:
            if sf not in seen_fields:
                all_fields_set.append(sf)
                seen_fields.add(sf)

        for row in districts:
            raw_state = row.get("state", "Unknown")
            # Normalise slug-style state names like "west-bengal"
            if raw_state == raw_state.lower() or "-" in raw_state:
                state = state_name_from_slug(raw_state)
            else:
                state = title_case_state(raw_state)

            for f in sample_fields:
                v = row.get(f)
                if v is not None and v != "":
                    try:
                        by_state[state][quarter_code][f].append(float(str(v).replace(",", "")))
                    except (ValueError, TypeError):
                        pass

    all_fields = all_fields_set
    return by_state, all_fields


def build_trend_text(indicator_key, state_name, quarters_data, all_fields):
    """
    quarters_data: quarter_code → field → [float values]
    Returns the trend summary text, or None if insufficient data.
    """
    ind_label = INDICATOR_LABELS.get(indicator_key, indicator_key.replace("_", " ").title())
    sorted_quarters = sorted(quarters_data.keys())

    if len(sorted_quarters) < 2:
        return None  # No trend to report for a single quarter

    # Compute per-quarter state averages
    # Format: list of (q_label, {field: avg})
    q_avgs = []
    for qc in sorted_quarters:
        fd = quarters_data[qc]
        avgs = {}
        for f in all_fields:
            vals = fd.get(f, [])
            if vals:
                avgs[f] = sum(vals) / len(vals)
        if avgs:
            q_avgs.append((qc, quarter_label(qc), avgs))

    if len(q_avgs) < 2:
        return None

    # Choose the primary metric:
    # 1. Prefer ratio/pct/coverage fields (most meaningful for trend analysis)
    # 2. Among those, pick the one with the most coverage across quarters
    # 3. Fall back to the field with highest overall coverage
    def field_coverage(f):
        return sum(1 for _, _, avgs in q_avgs if f in avgs)

    ratio_keywords = ("ratio", "pct", "percentage", "coverage", "rate")
    ratio_fields   = [f for f in all_fields if any(k in f.lower() for k in ratio_keywords)]
    count_fields   = [f for f in all_fields if f not in ratio_fields]

    # Pick best ratio field (highest coverage), then fall back to count fields
    primary_field = None
    for candidates in (ratio_fields, count_fields):
        if candidates:
            best = max(candidates, key=field_coverage)
            if field_coverage(best) >= len(q_avgs) * 0.3:  # at least 30% coverage
                primary_field = best
                break
    if primary_field is None:
        return None

    first_q_code, first_q_lbl, first_avgs = q_avgs[0]
    last_q_code,  last_q_lbl,  last_avgs  = q_avgs[-1]

    lines = []
    lines.append(f"FINER Trend Summary: {ind_label} — {state_name} (All Quarters)")
    lines.append(f"Indicator: {indicator_key}")
    lines.append(f"State: {state_name}")
    lines.append(f"Quarters covered: {len(q_avgs)} ({first_q_lbl} to {last_q_lbl})")
    lines.append(f"Primary metric: {field_label(primary_field)}")
    lines.append("")

    # ── Quarter-by-quarter state averages (primary metric only to stay compact) ──
    lines.append(f"State average — {field_label(primary_field)} — by quarter:")
    for _, q_lbl, avgs in q_avgs:
        v = avgs.get(primary_field)
        lines.append(f"  {q_lbl}: {fmt_val(v) if v is not None else 'N/A'}")

    # ── Net change ──
    v_first = first_avgs.get(primary_field)
    v_last  = last_avgs.get(primary_field)
    if v_first and v_last and v_first != 0:
        delta     = v_last - v_first
        delta_pct = delta / v_first * 100
        direction = "increase" if delta > 0 else "decrease"
        lines.append("")
        lines.append(
            f"Net change ({first_q_lbl} → {last_q_lbl}): "
            f"{fmt_val(abs(delta))} {direction} "
            f"({abs(delta_pct):.1f}% {direction})"
        )

    # ── Additional fields (secondary metrics, latest quarter averages) ──
    secondary = [f for f in all_fields if f != primary_field]
    if secondary:
        lines.append("")
        lines.append(f"Other metrics (state average, {last_q_lbl}):")
        for f in secondary[:4]:  # cap at 4 secondary metrics
            v = last_avgs.get(f)
            if v is not None:
                lines.append(f"  {field_label(f)}: {fmt_val(v)}")

    return "\n".join(lines)


def write_chunk(indicator_key, state_name, text, first_quarter, last_quarter):
    slug = state_slug(state_name)
    out_dir = os.path.join(TEXT_DIR, slug, "tables")
    os.makedirs(out_dir, exist_ok=True)

    fname = f"{indicator_key}_trend_summary.txt"
    fpath = os.path.join(out_dir, fname)

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(f"---\n")
        f.write(f"state: {state_name}\n")
        f.write(f"type: trend_summary\n")
        f.write(f"quarter: {quarter_label(first_quarter)} to {quarter_label(last_quarter)}\n")
        f.write(f"filename: {indicator_key}_{slug}_trend_summary\n")
        f.write(f"pages: 0\n")
        f.write(f"---\n\n")
        f.write(text)

    return fpath


def main():
    print("Building indicator trend summary chunks for RAG...")
    print(f"Source : {IND_DIR}")
    print(f"Output : {TEXT_DIR}")
    print()

    indicator_dirs = sorted(
        d for d in os.listdir(IND_DIR)
        if os.path.isdir(os.path.join(IND_DIR, d))
    )

    total_written = 0

    for indicator_key in indicator_dirs:
        if indicator_key in STATIC_INDICATORS:
            print(f"  {indicator_key}: skipped (static, no time series)")
            continue

        by_state, all_fields = collect_indicator_data(indicator_key)
        if not by_state:
            print(f"  {indicator_key}: no data found")
            continue

        written = 0
        for state_name, quarters_data in by_state.items():
            text = build_trend_text(indicator_key, state_name, quarters_data, all_fields)
            if not text:
                continue

            sorted_q = sorted(quarters_data.keys())
            write_chunk(indicator_key, state_name, text, sorted_q[0], sorted_q[-1])
            written += 1

        ind_label = INDICATOR_LABELS.get(indicator_key, indicator_key)
        print(f"  {ind_label}: {len(by_state)} states → {written} trend summaries")
        total_written += written

    print(f"\nTotal: {total_written} trend summary chunks written.")
    print("\nNext steps:")
    print("  python3 scripts/rag/build_index.py")
    print('  npx wrangler r2 object put "projectfiner-data/rag/chunks.json" \\')
    print('    --file=data/rag/index/chunks.json --content-type="application/json" --remote')
    print('  npx wrangler r2 object put "projectfiner-data/rag/bm25_params.json" \\')
    print('    --file=data/rag/index/bm25_params.json --content-type="application/json" --remote')


if __name__ == "__main__":
    main()
