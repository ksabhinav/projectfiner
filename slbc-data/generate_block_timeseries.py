#!/usr/bin/env python3
"""
Generate block-level timeseries JSONs from ne_blockwise_scrape.json.

Input: ne_blockwise_scrape.json
Output: public/slbc-data/{state}/{state}_block_timeseries.json for each state

Format:
{
  "periods": [
    {
      "period": "September 2025",
      "blocks": [
        {
          "block": "BHABANIPUR",
          "district": "BAJALI",
          "period": "September 2025",
          "blockwise_cdr__dep_rural": 22683.21,
          ...
        }
      ]
    }
  ]
}

Field naming: {report_key}__{header_normalized}
where header is lowercase, spaces replaced with underscores, special chars removed.
"""

import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(SCRIPT_DIR, "ne_blockwise_scrape.json")
PUBLIC_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "public", "slbc-data")

# State code -> directory slug
STATE_DIRS = {
    "AS": "assam",
    "MN": "manipur",
    "MZ": "mizoram",
    "NL": "nagaland",
    "TR": "tripura",
    "SK": "sikkim",
}

# Period ordering
MONTH_ORDER = {"March": 3, "June": 6, "September": 9, "December": 12}


def period_sort_key(period_str):
    """Convert 'June 2021' to (2021, 6) for sorting."""
    parts = period_str.split()
    if len(parts) != 2:
        return (0, 0)
    month = MONTH_ORDER.get(parts[0], 0)
    try:
        year = int(parts[1])
    except ValueError:
        year = 0
    return (year, month)


def normalize_header(h):
    """Normalize a header string to a field name."""
    h = h.strip().lower()
    # Remove common noise
    h = re.sub(r'[().,/\\]', ' ', h)
    h = re.sub(r'\s+', '_', h)
    h = re.sub(r'_+', '_', h)
    h = h.strip('_')
    # Remove leading numbers like "1_" if it's a column index
    h = re.sub(r'^(\d+)_', '', h)
    return h


def try_float(s):
    """Try to parse a string as a float. Returns the float or the original string."""
    if not s or not isinstance(s, str):
        return s
    s = s.strip().replace(",", "")
    if s in ("", "-", "N/A", "NA"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return s


def main():
    print(f"Loading {INPUT_PATH}...")
    with open(INPUT_PATH) as f:
        all_data = json.load(f)

    for state_code, state_dir in STATE_DIRS.items():
        if state_code not in all_data:
            print(f"  {state_code}: no data, skipping")
            continue

        state_data = all_data[state_code]
        print(f"\n  Processing {state_code} ({state_dir})...")

        # Collect all periods across all reports
        all_periods = set()
        for report_key in state_data:
            for period in state_data[report_key]:
                all_periods.add(period)

        sorted_periods = sorted(all_periods, key=period_sort_key)
        print(f"    Periods: {len(sorted_periods)} ({sorted_periods[0] if sorted_periods else 'none'} to {sorted_periods[-1] if sorted_periods else 'none'})")

        periods_list = []

        for period in sorted_periods:
            # For this period, collect all block data across all reports
            # Key: (district, block) -> { field: value }
            block_map = {}

            for report_key in state_data:
                if period not in state_data[report_key]:
                    continue

                report_data = state_data[report_key][period]
                headers = report_data.get("headers", [])
                blocks = report_data.get("blocks", [])

                if not headers or not blocks:
                    continue

                # Find district and block column indices
                district_idx = None
                block_idx = None
                for i, h in enumerate(headers):
                    hl = h.strip().lower()
                    if "district" in hl and district_idx is None:
                        district_idx = i
                    if "block" in hl and block_idx is None:
                        block_idx = i

                if block_idx is None:
                    # Try column 2 (common layout: Sl, District, Block, ...)
                    if len(headers) >= 3:
                        block_idx = 2
                        if district_idx is None:
                            district_idx = 1

                if district_idx is None:
                    district_idx = 1

                # Normalize headers for field names (skip first few metadata cols)
                field_start = max((block_idx or 2) + 1, 3)
                norm_headers = []
                for i in range(field_start, len(headers)):
                    nh = normalize_header(headers[i])
                    if nh:
                        norm_headers.append((i, f"{report_key}__{nh}"))

                for row in blocks:
                    if len(row) <= max(district_idx or 0, block_idx or 0):
                        continue

                    district = row[district_idx].strip().upper() if district_idx < len(row) else ""
                    block = row[block_idx].strip().upper() if block_idx is not None and block_idx < len(row) else ""

                    if not block or not district:
                        continue

                    key = (district, block)
                    if key not in block_map:
                        block_map[key] = {
                            "block": block,
                            "district": district,
                            "period": period,
                        }

                    for col_idx, field_name in norm_headers:
                        if col_idx < len(row):
                            val = try_float(row[col_idx])
                            block_map[key][field_name] = val

            if block_map:
                # Sort blocks by district then block name
                sorted_blocks = sorted(block_map.values(), key=lambda b: (b["district"], b["block"]))
                periods_list.append({
                    "period": period,
                    "blocks": sorted_blocks,
                })

        if not periods_list:
            print(f"    No block data for {state_code}, skipping")
            continue

        total_blocks = sum(len(p["blocks"]) for p in periods_list)
        print(f"    Total: {len(periods_list)} periods, {total_blocks} block-period records")

        # Write output
        out_dir = os.path.join(PUBLIC_DIR, state_dir)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{state_dir}_block_timeseries.json")

        output = {"periods": periods_list}
        with open(out_path, "w") as f:
            json.dump(output, f, ensure_ascii=False)

        file_size = os.path.getsize(out_path)
        print(f"    Output: {out_path} ({file_size / 1024 / 1024:.1f} MB)")

    print(f"\nDone!")


if __name__ == "__main__":
    main()
