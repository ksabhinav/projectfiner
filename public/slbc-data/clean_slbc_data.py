#!/usr/bin/env python3
"""
Clean SLBC data quality issues for Meghalaya and Arunachal Pradesh.
- Removes non-district entries (bank names, serial numbers, totals, junk)
- Normalizes district names to canonical spelling
- Fixes OCR artifacts in field names (mid-word spaces)
- Regenerates quarterly CSVs and timeseries files
"""

import json
import csv
import os
import re
import shutil
import unicodedata
from pathlib import Path

BASE = Path("/Users/abhinav/Downloads/projectfiner/public/slbc-data")

# ─── Canonical districts ───────────────────────────────────────────────

MEGHALAYA_CANONICAL = [
    "East Garo Hills",
    "East Jaintia Hills",
    "East Khasi Hills",
    "Eastern West Khasi Hills",
    "North Garo Hills",
    "Ri Bhoi",
    "South Garo Hills",
    "South West Garo Hills",
    "South West Khasi Hills",
    "West Garo Hills",
    "West Jaintia Hills",
    "West Khasi Hills",
]

ARUNACHAL_CANONICAL = [
    "Anjaw",
    "Capital Complex",
    "Changlang",
    "Dibang Valley",
    "East Kameng",
    "East Siang",
    "Kamle",
    "Kra Daadi",
    "Kurung Kumey",
    "Lepa Rada",
    "Lohit",
    "Longding",
    "Lower Dibang Valley",
    "Lower Siang",
    "Lower Subansiri",
    "Namsai",
    "Pakke Kessang",
    "Papum Pare",
    "Shi Yomi",
    "Siang",
    "Tawang",
    "Tirap",
    "Upper Siang",
    "Upper Subansiri",
    "West Kameng",
    "West Siang",
]


def normalize_unicode(s):
    """Replace ñ/ñ with n for Jaintia matching."""
    return s.replace("ñ", "n").replace("ñ", "n").replace("\u00f1", "n").replace("\u0303", "")


def clean_text(s):
    """Strip trailing junk chars, normalize whitespace."""
    s = s.strip()
    # Remove trailing 'l' (typo), 'T' (truncation), etc.
    s = re.sub(r'\s*Total$', '', s, flags=re.IGNORECASE)
    s = s.rstrip('l').rstrip()  # trailing lowercase L
    return s


def match_meghalaya_district(raw_name):
    """Try to match a raw district name to a canonical Meghalaya district.
    Returns canonical name or None if not a valid district."""
    # Normalize unicode
    name = normalize_unicode(raw_name)
    name = clean_text(name)

    # Quick reject: numbers, bank abbreviations, junk
    if not name:
        return None
    # Pure numbers
    if re.match(r'^[\d.]+$', name):
        return None
    # All uppercase short strings that are bank codes (<=6 chars, all caps)
    if len(name) <= 6 and name.isupper() and not any(c.isspace() for c in name):
        return None
    # Known junk patterns
    junk_patterns = [
        r'^\(P\)$', r'^No of$', r'^Prj\.$', r'^\[.*\]$', r'^REBHOI$',
        r'^Referred back', r'^ANB$',
        # Bank names (longer ones)
        r'^BANDHAN$', r'^NEDFI$', r'^NESFB$', r'^INDUS$',
    ]
    for pat in junk_patterns:
        if re.match(pat, name, re.IGNORECASE):
            return None

    # Build lookup: lowercase canonical -> canonical
    canonical_lower = {c.lower(): c for c in MEGHALAYA_CANONICAL}

    # Direct match (case-insensitive)
    if name.lower() in canonical_lower:
        return canonical_lower[name.lower()]

    # Try prefix matching for truncated names
    name_lower = name.lower()
    matches = []
    for cl, canonical in canonical_lower.items():
        # Check if raw name is a prefix of canonical (at least 8 chars)
        if len(name_lower) >= 8 and cl.startswith(name_lower):
            matches.append(canonical)
        # Check if canonical starts with the raw name
        elif len(name_lower) >= 8 and name_lower.startswith(cl[:len(name_lower)]):
            matches.append(canonical)

    if len(matches) == 1:
        return matches[0]

    # Handle specific known typos/variations
    typo_map = {
        "easten west khasi hills": "Eastern West Khasi Hills",
        "eastern west": "Eastern West Khasi Hills",
        "south west garo": "South West Garo Hills",
        "south west": "South West Khasi Hills",  # ambiguous but likely
        "west jaintia": "West Jaintia Hills",
        "west khasi hills t": "West Khasi Hills",
        "south west garo hillsl": "South West Garo Hills",
        "south west garo hills": "South West Garo Hills",
    }
    if name_lower in typo_map:
        return typo_map[name_lower]

    return None


