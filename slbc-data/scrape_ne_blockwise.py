#!/usr/bin/env python3
"""
Scrape ALL blockwise reports from onlineslbcne.nic.in for 6 NE states
using Playwright (sync API).

States: AS, MN, MZ, NL, TR, SK
Reports: CDR, PMJDY, KCC, SHG, Digital, Aadhaar, PMEGP, NRLM
Quarters: FY2022 Q1 through FY2026 Q3 (June 2021 through December 2025)

Output: ne_blockwise_scrape.json

SERVER REVAMP NOTE (June 2026): onlineslbcne.nic.in now binds the selected
state SERVER-SIDE per client IP (GET /<CODE>), not via a session cookie — see
scrape_onlineslbc.py + CLAUDE.md gotcha #34 for the full reference. This script
already (a) visits /<CODE> to bind and (b) uses the LIVE blockwise endpoints
(blockwisecdr.php, blockwisepmjdy.php, …) and submits the form natively (no
form.action override), so it survived the revamp. Hardened June 2026 to also
VERIFY the binding via the form page's "Go Back" link
(<a href="ME"><b>Go Back</b></a>) before each submit and re-select the state if
another client on the same IP flipped it. Never run two states concurrently
from the same IP. NOTE: blockwise data is finer-grained than the district-level
data the main FINER pipeline ingests — this is an auxiliary scraper.
"""

import json
import os
import time
import traceback
from playwright.sync_api import sync_playwright

BASE_URL = "https://onlineslbcne.nic.in"

STATES = ["AS", "MN", "MZ", "NL", "TR", "SK"]

REPORTS = [
    {"key": "blockwise_cdr", "page": "blockwisecdr.php", "name": "CDR"},
    {"key": "blockwise_pmjdy", "page": "blockwisepmjdy.php", "name": "PMJDY"},
    {"key": "blockwise_kcc", "page": "blockwisekcc.php", "name": "KCC"},
    {"key": "blockwise_shg", "page": "blockwiseshg.php", "name": "SHG"},
    {"key": "blockwise_digital", "page": "blockwisedigital.php", "name": "Digital"},
    {"key": "blockwise_aadhaar", "page": "blockwiseaadhaar.php", "name": "Aadhaar"},
    {"key": "blockwise_pmegp", "page": "blockwisepmegp.php", "name": "PMEGP"},
    {"key": "blockwise_nrlm", "page": "blockwisenrlm.php", "name": "NRLM"},
]

QUARTER_MONTH = {1: "June", 2: "September", 3: "December", 4: "March"}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "ne_blockwise_scrape.json")
CHECKPOINT_PATH = os.path.join(SCRIPT_DIR, "ne_blockwise_checkpoint.json")


def build_quarters():
    """Build quarter list: FY2022 Q1 through FY2026 Q3."""
    quarters = []
    for fy in range(2022, 2027):
        max_q = 3 if fy == 2026 else 4
        for q in range(1, max_q + 1):
            month = QUARTER_MONTH[q]
            year = fy if q == 4 else fy - 1
            quarters.append({"quarter": q, "fy_year": fy, "period": f"{month} {year}"})
    return quarters


QUARTERS = build_quarters()


def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_checkpoint(data):
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False)


def parse_table(page):
    """Parse the HTML table. Returns (headers, blocks) or (None, None).
    Skips district subtotal rows."""
    try:
        page.wait_for_selector("table", timeout=12000)
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
        if (!mainTable || maxRows < 3) return null;
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

    if not result or len(result) < 3:
        return None, None

    # Find header row
    header_idx = 0
    for i in range(min(5, len(result))):
        row_text = " ".join(result[i]).lower()
        if "block" in row_text or "district" in row_text or "sl" in row_text:
            header_idx = i
            break

    headers = result[header_idx]
    blocks = []

    for i in range(header_idx + 1, len(result)):
        row = result[i]
        if len(row) < 3:
            continue

        row_text = " ".join(row).upper()

        # Skip grand/state totals
        if "GRAND TOTAL" in row_text or "STATE GRAND TOTAL" in row_text:
            continue
        if "STATE TOTAL" in row_text:
            continue

        # Skip district subtotal rows (e.g. "BAJALI Total", "Total", etc.)
        is_subtotal = False
        for c in range(min(3, len(row))):
            cell_upper = row[c].upper().strip()
            if cell_upper == "TOTAL" or cell_upper.endswith(" TOTAL"):
                is_subtotal = True
                break
        if is_subtotal:
            continue

        # Check for any non-zero numeric data (starting from column 3)
        has_data = False
        for c in range(3, len(row)):
            try:
                val = float(row[c].replace(",", "").strip())
                if val != 0:
                    has_data = True
                    break
            except (ValueError, AttributeError):
                cell = row[c].strip()
                if cell and cell not in ("", "-", "0", "0.00"):
                    has_data = True
                    break
        if not has_data:
            continue

        blocks.append(row)

    if not blocks:
        return None, None

    return headers, blocks


