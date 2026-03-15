#!/usr/bin/env python3
"""
SLBC Data Quality Audit Script
Randomly samples 30 quarterly CSVs across all 8 NE states and performs
thorough data quality, structural, field name, and content checks.
Also audits timeseries CSVs for each state.
"""

import os
import random
import re
import csv
import json
from pathlib import Path
from collections import defaultdict, Counter
import math

random.seed(42)  # reproducibility

BASE = Path("/Users/abhinav/Downloads/projectfiner/public/slbc-data")
STATES = [
    "arunachal-pradesh", "assam", "manipur", "meghalaya",
    "mizoram", "nagaland", "sikkim", "tripura"
]

# ──────────────────────────── helpers ────────────────────────────

def read_csv_safe(path):
    """Read a CSV, return (headers, rows) where rows are list of dicts."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
        return headers, rows
    except Exception as e:
        return None, str(e)


def is_number_with_formatting(val):
    """Check if a value looks like a number but has formatting chars."""
    if not isinstance(val, str):
        return False
    val = val.strip()
    if not val:
        return False
    # Already a clean number?
    try:
        float(val)
        return False
    except ValueError:
        pass
    # Has commas, spaces, or other formatting in what looks like a number?
    cleaned = re.sub(r'[,\s]+', '', val)
    try:
        float(cleaned)
        return True  # it's a formatted number
    except ValueError:
        pass
    # Special chars like Rs., lakh, cr, % embedded
    cleaned2 = re.sub(r'[₹$%,\s]', '', val)
    cleaned2 = re.sub(r'(rs\.?|lakh|cr|crore|lakhs)', '', cleaned2, flags=re.IGNORECASE)
    try:
        float(cleaned2)
        return True
    except ValueError:
        return False


def looks_like_number(val):
    """Check if val can be parsed as a number."""
    if not isinstance(val, str):
        return False
    val = val.strip()
    if not val:
        return False
    try:
        float(val)
        return True
    except ValueError:
        return False


def is_garbled(name):
    """Check if a column name looks garbled or meaningless."""
    name = name.strip()
    if not name:
        return True
    if len(name) <= 1 and not name.isalpha():
        return True
    # Just a number
    try:
        float(name)
        return True
    except ValueError:
        pass
    # Too many special chars
    alpha_count = sum(1 for c in name if c.isalpha())
    if len(name) > 3 and alpha_count / len(name) < 0.3:
        return True
    return False


def has_ocr_artifacts(name):
    """Check for OCR artifacts in field names."""
    issues = []
    # Mid-word spaces (lowercase letter space lowercase letter)
    if re.search(r'[a-z]\s[a-z]', name) and len(name.split()) > 4:
        # Could be normal multi-word name, check for suspicious patterns
        if re.search(r'[a-z] [a-z]{1,2} [a-z]', name):
            issues.append("possible mid-word space break")
    # Hyphen breaks that look like word wraps
    if re.search(r'[a-z]-\s+[a-z]', name):
        issues.append("hyphen break (possible line wrap)")
    # Random capitalization mid-word
    if re.search(r'[a-z][A-Z][a-z]', name) and not any(w in name.lower() for w in ['msme', 'npa', 'kcc', 'pmay', 'pmmy', 'atm']):
        issues.append("unusual mid-word capitalization")
    # Garbled characters
    if re.search(r'[^\x00-\x7F]', name):
        non_ascii = [c for c in name if ord(c) > 127]
        if non_ascii:
            issues.append(f"non-ASCII chars: {non_ascii}")
    return issues


def find_near_duplicates(names):
    """Find near-duplicate column names."""
    dupes = []
    normalized = {}
    for name in names:
        key = re.sub(r'[\s_\-\.]+', '', name.lower())
        key = re.sub(r'[^a-z0-9]', '', key)
        if key in normalized:
            dupes.append((name, normalized[key]))
        else:
            normalized[key] = name
    return dupes


# Known NE district names for detection
NE_DISTRICTS = {
    "tawang", "west kameng", "east kameng", "papum pare", "kurung kumey",
    "lower subansiri", "upper subansiri", "west siang", "east siang",
    "upper siang", "dibang valley", "lower dibang valley", "lohit",
    "changlang", "tirap", "longding", "namsai", "kamle", "pakke-kessang",
    "lepa-rada", "shi-yomi", "siang", "anjaw", "itanagar",
    "baksa", "barpeta", "biswanath", "bongaigaon", "cachar", "charaideo",
    "chirang", "darrang", "dhemaji", "dhubri", "dibrugarh", "dima hasao",
    "goalpara", "golaghat", "hailakandi", "hojai", "jorhat", "kamrup",
    "kamrup metro", "karbi anglong", "karimganj", "kokrajhar", "lakhimpur",
    "majuli", "morigaon", "nagaon", "nalbari", "sivasagar", "sonitpur",
    "south salmara", "tinsukia", "udalguri", "west karbi anglong",
    "bishnupur", "chandel", "churachandpur", "imphal east", "imphal west",
    "jiribam", "kakching", "kamjong", "kangpokpi", "noney", "pherzawl",
    "senapati", "tamenglong", "tengnoupal", "thoubal", "ukhrul",
    "east garo hills", "east jaintia hills", "east khasi hills",
    "north garo hills", "ri bhoi", "south garo hills", "south west garo hills",
    "south west khasi hills", "west garo hills", "west jaintia hills",
    "west khasi hills",
    "aizawl", "champhai", "hnahthial", "khawzawl", "kolasib", "lawngtlai",
    "lunglei", "mamit", "saitual", "saiha", "serchhip",
    "dimapur", "kiphire", "kohima", "longleng", "mokokchung", "mon",
    "noklak", "peren", "phek", "tuensang", "wokha", "zunheboto",
    "east sikkim", "north sikkim", "south sikkim", "west sikkim",
    "dhalai", "gomati", "khowai", "north tripura", "sepahijala",
    "south tripura", "unakoti", "west tripura",
}


# ──────────────────────────── audit functions ────────────────────────────

def audit_quarterly_csv(filepath):
    """Comprehensive audit of a single quarterly CSV."""
    issues = {
        "data_quality": [],
        "structural": [],
        "field_names": [],
        "content": [],
    }

    headers, rows = read_csv_safe(filepath)
    if headers is None:
        issues["structural"].append(f"FAILED TO READ: {rows}")
        return issues

    if not headers:
        issues["structural"].append("NO HEADERS found in file")
        return issues

    if not rows:
        issues["content"].append("FILE IS EMPTY (no data rows)")
        return issues

    num_rows = len(rows)
    num_cols = len(headers)

    # ── A. DATA QUALITY ──

    # A1: Values that look like formatted numbers
    for col in headers:
        formatted_examples = []
        for row in rows[:50]:  # sample first 50 rows
            val = row.get(col, "")
            if val and is_number_with_formatting(val):
                formatted_examples.append(val)
        if formatted_examples:
            issues["data_quality"].append({
                "type": "formatted_numbers",
                "column": col,
                "examples": formatted_examples[:5],
                "count": len(formatted_examples),
            })

    # A2: Empty or near-empty CSVs
    districts_with_data = 0
    district_col = None
    for h in headers:
        if h.lower().strip() in ("district", "district name", "districts", "name of district"):
            district_col = h
            break
    if not district_col and headers:
        district_col = headers[0]

    data_cols = [h for h in headers if h != district_col]
    for row in rows:
        has_data = False
        for col in data_cols:
            val = row.get(col, "").strip()
            if val and val != "0" and val != "0.00" and val != "0.0":
                has_data = True
                break
        if has_data:
            districts_with_data += 1

    if districts_with_data < 3:
        issues["data_quality"].append({
            "type": "near_empty",
            "districts_with_data": districts_with_data,
            "total_rows": num_rows,
        })

    # A3: Columns where ALL values are the same
    for col in headers:
        vals = [row.get(col, "").strip() for row in rows if row.get(col, "").strip()]
        if len(vals) >= 2:
            unique = set(vals)
            if len(unique) == 1:
                issues["data_quality"].append({
                    "type": "all_same_value",
                    "column": col,
                    "value": list(unique)[0],
                    "count": len(vals),
                })

    # A4: Columns that are all zeros
    for col in data_cols:
        vals = [row.get(col, "").strip() for row in rows if row.get(col, "").strip()]
        if vals and all(v in ("0", "0.0", "0.00", "0.000") for v in vals):
            issues["data_quality"].append({
                "type": "all_zeros",
                "column": col,
                "count": len(vals),
            })

    # A5: Clearly wrong values (negative numbers, unreasonably large)
    for col in data_cols:
        for row in rows:
            val = row.get(col, "").strip()
            if not val:
                continue
            try:
                num = float(val)
                if num < 0 and col.lower() not in ("growth", "change", "difference", "variance"):
                    district = row.get(district_col, "?")
                    issues["data_quality"].append({
                        "type": "negative_value",
                        "column": col,
                        "value": val,
                        "district": district,
                    })
                if num > 1e10:  # > 10 billion seems suspicious for district-level
                    district = row.get(district_col, "?")
                    issues["data_quality"].append({
                        "type": "unreasonably_large",
                        "column": col,
                        "value": val,
                        "district": district,
                    })
            except ValueError:
                pass

    # A6: District name appearing as value in data column
    if district_col:
        district_names = {row.get(district_col, "").strip().lower() for row in rows if row.get(district_col, "")}
        for col in data_cols:
            for row in rows:
                val = row.get(col, "").strip().lower()
                if val and val in district_names and len(val) > 2:
                    issues["data_quality"].append({
                        "type": "district_as_value",
                        "column": col,
                        "value": val,
                        "district": row.get(district_col, "?"),
                    })

    # ── B. STRUCTURAL ISSUES ──

    # B1: Serial number columns
    serial_patterns = [r'^s\.?\s*no\.?$', r'^sl\.?\s*no\.?$', r'^sr\.?\s*no\.?$',
                       r'^serial\s*(no|number)?\.?$', r'^#$', r'^no\.?$', r'^sno$']
    for col in headers:
        col_lower = col.strip().lower()
        for pat in serial_patterns:
            if re.match(pat, col_lower):
                issues["structural"].append({
                    "type": "serial_number_column",
                    "column": col,
                })
                break

    # B2: District name repeated as another column
    if district_col:
        for col in headers:
            if col == district_col:
                continue
            vals = [row.get(col, "").strip().lower() for row in rows if row.get(col, "")]
            district_vals = [row.get(district_col, "").strip().lower() for row in rows if row.get(district_col, "")]
            if vals and district_vals and vals == district_vals:
                issues["structural"].append({
                    "type": "duplicate_district_column",
                    "column": col,
                })

    # B3: Column names that are just numbers or single characters
    for col in headers:
        col_stripped = col.strip()
        if len(col_stripped) <= 1:
            issues["structural"].append({
                "type": "single_char_column",
                "column": repr(col),
            })
        elif col_stripped.replace('.', '').replace('-', '').isdigit():
            issues["structural"].append({
                "type": "numeric_column_name",
                "column": col,
            })

    # B4: Garbled column names
    for col in headers:
        if is_garbled(col):
            issues["structural"].append({
                "type": "garbled_column_name",
                "column": repr(col),
            })

    # B5: Column names that look like data (bank name, district name)
    bank_patterns = [r'sbi\b', r'ubi\b', r'pnb\b', r'allahabad', r'gramin',
                     r'\bbank\b', r'canara', r'syndicate', r'andhra\s+bank']
    for col in headers:
        col_lower = col.strip().lower()
        # Check if column name is a district name
        if col_lower in NE_DISTRICTS:
            issues["structural"].append({
                "type": "column_name_is_district",
                "column": col,
            })
        for pat in bank_patterns:
            if re.search(pat, col_lower) and len(col_lower) < 40:
                issues["structural"].append({
                    "type": "column_name_looks_like_bank",
                    "column": col,
                })
                break

    # ── C. FIELD NAME ISSUES ──

    # C1: OCR artifacts
    for col in headers:
        artifacts = has_ocr_artifacts(col)
        if artifacts:
            issues["field_names"].append({
                "type": "ocr_artifacts",
                "column": col,
                "issues": artifacts,
            })

    # C2: Near-duplicates
    dupes = find_near_duplicates(headers)
    for name1, name2 in dupes:
        issues["field_names"].append({
            "type": "near_duplicate",
            "columns": (name1, name2),
        })

    # C3: Meaningless names
    for col in headers:
        col_stripped = col.strip()
        if not col_stripped:
            issues["field_names"].append({
                "type": "empty_name",
                "column": repr(col),
            })
        elif len(col_stripped) == 1 and not col_stripped.isalpha():
            issues["field_names"].append({
                "type": "punctuation_only",
                "column": repr(col),
            })
        elif all(c in '.-_/ ' for c in col_stripped):
            issues["field_names"].append({
                "type": "no_meaningful_chars",
                "column": repr(col),
            })

    # C4: Very long field names
    for col in headers:
        if len(col) > 80:
            issues["field_names"].append({
                "type": "very_long_name",
                "column": col,
                "length": len(col),
            })

    # ── D. CONTENT ISSUES ──

    # D1: Phantom rows (all data columns NaN/empty)
    phantom_count = 0
    phantom_examples = []
    for i, row in enumerate(rows):
        all_empty = True
        for col in data_cols:
            val = row.get(col, "").strip()
            if val:
                all_empty = False
                break
        if all_empty:
            phantom_count += 1
            if len(phantom_examples) < 3:
                phantom_examples.append({
                    "row_index": i,
                    "district": row.get(district_col, "?"),
                })
    if phantom_count > 0:
        issues["content"].append({
            "type": "phantom_rows",
            "count": phantom_count,
            "examples": phantom_examples,
        })

    # D2: Misclassified data detection
    # Check if the filename category matches column names
    filename = os.path.basename(filepath).replace('.csv', '')

    # D3: Concatenated values (values with multiple numbers separated by / or ;)
    for col in data_cols:
        for row in rows[:30]:
            val = row.get(col, "").strip()
            if not val:
                continue
            # Multiple numbers separated by / or ;
            if re.match(r'^\d+[\./;]\d+[\./;]\d+', val) and '.' not in val.replace(re.search(r'[\./;]', val).group(), ''):
                issues["content"].append({
                    "type": "concatenated_values",
                    "column": col,
                    "value": val,
                    "district": row.get(district_col, "?"),
                })

    # Check for percentage sign in values
    for col in data_cols:
        pct_vals = []
        for row in rows:
            val = row.get(col, "").strip()
            if '%' in val:
                pct_vals.append(val)
        if pct_vals:
            issues["data_quality"].append({
                "type": "percentage_sign_in_value",
                "column": col,
                "examples": pct_vals[:3],
            })

    return issues


def audit_timeseries_csv(filepath, state):
    """Audit a state's timeseries CSV."""
    issues = {
        "sparse_columns": [],
        "garbled_names": [],
        "near_duplicates": [],
        "other": [],
    }

    headers, rows = read_csv_safe(filepath)
    if headers is None:
        issues["other"].append(f"FAILED TO READ: {rows}")
        return issues

    if not rows:
        issues["other"].append("EMPTY FILE")
        return issues

    num_rows = len(rows)

    # Sparse columns (< 10% of rows have data)
    for col in headers:
        non_empty = sum(1 for row in rows if row.get(col, "").strip())
        pct = (non_empty / num_rows * 100) if num_rows > 0 else 0
        if pct < 10 and pct > 0:
            issues["sparse_columns"].append({
                "column": col,
                "non_empty_rows": non_empty,
                "total_rows": num_rows,
                "pct": round(pct, 1),
            })
        elif pct == 0:
            issues["sparse_columns"].append({
                "column": col,
                "non_empty_rows": 0,
                "total_rows": num_rows,
                "pct": 0,
                "note": "COMPLETELY EMPTY",
            })

    # Garbled names
    for col in headers:
        if is_garbled(col):
            issues["garbled_names"].append(col)

    # Near-duplicates
    dupes = find_near_duplicates(headers)
    for name1, name2 in dupes:
        issues["near_duplicates"].append((name1, name2))

    # Very long names
    for col in headers:
        if len(col) > 80:
            issues["other"].append({
                "type": "very_long_name",
                "column": col,
                "length": len(col),
            })

    # OCR artifacts
    for col in headers:
        artifacts = has_ocr_artifacts(col)
        if artifacts:
            issues["other"].append({
                "type": "ocr_artifacts",
                "column": col,
                "issues": artifacts,
            })

    return issues


