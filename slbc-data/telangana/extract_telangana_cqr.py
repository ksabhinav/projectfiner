"""
Telangana SLBC — Comprehensive Quarterly Return (CQR) Annexures extractor.

The TG SLBC publishes quarterly CQR Annexure PDFs at telanganaslbc.com/reports.aspx.
These contain CLEAN district-wise tables that the bare SLBC agendas don't bundle.

Each CQR PDF has a fixed annexure structure (per Dec 2025 sample):
  Annexure-2  : District Branch Network (Rural/Semi-Urban/Urban/Total)
  Annexure-4  : District CD Ratio (Branch + Deposits R/SU/U/T + Advances R/SU/U/T + CDR)
  Annexure-6  : District Priority Sector Advances (3 pages of tables)
  Annexure-8  : District Non-Priority Sector
  Annexure-10 : District Non-Priority Target-Achievement

Other annexures are bank-wise (not district-wise) — skipped here.

Inputs: cqr_YYYY-MM.pdf in this directory (one per quarter, 14 files Dec 2022 → Dec 2025).
Outputs: telangana_complete.json, telangana_fi_timeseries.json (+ csv + per-quarter csvs).
"""
import csv, json, os, re, glob
from collections import defaultdict
from pathlib import Path
import pdfplumber

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / 'slbc-data/telangana'

# ─── 33 Telangana districts (canonical, post-2019) ─────────────────────
TG_CANONICAL = [
    'Adilabad', 'Bhadradri Kothagudem', 'Hanumakonda', 'Hyderabad', 'Jagitial',
    'Jangoan', 'Jayashankar Bhupalapally', 'Jogulamba Gadwal', 'Kamareddy',
    'Karimnagar', 'Khammam', 'Kumuram Bheem Asifabad', 'Mahabubabad',
    'Mahabubnagar', 'Mancherial', 'Medak', 'Medchal Malkajgiri', 'Mulugu',
    'Nagarkurnool', 'Nalgonda', 'Narayanpet', 'Nirmal', 'Nizamabad',
    'Peddapalli', 'Rajanna Sircilla', 'Ranga Reddy', 'Sangareddy', 'Siddipet',
    'Suryapet', 'Vikarabad', 'Wanaparthy', 'Warangal', 'Yadadri Bhuvanagiri',
]

# Build aliases for the variations the PDFs use
ALIASES = {}
for d in TG_CANONICAL:
    ALIASES[d.upper()] = d
    ALIASES[d.lower()] = d

# Specific alternative spellings observed in CQR PDFs
ALT_NAMES = {
    'JAGTIAL': 'Jagitial',
    'JAGTIYAL': 'Jagitial',
    'JANGAON': 'Jangoan',
    'JAYASHANKAR BHUPALAPALLE': 'Jayashankar Bhupalapally',
    'JAYASHANKAR': 'Jayashankar Bhupalapally',
    'BHUPALAPALLY': 'Jayashankar Bhupalapally',
    'JOGULAMBA': 'Jogulamba Gadwal',
    'GADWAL': 'Jogulamba Gadwal',
    'KOMARAM BHEEM': 'Kumuram Bheem Asifabad',
    'KUMARAM BHEEM': 'Kumuram Bheem Asifabad',
    'KUMURAM BHEEM ASIFABAD': 'Kumuram Bheem Asifabad',
    'KUMARAM BHEEM ASIFABAD': 'Kumuram Bheem Asifabad',
    'ASIFABAD': 'Kumuram Bheem Asifabad',
    'MAHBUBNAGAR': 'Mahabubnagar',
    'MAHABUB NAGAR': 'Mahabubnagar',
    'MEDCHAL': 'Medchal Malkajgiri',
    'MEDCHAL MALKAJGIRI': 'Medchal Malkajgiri',
    'MEDCHAL-MALKAJGIRI': 'Medchal Malkajgiri',
    'RAJANNA': 'Rajanna Sircilla',
    'SIRCILLA': 'Rajanna Sircilla',
    'RAJANNA SIRCILLA': 'Rajanna Sircilla',
    'RANGAREDDY': 'Ranga Reddy',
    'R.R': 'Ranga Reddy',
    'R.R.': 'Ranga Reddy',
    'RANGA REDDY': 'Ranga Reddy',
    'YADADRI': 'Yadadri Bhuvanagiri',
    'BHUVANAGIRI': 'Yadadri Bhuvanagiri',
    'YADADRI BHUVANAGIRI': 'Yadadri Bhuvanagiri',
    'YADADRI BHONGIR': 'Yadadri Bhuvanagiri',
    'BHADRADRI': 'Bhadradri Kothagudem',
    'KOTHAGUDEM': 'Bhadradri Kothagudem',
    'BHADRADRI KOTHAGUDEM': 'Bhadradri Kothagudem',
    'WARANGAL URBAN': 'Hanumakonda',  # post-2021 rename
    'HANAMKONDA': 'Hanumakonda',
    'WARANGAL RURAL': 'Warangal',
    'HYD': 'Hyderabad',
}
ALIASES.update(ALT_NAMES)

