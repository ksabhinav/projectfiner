#!/usr/bin/env python3
"""
Aggressive field name normalization for ALL 8 NE states' SLBC data.

Fixes duplicate columns caused by:
- Case differences: DEPOSITS vs Deposits vs DEPOSITs
- Pluralization: DEPOSIT vs DEPOSITS, ADVANCE vs ADVANCES, CD RATIO vs CD RATIOs
- Suffix variants: Total Br vs Total Br(s), Semi-Urban vs Semi- Urban vs Semi Urban
- Trailing periods, (s) suffixes, NO vs No. etc.

Two-pass approach:
  Pass 1: String normalization (title-case, remove (s), fix Semi-Urban, etc.)
  Pass 2: Cross-quarter deduplication within each category
"""

import json
import csv
import os
import re
from pathlib import Path
from collections import Counter, defaultdict

BASE = Path("/Users/abhinav/Downloads/projectfiner/public/slbc-data")

STATES = [
    "assam",
    "meghalaya",
    "manipur",
    "arunachal-pradesh",
    "mizoram",
    "tripura",
    "nagaland",
    "sikkim",
]

STATE_SLUGS = {
    "assam": "assam",
    "meghalaya": "meghalaya",
    "manipur": "manipur",
    "arunachal-pradesh": "arunachal_pradesh",
    "mizoram": "mizoram",
    "tripura": "tripura",
    "nagaland": "nagaland",
    "sikkim": "sikkim",
}


