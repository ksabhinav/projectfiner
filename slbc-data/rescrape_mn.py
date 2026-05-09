#!/usr/bin/env python3
"""
Re-scrape contaminated MN (Manipur) reports.
The original scrape picked up AS or NL data for some reports due to session issues.

Contaminated reports:
- aadhaar_authentication (got NL data)
- digital_transactions (got AS data)
- fi_kcc (got AS data)
- minority_disbursement (got NL data)
- nrlm (got AS data)
- shg (got NL data)

Strategy: Create fresh browser context, set MN session carefully,
re-navigate to state page between EACH report to ensure session stays.
"""

import json
import os
import time
import traceback
from playwright.sync_api import sync_playwright

BASE_URL = "https://onlineslbcne.nic.in"

REPORTS_TO_FIX = [
    ("aadhaar_authentication", "districtwiseAadhaar.php", "districtwiseAadhaarreport.php"),
    ("digital_transactions", "districtwiseDigital.php", "districtwiseDigitalreport.php"),
    ("fi_kcc", "districtwiseFIKCC.php", "districtwiseFIKCCreport.php"),
    ("minority_disbursement", "districtwiseMinorityDisb.php", "districtwiseMinorityDisbreport.php"),
    ("nrlm", "districtwiseNrlmdata.php", "districtwiseNrlmdatareport.php"),
    ("shg", "districtwiseShg.php", "districtwiseShgreport.php"),
]

QUARTER_MONTH = {1: "June", 2: "September", 3: "December", 4: "March"}
FY_YEARS = list(range(2021, 2027))

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ne_full_scrape.json")


def quarter_to_period(quarter_num, fy_year):
    month = QUARTER_MONTH[quarter_num]
    if quarter_num == 4:
        year = fy_year
    else:
        year = fy_year - 1
    return f"{month} {year}"


def parse_table(page):
    try:
        page.wait_for_selector("table", timeout=10000)
    except Exception:
        return None, None

    result = page.evaluate("""() => {
        const tables = document.querySelectorAll('table');
        if (!tables.length) return null;
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
            if (rowData.length > 0) data.push(rowData);
        }
        return data;
    }""")

    if not result or len(result) < 2:
        return None, None

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
        row_text = " ".join(row).upper()
        if "GRAND TOTAL" in row_text or row_text.startswith("TOTAL") or "STATE TOTAL" in row_text:
            continue
        if len(row) >= 2 and row[1].strip() == "":
            continue
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


def main():
    with open(OUTPUT_PATH) as f:
        all_data = json.load(f)

    fixed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for report_key, form_page, report_action in REPORTS_TO_FIX:
            print(f"\n--- Re-scraping MN/{report_key} ---")

            # Fresh context for EACH report to avoid session drift
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()

            try:
                # Set MN session
                print("  Setting MN session...")
                page.goto(f"{BASE_URL}/MN", wait_until="networkidle", timeout=30000)
                time.sleep(4)
                page.goto(f"{BASE_URL}/slbc.php", wait_until="networkidle", timeout=30000)
                time.sleep(2)

                report_data = {}

                for fy_year in FY_YEARS:
                    for quarter in range(1, 5):
                        period = quarter_to_period(quarter, fy_year)

                        try:
                            page.goto(f"{BASE_URL}/{form_page}", wait_until="networkidle", timeout=30000)
                            time.sleep(1)
                            page.evaluate(f"document.querySelector('form').action = '{report_action}'")
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
                                # Try without report action
                                page.goto(f"{BASE_URL}/{form_page}", wait_until="networkidle", timeout=30000)
                                time.sleep(1)
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
                                    continue

                            headers, districts = parse_table(page)
                            if headers and districts:
                                # Verify it's actually Manipur data
                                first_name = districts[0][1].replace(" ", "").upper()
                                mn_names = ["BISHNUPUR", "CHANDEL", "CHURACHANDPUR", "IMPHAL", "JIRIBAM", "KAKCHING", "KAMJONG", "KANGPOKPI", "NONEY", "PHERZAWL", "SENAPATI", "TAMENGLONG", "TENGNOUPAL", "THOUBAL", "UKHRUL"]
                                is_mn = any(first_name.startswith(n[:5]) for n in mn_names)
                                if is_mn:
                                    report_data[period] = {"headers": headers, "districts": districts}
                                    fixed += 1
                                    print(f"  {period}: {len(districts)} districts (verified MN)")
                                else:
                                    print(f"  {period}: WRONG STATE ({first_name}) - skipping")
                            else:
                                pass  # no data
                        except Exception as e:
                            print(f"  {period}: ERROR {e}")

                # Update the data
                if report_data:
                    all_data["MN"][report_key] = report_data
                    print(f"  Updated MN/{report_key} with {len(report_data)} periods")

            finally:
                context.close()

        browser.close()

    # Save
    with open(OUTPUT_PATH, "w") as f:
        json.dump(all_data, f, ensure_ascii=False)

    print(f"\nDone! Fixed {fixed} entries. Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
