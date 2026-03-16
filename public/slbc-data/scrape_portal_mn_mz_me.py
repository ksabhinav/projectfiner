#!/usr/bin/env python3
"""
Targeted scraper for Manipur, Mizoram, Meghalaya district-level data
from onlineslbcne.nic.in. Uses the same approach as SLBC NE Scraper v5
but with auto-detected form actions.
"""

import sys, time, json, csv, os, warnings
from itertools import product

import requests
from bs4 import BeautifulSoup

warnings.filterwarnings('ignore')

BASE_URL = "https://onlineslbcne.nic.in"

STATES = {"MN": "Manipur", "MZ": "Mizoram", "ME": "Meghalaya"}

QUARTER_MAP = {"June": "1", "September": "2", "December": "3", "March": "4"}
QUARTERS = list(QUARTER_MAP.keys())

YEAR_MAP = {
    "FY2017-2018": "2018", "FY2018-2019": "2019", "FY2019-2020": "2020",
    "FY2020-2021": "2021", "FY2021-2022": "2022", "FY2022-2023": "2023",
    "FY2023-2024": "2024", "FY2024-2025": "2025", "FY2025-2026": "2026",
}
YEARS = list(YEAR_MAP.keys())

# District-level reports only
REPORTS = {
    "ACP_OS_D":      ("districtwiseacpoutstandings.php",           "District-wise ACP Outstanding"),
    "ACP_OS_SUM_D":  ("districtwiseAcpOSsummary.php",              "District-wise ACP (PS) Outstanding & NPA Summary"),
    "ACP_DA_D":      ("districtwiseacpdisbursementAgri.php",       "District-wise ACP Disbursement (Agri)"),
    "ACP_DM_D":      ("districtwiseacpdisbursementMsme.php",       "District-wise ACP Disbursement (MSME)"),
    "ACP_DO_D":      ("districtwiseacpdisbursementOther.php",      "District-wise ACP Disbursement (Other PS)"),
    "ACP_DN_D":      ("districtwiseacpdisbursementNonps.php",      "District-wise ACP Disbursement (Non-Priority)"),
    "ACP_NPA_D":     ("districtwiseAcpnpa.php",                    "District-wise ACP NPA"),
    "ACP_PERF_D":    ("districtwiseAcpperformance.php",            "District-wise ACP Performance vs Target"),
    "ACP_NPS_D":     ("districtwiseAcpOSNPSsummary.php",           "District-wise NPS Outstanding & NPA Summary"),
    "AGRI_OS_D":     ("districtwiseAGRIoutstandings.php",          "District-wise Agri (PS) Outstanding"),
    "AGRI_NPA_D":    ("districtwiseAGRInpa.php",                   "District-wise Agri (PS) NPA"),
    "MSME_OS_D":     ("districtwiseMSMEoutstandings.php",          "District-wise MSME (PS) Outstanding"),
    "MSME_NPA_D":    ("districtwiseMSMEnpa.php",                   "District-wise MSME (PS) NPA"),
    "OTHER_OS_D":    ("districtwiseOTHERoutstandings.php",         "District-wise Other PS Outstanding"),
    "OTHER_NPA_D":   ("districtwiseOTHERnpa.php",                  "District-wise Other PS NPA"),
    "NON_NPA_D":     ("districtwiseNONnpa.php",                    "District-wise Non-Priority NPA"),
    "WEAKER_D":      ("districtwiseLoantoweaker.php",              "District-wise Loan to Weaker Section"),
    "GOVT_NPA_D":    ("districtwiseGovtSponScheme.php",            "District-wise Govt Sponsored Schemes NPA"),
    "KCC_D":         ("districtwiseKccCard.php",                   "District-wise KCC"),
    "CROPS_KCC_D":   ("districtwisecropskcc.php",                  "District-wise Crops KCC"),
    "EDU_D":         ("districtwiseEduloan.php",                   "District-wise Education Loan"),
    "SHG_D":         ("districtwiseShg.php",                       "District-wise SHG"),
    "JLG_D":         ("districtwiseJlg.php",                       "District-wise JLG"),
    "PMMY_DISB_D":   ("districtwisePMMYDisb.php",                  "District-wise PMMY Disbursements"),
    "PMMY_OS_D":     ("districtwisePmmyouts.php",                  "District-wise PMMY Outstandings & NPA"),
    "MIN_D_D":       ("districtwiseMinorityDisb.php",              "District-wise Minority Disbursements"),
    "MIN_O_D":       ("districtwiseMinorityOuts.php",              "District-wise Minority Outstandings"),
    "SCST_D":        ("districtwiseSCSTDisb.php",                  "District-wise Finance to SC/ST"),
    "WOMEN_D":       ("districtwiseFinancetoWomen.php",            "District-wise Finance to Women"),
    "PMJDY_D":       ("districtwisePMJDY.php",                     "District-wise PMJDY"),
    "SBY_D":         ("districtwiseSBY.php",                       "District-wise Social Security Schemes"),
    "SUI_D":         ("districtwiseSUI.php",                       "District-wise SUI"),
    "AADHAAR_D":     ("districtwiseAadhaar.php",                   "District-wise Aadhaar Authentication"),
    "IC_DISB_D":     ("districtwiseInvestmentcreditDisb.php",      "District-wise Investment Credit Agri Disbursement"),
    "IC_OUTS_D":     ("districtwiseInvestmentcreditOuts.php",      "District-wise Investment Credit Agri Outstanding"),
    "FI_KCC_D":      ("districtwiseFIKCC.php",                     "District-wise FI & KCC"),
    "DIGITAL_D":     ("districtwiseDigital.php",                   "District-wise Digital Transactions"),
    "PMEGP_D":       ("districtwisePmegpdata.php",                 "District-wise PMEGP"),
    "NULM_D":        ("districtwiseNulm.php",                      "District-wise NULM"),
    "NRLM_D":        ("districtwiseNrlmdata.php",                  "District-wise NRLM"),
    "HOUSING_D":     ("districtwisefinanceunderhousing.php",       "District-wise Housing Finance"),
    "CDR_D":         ("districtwiseCdrdata.php",                   "District-wise Branches/ATM/BC/Deposits/Advances/CDR"),
    "CDR_RATIO_D":   ("CDRationdistrictwise.php",                  "District-wise Business & CD Ratio"),
    "BRANCH_D":      ("branchnetworkdistrictwise.php",             "District-wise Branch Network"),
    "CROPS_D":       ("districtwisecrops.php",                     "District-wise Crops"),
}

