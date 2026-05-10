"""
Andhra Pradesh SLBC quick-win extractor.

Processes 6 SLBC agenda PDFs (223rd–228th meetings, Mar 2023 → Jun 2024) downloaded
from the wayback machine for slbcap.nic.in. Pulls district-wise tables for the
core FI indicators present (CD ratio is the most consistently reported; others
where available in clean tabular form).

Filename → quarter mapping:
  223rd → 2023-03    225th → 2023-09    227th → 2024-03
  224th → 2023-06    226th → 2023-12    228th → 2024-06

This is a "quick win" — not the full AP integration. Just the 6 most recent agendas
we could grab from archive.org. For a comprehensive AP backfill, would need ~113 PDFs.

Output (in slbc-data/andhra-pradesh/):
  - andhra-pradesh_complete.json
  - andhra-pradesh_fi_timeseries.json
  - andhra-pradesh_fi_timeseries.csv
  - quarterly/{YYYY-MM}/*.csv
"""
import csv, json, re, os, glob
from collections import defaultdict
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / 'slbc-data/andhra-pradesh'

# Meeting → quarter
MEETING_QUARTER = {
    '223': ('2023-03', 'March 2023'),
    '224': ('2023-06', 'June 2023'),
    '225': ('2023-09', 'September 2023'),
    '226': ('2023-12', 'December 2023'),
    '227': ('2024-03', 'March 2024'),
    '228': ('2024-06', 'June 2024'),
}

# Canonical district names (matches FINER's `districts` table for state_lgd=28)
CANONICAL_DISTRICTS = [
    'Alluri Sitharama Raju', 'Anakapalli', 'Anantapur', 'Annamayya', 'Bapatla',
    'Chittoor', 'East Godavari', 'Eluru', 'Guntur', 'Kakinada', 'Konaseema',
    'Krishna', 'Kurnool', 'Nandyal', 'Ntr', 'Palnadu', 'Parvathipuram Manyam',
    'Prakasam', 'Spsr Nellore', 'Sri Sathya Sai', 'Srikakulam', 'Tirupati',
    'Visakhapatanam', 'Vizianagaram', 'West Godavari', 'Y.s.r.',
]

# Aliases from PDF source → canonical
DISTRICT_ALIASES = {
    'ananthapuramu': 'Anantapur',
    'anantapuramu': 'Anantapur',
    'anantapur': 'Anantapur',
    'dr. b.r.ambedkar konaseema': 'Konaseema',
    'dr b r ambedkar konaseema': 'Konaseema',
    'b.r. ambedkar konaseema': 'Konaseema',
    'ambedkar konaseema': 'Konaseema',
    'konaseema': 'Konaseema',
    'ntr': 'Ntr',
    'n.t.r.': 'Ntr',
    'visakhapatnam': 'Visakhapatanam',
    'visakapatanam': 'Visakhapatanam',
    'spsr nellore': 'Spsr Nellore',
    'sri potti sriramulu nellore': 'Spsr Nellore',
    'nellore': 'Spsr Nellore',
    'ysr': 'Y.s.r.',
    'ysr kadapa': 'Y.s.r.',
    'cuddapah': 'Y.s.r.',
    'kadapa': 'Y.s.r.',
    'y.s.r kadapa': 'Y.s.r.',
    'y.s.r.': 'Y.s.r.',
    'y.s.r': 'Y.s.r.',
    'y s r': 'Y.s.r.',
    'y s r kadapa': 'Y.s.r.',
    'parvathipuram manyam': 'Parvathipuram Manyam',
    'sri sathya sai': 'Sri Sathya Sai',
    'alluri sitharama raju': 'Alluri Sitharama Raju',
    'allur sitharama raju': 'Alluri Sitharama Raju',
}

# Plus exact canonical names
for c in CANONICAL_DISTRICTS:
    DISTRICT_ALIASES[c.lower()] = c

# Skip rows
SKIP_ROWS = {'total', 'state total', 'grand total', 'state average', 'average',
             's.no.', 'sno', 'sl.no', '', 'name of the district', 'district', None}


def normalize_district(name):
    """Map a raw PDF district name to canonical FINER name, or None."""
    if not name:
        return None
    s = str(name).strip().lower()
    s = re.sub(r'^\d+[\.\s]+', '', s)  # strip leading "1. " serial
    s = re.sub(r'\s+', ' ', s)
    s = s.strip(' .*,')
    if s in SKIP_ROWS:
        return None
    if s in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[s]
    # Try without trailing 'total' suffix
    s2 = re.sub(r'\s*total\s*$', '', s).strip()
    if s2 in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[s2]
    return None


def parse_value(s):
    """Parse a numeric cell — strip commas, %, blanks."""
    if s is None:
        return None
    s = str(s).strip()
    if s in ('', '-', '—', 'N/A', 'NA', 'Nil', 'nil'):
        return None
    s = s.replace(',', '').replace('%', '').strip()
    # Match optional sign + digits + optional decimal
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
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[^\w]', '_', s)
    s = re.sub(r'_+', '_', s)
    return s.lower().strip('_')


