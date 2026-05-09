#!/usr/bin/env python3
"""
Scraper for onlineslbcne.nic.in — extracts district-level SLBC data
for all 6 NE states across all available quarters and report types.

Usage:
    python3 scrape_onlineslbc.py

Output:
    Creates scraped_data/{state}/ directories with JSON files per report type.

Notes:
    - The site uses CSRF tokens per form, so we fetch the form page first
    - State is set via cookie (state=AS, AP, MN, MZ, ME, NL)
    - Quarter mapping: 1=June, 2=September, 3=December, 4=March
    - Year is the ending FY year (e.g., 2026 = FY2025-2026)
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

STATES = {
    'AS': 'Assam',
    'AP': 'Arunachal Pradesh',
    'MN': 'Manipur',
    'MZ': 'Mizoram',
    'ME': 'Meghalaya',
    'NL': 'Nagaland',
}

QUARTERS = {1: 'June', 2: 'September', 3: 'December', 4: 'March'}

# FY years to try (ending year): FY2017-18 through FY2025-26
YEARS = list(range(2018, 2027))

# District-level report endpoints and their form action targets
# Format: (form_page, action_page, report_name)
REPORTS = [
    ('districtwiseCDr.php', 'distwiseDepAdvReport.php', 'credit_deposit_ratio'),
    ('districtwisekcc.php', None, 'kcc'),  # action TBD - will auto-detect
    ('districtwisenrlm.php', None, 'nrlm'),
    ('districtwisemudra.php', None, 'mudra'),
    ('districtwiseminority.php', None, 'minority'),
    ('districtwisepmegp.php', None, 'pmegp'),
    ('sssdistrictwise.php', None, 'social_security'),
    ('districtwisepmay.php', None, 'pmay'),
    ('districtwisehousing.php', None, 'housing'),
    ('districtwisehousingprio.php', None, 'housing_priority'),
    ('districtwiserecoverypmegp.php', None, 'recovery_pmegp'),
    ('districtwiserecoverynrlm.php', None, 'recovery_nrlm'),
    ('districtwiserecoverybakijai.php', None, 'recovery_bakijai'),
    ('districtwisecdratio.php', None, 'cd_ratio_detailed'),
    ('districtwiseagri.php', None, 'priority_sector_agri'),
    ('districtwisemse.php', None, 'priority_sector_msme'),
    ('districtwiseservice.php', None, 'priority_sector_service'),
    ('districtwisecroploan.php', None, 'crop_loan'),
    ('districtwisecropkharif.php', None, 'crop_kharif'),
    ('districtwisecroprabi.php', None, 'crop_rabi'),
]

BASE_URL = 'https://onlineslbcne.nic.in/'
OUTPUT_DIR = 'scraped_data'

# ── HTML Table Parser ──────────────────────────────────────────

class TableParser(HTMLParser):
    """Extracts all tables from HTML into list of list of rows."""

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
            if len(self.current_table) > 1:  # Only keep tables with data
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
    """Extract tables from HTML."""
    parser = TableParser()
    parser.feed(html)
    return parser.tables


def extract_form_action(html):
    """Find the form action URL from HTML."""
    match = re.search(r'<form[^>]*action="([^"]+)"', html, re.I)
    return match.group(1) if match else None


def extract_token(html):
    """Extract CSRF token from form."""
    match = re.search(r'name="token"\s+value="([^"]+)"', html)
    if not match:
        match = re.search(r'value="([^"]+)"\s*name="token"', html)  # reversed order
    return match.group(1) if match else None


# ── HTTP Client ────────────────────────────────────────────────

def create_opener(state_code):
    """Create urllib opener with SSL and state cookie."""
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
    """Fetch a single report by getting token then POSTing."""
    # Step 1: GET form page to get token
    try:
        resp1 = opener.open(BASE_URL + form_url, timeout=30)
        html1 = resp1.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None, f'Form fetch error: {e}'

    token = extract_token(html1)
    if not token:
        return None, 'No token found'

    # Auto-detect action URL if not provided
    if not action_url:
        action_url = extract_form_action(html1)
        if not action_url:
            return None, 'No form action found'

    # Step 2: POST for data
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

    # Check for error redirect
    if 'window.location.href="error.php"' in html2:
        return None, 'Redirected to error page'

    # Parse tables
    tables = parse_tables(html2)
    if not tables:
        return None, 'No tables found'

    # Find the data table (usually the one with most rows)
    data_table = max(tables, key=len)

    if len(data_table) < 2:
        return None, 'Table has no data rows'

    # Check if Grand Total is all zeros (empty data)
    for row in data_table:
        if any('Grand Total' in cell for cell in row):
            non_label_cells = [c for c in row if 'Grand Total' not in c and 'Total' not in c]
            if all(c.strip() in ('0', '0.00', '') for c in non_label_cells):
                return None, 'All zeros (no data submitted)'

    return data_table, None


def table_to_dict(table):
    """Convert parsed table (list of rows) to list of district dicts."""
    if len(table) < 2:
        return []

    headers = table[0]
    rows = []
    for row in table[1:]:
        if len(row) != len(headers):
            # Pad or trim
            row = row[:len(headers)] + [''] * max(0, len(headers) - len(row))

        d = {}
        for h, v in zip(headers, row):
            h = h.strip()
            if h:
                d[h] = v.strip()

        # Skip total/grand total rows
        first_val = list(d.values())[0] if d else ''
        if 'total' in first_val.lower() and ('grand' in first_val.lower() or 'total' == first_val.lower().strip()):
            continue

        if d:
            rows.append(d)

    return rows


# ── Main Scraper ───────────────────────────────────────────────

def scrape_state(state_code, state_name):
    """Scrape all reports for a single state."""
    print(f'\n{"="*60}')
    print(f'  Scraping: {state_name} ({state_code})')
    print(f'{"="*60}')

    opener = create_opener(state_code)
    state_slug = state_name.lower().replace(' ', '-')
    state_dir = os.path.join(OUTPUT_DIR, state_slug)
    os.makedirs(state_dir, exist_ok=True)

    results = {}
    total_fetched = 0
    total_empty = 0
    total_error = 0

    for form_url, action_url, report_name in REPORTS:
        print(f'\n  Report: {report_name} ({form_url})')
        report_data = {}

        for year in YEARS:
            for quarter, qtr_name in QUARTERS.items():
                period = f'{qtr_name} {year - 1 if quarter != 4 else year}'

                table, error = fetch_report(opener, form_url, action_url, quarter, year)

                if error:
                    if 'All zeros' in error:
                        total_empty += 1
                    elif 'error page' in error:
                        total_error += 1
                    else:
                        total_error += 1
                    # Don't print every empty quarter, too noisy
                    continue

                rows = table_to_dict(table)
                if rows:
                    key = f'{year}-Q{quarter}'
                    report_data[key] = {
                        'period': period,
                        'headers': table[0],
                        'districts': rows,
                    }
                    total_fetched += 1
                    print(f'    ✓ {period}: {len(rows)} districts, {len(table[0])} fields')

                # Be polite to the server
                time.sleep(0.5)

        if report_data:
            results[report_name] = report_data
            # Save per-report JSON
            out_path = os.path.join(state_dir, f'{report_name}.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            print(f'    → Saved to {out_path}')

    print(f'\n  Summary for {state_name}: {total_fetched} quarter-reports with data, '
          f'{total_empty} empty, {total_error} errors')

    # Save combined results
    if results:
        combined_path = os.path.join(state_dir, f'{state_slug}_all_reports.json')
        with open(combined_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f'  → Combined data saved to {combined_path}')

    return results


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print('SLBC NE Online Portal Scraper')
    print(f'Base URL: {BASE_URL}')
    print(f'States: {", ".join(STATES.values())}')
    print(f'Years: FY{YEARS[0]-1}-{YEARS[0]} through FY{YEARS[-1]-1}-{YEARS[-1]}')
    print(f'Reports: {len(REPORTS)} types')
    print(f'Total requests (max): {len(STATES) * len(REPORTS) * len(YEARS) * len(QUARTERS)}')

    all_results = {}
    for state_code, state_name in STATES.items():
        all_results[state_code] = scrape_state(state_code, state_name)

    # Summary
    print(f'\n{"="*60}')
    print('  OVERALL SUMMARY')
    print(f'{"="*60}')
    for state_code, state_name in STATES.items():
        reports = all_results.get(state_code, {})
        total_qr = sum(len(v) for v in reports.values())
        print(f'  {state_name:25s}: {len(reports):2d} report types, {total_qr:3d} quarter-reports')


if __name__ == '__main__':
    main()