SKIP_ROWS = {'total', 'grand total', 'state total', 'sub total', 'sub-total',
             's.no.', 'sno', 's no', 'sl.no', 'sr.', 'sr', 'name of district',
             'name of the district', 'district', '', None}


def normalize_district(name):
    """Map a raw cell value to a canonical TG district, or None."""
    if name is None:
        return None
    s = str(name).strip()
    s = re.sub(r'^\d+[\.\s]+', '', s)  # strip leading "1. "
    s = s.strip(' .,*')
    if not s or s.lower() in SKIP_ROWS:
        return None
    if s.upper() in ALIASES:
        return ALIASES[s.upper()]
    if s.lower() in ALIASES:
        return ALIASES[s.lower()]
    # Token-by-token check — useful for partial matches like "Hanumakonda Old District"
    s_norm = re.sub(r'[^A-Z]', '', s.upper())
    for k, v in ALIASES.items():
        if re.sub(r'[^A-Z]', '', k.upper()) == s_norm:
            return v
    return None


def parse_value(s):
    if s is None: return None
    s = str(s).strip()
    if s in ('', '-', '—', 'N/A', 'NA', 'Nil', 'nil', 'NIL'):
        return None
    s = s.replace(',', '').replace('%', '').strip()
    m = re.match(r'^[+-]?\d+(\.\d+)?$', s)
    if not m: return None
    try: return float(s)
    except ValueError: return None


def to_snake(s):
    if not s: return ''
    s = str(s).strip().lower()
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[^\w]', '_', s)
    s = re.sub(r'_+', '_', s)
    return s.strip('_')


# ─── Annexure-specific extractors ─────────────────────────────────────

def extract_annexure_4(table):
    """ANNEXURE-4: DISTRICT WISE CD RATIO.
       Layout: SR | District | Branch | Deposits R/SU/U/T (4 cols) | Advances R/SU/U/T (4 cols) | CD Ratio (1+ cols)
       Returns list of (district, dict).
    """
    if not table or len(table) < 4: return []
    out = []
    for row in table:
        if not row or len(row) < 6: continue
        # First non-empty cell that resolves to a district
        dname = None; di = -1
        for i, c in enumerate(row):
            if c:
                cn = normalize_district(c)
                if cn:
                    dname = cn; di = i; break
        if not dname: continue
        # Numeric tail after district name
        nums = []
        for c in row[di+1:]:
            v = parse_value(c)
            if v is not None: nums.append(v)
        # Expected layout for CD ratio table: branch_count, deposits R/SU/U/T (4), advances R/SU/U/T (4), cd_ratio (1)
        # = 1 + 4 + 4 + 1 = 10 numbers
        rec = {}
        if len(nums) >= 10:
            rec['total_branch'] = nums[0]
            rec['deposits_rural'] = nums[1]
            rec['deposits_semi_urban'] = nums[2]
            rec['deposits_urban'] = nums[3]
            rec['total_deposit'] = nums[4]
            rec['advances_rural'] = nums[5]
            rec['advances_semi_urban'] = nums[6]
            rec['advances_urban'] = nums[7]
            rec['total_advance'] = nums[8]
            rec['cd_ratio'] = nums[9]
        elif len(nums) >= 9:
            # Some PDFs collapse one cell — try without one of the area splits
            rec['total_branch'] = nums[0]
            rec['total_deposit'] = nums[4] if len(nums)>4 else None
            rec['total_advance'] = nums[8] if len(nums)>8 else None
            rec['cd_ratio'] = nums[-1]
        if rec:
            out.append((dname, rec))
    return out


def extract_annexure_2(table):
    """ANNEXURE-2: DISTRICT WISE BRANCH NETWORK.
       Layout: SR | District | Rural | Semi-Urban | Urban | Total
    """
    out = []
    for row in table or []:
        if not row or len(row) < 4: continue
        dname = None; di = -1
        for i, c in enumerate(row):
            if c:
                cn = normalize_district(c)
                if cn:
                    dname = cn; di = i; break
        if not dname: continue
        nums = [parse_value(c) for c in row[di+1:] if c is not None]
        nums = [n for n in nums if n is not None]
        if len(nums) >= 4:
            out.append((dname, {
                'branch_rural': nums[0],
                'branch_semi_urban': nums[1],
                'branch_urban': nums[2],
                'total_branch': nums[3],
            }))
    return out


