"""
Telangana SLBC comprehensive extractor.

Processes all 13 SLBC agenda PDFs in slbc-data/telangana/ — covering the 36th
through 48th meetings (Dec 2022 → Dec 2025).

Important caveat — Telangana SLBC agenda PDFs do NOT include the district-wise
CD ratio table (referenced as "Annexure B" but maintained as a separate document
not included in the agenda booklet). Therefore CD ratio coverage is sparse to
non-existent. Coverage is concentrated in:
  - PMAY (housing subsidy) — present in nearly every quarter
  - KCC dairy/fish farmer progress — most quarters
  - PMJDY district-wise (only 44th has Annexure-D)
  - PMMY/MUDRA (only 44th has Annexure-G)
  - APY (only 42nd has district-wise table)
  - PMEGP (46th has district table)
  - Stand Up India (38th)

Output (in slbc-data/telangana/):
  - telangana_complete.json
  - telangana_fi_timeseries.json
  - telangana_fi_timeseries.csv
  - quarterly/{YYYY-MM}/*.csv
"""
import csv, json, re, os, glob
from collections import defaultdict
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / 'slbc-data/telangana'

# ─── Meeting → quarter mapping ──────────────────────────────────────
MEETING_QUARTER = {
    '36': ('2022-12', 'December 2022'),
    '37': ('2023-03', 'March 2023'),
    '38': ('2023-06', 'June 2023'),
    '39': ('2023-09', 'September 2023'),
    '40': ('2023-12', 'December 2023'),
    '41': ('2024-03', 'March 2024'),
    '42': ('2024-06', 'June 2024'),
    '43': ('2024-09', 'September 2024'),
    '44': ('2024-12', 'December 2024'),
    '45': ('2025-03', 'March 2025'),
    '46': ('2025-06', 'June 2025'),
    '47': ('2025-09', 'September 2025'),
    '48': ('2025-12', 'December 2025'),
}

# ─── Telangana 33 canonical districts ───────────────────────────────
TG_CANONICAL_DISTRICTS = [
    'Adilabad', 'Bhadradri Kothagudem', 'Hanumakonda', 'Hyderabad', 'Jagitial',
    'Jangoan', 'Jayashankar Bhupalapally', 'Jogulamba Gadwal', 'Kamareddy',
    'Karimnagar', 'Khammam', 'Kumuram Bheem Asifabad', 'Mahabubabad',
    'Mahabubnagar', 'Mancherial', 'Medak', 'Medchal Malkajgiri', 'Mulugu',
    'Nagarkurnool', 'Nalgonda', 'Narayanpet', 'Nirmal', 'Nizamabad',
    'Peddapalli', 'Rajanna Sircilla', 'Ranga Reddy', 'Sangareddy', 'Siddipet',
    'Suryapet', 'Vikarabad', 'Wanaparthy', 'Warangal', 'Yadadri Bhuvanagiri',
]

DISTRICT_ALIASES = {}

def _add(aliases, canonical):
    for a in aliases:
        DISTRICT_ALIASES[a.lower()] = (canonical, 'telangana')

_add(['adilabad'], 'Adilabad')
_add(['bhadradri', 'bhadradri kothagudem', 'bhadradri-kothagudem', 'bhadradri kothgudem', 'bhadradi'], 'Bhadradri Kothagudem')
_add(['hanumakonda', 'hanmakonda'], 'Hanumakonda')
_add(['hyderabad', 'hyd'], 'Hyderabad')
_add(['jagitial', 'jagtial', 'jagityal', 'jagitiyal'], 'Jagitial')
_add(['jangoan', 'jangaon', 'jangaon(new)'], 'Jangoan')
_add(['jayashankar bhupalapally', 'jayashankar bhupalpally', 'jayashankar bhupalapalle',
      'jayashankar bhoopalpally', 'jayashankar bhupalapally', 'jayashankar - bhoopalpally',
      'jayashankar', 'js bhupalapally', 'js bhupalpally', 'bhupalpally'], 'Jayashankar Bhupalapally')