def normalize_field_pass1(name):
    """
    Pass 1: Deterministic string normalization.
    Applied to every field name individually.
    """
    if not name or not isinstance(name, str):
        return name

    s = name.strip()

    # Normalize multiple spaces to single
    s = re.sub(r'\s+', ' ', s)

    # Fix spacing around slashes: "A/ C" -> "A/C"
    s = re.sub(r'\s*/\s*', '/', s)

    # --- Semi-Urban normalization ---
    # "Semi- Urban", "Semi Urban", "Semi -Urban" -> "Semi-Urban"
    s = re.sub(r'(?i)semi[\s-]+urban', 'Semi-Urban', s)

    # --- Remove trailing (s) ---
    s = re.sub(r'\(s\)$', '', s)
    # Also handle (s) in middle: "Total Br(s)" -> "Total Br"
    s = re.sub(r'\(s\)\b', '', s)

    # --- Br / Br. / Branches normalization -> "Br" ---
    # "Total Br." -> "Total Br"
    s = re.sub(r'\bBr\.\s*$', 'Br', s)
    s = re.sub(r'\bBr\.$', 'Br', s)

    # --- Trailing periods (but keep No.) ---
    # Strip trailing period unless preceded by "No"
    if s.endswith('.') and not s.endswith('No.') and not s.endswith('S.No.'):
        s = s.rstrip('.')

    # --- A/C normalization ---
    s = re.sub(r'\bA/[Cc]s\b', 'A/C', s)
    s = re.sub(r'\ba/cs?\b', 'A/C', s, flags=re.IGNORECASE)
    s = re.sub(r'\bA/c\b', 'A/C', s)
    s = re.sub(r'\bAC$', 'A/C', s)
    s = re.sub(r'\bAc$', 'A/C', s)
    s = re.sub(r'\bac$', 'A/C', s)
    s = re.sub(r'\bAC\s', 'A/C ', s)
    s = re.sub(r'\bAc\s', 'A/C ', s)

    # --- Amt / Amount normalization ---
    s = re.sub(r'\bAmt\.$', 'Amt', s)
    s = re.sub(r'\bAMT\.$', 'Amt', s)
    s = re.sub(r'\bAmount$', 'Amt', s)

    # --- No. normalization ---
    # NO -> No., Nos -> No., No.s -> No., Nos. -> No.
    s = re.sub(r'\bNos?\.*s?\.?$', 'No.', s)
    s = re.sub(r'\bNo\.s$', 'No.', s)
    s = re.sub(r'\bNO$', 'No.', s)

    # --- Pluralization normalization ---
    # These handle specific known plural variants that create duplicates

    # DEPOSITs -> Deposits, DEPOSITS -> Deposits, DEPOSIT -> Deposit -> Deposits
    s = re.sub(r'\bDEPOSITs\b', 'Deposits', s)
    s = re.sub(r'\bDEPOSITS\b', 'Deposits', s)
    s = re.sub(r'\bDEPOSIT\b', 'Deposit', s)

    # ADVANCES -> Advances, ADVANCE -> Advance
    s = re.sub(r'\bADVANCES\b', 'Advances', s)
    s = re.sub(r'\bADVANCE\b', 'Advance', s)

    # CD RATIOs -> CD Ratio
    s = re.sub(r'\bCD RATIOs\b', 'CD Ratio', s)
    s = re.sub(r'\bCD RATIO\b', 'CD Ratio', s)

    # BRANCHes -> Branches, BRANCH -> Branch
    s = re.sub(r'\bBRANCHes\b', 'Branches', s)
    s = re.sub(r'\bBRANCH\b', 'Branch', s)

    # ATMs -> ATM (keep uppercase for abbreviation)
    s = re.sub(r'\bATMs\b', 'ATM', s)
    s = re.sub(r'\bAtm\b', 'ATM', s)

    # CSPs -> CSP
    s = re.sub(r'\bCSPs\b', 'CSP', s)

    # BCs -> BC
    s = re.sub(r'\bBCs\b', 'BC', s)

    # Others -> Other (only as standalone field, not in compound)
    # Be careful: "Others" as a category name should stay

    # RENEW- ABLE -> Renewable, Renew- able -> Renewable
    s = re.sub(r'(?i)renew-?\s*able', 'Renewable', s)

    # --- ALL-CAPS words to Title Case ---
    # For multi-word all-caps like "AGRI INFRA" -> "Agri Infra"
    # "TERM LOAN" -> "Term Loan", etc.
    # But preserve known abbreviations: ATM, BC, CSP, CD, NPA, NPS, KCC, etc.
    PRESERVE_UPPER = {
        'ATM', 'BC', 'CSP', 'CD', 'NPA', 'NPS', 'KCC', 'NRLM', 'NULM',
        'PMEGP', 'SHG', 'SUI', 'DRI', 'PMJJBY', 'PMSBY', 'APY', 'PSA',
        'MUDRA', 'SISHU', 'KISHORE', 'TARUN', 'PMJDY', 'PMAY', 'PMFME',
        'RSETI', 'FLC', 'UPI', 'IMPS', 'USSD', 'BHIM', 'A/C', 'O/S',
        'CY', 'FY', 'IC', 'AH', 'PS', 'KVB', 'KVIC', 'KVIB', 'DIC',
        'SC', 'ST', 'NO', 'AMT', 'GE', 'CASA', 'IT', 'QR',
        'TOTAL', 'BAND', 'INDUS', 'II', 'III', 'IV',
    }

    # Only apply title-casing to ALL-CAPS words (2+ chars, all uppercase)
    def title_case_word(match):
        word = match.group(0)
        if word.upper() in PRESERVE_UPPER:
            return word  # keep as-is
        if word.isupper() and len(word) >= 2:
            return word.capitalize()
        return word

    s = re.sub(r'\b[A-Z]{2,}\b', title_case_word, s)

    # Final cleanup
    s = re.sub(r'\s+', ' ', s).strip()

    return s


def grouping_key(name):
    """
    Generate a key for grouping fields that should be the same.
    More aggressive than pass 1 - used for cross-quarter dedup.
    """
    s = name.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    # Remove trailing (s)
    s = re.sub(r'\(s\)', '', s)
    # Normalize semi-urban
    s = re.sub(r'semi[\s-]+urban', 'semi-urban', s)
    # Normalize br variants
    s = re.sub(r'\bbr\.?\s*$', 'br', s)
    # Normalize plurals
    s = re.sub(r'\bdeposits?\b', 'deposit', s)
    s = re.sub(r'\badvances?\b', 'advance', s)
    s = re.sub(r'\bratios?\b', 'ratio', s)
    s = re.sub(r'\bbranches\b', 'branch', s)
    s = re.sub(r'\batms?\b', 'atm', s)
    s = re.sub(r'\bothers?\b', 'other', s)
    s = re.sub(r'\bcsps?\b', 'csp', s)
    s = re.sub(r'\bbcs?\b', 'bc', s)
    # Strip trailing periods
    s = re.sub(r'\.+$', '', s)
    # Normalize no/nos/no.
    s = re.sub(r'\bnos?\.?\s*$', 'no', s)
    # Normalize amt
    s = re.sub(r'\bamt\.?\s*$', 'amt', s)
    # Normalize renew- able
    s = re.sub(r'renew-?\s*able', 'renewable', s)
    # Remove hyphens for comparison
    # s = s.replace('-', ' ')  # don't do this, semi-urban matters
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def pick_canonical(variants_with_counts):
    """
    Given a dict of {field_name: count}, pick the canonical form.
    Prefer: most frequent. On tie, prefer title-cased / more standard form.
    """
    if len(variants_with_counts) == 1:
        return list(variants_with_counts.keys())[0]

    # Sort by count (desc), then by "quality" heuristics
    def quality_score(name):
        score = 0
        # Prefer title case over ALL CAPS
        words = name.split()
        for w in words:
            if w[0].isupper() and not w.isupper():
                score += 1  # title-cased word
        # Prefer with trailing No. over NO
        if name.endswith('No.'):
            score += 2
        # Prefer without trailing (s)
        if '(s)' not in name:
            score += 1
        return score

    sorted_variants = sorted(
        variants_with_counts.items(),
        key=lambda x: (-x[1], -quality_score(x[0]), x[0])
    )
    return sorted_variants[0][0]


