"""
Uttar Pradesh SLBC extractor.

UP SLBC publishes quarterly agenda booklets at slbcup.com/Agenda/.
PDFs are 160-200 pages, 40-100 MB. Most district-wise tables don't extract
cleanly via pdfplumber.extract_tables() — we use text-line regex parsing
instead, scanning each page for an annexure title and then parsing the
"<sno> <district> <numbers...>" rows that follow.

12+ text-native PDFs cover Mar 2019 → Mar 2022 / Jun 2022.
2020-03 + 2020-12 may be partially corrupt — handled by try/except.

Output schema matches FINER's other state extractors (telangana, uttarakhand):
  uttar-pradesh_complete.json
  uttar-pradesh_fi_timeseries.json
  uttar-pradesh_fi_timeseries.csv
  quarterly/{YYYY-MM}/{category}.csv
"""
import csv, json, os, re, glob, sys
from collections import defaultdict
from pathlib import Path
import pdfplumber

SRC_DIR = Path(__file__).resolve().parent

# ─── 75 UP districts (canonical, per FINER DB state_lgd=9) ────────────
UP_CANONICAL = [
    'Agra', 'Aligarh', 'Ambedkar Nagar', 'Amethi', 'Amroha', 'Auraiya', 'Ayodhya',
    'Azamgarh', 'Baghpat', 'Bahraich', 'Ballia', 'Balrampur', 'Banda', 'Barabanki',
    'Bareilly', 'Basti', 'Bhadohi', 'Bijnor', 'Budaun', 'Bulandshahr', 'Chandauli',
    'Chitrakoot', 'Deoria', 'Etah', 'Etawah', 'Farrukhabad', 'Fatehpur', 'Firozabad',
    'Gautam Buddha Nagar', 'Ghaziabad', 'Ghazipur', 'Gonda', 'Gorakhpur', 'Hamirpur',
    'Hapur', 'Hardoi', 'Hathras', 'Jalaun', 'Jaunpur', 'Jhansi', 'Kannauj',
    'Kanpur Dehat', 'Kanpur Nagar', 'Kasganj', 'Kaushambi', 'Kheri', 'Kushi Nagar',
    'Lalitpur', 'Lucknow', 'Maharajganj', 'Mahoba', 'Mainpuri', 'Mathura', 'Mau',
    'Meerut', 'Mirzapur', 'Moradabad', 'Muzaffarnagar', 'Pilibhit', 'Pratapgarh',
    'Prayagraj', 'Rae Bareli', 'Rampur', 'Saharanpur', 'Sambhal', 'Sant Kabeer Nagar',
    'Shahjahanpur', 'Shamli', 'Shravasti', 'Siddharth Nagar', 'Sitapur', 'Sonbhadra',
    'Sultanpur', 'Unnao', 'Varanasi',
]

# ─── Aliases — PDF names → canonical ──────────────────────────────────
ALIASES = {}
for d in UP_CANONICAL:
    # Various spellings the PDFs use; we collapse to a normalized key
    ALIASES[_n := re.sub(r'[^a-z]', '', d.lower())] = d