_add(['jogulamba gadwal', 'jogulamba', 'gadwal', 'jogulamba-gadwal'], 'Jogulamba Gadwal')
_add(['kamareddy'], 'Kamareddy')
_add(['karimnagar', 'karim nagar'], 'Karimnagar')
_add(['khammam'], 'Khammam')
_add(['kumuram bheem asifabad', 'kumuram bheem', 'kumarambheem', 'komaram bheem',
      'komrambheem', 'kb asifabad', 'kbr asifabad', 'k.b.asifabad', 'kb-asifabad',
      'kumram bheem asifabad', 'kumram bheem', 'kumuram bheem(asifabad)',
      'kumuram bheem -asifabad', 'kumuram bheem-asifabad', 'asifabad'], 'Kumuram Bheem Asifabad')
_add(['mahabubabad'], 'Mahabubabad')
_add(['mahabubnagar', 'mahbubnagar', 'mahaboobnagar', 'mahboobnagar',
      'mahaboob nagar', 'mahbub nagar', 'mahabub nagar', 'mhbnr', 'mahbubngr'], 'Mahabubnagar')
_add(['mancherial', 'manchiryal', 'mancheryal'], 'Mancherial')
_add(['medak'], 'Medak')
_add(['medchal malkajgiri', 'medchal-malkajgiri', 'medchal_malkajgiri', 'medchal'], 'Medchal Malkajgiri')
_add(['mulugu', 'mulugu(new)'], 'Mulugu')
_add(['nagarkurnool', 'nagar kurnool'], 'Nagarkurnool')
_add(['nalgonda'], 'Nalgonda')
_add(['narayanpet'], 'Narayanpet')
_add(['nirmal'], 'Nirmal')
_add(['nizamabad'], 'Nizamabad')
_add(['peddapalli', 'peddapally'], 'Peddapalli')
_add(['rajanna sircilla', 'rajanna-sircilla', 'rajanna', 'sircilla'], 'Rajanna Sircilla')
_add(['ranga reddy', 'rangareddy', 'rangaareddy', 'r.r district', 'rr district',
      'r r district', 'rr', 'r r', 'r.r.', 'rangareddy(rr)'], 'Ranga Reddy')
_add(['sangareddy', 'sanga reddy', 'sangaredy'], 'Sangareddy')
_add(['siddipet'], 'Siddipet')
_add(['suryapet'], 'Suryapet')
_add(['vikarabad'], 'Vikarabad')
_add(['wanaparthy', 'wanaparthi'], 'Wanaparthy')
_add(['warangal', 'warangal urban', 'warangal rural', 'warangal (rural)', 'warangal(rural)',
      'warangal-rural', 'warangal-urban'], 'Warangal')
_add(['yadadri bhuvanagiri', 'yadadri', 'yadadri-bhuvanagiri',
      'yadadri (bhongir)', 'yadadribhuvanagiri'], 'Yadadri Bhuvanagiri')

# Skip rows
SKIP_ROWS = {'total', 'state total', 'grand total', 'state average', 'average',
             'overall', 'all districts', 's.no.', 'sno', 'sl.no', '',
             'name of the district', 'district', 'name of the bank', 'category',
             'sub total', 'subtotal', None}


def normalize_district(name):
    """Map a raw PDF district name to (canonical_name, state_slug), or None."""
    if not name:
        return None
    s = str(name).strip().lower()
    s = re.sub(r'^\d+[\.\s]+', '', s)
    s = re.sub(r'\s+', ' ', s)
    s = s.strip(' .*,:;')
    s = re.sub(r'\s+district\s*$', '', s)
    s = re.sub(r'\s+total\s*$', '', s)
    s = re.sub(r'\s*\(new\)\s*$', '', s)
    if s in SKIP_ROWS:
        return None
    if s in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[s]
    s2 = re.sub(r'\s*\([^)]*\)\s*', '', s).strip()
    if s2 in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[s2]
    return None