def process_state(state_dir_name):
    """Process one state: normalize fields, regenerate everything."""
    slug = STATE_SLUGS[state_dir_name]
    state_dir = BASE / state_dir_name
    json_path = state_dir / f"{slug}_complete.json"

    if not json_path.exists():
        print(f"  SKIP: {json_path} not found")
        return {}

    with open(json_path) as f:
        data = json.load(f)

    quarters = data.get("quarters", {})
    stats = {"merges": 0, "renames": 0, "categories_affected": set()}

    # ===== PASS 1: String normalization =====
    for qname, quarter in quarters.items():
        for tname, table in quarter.get("tables", {}).items():
            raw_fields = table.get("fields", [])
            new_fields = [normalize_field_pass1(f) for f in raw_fields]

            # Check for merges within this quarter after pass 1
            seen = {}
            deduped_fields = []
            for f in new_fields:
                if f not in seen:
                    seen[f] = True
                    deduped_fields.append(f)

            if len(deduped_fields) < len(new_fields):
                stats["merges"] += len(new_fields) - len(deduped_fields)

            # Rename district data
            districts = table.get("districts", {})
            for dist_name, dist_data in districts.items():
                new_data = {}
                for raw_f in list(dist_data.keys()):
                    norm_f = normalize_field_pass1(raw_f)
                    val = dist_data[raw_f]
                    if norm_f in new_data:
                        # Merge: prefer non-null
                        existing = new_data[norm_f]
                        if (existing is None or existing == "" or existing == "0") and val and val != "" and val != "0":
                            new_data[norm_f] = val
                    else:
                        new_data[norm_f] = val
                districts[dist_name] = new_data

            table["fields"] = deduped_fields
            table["districts"] = districts

    # ===== PASS 2: Cross-quarter deduplication =====
    # For each category, collect all field names across all quarters
    # Group by grouping_key, pick canonical, rename
    cat_field_counts = defaultdict(lambda: defaultdict(Counter))
    # cat_field_counts[category][grouping_key][original_name] = count

    for qname, quarter in quarters.items():
        for tname, table in quarter.get("tables", {}).items():
            for f in table.get("fields", []):
                gk = grouping_key(f)
                cat_field_counts[tname][gk][f] += 1

    # Build canonical mapping per category
    cat_canonical = {}  # (category, grouping_key) -> canonical_name
    for tname, gk_map in cat_field_counts.items():
        for gk, name_counts in gk_map.items():
            if len(name_counts) > 1:
                canonical = pick_canonical(dict(name_counts))
                cat_canonical[(tname, gk)] = canonical
                for variant in name_counts:
                    if variant != canonical:
                        stats["renames"] += name_counts[variant]
                        stats["categories_affected"].add(tname)
            else:
                canonical = list(name_counts.keys())[0]
                cat_canonical[(tname, gk)] = canonical

    # Apply pass 2 renaming
    for qname, quarter in quarters.items():
        for tname, table in quarter.get("tables", {}).items():
            raw_fields = table.get("fields", [])
            new_fields = []
            seen = set()
            for f in raw_fields:
                gk = grouping_key(f)
                canonical = cat_canonical.get((tname, gk), f)
                if canonical not in seen:
                    new_fields.append(canonical)
                    seen.add(canonical)

            # Rename in districts
            districts = table.get("districts", {})
            for dist_name, dist_data in districts.items():
                new_data = {}
                for old_f in list(dist_data.keys()):
                    gk = grouping_key(old_f)
                    canonical = cat_canonical.get((tname, gk), old_f)
                    val = dist_data[old_f]
                    if canonical in new_data:
                        existing = new_data[canonical]
                        if (existing is None or existing == "" or existing == "0") and val and val != "" and val != "0":
                            new_data[canonical] = val
                    else:
                        new_data[canonical] = val
                districts[dist_name] = new_data

            # Make sure fields list includes any fields from district data
            for dist_data in districts.values():
                for f in dist_data.keys():
                    if f not in seen:
                        new_fields.append(f)
                        seen.add(f)

            table["fields"] = new_fields
            table["districts"] = districts

    # Write back JSON
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Regenerate quarterly CSVs
    regenerate_quarterly_csvs(data, state_dir / "quarterly")

    # Regenerate timeseries
    regenerate_timeseries(data, state_dir, slug)

    stats["categories_affected"] = len(stats["categories_affected"])
    return stats


