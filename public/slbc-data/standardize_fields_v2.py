#!/usr/bin/env python3
"""
standardize_fields_v2.py — Cross-state field name standardization

Complements standardize_fields.py (which handles per-state fixes like Manipur
spacing, Meghalaya reorder, Bihar renames, abbreviations, typos, plurals).

This script handles the CROSS-STATE duplicate/inconsistent field names that
the audit found (~2500 HIGH-confidence duplicates). It:

  1. Loads each state's {state}_complete.json
  2. Applies category renames (cd_ratio -> credit_deposit_ratio, etc.)
  3. Applies comprehensive field rename maps at the human-readable level
  4. Strips numeric suffixes leaked from data values into field names
  5. Saves updated complete.json
  6. Regenerates timeseries JSON and CSV from the cleaned complete.json
  7. Updates quarterly CSVs

Run AFTER standardize_fields.py (v1).
"""

import csv
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent
STATES = [
    'assam', 'meghalaya', 'manipur', 'arunachal-pradesh',
    'mizoram', 'tripura', 'nagaland', 'sikkim', 'bihar', 'west-bengal'
]

# ═══════════════════════════════════════════════════════════════════════
# CATEGORY RENAMES — applied to complete.json table keys and quarterly
# CSV folder/file references
# ═══════════════════════════════════════════════════════════════════════

CATEGORY_RENAMES = {
    'cd_ratio': 'credit_deposit_ratio',
    'kcc_progress': 'kcc',
    'digital_payments': 'digital_transactions',
}

# ═══════════════════════════════════════════════════════════════════════
# FIELD RENAME MAPS — keyed by category
# Each map: { old_human_readable_name: new_human_readable_name }
# Applied to complete.json fields, district keys, and quarterly CSVs.
# ═══════════════════════════════════════════════════════════════════════

# Category-specific field renames
FIELD_RENAMES = {
    'credit_deposit_ratio': {
        'Deposit': 'Total Deposit',
        'deposit': 'Total Deposit',
        'Deposits': 'Total Deposit',
        'deposits': 'Total Deposit',
        'Advance': 'Total Advance',
        'advance': 'Total Advance',
        'Advances': 'Total Advance',
        'advances': 'Total Advance',
        'CD Ratio': 'Overall CD Ratio',
        'cd_ratio': 'Overall CD Ratio',
        'C:D Ratio': 'Overall CD Ratio',
        'Current C:D Ratio': 'Overall CD Ratio',
        'Current C:D Ratio (Cdr-1)': 'Overall CD Ratio',
        'No. Of Branch': 'Total Branch',
        'No. of Brs': 'Total Branch',
        'Br': 'Total Branch',
        'Branch': 'Total Branch',
        'Deposit Rural': 'Dep Rural',
        'Deposits Rural': 'Dep Rural',
        'Advance Rural': 'Adv Rural',
        'Advances Rural': 'Adv Rural',
    },
    'branch_network': {
        'Branch': 'Total Branch',
        'No. of Branches': 'Total Branch',
        'No. of Brs': 'Total Branch',
        'Total': 'Total Branch',
        'ATM': 'Total ATM',
        'No. of ATM': 'Total ATM',
        'BC': 'BC Total',
        'B/C': 'BC Total',
        'BC Fix': 'BC Fixed',
        'CSP Fixed': 'Out Of Total CSP, Fixed Point CSP',
        'Out Of Total CSP Outlet, Fixed Point CSP Outlets': 'Out Of Total CSP, Fixed Point CSP',
        'Out Of Total CSP Outlet, Other CSP Outlets': 'Out Of Total CSP,Other CSP',
    },
    'kcc': {
        'Number of Cardsissued': 'Number of Cards issued',
        'KCC Issuedduringqtr.': 'KCC Issued during qtr.',
        'Outstandingamount': 'Outstanding amount',
        'Outstanding Amt': 'Outstanding amount',
        'AH Outstanding Amt': 'AH Outstanding amount',
        'Fishery Card activated': 'Fishery Card Activated',
        'AH Card activated': 'AH Card Activated',
        'Fishery Total no. of KCC': 'Fishery Total No. of KCC',
        'Fishery No. of KCC': 'Fishery Total No. of KCC',
    },
    'pmjdy': {
        'PMJDY No.': 'Total PMJDY No.',
        'rupaycard_issued': 'No. of Rupay Card Issued',
        'rupaycar_d_issued': 'No. of Rupay Card Issued',
        'sum_of_rupaycard_issued': 'No. of Rupay Card Issued',
        'Rupay Card Issued No.': 'No. of Rupay Card Issued',
        'aadhaar_seeded': 'No. of Aadhaar Seeded',
        'aadhaar_card_seeded': 'No. of Aadhaar Seeded',
        'Aadhaar Seeded No.': 'No. of Aadhaar Seeded',
        'zero_balance_account': 'No. of Zero Balance A/C',
        'zero_balance_a_c_s': 'No. of Zero Balance A/C',
        'Zero Balance A/C No.': 'No. of Zero Balance A/C',
        'Amt Deposits Held In The A/C': 'Amt. Deposits held in the A/C',
        'female': 'Female No.',
        'male': 'Male No.',
        'total': 'Total PMJDY No.',
    },
    'aadhaar_authentication': {
        'Number of Aadhaar seeded CASA': 'No. of Aadhaar Seeded CASA',
        'Number of Aadhaar Seeded CASA': 'No. of Aadhaar Seeded CASA',
        'Aadhaar Seeded CASA': 'No. of Aadhaar Seeded CASA',
        'Number of operative CASA': 'No. of Operative CASA',
        'Number of Operative CASA': 'No. of Operative CASA',
        'Operative CASA': 'No. of Operative CASA',
        'Number of Authenticated CASA': 'No. of Authenticated CASA',
        'Authenticated CASA': 'No. of Authenticated CASA',
    },
    'shg': {
        'shg_credit_linkage': 'SHG Credit Linkage',
        'shg_credit_linkage_no': 'SHG Credit Linkage No.',
    },
}