def parse_value(s):
    if s is None:
        return None
    s = str(s).strip()
    if s in ('', '-', '—', '--', 'N/A', 'NA', 'Nil', 'nil', '*', '...', '…', 'na'):
        return None
    s = s.replace(',', '').replace('%', '').replace('₹', '').strip()
    # Remove trailing pct artifact
    s = s.rstrip('.')
    m = re.match(r'^[+-]?\d+(\.\d+)?$', s)
    if not m:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_snake(s):
    if not s:
        return ''
    s = str(s).strip()
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[^\w]', '_', s)
    s = re.sub(r'_+', '_', s)
    return s.lower().strip('_')


# ─── Table classification ────────────────────────────────────────────

REJECT = object()


def classify_table(title_text):
    t = (title_text or '').lower()
    # REJECT non-FI/diagnostic tables
    if 'dcc' in t and 'dlrc' in t and 'meeting' in t:
        return REJECT
    if 'meeting scheduled' in t or 'meeting held' in t:
        return REJECT
    if 'allotment' in t and 'district' not in t:
        return REJECT
    if 'fpo' in t or 'popi' in t:
        return REJECT
    if 'lead district' in t and 'flcc' in t:
        return REJECT
    if 'unbanked' in t or 'un-banked' in t:
        return REJECT
    if 'rseti' in t and ('claim' in t or 'pending' in t):
        return REJECT
    if 'ssa' in t and 'no. of ssa' in t:
        return REJECT
    if 'gram panchayat' in t:
        return REJECT
    if 'rudseti' in t:
        return REJECT
    if 'aadhaar enrol' in t or 'pin code' in t:
        return REJECT
    if 'aadhaar centre' in t or 'aadhaar center' in t:
        return REJECT
    if 'cluster' in t and 'msme' in t:
        return REJECT
    if 'mfi' in t:
        return REJECT
    if 'flc' in t and 'counsel' in t:
        return REJECT
    if 'fsa' in t and 'pin' in t:
        return REJECT
    if 'subdistrict' in t or 'mandal' in t:
        return REJECT

    # ── Real FI categories ──
    if 'cd ratio' in t or 'credit deposit' in t or 'c.d. ratio' in t or 'credit-deposit' in t:
        return 'credit_deposit_ratio'
    if 'pmjdy' in t or 'jan dhan' in t or 'pmjdy accounts' in t:
        return 'pmjdy'
    if ('kcc' in t and ('dairy' in t or 'fish' in t or 'animal husbandry' in t)) or 'kisan credit' in t:
        return 'kcc'
    # KCC campaign tables — applications for Dairy/Fish farmers (header may say Bank but rows are districts)
    if 'applications' in t and 'sanctioned' in t and 'rejected' in t and 'pendency' in t:
        return 'kcc'
    # CGTMSE Guarantee Approved tables — credit guarantee for MSMEs
    if 'guarantee approved' in t or 'cgtmse' in t:
        return 'mudra'  # closest priority sector category
    # PMEGP style tables — Applications forwarded to Banks, Sanctioned, Disbursed
    if 'applications forwarded' in t and ('disbursed' in t or 'sanctioned' in t):
        return 'pmegp'
    if 'shg' in t and ('linkage' in t or 'bank' in t or 'credit' in t or 'savings' in t):
        return 'shg'
    if 'self help group' in t:
        return 'shg'
    if 'mudra' in t or 'pmmy' in t:
        return 'mudra'
    if 'apy' in t or 'atal pension' in t:
        return 'social_security'
    if 'pmjjby' in t or 'pmsby' in t or 'social security' in t:
        return 'social_security'
    if 'pmay' in t and ('subsidy' in t or 'lending' in t or 'housing' in t or 'loan' in t or 'performance' in t):
        return 'housing_pmay'
    if 'housing' in t and 'subsidy' in t:
        return 'housing_pmay'
    if 'pmegp' in t:
        return 'pmegp'
    if 'stand up india' in t or 'standup india' in t or 'stand-up india' in t:
        return 'stand_up_india'
    if 'education loan' in t:
        return 'education_loan'
    if 'minority' in t and ('finance' in t or 'corp' in t):
        return 'minority_finance'
    if 'weaker section' in t:
        return 'weaker_sections'
    if 'women' in t and ('credit' in t or 'finance' in t or 'loan' in t):
        return 'women_finance'
    if 'digital' in t and ('coverage' in t or 'transaction' in t):
        return 'digital_transactions'
    if 'no. of branches' in t or 'no of branches' in t or 'number of branches' in t:
        return 'branch_network'
    if 'priority sector' in t and ('outstanding' in t or 'advances' in t):
        return 'priority_sector'
    if 'recovery' in t or ('npa' in t and 'position' in t):
        return 'recovery_npa'
    if 'aadhaar' in t and 'seed' in t:
        return 'aadhaar_authentication'
    if 'nrlm' in t or 'nulm' in t or 'mepma' in t:
        return 'shg'
    if 'sc corp' in t or 'tricor' in t or 'bc corporation' in t:
        return 'sc_st_finance'
    if 'visw' in t or 'viswakarma' in t or 'vishwakarma' in t:
        return 'pm_vishwakarma'
    if 'agri' in t and ('infrastructure' in t or 'fund' in t):
        return 'agri_infrastructure'
    return None


