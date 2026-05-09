#!/usr/bin/env python3
"""
Audit field name consistency across 10 states in Project FINER.
Reads all {state}_complete.json files and reports:
  a) All categories per state (sorted)
  b) Field names per state for key categories
  c) Field names appearing in only 1-2 states (non-standardized)
  d) Categories appearing in only 1-2 states
"""

import json
import os
from collections import defaultdict

BASE = "/Users/abhinav/Downloads/projectfiner/public/slbc-data"
STATES = [
    "assam", "meghalaya", "manipur", "arunachal-pradesh",
    "mizoram", "tripura", "nagaland", "sikkim", "bihar", "west-bengal"
]

KEY_CATEGORIES = [
    "credit_deposit_ratio", "branch_network", "kcc", "pmjdy",
    "shg", "digital_transactions", "aadhaar_authentication"
]

# Also check variants of key categories
KEY_CATEGORY_VARIANTS = {
    "kcc": ["kcc", "fi_kcc", "kcc_outstanding", "kcc_animal_husbandry", "kcc_fishery"],
    "shg": ["shg", "shg_nrlm", "nrlm", "shg_p2", "shg_p3"],
    "pmjdy": ["pmjdy", "pmjdy_2", "pmjdy_3", "pmjdy_p2", "pmjdy_p3", "pmjdy_p4"],
    "branch_network": ["branch_network", "branch_network_p2"],
    "social_security": ["social_security", "social_security_schemes"],
}


def load_state_data(state):
    path = os.path.join(BASE, state, f"{state}_complete.json")
    with open(path) as f:
        return json.load(f)


