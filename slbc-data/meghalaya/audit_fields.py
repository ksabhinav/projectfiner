#!/usr/bin/env python3
"""
Comprehensive field audit of meghalaya_complete.json
Checks every category across all quarters for:
  - Field name variations (spelling inconsistencies)
  - Data completeness (empty vs non-empty values per field per quarter)
  - Nearly-empty fields (>80% empty)
"""

import json
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

DATA_FILE = Path(__file__).parent / "meghalaya_complete.json"

def normalize(s):
    """Normalize a field name for fuzzy comparison."""
    s = s.strip().lower()
    s = s.replace(".", "").replace(",", "").replace("(", "").replace(")", "")
    s = s.replace("-", " ").replace("_", " ")
    # collapse whitespace
    s = " ".join(s.split())
    return s

def are_similar(a, b, threshold=0.85):
    """Check if two field names are similar but not identical."""
    if a == b:
        return False
    na, nb = normalize(a), normalize(b)
    if na == nb:
        return True
    ratio = SequenceMatcher(None, na, nb).ratio()
    return ratio >= threshold

def main():
    print("=" * 100)
    print("SLBC MEGHALAYA — COMPREHENSIVE FIELD AUDIT")
    print("=" * 100)

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    quarters_data = data["quarters"]
    quarter_names = list(quarters_data.keys())
    print(f"\nQuarters found: {len(quarter_names)}")
    print(f"  {', '.join(quarter_names)}")

    # ── Collect all categories across all quarters ──
    all_categories = set()
    for qname, qdata in quarters_data.items():
        for cat in qdata.get("tables", {}):
            all_categories.add(cat)
    all_categories = sorted(all_categories)
    print(f"\nTotal unique categories: {len(all_categories)}")

    # ── Global summaries ──
    global_spelling_issues = []
    global_empty_fields = []
    global_category_summary = []

    # ── Per-category analysis ──
    for cat in all_categories:
        print("\n" + "━" * 100)
        print(f"  CATEGORY: {cat}")
        print("━" * 100)

        # Which quarters have this category?
        quarters_with_cat = []
        for qname in quarter_names:
            if cat in quarters_data[qname].get("tables", {}):
                quarters_with_cat.append(qname)

        print(f"  Present in {len(quarters_with_cat)}/{len(quarter_names)} quarters: ", end="")
        if len(quarters_with_cat) <= 6:
            print(", ".join(quarters_with_cat))
        else:
            print(f"{quarters_with_cat[0]} ... {quarters_with_cat[-1]}")

        # Collect all unique field names and which quarters they appear in
        field_to_quarters = defaultdict(list)  # field_name -> [quarter_names]
        # Also track per-field, per-quarter data completeness
        field_quarter_stats = defaultdict(lambda: defaultdict(lambda: {"total": 0, "non_empty": 0, "empty": 0}))

        for qname in quarters_with_cat:
            table = quarters_data[qname]["tables"][cat]
            fields_list = table.get("fields", [])
            districts = table.get("districts", {})

            # Deduplicate fields list (some have repeated "None")
            seen_fields = set()
            unique_fields = []
            for f in fields_list:
                if f not in seen_fields:
                    seen_fields.add(f)
                    unique_fields.append(f)

            for field in unique_fields:
                field_to_quarters[field].append(qname)

                for dist_name, dist_data in districts.items():
                    val = dist_data.get(field, "")
                    field_quarter_stats[field][qname]["total"] += 1
                    if val is None or str(val).strip() == "" or str(val).strip() == "None" or str(val).strip() == "-":
                        field_quarter_stats[field][qname]["empty"] += 1
                    else:
                        field_quarter_stats[field][qname]["non_empty"] += 1

        all_fields = sorted(field_to_quarters.keys())
        print(f"  Total unique field names: {len(all_fields)}")

        # ── 1. Field names and their quarter coverage ──
        print(f"\n  {'Field Name':<60} {'Quarters':>10}")
        print(f"  {'─' * 60} {'─' * 10}")
        for field in all_fields:
            qcount = len(field_to_quarters[field])
            marker = ""
            if qcount < len(quarters_with_cat):
                marker = " ◄ NOT IN ALL"
            print(f"  {field:<60} {qcount:>4}/{len(quarters_with_cat)}{marker}")

        # ── 2. Detect spelling variations ──
        similar_groups = []
        used = set()
        for i, f1 in enumerate(all_fields):
            if f1 in used:
                continue
            group = [f1]
            for j, f2 in enumerate(all_fields):
                if j <= i or f2 in used:
                    continue
                if are_similar(f1, f2):
                    group.append(f2)
                    used.add(f2)
            if len(group) > 1:
                used.add(f1)
                similar_groups.append(group)

        if similar_groups:
            print(f"\n  *** SPELLING VARIATIONS DETECTED ({len(similar_groups)} groups) ***")
            for gi, group in enumerate(similar_groups, 1):
                print(f"\n  Group {gi}:")
                for field in group:
                    qs = field_to_quarters[field]
                    print(f"    \"{field}\"")
                    print(f"      in quarters: {', '.join(qs)}")
                global_spelling_issues.append((cat, group))
        else:
            print(f"\n  No spelling variations detected.")

        # ── 3. Data completeness per field ──
        print(f"\n  DATA COMPLETENESS (non-empty / total cells across all quarters):")
        print(f"  {'Field Name':<55} {'Non-Empty':>10} {'Total':>8} {'Fill%':>7}  Status")
        print(f"  {'─' * 55} {'─' * 10} {'─' * 8} {'─' * 7}  {'─' * 15}")

        for field in all_fields:
            total_cells = 0
            non_empty_cells = 0
            for qname in field_to_quarters[field]:
                stats = field_quarter_stats[field][qname]
                total_cells += stats["total"]
                non_empty_cells += stats["non_empty"]

            if total_cells == 0:
                pct = 0.0
            else:
                pct = (non_empty_cells / total_cells) * 100

            status = ""
            if pct == 0:
                status = "COMPLETELY EMPTY"
            elif pct < 20:
                status = ">80% EMPTY"
            elif pct < 50:
                status = "MOSTLY EMPTY"

            if pct < 20 and total_cells > 0:
                global_empty_fields.append((cat, field, non_empty_cells, total_cells, pct))

            print(f"  {field:<55} {non_empty_cells:>10} {total_cells:>8} {pct:>6.1f}%  {status}")

        # ── 4. Per-quarter breakdown for fields not present in all quarters ──
        partial_fields = [f for f in all_fields if len(field_to_quarters[f]) < len(quarters_with_cat)]
        if partial_fields:
            print(f"\n  FIELDS NOT PRESENT IN ALL QUARTERS:")
            for field in partial_fields:
                present = set(field_to_quarters[field])
                missing = [q for q in quarters_with_cat if q not in present]
                print(f"    \"{field}\"")
                print(f"      Missing from: {', '.join(missing)}")

        # Category summary
        total_all = sum(
            field_quarter_stats[f][q]["total"]
            for f in all_fields for q in field_to_quarters[f]
        )
        nonempty_all = sum(
            field_quarter_stats[f][q]["non_empty"]
            for f in all_fields for q in field_to_quarters[f]
        )
        fill_pct = (nonempty_all / total_all * 100) if total_all > 0 else 0
        global_category_summary.append((cat, len(all_fields), len(quarters_with_cat), len(similar_groups), fill_pct))

    # ══════════════════════════════════════════════════════════════
    # GLOBAL SUMMARY
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("  GLOBAL SUMMARY")
    print("=" * 100)

    # Category overview table
    print(f"\n  {'Category':<45} {'Fields':>7} {'Quarters':>9} {'Spell Issues':>13} {'Fill%':>7}")
    print(f"  {'─' * 45} {'─' * 7} {'─' * 9} {'─' * 13} {'─' * 7}")
    for cat, nfields, nquarters, nspelling, fillpct in sorted(global_category_summary, key=lambda x: x[0]):
        spell_flag = f"{nspelling} groups" if nspelling > 0 else "-"
        print(f"  {cat:<45} {nfields:>7} {nquarters:>9} {spell_flag:>13} {fillpct:>6.1f}%")

    # All spelling issues
    if global_spelling_issues:
        print(f"\n  === ALL SPELLING VARIATION ISSUES ({len(global_spelling_issues)} total) ===")
        for cat, group in global_spelling_issues:
            print(f"\n  [{cat}]")
            for field in group:
                print(f"    - \"{field}\"")
    else:
        print(f"\n  No spelling variation issues found across any category.")

    # All nearly-empty fields
    if global_empty_fields:
        print(f"\n  === FIELDS >80% EMPTY ({len(global_empty_fields)} total) ===")
        print(f"  {'Category':<40} {'Field':<45} {'Fill%':>7}")
        print(f"  {'─' * 40} {'─' * 45} {'─' * 7}")
        for cat, field, nonempty, total, pct in sorted(global_empty_fields, key=lambda x: x[4]):
            print(f"  {cat:<40} {field:<45} {pct:>6.1f}%")
    else:
        print(f"\n  No fields are >80% empty.")

    print("\n" + "=" * 100)
    print("  AUDIT COMPLETE")
    print("=" * 100)

if __name__ == "__main__":
    main()
