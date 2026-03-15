#!/usr/bin/env python3
"""
Comprehensive fuzzy field name deduplication across ALL 8 NE states' SLBC data.

Fixes near-duplicate field names caused by OCR artifacts, typos, spacing issues,
abbreviation differences, and minor wording changes.

Strategy:
  1. Deterministic normalization (fix known OCR patterns)
  2. Fuzzy matching within each category, using non-overlapping quarters as signal
  3. Pick canonical name (most-used variant), rename all others
  4. Merge data when fields collapse
  5. Regenerate CSVs and timeseries
"""

import json
import csv
import os
import re
from pathlib import Path
from collections import Counter, defaultdict
from difflib import SequenceMatcher

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


# ============================================================
# EXCLUSION RULES: pairs that should NEVER be merged
# ============================================================

def should_exclude_merge(a, b):
    """
    Return True if these two fields are genuinely different
    despite high string similarity.
    """
    al = a.lower()
    bl = b.lower()

    # Different scheme acronyms
    if ('pmjjby' in al) != ('pmjjby' in bl):
        return True
    if ('pmsby' in al) != ('pmsby' in bl):
        return True
    # NRLM vs NULM are different schemes
    if ('nrlm' in al) != ('nrlm' in bl):
        return True
    if ('nulm' in al) != ('nulm' in bl):
        return True

    # Different seasons
    if ('kharif' in al) != ('kharif' in bl):
        return True
    if ('rabi' in al) != ('rabi' in bl):
        return True

    # Different metrics: QoQ vs YoY
    if ('qoq' in al) != ('qoq' in bl):
        return True
    if ('yoy' in al) != ('yoy' in bl):
        return True

    # O/S vs NPA are different metrics
    if ('o/s' in al) != ('o/s' in bl):
        return True
    if ('npa' in al) != ('npa' in bl):
        return True

    # Disb vs Target are different
    if ('disb' in al) != ('disb' in bl):
        return True
    if ('target' in al) != ('target' in bl):
        return True

    # A/C vs Amt vs No. fields - these are DIFFERENT columns
    # The key issue: "Social Infrastructure" (no suffix) should NOT merge
    # with "Social Infrastructure A/C" or "Social Infrastructure Amt"
    a_suffix = get_field_suffix(al)
    b_suffix = get_field_suffix(bl)
    if a_suffix and b_suffix and a_suffix != b_suffix:
        # Both have clear suffixes but they differ -> different fields
        return True
    # If one has a suffix and the other doesn't, AND the one without suffix
    # is basically the same string minus the suffix, they're different fields
    # (e.g., "Social Infrastructure" vs "Social Infrastructure A/C")
    if a_suffix and not b_suffix:
        # a has a suffix, b doesn't -> likely different columns
        # Unless the suffix IS the differentiator (e.g., "Amt." vs "Amt")
        return True
    if b_suffix and not a_suffix:
        return True

    # Women PMJDY vs PMJDY
    if ('women' in al) != ('women' in bl):
        return True

    # AH (Animal Husbandry) prefix matters
    if al.startswith('ah ') != bl.startswith('ah '):
        return True

    # Total KCC vs Total AH KCC - different
    if ('ah kcc' in al) != ('ah kcc' in bl):
        return True

    # savings vs current accounts
    if ('savings' in al) != ('savings' in bl):
        return True
    if ('current account' in al) != ('current account' in bl):
        return True

    # NPS vs PS in category context
    # Check both with and without parens: "(NPS)" and "NPS" as standalone
    a_has_nps = '(nps)' in al or ' nps ' in al or al.endswith(' nps') or al.startswith('nps ')
    b_has_nps = '(nps)' in bl or ' nps ' in bl or bl.endswith(' nps') or bl.startswith('nps ')
    a_has_ps = '(ps)' in al or ' ps ' in al or al.endswith(' ps') or al.startswith('ps ')
    b_has_ps = '(ps)' in bl or ' ps ' in bl or bl.endswith(' ps') or bl.startswith('ps ')
    if a_has_nps != b_has_nps:
        if a_has_ps or b_has_ps:
            return True

    # "Number of" vs "Amount of" / "No. of" vs "Amountof" are different fields
    # These are count vs value columns in recovery_bakijai and similar
    a_is_count = bool(re.search(r'\b(number|no\.?\s*of|noof)\b', al))
    b_is_count = bool(re.search(r'\b(number|no\.?\s*of|noof)\b', al))
    a_is_amount = bool(re.search(r'\b(amount|amountof|amtof|amt\s*of)\b', al))
    b_is_amount = bool(re.search(r'\b(amount|amountof|amtof|amt\s*of)\b', bl))
    # If one starts with a count prefix and other with amount prefix, exclude
    a_starts_count = bool(re.match(r'(number|no\.?\s*of|noof)', al))
    b_starts_count = bool(re.match(r'(number|no\.?\s*of|noof)', bl))
    a_starts_amount = bool(re.match(r'(amount|amountof|amtof|amt\s*of)', al))
    b_starts_amount = bool(re.match(r'(amount|amountof|amtof|amt\s*of)', bl))
    if (a_starts_count and b_starts_amount) or (a_starts_amount and b_starts_count):
        return True

    # "Issued" vs not issued (New Issued vs just Issued could be different)
    # But "KCC Animal Husbandry Issued" vs "KCC Animal Husbandry New Issued" - be cautious

    # Different year references
    years_a = set(re.findall(r'20\d{2}(?:-\d{2})?', al))
    years_b = set(re.findall(r'20\d{2}(?:-\d{2})?', bl))
    if years_a and years_b and years_a != years_b:
        return True

    # Different date references (June vs Mar, etc.)
    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
              'january', 'february', 'march', 'april', 'june', 'july', 'august', 'september',
              'october', 'november', 'december']
    a_months = set(m for m in months if m in al)
    b_months = set(m for m in months if m in bl)
    if a_months and b_months and a_months != b_months:
        return True

    # "Total PS" vs "Total Ops" could be OCR, but careful
    # "Msme NPA Amt %" vs "Msme NPA Amt" - pct vs non-pct
    if (al.endswith('%') or 'amt %' in al or 'amt. %' in al) != \
       (bl.endswith('%') or 'amt %' in bl or 'amt. %' in bl):
        return True

    return False


