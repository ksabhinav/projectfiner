#!/usr/bin/env python3
"""
Targeted scraper for onlineslbcne.nic.in — fetches ONLY missing quarters.

Targets:
- Assam, Meghalaya, Manipur, Mizoram: December 2025 (FY2026 Q3)
- Nagaland: June 2025, September 2025, December 2025 + backfill FY2022-FY2025
- Arunachal Pradesh: June 2025, September 2025, December 2025 + backfill FY2024-FY2025
- Sikkim: backfill FY2022-FY2026

Then integrates into existing _fi_timeseries.json files.
"""

import urllib.request
import urllib.parse
import http.cookiejar
import ssl
import re
import json
import os
import time
from html.parser import HTMLParser

# ── Configuration ──────────────────────────────────────────────

BASE_URL = 'https://onlineslbcne.nic.in/'
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scraped_data')
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public', 'slbc-data')

STATES = {
    'AS': 'Assam',
    'AP': 'Arunachal Pradesh',
    'MN': 'Manipur',
    'MZ': 'Mizoram',
    'ME': 'Meghalaya',
    'NL': 'Nagaland',
    'SK': 'Sikkim',
}

STATE_SLUGS = {
    'AS': 'assam',
    'AP': 'arunachal-pradesh',
    'MN': 'manipur',
    'MZ': 'mizoram',
    'ME': 'meghalaya',
    'NL': 'nagaland',
    'SK': 'sikkim',
}

QUARTERS = {1: 'June', 2: 'September', 3: 'December', 4: 'March'}

# Key FI reports
REPORTS = [
    ('districtwiseCDr.php', 'distwiseDepAdvReport.php', 'credit_deposit_ratio'),
    ('districtwisekcc.php', None, 'kcc'),
    ('districtwisenrlm.php', None, 'nrlm'),
    ('districtwisemudra.php', None, 'mudra'),
    ('districtwiseminority.php', None, 'minority'),
    ('districtwisepmegp.php', None, 'pmegp'),
    ('sssdistrictwise.php', None, 'social_security'),
]

# ── Define EXACTLY which (year, quarter) combos to fetch per state ──

def build_targets():
    """Build the targeted scrape list: {state_code: [(year, quarter), ...]}"""
    targets = {}

    # Assam, Meghalaya, Manipur, Mizoram: need Dec 2025 = FY2026 Q3
    for code in ['AS', 'ME', 'MN', 'MZ']:
        targets[code] = [(2026, 3)]  # year=2026, quarter=3 → December 2025

    # Nagaland: need Jun 2025, Sep 2025, Dec 2025 + backfill FY2022-FY2025
    nl_targets = []
    # New quarters
    nl_targets.append((2026, 1))  # June 2025
    nl_targets.append((2026, 2))  # September 2025
    nl_targets.append((2026, 3))  # December 2025
    # Backfill: FY2022 (year=2022) through FY2025 (year=2025), all 4 quarters each
    for year in range(2022, 2026):
        for q in [1, 2, 3, 4]:
            nl_targets.append((year, q))
    targets['NL'] = nl_targets

    # Arunachal Pradesh: need Jun 2025, Sep 2025, Dec 2025 + backfill FY2024-FY2025
    ap_targets = []
    ap_targets.append((2026, 1))  # June 2025
    ap_targets.append((2026, 2))  # September 2025
    ap_targets.append((2026, 3))  # December 2025
    # Backfill FY2024 (year=2024) and FY2025 (year=2025)
    for year in [2024, 2025]:
        for q in [1, 2, 3, 4]:
            ap_targets.append((year, q))
    targets['AP'] = ap_targets

    # Sikkim: backfill FY2022-FY2026
    sk_targets = []
    for year in range(2022, 2027):
        for q in [1, 2, 3, 4]:
            sk_targets.append((year, q))
    targets['SK'] = sk_targets

    return targets


