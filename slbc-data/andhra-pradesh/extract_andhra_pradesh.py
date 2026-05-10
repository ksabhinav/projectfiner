"""
Andhra Pradesh SLBC comprehensive extractor.

Processes all SLBC agenda PDFs in slbc-data/andhra-pradesh/ — 47 PDFs spanning
the 166th meeting (Jul 2009) through the 228th meeting (Jun 2024). Handles three
eras of district structure:

  1. Pre-2014 (United AP): districts include both modern AP and modern Telangana.
     Pre-2014 PDFs from this archive (166-201) only carry bank-wise CD ratio in
     clean tabular form, no district-wise FI tables. They yield no usable data
     and are skipped after table inspection. (When district-wise tables are
     encountered, this extractor routes them to the appropriate state.)
  2. Post-2014 split (202-219, Mar 2018 - Mar 2022): 13 modern AP districts.
  3. Post-2022 reorganisation (221+, Sep 2022 onwards): 26 modern AP districts.

Output (in slbc-data/andhra-pradesh/):
  - andhra-pradesh_complete.json
  - andhra-pradesh_fi_timeseries.json
  - andhra-pradesh_fi_timeseries.csv
  - quarterly/{YYYY-MM}/*.csv

Plus, for any pre-2014 data routed to Telangana districts (currently none, since
no clean district-wise tables are extractable from the available pre-2014 PDFs):
  - telangana_pre2014_complete.json
  - telangana_pre2014_fi_timeseries.json
"""
import csv, json, re, os, glob
from collections import defaultdict
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / 'slbc-data/andhra-pradesh'

# ─── Meeting → quarter mapping ──────────────────────────────────────
# Pre-2014 (United AP era — district tables route per-district to AP or TG)
# Post-2014 (modern AP only)
# Post-2022 (modern AP, 26 districts)
MEETING_QUARTER = {
    # Pre-2014 (Andhra Pradesh + Telangana districts mixed in source booklets)
    '166': ('2009-06', 'June 2009'),
    '170': ('2010-03', 'March 2010'),
    '174': ('2011-03', 'March 2011'),
    '175': ('2011-06', 'June 2011'),
    '176': ('2011-09', 'September 2011'),
    '177': ('2011-12', 'December 2011'),  # 201_agenda actually says 177th meeting on 24.03.2012
    '178': ('2012-03', 'March 2012'),
    '179': ('2012-06', 'June 2012'),
    '180': ('2012-09', 'September 2012'),
    '181': ('2012-12', 'December 2012'),
    '182': ('2013-03', 'March 2013'),
    '183': ('2013-06', 'June 2013'),
    '184': ('2013-09', 'September 2013'),
    '186': ('2014-03', 'March 2014'),  # last united-AP meeting
    # Post-2014 split (modern AP only, 13 districts)
    '188': ('2014-09', 'September 2014'),
    '189': ('2014-12', 'December 2014'),
    '190': ('2015-03', 'March 2015'),
    '191': ('2015-06', 'June 2015'),
    '192': ('2015-09', 'September 2015'),
    '193': ('2015-12', 'December 2015'),
    '194': ('2016-03', 'March 2016'),
    '195': ('2016-06', 'June 2016'),
    '197': ('2016-12', 'December 2016'),
    '198': ('2017-03', 'March 2017'),
    '199': ('2017-06', 'June 2017'),
    '200': ('2017-09', 'September 2017'),
    '201': ('2017-12', 'December 2017'),  # mislabelled — this PDF says 177th on 24.03.2012
    '202': ('2019-03', 'March 2019'),  # Actually 207th meeting agenda — quarter is Mar 2019
    '203': ('2018-03', 'March 2018'),
    '204': ('2018-06', 'June 2018'),
    '205': ('2018-09', 'September 2018'),
    '206': ('2018-12', 'December 2018'),
    '208': ('2019-06', 'June 2019'),  # meeting Jul 2019, quarter Jun 2019
    '209': ('2019-09', 'September 2019'),
    '210': ('2019-12', 'December 2019'),  # meeting Jan 2020, quarter Dec 2019
    '211': ('2020-03', 'March 2020'),
    '213': ('2020-09', 'September 2020'),
    '216': ('2021-06', 'June 2021'),
    '217': ('2021-09', 'September 2021'),
    '218': ('2021-12', 'December 2021'),
    '219': ('2022-03', 'March 2022'),
    # Post-2022 reorganisation (26 modern AP districts)
    '221': ('2022-09', 'September 2022'),
    '222': ('2022-12', 'December 2022'),
    '223': ('2023-03', 'March 2023'),
    '224': ('2023-06', 'June 2023'),
    '225': ('2023-09', 'September 2023'),
    '226': ('2023-12', 'December 2023'),
    '227': ('2024-03', 'March 2024'),
    '228': ('2024-06', 'June 2024'),
}

