#!/usr/bin/env python3
"""
Comprehensive SLBC Field Name Inconsistency Audit v2
=====================================================
More focused: higher thresholds for duplicate detection,
compact output, actionable results.
"""

import json
import os
import re
from collections import defaultdict
from difflib import SequenceMatcher
from itertools import combinations

BASE_DIR = "/Users/abhinav/Downloads/projectfiner/public/slbc-data"

STATES = [
    "assam", "meghalaya", "manipur", "arunachal-pradesh", "mizoram",
    "tripura", "nagaland", "sikkim", "bihar", "west-bengal"
]

PRIORITY_CATEGORIES = [
    "credit_deposit_ratio", "branch_network", "kcc", "pmjdy",
    "digital_transactions", "aadhaar_authentication", "shg",
    "education_loan", "housing_pmay", "pmmy_mudra",
    "msme_outstanding", "agriculture_outstanding", "agriculture_credit",
    "priority_sector", "weaker_section", "deposit", "advance",
    "cd_ratio", "atm", "bc_agent", "rseti", "flcc", "pm_svanidhi",
    "pm_vishwakarma", "stand_up_india", "housing_loan",
]


def normalize_for_comparison(name):
    """Aggressively normalize a field name for comparison."""
    n = name.lower().strip()
    # Remove parenthetical content
    n = re.sub(r'\(.*?\)', '', n)
    # Normalize separators
    n = re.sub(r'[\s\-\.]+', '_', n)
    # Remove common prefixes/suffixes
    n = re.sub(r'^(total_|no_of_|num_|number_of_|count_of_)', '', n)
    n = re.sub(r'_(total|count|number|no|num)$', '', n)
    # Common abbreviation normalization
    n = n.replace('amt', 'amount')
    n = n.replace('bal', 'balance')
    n = n.replace('a_c', 'account').replace('a/c', 'account')
    n = n.replace('o_s', 'outstanding').replace('o/s', 'outstanding')
    n = n.replace('nos', 'number')
    n = n.replace('rs_', 'amount_').replace('_rs', '_amount')
    n = n.strip('_')
    return n


