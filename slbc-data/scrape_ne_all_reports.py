#!/usr/bin/env python3
"""
Scrape ALL district-wise reports from onlineslbcne.nic.in for all 6 NE states
using Playwright (sync API).

Reports: CDR, PMJDY, FI&KCC, Digital, NRLM, PMEGP, Aadhaar, SHG, Minority, SC/ST
States: AS, ME, MN, MZ, NL, AP
Quarters: FY2021-FY2026 (24 quarters)

Output: ne_full_scrape.json
"""

import json
import os
import sys
import time
import traceback
from playwright.sync_api import sync_playwright

BASE_URL = "https://onlineslbcne.nic.in"

STATES = {
    "AS": "assam",
    "ME": "meghalaya",
    "MN": "manipur",
    "MZ": "mizoram",
    "NL": "nagaland",
    "AP": "arunachal-pradesh",
}

# Report definitions: key, form page, report action page, friendly name
REPORTS = [
    ("credit_deposit_ratio", "districtwiseCDr.php", "districtwiseCdrreport.php", "CD Ratio"),
    ("pmjdy", "districtwisePMJDY.php", "districtwisePMJDYreport.php", "PMJDY"),
    ("fi_kcc", "districtwiseFIKCC.php", "districtwiseFIKCCreport.php", "FI & KCC"),
    ("digital_transactions", "districtwiseDigital.php", "districtwiseDigitalreport.php", "Digital"),
    ("nrlm", "districtwiseNrlmdata.php", "districtwiseNrlmdatareport.php", "NRLM/SHG"),
    ("pmegp", "districtwisePmegpdata.php", "districtwisePmegpdatareport.php", "PMEGP"),
    ("aadhaar_authentication", "districtwiseAadhaar.php", "districtwiseAadhaarreport.php", "Aadhaar"),
    ("shg", "districtwiseShg.php", "districtwiseShgreport.php", "SHG"),
    ("minority_disbursement", "districtwiseMinorityDisb.php", "districtwiseMinorityDisbreport.php", "Minority"),
    ("sc_st_finance", "districtwiseSCSTDisb.php", "districtwiseSCSTDisbreport.php", "SC/ST"),
]

# Quarter mapping: quarter_num -> month name for period label
QUARTER_MONTH = {1: "June", 2: "September", 3: "December", 4: "March"}

# FY years to scrape
FY_YEARS = list(range(2021, 2027))  # FY2021 through FY2026

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ne_full_scrape.json")
CHECKPOINT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ne_full_scrape_checkpoint.json")


def quarter_to_period(quarter_num, fy_year):
    """Convert quarter number and FY year to period label like 'June 2020'."""
    month = QUARTER_MONTH[quarter_num]
    # FY2021 means April 2020 - March 2021
    # Q1 (June) -> 2020, Q2 (Sep) -> 2020, Q3 (Dec) -> 2020, Q4 (Mar) -> 2021
    if quarter_num == 4:  # March
        year = fy_year
    else:
        year = fy_year - 1
    return f"{month} {year}"


def parse_table(page):
    """Parse the HTML table from the report page. Returns (headers, districts) or (None, None)."""
    try:
        # Wait for table to appear
        page.wait_for_selector("table", timeout=10000)
    except Exception:
        return None, None

    # Extract table data via JS
    result = page.evaluate("""() => {
        const tables = document.querySelectorAll('table');
        if (!tables.length) return null;

        // Find the main data table (usually the largest one)
        let mainTable = null;
        let maxRows = 0;
        for (const t of tables) {
            const rows = t.querySelectorAll('tr');
            if (rows.length > maxRows) {
                maxRows = rows.length;
                mainTable = t;
            }
        }
        if (!mainTable || maxRows < 2) return null;

        const rows = mainTable.querySelectorAll('tr');
        const data = [];
        for (const row of rows) {
            const cells = row.querySelectorAll('td, th');
            const rowData = [];
            for (const cell of cells) {
                rowData.push(cell.textContent.trim());
            }
            if (rowData.length > 0) {
                data.push(rowData);
            }
        }
        return data;
    }""")

    if not result or len(result) < 2:
        return None, None

    # First row(s) are headers. Find the header row (contains "Sl" or "District")
    header_idx = 0
    for i, row in enumerate(result):
        row_text = " ".join(row).lower()
        if "sl" in row_text or "district" in row_text:
            header_idx = i
            break

    headers = result[header_idx]
    districts = []

    for row in result[header_idx + 1:]:
        if len(row) < 2:
            continue
        # Skip Grand Total, Total, and empty rows
        row_text = " ".join(row).upper()
        if "GRAND TOTAL" in row_text or row_text.startswith("TOTAL"):
            continue
        if "STATE TOTAL" in row_text:
            continue
        # Skip rows where district name looks empty
        if len(row) >= 2 and row[1].strip() == "":
            continue
        # Check if it has any non-zero values (at least one numeric cell with value > 0)
        has_data = False
        for cell in row[2:]:
            try:
                val = float(cell.replace(",", "").strip())
                if val != 0:
                    has_data = True
                    break
            except (ValueError, AttributeError):
                if cell.strip() and cell.strip() not in ("", "-", "0", "0.00"):
                    has_data = True
                    break
        if not has_data:
            continue

        districts.append(row)

    if not districts:
        return None, None

    return headers, districts