# Specific renames + spellings
ALT = {
    'allahabad': 'Prayagraj',
    'faizabad': 'Ayodhya',
    'santravidasnagar': 'Bhadohi',
    'santravidasnagarbhadohi': 'Bhadohi',
    'lakhimpurkheri': 'Kheri',
    'lakhimpur': 'Kheri',
    'santkabirnagar': 'Sant Kabeer Nagar',
    'santkabeernagar': 'Sant Kabeer Nagar',
    'siddharthnagar': 'Siddharth Nagar',
    'siddharth nagar': 'Siddharth Nagar',
    'kushinagar': 'Kushi Nagar',
    'raebareli': 'Rae Bareli',
    'gautambuddhnagar': 'Gautam Buddha Nagar',
    'gautambudhanagar': 'Gautam Buddha Nagar',
    'gautamBuddhaNagar': 'Gautam Buddha Nagar',
    'gbnagar': 'Gautam Buddha Nagar',
    'noida': 'Gautam Buddha Nagar',
    'hamirpur': 'Hamirpur',
    'hamir pur': 'Hamirpur',
    'kanpurnagar': 'Kanpur Nagar',
    'kanpurdehat': 'Kanpur Dehat',
    # OCR/spacing artefacts seen in the PDFs
    'ambedkarnagar': 'Ambedkar Nagar',
    'amethi': 'Amethi',
    'baraBanki': 'Barabanki',
    'barabanki': 'Barabanki',
    'baraBanki': 'Barabanki',
    'sonebhadra': 'Sonbhadra',
    'sonebhadr': 'Sonbhadra',
    'shrawasti': 'Shravasti',
    'shravasti': 'Shravasti',
    'shrawastiSrawasti': 'Shravasti',
    'sharnf': 'Shamli',
    'shamli': 'Shamli',
    'sambhal': 'Sambhal',
    'avodhya': 'Ayodhya',
    'avodhya': 'Ayodhya',
    'bijnour': 'Bijnor',
    'badaun': 'Budaun',
    'budaun': 'Budaun',
    'urinao': 'Unnao',
    'unnao': 'Unnao',
    'neorra': 'Deoria',  # OCR misread
    'deoria': 'Deoria',
    'kushlnagar': 'Kushi Nagar',
    'kushinaqar': 'Kushi Nagar',
    'mahoba': 'Mahoba',
    'meerut': 'Meerut',
    'mainpuri': 'Mainpuri',
    'mathura': 'Mathura',
    'mau': 'Mau',
    'prayagraj': 'Prayagraj',
    'firozabad': 'Firozabad',
    'firazabad': 'Firozabad',
    'avraiya': 'Auraiya',
    'auraiya': 'Auraiya',
    'amroha': 'Amroha',
    'agra': 'Agra',
    'aligarh': 'Aligarh',
    'azamgarh': 'Azamgarh',
    'azamarh': 'Azamgarh',
    'arra': 'Agra',
    'baghpat': 'Baghpat',
    'bahraich': 'Bahraich',
    'ballia': 'Ballia',
    'balrampur': 'Balrampur',
    'balrarnpur': 'Balrampur',
    'banda': 'Banda',
    'bareilly': 'Bareilly',
    'basti': 'Basti',
    'bhadohi': 'Bhadohi',
    'bulandshahr': 'Bulandshahr',
    'chandauli': 'Chandauli',
    'chitrakoot': 'Chitrakoot',
    'chitrakoocrt': 'Chitrakoot',
    'chitrakoootot': 'Chitrakoot',
    'etah': 'Etah',
    'etawah': 'Etawah',
    'farrukhabad': 'Farrukhabad',
    'fatehpur': 'Fatehpur',
    'ghaziabad': 'Ghaziabad',
    'ghazipur': 'Ghazipur',
    'gonda': 'Gonda',
    'gorakhpur': 'Gorakhpur',
    'hapur': 'Hapur',
    'hardoi': 'Hardoi',
    'hathras': 'Hathras',
    'jalaun': 'Jalaun',
    'jaunpur': 'Jaunpur',
    'jhansi': 'Jhansi',
    'kannauj': 'Kannauj',
    'kannau': 'Kannauj',
    'kasganj': 'Kasganj',
    'kaushambi': 'Kaushambi',
    'lalitpur': 'Lalitpur',
    'lucknow': 'Lucknow',
    'maharajganj': 'Maharajganj',
    'mirzapur': 'Mirzapur',
    'moradabad': 'Moradabad',
    'muzaffarnagar': 'Muzaffarnagar',
    'pilibhit': 'Pilibhit',
    'pratapgarh': 'Pratapgarh',
    'rampur': 'Rampur',
    'saharanpur': 'Saharanpur',
    'shahjahanpur': 'Shahjahanpur',
    'sitapur': 'Sitapur',
    'sultanpur': 'Sultanpur',
    'varanasi': 'Varanasi',
    'vizianagaram': None,  # not UP
}
for k, v in ALT.items():
    if v is None: continue
    ALIASES[re.sub(r'[^a-z]', '', k.lower())] = v

SKIP_ROWS = {'total', 'grandtotal', 'statetotal', 'subtotal',
             'sno', 'srno', 'name', 'nameofdistrict',
             'nameofthedistrict', 'district', 'state'}