def match_arunachal_district(raw_name):
    """Try to match a raw district name to a canonical Arunachal Pradesh district.
    Returns canonical name or None if not a valid district."""
    name = raw_name.strip()

    # Quick reject
    if not name:
        return None
    if re.match(r'^[\d.]+$', name):
        return None

    # Known junk
    junk_patterns = [
        r'^Sl\.?\s*No\.?$', r'^Name of the District', r'^N\.B\.',
        r'^DISTRICT', r'^BANK WISE', r'^ACB$',
    ]
    for pat in junk_patterns:
        if re.match(pat, name, re.IGNORECASE):
            return None

    canonical_lower = {c.lower(): c for c in ARUNACHAL_CANONICAL}

    # Direct match
    if name.lower() in canonical_lower:
        return canonical_lower[name.lower()]

    # Known variations mapping
    variation_map = {
        "d. valley": "Dibang Valley",
        "l.d. valley": "Lower Dibang Valley",
        "k.  kumey": "Kurung Kumey",
        "k. kumey": "Kurung Kumey",
        "kurung kume": "Kurung Kumey",
        "kururn kumey": "Kurung Kumey",
        "lower diabng valley": "Lower Dibang Valley",
        "lower subansisri": "Lower Subansiri",
        "eat siang": "East Siang",
        "pake kessang": "Pakke Kessang",
        "pakekessang": "Pakke Kessang",
        "papumpae": "Papum Pare",
        "papumpare (capital complex)": "Capital Complex",
        "papumpare (icc)": "Capital Complex",
        "papum pare (c.c)": "Capital Complex",
        "papumpare (yupia)": "Papum Pare",
        "itanagar": "Capital Complex",
        "capital complex": "Capital Complex",
    }
    if name.lower() in variation_map:
        return variation_map[name.lower()]

    # Prefix matching
    name_lower = name.lower()
    matches = []
    for cl, canonical in canonical_lower.items():
        if len(name_lower) >= 6 and cl.startswith(name_lower):
            matches.append(canonical)
    if len(matches) == 1:
        return matches[0]

    return None


def fix_field_name(field_name):
    """Fix OCR artifacts in field names like mid-word spaces."""
    # Known OCR mid-word space fixes
    fixes = {
        "Infrastru cture": "Infrastructure",
        "Mecha nisation": "Mechanisation",
        "nisation Mecha": "Mechanisation",
        "Farm nisation Mecha": "Farm Mechanisation",
        "No Farm nisation Mecha": "Farm Mechanisation No.",
        "Amt Farm nisation Mecha": "Farm Mechanisation Amt",
        "ifsheries": "Fisheries",
        "Amt ifsheries": "Fisheries Amt",
        "chris tians": "Christians",
        "mus lims": "Muslims",
        "bud dhists": "Buddhists",
        "zorastri ans": "Zoroastrians",
        "zoras trians": "Zoroastrians",
        "Renew able": "Renewable",
        "Beneifof": "Beneficiary of",
        "ciary Beneifof": "Beneficiary of",
        "Alied": "Allied",
        "Prio": "Priority",
        "Edu cation": "Education",
        "cation Edu": "Education",
        # Reversed/garbled OCR from PDF text reversal
        "ANS Amt. ZORASTRI": "Zoroastrians Amt",
        "Amt. TRIANS ZORAS": "Zoroastrians Amt",
        "No. TRIANS ZORAS": "Zoroastrians No.",
        "Amt. LIMS MUS": "Muslims Amt",
    }
    result = field_name
    for old, new in fixes.items():
        result = result.replace(old, new)
    return result


def fix_timeseries_field_key(key):
    """Fix OCR artifacts in timeseries field keys (category__field format)."""
    fixes = {
        "chris_tians": "christians",
        "mus_lims": "muslims",
        "bud_dhists": "buddhists",
        "zorastri_ans": "zoroastrians",
        "zoras_trians": "zoroastrians",
        "ans_amt._zorastri": "zoroastrians_amt",
        "ans_no._zorastri": "zoroastrians_no",
        "renew_able": "renewable",
        "infrastru_cture": "infrastructure",
    }
    result = key
    for old, new in fixes.items():
        result = result.replace(old, new)
    return result