ID_KEYWORDS = {"sl", "no.", "no ", "serial", "district", "block", "bank",
               "state", "area", "name", "region", "zone", "branch"}

# ── Session ──────────────────────────────────────────────────────

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-IN,en;q=0.9",
})
SESSION.verify = False

# ── Checkpoint ───────────────────────────────────────────────────

CHECKPOINT_FILE = "scrape_missing_checkpoint.json"

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}

def save_checkpoint(cp):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(cp, f)

def is_done(cp, key):
    return key in cp

def mark_done(cp, key, had_data):
    cp[key] = had_data
    save_checkpoint(cp)

# ── Helpers ──────────────────────────────────────────────────────

def get_page(url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, timeout=30)
            r.raise_for_status()
            return BeautifulSoup(r.content, "lxml")
        except Exception as e:
            print(f"  GET attempt {attempt}/{retries} failed: {e}", file=sys.stderr)
            if attempt < retries:
                time.sleep(3 * attempt)
    return None


def post_page(url, data, referer=None, retries=3):
    headers = {}
    if referer:
        headers["Referer"] = referer
        headers["Origin"] = BASE_URL
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.post(url, data=data, headers=headers, timeout=30)
            r.raise_for_status()
            return BeautifulSoup(r.content, "lxml")
        except Exception as e:
            print(f"  POST attempt {attempt}/{retries} failed: {e}", file=sys.stderr)
            if attempt < retries:
                time.sleep(3 * attempt)
    return None


def extract_table(soup):
    tables = soup.find_all("table")
    best, best_score = None, 0
    for t in tables:
        tds = t.find_all(["td", "th"])
        rows = t.find_all("tr")
        score = len(rows) * 2 + len(tds)
        if score > best_score and len(tds) > 4:
            best, best_score = t, score
    if not best:
        return []
    data = []
    for tr in best.find_all("tr"):
        row = [c.get_text(separator=" ", strip=True) for c in tr.find_all(["th", "td"])]
        if any(cell.strip() for cell in row):
            data.append(row)
    return data


def is_id_col(header):
    h = header.lower()
    return any(kw in h for kw in ID_KEYWORDS)