# ── HTML Table Parser ──────────────────────────────────────────

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = None
        self.current_row = None
        self.current_cell = None
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.current_table = []
        elif tag == 'tr' and self.current_table is not None:
            self.current_row = []
        elif tag in ('td', 'th') and self.current_row is not None:
            self.current_cell = ''
            self.in_cell = True

    def handle_endtag(self, tag):
        if tag == 'table' and self.current_table is not None:
            if len(self.current_table) > 1:
                self.tables.append(self.current_table)
            self.current_table = None
        elif tag == 'tr' and self.current_row is not None:
            if self.current_table is not None:
                self.current_table.append(self.current_row)
            self.current_row = None
        elif tag in ('td', 'th') and self.in_cell:
            if self.current_row is not None:
                self.current_row.append(self.current_cell.strip())
            self.in_cell = False
            self.current_cell = None

    def handle_data(self, data):
        if self.in_cell and self.current_cell is not None:
            self.current_cell += data


def parse_tables(html):
    parser = TableParser()
    parser.feed(html)
    return parser.tables


def extract_form_action(html):
    match = re.search(r'<form[^>]*action="([^"]+)"', html, re.I)
    return match.group(1) if match else None


def extract_token(html):
    match = re.search(r'name="token"\s+value="([^"]+)"', html)
    if not match:
        match = re.search(r'value="([^"]+)"\s*name="token"', html)
    return match.group(1) if match else None


# ── HTTP Client ────────────────────────────────────────────────

def create_opener(state_code):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    cj = http.cookiejar.CookieJar()
    cj.set_cookie(http.cookiejar.Cookie(
        version=0, name='state', value=state_code, port=None, port_specified=False,
        domain='onlineslbcne.nic.in', domain_specified=True, domain_initial_dot=False,
        path='/', path_specified=True, secure=False, expires=None, discard=True,
        comment=None, comment_url=None, rest={}, rfc2109=False
    ))

    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPCookieProcessor(cj)
    )
    opener.addheaders = [
        ('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'),
        ('Accept', 'text/html,application/xhtml+xml'),
        ('Accept-Language', 'en-US,en;q=0.9'),
    ]
    return opener


def fetch_report(opener, form_url, action_url, quarter, year):
    """Fetch a single report."""
    try:
        resp1 = opener.open(BASE_URL + form_url, timeout=30)
        html1 = resp1.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None, f'Form fetch error: {e}'

    token = extract_token(html1)
    if not token:
        return None, 'No token found'

    if not action_url:
        action_url = extract_form_action(html1)
        if not action_url:
            return None, 'No form action found'

    data = urllib.parse.urlencode({
        'quarter': str(quarter),
        'year': str(year),
        'token': token,
        'View': 'View Report >>'
    }).encode('utf-8')

    try:
        req = urllib.request.Request(
            BASE_URL + action_url,
            data=data,
            headers={'Referer': BASE_URL + form_url}
        )
        resp2 = opener.open(req, timeout=30)
        html2 = resp2.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None, f'POST error: {e}'

    if 'window.location.href="error.php"' in html2:
        return None, 'Redirected to error page'

    tables = parse_tables(html2)
    if not tables:
        return None, 'No tables found'

    data_table = max(tables, key=len)
    if len(data_table) < 2:
        return None, 'Table has no data rows'

    # Check if Grand Total is all zeros
    for row in data_table:
        if any('Grand Total' in cell for cell in row):
            non_label_cells = [c for c in row if 'Grand Total' not in c and 'Total' not in c]
            if all(c.strip() in ('0', '0.00', '') for c in non_label_cells):
                return None, 'All zeros (no data submitted)'

    return data_table, None


def table_to_dict(table):
    """Convert parsed table to list of district dicts."""
    if len(table) < 2:
        return []

    headers = table[0]
    rows = []
    for row in table[1:]:
        if len(row) != len(headers):
            row = row[:len(headers)] + [''] * max(0, len(headers) - len(row))

        d = {}
        for h, v in zip(headers, row):
            h = h.strip()
            if h:
                d[h] = v.strip()

        first_val = list(d.values())[0] if d else ''
        if 'total' in first_val.lower() and ('grand' in first_val.lower() or 'total' == first_val.lower().strip()):
            continue

        if d:
            rows.append(d)

    return rows


def period_label(year, quarter):
    """Convert (year, quarter) to period label like 'December 2025'."""
    qtr_name = QUARTERS[quarter]
    if quarter == 4:
        return f'{qtr_name} {year}'
    else:
        return f'{qtr_name} {year - 1}'