# ─── District canonicals ─────────────────────────────────────────────
# Modern AP (state_lgd=28) — 26 districts after 2022 reorg
AP_CANONICAL_DISTRICTS = [
    'Alluri Sitharama Raju', 'Anakapalli', 'Anantapur', 'Annamayya', 'Bapatla',
    'Chittoor', 'East Godavari', 'Eluru', 'Guntur', 'Kakinada', 'Konaseema',
    'Krishna', 'Kurnool', 'Nandyal', 'Ntr', 'Palnadu', 'Parvathipuram Manyam',
    'Prakasam', 'Spsr Nellore', 'Sri Sathya Sai', 'Srikakulam', 'Tirupati',
    'Visakhapatanam', 'Vizianagaram', 'West Godavari', 'Y.s.r.',
]
# Modern Telangana (state_lgd=36)
TG_CANONICAL_DISTRICTS = [
    'Hyderabad', 'Adilabad', 'Karimnagar', 'Khammam', 'Mahabubnagar',
    'Medak', 'Nalgonda', 'Nizamabad', 'Ranga Reddy', 'Warangal',
]

# Aliases from PDF source → (canonical_district, target_state_slug)
DISTRICT_ALIASES = {}

def _add(aliases, canonical, state_slug):
    for a in aliases:
        DISTRICT_ALIASES[a.lower()] = (canonical, state_slug)

# AP modern district aliases
_add(['ananthapuramu', 'anantapuramu', 'anantapur', 'ananthapur', 'anantpuram', 'anantpuramu', 'anantpuram', 'ananthapurum', 'anantapuram'], 'Anantapur', 'andhra-pradesh')
_add(['dr. b.r.ambedkar konaseema', 'dr b r ambedkar konaseema', 'b.r. ambedkar konaseema', 'ambedkar konaseema', 'konaseema'], 'Konaseema', 'andhra-pradesh')
_add(['ntr', 'n.t.r.', 'n.t.r'], 'Ntr', 'andhra-pradesh')
_add(['visakhapatnam', 'visakapatanam', 'visakhapatanam', 'visakhapattnam'], 'Visakhapatanam', 'andhra-pradesh')
_add(['spsr nellore', 'sri potti sriramulu nellore', 'nellore', 'sps nellore', 's p s r nellore', 'spsrnellore'], 'Spsr Nellore', 'andhra-pradesh')
_add(['ysr', 'ysr kadapa', 'cuddapah', 'kadapa', 'y.s.r kadapa', 'y.s.r.', 'y.s.r', 'y s r', 'y s r kadapa', 'ys.r', 'ysr cuddapah'], 'Y.s.r.', 'andhra-pradesh')
_add(['parvathipuram manyam', 'parvathipuram', 'parvathipuram-manyam'], 'Parvathipuram Manyam', 'andhra-pradesh')
_add(['sri sathya sai', 'sathya sai', 'sri satya sai'], 'Sri Sathya Sai', 'andhra-pradesh')
_add(['alluri sitharama raju', 'allur sitharama raju', 'alluri sita ramaraju', 'alluri seetharama raju'], 'Alluri Sitharama Raju', 'andhra-pradesh')
_add(['anakapalli', 'anakapalle'], 'Anakapalli', 'andhra-pradesh')
_add(['annamayya'], 'Annamayya', 'andhra-pradesh')
_add(['bapatla'], 'Bapatla', 'andhra-pradesh')
_add(['chittoor', 'chittor'], 'Chittoor', 'andhra-pradesh')
_add(['east godavari', 'eastgodavari'], 'East Godavari', 'andhra-pradesh')
_add(['eluru'], 'Eluru', 'andhra-pradesh')
_add(['guntur'], 'Guntur', 'andhra-pradesh')
_add(['kakinada'], 'Kakinada', 'andhra-pradesh')
_add(['krishna'], 'Krishna', 'andhra-pradesh')
_add(['kurnool'], 'Kurnool', 'andhra-pradesh')
_add(['nandyal'], 'Nandyal', 'andhra-pradesh')
_add(['palnadu', 'palnad'], 'Palnadu', 'andhra-pradesh')
_add(['prakasam'], 'Prakasam', 'andhra-pradesh')
_add(['srikakulam'], 'Srikakulam', 'andhra-pradesh')
_add(['tirupati', 'tirupathi'], 'Tirupati', 'andhra-pradesh')
_add(['vizianagaram'], 'Vizianagaram', 'andhra-pradesh')
_add(['west godavari', 'westgodavari'], 'West Godavari', 'andhra-pradesh')