# ─── Table classification ────────────────────────────────────────────

def classify_table(title_text):
    """Map a table's surrounding title text to a standard category."""
    t = (title_text or '').lower()
    if 'cd ratio' in t or 'credit deposit' in t or 'c.d. ratio' in t or 'c d ratio' in t:
        return 'credit_deposit_ratio'
    if 'pmjdy' in t or 'jan dhan' in t or 'bsbda' in t:
        return 'pmjdy'
    if 'kcc' in t or 'kisan credit' in t:
        return 'kcc'
    if 'shg' in t or 'self help group' in t:
        return 'shg'
    if 'mudra' in t or 'pmmy' in t:
        return 'mudra'
    if 'social security' in t or 'pmjjby' in t or 'pmsby' in t or 'apy' in t or 'atal pension' in t:
        return 'social_security'
    if 'pmay' in t or 'housing' in t:
        return 'housing_pmay'
    if 'education loan' in t:
        return 'education_loan'
    if 'pmegp' in t:
        return 'pmegp'
    if 'minority' in t:
        return 'minority_finance'
    if 'sc/st' in t or 'weaker section' in t or 'weakers' in t:
        return 'sc_st_finance'
    if 'women' in t:
        return 'women_finance'
    if 'digital' in t and ('coverage' in t or 'transaction' in t):
        return 'digital_transactions'
    if 'branch' in t or 'atm' in t:
        return 'branch_network'
    if 'priority sector' in t or 'priority advances' in t:
        return 'priority_sector'
    if 'recovery' in t or 'npa' in t:
        return 'recovery_npa'
    if 'aadhaar' in t and 'seed' in t:
        return 'aadhaar_authentication'
    return None  # Unknown — skip


# ─── Header parsing ──────────────────────────────────────────────────

def is_district_table(table):
    """Check if a table contains AP districts in its data rows."""
    if not table or len(table) < 3:
        return False
    n_district_rows = 0
    for row in table:
        for cell in row:
            if cell and isinstance(cell, str):
                if normalize_district(cell):
                    n_district_rows += 1
                    break
    return n_district_rows >= 6  # Need at least 6 districts


def find_header_rows(table):
    """Return number of header rows (1-3) by detecting the first row that has a district name."""
    for i, row in enumerate(table):
        for cell in row:
            if cell and isinstance(cell, str) and normalize_district(cell):
                return i  # header rows are 0..i-1
    return 1  # fallback


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
                cell = str(row[col_idx]).strip()
                if cell and cell.lower() not in [p.lower() for p in parts]:
                    parts.append(cell)
        merged = ' '.join(parts).strip()
        fields.append(to_snake(merged))
    return fields


# ─── Per-PDF extraction ──────────────────────────────────────────────

def extract_pdf(pdf_path, period_code, period_label):
    """Extract all district-wise tables from one PDF.
    Returns: dict[category] = {'fields': [...], 'districts': {dname: {field: value}}}
    """
    out_tables = {}  # category → table dict
    with pdfplumber.open(pdf_path) as p:
        for page_idx, page in enumerate(p.pages):
            tables = page.extract_tables()
            if not tables:
                continue
            text = page.extract_text() or ''
            # Get title from text above tables (first 5 lines)
            title_lines = text.split('\n')[:8]
            title_text = ' | '.join(title_lines)

            for tbl_idx, tbl in enumerate(tables):
                if not is_district_table(tbl):
                    continue
                # Try classifying from page title text first; fall back to table headers
                category = classify_table(title_text)
                if not category:
                    # Fallback: classify from the table's own header rows
                    hdr_text = ' '.join(
                        str(c) for r in tbl[:3] for c in r if c
                    )
                    category = classify_table(hdr_text)
                if not category:
                    continue
                hdr_n = find_header_rows(tbl)
                if hdr_n < 1:
                    hdr_n = 1
                header_rows = tbl[:hdr_n]
                data_rows = tbl[hdr_n:]
                fields = build_field_names(header_rows)
                # Build per-district records
                district_records = {}
                for row in data_rows:
                    if not row:
                        continue
                    # Find FIRST cell that normalizes to a canonical district
                    # (district may be in col 0, 1, or 2 depending on whether S.No. is present)
                    canonical = None
                    dname_idx = -1
                    for i, cell in enumerate(row):
                        if cell:
                            cn = normalize_district(cell)
                            if cn:
                                canonical = cn
                                dname_idx = i
                                break
                    if not canonical:
                        continue
                    rec = {}
                    for col_i, val in enumerate(row):
                        if col_i == dname_idx:
                            continue
                        if col_i >= len(fields):
                            continue
                        fkey = fields[col_i]
                        if not fkey or fkey == 's_no':
                            continue
                        parsed = parse_value(val)
                        if parsed is not None:
                            rec[fkey] = parsed
                    if rec:
                        district_records[canonical] = rec

                if not district_records:
                    continue

                # Initialize or extend category
                if category not in out_tables:
                    out_tables[category] = {
                        'fields': [f for f in fields if f and f != 's_no'],
                        'districts': {},
                    }
                # Merge field list
                for f in fields:
                    if f and f != 's_no' and f not in out_tables[category]['fields']:
                        out_tables[category]['fields'].append(f)
                # Merge districts (later table wins)
                for dname, rec in district_records.items():
                    if dname not in out_tables[category]['districts']:
                        out_tables[category]['districts'][dname] = {}
                    out_tables[category]['districts'][dname].update(rec)

    return out_tables