# ═══════════════════════════════════════════════════════════════════════
# Statistics tracking
# ═══════════════════════════════════════════════════════════════════════

stats = defaultdict(lambda: defaultdict(int))
# stats[state][category] = count of renames


def to_snake(s):
    """Convert human-readable field name to snake_case."""
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = s.strip('_')
    return s


# ═══════════════════════════════════════════════════════════════════════
# Numeric suffix stripping
# ═══════════════════════════════════════════════════════════════════════

# Pattern: field name ending with _DIGITS where digits look like data values
# e.g. zero_balance_account_239234, total_no_pmjdy_a_c_48_65_561
NUMERIC_SUFFIX_RE = re.compile(r'^(.+?)(?:_\d{2,})+$')


def strip_numeric_suffix(field_name):
    """Strip trailing numeric suffixes that look like leaked data values.

    Only applies to snake_case-looking field names (lowercase with underscores).
    Returns (cleaned_name, was_changed).
    """
    # Only apply to fields that look like snake_case (have underscores, lowercase)
    if '_' not in field_name:
        return field_name, False
    # Don't touch fields that are clearly human-readable (have spaces or uppercase)
    if ' ' in field_name and not field_name.islower():
        return field_name, False

    m = NUMERIC_SUFFIX_RE.match(field_name)
    if m:
        cleaned = m.group(1)
        # Sanity: the base must be at least 3 chars and contain a letter
        if len(cleaned) >= 3 and re.search(r'[a-z]', cleaned):
            return cleaned, True
    return field_name, False


# ═══════════════════════════════════════════════════════════════════════
# Field renaming logic
# ═══════════════════════════════════════════════════════════════════════

def rename_field(field_name, category, state):
    """Apply field rename for a given category context.

    Returns (new_name, was_renamed).
    """
    original = field_name

    # Step 1: Strip numeric suffixes from snake_case fields
    field_name, stripped = strip_numeric_suffix(field_name)

    # Step 2: Look up category-specific renames
    # Use the canonical category name (after any category rename)
    cat_renames = FIELD_RENAMES.get(category, {})
    if field_name in cat_renames:
        field_name = cat_renames[field_name]

    changed = (field_name != original)
    return field_name, changed


def rename_category(cat_name):
    """Apply category rename. Returns (new_name, was_renamed)."""
    if cat_name in CATEGORY_RENAMES:
        return CATEGORY_RENAMES[cat_name], True
    return cat_name, False


# ═══════════════════════════════════════════════════════════════════════
# Process complete.json
# ═══════════════════════════════════════════════════════════════════════