def rows_to_long(rows, state_code, state_name, report_key, report_name, quarter, year):
    """Convert table rows to long-format dicts."""
    if len(rows) < 2:
        return []
    headers = rows[0]
    result = []
    for row in rows[1:]:
        if len(row) != len(headers):
            row = row[:len(headers)] + [''] * max(0, len(headers) - len(row))

        # Get district name (first non-serial text column)
        district = ""
        for h, v in zip(headers, row):
            if is_id_col(h) and not any(kw in h.lower() for kw in ("sl", "no.", "serial")):
                district = v.strip()
                break
        if not district:
            # Try second column
            if len(row) > 1:
                district = row[1].strip()

        # Skip total rows
        if 'total' in district.lower() and ('grand' in district.lower() or district.lower().strip() == 'total'):
            continue

        for h, v in zip(headers, row):
            if is_id_col(h):
                continue
            v = v.strip()
            if not v:
                continue
            result.append({
                "state_code": state_code,
                "state_name": state_name,
                "report_key": report_key,
                "report_name": report_name,
                "level": "district",
                "fiscal_year": year,
                "quarter": quarter,
                "district": district,
                "block": "",
                "bank": "",
                "metric": h.strip(),
                "value": v,
            })
    return result


def fetch_report(form_endpoint, state_code, quarter_label, year_label):
    form_url = f"{BASE_URL}/{form_endpoint}"
    q_val = QUARTER_MAP[quarter_label]
    y_val = YEAR_MAP[year_label]

    soup = get_page(form_url)
    if soup is None:
        return []

    # Auto-detect form action
    form = soup.find("form")
    if not form:
        return []

    action = form.get("action", "").strip()
    if not action:
        return []
    if not action.startswith("http"):
        action = BASE_URL + "/" + action.lstrip("/")

    # Get token
    token_inp = form.find("input", attrs={"name": "token"})
    token = token_inp["value"] if token_inp else ""

    # POST
    post_data = {"quarter": q_val, "year": y_val, "token": token, "View": "View Report >>"}
    result_soup = post_page(action, post_data, referer=form_url)
    if result_soup is None:
        return []

    # Check for error
    if "error.php" in str(result_soup):
        return []

    rows = extract_table(result_soup)
    if len(rows) < 2:
        return []

    # Check if all data is zeros
    if len(rows) == 2:  # Only header + Grand Total
        data_cells = [c for c in rows[1] if c.strip() not in ('', 'Grand Total', 'Total')]
        if all(c.strip() in ('0', '0.00', '0.0') for c in data_cells):
            return []

    return rows


# ── Main ─────────────────────────────────────────────────────────

def main():
    checkpoint = load_checkpoint()
    csv_file = "slbc_missing_states_district.csv"
    csv_fields = ["state_code", "state_name", "report_key", "report_name",
                  "level", "fiscal_year", "quarter", "district", "block", "bank",
                  "metric", "value"]

    # Open CSV in append mode
    file_exists = os.path.exists(csv_file)
    csvf = open(csv_file, 'a', newline='', encoding='utf-8')
    writer = csv.DictWriter(csvf, fieldnames=csv_fields)
    if not file_exists:
        writer.writeheader()

    total_data = 0
    total_empty = 0
    total_skip = 0

    for state_code, state_name in STATES.items():
        print(f"\n{'='*60}")
        print(f"  {state_name} ({state_code})")
        print(f"{'='*60}")

        # Visit state landing page
        get_page(f"{BASE_URL}/{state_code}")
        SESSION.headers["Referer"] = f"{BASE_URL}/{state_code}"
        time.sleep(1)

        for report_key, (endpoint, report_name) in REPORTS.items():
            print(f"\n  [{state_code}] {report_name}")

            for quarter, year in product(QUARTERS, YEARS):
                cp_key = f"{state_code}|{report_key}|{quarter}|{year}"

                if is_done(checkpoint, cp_key):
                    total_skip += 1
                    continue

                rows = fetch_report(endpoint, state_code, quarter, year)

                if not rows:
                    total_empty += 1
                    mark_done(checkpoint, cp_key, False)
                    continue

                long_rows = rows_to_long(rows, state_code, state_name,
                                         report_key, report_name, quarter, year)

                if long_rows:
                    total_data += 1
                    writer.writerows(long_rows)
                    csvf.flush()
                    districts = set(r["district"] for r in long_rows)
                    print(f"    ✓ {quarter} {year}: {len(districts)} districts, "
                          f"{len(rows[0])} fields, {len(long_rows)} values")
                else:
                    total_empty += 1

                mark_done(checkpoint, cp_key, bool(long_rows))
                time.sleep(0.3)  # Be polite

    csvf.close()

    print(f"\n{'='*60}")
    print(f"  DONE: {total_data} with data, {total_empty} empty, {total_skip} skipped (checkpoint)")
    print(f"  Output: {csv_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
