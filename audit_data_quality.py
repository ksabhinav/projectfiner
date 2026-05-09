#!/usr/bin/env python3
"""
Project FINER — SLBC Data Quality Audit
Checks for missing data, garbled values, inconsistencies across 10 states.
"""

import json
import os
import re
from collections import defaultdict

BASE = "/Users/abhinav/Downloads/projectfiner/public/slbc-data"
STATES = [
    "assam", "meghalaya", "manipur", "arunachal-pradesh",
    "mizoram", "tripura", "nagaland", "sikkim", "bihar", "west-bengal"
]

# Known districts per state (for garbled district detection)
KNOWN_DISTRICTS = {
    "assam": {"Baksa","Barpeta","Bongaigaon","Cachar","Darrang","Dhemaji","Dhubri","Dibrugarh",
              "Goalpara","Golaghat","Hailakandi","Jorhat","Kamrup","Kamrup Metro","Karbi Anglong",
              "Karimganj","Kokrajhar","Lakhimpur","Morigaon","Nagaon","Nalbari","Dima Hasao",
              "Sivasagar","Sonitpur","Tinsukia","Udalguri","Chirang","Biswanath","Charaideo",
              "Hojai","Majuli","South Salmara Mankachar","West Karbi Anglong","Bajali",
              "Tamulpur","Darrang"},
    "meghalaya": {"East Garo Hills","East Jaintia Hills","East Khasi Hills","North Garo Hills",
                  "Ri Bhoi","South Garo Hills","South West Garo Hills","South West Khasi Hills",
                  "West Garo Hills","West Jaintia Hills","West Khasi Hills","Eastern West Khasi Hills"},
    "manipur": {"Bishnupur","Chandel","Churachandpur","Imphal East","Imphal West","Jiribam",
                "Kakching","Kamjong","Kangpokpi","Noney","Pherzawl","Senapati","Tamenglong",
                "Tengnoupal","Thoubal","Ukhrul"},
    "arunachal-pradesh": {"Anjaw","Changlang","Dibang Valley","East Kameng","East Siang",
                          "Kamle","Kra Daadi","Kurung Kumey","Lepa Rada","Lohit","Longding",
                          "Lower Dibang Valley","Lower Siang","Lower Subansiri","Namsai",
                          "Pakke Kessang","Papum Pare","Shi Yomi","Siang","Tawang",
                          "Tirap","Upper Siang","Upper Subansiri","West Kameng","West Siang",
                          "Capital Complex","Keyi Panyor"},
    "mizoram": {"Aizawl","Champhai","Hnahthial","Khawzawl","Kolasib","Lawngtlai","Lunglei",
                "Mamit","Saitual","Saiha","Serchhip"},
    "tripura": {"Dhalai","Gomati","Khowai","North Tripura","Sepahijala","South Tripura",
                "Unakoti","West Tripura"},
    "nagaland": {"Chümoukedima","Dimapur","Kiphire","Kohima","Longleng","Mokokchung","Mon",
                 "Niuland","Noklak","Peren","Phek","Shamator","Tseminyü","Tuensang",
                 "Wokha","Zunheboto"},
    "sikkim": {"East Sikkim","North Sikkim","South Sikkim","West Sikkim",
               "Gangtok","Mangan","Namchi","Gyalshing","Pakyong","Soreng"},
    "bihar": {"Araria","Arwal","Aurangabad","Banka","Begusarai","Bhagalpur","Bhojpur","Buxar",
              "Darbhanga","Gaya","Gopalganj","Jamui","Jehanabad","Kaimur","Katihar","Khagaria",
              "Kishanganj","Lakhisarai","Madhepura","Madhubani","Munger","Muzaffarpur","Nalanda",
              "Nawada","Purbi Champaran","Pashchimi Champaran","Patna","Purnia","Rohtas",
              "Saharsa","Samastipur","Saran","Sheikhpura","Sheohar","Sitamarhi","Siwan",
              "Supaul","Vaishali"},
    "west-bengal": {"Alipurduar","Bankura","Birbhum","Cooch Behar","Dakshin Dinajpur","Darjeeling",
                    "Hooghly","Howrah","Jalpaiguri","Jhargram","Kalimpong","Kolkata","Malda",
                    "Murshidabad","Nadia","North 24 Parganas","Paschim Bardhaman","Paschim Medinipur",
                    "Purba Bardhaman","Purba Medinipur","Purulia","South 24 Parganas","Uttar Dinajpur"},
}