# Telangana district aliases (for pre-2014 PDFs)
_add(['hyderabad', 'hyd'], 'Hyderabad', 'telangana')
_add(['adilabad'], 'Adilabad', 'telangana')
_add(['karimnagar', 'karim nagar'], 'Karimnagar', 'telangana')
_add(['khammam'], 'Khammam', 'telangana')
_add(['mahabubnagar', 'mahbubnagar', 'mahaboobnagar', 'mahboobnagar', 'mahaboob nagar', 'mahbub nagar', 'mahabub nagar'], 'Mahabubnagar', 'telangana')
_add(['medak'], 'Medak', 'telangana')
_add(['nalgonda'], 'Nalgonda', 'telangana')
_add(['nizamabad'], 'Nizamabad', 'telangana')
_add(['rangareddy', 'ranga reddy', 'r.r district', 'rr district', 'r r district', 'rangaareddy'], 'Ranga Reddy', 'telangana')
_add(['warangal'], 'Warangal', 'telangana')

# Skip rows
SKIP_ROWS = {'total', 'state total', 'grand total', 'state average', 'average',
             'overall', 'all districts',
             's.no.', 'sno', 'sl.no', '', 'name of the district', 'district',
             'name of the bank', 'category', None}


def normalize_district(name):
    """Map a raw PDF district name to (canonical_name, state_slug), or None."""
    if not name:
        return None
    s = str(name).strip().lower()
    # Strip leading "1. " or "1 " serial
    s = re.sub(r'^\d+[\.\s]+', '', s)
    s = re.sub(r'\s+', ' ', s)
    s = s.strip(' .*,:')
    # Strip common suffixes
    s = re.sub(r'\s+district\s*$', '', s)
    s = re.sub(r'\s+total\s*$', '', s)
    if s in SKIP_ROWS:
        return None
    if s in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[s]
    # Try removing parenthetical
    s2 = re.sub(r'\s*\([^)]*\)\s*', '', s).strip()
    if s2 in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[s2]
    return None


def parse_value(s):
    """Parse a numeric cell — strip commas, %, blanks."""
    if s is None:
        return None
    s = str(s).strip()
    if s in ('', '-', '—', '--', 'N/A', 'NA', 'Nil', 'nil', '*', '...', '…', 'na'):
        return None
    s = s.replace(',', '').replace('%', '').strip()
    m = re.match(r'^[+-]?\d+(\.\d+)?$', s)
    if not m:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_snake(s):
    """Snake-case a column header."""
    if not s:
        return ''
    s = str(s).strip()
    # collapse multi-line
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[^\w]', '_', s)
    s = re.sub(r'_+', '_', s)
    return s.lower().strip('_')


# ─── Table classification ────────────────────────────────────────────

REJECT = object()  # Sentinel: definitely not an FI category, don't fall back