def active_state_on_page(page):
    """Read the server-side active state from the form page's "Go Back" link
    (<a href="ME"><b>Go Back</b></a>). Returns the 2-letter code or None."""
    try:
        return page.evaluate(
            """() => {
                for (const a of document.querySelectorAll('a')) {
                    const h = (a.getAttribute('href') || '').trim();
                    if (/^[A-Z]{2}$/.test(h) &&
                        (a.textContent || '').trim().toLowerCase().includes('go back')) {
                        return h;
                    }
                }
                return null;
            }"""
        )
    except Exception:
        return None


def scrape_report(page, state_code, report_page, quarter, fy_year):
    """Scrape a single blockwise report for one quarter. Returns (headers, blocks) or (None, None)."""
    try:
        # Open the report form, verifying the per-IP state binding. If another
        # client on our IP flipped it, re-select /<CODE> once and re-fetch.
        for attempt in range(2):
            page.goto(f"{BASE_URL}/{report_page}", wait_until="networkidle", timeout=30000)
            time.sleep(1)
            if active_state_on_page(page) == state_code:
                break
            if attempt == 0:
                page.goto(f"{BASE_URL}/{state_code}", wait_until="networkidle", timeout=30000)
                time.sleep(1)
            else:
                print(f"    binding failed (server has "
                      f"{active_state_on_page(page)!r}, want {state_code!r})")
                return None, None

        # Select quarter
        try:
            page.select_option('select[name="quarter"]', str(quarter))
        except Exception:
            return None, None
        time.sleep(0.3)

        # Select year
        try:
            page.select_option('select[name="year"]', str(fy_year))
        except Exception:
            return None, None
        time.sleep(0.3)

        # Submit
        try:
            page.click('input[type="submit"], button[type="submit"]')
        except Exception:
            try:
                page.keyboard.press("Enter")
            except Exception:
                return None, None
        time.sleep(2)

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Check for errors
        body_text = page.inner_text("body")
        if "Connection Error" in body_text or "No Data Found" in body_text or "No data found" in body_text:
            return None, None

        return parse_table(page)
    except Exception as e:
        print(f"    ERROR: {e}")
        return None, None


def main():
    all_data = load_checkpoint()
    new_data_count = 0
    total_ops = len(STATES) * len(REPORTS) * len(QUARTERS)
    done = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for state_code in STATES:
            print(f"\n{'=' * 60}")
            print(f"  STATE: {state_code}")
            print(f"{'=' * 60}")

            if state_code not in all_data:
                all_data[state_code] = {}

            # Fresh browser context per state
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()

            try:
                # Step 1: Set state session
                print(f"  Setting state session: {BASE_URL}/{state_code}")
                page.goto(f"{BASE_URL}/{state_code}", wait_until="networkidle", timeout=30000)
                time.sleep(3)

                # Step 2: Navigate to slbc.php
                page.goto(f"{BASE_URL}/slbc.php", wait_until="networkidle", timeout=30000)
                time.sleep(2)

                for report in REPORTS:
                    if report["key"] not in all_data[state_code]:
                        all_data[state_code][report["key"]] = {}

                    for q in QUARTERS:
                        done += 1

                        # Skip if already scraped
                        if q["period"] in all_data[state_code][report["key"]]:
                            continue

                        headers, blocks = scrape_report(page, state_code, report["page"], q["quarter"], q["fy_year"])

                        if headers and blocks:
                            all_data[state_code][report["key"]][q["period"]] = {
                                "headers": headers,
                                "blocks": blocks,
                            }
                            new_data_count += 1
                            print(
                                f"  [{done}/{total_ops}] {state_code}/{report['name']}/{q['period']}: "
                                f"{len(blocks)} blocks, {len(headers)} cols"
                            )
                        else:
                            # Mark as attempted
                            all_data[state_code][report["key"]][q["period"]] = None
                            if done % 30 == 0:
                                print(f"  [{done}/{total_ops}] {state_code}/{report['name']}/{q['period']}: no data")

                        # Checkpoint every 25 new data points
                        if new_data_count > 0 and new_data_count % 25 == 0:
                            save_checkpoint(all_data)
                            print(f"    [Checkpoint saved: {new_data_count} new entries]")

            except Exception as e:
                print(f"  FATAL ERROR for {state_code}: {e}")
                traceback.print_exc()
            finally:
                context.close()

            # Save checkpoint after each state
            save_checkpoint(all_data)
            print(f"  [State {state_code} done. Checkpoint saved.]")

        browser.close()

    # Clean up null entries for final output
    clean_data = {}
    total_entries = 0
    for sc in all_data:
        clean_data[sc] = {}
        for rk in all_data[sc]:
            clean_data[sc][rk] = {}
            for period, val in all_data[sc][rk].items():
                if val is not None:
                    clean_data[sc][rk][period] = val
                    total_entries += 1

    with open(OUTPUT_PATH, "w") as f:
        json.dump(clean_data, f, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"SCRAPING COMPLETE")
    print(f"  Total new data points: {new_data_count}")
    print(f"  Total entries in output: {total_entries}")
    print(f"  Output: {OUTPUT_PATH}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