def get_field_suffix(name_lower):
    """Extract the semantic suffix type: 'ac', 'amt', 'no', 'pct', or None."""
    s = name_lower.strip()

    # Percentage
    if s.endswith('%') or s.endswith('amt.%') or s.endswith('amt. %'):
        return 'pct'

    # Account/Number of accounts
    if s.endswith('a/c') or s.endswith('a/cc') or s.endswith('acc') or s.endswith('a/cs'):
        return 'ac'

    # "A/C No." is actually a count field
    if s.endswith('a/c no.') or s.endswith('a/c no'):
        return 'ac_no'

    # Amount
    if s.endswith('amt') or s.endswith('amt.') or s.endswith('amount'):
        return 'amt'

    # Number/count
    if s.endswith('no.') or s.endswith('no'):
        return 'no'

    return None


# ============================================================
# DETERMINISTIC NORMALIZATION (Pass 1)
# ============================================================

def normalize_deterministic(name):
    """
    Apply deterministic normalization rules to fix known OCR artifacts.
    """
    if not name or not isinstance(name, str):
        return name

    s = name.strip()

    # --- Fix OCR line-break artifacts ---
    # "Bene- ficiary" -> "Beneficiary"
    # "Self- Help" -> "Self-Help"
    # "Enrol- ment" -> "Enrolment"
    # "IC- Agri" -> "IC-Agri"
    # Pattern: word- word where the hyphen-space breaks a word
    # But keep real hyphens like "Semi-Urban"
    def fix_ocr_hyphen(m):
        before = m.group(1)
        after = m.group(2)
        # If the parts form a known compound, join them
        combined = before + after
        combined_hyph = before + '-' + after
        # Check common OCR breaks
        ocr_breaks = {
            'Bene ficiary': 'Beneficiary',
            'Enrol ment': 'Enrolment',
            'Enrol-ment': 'Enrolment',
        }
        test = before + ' ' + after
        if test in ocr_breaks:
            return ocr_breaks[test]
        # For "IC- Agri" -> "IC-Agri" (remove space after hyphen)
        return before + '-' + after

    s = re.sub(r'(\w+)-\s+(\w+)', fix_ocr_hyphen, s)

    # --- Fix missing spaces (OCR joining) ---
    # "Disbursedunder" -> "Disbursed under"
    # "Forestryandwasteland" -> "Forestryandwasteland" (keep as-is, will be matched fuzzy)
    # "CropProduction" -> "Crop Production"
    # "WaterResources" -> "Water Resources"
    # "Farmmechanization" -> "Farm mechanization"
    # But be careful: "PMJDY" should not become "P M J D Y"
    known_joins = {
        'Disbursedunder': 'Disbursed under',
        'CropProduction': 'Crop Production',
        'WaterResources': 'Water Resources',
        'Farmmechanization': 'Farm Mechanization',
        'Forestryandwasteland': 'Forestry And Wasteland',
        'IrregularA/C': 'Irregular A/C',
        'Loansunder': 'Loans under',
        'Numberof': 'Number of',
        'Aadhaarseeded': 'Aadhaar Seeded',
        'Coveredby': 'Covered by',
        'enabledbankingoutlet': 'enabled banking outlet',
        'eligiblecasesunder': 'eligible cases under',
        'eligiblecasesunderPMJJBY': 'eligible cases under PMJJBY',
        'Priorityrityrityrity': 'Priority',
    }
    for joined, fixed in known_joins.items():
        s = s.replace(joined, fixed)

    # --- Fix common typos ---
    typo_fixes = {
        'Begining': 'Beginning',
        'Husbandary': 'Husbandry',
        'Casses': 'Cases',
        'Overal ': 'Overall ',
        'Infrastructur ': 'Infrastructure ',
        'Infrastructur$': 'Infrastructure',
        'coverag': 'coverage',
        'Oustanding': 'Outstanding',
        'Chriatian': 'Christian',
        'Christi Ans': 'Christians',
        'Budhist': 'Buddhist',
        'Zorastrian': 'Zoroastrian',
        'Zorastrians': 'Zoroastrians',
        'emplyd': 'Employed',
        'Barod a': 'Baroda',
        'Buddhist S ': 'Buddhists ',
        'Zorastrian S ': 'Zoroastrians ',
        'Nrl M ': 'NRLM ',
        'Pmeg P ': 'PMEGP ',
        'BHIM/Up I': 'BHIM/UPI',
        'B/C ': 'BC ',
        'A/Cp ': 'Acp ',
        'A/Cc': 'A/C',
    }
    for typo, fix in typo_fixes.items():
        if typo.endswith('$'):
            # End-of-string match
            pattern = typo[:-1]
            if s.endswith(pattern):
                s = s[:-len(pattern)] + fix
        else:
            s = s.replace(typo, fix)

    # --- Fix Os -> O/S (outstanding) ---
    # "NRLM Os No." -> "NRLM O/S No."
    # But don't change "Zorastrians"
    s = re.sub(r'\bOs\b', 'O/S', s)
    s = re.sub(r'\bos\b', 'O/S', s)

    # --- Fix amt variants ---
    s = re.sub(r'\bOs AMT\b', 'O/S Amt', s)
    s = re.sub(r'\bos amt\b', 'O/S Amt', s)
    s = re.sub(r'\bos Amt\b', 'O/S Amt', s)
    s = re.sub(r'\bos no\b', 'O/S No.', s)
    s = re.sub(r'\bos No\.\b', 'O/S No.', s)

    # --- Fix "Amt.%" -> "Amt. %" (add space) ---
    s = s.replace('Amt.%', 'Amt. %')

    # --- Fix "No of" -> "No. of" ---
    s = re.sub(r'\bNo of\b', 'No. of', s)

    # --- Fix "Amt Deposits" -> "Amt. Deposits" ---
    s = re.sub(r'\bAmt Deposits\b', 'Amt. Deposits', s)

    # --- Fix "Amt." at end -> "Amt" (but keep "Amt. %" and "Amt. Deposits") ---
    if s.endswith('Amt.') and not s.endswith('Amt. %'):
        s = s[:-1]

    # --- Normalize multiple spaces ---
    s = re.sub(r'\s+', ' ', s).strip()

    # --- Fix "Sishu" casing (sometimes "sishu") ---
    s = re.sub(r'\bsishu\b', 'Sishu', s, flags=re.IGNORECASE)
    s = re.sub(r'\bkishore\b', 'Kishore', s, flags=re.IGNORECASE)
    s = re.sub(r'\btarun\b', 'Tarun', s, flags=re.IGNORECASE)

    # --- Fix spacing difference in "(Rs. in Lakhs)" ---
    s = re.sub(r'\(Rs\.\s*in\s*Lakhs\)', '(Rs. in Lakhs)', s)
    # Fix "(Since Inception) (Rs." vs "(Since Inception)(Rs."
    s = s.replace(')(Rs.', ') (Rs.')

    return s