# ─── Header / table parsing ─────────────────────────────────────────

BANK_KEYWORDS = ('bank of baroda', 'bank of india', 'bank of maharashtra', 'canara bank',
                 'central bank', 'indian bank', 'punjab national', 'state bank',
                 'union bank', 'syndicate bank', 'icici', 'hdfc',
                 'axis bank', 'kotak', 'corporation bank',
                 'sbi ', 'rrb', 'commercial banks', 'co-operative',
                 'regional rural', 'name of the bank', 'tgb', 'apgvb',
                 'telangana grameena', 'idfc first', 'esaf', 'small finance',
                 'idbi bank', 'punjab and sind', 'punjab & sind', 'south indian',
                 'karur vysya', 'karnataka bank', 'federal bank', 'yes bank',
                 'indusind', 'rbl bank', 'dhanlaxmi', 'tamilnad mercantile',
                 'jammu and kashmir', 'standard chartered', 'bandhan', 'dcb',
                 'csb bank', 'city union', 'nabard', 'ippb', 'tscab',
                 'cooperative bank', 'private', 'public sector')


def is_bankwise_table(table):
    if not table or len(table) < 4:
        return False
    bank_rows = 0
    for row in table[:min(20, len(table))]:
        for cell in row[:3]:
            if cell:
                cl = str(cell).lower()
                if any(k in cl for k in BANK_KEYWORDS):
                    bank_rows += 1
                    break
    return bank_rows >= 4


def is_continuation_table(table):
    """A continuation has no header row — all rows look like data (district + numbers)."""
    if not table:
        return False
    # If the first non-empty row's textual cell matches a district, it's a continuation
    for row in table[:1]:
        for cell in row:
            if cell and isinstance(cell, str):
                d = normalize_district(cell)
                if d:
                    return True
                # If first non-numeric cell is not a district but could be bank etc, no
                if not re.match(r'^[\d,.%\-\s]+$', str(cell)):
                    return False
    return False


def is_district_table(table, min_districts=6):
    if not table or len(table) < 3:
        return False
    if is_bankwise_table(table):
        return False
    if is_continuation_table(table):
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
    for i, row in enumerate(table):
        for cell in row:
            if cell and isinstance(cell, str) and normalize_district(cell):
                return i
    return 1


def clean_header_cell(cell):
    if not cell:
        return ''
    s = str(cell).strip()
    if '\n' in s:
        # Drop trailing numeric lines (data leak), keep textual header parts
        parts = [p.strip() for p in s.split('\n')]
        text_parts = []
        for p in parts:
            if not p:
                continue
            # If the whole part is numeric/data, stop accumulating
            if re.match(r'^[\d,.%\-]+$', p):
                break
            text_parts.append(p)
        if text_parts:
            s = ' '.join(text_parts)
        else:
            s = parts[0] if parts else ''
    s = re.sub(r'(?i)slbc.*?(convener|convenor)\s*:?', '', s)
    s = re.sub(r'(?i)\d+(th|st|nd|rd)\s+meeting\s+of\s+slbc', '', s)
    return s.strip()