def classify_table(title_text):
    """Map a table's surrounding title text to a standard category.

    Returns:
      - category string if matched
      - REJECT sentinel if explicitly rejected (caller should not fall back)
      - None if no match (caller may try alternate title source)
    """
    t = (title_text or '').lower()
    # Skip non-FI tables (DCC/DLRC meeting lists, contact lists, etc.)
    if 'dcc' in t and 'dlrc' in t:
        return REJECT
    if 'meeting scheduled' in t or 'meeting conducted' in t:
        return REJECT
    if 'allotment' in t or 'fpo' in t or 'popi' in t:
        return REJECT
    if 'lead district' in t and 'flcc' in t:
        return REJECT
    if 'unbanked' in t or 'un-banked' in t or 'un banked' in t:
        return REJECT
    if ('rsetis' in t or 'rseti' in t) and 'training' in t:
        return REJECT
    if 'ssa' in t or ' gps' in t or 'no of ssa' in t or 'no. of ssa' in t:
        return REJECT
    if 'gram panchayat' in t or 'panchayats' in t:
        return REJECT
    if 'rudseti' in t:
        return REJECT
    if 'clearing house' in t:
        return REJECT
    if 'cluster' in t and ('centres' in t or 'mandals' in t):
        return REJECT
    if 'doubling' in t and 'farmers' in t:
        return REJECT
    if 'mfi' in t:
        return REJECT
    # KCC sub-categories that aren't the main KCC count
    if 'animal husbandry' in t and 'fishery' in t:
        return REJECT
    if 'extension of kcc' in t:
        return REJECT
    # Annual credit plan target/achievement tables — different metric
    if 'annual credit plan' in t and ('target' in t or 'achievement' in t):
        return 'annual_credit_plan'
    # Loaner card tables, allotment tables
    if 'lec' in t or 'licensed cultivator' in t:
        return REJECT
    if 'farmer' in t and ('non loanee' in t or 'non-loanee' in t):
        return REJECT
    # Programme/training/operational tables
    if 'medp' in t or ' edp ' in t or 'establishment of clearing' in t:
        return REJECT
    if 'proposed' in t and 'sanctioned' in t and 'lwe' in t:
        return REJECT
    # SSA, BC coverage (header has gps/ssas/active/inactive bcs)
    if 'inactive' in t and ('bc' in t or 'bcs' in t or 'attrition' in t):
        return REJECT
    if 'gps' in t and ('no_of' in t or 'no of' in t or 'ssa' in t):
        return REJECT

    # Real categories
    if 'cd ratio' in t or 'credit deposit' in t or 'c.d. ratio' in t or 'c d ratio' in t or 'credit-deposit' in t or 'c r e d i t  d e p o s i t' in t:
        return 'credit_deposit_ratio'
    if 'pmjdy' in t or 'jan dhan' in t or 'bsbda' in t:
        return 'pmjdy'
    if 'kcc' in t or 'kisan credit' in t:
        return 'kcc'
    if 'shg' in t and ('linkage' in t or 'bank' in t or 'credit' in t or 'savings' in t):
        return 'shg'
    if 'self help group' in t:
        return 'shg'
    if 'mudra' in t or 'pmmy' in t:
        return 'mudra'
    if 'social security' in t or 'pmjjby' in t or 'pmsby' in t or 'atal pension' in t:
        return 'social_security'
    if 'pmay' in t and 'housing' in t:
        return 'housing_pmay'
    if 'housing loan' in t and 'district' in t and 'priority sector' not in t and 'annual credit plan' not in t:
        return 'housing_pmay'
    if 'education loan' in t:
        return 'education_loan'
    if 'pmegp' in t:
        return 'pmegp'
    if 'minority' in t:
        return 'minority_finance'
    if 'weaker section' in t or 'weakers' in t:
        return 'sc_st_finance'
    if 'women' in t and ('credit' in t or 'finance' in t or 'loan' in t):
        return 'women_finance'
    if 'digital' in t and ('coverage' in t or 'transaction' in t):
        return 'digital_transactions'
    if 'no. of branches' in t or 'no of branches' in t or 'number of branches' in t or 'district-wise no. of branches' in t:
        return 'branch_network'
    if ('rural' in t and 'semi urban' in t and 'urban' in t) or ('rural' in t and 'metro' in t):
        return 'branch_network'
    if 'annual credit plan' in t:
        return 'annual_credit_plan'
    if 'priority sector' in t and ('outstanding' in t or 'advances' in t):
        return 'priority_sector'
    if 'recovery' in t or ('npa' in t and 'position' in t):
        return 'recovery_npa'
    if 'aadhaar' in t and 'seed' in t:
        return 'aadhaar_authentication'
    return None


# ─── Header / table parsing ─────────────────────────────────────────

BANK_KEYWORDS = ('bank of baroda', 'bank of india', 'bank of maharashtra', 'canara bank',
                 'central bank', 'indian bank', 'punjab national', 'state bank',
                 'union bank', 'syndicate bank', 'andhra bank', 'icici', 'hdfc',
                 'axis bank', 'kotak', 'corporation bank', 'allahabad bank',
                 'sbi', 'rrb', 'nabard', 'commercial banks', 'cooperative banks',
                 'co-operative', 'regional rural', 'bank type', 'name of the bank')


def is_bankwise_table(table):
    """Detect if a table is bank-wise (rows are banks, not districts)."""
    if not table or len(table) < 4:
        return False
    bank_rows = 0
    for row in table[:min(15, len(table))]:
        for cell in row[:3]:
            if cell:
                cl = str(cell).lower()
                if any(k in cl for k in BANK_KEYWORDS):
                    bank_rows += 1
                    break
    return bank_rows >= 3


def is_district_table(table, min_districts=6):
    """Check if a table contains AP/TG districts in its data rows."""
    if not table or len(table) < 3:
        return False
    if is_bankwise_table(table):
        return False
    n_unique = set()
    for row in table:
        for cell in row:
            if cell and isinstance(cell, str):
                d = normalize_district(cell)
                if d:
                    n_unique.add(d[0])
                    break
    return len(n_unique) >= min_districts


def find_header_rows(table):
    """Return number of header rows by detecting the first row that has a district name."""
    for i, row in enumerate(table):
        for cell in row:
            if cell and isinstance(cell, str) and normalize_district(cell):
                return i
    return 1