def scrape_report(page, state_code, report_key, form_page, report_action, quarter, fy_year):
    """Scrape a single report for one state/quarter. Returns (headers, districts) or (None, None)."""
    period = quarter_to_period(quarter, fy_year)

    try:
        # Navigate to form page
        page.goto(f"{BASE_URL}/{form_page}", wait_until="networkidle", timeout=30000)
        time.sleep(1)

        # Change form action to report page
        page.evaluate(f"document.querySelector('form').action = '{report_action}'")

        # Select quarter
        page.select_option('select[name="quarter"]', str(quarter))
        time.sleep(0.3)

        # Select year
        page.select_option('select[name="year"]', str(fy_year))
        time.sleep(0.3)

        # Submit form
        page.click('input[type="submit"], button[type="submit"]')
        time.sleep(2)

        # Try to wait for the result
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Check for connection error
        body_text = page.inner_text("body")
        if "Connection Error" in body_text or "No Data Found" in body_text:
            # Try with original form action (without "report")
            page.goto(f"{BASE_URL}/{form_page}", wait_until="networkidle", timeout=30000)
            time.sleep(1)
            # Don't change form action this time
            page.select_option('select[name="quarter"]', str(quarter))
            time.sleep(0.3)
            page.select_option('select[name="year"]', str(fy_year))
            time.sleep(0.3)
            page.click('input[type="submit"], button[type="submit"]')
            time.sleep(2)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            body_text = page.inner_text("body")
            if "Connection Error" in body_text or "No Data Found" in body_text:
                return None, None

        headers, districts = parse_table(page)
        return headers, districts

    except Exception as e:
        print(f"    ERROR: {report_key} Q{quarter}/FY{fy_year}: {e}")
        return None, None


def load_checkpoint():
    """Load checkpoint if exists."""
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {}


def save_checkpoint(data):
    """Save checkpoint."""
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False)


def main():
    # Load existing checkpoint data
    all_data = load_checkpoint()

    total_reports = len(STATES) * len(REPORTS) * len(FY_YEARS) * 4
    done = 0
    new_data = 0

    with sync_playwright() as p:
        for state_code, state_dir in STATES.items():
            print(f"\n{'='*60}")
            print(f"  STATE: {state_code} ({state_dir})")
            print(f"{'='*60}")

            if state_code not in all_data:
                all_data[state_code] = {}

            # Create a fresh browser context for each state
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()

            try:
                # Step 1: Navigate to state code page to set session
                print(f"  Setting state session: {BASE_URL}/{state_code}")
                page.goto(f"{BASE_URL}/{state_code}", wait_until="networkidle", timeout=30000)
                time.sleep(3)

                # Step 2: Navigate to slbc.php to confirm session
                page.goto(f"{BASE_URL}/slbc.php", wait_until="networkidle", timeout=30000)
                time.sleep(2)

                # Now scrape all reports
                for report_key, form_page, report_action, report_name in REPORTS:
                    if report_key not in all_data[state_code]:
                        all_data[state_code][report_key] = {}

                    for fy_year in FY_YEARS:
                        for quarter in range(1, 5):
                            done += 1
                            period = quarter_to_period(quarter, fy_year)

                            # Skip if already scraped
                            if period in all_data[state_code][report_key]:
                                if done % 50 == 0:
                                    print(f"  [{done}/{total_reports}] Skip {state_code}/{report_name}/{period} (cached)")
                                continue

                            headers, districts = scrape_report(
                                page, state_code, report_key, form_page, report_action, quarter, fy_year
                            )

                            if headers and districts:
                                all_data[state_code][report_key][period] = {
                                    "headers": headers,
                                    "districts": districts,
                                }
                                new_data += 1
                                print(f"  [{done}/{total_reports}] {state_code}/{report_name}/{period}: {len(districts)} districts, {len(headers)} cols")
                            else:
                                # Store empty marker so we don't retry
                                all_data[state_code][report_key][period] = None
                                if done % 20 == 0:
                                    print(f"  [{done}/{total_reports}] {state_code}/{report_name}/{period}: no data")

                            # Checkpoint every 20 successful scrapes
                            if new_data > 0 and new_data % 20 == 0:
                                save_checkpoint(all_data)
                                print(f"    [Checkpoint saved: {new_data} new entries]")

            except Exception as e:
                print(f"  FATAL ERROR for {state_code}: {e}")
                traceback.print_exc()
            finally:
                context.close()
                browser.close()

            # Save checkpoint after each state
            save_checkpoint(all_data)
            print(f"  [State {state_code} done. Checkpoint saved.]")

    # Clean up None entries and save final output
    clean_data = {}
    total_entries = 0
    for state_code in all_data:
        clean_data[state_code] = {}
        for report_key in all_data[state_code]:
            clean_data[state_code][report_key] = {}
            for period, val in all_data[state_code][report_key].items():
                if val is not None:
                    clean_data[state_code][report_key][period] = val
                    total_entries += 1

    with open(OUTPUT_PATH, "w") as f:
        json.dump(clean_data, f, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETE")
    print(f"  Total new data points: {new_data}")
    print(f"  Total entries in output: {total_entries}")
    print(f"  Output: {OUTPUT_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