def period_to_sort_key(period_str):
    """Convert 'June 2025' to '2025-06' for sorting."""
    month_map = {'March': '03', 'June': '06', 'September': '09', 'December': '12'}
    parts = period_str.split()
    return f'{parts[1]}-{month_map[parts[0]]}'


# ── Field name standardization (portal headers → snake_case) ──

def to_snake_case(s):
    s = re.sub(r'\s+', ' ', s.strip())
    s = re.sub(r'[^a-zA-Z0-9]+', '_', s)
    s = re.sub(r'([a-z])([A-Z])', r'\1_\2', s)
    s = s.lower().strip('_')
    s = re.sub(r'_+', '_', s)
    return s


def clean_value(v):
    if not isinstance(v, str):
        return v
    v = v.strip()
    if not v:
        return v
    stripped = v.replace(',', '')
    try:
        float(stripped)
        return stripped
    except ValueError:
        return v


# ── Main Scraper ───────────────────────────────────────────────

def scrape_targeted():
    targets = build_targets()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_results = {}  # {state_code: {report_name: {year-Qq: {...}}}}

    for state_code in targets:
        state_name = STATES[state_code]
        state_slug = STATE_SLUGS[state_code]
        state_targets = targets[state_code]

        print(f'\n{"="*60}')
        print(f'  {state_name} ({state_code}) — {len(state_targets)} quarter(s) to check')
        print(f'{"="*60}')

        # Set state
        opener = create_opener(state_code)
        try:
            opener.open(BASE_URL + f'selectState.php?state={state_code}', timeout=15)
        except Exception as e:
            print(f'  Warning: selectState failed: {e}')

        state_dir = os.path.join(OUTPUT_DIR, state_slug)
        os.makedirs(state_dir, exist_ok=True)

        state_results = {}
        fetched = 0
        empty = 0
        errors = 0

        for form_url, action_url, report_name in REPORTS:
            report_data = {}

            # Load existing scraped data if present
            existing_path = os.path.join(state_dir, f'{report_name}.json')
            if os.path.exists(existing_path):
                with open(existing_path, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)

            print(f'\n  Report: {report_name}')
            new_for_report = 0

            for year, quarter in state_targets:
                key = f'{year}-Q{quarter}'

                # Skip if we already have this data
                if key in report_data:
                    continue

                period = period_label(year, quarter)
                table, error = fetch_report(opener, form_url, action_url, quarter, year)

                if error:
                    if 'All zeros' in error:
                        empty += 1
                    else:
                        errors += 1
                    continue

                rows = table_to_dict(table)
                if rows:
                    report_data[key] = {
                        'period': period,
                        'headers': table[0],
                        'districts': rows,
                    }
                    fetched += 1
                    new_for_report += 1
                    print(f'    + {period}: {len(rows)} districts, {len(table[0])} fields')

                time.sleep(0.4)

            if new_for_report > 0:
                # Save updated report JSON
                with open(existing_path, 'w', encoding='utf-8') as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
                print(f'    -> Saved {existing_path}')

            if report_data:
                state_results[report_name] = report_data

        all_results[state_code] = state_results
        print(f'\n  {state_name} summary: {fetched} new quarter-reports fetched, {empty} empty, {errors} errors')

    return all_results


# ── Integration into timeseries ────────────────────────────────