def normalize_district(name):
    """Map a raw cell value to a canonical UP district, or None."""
    if name is None:
        return None
    s = str(name).strip()
    s = re.sub(r'^\d+[\.\s]+', '', s)  # strip leading "1. "
    s = s.strip(' .,*\'":;()-')
    if not s:
        return None
    key = re.sub(r'[^a-z]', '', s.lower())
    if key in SKIP_ROWS or not key:
        return None
    if key in ALIASES:
        return ALIASES[key]
    # Try removing trailing single chars (OCR noise)
    if len(key) > 4:
        for cut in (1, 2):
            if key[:-cut] in ALIASES:
                return ALIASES[key[:-cut]]
    return None


def parse_value(s):
    if s is None: return None
    s = str(s).strip().replace(',', '').replace('%', '').strip()
    if s in ('', '-', '—', 'N/A', 'NA', 'Nil', 'nil', 'NIL', 'NA.', '.', '..'):
        return None
    m = re.match(r'^[+-]?\d+(\.\d+)?$', s)
    if not m: return None
    try:
        return float(s)
    except ValueError:
        return None


def to_snake(s):
    if not s: return ''
    s = str(s).strip().lower()
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[^\w]', '_', s)
    s = re.sub(r'_+', '_', s)
    return s.strip('_')


# ─── Annexure / category classification ───────────────────────────────

def classify_page(text):
    """Return (category, fields_hint) or (None, None) if not a district-wise table.

    Matching is done against ``flat`` (uppercase, all separators stripped) so
    the OCR'd booklets — where spaces are missing or extra periods/dashes appear —
    still classify correctly.
    """
    if not text:
        return (None, None)
    upper = text.upper()
    # Strip ALL non-alphanumerics to defeat the random spacing/punctuation
    flat = re.sub(r'[^A-Z0-9]', '', upper)

    # Must look like a district-wise table
    is_dist = ('DISTRICTWISE' in flat or 'DISTRICTSWISE' in flat
               or 'NAMEOFTHEDISTRICT' in flat or 'NAMEOFDISTRICT' in flat
               or 'NAMEOFTHEDISTRIA' in flat  # OCR mangled "DISTRICT"
               )
    if not is_dist:
        return (None, None)

    # Reject obvious bank-wise tables that mention district somewhere
    if ('NAMEOFTHEBANK' in flat or 'NAMEOFBANK' in flat
            or 'BANKWISE' in flat[:100]) and 'NAMEOFTHEDISTRICT' not in flat and 'NAMEOFDISTRICT' not in flat:
        return (None, None)

    # PMSBY / PMJJBY claims come BEFORE PMJDY (their flat both contain PMJDY-ish keys)
    if 'PMSBY' in flat or 'PRADHANMANTRISURAKSHA' in flat:
        return ('social_security_pmsby', None)
    if 'PMJJBY' in flat or 'PRADHANMANTRIJEEVAN' in flat:
        return ('social_security_pmjjby', None)
    if 'ATALPENSION' in flat or 'APYDISTRICTWISE' in flat or ('APY' in upper and 'SUBSCRIBER' in upper):
        return ('social_security_apy', None)
    if 'JANSURAKSHA' in flat:
        return ('jansuraksha', None)

    # PMJDY
    if 'PMJDY' in flat or 'JANDHAN' in flat or 'PRADHANMANTRIJAN' in flat:
        return ('pmjdy', None)

    if 'CDRATIO' in flat or 'CREDITDEPOSIT' in flat:
        return ('credit_deposit_ratio', None)

    if 'KISANCREDIT' in flat or ('KCC' in flat and 'KCCCASES' not in flat):
        return ('kcc', None)

    if 'MUDRAYOJANA' in flat or 'PMMY' in flat or 'PRADHANMANTRIMUDRA' in flat:
        return ('mudra', None)

    if 'STANDUPINDIA' in flat or 'STANDUP' in flat:
        return ('stand_up_india', None)

    if 'PMEGP' in flat or 'EMPLOYMENTGENERATION' in flat:
        return ('pmegp', None)

    if 'PMAY' in flat or 'PRADHANMANTRIAWAS' in flat:
        return ('housing_pmay', None)

    if ('NRLM' in flat or 'SELFHELP' in flat
            or 'NATIONALRURALLIVELIHOOD' in flat or 'SHGBANKLINKAGE' in flat
            or ('SHG' in flat and 'SHGS' in flat)):
        return ('shg', None)

    if 'CGTMSE' in flat:
        return ('cgtmse', None)

    if 'ANIMALHUSBANDRY' in flat:
        return ('animal_husbandry', None)

    if 'FISHERIES' in flat or 'FISHERY' in flat:
        return ('fisheries', None)

    if 'DISTRICTWISEATM' in flat or 'ATMS' in flat[:200]:
        # ATM page is just "District wise ATMs : Uttar Pradesh" + serial+district+count
        return ('atm_network', None)

    if 'BANKMITRA' in flat or 'BCNETWORK' in flat:
        return ('bank_mitra', None)

    if 'EDUCATIONLOAN' in flat:
        return ('education_loan', None)

    if 'PRIORITYSECTOR' in flat:
        if 'NONPRIORITY' in flat:
            return ('non_priority_sector', None)
        return ('priority_sector', None)

    if 'ANNUALCREDITPLAN' in flat or flat.count('ACP') >= 2:
        return ('acp_achievement', None)

    if 'WOMENENTREPRENEUR' in flat or 'WOMENBORROW' in flat:
        return ('women_finance', None)

    return (None, None)


