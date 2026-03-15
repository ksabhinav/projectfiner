#!/usr/bin/env python3
"""
Redistribute date-embedded historical values to their correct quarters.

The previous fix (fix_date_fields.py) kept only the current quarter's value
and DROPPED historical values. This script recovers those historical values
from the pre-fix JSON (via git) and places them into their correct quarters.

Affected:
  - Tripura: credit_deposit_ratio, branch_network, bc_coverage, pmjdy
  - Assam: flc_report
"""

import json
import csv
import re
import subprocess
from pathlib import Path
from collections import defaultdict
from copy import deepcopy

BASE = Path("/Users/abhinav/Downloads/projectfiner/public/slbc-data")
REPO = Path("/Users/abhinav/Downloads/projectfiner")

# ── Month parsing utilities ──────────────────────────────────────────

MONTH_TO_NUM = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

NUM_TO_MONTH = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April',
    5: 'May', 6: 'June', 7: 'July', 8: 'August',
    9: 'September', 10: 'October', 11: 'November', 12: 'December',
}

MONTH_LAST_DAY = {
    1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
}


def parse_date_from_field(field_name):
    """
    Extract (month_num, year) from a field name containing a date.
    Returns (month_num, year) or None.
    """
    m = re.search(
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"[\s'\u2018\u2019\u0027]*(\d{2,4})",
        field_name, re.IGNORECASE
    )
    if m:
        month_str = m.group(1).lower().rstrip("'\u2018\u2019")
        year_str = m.group(2)
        month_num = MONTH_TO_NUM.get(month_str)
        if month_num:
            year = int(year_str)
            if year < 100:
                year += 2000
            return (month_num, year)
    return None


def date_to_quarter_key(month, year):
    """Convert (month, year) to quarter key like '2024-12'."""
    return f"{year:04d}-{month:02d}"


def make_quarter_metadata(quarter_key):
    """Create period, as_on_date, fy for a new quarter."""
    parts = quarter_key.split('-')
    year = int(parts[0])
    month = int(parts[1])

    period = f"{NUM_TO_MONTH[month]} {year}"
    day = MONTH_LAST_DAY[month]
    as_on_date = f"{day:02d}-{month:02d}-{year}"

    # Determine FY: April-March cycle
    if month >= 4:
        fy_start = year
    else:
        fy_start = year - 1
    fy = f"{fy_start}-{(fy_start + 1) % 100:02d}"

    return period, as_on_date, fy


def ensure_quarter_exists(data, quarter_key):
    """Ensure a quarter exists in the data, creating it if needed."""
    if quarter_key not in data['quarters']:
        period, as_on_date, fy = make_quarter_metadata(quarter_key)
        data['quarters'][quarter_key] = {
            'period': period,
            'as_on_date': as_on_date,
            'fy': fy,
            'tables': {}
        }
    return data['quarters'][quarter_key]


def ensure_table_exists(quarter, category):
    """Ensure a table/category exists in a quarter."""
    if category not in quarter['tables']:
        quarter['tables'][category] = {
            'page': None,
            'fields': [],
            'num_districts': 0,
            'districts': {}
        }
    return quarter['tables'][category]