def build_field_names(header_rows):
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
        merged = re.sub(r'\s+[\d,.%\-]+$', '', merged).strip()
        fields.append(to_snake(merged))
    return fields


def is_noisy_field(fkey):
    if not fkey or fkey == 's_no':
        return True
    if fkey.startswith('s_no'):
        return True
    if fkey in ('sno', 'srno', 'sr_no', 'sl_no', 'sl', 'sr', 'remarks',
                'name_of_the_district', 'district', 'name_of_district',
                'name_of_the_bank', 'name_of_bank', 'bank_name', 'institution_name',
                'name_of_the_district_'):
        return True
    if fkey.startswith('district_') and fkey not in ('district_code',):
        return True
    if fkey.startswith('name_of_the_'):
        return True
    if len(fkey) > 80:
        return True
    # All-numeric field name = data leak (continuation table parsed without header)
    if re.match(r'^[\d_]+$', fkey):
        return True
    return False


# ─── Field key standardization ──────────────────────────────────────

FIELD_RENAMES = {
    'convener_cd_ratio': 'cd_ratio',
    'no_of_active_pmjdy_a_c': 'total_pmjdy_no',
    'no_of_active_pmjdy_a_cs': 'total_pmjdy_no',
    'total_number_of_accounts': 'total_pmjdy_no',
    'no_of_pmjdy_accounts': 'total_pmjdy_no',
    'no_of_pmjdy': 'total_pmjdy_no',
    'no_of_pmjdy_accounts_female': 'female_no',
    'no_of_pmjdy_accounts_male': 'male_no',
    'no_of_accounts_female': 'female_no',
    'no_of_accounts_male': 'male_no',
    'no_of_accounts_rural': 'rural_no',
    'no_of_accounts_urban': 'urban_no',
    'no_of_kcc': 'total_no_of_kcc',
    'kcc_no': 'total_no_of_kcc',
    'rupay_card_issued_in_kcc': 'total_no_of_kcc',
    'no_of_branches': 'total_branch',
    'no_of_brs': 'total_branch',
    'total_branches': 'total_branch',
    'total_brs': 'total_branch',
    'deposits': 'total_deposit',
    'advances': 'total_advance',
    'total_no_of_shg': 'savings_linked_no',
    'shg_credit_linked_no': 'credit_linked_no',
    'no_of_loan_accounts': 'no_of_accounts',
    'no_of_a_cs': 'no_of_accounts',
}

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
    if not fkey:
        return None
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
            # Use larger context for title
            title_lines = text.split('\n')[:15]
            title_text = ' | '.join(title_lines)

            for tbl_idx, tbl in enumerate(tables):
                if not is_district_table(tbl, min_districts=5):
                    continue

                # Classify — try table headers FIRST, then page text
                hdr_text = ' '.join(str(c) for r in tbl[:4] for c in r if c)
                hdr_cls = classify_table(hdr_text)
                if hdr_cls is REJECT:
                    continue
                category = hdr_cls
                if not category:
                    title_cls = classify_table(title_text)
                    if title_cls is REJECT:
                        continue
                    category = title_cls
                if not category:
                    continue

                hdr_n = find_header_rows(tbl)
                if hdr_n < 1:
                    hdr_n = 1
                header_rows = tbl[:hdr_n]
                data_rows = tbl[hdr_n:]
                fields = build_field_names(header_rows)

                state_district_records = defaultdict(dict)

                for row in data_rows:
                    if not row:
                        continue
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

                    col_to_field = {}
                    last_good_raw_field = None
                    for col_i in range(len(fields)):
                        fkey = fields[col_i]
                        if not fkey:
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
                        if fkey_std not in rec:
                            rec[fkey_std] = parsed
                    if rec:
                        if canonical in state_district_records[state_slug]:
                            state_district_records[state_slug][canonical].update(rec)
                        else:
                            state_district_records[state_slug][canonical] = rec

                if not state_district_records:
                    continue

                fields_std = []
                for f in fields:
                    if is_noisy_field(f):
                        continue
                    fs = standardize_field(f, category)
                    if fs and fs not in fields_std:
                        fields_std.append(fs)

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
    if file_prefix is None:
        file_prefix = state_slug
    canon_districts = TG_CANONICAL_DISTRICTS

    out_complete = src_dir / f'{file_prefix}_complete.json'
    with open(out_complete, 'w') as f:
        json.dump(complete, f, indent=2)
    print(f"  Wrote {out_complete.name} ({out_complete.stat().st_size/1024:.1f} KB)")

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

    # Per-quarter per-category CSVs
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

    pdfs_with_period.sort(key=lambda x: x[2])

    state_quarters = defaultdict(lambda: defaultdict(lambda: {'period': '', 'tables': {}}))

    skipped_pdfs = []
    MIN_DISTRICTS = 8

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
            print(f"  skip {name}: only {page_count} pages")
            skipped_pdfs.append((name, f"truncated to {page_count} pages"))
            continue

        print(f"\n=== {name} → {period_code} {period_label} ({page_count} pages) ===")
        tables = extract_pdf(pdf)
        if not tables:
            print("  no district-wise tables extracted")
            continue

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

    # Cleanup unused fields
    for state_slug, qmap in state_quarters.items():
        for pc, q in qmap.items():
            for cat, t in q['tables'].items():
                used = set()
                for drec in t['districts'].values():
                    used.update(drec.keys())
                t['fields'] = [f for f in t['fields'] if f in used]

    # Write outputs
    print("\n\n========== Writing outputs ==========")
    tg_complete = {'state': 'Telangana',
                   'quarters': dict(state_quarters.get('telangana', {}))}
    if tg_complete['quarters']:
        print("\n--- Telangana ---")
        write_state_outputs('telangana', tg_complete, SRC_DIR)

    # ─── Summary ─────────────────────────────────────────────────────
    print("\n\n========== SUMMARY ==========")
    print(f"\nProcessed {len(pdfs_with_period)} PDFs")
    if skipped_pdfs:
        print(f"Skipped {len(skipped_pdfs)} PDFs:")
        for name, reason in skipped_pdfs:
            print(f"  - {name}: {reason}")

    print(f"\nTelangana quarters: {len(tg_complete['quarters'])}")
    for pc in sorted(tg_complete['quarters'].keys()):
        q = tg_complete['quarters'][pc]
        cats = list(q['tables'].keys())
        n_dist = max((len(t['districts']) for t in q['tables'].values()), default=0)
        per_cat = {c: len(t['districts']) for c, t in q['tables'].items()}
        print(f"  {pc} ({q['period']}): {len(cats)} cats, max {n_dist} dist; {per_cat}")

    cd_quarters = sum(1 for q in tg_complete['quarters'].values() if 'credit_deposit_ratio' in q['tables'])
    pmjdy_q = sum(1 for q in tg_complete['quarters'].values() if 'pmjdy' in q['tables'])
    kcc_q = sum(1 for q in tg_complete['quarters'].values() if 'kcc' in q['tables'])
    pmay_q = sum(1 for q in tg_complete['quarters'].values() if 'housing_pmay' in q['tables'])
    print(f"\nIndicator coverage:")
    print(f"  CD ratio:       {cd_quarters}/{len(tg_complete['quarters'])} quarters")
    print(f"  PMJDY:          {pmjdy_q}/{len(tg_complete['quarters'])} quarters")
    print(f"  KCC:            {kcc_q}/{len(tg_complete['quarters'])} quarters")
    print(f"  PMAY:           {pmay_q}/{len(tg_complete['quarters'])} quarters")


if __name__ == '__main__':
    main()