def clean_header_cell(cell):
    """Strip embedded numeric suffixes from a header cell.
    e.g. 'CD Ratio\n115.15' → 'CD Ratio'; 'Name of the District\nAnanthapuram' → 'Name of the District'
    Also strip rotated-text noise like 'SLBC of AP 217th Meeting...'.
    """
    if not cell:
        return ''
    s = str(cell).strip()
    # Drop everything from the first newline onwards (header text usually before; data after)
    if '\n' in s:
        first = s.split('\n')[0].strip()
        # Only use first line if it doesn't look like just a number
        if first and not re.match(r'^[\d,.%\-]+$', first):
            s = first
    # Strip SLBC noise prefix
    s = re.sub(r'(?i)slbc\s+of\s+ap.*?(convener|convenor)\s*:?', '', s)
    s = re.sub(r'(?i)\d+(th|st|nd|rd)\s+meeting\s+of\s+slbc', '', s)
    s = re.sub(r'(?i)convener\s*:?\s*union\s+bank\s+of\s+india', '', s)
    return s.strip()


def build_field_names(header_rows):
    """Combine multi-row headers into one snake_case name per column."""
    if not header_rows or not header_rows[0]:
        return []
    n_cols = max(len(r) for r in header_rows)
    fields = []
    for col_idx in range(n_cols):
        parts = []
        for row in header_rows:
            if col_idx < len(row) and row[col_idx]:
                cell = clean_header_cell(row[col_idx])
                if cell and cell.lower() not in [p.lower() for p in parts]:
                    parts.append(cell)
        merged = ' '.join(parts).strip()
        # Drop trailing standalone numbers
        merged = re.sub(r'\s+[\d,.%\-]+$', '', merged).strip()
        fields.append(to_snake(merged))
    return fields


def is_noisy_field(fkey):
    """Filter out noise field names from rotated SLBC header cruft."""
    if not fkey or fkey == 's_no':
        return True
    if 'meeting_of_slbc' in fkey or 'slbc_convener' in fkey or 'slbc_convenor' in fkey:
        return True
    if 'slbc_of_ap' in fkey or 'slbc_of_a_p' in fkey:
        return True
    if fkey == 'name_of_the_district' or fkey == 'district' or fkey == 'name_of_district':
        return True
    if fkey in ('district_code', 'remarks', 's_no_1', 'sno', 'srno', 'sr_no', 'convener', 'convenor'):
        return True
    if fkey.startswith('district_'):
        return True
    if fkey.startswith('name_of_the_district_') or fkey.startswith('name_of_the_'):
        return True
    if fkey.startswith('achv') and len(fkey) <= 8:  # achv_5, achv_4_1 etc
        return True
    if len(fkey) > 70:  # very long field name = header noise
        return True
    return False


# ─── Field key standardization ──────────────────────────────────────

# Rename common fkeys to canonical names (category-agnostic)
FIELD_RENAMES = {
    'convener_cd_ratio': 'cd_ratio',
    'cd_ratio': 'cd_ratio',
    '217th_meeting_of_slbc_name_of_the_district': None,
    '217th_meeting_of_slbc_cd_ratio': 'cd_ratio',
    'no_of_active_pmjdy_a_c': 'total_pmjdy_no',
    'no_of_pmjdy_accounts': 'total_pmjdy_no',
    'no_of_pmjdy': 'total_pmjdy_no',
    'no_of_kcc': 'total_no_of_kcc',
    'kcc_no': 'total_no_of_kcc',
    'rupay_card_issued_in_kcc': 'total_no_of_kcc',
    'no_of_branches': 'total_branch',
    'no_of_brs': 'total_branch',
    'total_branches': 'total_branch',
    'total_brs': 'total_branch',
    'deposits': 'total_deposit',
    'advances': 'total_advance',
}

# Category-specific renames (applied after generic FIELD_RENAMES)
CATEGORY_FIELD_RENAMES = {
    'branch_network': {
        'rural': 'branch_rural',
        'semi_urban': 'branch_semi_urban',
        'urban': 'branch_urban',
        'metro': 'branch_metro',
        'total': 'total_branch',
    },
}


def standardize_field(fkey, category=None):
    """Apply renames; return None to drop."""
    if not fkey:
        return None
    # Strip embedded numbers from CD ratio noise
    fkey = re.sub(r'^cd_ratio_[\d_.%]+$', 'cd_ratio', fkey)
    fkey = re.sub(r'^deposits_[\d_.%]+$', 'total_deposit', fkey)
    fkey = re.sub(r'^advances_[\d_.%]+$', 'total_advance', fkey)
    if category and category in CATEGORY_FIELD_RENAMES:
        if fkey in CATEGORY_FIELD_RENAMES[category]:
            fkey = CATEGORY_FIELD_RENAMES[category][fkey]
    if fkey in FIELD_RENAMES:
        return FIELD_RENAMES[fkey]
    return fkey