def regenerate_quarterly_csvs(data, quarterly_dir):
    """Regenerate all quarterly CSVs from the normalized JSON."""
    quarters = data.get("quarters", {})

    for qname, quarter in quarters.items():
        folder_name = qname
        if not re.match(r'^\d{4}-\d{2}$', folder_name):
            as_on = quarter.get("as_on_date", "")
            if as_on:
                parts = as_on.split("-")
                if len(parts) == 3:
                    folder_name = f"{parts[2]}-{parts[1]}"
            if not re.match(r'^\d{4}-\d{2}$', folder_name):
                continue

        folder_path = quarterly_dir / folder_name

        if folder_path.exists():
            for f in folder_path.glob("*.csv"):
                f.unlink()
        else:
            folder_path.mkdir(parents=True, exist_ok=True)

        tables = quarter.get("tables", {})
        for tname, table in tables.items():
            districts = table.get("districts", {})
            if not districts:
                continue

            fields = table.get("fields", [])
            if not fields:
                first_dist = next(iter(districts.values()))
                fields = list(first_dist.keys())

            csv_path = folder_path / f"{tname}.csv"
            with open(csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["District"] + fields)
                for dist_name in sorted(districts.keys()):
                    dist_data = districts[dist_name]
                    row = [dist_name] + [dist_data.get(fld, "") for fld in fields]
                    writer.writerow(row)


def normalize_timeseries_key(key):
    """
    Normalize a timeseries column key.
    Applied after lowercasing + underscoring.
    """
    # Strip trailing periods
    key = re.sub(r'\.+$', '', key)

    # A/C normalization
    key = re.sub(r'_ac$', '_a/c', key)
    key = re.sub(r'_acs$', '_a/c', key)
    key = re.sub(r'_a/cs$', '_a/c', key)

    # Amt normalization
    key = re.sub(r'_amount$', '_amt', key)
    key = re.sub(r'_amt\.$', '_amt', key)

    # No. normalization
    key = re.sub(r'_nos?\.?s?\.?$', '_no.', key)
    key = re.sub(r'_no\.s$', '_no.', key)
    if key.endswith('_no'):
        key = key + '.'

    # Semi-urban normalization
    key = re.sub(r'semi[\s_-]+urban', 'semi-urban', key)

    # Plural normalization
    key = re.sub(r'_deposits_', '_deposit_', key)
    key = re.sub(r'_deposits$', '_deposit', key)
    key = re.sub(r'_advances_', '_advance_', key)
    key = re.sub(r'_advances$', '_advance', key)
    key = re.sub(r'_ratios_', '_ratio_', key)
    key = re.sub(r'_ratios$', '_ratio', key)
    key = re.sub(r'_branches_', '_branch_', key)
    key = re.sub(r'_branches$', '_branch', key)
    key = re.sub(r'_atms_', '_atm_', key)
    key = re.sub(r'_atms$', '_atm', key)
    key = re.sub(r'_others_', '_other_', key)
    key = re.sub(r'_others$', '_other', key)
    key = re.sub(r'_csps_', '_csp_', key)
    key = re.sub(r'_csps$', '_csp', key)
    key = re.sub(r'_bcs_', '_bc_', key)
    key = re.sub(r'_bcs$', '_bc', key)

    # Br(s) normalization
    key = re.sub(r'_br\(s\)', '_br', key)
    key = re.sub(r'_br\.$', '_br', key)

    # Renew- able -> renewable
    key = re.sub(r'renew-?\s*able', 'renewable', key)

    # Fix double underscores
    key = re.sub(r'_+', '_', key)
    key = key.strip('_')

    return key