def process_complete_json(state):
    """Process {state}_complete.json: rename categories and fields."""
    fpath = BASE_DIR / state / f'{state}_complete.json'
    if not fpath.exists():
        print(f'  [SKIP] complete.json not found')
        return None

    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    field_rename_count = 0
    cat_rename_count = 0
    numeric_strip_count = 0

    for q_key, q_val in data.get('quarters', {}).items():
        tables = q_val.get('tables', {})

        # Collect category renames needed for this quarter
        cat_renames_needed = {}
        for table_name in list(tables.keys()):
            new_cat, cat_changed = rename_category(table_name)
            if cat_changed:
                cat_renames_needed[table_name] = new_cat

        # Apply category renames
        for old_cat, new_cat in cat_renames_needed.items():
            if new_cat in tables:
                # Merge: new_cat already exists, merge old into it
                existing = tables[new_cat]
                old_table = tables.pop(old_cat)
                # Merge fields lists (add unique fields from old)
                existing_fields_set = set(existing.get('fields', []))
                for f in old_table.get('fields', []):
                    if f not in existing_fields_set:
                        existing['fields'].append(f)
                        existing_fields_set.add(f)
                # Merge district data
                for dist, dist_data in old_table.get('districts', {}).items():
                    if dist not in existing.get('districts', {}):
                        existing.setdefault('districts', {})[dist] = dist_data
                    else:
                        # Merge fields into existing district
                        for k, v in dist_data.items():
                            if k not in existing['districts'][dist] or not existing['districts'][dist][k]:
                                existing['districts'][dist][k] = v
            else:
                tables[new_cat] = tables.pop(old_cat)
            cat_rename_count += 1
            stats[state]['category_renames'] += 1

        # Now rename fields within each (possibly-renamed) category
        for table_name, table_data in tables.items():
            # Rename in fields list
            if 'fields' in table_data:
                new_fields = []
                seen_fields = set()
                for f_name in table_data['fields']:
                    new_name, changed = rename_field(f_name, table_name, state)
                    if changed:
                        field_rename_count += 1
                        stats[state][table_name] += 1
                    # Deduplicate fields list
                    if new_name not in seen_fields:
                        new_fields.append(new_name)
                        seen_fields.add(new_name)
                table_data['fields'] = new_fields

            # Rename keys in district data
            for dist_name in list(table_data.get('districts', {}).keys()):
                dist_data = table_data['districts'][dist_name]
                new_dist = {}
                for key, val in dist_data.items():
                    new_key, changed = rename_field(key, table_name, state)
                    if changed:
                        field_rename_count += 1
                    # Handle merge if rename causes duplicate
                    if new_key in new_dist:
                        existing = new_dist[new_key]
                        if not existing or existing == '' or existing is None:
                            new_dist[new_key] = val
                    else:
                        new_dist[new_key] = val
                table_data['districts'][dist_name] = new_dist

    print(f'  [complete.json] {cat_rename_count} cat renames, {field_rename_count} field renames')

    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return data


# ═══════════════════════════════════════════════════════════════════════
# Regenerate timeseries JSON from complete.json
# ═══════════════════════════════════════════════════════════════════════

# Quarter key to human-readable period label
def quarter_key_to_label(q_key):
    """Convert quarter key to human-readable label.

    Handles both formats:
      '2024-09' -> 'September 2024'
      'june_2024' -> 'June 2024'
      'sept_2025' -> 'September 2025'
    """
    month_names = {
        '01': 'January', '02': 'February', '03': 'March',
        '04': 'April', '05': 'May', '06': 'June',
        '07': 'July', '08': 'August', '09': 'September',
        '10': 'October', '11': 'November', '12': 'December',
    }
    word_months = {
        'january': 'January', 'february': 'February', 'march': 'March',
        'april': 'April', 'may': 'May', 'june': 'June',
        'july': 'July', 'august': 'August', 'september': 'September',
        'sept': 'September',
        'october': 'October', 'november': 'November', 'december': 'December',
        'dec': 'December',
    }

    # Try YYYY-MM format
    m = re.match(r'^(\d{4})-(\d{2})$', q_key)
    if m:
        year, month = m.groups()
        return f'{month_names.get(month, month)} {year}'

    # Try word_YYYY format (e.g. june_2024, sept_2025, december_2015)
    m = re.match(r'^([a-z]+)_(\d{4})$', q_key)
    if m:
        month_word, year = m.groups()
        label = word_months.get(month_word, month_word.capitalize())
        return f'{label} {year}'

    return q_key