def string_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def load_all_data():
    all_data = {}
    for state in STATES:
        path = os.path.join(BASE_DIR, state, f"{state}_complete.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        all_data[state] = data
        quarters = list(data.get("quarters", {}).keys())
        cats_set = set()
        for q in quarters:
            cats_set.update(data["quarters"][q].get("tables", {}).keys())
        print(f"  {state}: {len(quarters)} quarters, {len(cats_set)} categories")
    return all_data


def build_field_index(all_data):
    field_index = defaultdict(lambda: defaultdict(list))
    category_coverage = defaultdict(set)

    for state, data in all_data.items():
        for quarter, qdata in data.get("quarters", {}).items():
            for category, cdata in qdata.get("tables", {}).items():
                fields = set(cdata.get("fields", []))
                districts = cdata.get("districts", {})
                for dname, dvals in districts.items():
                    if isinstance(dvals, dict):
                        fields.update(dvals.keys())
                fields.discard("District")
                fields.discard("district")

                category_coverage[category].add((state, quarter))
                for field in fields:
                    field_index[category][field].append((state, quarter))

    return field_index, category_coverage


def find_duplicates(fields_dict, category_coverage):
    """Find likely duplicate field pairs with strict criteria."""
    field_names = list(fields_dict.keys())
    if len(field_names) < 2:
        return []

    total_sq = len(category_coverage)
    duplicates = []

    # Pre-compute normalized names
    norm_map = {f: normalize_for_comparison(f) for f in field_names}

    for f1, f2 in combinations(field_names, 2):
        n1, n2 = norm_map[f1], norm_map[f2]

        sq_f1 = set(fields_dict[f1])
        sq_f2 = set(fields_dict[f2])
        overlap = sq_f1 & sq_f2
        union = sq_f1 | sq_f2

        # Skip if both are very rare (noise)
        if len(sq_f1) <= 1 and len(sq_f2) <= 1:
            continue

        # Criteria 1: Identical after normalization
        if n1 == n2:
            complementarity = 1.0 - (len(overlap) / len(union)) if union else 0
            duplicates.append({
                "field_a": f1, "field_b": f2,
                "type": "IDENTICAL_NORMALIZED",
                "confidence": "HIGH",
                "quarters_a": len(sq_f1), "quarters_b": len(sq_f2),
                "overlap": len(overlap),
                "complementarity": complementarity,
                "sq_a": sq_f1, "sq_b": sq_f2,
            })
            continue

        # Criteria 2: Very high similarity + complementary coverage
        sim = string_similarity(n1, n2)
        complementarity = 1.0 - (len(overlap) / len(union)) if union else 0

        if sim >= 0.8 and complementarity >= 0.7:
            duplicates.append({
                "field_a": f1, "field_b": f2,
                "type": f"SIMILAR_COMPLEMENTARY (sim={sim:.2f}, comp={complementarity:.2f})",
                "confidence": "HIGH",
                "quarters_a": len(sq_f1), "quarters_b": len(sq_f2),
                "overlap": len(overlap),
                "complementarity": complementarity,
                "sq_a": sq_f1, "sq_b": sq_f2,
            })
            continue

        # Criteria 3: One contains the other (normalized) + complementary
        if (len(n1) > 3 and len(n2) > 3) and (n1 in n2 or n2 in n1) and complementarity >= 0.5:
            duplicates.append({
                "field_a": f1, "field_b": f2,
                "type": f"SUBSTRING_MATCH (comp={complementarity:.2f})",
                "confidence": "MEDIUM",
                "quarters_a": len(sq_f1), "quarters_b": len(sq_f2),
                "overlap": len(overlap),
                "complementarity": complementarity,
                "sq_a": sq_f1, "sq_b": sq_f2,
            })
            continue

        # Criteria 4: High similarity alone
        if sim >= 0.85:
            duplicates.append({
                "field_a": f1, "field_b": f2,
                "type": f"HIGH_SIMILARITY (sim={sim:.2f})",
                "confidence": "MEDIUM",
                "quarters_a": len(sq_f1), "quarters_b": len(sq_f2),
                "overlap": len(overlap),
                "complementarity": complementarity,
                "sq_a": sq_f1, "sq_b": sq_f2,
            })

    duplicates.sort(key=lambda x: (0 if x["confidence"] == "HIGH" else 1, -x["complementarity"]))
    return duplicates


def format_state_quarters(sq_set):
    """Compact format for state-quarter sets."""
    by_state = defaultdict(list)
    for s, q in sq_set:
        by_state[s].append(q)
    parts = []
    for s in sorted(by_state):
        qs = sorted(by_state[s])
        parts.append(f"{s}[{','.join(qs)}]")
    return "; ".join(parts)


def main():
    print("=" * 100)
    print("SLBC FIELD NAME INCONSISTENCY AUDIT")
    print("=" * 100)
    print()

    print("Loading state data...")
    all_data = load_all_data()
    print(f"\nLoaded {len(all_data)} states.\n")

    print("Building field index...")
    field_index, category_coverage = build_field_index(all_data)
    print(f"Found {len(field_index)} total categories.\n")

    all_categories = sorted(field_index.keys())
    priority_present = [c for c in PRIORITY_CATEGORIES if c in field_index]
    other_cats = [c for c in all_categories if c not in set(PRIORITY_CATEGORIES)]
    ordered_cats = priority_present + other_cats

    # ===== SUMMARY TABLE =====
    print("=" * 100)
    print("CATEGORY OVERVIEW")
    print("=" * 100)
    print(f"{'Category':<40} {'Unique Fields':>13} {'States':>7} {'Qtrs':>6}")
    print("-" * 70)
    for cat in ordered_cats:
        fields = field_index[cat]
        states_with = set(s for s, q in category_coverage[cat])
        quarters_with = set(q for s, q in category_coverage[cat])
        marker = " ***" if cat in priority_present else ""
        print(f"{cat:<40} {len(fields):>13} {len(states_with):>7} {len(quarters_with):>6}{marker}")

    # ===== DETAILED PER-CATEGORY =====
    print("\n\n")
    print("=" * 100)
    print("DETAILED FIELD AUDIT BY CATEGORY")
    print("=" * 100)

    all_high_dupes = []
    all_med_dupes = []

    for cat in ordered_cats:
        fields = field_index[cat]
        total_sq = len(category_coverage[cat])
        states_with = sorted(set(s for s, q in category_coverage[cat]))

        print(f"\n{'━' * 100}")
        print(f"  CATEGORY: {cat}")
        print(f"  States: {', '.join(states_with)} | {total_sq} state-quarter combos | {len(fields)} unique fields")
        print(f"{'━' * 100}")

        # Fields sorted by coverage
        sorted_fields = sorted(fields.items(), key=lambda x: -len(x[1]))
        print(f"\n  {'Field Name':<60} {'Count':>6} {'Cov%':>6}")
        print(f"  {'─'*60} {'─'*6} {'─'*6}")
        for fname, sq_list in sorted_fields:
            pct = len(sq_list) / total_sq * 100 if total_sq else 0
            gap_marker = " <<<" if pct < 90 and pct > 5 else ""
            print(f"  {fname:<60} {len(sq_list):>6} {pct:>5.1f}%{gap_marker}")

        # Duplicates
        dupes = find_duplicates(fields, category_coverage[cat])
        if dupes:
            print(f"\n  *** SUSPECTED DUPLICATES ***")
            for d in dupes:
                conf_label = f"[{d['confidence']}]"
                print(f"\n    {conf_label} {d['type']}")
                print(f"      \"{d['field_a']}\"  ({d['quarters_a']} sq)")
                print(f"      \"{d['field_b']}\"  ({d['quarters_b']} sq)")
                print(f"      Overlap: {d['overlap']} | Complementarity: {d['complementarity']:.2f}")

                # Compact breakdown
                only_a = d["sq_a"] - d["sq_b"]
                only_b = d["sq_b"] - d["sq_a"]
                if only_a and len(only_a) <= 30:
                    by_s = defaultdict(list)
                    for s, q in only_a:
                        by_s[s].append(q)
                    for s in sorted(by_s):
                        print(f"        Only A in {s}: {', '.join(sorted(by_s[s]))}")
                if only_b and len(only_b) <= 30:
                    by_s = defaultdict(list)
                    for s, q in only_b:
                        by_s[s].append(q)
                    for s in sorted(by_s):
                        print(f"        Only B in {s}: {', '.join(sorted(by_s[s]))}")

                if d["confidence"] == "HIGH":
                    all_high_dupes.append((cat, d))
                else:
                    all_med_dupes.append((cat, d))

    # ===== EXECUTIVE SUMMARY =====
    print("\n\n")
    print("=" * 100)
    print("EXECUTIVE SUMMARY: ALL HIGH-CONFIDENCE DUPLICATES")
    print("=" * 100)
    if all_high_dupes:
        current_cat = None
        for cat, d in all_high_dupes:
            if cat != current_cat:
                print(f"\n  [{cat}]")
                current_cat = cat
            print(f"    \"{d['field_a']}\" <-> \"{d['field_b']}\" | {d['type']} | A:{d['quarters_a']} B:{d['quarters_b']} overlap:{d['overlap']}")
    else:
        print("  None found.")

    print(f"\n\nTotal HIGH confidence: {len(all_high_dupes)}")
    print(f"Total MEDIUM confidence: {len(all_med_dupes)}")
    print(f"Grand total suspected duplicates: {len(all_high_dupes) + len(all_med_dupes)}")

    # ===== MEDIUM CONFIDENCE SUMMARY =====
    if all_med_dupes:
        print("\n\n")
        print("=" * 100)
        print("ALL MEDIUM-CONFIDENCE DUPLICATES")
        print("=" * 100)
        current_cat = None
        for cat, d in all_med_dupes:
            if cat != current_cat:
                print(f"\n  [{cat}]")
                current_cat = cat
            print(f"    \"{d['field_a']}\" <-> \"{d['field_b']}\" | {d['type']}")


if __name__ == "__main__":
    main()