# ─── Per-PDF extraction ─────────────────────────────────────────────

def extract_pdf(pdf_path):
    """Extract all district-wise tables from one PDF.

    Returns: dict[(state_slug, category)] = {'fields': [...], 'districts': {dname: {field: value}}}
    """
    out = {}  # (state_slug, category) -> {fields, districts}

    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        print(f"  ERROR opening {pdf_path}: {e}")
        return out

    with pdf:
        for page_idx, page in enumerate(pdf.pages):
            try:
                tables = page.extract_tables()
            except Exception:
                continue
            if not tables:
                continue
            try:
                text = page.extract_text() or ''
            except Exception:
                text = ''
            title_lines = text.split('\n')[:8]
            title_text = ' | '.join(title_lines)

            for tbl_idx, tbl in enumerate(tables):
                if not is_district_table(tbl, min_districts=5):
                    continue

                # Classify — try table headers FIRST (most reliable), then page text
                hdr_text = ' '.join(str(c) for r in tbl[:4] for c in r if c)
                hdr_cls = classify_table(hdr_text)
                if hdr_cls is REJECT:
                    continue  # explicit rejection from header
                category = hdr_cls
                if not category:
                    title_cls = classify_table(title_text)
                    if title_cls is REJECT:
                        continue
                    category = title_cls
                if not category:
                    # CD ratio tables often have just "S.No | Name of the District | CD Ratio"
                    cols_per_row = max(len(r) for r in tbl)
                    if cols_per_row <= 4 and 'cd ratio' in title_text.lower():
                        category = 'credit_deposit_ratio'
                if not category:
                    continue

                hdr_n = find_header_rows(tbl)
                if hdr_n < 1:
                    hdr_n = 1
                header_rows = tbl[:hdr_n]
                data_rows = tbl[hdr_n:]
                fields = build_field_names(header_rows)

                # Per state, per district records
                state_district_records = defaultdict(dict)  # state_slug -> {dname: {field: value}}

                for row in data_rows:
                    if not row:
                        continue
                    # Find first cell that normalizes to a district
                    canonical = None
                    state_slug = None
                    dname_idx = -1
                    for i, cell in enumerate(row):
                        if cell:
                            d = normalize_district(cell)
                            if d:
                                canonical, state_slug = d
                                dname_idx = i
                                break
                    if not canonical:
                        continue

                    # Build (col_i → fkey_std) — propagate non-empty headers forward to fill empty cols
                    col_to_field = {}
                    last_good_raw_field = None
                    for col_i in range(len(fields)):
                        fkey = fields[col_i]
                        if not fkey:
                            # use last good header if available
                            if last_good_raw_field:
                                fkey_use = last_good_raw_field
                            else:
                                col_to_field[col_i] = None
                                continue
                        else:
                            fkey_use = fkey
                            last_good_raw_field = fkey
                        if is_noisy_field(fkey_use):
                            col_to_field[col_i] = None
                        else:
                            col_to_field[col_i] = standardize_field(fkey_use, category)

                    rec = {}
                    for col_i, val in enumerate(row):
                        if col_i == dname_idx:
                            continue
                        if col_i >= len(fields):
                            continue
                        fkey_std = col_to_field.get(col_i)
                        if fkey_std is None:
                            continue
                        parsed = parse_value(val)
                        if parsed is None:
                            continue
                        # Only set if not already set OR existing is "default" (later col-data wins)
                        if fkey_std not in rec:
                            rec[fkey_std] = parsed
                    # Special fallback for cd_ratio when no field labeled cd_ratio but
                    # category is credit_deposit_ratio and table is small (S.No, district, value)
                    if category == 'credit_deposit_ratio' and 'cd_ratio' not in rec:
                        # Find a value in a column whose header is empty/noisy and is numeric in 5-1000 range
                        # Prefer the last column (CD ratio is usually at the end)
                        for col_i in reversed(range(len(row))):
                            if col_i == dname_idx:
                                continue
                            if col_i < len(fields) and col_to_field.get(col_i):
                                continue  # already mapped
                            v = parse_value(row[col_i])
                            if v is not None and 5 < v < 1000:
                                rec['cd_ratio'] = v
                                break
                    if rec:
                        # Merge into state_district_records (later wins for duplicates)
                        if canonical in state_district_records[state_slug]:
                            state_district_records[state_slug][canonical].update(rec)
                        else:
                            state_district_records[state_slug][canonical] = rec

                if not state_district_records:
                    continue

                # Build standardized field list (apply rename and drop dupes)
                fields_std = []
                for f in fields:
                    if is_noisy_field(f):
                        continue
                    fs = standardize_field(f, category)
                    if fs and fs not in fields_std:
                        fields_std.append(fs)

                # Merge per-state into out
                for state_slug, drecs in state_district_records.items():
                    key = (state_slug, category)
                    if key not in out:
                        out[key] = {'fields': list(fields_std), 'districts': {}}
                    for f in fields_std:
                        if f not in out[key]['fields']:
                            out[key]['fields'].append(f)
                    for dname, rec in drecs.items():
                        if dname not in out[key]['districts']:
                            out[key]['districts'][dname] = {}
                        out[key]['districts'][dname].update(rec)

    return out