def main():
    # Collect data
    state_data = {}
    state_categories = {}  # state -> set of category names
    state_fields = {}      # state -> { category -> set of field names }
    category_states = defaultdict(set)   # category -> set of states that have it
    category_fields = defaultdict(lambda: defaultdict(set))  # category -> state -> set of fields
    all_fields_global = defaultdict(set)  # field_name -> set of states

    for state in STATES:
        try:
            data = load_state_data(state)
        except FileNotFoundError:
            print(f"WARNING: {state}_complete.json not found, skipping")
            continue

        state_data[state] = data
        cats = set()
        fields_by_cat = defaultdict(set)

        quarters = data.get("quarters", {})
        for qk, qv in quarters.items():
            tables = qv.get("tables", {})
            for cat_name, cat_data in tables.items():
                cats.add(cat_name)
                category_states[cat_name].add(state)
                flds = cat_data.get("fields", [])
                # Exclude "District" as it's always present
                flds_clean = [f for f in flds if f.lower() != "district"]
                for f in flds_clean:
                    fields_by_cat[cat_name].add(f)
                    category_fields[cat_name][state].add(f)
                    all_fields_global[f].add(state)

        state_categories[state] = cats
        state_fields[state] = fields_by_cat

    # =========================================================
    # REPORT
    # =========================================================
    separator = "=" * 80

    # --- (a) All categories per state ---
    print(separator)
    print("SECTION A: ALL CATEGORIES PER STATE")
    print(separator)
    for state in STATES:
        if state not in state_categories:
            continue
        cats = sorted(state_categories[state])
        print(f"\n{state.upper()} ({len(cats)} categories):")
        for c in cats:
            print(f"  - {c}")

    # Summary: all unique categories across all states
    all_cats = set()
    for s in state_categories.values():
        all_cats |= s
    print(f"\n{separator}")
    print(f"TOTAL UNIQUE CATEGORIES ACROSS ALL STATES: {len(all_cats)}")
    print(separator)
    for c in sorted(all_cats):
        states_with = sorted(category_states[c])
        print(f"  {c:50s} [{len(states_with)} states] {', '.join(states_with)}")

    # --- (b) Field names per state for key categories ---
    print(f"\n{separator}")
    print("SECTION B: FIELD NAMES PER STATE FOR KEY CATEGORIES")
    print(separator)

    for key_cat in KEY_CATEGORIES:
        print(f"\n{'─' * 70}")
        print(f"CATEGORY: {key_cat}")
        print(f"{'─' * 70}")

        # Check variants too
        variants = KEY_CATEGORY_VARIANTS.get(key_cat, [key_cat])

        for state in STATES:
            if state not in state_fields:
                continue

            # Find which variant(s) this state has
            found_cats = []
            for v in variants:
                if v in state_fields[state]:
                    found_cats.append(v)

            # Also check exact key_cat
            if key_cat in state_fields[state] and key_cat not in found_cats:
                found_cats.insert(0, key_cat)

            if not found_cats:
                print(f"\n  {state.upper()}: ** NOT FOUND ** (checked: {', '.join(variants)})")
            else:
                for fc in found_cats:
                    fields = sorted(state_fields[state][fc])
                    print(f"\n  {state.upper()} [{fc}] ({len(fields)} fields):")
                    for f in fields:
                        print(f"    - {f}")

    # --- (c) Field names appearing in only 1-2 states ---
    print(f"\n{separator}")
    print("SECTION C: FIELD NAMES APPEARING IN ONLY 1-2 STATES (LIKELY NON-STANDARDIZED)")
    print(separator)

    # Focus on key categories
    for key_cat in KEY_CATEGORIES:
        variants = KEY_CATEGORY_VARIANTS.get(key_cat, [key_cat])

        # Collect all fields across variants for this key category
        field_to_states = defaultdict(set)
        for state in STATES:
            if state not in state_fields:
                continue
            for v in variants:
                if v in state_fields[state]:
                    for f in state_fields[state][v]:
                        field_to_states[f].add(state)

        rare_fields = {f: ss for f, ss in field_to_states.items() if len(ss) <= 2}
        if rare_fields:
            print(f"\n  {key_cat} (and variants {variants}):")
            for f in sorted(rare_fields.keys()):
                ss = sorted(rare_fields[f])
                print(f"    {f:60s} -> {', '.join(ss)}")

    # Also do a global scan across ALL categories
    print(f"\n{'─' * 70}")
    print("GLOBAL: Fields appearing in only 1 state (across all categories):")
    print(f"{'─' * 70}")
    single_state_fields = {f: list(ss)[0] for f, ss in all_fields_global.items() if len(ss) == 1}
    # Group by state
    by_state = defaultdict(list)
    for f, s in single_state_fields.items():
        by_state[s].append(f)
    for state in STATES:
        if state in by_state:
            fields = sorted(by_state[state])
            print(f"\n  {state.upper()} ({len(fields)} unique-to-state fields):")
            for f in fields[:30]:  # Cap at 30 to avoid overwhelming output
                print(f"    - {f}")
            if len(fields) > 30:
                print(f"    ... and {len(fields) - 30} more")

    # --- (d) Categories appearing in only 1-2 states ---
    print(f"\n{separator}")
    print("SECTION D: CATEGORIES APPEARING IN ONLY 1-2 STATES")
    print(separator)
    rare_cats = {c: sorted(ss) for c, ss in category_states.items() if len(ss) <= 2}
    for c in sorted(rare_cats.keys()):
        print(f"  {c:50s} -> {', '.join(rare_cats[c])}")

    # --- Bonus: Potential category duplicates ---
    print(f"\n{separator}")
    print("SECTION E: POTENTIAL CATEGORY NAME INCONSISTENCIES")
    print(separator)
    print("\nCategories that look like variants of each other:")

    cat_list = sorted(all_cats)
    reported = set()
    for i, c1 in enumerate(cat_list):
        for c2 in cat_list[i+1:]:
            # Check if one is a prefix/suffix variant of the other
            c1_parts = set(c1.split("_"))
            c2_parts = set(c2.split("_"))
            overlap = c1_parts & c2_parts
            union = c1_parts | c2_parts
            if len(overlap) >= 2 and len(overlap) / len(union) > 0.5:
                key = tuple(sorted([c1, c2]))
                if key not in reported:
                    reported.add(key)
                    s1 = sorted(category_states[c1])
                    s2 = sorted(category_states[c2])
                    print(f"\n  '{c1}' [{len(s1)} states: {', '.join(s1)}]")
                    print(f"  '{c2}' [{len(s2)} states: {', '.join(s2)}]")

    # --- Bonus: Cross-state field comparison for key categories ---
    print(f"\n{separator}")
    print("SECTION F: CROSS-STATE FIELD COMPARISON FOR KEY CATEGORIES")
    print(separator)
    print("(Fields present in ALL states vs fields missing from some states)\n")

    for key_cat in KEY_CATEGORIES:
        variants = KEY_CATEGORY_VARIANTS.get(key_cat, [key_cat])

        # Collect fields per state (merging variants)
        state_field_sets = {}
        for state in STATES:
            if state not in state_fields:
                continue
            merged = set()
            for v in variants:
                if v in state_fields[state]:
                    merged |= state_fields[state][v]
            if merged:
                state_field_sets[state] = merged

        if not state_field_sets:
            continue

        all_f = set()
        for fs in state_field_sets.values():
            all_f |= fs

        n_states_with_cat = len(state_field_sets)

        # Common fields (in all states that have this category)
        common = set.intersection(*state_field_sets.values()) if state_field_sets else set()

        print(f"\n{'─' * 70}")
        print(f"{key_cat} — {n_states_with_cat} states have this category, {len(all_f)} total unique fields")
        print(f"{'─' * 70}")

        if common:
            print(f"  Fields in ALL {n_states_with_cat} states:")
            for f in sorted(common):
                print(f"    - {f}")

        # Fields not in all states
        partial = all_f - common
        if partial:
            print(f"\n  Fields NOT in all states:")
            for f in sorted(partial):
                has_states = sorted([s for s, fs in state_field_sets.items() if f in fs])
                missing = sorted(set(state_field_sets.keys()) - set(has_states))
                print(f"    {f:55s} IN: {', '.join(has_states)}")
                if len(missing) <= 4:
                    print(f"    {'':55s} MISSING: {', '.join(missing)}")


if __name__ == "__main__":
    main()