def regenerate_timeseries(data, state_dir, state_slug):
    """Regenerate timeseries CSV and JSON from normalized data."""
    all_records = []
    all_field_keys = set()

    quarters = data.get("quarters", {})

    # Build normalized keys
    def make_ts_key(tname, fld):
        key = f"{tname}__{fld}"
        norm_key = re.sub(r'[^a-z0-9_/()&.,%]+', '_', key.lower().replace(' ', '_'))
        norm_key = re.sub(r'_+', '_', norm_key).strip('_')
        norm_key = normalize_timeseries_key(norm_key)
        return norm_key

    # First pass: collect all field keys
    for qname, q in quarters.items():
        for tname, table in q.get("tables", {}).items():
            for dist_name, fields in table.get("districts", {}).items():
                for fld in fields.keys():
                    all_field_keys.add(make_ts_key(tname, fld))

    sorted_fields = sorted(all_field_keys)

    # Second pass: build records
    periods_data = {}

    for qname, q in quarters.items():
        period = q.get("period", qname)
        as_on = q.get("as_on_date", "")
        fy = q.get("fy", "")

        quarter_districts = {}
        for tname, table in q.get("tables", {}).items():
            for dist_name, fields in table.get("districts", {}).items():
                if dist_name not in quarter_districts:
                    quarter_districts[dist_name] = {
                        "district": dist_name,
                        "period": period,
                        "as_on_date": as_on,
                        "fy": fy,
                    }
                for fld, val in fields.items():
                    norm_key = make_ts_key(tname, fld)
                    existing = quarter_districts[dist_name].get(norm_key)
                    if existing is None or existing == "" or existing == "0":
                        quarter_districts[dist_name][norm_key] = val
                    elif val and val != "" and val != "0" and (existing is None or existing == ""):
                        quarter_districts[dist_name][norm_key] = val

        for dist_name, record in sorted(quarter_districts.items()):
            all_records.append(record)

        if period not in periods_data:
            periods_data[period] = {
                "period": period,
                "num_districts": len(quarter_districts),
                "districts": [],
            }
        periods_data[period]["districts"] = [
            quarter_districts[d] for d in sorted(quarter_districts.keys())
        ]

    # Write CSV
    csv_path = state_dir / f"{state_slug}_fi_timeseries.csv"
    csv_columns = ["district", "period", "as_on_date", "fy"] + sorted_fields

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction='ignore')
        writer.writeheader()
        for record in all_records:
            writer.writerow(record)

    # Write JSON
    json_path = state_dir / f"{state_slug}_fi_timeseries.json"

    period_dates = {}
    for r in all_records:
        if r["period"] not in period_dates and r.get("as_on_date"):
            period_dates[r["period"]] = r["as_on_date"]

    def parse_date(d):
        try:
            parts = d.split("-")
            return (int(parts[2]), int(parts[1]), int(parts[0]))
        except:
            return (0, 0, 0)

    sorted_periods = sorted(periods_data.keys(),
                           key=lambda p: parse_date(period_dates.get(p, "01-01-1900")))

    ts_json = {
        "source": data.get("source", "SLBC NE"),
        "state": data.get("state", ""),
        "description": "Complete district-wise FI time-series",
        "num_periods": len(periods_data),
        "total_records": len(all_records),
        "total_fields": len(sorted_fields),
        "periods": [periods_data[p] for p in sorted_periods],
    }

    with open(json_path, "w") as f:
        json.dump(ts_json, f, indent=2, ensure_ascii=False)

    return len(sorted_fields)


def count_timeseries_columns(state_dir_name):
    """Count columns in a state's timeseries CSV."""
    slug = STATE_SLUGS[state_dir_name]
    csv_path = BASE / state_dir_name / f"{slug}_fi_timeseries.csv"
    if not csv_path.exists():
        return 0
    with open(csv_path) as f:
        header = next(csv.reader(f))
        return len(header)