def clean_complete_json(filepath, match_func, state_name):
    """Clean the _complete.json file. Returns cleaned data."""
    with open(filepath) as f:
        data = json.load(f)

    stats = {"quarters_processed": 0, "districts_kept": 0, "districts_removed": 0,
             "categories_removed": 0, "fields_fixed": 0}

    for qname, quarter in data["quarters"].items():
        stats["quarters_processed"] += 1
        tables_to_remove = []

        for tname, table in quarter["tables"].items():
            districts = table.get("districts", {})
            cleaned_districts = {}

            for raw_dist, fields in districts.items():
                canonical = match_func(raw_dist)
                if canonical:
                    # Fix field names in the data
                    fixed_fields = {}
                    for fk, fv in fields.items():
                        new_fk = fix_field_name(fk)
                        if new_fk != fk:
                            stats["fields_fixed"] += 1
                        fixed_fields[new_fk] = fv
                    # If same canonical district already exists, merge (keep first)
                    if canonical not in cleaned_districts:
                        cleaned_districts[canonical] = fixed_fields
                    stats["districts_kept"] += 1
                else:
                    stats["districts_removed"] += 1

            if cleaned_districts:
                table["districts"] = cleaned_districts
                table["num_districts"] = len(cleaned_districts)
                # Also fix field names in the fields list
                if "fields" in table and isinstance(table["fields"], list):
                    table["fields"] = [fix_field_name(f) for f in table["fields"]]
            else:
                tables_to_remove.append(tname)

        for tname in tables_to_remove:
            del quarter["tables"][tname]
            stats["categories_removed"] += 1

    # Write back
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  [{state_name}] complete.json cleaned:")
    print(f"    Quarters: {stats['quarters_processed']}")
    print(f"    Districts kept: {stats['districts_kept']}, removed: {stats['districts_removed']}")
    print(f"    Categories removed (empty): {stats['categories_removed']}")
    print(f"    Fields fixed: {stats['fields_fixed']}")

    return data


def regenerate_quarterly_csvs(data, quarterly_dir):
    """Delete and recreate all CSVs in quarterly/YYYY-MM/ directories."""
    # Map quarter key names to folder names
    quarter_to_folder = {}
    for qname, q in data["quarters"].items():
        # qname like "dec_2020" -> folder "2020-12"
        # Extract from as_on_date or period
        period = q.get("period", "")
        as_on = q.get("as_on_date", "")

        # Try to derive folder name from as_on_date (DD-MM-YYYY)
        if as_on:
            parts = as_on.split("-")
            if len(parts) == 3:
                day, month, year = parts
                folder = f"{year}-{month}"
                quarter_to_folder[qname] = folder
                continue

        # Fallback: parse from qname
        month_map = {
            "mar": "03", "jun": "06", "sep": "09", "dec": "12",
            "march": "03", "june": "06", "sept": "09", "september": "09",
            "december": "12",
        }
        # Try pattern like "dec_2020" or "2018-03"
        m = re.match(r'(\w+)_(\d{4})', qname)
        if m:
            mon, year = m.group(1).lower(), m.group(2)
            if mon in month_map:
                quarter_to_folder[qname] = f"{year}-{month_map[mon]}"
                continue
        # Try "YYYY-MM"
        m = re.match(r'(\d{4})-(\d{2})', qname)
        if m:
            quarter_to_folder[qname] = qname
            continue

        print(f"    WARNING: Could not determine folder for quarter key '{qname}'")

    for qname, q in data["quarters"].items():
        folder_name = quarter_to_folder.get(qname)
        if not folder_name:
            continue

        folder_path = quarterly_dir / folder_name
        # Delete existing CSVs in this folder
        if folder_path.exists():
            for f in folder_path.glob("*.csv"):
                f.unlink()
        else:
            folder_path.mkdir(parents=True, exist_ok=True)

        # Write one CSV per category/table
        for tname, table in q["tables"].items():
            districts = table.get("districts", {})
            if not districts:
                continue

            fields = table.get("fields", [])
            if not fields:
                # Derive from first district's keys
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

    # Clean up empty quarterly folders
    if quarterly_dir.exists():
        for folder in quarterly_dir.iterdir():
            if folder.is_dir() and not any(folder.glob("*.csv")):
                # Check if folder should exist
                if folder.name not in quarter_to_folder.values():
                    shutil.rmtree(folder)