def load_old_json(state_slug):
    """Load the pre-fix JSON from git history (HEAD~2)."""
    result = subprocess.run(
        ['git', 'show', f'HEAD~2:public/slbc-data/{state_slug}/{state_slug}_complete.json'],
        capture_output=True, text=True, cwd=str(REPO)
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to load old JSON for {state_slug}: {result.stderr}")
    return json.loads(result.stdout)


# ── Tripura credit_deposit_ratio redistribution ──────────────────────

def redistribute_tripura_cdr(old_data, current_data):
    """
    From old data, extract historical CD Ratio values and place them
    into their correct quarters in current_data.
    """
    stats = {'values_redistributed': 0, 'quarters_created': 0, 'quarters_backfilled': 0}

    for source_qk in sorted(old_data['quarters'].keys()):
        source_q = old_data['quarters'][source_qk]
        if 'credit_deposit_ratio' not in source_q.get('tables', {}):
            continue

        table = source_q['tables']['credit_deposit_ratio']
        fields = table.get('fields', [])
        districts = table.get('districts', {})

        for field in fields:
            # Skip non-date fields
            if re.search(r'since|y-o-y|q-o-q', field, re.IGNORECASE):
                continue

            # Parse the date from the field name
            parsed = parse_date_from_field(field)
            if not parsed:
                continue

            target_qk = date_to_quarter_key(parsed[0], parsed[1])

            # Skip if this field refers to the current quarter (already handled)
            if target_qk == source_qk:
                continue

            # Get or create the target quarter
            existed_before = target_qk in current_data['quarters']
            target_q = ensure_quarter_exists(current_data, target_qk)
            if not existed_before:
                stats['quarters_created'] += 1

            target_table = ensure_table_exists(target_q, 'credit_deposit_ratio')

            # Ensure 'CD Ratio' is in the fields list
            if 'CD Ratio' not in target_table['fields']:
                target_table['fields'].append('CD Ratio')

            # Redistribute district data
            backfilled = False
            for dist_name, dist_data in districts.items():
                val = dist_data.get(field, '')
                if not val or not str(val).strip():
                    continue

                if dist_name not in target_table['districts']:
                    target_table['districts'][dist_name] = {}

                # Don't overwrite existing data (quarter's own data is more authoritative)
                if 'CD Ratio' not in target_table['districts'][dist_name] or \
                   not target_table['districts'][dist_name]['CD Ratio'] or \
                   target_table['districts'][dist_name]['CD Ratio'] == '':
                    target_table['districts'][dist_name]['CD Ratio'] = val
                    stats['values_redistributed'] += 1
                    backfilled = True

            if backfilled:
                # Update num_districts
                target_table['num_districts'] = len(target_table['districts'])

        # Also handle QoQ/YoY for the current quarter
        for field in fields:
            if re.search(r'q-o-q', field, re.IGNORECASE):
                # Find the current quarter's data
                target_qk = source_qk
                if target_qk in current_data['quarters']:
                    target_q = current_data['quarters'][target_qk]
                    if 'credit_deposit_ratio' in target_q['tables']:
                        target_table = target_q['tables']['credit_deposit_ratio']
                        if 'CD Ratio QoQ Change' not in target_table['fields']:
                            target_table['fields'].append('CD Ratio QoQ Change')
                        for dist_name, dist_data in districts.items():
                            val = dist_data.get(field, '')
                            if val and str(val).strip() and dist_name in target_table['districts']:
                                if 'CD Ratio QoQ Change' not in target_table['districts'][dist_name] or \
                                   not target_table['districts'][dist_name].get('CD Ratio QoQ Change'):
                                    target_table['districts'][dist_name]['CD Ratio QoQ Change'] = val

            if re.search(r'y-o-y', field, re.IGNORECASE):
                target_qk = source_qk
                if target_qk in current_data['quarters']:
                    target_q = current_data['quarters'][target_qk]
                    if 'credit_deposit_ratio' in target_q['tables']:
                        target_table = target_q['tables']['credit_deposit_ratio']
                        if 'CD Ratio YoY Change' not in target_table['fields']:
                            target_table['fields'].append('CD Ratio YoY Change')
                        for dist_name, dist_data in districts.items():
                            val = dist_data.get(field, '')
                            if val and str(val).strip() and dist_name in target_table['districts']:
                                if 'CD Ratio YoY Change' not in target_table['districts'][dist_name] or \
                                   not target_table['districts'][dist_name].get('CD Ratio YoY Change'):
                                    target_table['districts'][dist_name]['CD Ratio YoY Change'] = val

    return stats


# ── Tripura branch_network redistribution ─────────────────────────────

def redistribute_tripura_branch_network(old_data, current_data):
    """Redistribute historical branch_network values."""
    stats = {'values_redistributed': 0, 'quarters_created': 0}

    for source_qk in sorted(old_data['quarters'].keys()):
        source_q = old_data['quarters'][source_qk]
        if 'branch_network' not in source_q.get('tables', {}):
            continue

        table = source_q['tables']['branch_network']
        fields = table.get('fields', [])
        districts = table.get('districts', {})

        for field in fields:
            # Parse "No. of ATM as on [Date]" or "No. of Branches as on [Date]"
            generic_name = None
            m = re.match(r'No\.\s*of\s+(ATMs?)\s+as\s+on\s+(.+)', field, re.IGNORECASE)
            if m:
                generic_name = 'No. of ATM'
                date_part = m.group(2)
            else:
                m = re.match(r'No\.\s*of\s+(Branch(?:es)?)\s+as\s+on\s+(.+)', field, re.IGNORECASE)
                if m:
                    generic_name = 'No. of Branches'
                    date_part = m.group(2)

            if not generic_name:
                continue

            parsed = parse_date_from_field(date_part)
            if not parsed:
                continue

            target_qk = date_to_quarter_key(parsed[0], parsed[1])

            # Skip if same as source quarter
            if target_qk == source_qk:
                continue

            existed_before = target_qk in current_data['quarters']
            target_q = ensure_quarter_exists(current_data, target_qk)
            if not existed_before:
                stats['quarters_created'] += 1

            target_table = ensure_table_exists(target_q, 'branch_network')

            if generic_name not in target_table['fields']:
                target_table['fields'].append(generic_name)

            for dist_name, dist_data in districts.items():
                val = dist_data.get(field, '')
                if not val or not str(val).strip():
                    continue

                if dist_name not in target_table['districts']:
                    target_table['districts'][dist_name] = {}

                if generic_name not in target_table['districts'][dist_name] or \
                   not target_table['districts'][dist_name][generic_name] or \
                   target_table['districts'][dist_name][generic_name] == '':
                    target_table['districts'][dist_name][generic_name] = val
                    stats['values_redistributed'] += 1

            target_table['num_districts'] = len(target_table['districts'])

    return stats


# ── Tripura bc_coverage redistribution ────────────────────────────────

def redistribute_tripura_bc_coverage(old_data, current_data):
    """Redistribute historical bc_coverage values."""
    stats = {'values_redistributed': 0, 'quarters_created': 0}

    for source_qk in sorted(old_data['quarters'].keys()):
        source_q = old_data['quarters'][source_qk]
        if 'bc_coverage' not in source_q.get('tables', {}):
            continue

        table = source_q['tables']['bc_coverage']
        fields = table.get('fields', [])
        districts = table.get('districts', {})

        for field in fields:
            m = re.match(r'No\.\s*of\s+BC/CSP\s+as\s+on\s+(.+)', field, re.IGNORECASE)
            if not m:
                continue

            parsed = parse_date_from_field(m.group(1))
            if not parsed:
                continue

            target_qk = date_to_quarter_key(parsed[0], parsed[1])
            if target_qk == source_qk:
                continue

            existed_before = target_qk in current_data['quarters']
            target_q = ensure_quarter_exists(current_data, target_qk)
            if not existed_before:
                stats['quarters_created'] += 1

            target_table = ensure_table_exists(target_q, 'bc_coverage')
            generic_name = 'No. of BC/CSP'

            if generic_name not in target_table['fields']:
                target_table['fields'].append(generic_name)

            for dist_name, dist_data in districts.items():
                val = dist_data.get(field, '')
                if not val or not str(val).strip():
                    continue

                if dist_name not in target_table['districts']:
                    target_table['districts'][dist_name] = {}

                if generic_name not in target_table['districts'][dist_name] or \
                   not target_table['districts'][dist_name][generic_name] or \
                   target_table['districts'][dist_name][generic_name] == '':
                    target_table['districts'][dist_name][generic_name] = val
                    stats['values_redistributed'] += 1

            target_table['num_districts'] = len(target_table['districts'])

    return stats


# ── Tripura pmjdy redistribution ─────────────────────────────────────

def redistribute_tripura_pmjdy(old_data, current_data):
    """Redistribute historical pmjdy values."""
    stats = {'values_redistributed': 0, 'quarters_created': 0}

    for source_qk in sorted(old_data['quarters'].keys()):
        source_q = old_data['quarters'][source_qk]
        if 'pmjdy' not in source_q.get('tables', {}):
            continue

        table = source_q['tables']['pmjdy']
        fields = table.get('fields', [])
        districts = table.get('districts', {})

        for field in fields:
            # Match "No. of PMJDY accounts as on [Date]" or "No. of Women PMJDY accounts as on [Date]"
            generic_name = None
            m = re.match(r'No\.\s*of\s+Women\s+PMJDY\s+accounts?\s+as\s+on\s+(.+)', field, re.IGNORECASE)
            if m:
                generic_name = 'No. of Women PMJDY Accounts'
                date_part = m.group(1)
            else:
                m = re.match(r'No\.\s*of\s+PMJDY\s+accounts?\s+as\s+on\s+(.+)', field, re.IGNORECASE)
                if m:
                    generic_name = 'No. of PMJDY Accounts'
                    date_part = m.group(1)

            if not generic_name:
                continue

            parsed = parse_date_from_field(date_part)
            if not parsed:
                continue

            target_qk = date_to_quarter_key(parsed[0], parsed[1])
            if target_qk == source_qk:
                continue

            existed_before = target_qk in current_data['quarters']
            target_q = ensure_quarter_exists(current_data, target_qk)
            if not existed_before:
                stats['quarters_created'] += 1

            target_table = ensure_table_exists(target_q, 'pmjdy')

            if generic_name not in target_table['fields']:
                target_table['fields'].append(generic_name)

            for dist_name, dist_data in districts.items():
                val = dist_data.get(field, '')
                if not val or not str(val).strip():
                    continue
                # Skip obviously bad data (multi-value cells like "148983 150224 42282")
                if len(str(val).split()) > 1:
                    continue

                if dist_name not in target_table['districts']:
                    target_table['districts'][dist_name] = {}

                if generic_name not in target_table['districts'][dist_name] or \
                   not target_table['districts'][dist_name][generic_name] or \
                   target_table['districts'][dist_name][generic_name] == '':
                    target_table['districts'][dist_name][generic_name] = val
                    stats['values_redistributed'] += 1

            target_table['num_districts'] = len(target_table['districts'])

    return stats


# ── Assam flc_report redistribution ──────────────────────────────────

def parse_assam_flc_quarter_date(field_name):
    """
    Parse the quarter date from an Assam FLC field name.
    Returns (month_num, year) or None for quarter-specific fields.
    Returns 'total' for FY total fields.
    """
    m = re.search(
        r"(?:the\s+)(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"['\s]*(\d{2,4})\s+Quarter",
        field_name, re.IGNORECASE
    )
    if m:
        month_str = m.group(1).lower()
        year_str = m.group(2)
        month_num = MONTH_TO_NUM.get(month_str)
        if month_num:
            year = int(year_str)
            if year < 100:
                year += 2000
            return (month_num, year)

    if re.search(r'Total.*FY', field_name, re.IGNORECASE):
        return 'total'

    return None


def redistribute_assam_flc(old_data, current_data):
    """
    Redistribute historical FLC camp counts to their correct quarters.
    Each quarter's FLC table has data for all 4 quarters of its FY.
    We redistribute each quarter-specific value to its proper quarter.
    """
    stats = {'values_redistributed': 0, 'quarters_created': 0}

    for source_qk in sorted(old_data['quarters'].keys()):
        source_q = old_data['quarters'][source_qk]
        if 'flc_report' not in source_q.get('tables', {}):
            continue

        table = source_q['tables']['flc_report']
        fields = table.get('fields', [])
        districts = table.get('districts', {})

        for field in fields:
            parsed = parse_assam_flc_quarter_date(field)
            if parsed is None or parsed == 'total':
                continue

            month_num, year = parsed
            target_qk = date_to_quarter_key(month_num, year)

            # Skip if same as source quarter
            if target_qk == source_qk:
                continue

            existed_before = target_qk in current_data['quarters']
            target_q = ensure_quarter_exists(current_data, target_qk)
            if not existed_before:
                stats['quarters_created'] += 1

            target_table = ensure_table_exists(target_q, 'flc_report')
            generic_name = 'No. of Camps Conducted'

            if generic_name not in target_table['fields']:
                target_table['fields'].append(generic_name)

            for dist_name, dist_data in districts.items():
                val = dist_data.get(field, '')
                if not val or not str(val).strip():
                    continue
                # Skip "NOT YET" / "Not Yet" values
                if 'not yet' in str(val).lower():
                    continue

                if dist_name not in target_table['districts']:
                    target_table['districts'][dist_name] = {}

                if generic_name not in target_table['districts'][dist_name] or \
                   not target_table['districts'][dist_name][generic_name] or \
                   target_table['districts'][dist_name][generic_name] == '':
                    target_table['districts'][dist_name][generic_name] = val
                    stats['values_redistributed'] += 1

            target_table['num_districts'] = len(target_table['districts'])

    # Also ensure the current quarter's own value is stored with generic name
    for source_qk in sorted(old_data['quarters'].keys()):
        source_q = old_data['quarters'][source_qk]
        if 'flc_report' not in source_q.get('tables', {}):
            continue

        table = source_q['tables']['flc_report']
        fields = table.get('fields', [])
        districts = table.get('districts', {})

        for field in fields:
            parsed = parse_assam_flc_quarter_date(field)
            if parsed is None or parsed == 'total':
                # Handle total and non-camp fields in current quarter
                if parsed == 'total' and source_qk in current_data['quarters']:
                    target_q = current_data['quarters'][source_qk]
                    target_table = ensure_table_exists(target_q, 'flc_report')
                    generic_name = 'Total No. of Camps (FY)'
                    if generic_name not in target_table['fields']:
                        target_table['fields'].append(generic_name)
                    for dist_name, dist_data in districts.items():
                        val = dist_data.get(field, '')
                        if val and str(val).strip():
                            if dist_name not in target_table['districts']:
                                target_table['districts'][dist_name] = {}
                            if generic_name not in target_table['districts'][dist_name] or \
                               not target_table['districts'][dist_name][generic_name]:
                                target_table['districts'][dist_name][generic_name] = val
                continue

            month_num, year = parsed
            target_qk = date_to_quarter_key(month_num, year)

            # Only handle current quarter's own value here
            if target_qk == source_qk:
                if source_qk in current_data['quarters']:
                    target_q = current_data['quarters'][source_qk]
                    target_table = ensure_table_exists(target_q, 'flc_report')
                    generic_name = 'No. of Camps Conducted'
                    if generic_name not in target_table['fields']:
                        target_table['fields'].append(generic_name)
                    for dist_name, dist_data in districts.items():
                        val = dist_data.get(field, '')
                        if val and str(val).strip() and 'not yet' not in str(val).lower():
                            if dist_name not in target_table['districts']:
                                target_table['districts'][dist_name] = {}
                            if generic_name not in target_table['districts'][dist_name] or \
                               not target_table['districts'][dist_name][generic_name]:
                                target_table['districts'][dist_name][generic_name] = val

    # Also carry over 'No of rural branches in district' for each quarter
    for source_qk in sorted(old_data['quarters'].keys()):
        source_q = old_data['quarters'][source_qk]
        if 'flc_report' not in source_q.get('tables', {}):
            continue

        table = source_q['tables']['flc_report']
        districts = table.get('districts', {})

        for field in table.get('fields', []):
            if 'rural branch' in field.lower():
                if source_qk in current_data['quarters']:
                    target_q = current_data['quarters'][source_qk]
                    target_table = ensure_table_exists(target_q, 'flc_report')
                    if field not in target_table['fields']:
                        target_table['fields'].append(field)
                    for dist_name, dist_data in districts.items():
                        val = dist_data.get(field, '')
                        if val and str(val).strip():
                            if dist_name not in target_table['districts']:
                                target_table['districts'][dist_name] = {}
                            if field not in target_table['districts'][dist_name] or \
                               not target_table['districts'][dist_name].get(field):
                                target_table['districts'][dist_name][field] = val

    return stats


# ── Timeseries / CSV regeneration ─────────────────────────────────────

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


def regenerate_quarterly_csvs(data, quarterly_dir):
    """Regenerate all quarterly CSVs from the JSON."""
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


def regenerate_timeseries(data, state_dir, state_slug):
    """Regenerate timeseries CSV and JSON from data."""
    all_records = []
    all_field_keys = set()
    quarters = data.get("quarters", {})

    def make_ts_key(tname, fld):
        key = f"{tname}__{fld}"
        norm_key = re.sub(r'[^a-z0-9_/()&.,%]+', '_', key.lower().replace(' ', '_'))
        norm_key = re.sub(r'_+', '_', norm_key).strip('_')
        norm_key = normalize_timeseries_key(norm_key)
        return norm_key

    for qname, q in quarters.items():
        for tname, table in q.get("tables", {}).items():
            for dist_name, fields in table.get("districts", {}).items():
                for fld in fields.keys():
                    all_field_keys.add(make_ts_key(tname, fld))

    sorted_fields = sorted(all_field_keys)
    periods_data = {}

    for qname in sorted(quarters.keys()):
        q = quarters[qname]
        period = q.get("period", qname)
        as_on = q.get("as_on_date", "")
        fy = q.get("fy", "")
        quarter_districts = {}
        for tname, table in q.get("tables", {}).items():
            for dist_name, fields in table.get("districts", {}).items():
                if dist_name not in quarter_districts:
                    quarter_districts[dist_name] = {
                        "district": dist_name, "period": period,
                        "as_on_date": as_on, "fy": fy,
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
                "period": period, "num_districts": len(quarter_districts), "districts": [],
            }
        periods_data[period]["districts"] = [
            quarter_districts[d] for d in sorted(quarter_districts.keys())
        ]

    csv_path = state_dir / f"{state_slug}_fi_timeseries.csv"
    csv_columns = ["district", "period", "as_on_date", "fy"] + sorted_fields
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction='ignore')
        writer.writeheader()
        for record in all_records:
            writer.writerow(record)

    json_path = state_dir / f"{state_slug}_fi_timeseries.json"
    period_dates = {}
    for r in all_records:
        if r["period"] not in period_dates and r.get("as_on_date"):
            period_dates[r["period"]] = r["as_on_date"]

    def parse_date_str(d):
        try:
            parts = d.split("-")
            return (int(parts[2]), int(parts[1]), int(parts[0]))
        except:
            return (0, 0, 0)

    sorted_periods = sorted(periods_data.keys(),
                           key=lambda p: parse_date_str(period_dates.get(p, "01-01-1900")))
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

    return len(sorted_fields), len(periods_data)


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("REDISTRIBUTE DATE-EMBEDDED HISTORICAL VALUES")
    print("=" * 70)

    # ── Record BEFORE state ──
    print("\n--- BEFORE ---")
    for state, slug in [('tripura', 'tripura'), ('assam', 'assam')]:
        json_path = BASE / state / f"{slug}_complete.json"
        with open(json_path) as f:
            data = json.load(f)
        n_quarters = len(data['quarters'])
        cdr_quarters = sum(1 for q in data['quarters'].values()
                          if 'credit_deposit_ratio' in q.get('tables', {}))
        print(f"  {state}: {n_quarters} quarters total, {cdr_quarters} with credit_deposit_ratio")

        csv_path = BASE / state / f"{slug}_fi_timeseries.csv"
        if csv_path.exists():
            with open(csv_path) as f:
                header = next(csv.reader(f))
            print(f"  Timeseries: {len(header)} columns")

    # ── Load old JSONs from git ──
    print("\n--- Loading old JSONs from git (HEAD~2) ---")
    old_tripura = load_old_json('tripura')
    old_assam = load_old_json('assam')
    print(f"  Old Tripura: {len(old_tripura['quarters'])} quarters")
    print(f"  Old Assam: {len(old_assam['quarters'])} quarters")

    # ── Load current JSONs ──
    with open(BASE / "tripura" / "tripura_complete.json") as f:
        tripura_data = json.load(f)
    with open(BASE / "assam" / "assam_complete.json") as f:
        assam_data = json.load(f)

    # ── Process Tripura ──
    print("\n--- Redistributing Tripura credit_deposit_ratio ---")
    cdr_stats = redistribute_tripura_cdr(old_tripura, tripura_data)
    for k, v in sorted(cdr_stats.items()):
        print(f"  {k}: {v}")

    print("\n--- Redistributing Tripura branch_network ---")
    bn_stats = redistribute_tripura_branch_network(old_tripura, tripura_data)
    for k, v in sorted(bn_stats.items()):
        print(f"  {k}: {v}")

    print("\n--- Redistributing Tripura bc_coverage ---")
    bc_stats = redistribute_tripura_bc_coverage(old_tripura, tripura_data)
    for k, v in sorted(bc_stats.items()):
        print(f"  {k}: {v}")

    print("\n--- Redistributing Tripura pmjdy ---")
    pmjdy_stats = redistribute_tripura_pmjdy(old_tripura, tripura_data)
    for k, v in sorted(pmjdy_stats.items()):
        print(f"  {k}: {v}")

    # ── Process Assam ──
    print("\n--- Redistributing Assam flc_report ---")
    flc_stats = redistribute_assam_flc(old_assam, assam_data)
    for k, v in sorted(flc_stats.items()):
        print(f"  {k}: {v}")

    # ── Save updated JSONs ──
    print("\n--- Saving updated JSONs ---")
    with open(BASE / "tripura" / "tripura_complete.json", 'w') as f:
        json.dump(tripura_data, f, indent=2, ensure_ascii=False)
    print("  Saved tripura_complete.json")

    with open(BASE / "assam" / "assam_complete.json", 'w') as f:
        json.dump(assam_data, f, indent=2, ensure_ascii=False)
    print("  Saved assam_complete.json")

    # ── Regenerate CSVs and timeseries ──
    print("\n--- Regenerating Tripura CSVs and timeseries ---")
    regenerate_quarterly_csvs(tripura_data, BASE / "tripura" / "quarterly")
    tri_cols, tri_periods = regenerate_timeseries(tripura_data, BASE / "tripura", "tripura")
    print(f"  Timeseries: {tri_cols} columns, {tri_periods} periods")

    print("\n--- Regenerating Assam CSVs and timeseries ---")
    regenerate_quarterly_csvs(assam_data, BASE / "assam" / "quarterly")
    asm_cols, asm_periods = regenerate_timeseries(assam_data, BASE / "assam", "assam")
    print(f"  Timeseries: {asm_cols} columns, {asm_periods} periods")

    # ── AFTER state ──
    print("\n--- AFTER ---")
    for state, slug in [('tripura', 'tripura'), ('assam', 'assam')]:
        json_path = BASE / state / f"{slug}_complete.json"
        with open(json_path) as f:
            data = json.load(f)
        n_quarters = len(data['quarters'])
        cdr_quarters = sum(1 for q in data['quarters'].values()
                          if 'credit_deposit_ratio' in q.get('tables', {}))
        print(f"  {state}: {n_quarters} quarters total, {cdr_quarters} with credit_deposit_ratio")

        csv_path = BASE / state / f"{slug}_fi_timeseries.csv"
        if csv_path.exists():
            with open(csv_path) as f:
                header = next(csv.reader(f))
            print(f"  Timeseries: {len(header)} columns")

    # ── VERIFICATION ──
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    # Verify Tripura CDR continuity
    print("\n  Tripura credit_deposit_ratio — CD Ratio per quarter:")
    with open(BASE / "tripura" / "tripura_complete.json") as f:
        data = json.load(f)
    for qk in sorted(data['quarters'].keys()):
        if 'credit_deposit_ratio' in data['quarters'][qk].get('tables', {}):
            t = data['quarters'][qk]['tables']['credit_deposit_ratio']
            fields = t.get('fields', [])
            dists = t.get('districts', {})
            n_dists = len(dists)
            # Show first district's CD Ratio
            sample_dist = sorted(dists.keys())[0] if dists else 'N/A'
            cd_val = dists.get(sample_dist, {}).get('CD Ratio', 'MISSING')
            print(f"    {qk}: fields={fields}, n_districts={n_dists}, {sample_dist}={cd_val}")

    # Verify Tripura branch_network
    print("\n  Tripura branch_network — fields per quarter:")
    for qk in sorted(data['quarters'].keys()):
        if 'branch_network' in data['quarters'][qk].get('tables', {}):
            t = data['quarters'][qk]['tables']['branch_network']
            fields = t.get('fields', [])
            n_dists = len(t.get('districts', {}))
            print(f"    {qk}: fields={fields}, n_districts={n_dists}")

    # Verify Tripura bc_coverage
    print("\n  Tripura bc_coverage — fields per quarter:")
    for qk in sorted(data['quarters'].keys()):
        if 'bc_coverage' in data['quarters'][qk].get('tables', {}):
            t = data['quarters'][qk]['tables']['bc_coverage']
            fields = t.get('fields', [])
            n_dists = len(t.get('districts', {}))
            print(f"    {qk}: fields={fields}, n_districts={n_dists}")

    # Verify Tripura pmjdy
    print("\n  Tripura pmjdy — fields per quarter:")
    for qk in sorted(data['quarters'].keys()):
        if 'pmjdy' in data['quarters'][qk].get('tables', {}):
            t = data['quarters'][qk]['tables']['pmjdy']
            fields = t.get('fields', [])
            n_dists = len(t.get('districts', {}))
            print(f"    {qk}: fields={fields}, n_districts={n_dists}")

    # Verify Assam flc_report
    print("\n  Assam flc_report — fields per quarter:")
    with open(BASE / "assam" / "assam_complete.json") as f:
        data = json.load(f)
    for qk in sorted(data['quarters'].keys()):
        if 'flc_report' in data['quarters'][qk].get('tables', {}):
            t = data['quarters'][qk]['tables']['flc_report']
            fields = t.get('fields', [])
            n_dists = len(t.get('districts', {}))
            sample_dist = sorted(t['districts'].keys())[0] if t.get('districts') else 'N/A'
            camp_val = t.get('districts', {}).get(sample_dist, {}).get('No. of Camps Conducted', 'MISSING')
            print(f"    {qk}: fields={fields}, n_districts={n_dists}, {sample_dist} camps={camp_val}")

    # Check timeseries CSV for CD Ratio continuity
    print("\n  Tripura timeseries — CD Ratio column check:")
    csv_path = BASE / "tripura" / "tripura_fi_timeseries.csv"
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        cdr_cols = [h for h in headers if 'credit_deposit_ratio' in h and 'cd_ratio' in h.lower()]
        print(f"    CD Ratio columns: {cdr_cols}")

        # Count non-empty values per period for first CD Ratio column
        if cdr_cols:
            f.seek(0)
            reader = csv.DictReader(f)
            period_counts = defaultdict(int)
            for row in reader:
                period = row.get('period', '')
                for col in cdr_cols:
                    if row.get(col, '').strip():
                        period_counts[period] += 1
                        break
            print(f"    Periods with CD Ratio data: {len(period_counts)}")
            for p in sorted(period_counts.keys()):
                print(f"      {p}: {period_counts[p]} districts")

    print(f"\n{'='*70}")
    print("DONE — redistribution complete!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