# ──────────────────────────── sampling ────────────────────────────

def collect_all_csvs():
    """Collect all quarterly CSV paths per state."""
    state_csvs = {}
    for state in STATES:
        quarterly_dir = BASE / state / "quarterly"
        csvs = []
        if quarterly_dir.exists():
            for quarter_dir in sorted(quarterly_dir.iterdir()):
                if quarter_dir.is_dir():
                    for csv_file in sorted(quarter_dir.glob("*.csv")):
                        csvs.append(str(csv_file))
        state_csvs[state] = csvs
    return state_csvs


def sample_csvs(state_csvs, total=30, min_per_state=2):
    """Sample CSVs ensuring min per state and proportional allocation."""
    sampled = []

    # First ensure minimum per state
    for state in STATES:
        csvs = state_csvs[state]
        if len(csvs) >= min_per_state:
            sampled.extend([(state, c) for c in random.sample(csvs, min_per_state)])
        else:
            sampled.extend([(state, c) for c in csvs])

    remaining = total - len(sampled)
    if remaining > 0:
        # Allocate remaining proportionally
        already_sampled = {c for _, c in sampled}
        pool = []
        for state in STATES:
            for c in state_csvs[state]:
                if c not in already_sampled:
                    pool.append((state, c))

        if pool:
            extra = random.sample(pool, min(remaining, len(pool)))
            sampled.extend(extra)

    return sampled