def extract_annexure_6(table, header_text=''):
    """ANNEXURE-6: DISTRICT WISE PRIORITY SECTOR ADVANCES.
       Multi-page; each table has different sub-categories. Captures all numeric
       columns generically as priority_sector__col_N or matched headers.
    """
    if not table or len(table) < 3: return []
    # Header row: row index where 'District' or 'Name' shows up
    header_row_idx = None
    for i, row in enumerate(table[:5]):
        joined = ' '.join(str(c) for c in row if c).lower()
        if 'name of' in joined and 'district' in joined:
            header_row_idx = i; break
    headers = [str(c).strip() if c else '' for c in (table[header_row_idx] if header_row_idx is not None else [])]
    out = []
    for row in (table[header_row_idx+1:] if header_row_idx is not None else table):
        if not row: continue
        dname = None; di = -1
        for i, c in enumerate(row):
            if c:
                cn = normalize_district(c)
                if cn:
                    dname = cn; di = i; break
        if not dname: continue
        rec = {}
        for j, c in enumerate(row[di+1:], start=di+1):
            v = parse_value(c)
            if v is None: continue
            # Use header if available, else col_N
            label = headers[j] if j < len(headers) and headers[j] else f'col_{j}'
            key = to_snake(label)
            if key and key not in ('s_no', 'sr_no', '_'):
                if key not in rec:
                    rec[key] = v
        if rec and len(rec) >= 2:
            out.append((dname, rec))
    return out


# ─── Main extractor per CQR PDF ───────────────────────────────────────

def _is_reversed_page(text):
    """Detect pages where text is character-reversed (a known TG CQR PDF artifact)."""
    if not text: return False
    # Reversed indicators
    return ('ERUXENNA' in text.upper() or 'ANAGNALET CBLS' in text.upper()
            or 'eruxennA' in text)


def _reverse_cell(c):
    """Reverse a cell's characters. Handles None and non-string types."""
    if c is None: return None
    s = str(c)
    return s[::-1]


def _maybe_reverse_table(table, reversed_page):
    """If page is rotated 180°, table is BOTH text-reversed and rotated.
       To recover: reverse each cell's characters, then transpose (since the page
       is laid out perpendicular — rows<->cols swap), then optionally reverse row order.
    """
    if not reversed_page: return table
    # Step 1: reverse character content of each cell
    reversed_cells = [[_reverse_cell(c) for c in row] for row in table]
    # Step 2: transpose (since rows and cols swap when page is rotated 180°)
    n_cols = max((len(r) for r in reversed_cells), default=0)
    transposed = []
    for col in range(n_cols):
        new_row = []
        for r in reversed_cells:
            new_row.append(r[col] if col < len(r) else None)
        transposed.append(new_row)
    # Step 3: row order may be reversed (last row in transposed = first district)
    transposed.reverse()
    return transposed


def extract_cqr(pdf_path):
    """Returns dict of category → {district: {field: value}}"""
    result = defaultdict(lambda: defaultdict(dict))
    with pdfplumber.open(pdf_path) as p:
        for page_idx, page in enumerate(p.pages):
            text = page.extract_text() or ''
            reversed_page = _is_reversed_page(text)
            # Build a "logical" text we can use for classification
            classify_text = text
            if reversed_page:
                # Reverse line by line, then reverse the line order
                rev_lines = [ln[::-1] for ln in text.split('\n')]
                classify_text = '\n'.join(rev_lines[::-1])
            text_upper = classify_text.upper()
            tables = page.extract_tables()
            if not tables: continue
            # Determine annexure type
            is_district = ('DISTRICT WISE' in text_upper) or ('DISTRICT-WISE' in text_upper)
            if not is_district: continue

            # Pick the largest table on the page (data table)
            table = max(tables, key=lambda t: len(t) if t else 0)
            if len(table) < 4: continue
            # If page is reversed, un-reverse cells
            table = _maybe_reverse_table(table, reversed_page)

            # Classify based on title text
            if 'BRANCH NETWORK' in text_upper:
                for dname, rec in extract_annexure_2(table):
                    result['branch_network'][dname].update(rec)
            elif 'CD RATIO' in text_upper or 'CREDIT' in text_upper and 'DEPOSIT' in text_upper:
                for dname, rec in extract_annexure_4(table):
                    result['credit_deposit_ratio'][dname].update(rec)
            elif 'PRIORITY SECTOR' in text_upper and ('NON-' not in text_upper.split('PRIORITY SECTOR')[0][-10:] and 'NON ' not in text_upper.split('PRIORITY SECTOR')[0][-10:]):
                for dname, rec in extract_annexure_6(table, text):
                    result['priority_sector'][dname].update(rec)
            elif 'NON-PRIORITY' in text_upper or 'NON PRIORITY' in text_upper:
                for dname, rec in extract_annexure_6(table, text):
                    result['non_priority_sector'][dname].update(rec)
            elif 'TARGET' in text_upper and 'ACHI' in text_upper:
                for dname, rec in extract_annexure_6(table, text):
                    result['acp_achievement'][dname].update(rec)
    return result