# ─── Header parsing ───────────────────────────────────────────────────

def find_header_text(text):
    """Pull the first 1-3 lines after the title for header inference."""
    lines = text.split('\n')
    # Skip blank and title lines (first ~3 lines), take next non-empty
    return lines[:8]


# ─── Row extraction from text lines ──────────────────────────────────

# Pattern: optional whitespace, sno, whitespace, district name (words), whitespace, numbers
ROW_PATTERN = re.compile(
    r'^\s*(\d{1,3})\s+'                                # serial number
    r'([A-Za-z][A-Za-z\.\'\(\)\-\s]{2,40}?)\s+'        # district name
    r'((?:[+-]?\d+(?:[\.,]\d+)?\s*){2,})'              # at least 2 numeric tokens
    r'\s*$'
)
# Some rows have district name with embedded digits, e.g. "Sant Ravidas Nagar Bhadohi 123 ..."
# We allow multi-word district names. The non-greedy match terminates at whitespace before
# the first numeric token.

def parse_data_row(line):
    """Try to parse a 'N. district num1 num2 ...' row. Returns (district, [floats]) or None."""
    m = ROW_PATTERN.match(line)
    if not m:
        return None
    sno, dname_raw, numstr = m.groups()
    dname = normalize_district(dname_raw)
    if not dname:
        return None
    nums = re.findall(r'[+-]?\d+(?:[\.,]\d+)?', numstr)
    vals = [parse_value(n) for n in nums]
    vals = [v for v in vals if v is not None]
    return (dname, vals)


# ─── Field-name mapping per category ──────────────────────────────────

# For each category, we know the typical column order from the headers.
# When we extract N numeric values per row we map them to these field names.
# If the column count doesn't match exactly we fall back to col_N labels.

