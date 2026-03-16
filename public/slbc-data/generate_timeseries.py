#!/usr/bin/env python3
"""
Generate _fi_timeseries.json from _complete.json for new states.
Converts: quarters → {YYYY-MM} → tables → {category} → districts → {field: value}
Into:     periods[] → { period, districts[] → { district, period, category__field: value } }
"""

import os, json, re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# State configs: (slug, complete_json_name, min_districts_threshold)
STATES = [
    ("kerala", "kerala_complete.json", 5),
    ("karnataka", "karnataka_complete.json", 10),
    ("tamil-nadu", "tamilnadu_complete.json", 10),
]

MONTH_NAMES = {
    "03": "March", "06": "June", "09": "September", "12": "December"
}


def to_snake_case(s):
    """Convert a field name to snake_case."""
    # Replace newlines and multiple spaces with single space
    s = re.sub(r'\s+', ' ', s.strip())
    # Replace special chars with underscore
    s = re.sub(r'[^a-zA-Z0-9]+', '_', s)
    # CamelCase to snake_case
    s = re.sub(r'([a-z])([A-Z])', r'\1_\2', s)
    s = s.lower().strip('_')
    # Collapse multiple underscores
    s = re.sub(r'_+', '_', s)
    return s


def clean_value(v):
    """Clean a value: strip Indian comma-formatted numbers, trim whitespace."""
    if not isinstance(v, str):
        return v
    v = v.strip()
    if not v:
        return v
    # Try to parse as number after removing commas (Indian format: 7,55,908.02)
    stripped = v.replace(',', '')
    try:
        float(stripped)
        return stripped
    except ValueError:
        return v


def generate_timeseries(slug, complete_json_name, min_districts):
    complete_path = os.path.join(BASE_DIR, slug, complete_json_name)
    out_path = os.path.join(BASE_DIR, slug, f"{slug}_fi_timeseries.json")

    print(f"\n=== {slug} ===")

    with open(complete_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    periods = []
    total_records = 0
    all_fields = set()

    for qkey in sorted(data["quarters"].keys()):
        quarter = data["quarters"][qkey]
        period_name = quarter.get("period", "")

        # Convert YYYY-MM to period name if needed
        if not period_name and "-" in qkey:
            year, month = qkey.split("-")
            period_name = f"{MONTH_NAMES.get(month, month)} {year}"

        # Collect all district data across categories for this quarter
        district_records = {}  # district_name → {field: value}

        for cat_name, cat_data in quarter.get("tables", {}).items():
            districts = cat_data.get("districts", {})

            # Skip categories with very few districts (likely broken extraction)
            if len(districts) < min_districts:
                continue

            # Skip categories with raw annexure names (Karnataka early data)
            if re.match(r'^(anx_|ag_\d)', cat_name):
                continue

            for dist_name, dist_data in districts.items():
                if dist_name not in district_records:
                    district_records[dist_name] = {
                        "district": dist_name,
                        "period": period_name,
                    }

                for field_name, value in dist_data.items():
                    if field_name == "District":
                        continue

                    snake_field = to_snake_case(field_name)
                    if not snake_field or snake_field.startswith("col_"):
                        continue

                    key = f"{cat_name}__{snake_field}"
                    district_records[dist_name][key] = clean_value(value)
                    all_fields.add(key)

        if district_records:
            periods.append({
                "period": period_name,
                "districts": list(district_records.values()),
            })
            total_records += len(district_records)

    result = {
        "source": data.get("source", f"SLBC {slug.replace('-', ' ').title()}"),
        "state": slug,
        "description": f"Financial inclusion timeseries data for {slug.replace('-', ' ').title()}",
        "num_periods": len(periods),
        "total_records": total_records,
        "total_fields": len(all_fields),
        "periods": periods,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  Periods: {len(periods)}")
    print(f"  Total district-period records: {total_records}")
    print(f"  Total unique fields: {len(all_fields)}")
    print(f"  Output: {out_path}")

    # Show sample fields
    if all_fields:
        sample = sorted(all_fields)[:10]
        print(f"  Sample fields: {sample}")


if __name__ == "__main__":
    for slug, complete_name, min_dist in STATES:
        generate_timeseries(slug, complete_name, min_dist)
    print("\nDone!")