# ============================================================
# FUZZY MATCHING (Pass 2)
# ============================================================

def normalize_for_comparison(name):
    """
    Aggressively normalize a field name for fuzzy comparison purposes.
    This is NOT the final name - just used to detect similar pairs.
    """
    s = name.lower().strip()
    # Remove all punctuation except meaningful ones
    s = re.sub(r'[.,;:!?]', '', s)
    # Collapse spaces
    s = re.sub(r'\s+', ' ', s)
    # Normalize separators
    s = s.replace('-', ' ').replace('_', ' ')
    # Remove articles
    s = s.replace(' the ', ' ').replace(' of ', ' ').replace(' in ', ' ')
    return s.strip()


def fuzzy_ratio(a, b):
    """Compute similarity ratio between two field names."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def build_fuzzy_mapping(cat_fields, cat_name):
    """
    For a single category, build a mapping from variant field names to canonical names.

    cat_fields: dict of {field_name: set_of_quarters}
    Returns: dict of {variant_name: canonical_name}
    """
    fields = list(cat_fields.keys())
    if len(fields) <= 1:
        return {}

    # Build groups of similar fields
    # Use Union-Find to group transitively similar fields
    parent = {f: f for f in fields}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(len(fields)):
        for j in range(i + 1, len(fields)):
            a, b = fields[i], fields[j]
            ratio = fuzzy_ratio(a, b)
            if ratio > 0.88:
                qa = cat_fields[a]
                qb = cat_fields[b]
                overlap = qa & qb

                # Key insight: if two similar fields NEVER appear in the same quarter,
                # they're likely the same field with different spellings.
                # If they DO appear together, they're genuinely different fields.
                if len(overlap) > 0:
                    continue

                # Check exclusion rules
                if should_exclude_merge(a, b):
                    continue

                union(a, b)

    # Collect groups
    groups = defaultdict(list)
    for f in fields:
        groups[find(f)].append(f)

    # Build mapping
    mapping = {}
    for root, members in groups.items():
        if len(members) <= 1:
            continue

        # Pick canonical: the one used in most quarters
        members_with_counts = [(m, len(cat_fields[m])) for m in members]
        members_with_counts.sort(key=lambda x: (-x[1], x[0]))
        canonical = members_with_counts[0][0]

        for m, _ in members_with_counts:
            if m != canonical:
                mapping[m] = canonical

    return mapping


# ============================================================
# PROCESSING
# ============================================================

def process_state(state_dir_name):
    """Process one state: normalize fields, apply fuzzy dedup, regenerate."""
    slug = STATE_SLUGS[state_dir_name]
    state_dir = BASE / state_dir_name
    json_path = state_dir / f"{slug}_complete.json"

    if not json_path.exists():
        print(f"  SKIP: {json_path} not found")
        return {}

    with open(json_path) as f:
        data = json.load(f)

    quarters = data.get("quarters", {})
    stats = {
        "deterministic_renames": 0,
        "fuzzy_merges": 0,
        "categories_affected": set(),
        "merge_details": [],
    }

    # ===== PASS 1: Deterministic normalization =====
    for qname, quarter in quarters.items():
        for tname, table in quarter.get("tables", {}).items():
            raw_fields = table.get("fields", [])
            new_fields = []
            seen = set()
            for f in raw_fields:
                nf = normalize_deterministic(f)
                if nf not in seen:
                    new_fields.append(nf)
                    seen.add(nf)
                if nf != f:
                    stats["deterministic_renames"] += 1

            # Rename district data
            districts = table.get("districts", {})
            for dist_name, dist_data in list(districts.items()):
                new_data = {}
                for raw_f in list(dist_data.keys()):
                    norm_f = normalize_deterministic(raw_f)
                    val = dist_data[raw_f]
                    if norm_f in new_data:
                        existing = new_data[norm_f]
                        if (existing is None or existing == "" or existing == "0") and val and val != "" and val != "0":
                            new_data[norm_f] = val
                    else:
                        new_data[norm_f] = val
                districts[dist_name] = new_data

            table["fields"] = new_fields
            table["districts"] = districts

    # ===== PASS 2: Fuzzy cross-quarter deduplication =====
    # For each category, collect all field names across all quarters
    cat_field_quarters = defaultdict(lambda: defaultdict(set))
    for qname, quarter in quarters.items():
        for tname, table in quarter.get("tables", {}).items():
            for f in table.get("fields", []):
                cat_field_quarters[tname][f].add(qname)

    # Build fuzzy mapping per category
    all_mappings = {}  # (category, old_name) -> canonical_name
    for tname in sorted(cat_field_quarters.keys()):
        mapping = build_fuzzy_mapping(cat_field_quarters[tname], tname)
        for old_name, canonical in mapping.items():
            all_mappings[(tname, old_name)] = canonical
            stats["fuzzy_merges"] += 1
            stats["categories_affected"].add(tname)
            old_quarters = len(cat_field_quarters[tname][old_name])
            can_quarters = len(cat_field_quarters[tname][canonical])
            stats["merge_details"].append(
                f"  {tname}: [{old_name}]({old_quarters}q) -> [{canonical}]({can_quarters}q)"
            )

    # Apply fuzzy mapping
    for qname, quarter in quarters.items():
        for tname, table in quarter.get("tables", {}).items():
            raw_fields = table.get("fields", [])
            new_fields = []
            seen = set()
            for f in raw_fields:
                canonical = all_mappings.get((tname, f), f)
                if canonical not in seen:
                    new_fields.append(canonical)
                    seen.add(canonical)

            # Rename in districts
            districts = table.get("districts", {})
            for dist_name, dist_data in list(districts.items()):
                new_data = {}
                for old_f in list(dist_data.keys()):
                    canonical = all_mappings.get((tname, old_f), old_f)
                    val = dist_data[old_f]
                    if canonical in new_data:
                        existing = new_data[canonical]
                        if (existing is None or existing == "" or existing == "0") and val and val != "" and val != "0":
                            new_data[canonical] = val
                    else:
                        new_data[canonical] = val
                districts[dist_name] = new_data

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
    """Normalize a timeseries column key."""
    key = re.sub(r'\.+$', '', key)
    key = re.sub(r'_ac$', '_a/c', key)
    key = re.sub(r'_acs$', '_a/c', key)
    key = re.sub(r'_a/cs$', '_a/c', key)
    key = re.sub(r'_amount$', '_amt', key)
    key = re.sub(r'_amt\.$', '_amt', key)
    key = re.sub(r'_nos?\.?s?\.?$', '_no.', key)
    key = re.sub(r'_no\.s$', '_no.', key)
    if key.endswith('_no'):
        key = key + '.'
    key = re.sub(r'semi[\s_-]+urban', 'semi-urban', key)
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
    key = re.sub(r'_br\(s\)', '_br', key)
    key = re.sub(r'_br\.$', '_br', key)
    key = re.sub(r'renew-?\s*able', 'renewable', key)
    key = re.sub(r'_+', '_', key)
    key = key.strip('_')
    return key


def regenerate_timeseries(data, state_dir, state_slug):
    """Regenerate timeseries CSV and JSON from normalized data."""
    all_records = []
    all_field_keys = set()

    quarters = data.get("quarters", {})

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


def verify_no_remaining_fuzzy_dupes(state_dir_name):
    """Check for remaining non-overlapping fuzzy pairs after dedup."""
    slug = STATE_SLUGS[state_dir_name]
    json_path = BASE / state_dir_name / f"{slug}_complete.json"
    if not json_path.exists():
        return []

    with open(json_path) as f:
        data = json.load(f)

    cat_fields = defaultdict(lambda: defaultdict(set))
    for qk, q in data.get("quarters", {}).items():
        for cat, table in q.get("tables", {}).items():
            for f in table.get("fields", []):
                cat_fields[cat][f].add(qk)

    remaining = []
    for cat in sorted(cat_fields.keys()):
        fields = list(cat_fields[cat].keys())
        for i in range(len(fields)):
            for j in range(i + 1, len(fields)):
                a, b = fields[i], fields[j]
                ratio = fuzzy_ratio(a, b)
                if ratio > 0.88:
                    qa = cat_fields[cat][a]
                    qb = cat_fields[cat][b]
                    overlap = qa & qb
                    if len(overlap) == 0 and not should_exclude_merge(a, b):
                        remaining.append((cat, a, len(qa), b, len(qb), ratio))

    return remaining


def main():
    print("=" * 70)
    print("FUZZY FIELD NAME DEDUPLICATION — ALL 8 NE STATES")
    print("=" * 70)

    # Record BEFORE counts
    print("\n--- BEFORE: Timeseries column counts ---")
    before_counts = {}
    for state in STATES:
        count = count_timeseries_columns(state)
        before_counts[state] = count
        print(f"  {state}: {count} columns")

    # Process each state
    for state in STATES:
        print(f"\n{'=' * 50}")
        print(f"Processing: {state}")
        print(f"{'=' * 50}")
        stats = process_state(state)
        if stats:
            print(f"  Deterministic renames: {stats.get('deterministic_renames', 0)}")
            print(f"  Fuzzy merges: {stats.get('fuzzy_merges', 0)}")
            print(f"  Categories affected: {stats.get('categories_affected', 0)}")
            if stats.get('merge_details'):
                print(f"  Merge details:")
                for detail in stats['merge_details']:
                    print(detail)

    # Record AFTER counts
    print(f"\n\n{'=' * 70}")
    print("RESULTS — TIMESERIES COLUMN COUNTS")
    print(f"{'=' * 70}")

    print(f"\n{'State':<25} {'Before':>8} {'After':>8} {'Reduced':>8}")
    print(f"{'-' * 25} {'-' * 8} {'-' * 8} {'-' * 8}")
    total_before = 0
    total_after = 0
    for state in STATES:
        after = count_timeseries_columns(state)
        before = before_counts[state]
        reduced = before - after
        total_before += before
        total_after += after
        marker = " ***" if reduced > 0 else ""
        print(f"{state:<25} {before:>8} {after:>8} {reduced:>8}{marker}")
    print(f"{'-' * 25} {'-' * 8} {'-' * 8} {'-' * 8}")
    print(f"{'TOTAL':<25} {total_before:>8} {total_after:>8} {total_before - total_after:>8}")

    # Verify no remaining fuzzy dupes
    print(f"\n\n{'=' * 70}")
    print("VERIFICATION — Remaining non-overlapping fuzzy pairs")
    print(f"{'=' * 70}")
    any_remaining = False
    for state in STATES:
        remaining = verify_no_remaining_fuzzy_dupes(state)
        if remaining:
            any_remaining = True
            print(f"\n  {state}: {len(remaining)} remaining pairs")
            for cat, a, qa, b, qb, ratio in remaining[:20]:
                print(f"    {cat}: [{a}]({qa}q) vs [{b}]({qb}q) ratio={ratio:.3f}")
            if len(remaining) > 20:
                print(f"    ... and {len(remaining) - 20} more")
        else:
            print(f"  {state}: CLEAN")

    # Check for duplicate timeseries columns
    print(f"\n\n{'=' * 70}")
    print("VERIFICATION — Duplicate columns in timeseries CSV")
    print(f"{'=' * 70}")
    for state in STATES:
        slug = STATE_SLUGS[state]
        csv_path = BASE / state / f"{slug}_fi_timeseries.csv"
        if not csv_path.exists():
            print(f"  {state}: No CSV")
            continue
        with open(csv_path) as f:
            header = next(csv.reader(f))
        counts = Counter(header)
        dups = [(col, cnt) for col, cnt in counts.items() if cnt > 1]
        if dups:
            print(f"  {state}: {len(dups)} duplicate columns")
            for col, cnt in dups[:10]:
                print(f"    {col} x{cnt}")
        else:
            print(f"  {state}: CLEAN")

    print(f"\n{'=' * 70}")
    print("DONE")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