CATEGORY_FIELDS = {
    'pmjdy': [
        # Order seen in 2022-03 page 14:
        # rural_a/c, urban_a/c, male, female, total_a/c, active, balance,
        # zero_bal, ru-pay-issued, rupay-active, %active, %rupay
        # 12 columns
        'rural_no', 'urban_no', 'male_no', 'female_no', 'total_pmjdy_no',
        'active_no', 'balance_amt_crore', 'zero_balance_no', 'rupay_issued_no',
        'rupay_active_no', 'active_pct', 'rupay_active_pct',
    ],
    'social_security_pmjjby': [
        # PMJJBY claims: paid, rejected, under_process, pending_with_insurer, total, amount
        'claims_paid_no', 'claims_rejected_no', 'claims_under_process_no',
        'claims_pending_no', 'claims_total_no', 'claims_amount_crore',
    ],
    'social_security_pmsby': [
        'claims_paid_no', 'claims_rejected_no', 'claims_under_process_no',
        'claims_pending_no', 'claims_total_no', 'claims_amount_crore',
    ],
    'social_security_apy': [
        'subscribers_fy15', 'subscribers_fy16', 'subscribers_fy17',
        'subscribers_fy18', 'subscribers_fy19', 'subscribers_fy20',
        'subscribers_fy21', 'subscribers_fy22', 'cumulative_no',
    ],
    'atm_network': ['no_of_atm'],
    'bank_mitra': ['no_of_bank_mitra'],
    'kcc': [
        # commonly: target_no, target_amt, achievement_no, achievement_amt, %_no, %_amt
        'target_no', 'target_amt', 'achievement_no', 'achievement_amt',
        'achievement_pct_no', 'achievement_pct_amt',
    ],
    'shg': [
        'target_no', 'target_amt', 'achievement_no', 'achievement_amt',
        'achievement_pct_no', 'achievement_pct_amt',
    ],
    'mudra': [
        'shishu_no', 'shishu_amt', 'kishore_no', 'kishore_amt',
        'tarun_no', 'tarun_amt', 'total_no', 'total_amt',
    ],
    'pmegp': [
        'target_projects', 'target_margin_money', 'target_employment',
        'sponsored_projects', 'sanctioned_projects', 'sanctioned_amt',
        'disbursed_projects', 'disbursed_amt',
    ],
    'stand_up_india': [
        'sc_st_loans', 'sc_st_amount', 'women_loans', 'women_amount',
        'total_loans', 'total_amount',
    ],
    'cgtmse': [
        'no_of_accounts', 'amount_crore',
    ],
    'animal_husbandry': [
        'target_no', 'achievement_no', 'amount_crore',
    ],
    'fisheries': [
        'target_no', 'achievement_no', 'amount_crore',
    ],
    'credit_deposit_ratio': [
        # Lead-district view: only one row per bank with district + (Deposits, Advances, CDR)
        # But this is often per bank not per district. We try anyway.
        'total_deposit', 'total_advances', 'cd_ratio',
    ],
    'priority_sector': None,  # generic numbered fields
    'non_priority_sector': None,
    'acp_achievement': None,
    'women_finance': None,
    'education_loan': None,
    'housing_pmay': None,
    'social_security': None,
}


def assign_fields(category, vals):
    fields = CATEGORY_FIELDS.get(category)
    rec = {}
    if fields:
        for i, name in enumerate(fields):
            if i < len(vals) and vals[i] is not None:
                rec[name] = vals[i]
    else:
        for i, v in enumerate(vals):
            if v is not None:
                rec[f'col_{i+1}'] = v
    return rec


# ─── Main per-PDF extractor ───────────────────────────────────────────

def extract_pdf(pdf_path):
    """Returns dict of category → {district: {field: value}}."""
    result = defaultdict(lambda: defaultdict(dict))
    try:
        p = pdfplumber.open(pdf_path)
    except Exception as e:
        print(f"  ERR opening: {e}")
        return result

    # Walk pages with state machine: when we see a district-wise title, we
    # accumulate rows until next title or end of page region.
    current_cat = None
    rows_in_section = []

    for page_idx, page in enumerate(p.pages):
        try:
            text = page.extract_text() or ''
        except Exception:
            continue

        cat, _ = classify_page(text)
        if cat:
            current_cat = cat
            rows_in_section = []

        if not current_cat:
            continue

        # Try parsing each line as a data row
        section_rows = []
        for line in text.split('\n'):
            parsed = parse_data_row(line)
            if parsed:
                dname, vals = parsed
                section_rows.append((dname, vals))

        # If page has too few district rows (< 5) and we didn't just start a new category,
        # likely a header / non-data page — skip.
        if section_rows:
            for dname, vals in section_rows:
                rec = assign_fields(current_cat, vals)
                if rec:
                    # Merge — most recent wins for overlapping fields
                    result[current_cat][dname].update(rec)

    p.close()
    # Drop categories with too few districts (likely misclassified)
    cleaned = {}
    for cat, dist_data in result.items():
        if len(dist_data) >= 15:
            cleaned[cat] = dict(dist_data)
        else:
            # report dropped
            pass
    return cleaned


# ─── Pipeline ────────────────────────────────────────────────────────