def integrate_into_timeseries(all_results):
    """Integrate scraped data into existing _fi_timeseries.json files."""
    print(f'\n{"="*60}')
    print('  INTEGRATING INTO TIMESERIES')
    print(f'{"="*60}')

    for state_code, reports in all_results.items():
        if not reports:
            print(f'\n  {STATES[state_code]}: No data to integrate')
            continue

        state_slug = STATE_SLUGS[state_code]
        ts_path = os.path.join(PUBLIC_DIR, state_slug, f'{state_slug}_fi_timeseries.json')

        if not os.path.exists(ts_path):
            print(f'\n  {STATES[state_code]}: No timeseries file found at {ts_path}')
            continue

        print(f'\n  {STATES[state_code]}:')

        with open(ts_path, 'r', encoding='utf-8') as f:
            ts_data = json.load(f)

        existing_periods = {p['period'] for p in ts_data['periods']}
        print(f'    Existing periods: {len(existing_periods)}')

        # Collect all new periods from scraped data
        # Structure: {period_label: {district: {category__field: value}}}
        new_periods_data = {}

        for report_name, report_quarters in reports.items():
            for qkey, qdata in report_quarters.items():
                period = qdata['period']

                if period not in new_periods_data:
                    new_periods_data[period] = {}

                headers = qdata['headers']
                for district_row in qdata['districts']:
                    # Get district name (try various header names)
                    dist_name = None
                    for hdr in ['District Name', 'District', 'Name of the District',
                                'Districts', 'Dist Name', 'Name of District']:
                        if hdr in district_row:
                            dist_name = district_row[hdr].strip()
                            break

                    if not dist_name:
                        # Try second column
                        vals = list(district_row.values())
                        if len(vals) >= 2:
                            dist_name = vals[1].strip() if vals[1].strip() else vals[0].strip()

                    if not dist_name or 'total' in dist_name.lower():
                        continue

                    # Title case
                    dist_name = dist_name.title()

                    if dist_name not in new_periods_data[period]:
                        new_periods_data[period][dist_name] = {
                            'district': dist_name,
                            'period': period,
                        }

                    # Add fields with category prefix
                    for header, value in district_row.items():
                        header_clean = header.strip()
                        # Skip meta fields
                        if header_clean in ('Sl No', 'Sl No.', 'S.No', 'Sl.No', 'S.No.', 'Sr No',
                                           'District Name', 'District', 'Name of the District',
                                           'Districts', 'Dist Name', 'Name of District'):
                            continue

                        field = to_snake_case(header_clean)
                        if not field:
                            continue

                        key = f'{report_name}__{field}'
                        val = clean_value(value)
                        new_periods_data[period][dist_name][key] = val

        # Now merge into timeseries
        added_periods = 0
        updated_periods = 0

        for period, districts in sorted(new_periods_data.items(),
                                         key=lambda x: period_to_sort_key(x[0])):
            if not districts:
                continue

            district_list = list(districts.values())

            if period in existing_periods:
                # Update existing period with new fields
                for p in ts_data['periods']:
                    if p['period'] == period:
                        existing_dists = {d['district']: d for d in p['districts']}
                        for new_d in district_list:
                            dname = new_d['district']
                            if dname in existing_dists:
                                # Merge new fields
                                for k, v in new_d.items():
                                    if k not in ('district', 'period'):
                                        existing_dists[dname][k] = v
                            else:
                                existing_dists[dname] = new_d
                        p['districts'] = list(existing_dists.values())
                        updated_periods += 1
                        break
            else:
                # Add new period
                ts_data['periods'].append({
                    'period': period,
                    'districts': district_list,
                })
                added_periods += 1

        # Sort periods chronologically
        ts_data['periods'].sort(key=lambda p: period_to_sort_key(p['period']))

        # Update metadata
        ts_data['num_periods'] = len(ts_data['periods'])
        ts_data['total_records'] = sum(len(p['districts']) for p in ts_data['periods'])

        # Count unique fields
        all_fields = set()
        for p in ts_data['periods']:
            for d in p['districts']:
                all_fields.update(d.keys())
        ts_data['total_fields'] = len(all_fields)

        # Save
        with open(ts_path, 'w', encoding='utf-8') as f:
            json.dump(ts_data, f, indent=2, ensure_ascii=False)

        print(f'    Added {added_periods} new periods, updated {updated_periods} existing periods')
        print(f'    Total periods now: {ts_data["num_periods"]}')
        print(f'    Saved to {ts_path}')


def main():
    print('SLBC NE Targeted Scraper — Missing Quarters Only')
    print(f'Base URL: {BASE_URL}')
    print(f'Reports: {len(REPORTS)} key FI types')

    targets = build_targets()
    total_requests = sum(len(t) * len(REPORTS) for t in targets.values())
    print(f'Total requests (max): {total_requests}')
    print()

    for code, tlist in targets.items():
        periods = sorted(set(period_label(y, q) for y, q in tlist),
                        key=period_to_sort_key)
        print(f'  {STATES[code]:25s}: {len(tlist)} quarter(s) — {", ".join(periods[:5])}{"..." if len(periods) > 5 else ""}')

    all_results = scrape_targeted()
    integrate_into_timeseries(all_results)

    print('\nDone!')


if __name__ == '__main__':
    main()