def check_duplicates(state_dir_name):
    """Check for remaining field duplicates in complete.json."""
    slug = STATE_SLUGS[state_dir_name]
    json_path = BASE / state_dir_name / f"{slug}_complete.json"
    if not json_path.exists():
        return []

    with open(json_path) as f:
        data = json.load(f)

    dups = []
    cat_fields = defaultdict(lambda: defaultdict(set))
    for qname, q in data.get("quarters", {}).items():
        for tname, table in q.get("tables", {}).items():
            for f in table.get("fields", []):
                gk = grouping_key(f)
                cat_fields[tname][gk].add(f)

    for cat, gk_map in sorted(cat_fields.items()):
        for gk, originals in sorted(gk_map.items()):
            if len(originals) > 1:
                dups.append((cat, sorted(originals)))

    return dups


def check_timeseries_duplicates(state_dir_name):
    """Check for duplicate columns in timeseries CSV."""
    slug = STATE_SLUGS[state_dir_name]
    csv_path = BASE / state_dir_name / f"{slug}_fi_timeseries.csv"
    if not csv_path.exists():
        return []

    with open(csv_path) as f:
        header = next(csv.reader(f))

    counts = Counter(header)
    return [(col, cnt) for col, cnt in counts.items() if cnt > 1]


def main():
    print("=" * 70)
    print("AGGRESSIVE FIELD NAME NORMALIZATION v2 — ALL 8 NE STATES")
    print("=" * 70)

    # Record BEFORE counts
    print("\n--- BEFORE: Timeseries column counts ---")
    before_counts = {}
    for state in STATES:
        count = count_timeseries_columns(state)
        before_counts[state] = count
        print(f"  {state}: {count} columns")

    # Process each state
    print()
    for state in STATES:
        print(f"\n{'='*50}")
        print(f"Processing: {state}")
        print(f"{'='*50}")
        stats = process_state(state)
        if stats:
            print(f"  Pass 1 merges (within-quarter): {stats.get('merges', 0)}")
            print(f"  Pass 2 renames (cross-quarter): {stats.get('renames', 0)}")
            print(f"  Categories affected: {stats.get('categories_affected', 0)}")

    # Record AFTER counts
    print(f"\n\n{'='*70}")
    print("RESULTS")
    print(f"{'='*70}")

    print(f"\n{'State':<25} {'Before':>8} {'After':>8} {'Reduced':>8}")
    print(f"{'-'*25} {'-'*8} {'-'*8} {'-'*8}")
    for state in STATES:
        after = count_timeseries_columns(state)
        before = before_counts[state]
        reduced = before - after
        marker = " ***" if reduced > 0 else ""
        print(f"{state:<25} {before:>8} {after:>8} {reduced:>8}{marker}")

    # Check for remaining duplicates
    print(f"\n--- VERIFICATION: Remaining field duplicates in complete.json ---")
    any_dups = False
    for state in STATES:
        dups = check_duplicates(state)
        if dups:
            any_dups = True
            print(f"\n  {state}:")
            for cat, variants in dups:
                print(f"    {cat}: {variants}")
        else:
            print(f"  {state}: CLEAN - no duplicates")

    # Check timeseries column duplicates
    print(f"\n--- VERIFICATION: Duplicate columns in timeseries CSV ---")
    for state in STATES:
        dups = check_timeseries_duplicates(state)
        if dups:
            print(f"  {state}: DUPLICATES FOUND: {dups}")
        else:
            print(f"  {state}: CLEAN")

    # Spot-check Mizoram credit_deposit_ratio
    print(f"\n--- SPOT CHECK: Mizoram credit_deposit_ratio ---")
    slug = STATE_SLUGS["mizoram"]
    csv_path = BASE / "mizoram" / f"{slug}_fi_timeseries.csv"
    if csv_path.exists():
        with open(csv_path) as f:
            header = next(csv.reader(f))
        cd_cols = [c for c in header if 'credit_deposit_ratio' in c]
        print(f"  credit_deposit_ratio columns ({len(cd_cols)}):")
        for c in sorted(cd_cols):
            print(f"    {c}")

    # Spot-check Mizoram branch_network
    print(f"\n--- SPOT CHECK: Mizoram branch_network ---")
    if csv_path.exists():
        with open(csv_path) as f:
            header = next(csv.reader(f))
        bn_cols = [c for c in header if 'branch_network' in c]
        print(f"  branch_network columns ({len(bn_cols)}):")
        for c in sorted(bn_cols):
            print(f"    {c}")

    print(f"\n{'='*70}")
    print("DONE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