QUARTER_LABEL = {
    '2019-03': 'March 2019', '2019-06': 'June 2019', '2019-09': 'September 2019',
    '2019-12': 'December 2019',
    '2020-03': 'March 2020', '2020-06': 'June 2020', '2020-09': 'September 2020',
    '2020-12': 'December 2020',
    '2021-03': 'March 2021', '2021-06': 'June 2021', '2021-09': 'September 2021',
    '2021-12': 'December 2021',
    '2022-03': 'March 2022', '2022-06': 'June 2022', '2022-09': 'September 2022',
    '2022-12': 'December 2022',
}


def main():
    pdfs = sorted(glob.glob(str(SRC_DIR / '20*-*_booklet.pdf')))
    print(f"Found {len(pdfs)} UP booklets")

    complete = {'state': 'Uttar Pradesh', 'quarters': {}}
    for fp in pdfs:
        m = re.search(r'(\d{4}-\d{2})_booklet\.pdf', os.path.basename(fp))
        if not m:
            continue
        period = m.group(1)
        label = QUARTER_LABEL.get(period, period)
        print(f"\n=== {os.path.basename(fp)} → {period} ({label}) ===")
        try:
            cats = extract_pdf(fp)
        except Exception as e:
            print(f"  EXTRACTION ERROR: {e}")
            continue
        if not cats:
            print(f"  no district tables extracted")
            continue
        tables_dict = {}
        for cat, dist_data in cats.items():
            field_set = []
            for d, rec in dist_data.items():
                for fld in rec:
                    if fld not in field_set:
                        field_set.append(fld)
            tables_dict[cat] = {
                'fields': field_set,
                'districts': dict(dist_data),
            }
            print(f"  {cat}: {len(dist_data)} districts, {len(field_set)} fields")
        complete['quarters'][period] = {'period': label, 'tables': tables_dict}

    out_complete = SRC_DIR / 'uttar-pradesh_complete.json'
    with open(out_complete, 'w') as f:
        json.dump(complete, f, indent=2)
    print(f"\nWrote {out_complete.name} ({out_complete.stat().st_size//1024} KB)")

    # Build fi_timeseries.json
    periods_out = []
    for period in sorted(complete['quarters'].keys()):
        q = complete['quarters'][period]
        records = {}
        for cat, table in q['tables'].items():
            for dname, rec in table['districts'].items():
                if dname not in records:
                    records[dname] = {'district': dname, 'period': q['period']}
                for fld, v in rec.items():
                    records[dname][f"{cat}__{fld}"] = v
        periods_out.append({'period': q['period'], 'districts': list(records.values())})
    with open(SRC_DIR / 'uttar-pradesh_fi_timeseries.json', 'w') as f:
        json.dump({'periods': periods_out}, f, indent=2)
    print(f"Wrote uttar-pradesh_fi_timeseries.json")

    # CSV (wide)
    all_fields = set()
    for p in periods_out:
        for r in p['districts']:
            all_fields.update(r.keys())
    all_fields.discard('district'); all_fields.discard('period')
    fieldnames = ['district', 'period'] + sorted(all_fields)
    with open(SRC_DIR / 'uttar-pradesh_fi_timeseries.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for p in periods_out:
            for r in p['districts']:
                w.writerow(r)
    print(f"Wrote uttar-pradesh_fi_timeseries.csv")

    # Per-quarter per-category CSVs
    for period, q in complete['quarters'].items():
        qdir = SRC_DIR / 'quarterly' / period
        qdir.mkdir(parents=True, exist_ok=True)
        for cat, table in q['tables'].items():
            csv_path = qdir / f'{cat}.csv'
            with open(csv_path, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['District'] + table['fields'])
                for dname in UP_CANONICAL:
                    if dname in table['districts']:
                        rec = table['districts'][dname]
                        w.writerow([dname] + [rec.get(fk, '') for fk in table['fields']])

    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"Quarters extracted: {len(complete['quarters'])}")
    cat_quarters = defaultdict(int)
    cat_max_districts = defaultdict(int)
    for q in complete['quarters'].values():
        for cat, table in q['tables'].items():
            cat_quarters[cat] += 1
            cat_max_districts[cat] = max(cat_max_districts[cat], len(table['districts']))
    for cat, n in sorted(cat_quarters.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n} quarters (max {cat_max_districts[cat]} districts)")


if __name__ == '__main__':
    main()