# ─── Output writers ─────────────────────────────────────────────────

def write_state_outputs(state_slug, complete, src_dir, file_prefix=None):
    """Write *_complete.json, *_fi_timeseries.json, *_fi_timeseries.csv,
    plus per-quarter category CSVs."""
    if file_prefix is None:
        file_prefix = state_slug

    if state_slug == 'andhra-pradesh':
        canon_districts = AP_CANONICAL_DISTRICTS
    elif state_slug == 'telangana':
        canon_districts = TG_CANONICAL_DISTRICTS
    else:
        canon_districts = []

    out_complete = src_dir / f'{file_prefix}_complete.json'
    with open(out_complete, 'w') as f:
        json.dump(complete, f, indent=2)
    print(f"  Wrote {out_complete.name} ({out_complete.stat().st_size/1024:.1f} KB)")

    # Build fi_timeseries.json
    timeseries_periods = []
    for period_code in sorted(complete['quarters'].keys()):
        q = complete['quarters'][period_code]
        period_label = q['period']
        district_records = {}
        for cat, table in q['tables'].items():
            for dname, fields in table['districts'].items():
                if dname not in district_records:
                    district_records[dname] = {'district': dname, 'period': period_label}
                for fkey, val in fields.items():
                    flat_key = f"{cat}__{fkey}"
                    district_records[dname][flat_key] = val
        timeseries_periods.append({
            'period': period_label,
            'districts': list(district_records.values()),
        })

    out_ts = src_dir / f'{file_prefix}_fi_timeseries.json'
    with open(out_ts, 'w') as f:
        json.dump({'periods': timeseries_periods}, f, indent=2)
    print(f"  Wrote {out_ts.name} ({out_ts.stat().st_size/1024:.1f} KB)")

    # Build CSV (wide format)
    out_csv = src_dir / f'{file_prefix}_fi_timeseries.csv'
    all_fields = set()
    for period in timeseries_periods:
        for rec in period['districts']:
            all_fields.update(rec.keys())
    all_fields.discard('district')
    all_fields.discard('period')
    fieldnames = ['district', 'period'] + sorted(all_fields)
    with open(out_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for period in timeseries_periods:
            for rec in period['districts']:
                w.writerow(rec)
    print(f"  Wrote {out_csv.name} ({out_csv.stat().st_size/1024:.1f} KB)")

    # Build per-quarter per-category CSVs (only for primary state — AP)
    if state_slug == 'andhra-pradesh':
        for period_code, q in complete['quarters'].items():
            qdir = src_dir / 'quarterly' / period_code
            qdir.mkdir(parents=True, exist_ok=True)
            for cat, table in q['tables'].items():
                csv_path = qdir / f'{cat}.csv'
                field_list = ['District'] + table['fields']
                with open(csv_path, 'w', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(field_list)
                    for dname in canon_districts:
                        if dname in table['districts']:
                            rec = table['districts'][dname]
                            row = [dname] + [rec.get(fk, '') for fk in table['fields']]
                            w.writerow(row)


# ─── Main ────────────────────────────────────────────────────────────

def main():
    pdfs = sorted(glob.glob(str(SRC_DIR / '*.pdf')))
    print(f"PDFs found: {len(pdfs)}")

    pdfs_with_period = []
    for pdf in pdfs:
        m = re.search(r'(\d+)(?:rd|th|nd|st)?_agenda', os.path.basename(pdf))
        if not m:
            print(f"  skip (no meeting num): {os.path.basename(pdf)}")
            continue
        meeting = m.group(1)
        if meeting not in MEETING_QUARTER:
            print(f"  skip (unknown meeting {meeting}): {os.path.basename(pdf)}")
            continue
        period_code, period_label = MEETING_QUARTER[meeting]
        pdfs_with_period.append((pdf, meeting, period_code, period_label))

    # Process oldest-first; later PDFs win on duplicates
    pdfs_with_period.sort(key=lambda x: x[2])

    # Per-state, per-quarter accumulator
    # state_slug -> period_code -> {period_label, tables: {cat: {fields, districts}}}
    state_quarters = defaultdict(lambda: defaultdict(lambda: {'period': '', 'tables': {}}))

    skipped_pdfs = []
    MIN_DISTRICTS = 8  # threshold for accepting a category

    for pdf, meeting, period_code, period_label in pdfs_with_period:
        name = os.path.basename(pdf)
        try:
            with pdfplumber.open(pdf) as p:
                page_count = len(p.pages)
        except Exception as e:
            print(f"  skip {name}: cannot open ({e})")
            skipped_pdfs.append((name, f"open error: {e}"))
            continue
        if page_count < 8:
            print(f"  skip {name}: only {page_count} pages (truncated/broken download)")
            skipped_pdfs.append((name, f"truncated to {page_count} pages"))
            continue

        print(f"\n=== {name} → {period_code} {period_label} ({page_count} pages) ===")
        tables = extract_pdf(pdf)
        if not tables:
            print("  no district-wise tables extracted")
            continue

        # Filter by min districts and accumulate per state
        for (state_slug, category), tbl in tables.items():
            n_d = len(tbl['districts'])
            if n_d < MIN_DISTRICTS:
                print(f"  drop {state_slug}/{category}: only {n_d} districts (<{MIN_DISTRICTS})")
                continue
            print(f"  {state_slug}/{category}: {n_d} districts, {len(tbl['fields'])} fields")
            target = state_quarters[state_slug][period_code]
            target['period'] = period_label
            if category not in target['tables']:
                target['tables'][category] = {'fields': list(tbl['fields']), 'districts': {}}
            else:
                for f in tbl['fields']:
                    if f not in target['tables'][category]['fields']:
                        target['tables'][category]['fields'].append(f)
            for dname, rec in tbl['districts'].items():
                if dname not in target['tables'][category]['districts']:
                    target['tables'][category]['districts'][dname] = {}
                target['tables'][category]['districts'][dname].update(rec)

    # Cleanup: prune fields not actually populated in any district
    for state_slug, qmap in state_quarters.items():
        for pc, q in qmap.items():
            for cat, t in q['tables'].items():
                used = set()
                for drec in t['districts'].values():
                    used.update(drec.keys())
                t['fields'] = [f for f in t['fields'] if f in used]

    # Write outputs
    print("\n\n========== Writing outputs ==========")

    # AP
    ap_complete = {'state': 'Andhra Pradesh', 'quarters': dict(state_quarters.get('andhra-pradesh', {}))}
    if ap_complete['quarters']:
        print("\n--- Andhra Pradesh ---")
        write_state_outputs('andhra-pradesh', ap_complete, SRC_DIR)

    # TG (pre-2014 data only — written to AP folder so we don't overwrite TG outputs)
    tg_complete = {'state': 'Telangana (pre-2014, from united-AP SLBC PDFs)',
                   'quarters': dict(state_quarters.get('telangana', {}))}
    if tg_complete['quarters']:
        print("\n--- Telangana (pre-2014, from united-AP) ---")
        write_state_outputs('telangana', tg_complete, SRC_DIR, file_prefix='telangana_pre2014')
    else:
        print("\n(No Telangana pre-2014 data extracted — pre-2014 AP PDFs have only bank-wise tables.)")

    # ─── Summary ─────────────────────────────────────────────────────
    print("\n\n========== SUMMARY ==========")
    print(f"\nProcessed {len(pdfs_with_period)} PDFs")
    print(f"Skipped {len(skipped_pdfs)} PDFs:")
    for name, reason in skipped_pdfs:
        print(f"  - {name}: {reason}")

    print(f"\nAndhra Pradesh quarters: {len(ap_complete['quarters'])}")
    for pc in sorted(ap_complete['quarters'].keys()):
        q = ap_complete['quarters'][pc]
        cats = list(q['tables'].keys())
        n_dist = max((len(t['districts']) for t in q['tables'].values()), default=0)
        cd_count = len(q['tables'].get('credit_deposit_ratio', {}).get('districts', {}))
        print(f"  {pc} ({q['period']}): {len(cats)} cats, max {n_dist} dist, CD={cd_count}; {cats}")

    print(f"\nTelangana pre-2014 quarters: {len(tg_complete['quarters'])}")
    for pc in sorted(tg_complete['quarters'].keys()):
        q = tg_complete['quarters'][pc]
        cats = list(q['tables'].keys())
        n_dist = max((len(t['districts']) for t in q['tables'].values()), default=0)
        print(f"  {pc} ({q['period']}): {len(cats)} cats, max {n_dist} dist; {cats}")

    # CD ratio coverage
    cd_quarters = sum(1 for q in ap_complete['quarters'].values() if 'credit_deposit_ratio' in q['tables'])
    print(f"\nAP CD ratio coverage: {cd_quarters}/{len(ap_complete['quarters'])} quarters")


if __name__ == '__main__':
    main()