# ─── Main ────────────────────────────────────────────────────────────

def main():
    pdfs = sorted(glob.glob(str(SRC_DIR / '*.pdf')))
    print(f"PDFs found: {len(pdfs)}")

    complete = {'state': 'Andhra Pradesh', 'quarters': {}}
    timeseries_periods = []

    # Process in chronological order
    pdfs_with_period = []
    for pdf in pdfs:
        m = re.search(r'(\d+)(?:rd|th|nd|st)?_agenda', os.path.basename(pdf))
        if not m:
            print(f"  skip (no meeting num): {pdf}")
            continue
        meeting = m.group(1)
        if meeting not in MEETING_QUARTER:
            print(f"  skip (unknown meeting {meeting}): {pdf}")
            continue
        period_code, period_label = MEETING_QUARTER[meeting]
        pdfs_with_period.append((pdf, period_code, period_label))

    pdfs_with_period.sort(key=lambda x: x[1])

    MIN_DISTRICTS = 10  # reject misclassified tables that resolve to <10 districts (e.g. village listings where rows are villages, not districts)
    for pdf, period_code, period_label in pdfs_with_period:
        print(f"\n=== {os.path.basename(pdf)} → {period_code} {period_label} ===")
        tables = extract_pdf(pdf, period_code, period_label)
        # Drop categories with fewer than MIN_DISTRICTS — usually misclassification noise
        filtered = {}
        for cat, t in tables.items():
            if len(t['districts']) >= MIN_DISTRICTS:
                filtered[cat] = t
            else:
                print(f"  skipping {cat} ({len(t['districts'])} districts < {MIN_DISTRICTS} threshold)")
        if not filtered:
            print(f"  no usable tables after threshold filter")
            continue
        complete['quarters'][period_code] = {
            'period': period_label,
            'tables': filtered,
        }
        for cat, t in filtered.items():
            print(f"  {cat}: {len(t['districts'])} districts, {len(t['fields'])} fields")

    # Write complete.json
    out_complete = SRC_DIR / 'andhra-pradesh_complete.json'
    with open(out_complete, 'w') as f:
        json.dump(complete, f, indent=2)
    print(f"\nWrote {out_complete} ({out_complete.stat().st_size/1024:.1f} KB)")

    # Build fi_timeseries.json: periods → districts → flat record
    for period_code in sorted(complete['quarters'].keys()):
        q = complete['quarters'][period_code]
        period_label = q['period']
        district_records = {}  # dname → flat record
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

    out_ts = SRC_DIR / 'andhra-pradesh_fi_timeseries.json'
    with open(out_ts, 'w') as f:
        json.dump({'periods': timeseries_periods}, f, indent=2)
    print(f"Wrote {out_ts} ({out_ts.stat().st_size/1024:.1f} KB)")

    # Build CSV (wide format)
    out_csv = SRC_DIR / 'andhra-pradesh_fi_timeseries.csv'
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
    print(f"Wrote {out_csv} ({out_csv.stat().st_size/1024:.1f} KB)")

    # Build per-quarter per-category CSVs
    for period_code, q in complete['quarters'].items():
        qdir = SRC_DIR / 'quarterly' / period_code
        qdir.mkdir(parents=True, exist_ok=True)
        for cat, table in q['tables'].items():
            csv_path = qdir / f'{cat}.csv'
            field_list = ['District'] + table['fields']
            with open(csv_path, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(field_list)
                for dname in CANONICAL_DISTRICTS:
                    if dname in table['districts']:
                        rec = table['districts'][dname]
                        row = [dname] + [rec.get(fk, '') for fk in table['fields']]
                        w.writerow(row)

    # Summary
    print(f"\n=== Summary ===")
    print(f"Quarters extracted: {len(complete['quarters'])}")
    for pc in sorted(complete['quarters'].keys()):
        q = complete['quarters'][pc]
        cats = list(q['tables'].keys())
        n_dist = max((len(t['districts']) for t in q['tables'].values()), default=0)
        print(f"  {pc} ({q['period']}): {len(cats)} cats, max {n_dist} districts; {cats}")


if __name__ == '__main__':
    main()