def parse_quarter_key(qk):
    """Convert quarter key to (year, month_num) for sorting. Handles both formats."""
    # Format: YYYY-MM
    m = re.match(r'^(\d{4})-(\d{2})$', qk)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    # Format: month_year (e.g. june_2020, sept_2025, december_2015)
    month_map = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'sept': 9, 'october': 10, 'november': 11, 'december': 12
    }
    parts = qk.split('_')
    if len(parts) >= 2:
        month_str = parts[0].lower()
        year_str = parts[-1]
        if month_str in month_map and year_str.isdigit():
            return (int(year_str), month_map[month_str])
    return (9999, 0)  # unknown


def is_garbled_value(val):
    """Check if a string value looks garbled."""
    if not isinstance(val, str) or val == "":
        return False
    # Contains unusual Unicode chars (not ASCII printable, not common Indian chars)
    if re.search(r'[\x00-\x08\x0e-\x1f\x7f-\x9f]', val):
        return True
    # Very long non-numeric string (>100 chars)
    stripped = val.replace(',', '').replace('.', '').replace('-', '').replace(' ', '')
    if len(val) > 100 and not stripped.replace('_', '').isdigit():
        return True
    return False


def is_garbled_field(name):
    """Check if a field name looks garbled."""
    issues = []
    # Numbers concatenated in weird ways (like rural_a_c_31_57_805)
    if re.search(r'_\d+_\d+_\d+', name):
        issues.append("has concatenated numbers")
    # Unusually long
    if len(name) > 50:
        issues.append(f"very long ({len(name)} chars)")
    # Excessive underscores (more than 8)
    if name.count('_') > 8:
        issues.append(f"excessive underscores ({name.count('_')})")
    return issues


def is_garbled_district(name, state):
    """Check if a district name looks wrong."""
    issues = []
    # Contains numbers (except known cases like "North 24 Parganas")
    if re.search(r'\d', name) and name not in KNOWN_DISTRICTS.get(state, set()):
        issues.append("contains numbers")
    # Contains special chars beyond basic punctuation
    if re.search(r'[<>\[\]{}|\\^~`@#$%&*+=]', name):
        issues.append("contains special characters")
    # Very short (likely parsing artifact)
    if len(name) <= 2:
        issues.append("very short name")
    # Very long
    if len(name) > 40:
        issues.append(f"very long ({len(name)} chars)")
    # All caps or all lower (unusual for proper nouns) — only flag if >5 chars
    if len(name) > 5 and (name == name.upper() or name == name.lower()):
        issues.append("unusual casing")
    return issues


def check_suspicious_number(val_str):
    """Check if a numeric value is suspicious."""
    if not isinstance(val_str, str):
        return None
    # Try parsing as number
    cleaned = val_str.replace(',', '').strip()
    try:
        num = float(cleaned)
        if num < -1e8:
            return f"extremely negative: {val_str}"
        if num > 1e12:
            return f"extremely large: {val_str}"
    except ValueError:
        pass
    return None