# ─── Pipeline ────────────────────────────────────────────────────────

QUARTER_LABEL = {
    '2022-12': 'December 2022', '2023-03': 'March 2023', '2023-06': 'June 2023',
    '2023-09': 'September 2023', '2023-12': 'December 2023',
    '2024-03': 'March 2024', '2024-06': 'June 2024', '2024-09': 'September 2024',
    '2024-12': 'December 2024',
    '2025-03': 'March 2025', '2025-06': 'June 2025', '2025-09': 'September 2025',
    '2025-12': 'December 2025',
}


def main():
    cqr_files = sorted(glob.glob(str(SRC_DIR / 'cqr_*.pdf')))
    print(f"Found {len(cqr_files)} CQR PDFs")

    complete = {'state': 'Telangana', 'quarters': {}}
    for fp in cqr_files:
        m = re.search(r'cqr_(\d{4}-\d{2})\.pdf', os.path.basename(fp))
        if not m:
            print(f"  skip (no period in filename): {fp}"); continue
        period = m.group(1)
        label = QUARTER_LABEL.get(period, period)
        print(f"\n=== {os.path.basename(fp)} → {period} ({label}) ===")
        try:
            cats = extract_cqr(fp)
        except Exception as e:
            print(f"  ERR: {e}"); continue
        if not cats:
            print(f"  no district tables"); continue
        # Build complete.json structure
        tables_dict = {}
        for cat, dist_data in cats.items():
            field_set = []
            for d, rec in dist_data.items():
                for f in rec:
                    if f not in field_set:
                        field_set.append(f)
            tables_dict[cat] = {
                'fields': field_set,
                'districts': dict(dist_data),
            }
            print(f"  {cat}: {len(dist_data)} districts, {len(field_set)} fields")
        complete['quarters'][period] = {'period': label, 'tables': tables_dict}

    # Write complete.json
    with open(SRC_DIR / 'telangana_complete.json', 'w') as f:
        json.dump(complete, f, indent=2)
    print(f"\nWrote telangana_complete.json ({(SRC_DIR / 'telangana_complete.json').stat().st_size//1024} KB)")

    # Build fi_timeseries.json
    periods_out = []
    for period in sorted(complete['quarters'].keys()):
        q = complete['quarters'][period]
        records = {}
        for cat, table in q['tables'].items():
            for dname, rec in table['districts'].items():
                if dname not in records:
                    records[dname] = {'district': dname, 'period': q['period']}
                for f, v in rec.items():
                    records[dname][f"{cat}__{f}"] = v
        periods_out.append({'period': q['period'], 'districts': list(records.values())})

    with open(SRC_DIR / 'telangana_fi_timeseries.json', 'w') as f:
        json.dump({'periods': periods_out}, f, indent=2)
    print(f"Wrote telangana_fi_timeseries.json")

    # CSV (wide)
    all_fields = set()
    for p in periods_out:
        for r in p['districts']:
            all_fields.update(r.keys())
    all_fields.discard('district'); all_fields.discard('period')
    fieldnames = ['district', 'period'] + sorted(all_fields)
    with open(SRC_DIR / 'telangana_fi_timeseries.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for p in periods_out:
            for r in p['districts']:
                w.writerow(r)
    print(f"Wrote telangana_fi_timeseries.csv")

    # Per-quarter per-category CSVs
    for period, q in complete['quarters'].items():
        qdir = SRC_DIR / 'quarterly' / period
        qdir.mkdir(parents=True, exist_ok=True)
        for cat, table in q['tables'].items():
            csv_path = qdir / f'{cat}.csv'
            with open(csv_path, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['District'] + table['fields'])
                for dname in TG_CANONICAL:
                    if dname in table['districts']:
                        rec = table['districts'][dname]
                        w.writerow([dname] + [rec.get(fk, '') for fk in table['fields']])

    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"Quarters extracted: {len(complete['quarters'])}")
    cat_quarters = defaultdict(int)
    for q in complete['quarters'].values():
        for cat in q['tables']:
            cat_quarters[cat] += 1
    for cat, n in sorted(cat_quarters.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n} quarters")


if __name__ == '__main__':
    main()