def regenerate_timeseries(data, state_dir, state_slug):
    """Regenerate timeseries CSV and JSON files."""
    # Build timeseries records: one row per district per quarter
    all_records = []
    all_field_keys = set()

    # Collect all category__field combinations
    for qname, q in data["quarters"].items():
        for tname, table in q["tables"].items():
            for dist_name, fields in table.get("districts", {}).items():
                for fld in fields.keys():
                    key = f"{tname}__{fld}"
                    key = fix_timeseries_field_key(key)
                    # Normalize: lowercase, replace spaces with _, clean up
                    norm_key = re.sub(r'[^a-z0-9_/()&.,%]+', '_',
                                      key.lower().replace(' ', '_'))
                    norm_key = re.sub(r'_+', '_', norm_key).strip('_')
                    all_field_keys.add(norm_key)

    # Sort field keys for consistent output
    sorted_fields = sorted(all_field_keys)

    # Build records grouped by period for JSON
    periods_data = {}

    for qname, q in data["quarters"].items():
        period = q.get("period", qname)
        as_on = q.get("as_on_date", "")
        fy = q.get("fy", "")

        # Collect all districts in this quarter
        quarter_districts = {}
        for tname, table in q["tables"].items():
            for dist_name, fields in table.get("districts", {}).items():
                if dist_name not in quarter_districts:
                    quarter_districts[dist_name] = {
                        "district": dist_name,
                        "period": period,
                        "as_on_date": as_on,
                        "fy": fy,
                    }
                for fld, val in fields.items():
                    key = f"{tname}__{fld}"
                    key = fix_timeseries_field_key(key)
                    norm_key = re.sub(r'[^a-z0-9_/()&.,%]+', '_',
                                      key.lower().replace(' ', '_'))
                    norm_key = re.sub(r'_+', '_', norm_key).strip('_')
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
    ts_json = {
        "source": data.get("source", "SLBC NE"),
        "state": data.get("state", ""),
        "description": "Complete district-wise FI time-series",
        "num_periods": len(periods_data),
        "total_records": len(all_records),
        "total_fields": len(sorted_fields),
        "periods": [periods_data[p] for p in sorted(periods_data.keys(),
                    key=lambda x: all_records[[r["period"] for r in all_records].index(x)]["as_on_date"]
                    if x in [r["period"] for r in all_records] else "")]
    }

    # Better sort: by as_on_date
    period_dates = {}
    for r in all_records:
        if r["period"] not in period_dates and r.get("as_on_date"):
            period_dates[r["period"]] = r["as_on_date"]

    def parse_date(d):
        """Parse DD-MM-YYYY to sortable tuple."""
        try:
            parts = d.split("-")
            return (int(parts[2]), int(parts[1]), int(parts[0]))
        except:
            return (0, 0, 0)

    sorted_periods = sorted(periods_data.keys(),
                           key=lambda p: parse_date(period_dates.get(p, "01-01-1900")))

    ts_json["periods"] = [periods_data[p] for p in sorted_periods]

    with open(json_path, "w") as f:
        json.dump(ts_json, f, indent=2, ensure_ascii=False)

    print(f"  Timeseries: {len(all_records)} records, {len(sorted_fields)} fields, {len(periods_data)} periods")


def clean_preexisting_quarterly_csvs(quarterly_dir, match_func, state_name):
    """Clean any pre-existing quarterly CSVs (not regenerated by us) that have junk districts.
    Skip bankwise files."""
    if not quarterly_dir.exists():
        return
    fixed = 0
    for folder in sorted(quarterly_dir.iterdir()):
        if not folder.is_dir():
            continue
        for csv_file in sorted(folder.glob("*.csv")):
            if "bankwise" in csv_file.name:
                continue
            # Read, filter, rewrite
            with open(csv_file, newline="") as f:
                reader = csv.reader(f)
                header = next(reader)
                rows = list(reader)

            clean_rows = []
            for row in rows:
                if not row:
                    continue
                raw_dist = row[0]
                canonical = match_func(raw_dist)
                if canonical:
                    row[0] = canonical
                    clean_rows.append(row)

            if len(clean_rows) != len(rows):
                with open(csv_file, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                    writer.writerows(clean_rows)
                fixed += 1

    if fixed:
        print(f"  [{state_name}] Fixed {fixed} pre-existing quarterly CSVs")
    else:
        print(f"  [{state_name}] No pre-existing CSVs needed fixing")


def main():
    print("=" * 60)
    print("SLBC Data Quality Cleaning")
    print("=" * 60)

    # ─── Meghalaya ───
    print("\n--- Meghalaya ---")
    meg_dir = BASE / "meghalaya"
    meg_json = meg_dir / "meghalaya_complete.json"
    meg_data = clean_complete_json(meg_json, match_meghalaya_district, "Meghalaya")
    regenerate_quarterly_csvs(meg_data, meg_dir / "quarterly")
    regenerate_timeseries(meg_data, meg_dir, "meghalaya")

    # ─── Arunachal Pradesh ───
    print("\n--- Arunachal Pradesh ---")
    ap_dir = BASE / "arunachal-pradesh"
    ap_json = ap_dir / "arunachal_pradesh_complete.json"
    ap_data = clean_complete_json(ap_json, match_arunachal_district, "Arunachal Pradesh")
    regenerate_quarterly_csvs(ap_data, ap_dir / "quarterly")
    regenerate_timeseries(ap_data, ap_dir, "arunachal_pradesh")

    # ─── Clean pre-existing quarterly CSVs not managed by complete.json ───
    print("\n--- Cleaning pre-existing quarterly CSVs ---")
    clean_preexisting_quarterly_csvs(
        meg_dir / "quarterly", match_meghalaya_district, "Meghalaya")
    clean_preexisting_quarterly_csvs(
        ap_dir / "quarterly", match_arunachal_district, "Arunachal Pradesh")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