def main():
    print("=" * 80)
    print("PROJECT FINER — SLBC DATA QUALITY AUDIT")
    print("=" * 80)

    all_state_data = {}
    missing_files = []

    # Load all data
    for state in STATES:
        path = os.path.join(BASE, state, f"{state}_complete.json")
        if not os.path.exists(path):
            missing_files.append(state)
            continue
        with open(path) as f:
            all_state_data[state] = json.load(f)

    if missing_files:
        print(f"\n!!! MISSING FILES: {missing_files}")

    # =========================================================================
    # 1. QUARTER COVERAGE
    # =========================================================================
    print("\n" + "=" * 80)
    print("1. QUARTER COVERAGE")
    print("=" * 80)

    for state in STATES:
        if state not in all_state_data:
            continue
        data = all_state_data[state]
        quarters = list(data.get("quarters", {}).keys())
        parsed = [(qk, parse_quarter_key(qk)) for qk in quarters]
        parsed.sort(key=lambda x: x[1])

        print(f"\n  {state.upper()} — {len(quarters)} quarters")
        if parsed:
            print(f"    Range: {parsed[0][0]} to {parsed[-1][0]}")

        # Detect gaps: check for missing quarters in the sequence
        sorted_ym = [p[1] for p in parsed]
        gaps = []
        for i in range(1, len(sorted_ym)):
            y1, m1 = sorted_ym[i - 1]
            y2, m2 = sorted_ym[i]
            # Calculate months between
            months_diff = (y2 - y1) * 12 + (m2 - m1)
            if months_diff > 4:  # more than one quarter gap
                gaps.append(f"{parsed[i-1][0]} -> {parsed[i][0]} (gap of ~{months_diff} months)")

        if gaps:
            print(f"    GAPS DETECTED:")
            for g in gaps:
                print(f"      - {g}")
        else:
            print(f"    No significant gaps detected")

    # =========================================================================
    # 2. CATEGORY COVERAGE PER QUARTER
    # =========================================================================
    print("\n" + "=" * 80)
    print("2. CATEGORY COVERAGE PER QUARTER")
    print("=" * 80)

    for state in STATES:
        if state not in all_state_data:
            continue
        data = all_state_data[state]
        quarters = data.get("quarters", {})

        print(f"\n  {state.upper()}")
        low_cat_quarters = []
        cat_counts = []

        parsed_quarters = sorted(quarters.keys(), key=lambda qk: parse_quarter_key(qk))
        for qk in parsed_quarters:
            qdata = quarters[qk]
            tables = qdata.get("tables", {})
            n_cats = len(tables)
            cat_counts.append(n_cats)
            if n_cats < 10:
                low_cat_quarters.append((qk, n_cats))

        if cat_counts:
            avg = sum(cat_counts) / len(cat_counts)
            print(f"    Category count range: {min(cat_counts)} - {max(cat_counts)} (avg: {avg:.1f})")

        if low_cat_quarters:
            print(f"    LOW CATEGORY QUARTERS (<10):")
            for qk, n in low_cat_quarters:
                print(f"      - {qk}: {n} categories")
        else:
            print(f"    All quarters have >=10 categories")

    # =========================================================================
    # 3. DISTRICT COUNT CONSISTENCY
    # =========================================================================
    print("\n" + "=" * 80)
    print("3. DISTRICT COUNT CONSISTENCY")
    print("=" * 80)

    for state in STATES:
        if state not in all_state_data:
            continue
        data = all_state_data[state]
        quarters = data.get("quarters", {})

        print(f"\n  {state.upper()}")

        # Collect district counts per quarter across all categories
        all_counts = []
        anomalies = []

        for qk in sorted(quarters.keys(), key=lambda qk: parse_quarter_key(qk)):
            qdata = quarters[qk]
            tables = qdata.get("tables", {})
            q_counts = []
            for cat_name, cat_data in tables.items():
                districts = cat_data.get("districts", {})
                n = len(districts)
                q_counts.append(n)
                all_counts.append(n)

            if q_counts:
                mode_count = max(set(q_counts), key=q_counts.count)
                for cat_name, cat_data in tables.items():
                    n = len(cat_data.get("districts", {}))
                    # Flag if district count is less than half the mode for this quarter
                    if n < mode_count * 0.5 and mode_count > 3:
                        anomalies.append((qk, cat_name, n, mode_count))

        if all_counts:
            mode_overall = max(set(all_counts), key=all_counts.count)
            print(f"    Typical district count: {mode_overall} (range: {min(all_counts)}-{max(all_counts)})")

        if anomalies:
            print(f"    DISTRICT COUNT ANOMALIES ({len(anomalies)} found):")
            for qk, cat, n, mode in anomalies[:20]:
                print(f"      - {qk} / {cat}: {n} districts (expected ~{mode})")
            if len(anomalies) > 20:
                print(f"      ... and {len(anomalies) - 20} more")
        else:
            print(f"    District counts are consistent")

    # =========================================================================
    # 4. GARBLED VALUES
    # =========================================================================
    print("\n" + "=" * 80)
    print("4. GARBLED VALUES SCAN")
    print("=" * 80)

    for state in STATES:
        if state not in all_state_data:
            continue
        data = all_state_data[state]
        quarters = data.get("quarters", {})

        garbled_texts = []
        suspicious_numbers = []
        empty_count = 0
        null_count = 0
        comma_numbers = []
        total_values = 0

        for qk, qdata in quarters.items():
            tables = qdata.get("tables", {})
            for cat_name, cat_data in tables.items():
                districts = cat_data.get("districts", {})
                for dist_name, dist_data in districts.items():
                    for field, val in dist_data.items():
                        total_values += 1

                        if val is None:
                            null_count += 1
                            continue
                        if isinstance(val, str) and val.strip() == "":
                            empty_count += 1
                            continue

                        val_str = str(val)

                        # Check garbled text
                        if is_garbled_value(val_str):
                            garbled_texts.append((qk, cat_name, dist_name, field, val_str[:80]))

                        # Check suspicious numbers
                        num_issue = check_suspicious_number(val_str)
                        if num_issue:
                            suspicious_numbers.append((qk, cat_name, dist_name, field, num_issue))

                        # Check comma-separated numbers stored as strings
                        if isinstance(val, str) and re.match(r'^\d{1,3}(,\d{3})+(\.\d+)?$', val.strip()):
                            comma_numbers.append((qk, cat_name, dist_name, field, val))

        print(f"\n  {state.upper()} — {total_values} total values")
        print(f"    Empty strings: {empty_count}")
        print(f"    Null values: {null_count}")

        if garbled_texts:
            print(f"    GARBLED TEXT VALUES ({len(garbled_texts)}):")
            for item in garbled_texts[:10]:
                print(f"      - {item[0]}/{item[1]}/{item[2]}: {item[3]} = '{item[4]}'")
            if len(garbled_texts) > 10:
                print(f"      ... and {len(garbled_texts) - 10} more")
        else:
            print(f"    No garbled text values found")

        if suspicious_numbers:
            print(f"    SUSPICIOUS NUMBERS ({len(suspicious_numbers)}):")
            for item in suspicious_numbers[:10]:
                print(f"      - {item[0]}/{item[1]}/{item[2]}: {item[3]} -> {item[4]}")
            if len(suspicious_numbers) > 10:
                print(f"      ... and {len(suspicious_numbers) - 10} more")
        else:
            print(f"    No suspicious numbers found")

        if comma_numbers:
            print(f"    COMMA-FORMATTED NUMBERS ({len(comma_numbers)}):")
            for item in comma_numbers[:10]:
                print(f"      - {item[0]}/{item[1]}/{item[2]}: {item[3]} = '{item[4]}'")
            if len(comma_numbers) > 10:
                print(f"      ... and {len(comma_numbers) - 10} more")
        else:
            print(f"    No comma-formatted number strings found")

    # =========================================================================
    # 5. GARBLED FIELD NAMES
    # =========================================================================
    print("\n" + "=" * 80)
    print("5. GARBLED FIELD NAMES")
    print("=" * 80)

    for state in STATES:
        if state not in all_state_data:
            continue
        data = all_state_data[state]
        quarters = data.get("quarters", {})

        flagged_fields = {}  # field -> (issues, locations)

        for qk, qdata in quarters.items():
            tables = qdata.get("tables", {})
            for cat_name, cat_data in tables.items():
                fields = cat_data.get("fields", [])
                for field in fields:
                    issues = is_garbled_field(field)
                    if issues:
                        key = field
                        if key not in flagged_fields:
                            flagged_fields[key] = (issues, [])
                        flagged_fields[key][1].append(f"{qk}/{cat_name}")

        print(f"\n  {state.upper()}")
        if flagged_fields:
            print(f"    GARBLED FIELD NAMES ({len(flagged_fields)}):")
            for field, (issues, locs) in sorted(flagged_fields.items()):
                issue_str = ", ".join(issues)
                n_locs = len(locs)
                sample_loc = locs[0]
                print(f"      - '{field[:70]}' [{issue_str}] in {n_locs} location(s), e.g. {sample_loc}")
        else:
            print(f"    No garbled field names found")

    # =========================================================================
    # 6. GARBLED DISTRICT NAMES
    # =========================================================================
    print("\n" + "=" * 80)
    print("6. GARBLED DISTRICT NAMES")
    print("=" * 80)

    for state in STATES:
        if state not in all_state_data:
            continue
        data = all_state_data[state]
        quarters = data.get("quarters", {})

        flagged_districts = {}  # name -> (issues, locations)
        known = KNOWN_DISTRICTS.get(state, set())
        # Build case-insensitive known set
        known_lower = {d.lower() for d in known}

        for qk, qdata in quarters.items():
            tables = qdata.get("tables", {})
            for cat_name, cat_data in tables.items():
                districts = cat_data.get("districts", {})
                for dist_name in districts:
                    issues = is_garbled_district(dist_name, state)
                    # Also flag if not in known list (case-insensitive)
                    if dist_name.lower() not in known_lower and known:
                        issues.append("not in known district list")
                    if issues:
                        key = dist_name
                        if key not in flagged_districts:
                            flagged_districts[key] = (issues, [])
                        flagged_districts[key][1].append(f"{qk}/{cat_name}")

        print(f"\n  {state.upper()}")
        if flagged_districts:
            # Separate truly garbled from just "not in known list"
            truly_garbled = {k: v for k, v in flagged_districts.items()
                           if any(i != "not in known district list" for i in v[0])}
            unknown_only = {k: v for k, v in flagged_districts.items()
                          if all(i == "not in known district list" for i in v[0])}

            if truly_garbled:
                print(f"    GARBLED DISTRICT NAMES ({len(truly_garbled)}):")
                for name, (issues, locs) in sorted(truly_garbled.items()):
                    issue_str = ", ".join(issues)
                    print(f"      - '{name}' [{issue_str}] in {len(locs)} location(s)")

            if unknown_only:
                print(f"    UNKNOWN DISTRICTS (not in reference list) ({len(unknown_only)}):")
                for name, (issues, locs) in sorted(unknown_only.items()):
                    print(f"      - '{name}' ({len(locs)} occurrences)")
        else:
            print(f"    All district names look clean")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for state in STATES:
        if state not in all_state_data:
            print(f"  {state.upper()}: FILE MISSING")
            continue
        data = all_state_data[state]
        quarters = data.get("quarters", {})
        n_quarters = len(quarters)
        total_cats = sum(len(qd.get("tables", {})) for qd in quarters.values())
        total_districts = set()
        for qd in quarters.values():
            for cat_data in qd.get("tables", {}).values():
                total_districts.update(cat_data.get("districts", {}).keys())
        print(f"  {state.upper()}: {n_quarters} quarters, {total_cats} total category-quarter combos, {len(total_districts)} unique districts")

    print("\nAudit complete.")


if __name__ == "__main__":
    main()