# ──────────────────────────── main ────────────────────────────

def format_issue(issue):
    """Format a single issue for display."""
    if isinstance(issue, str):
        return f"    - {issue}"
    if isinstance(issue, dict):
        typ = issue.get("type", "unknown")
        parts = [f"    - [{typ}]"]
        for k, v in issue.items():
            if k == "type":
                continue
            if isinstance(v, list) and len(v) > 5:
                parts.append(f"      {k}: {v[:5]} ... ({len(v)} total)")
            else:
                parts.append(f"      {k}: {v}")
        return "\n".join(parts)
    return f"    - {issue}"


def main():
    print("=" * 100)
    print("SLBC DATA QUALITY AUDIT")
    print("=" * 100)

    state_csvs = collect_all_csvs()
    print("\n📊 CSV counts per state:")
    for state in STATES:
        print(f"  {state}: {len(state_csvs[state])} CSVs")

    sampled = sample_csvs(state_csvs, total=30, min_per_state=2)
    print(f"\nSampled {len(sampled)} CSVs:")
    state_counts = Counter(s for s, _ in sampled)
    for state in STATES:
        print(f"  {state}: {state_counts.get(state, 0)} sampled")

    # ── Audit quarterly CSVs ──
    all_issues = defaultdict(list)
    systemic = defaultdict(int)

    print("\n" + "=" * 100)
    print("PART 1: QUARTERLY CSV AUDIT (30 sampled files)")
    print("=" * 100)

    for idx, (state, filepath) in enumerate(sampled, 1):
        rel = os.path.relpath(filepath, BASE)
        print(f"\n{'─' * 80}")
        print(f"[{idx}/30] {rel}")
        print(f"{'─' * 80}")

        issues = audit_quarterly_csv(filepath)
        total_issues = sum(len(v) for v in issues.values())

        if total_issues == 0:
            print("  ✓ No issues found")
        else:
            for category, items in issues.items():
                if not items:
                    continue
                print(f"\n  [{category.upper()}] ({len(items)} issue(s)):")
                for item in items:
                    print(format_issue(item))
                    # Track systemic issues
                    if isinstance(item, dict):
                        systemic[item.get("type", "unknown")] += 1
                    else:
                        systemic["other"] += 1

        all_issues[state].extend(
            [(filepath, cat, item) for cat, items in issues.items() for item in items]
        )

    # ── Audit timeseries CSVs ──
    print("\n" + "=" * 100)
    print("PART 2: TIMESERIES CSV AUDIT (all 8 states)")
    print("=" * 100)

    ts_systemic = defaultdict(int)

    for state in STATES:
        slug = state.replace("-", "_")
        ts_path = BASE / state / f"{slug}_fi_timeseries.csv"

        print(f"\n{'─' * 80}")
        print(f"{state}: {ts_path.name}")
        print(f"{'─' * 80}")

        if not ts_path.exists():
            print("  ✗ FILE NOT FOUND")
            continue

        issues = audit_timeseries_csv(str(ts_path), state)

        total_issues = sum(len(v) for v in issues.values())
        if total_issues == 0:
            print("  ✓ No issues found")
        else:
            for category, items in issues.items():
                if not items:
                    continue
                print(f"\n  [{category.upper()}] ({len(items)} issue(s)):")
                for item in items:
                    print(format_issue(item))
                    if isinstance(item, dict):
                        ts_systemic[item.get("type", "unknown")] += 1
                    elif isinstance(item, tuple):
                        ts_systemic["near_duplicate"] += 1
                    else:
                        ts_systemic["garbled_name"] += 1

    # ── Summary ──
    print("\n" + "=" * 100)
    print("PART 3: SYSTEMIC ISSUES SUMMARY")
    print("=" * 100)

    print("\n--- Quarterly CSV Issues (across 30 sampled files) ---")
    if systemic:
        for issue_type, count in sorted(systemic.items(), key=lambda x: -x[1]):
            print(f"  {issue_type}: {count} occurrences")
    else:
        print("  No issues found!")

    print("\n--- Timeseries CSV Issues (across 8 states) ---")
    if ts_systemic:
        for issue_type, count in sorted(ts_systemic.items(), key=lambda x: -x[1]):
            print(f"  {issue_type}: {count} occurrences")
    else:
        print("  No issues found!")

    # Per-state summary
    print("\n--- Issues by State ---")
    for state in STATES:
        state_issues = all_issues.get(state, [])
        if state_issues:
            cats = Counter(cat for _, cat, _ in state_issues)
            print(f"  {state}: {len(state_issues)} total issues — {dict(cats)}")
        else:
            print(f"  {state}: No issues found")

    # Most problematic columns across all files
    print("\n--- Most Problematic Column Names (appearing in issues) ---")
    col_issues = Counter()
    for state, items in all_issues.items():
        for filepath, cat, item in items:
            if isinstance(item, dict):
                col = item.get("column", item.get("columns", ""))
                if col:
                    col_issues[str(col)] += 1
    for col, count in col_issues.most_common(20):
        print(f"  '{col}': {count} issues")


if __name__ == "__main__":
    main()