def quarter_key_sort_value(q_key):
    """Return a sortable value for quarter keys."""
    m = re.match(r'^(\d{4})-(\d{2})$', q_key)
    if m:
        return q_key

    month_nums = {
        'january': '01', 'february': '02', 'march': '03',
        'april': '04', 'may': '05', 'june': '06',
        'july': '07', 'august': '08', 'september': '09', 'sept': '09',
        'october': '10', 'november': '11', 'december': '12', 'dec': '12',
    }
    m = re.match(r'^([a-z]+)_(\d{4})$', q_key)
    if m:
        month_word, year = m.groups()
        mm = month_nums.get(month_word, '00')
        return f'{year}-{mm}'
    return q_key


def rebuild_timeseries(state, complete_data):
    """Rebuild timeseries JSON and CSV from complete.json data."""

    if complete_data is None:
        return

    # Build timeseries structure
    periods = []
    all_ts_fields = set()

    sorted_quarters = sorted(complete_data.get('quarters', {}).keys(),
                              key=quarter_key_sort_value)

    for q_key in sorted_quarters:
        q_val = complete_data['quarters'][q_key]
        period_label = q_val.get('period', quarter_key_to_label(q_key))

        # Collect all districts across all tables for this quarter
        district_data = {}  # district_name -> {ts_field: value, ...}

        for table_name, table_data in q_val.get('tables', {}).items():
            for dist_name, dist_vals in table_data.get('districts', {}).items():
                if dist_name not in district_data:
                    district_data[dist_name] = {
                        'district': dist_name,
                        'period': period_label,
                    }
                for field_name, value in dist_vals.items():
                    snake_field = to_snake(field_name)
                    ts_key = f'{table_name}__{snake_field}'
                    all_ts_fields.add(ts_key)
                    district_data[dist_name][ts_key] = value

        if district_data:
            districts_list = sorted(district_data.values(), key=lambda d: d.get('district', ''))
            periods.append({
                'period': period_label,
                'districts': districts_list,
            })

    # Write timeseries JSON
    ts_json_path = BASE_DIR / state / f'{state}_fi_timeseries.json'
    ts_data = {
        'source': f'SLBC {state.replace("-", " ").title()}',
        'state': state,
        'description': f'Financial inclusion timeseries data for {state.replace("-", " ").title()}',
        'num_periods': len(periods),
        'total_records': sum(len(p['districts']) for p in periods),
        'total_fields': len(all_ts_fields) + 2,  # +2 for district, period
        'periods': periods,
    }

    with open(ts_json_path, 'w', encoding='utf-8') as f:
        json.dump(ts_data, f, indent=2, ensure_ascii=False)

    print(f'  [timeseries JSON] {len(periods)} periods, {len(all_ts_fields)} fields')

    # Write timeseries CSV (wide format: all districts x all quarters)
    ts_csv_path = BASE_DIR / state / f'{state}_fi_timeseries.csv'

    # Collect all columns
    fixed_cols = ['district', 'period']
    data_cols = sorted(all_ts_fields)
    all_cols = fixed_cols + data_cols

    with open(ts_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(all_cols)
        for period in periods:
            for dist in period['districts']:
                row = [dist.get(col, '') for col in all_cols]
                writer.writerow(row)

    print(f'  [timeseries CSV] {sum(len(p["districts"]) for p in periods)} rows, {len(all_cols)} cols')


# ═══════════════════════════════════════════════════════════════════════
# Update quarterly CSVs
# ═══════════════════════════════════════════════════════════════════════

def process_quarterly_csvs(state):
    """Process quarterly CSV files - rename headers and handle category renames."""
    quarterly_dir = BASE_DIR / state / 'quarterly'
    if not quarterly_dir.exists():
        print(f'  [quarterly CSVs] directory not found, skipping')
        return

    total_renames = 0
    total_files = 0
    cat_file_renames = 0

    for period_dir in sorted(quarterly_dir.iterdir()):
        if not period_dir.is_dir():
            continue
        for csv_file in sorted(period_dir.glob('*.csv')):
            try:
                with open(csv_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    try:
                        headers = next(reader)
                    except StopIteration:
                        continue
                    rows = list(reader)
            except Exception:
                continue

            # Determine category from filename
            cat_name = csv_file.stem  # e.g., "credit_deposit_ratio"
            canonical_cat, cat_changed = rename_category(cat_name)

            # Apply field renames using the canonical category
            file_renames = 0
            new_headers = []
            for h in headers:
                new_h, changed = rename_field(h, canonical_cat, state)
                new_headers.append(new_h)
                if changed:
                    file_renames += 1

            needs_write = file_renames > 0 or cat_changed

            if file_renames > 0:
                # Handle merges from duplicate headers
                new_headers, rows, _ = merge_duplicate_columns(new_headers, rows)
                total_renames += file_renames

            if needs_write:
                # Write back (possibly to new filename if category renamed)
                target_file = csv_file
                if cat_changed:
                    target_file = csv_file.parent / f'{canonical_cat}.csv'
                    if target_file != csv_file and csv_file.exists():
                        # If target already exists, we'd need to merge, but for simplicity
                        # just rename (the old file gets replaced)
                        pass
                    cat_file_renames += 1

                with open(target_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(new_headers)
                    writer.writerows(rows)

                # Remove old file if renamed
                if cat_changed and target_file != csv_file and csv_file.exists():
                    csv_file.unlink()

            total_files += 1

    print(f'  [quarterly CSVs] {total_files} files, {total_renames} header renames, {cat_file_renames} file renames')


def merge_duplicate_columns(headers, rows):
    """If renaming causes duplicate columns, merge them."""
    if len(headers) == len(set(headers)):
        return headers, rows, 0

    col_indices = defaultdict(list)
    for i, h in enumerate(headers):
        col_indices[h].append(i)

    merge_count = 0
    unique_headers = []
    keep_indices = []
    merge_map = {}

    seen = set()
    for i, h in enumerate(headers):
        if h not in seen:
            seen.add(h)
            unique_headers.append(h)
            keep_indices.append(i)
            if len(col_indices[h]) > 1:
                merge_map[i] = col_indices[h][1:]
                merge_count += len(col_indices[h]) - 1

    new_rows = []
    for row in rows:
        new_row = list(row) + [''] * max(0, len(headers) - len(row))
        for primary_idx, secondary_indices in merge_map.items():
            for sec_idx in secondary_indices:
                if sec_idx < len(new_row):
                    pv = new_row[primary_idx]
                    sv = new_row[sec_idx]
                    if not pv or str(pv).strip() == '':
                        new_row[primary_idx] = sv
        merged_row = [new_row[idx] if idx < len(new_row) else '' for idx in keep_indices]
        new_rows.append(merged_row)

    return unique_headers, new_rows, merge_count


# ═══════════════════════════════════════════════════════════════════════
# Backup
# ═══════════════════════════════════════════════════════════════════════

def backup_complete_json(state):
    """Create a backup of complete.json before modifying."""
    fpath = BASE_DIR / state / f'{state}_complete.json'
    backup = BASE_DIR / state / f'{state}_complete.json.bak_v2'
    if fpath.exists() and not backup.exists():
        shutil.copy2(fpath, backup)
        print(f'  [backup] created {backup.name}')


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    print('=' * 70)
    print('SLBC Cross-State Field Standardization v2')
    print('=' * 70)

    for state in STATES:
        state_dir = BASE_DIR / state
        if not state_dir.exists():
            print(f'\n--- {state.upper()} --- [NOT FOUND]')
            continue

        print(f'\n--- {state.upper()} ---')

        # 1. Backup
        backup_complete_json(state)

        # 2. Process complete.json (categories + fields)
        complete_data = process_complete_json(state)

        # 3. Regenerate timeseries JSON + CSV from cleaned complete.json
        if complete_data is not None:
            rebuild_timeseries(state, complete_data)

        # 4. Update quarterly CSVs
        process_quarterly_csvs(state)

    # Print statistics
    print('\n' + '=' * 70)
    print('STATISTICS — Renames per state per category')
    print('=' * 70)

    grand_total = 0
    for state in STATES:
        if state not in stats:
            continue
        state_total = sum(stats[state].values())
        grand_total += state_total
        print(f'\n  {state.upper()} ({state_total} total renames):')
        for cat, count in sorted(stats[state].items()):
            print(f'    {cat:40s}: {count:5d}')

    print(f'\n  GRAND TOTAL: {grand_total} renames')
    print('\n' + '=' * 70)
    print('Done.')


if __name__ == '__main__':
    main()
