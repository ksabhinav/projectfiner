#!/usr/bin/env python3
"""
Extract district-wise tables from the Telangana Wayback PDF haul.

Mirror of db/extract_wayback_kerala.py for Telangana, with three adaptations:

1. Telangana had only 10 districts pre-2016 (Hyderabad, Adilabad, Karimnagar,
   Khammam, Mahbubnagar, Medak, Nalgonda, Nizamabad, Rangareddy, Warangal)
   and 31-33 post-2016. The district-wise threshold is >= 8 unique resolved
   districts (keeps pre-2016 tables) PLUS a majority condition: matched
   district rows must be >= 60% of the table's data rows (rejects village
   lists / narrative tables where a few district names appear incidentally).

2. Many telanganaslbc.com PDFs are combined annexure books (e.g.
   Dec_2015_Annex.pdf, 85 pages) carrying MANY district-wise tables
   (branch network, CD ratio, priority sector, ...). All qualifying tables
   are captured: the first one fills the Kerala-compatible top-level keys
   (title/inferredPeriod/districtColumn/districts/headers/rows) and the
   rest land in `moreTables` (same per-table shape).

3. Some telanganaslbc.com PDFs have 180°-rotated pages where cell text is
   character-reversed ("DABALIDA" = "ADILABAD") and the grid transposed —
   the same artifact handled in slbc-data/telangana/extract_telangana_cqr.py.
   The transpose + cell-reversal recovery pass is reused here.

RAW dumps only — every cell verbatim from the PDF (no unit conversion,
no normalization, no invented values). Output:
slbc-data/telangana/wayback/extracted/<basename>.json

Run AFTER db/fetch_wayback_pdfs.py telangana telanganaslbc.com:
    python3 db/extract_wayback_telangana.py
    python3 db/extract_wayback_telangana.py --only-district-wise
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'telangana'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback'
OUT_DIR = WAYBACK_DIR / 'extracted'

PDF_TIME_BUDGET_S = 180  # default per-PDF wall-clock timeout (override --timeout)


# ── Districts ──────────────────────────────────────────────────────────
# 33 modern districts (post-2019 canonical, per extract_telangana_cqr.py).
# The 10 pre-2016 districts are a subset by name (Mahbubnagar→Mahabubnagar,
# Rangareddy→Ranga Reddy handled via aliases).
TG_CANONICAL = [
    'Adilabad', 'Bhadradri Kothagudem', 'Hanumakonda', 'Hyderabad', 'Jagitial',
    'Jangoan', 'Jayashankar Bhupalapally', 'Jogulamba Gadwal', 'Kamareddy',
    'Karimnagar', 'Khammam', 'Kumuram Bheem Asifabad', 'Mahabubabad',
    'Mahabubnagar', 'Mancherial', 'Medak', 'Medchal Malkajgiri', 'Mulugu',
    'Nagarkurnool', 'Nalgonda', 'Narayanpet', 'Nirmal', 'Nizamabad',
    'Peddapalli', 'Rajanna Sircilla', 'Ranga Reddy', 'Sangareddy', 'Siddipet',
    'Suryapet', 'Vikarabad', 'Wanaparthy', 'Warangal', 'Yadadri Bhuvanagiri',
]

# Alternative spellings observed in TG SLBC PDFs (from extract_telangana_cqr.py
# plus wayback-haul filename variants). Keys are matched after stripping
# everything but letters and lowercasing.
ALT_NAMES = {
    'JAGTIAL': 'Jagitial',
    'JAGTIYAL': 'Jagitial',
    'JAGITYAL': 'Jagitial',
    'JANGAON': 'Jangoan',
    'JANAGAON': 'Jangoan',
    'JANGOAN': 'Jangoan',
    'JAYASHANKAR BHUPALAPALLE': 'Jayashankar Bhupalapally',
    'JAYASHANKAR': 'Jayashankar Bhupalapally',
    'BHUPALAPALLY': 'Jayashankar Bhupalapally',
    'JOGULAMBA': 'Jogulamba Gadwal',
    'JOGULAMBHA': 'Jogulamba Gadwal',
    'GADWAL': 'Jogulamba Gadwal',
    'KOMARAM BHEEM': 'Kumuram Bheem Asifabad',
    'KOMARAMBHEEM': 'Kumuram Bheem Asifabad',
    'KUMARAM BHEEM': 'Kumuram Bheem Asifabad',
    'KUMRAM BHEEM': 'Kumuram Bheem Asifabad',
    'KUMURAM BHEEM ASIFABAD': 'Kumuram Bheem Asifabad',
    'KUMARAM BHEEM ASIFABAD': 'Kumuram Bheem Asifabad',
    'ASIFABAD': 'Kumuram Bheem Asifabad',
    'MAHBUBNAGAR': 'Mahabubnagar',
    'MAHABUB NAGAR': 'Mahabubnagar',
    'MAHABOOBNAGAR': 'Mahabubnagar',
    'MAHABOOB NAGAR': 'Mahabubnagar',
    'MEDCHAL': 'Medchal Malkajgiri',
    'MEDCHAL MALKAJGIRI': 'Medchal Malkajgiri',
    'MEDCHAL-MALKAJGIRI': 'Medchal Malkajgiri',
    'MALKAJGIRI': 'Medchal Malkajgiri',
    'RAJANNA': 'Rajanna Sircilla',
    'SIRCILLA': 'Rajanna Sircilla',
    'SIRICILLA': 'Rajanna Sircilla',
    'RAJANNA SIRCILLA': 'Rajanna Sircilla',
    'RANGAREDDY': 'Ranga Reddy',
    'RANGA REDDY': 'Ranga Reddy',
    'K V RANGAREDDY': 'Ranga Reddy',
    'KVRANGAREDDY': 'Ranga Reddy',
    'YADADRI': 'Yadadri Bhuvanagiri',
    'BHUVANAGIRI': 'Yadadri Bhuvanagiri',
    'BHONGIR': 'Yadadri Bhuvanagiri',
    'YADADRI BHUVANAGIRI': 'Yadadri Bhuvanagiri',
    'YADADRI BHONGIR': 'Yadadri Bhuvanagiri',
    'BHADRADRI': 'Bhadradri Kothagudem',
    'BADRADRI': 'Bhadradri Kothagudem',
    'KOTHAGUDEM': 'Bhadradri Kothagudem',
    'BHADRADRI KOTHAGUDEM': 'Bhadradri Kothagudem',
    'WARANGAL URBAN': 'Hanumakonda',   # post-2021 rename
    'WARANGAL U': 'Hanumakonda',
    'HANAMKONDA': 'Hanumakonda',
    'WARANGAL RURAL': 'Warangal',
    'WARANGAL R': 'Warangal',
    'NAGAR KURNOOL': 'Nagarkurnool',
    'NARAYANAPET': 'Narayanpet',
    'MANCHERIYAL': 'Mancherial',
    'SANGA REDDY': 'Sangareddy',
    'SURYAPETA': 'Suryapet',
    'YADADRI BHUVANGIRI': 'Yadadri Bhuvanagiri',
}


def _akey(s: str) -> str:
    """Alpha-only lowercase key for fuzzy-tolerant exact matching."""
    return re.sub(r'[^a-z]', '', s.lower())


DISTRICT_KEYS: dict[str, str] = {}
for _d in TG_CANONICAL:
    DISTRICT_KEYS[_akey(_d)] = _d
for _a, _d in ALT_NAMES.items():
    DISTRICT_KEYS[_akey(_a)] = _d


def canon_district(s: str | None) -> str | None:
    """Return canonical TG district name or None. Conservative: alpha-key
    exact match after stripping leading serial numbers; no substring scan
    (avoids matching district names inside narrative sentences)."""
    if not s:
        return None
    raw = str(s).strip()
    if len(raw) > 45:           # narrative cell, not a district label
        return None
    raw = re.sub(r'^\d+[\.\)\s]+', '', raw)   # strip leading "1. " / "2) "
    raw = raw.strip(' .,*:-')
    # Drop common suffixes like "Dist", "District", "Total"
    raw = re.sub(r'\b(dist(rict)?|total)\b\.?$', '', raw, flags=re.IGNORECASE).strip()
    key = _akey(raw)
    if not key or len(key) > 35:
        return None
    return DISTRICT_KEYS.get(key)


# ── Period inference ───────────────────────────────────────────────────
MONTHS = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05',
    'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10',
    'nov': '11', 'dec': '12',
}


def infer_period(text: str) -> str | None:
    """Pull a reporting period from title/filename text. Null when unsure."""
    if not text:
        return None
    # dd.mm.yyyy / dd/mm/yyyy / dd-mm-yyyy
    m = re.search(r'\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b', text)
    if m:
        mo = int(m.group(2))
        if 1 <= mo <= 12:
            return f'{m.group(3)}-{mo:02d}'
    # dd.mm.yy (two-digit year, e.g. "as on 31.03.24")
    m = re.search(r'\b(\d{1,2})[./-](\d{1,2})[./-](\d{2})\b(?![./-]?\d)', text)
    if m:
        mo, yy = int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 14 <= yy <= 39:
            return f'20{yy:02d}-{mo:02d}'
    # Month-name + 4-digit year ("AS ON December 2022", "March-2016", "SEPT_2017")
    m = re.search(r'\b([A-Za-z]{3,9})[\s,_.-]*(20\d{2})\b', text)
    if m:
        mo = MONTHS.get(m.group(1).lower()[:3])
        if mo:
            return f'{m.group(2)}-{mo}'
    # Month-name + 2-digit year ("CQR_Annex_March23", "December_23", "SEPT_22")
    m = re.search(r'\b([A-Za-z]{3,9})[\s,_.-]*(\d{2})\b', text)
    if m:
        mo = MONTHS.get(m.group(1).lower()[:3])
        yy = int(m.group(2))
        if mo and 14 <= yy <= 39:
            return f'20{yy:02d}-{mo}'
    # CQR filename MMYY pattern: CQR-0618 / CQR-1218 / CQR-ANNEX-0318
    m = re.search(r'CQR[-_]?(?:ANNEX[-_]?)?(\d{2})(\d{2})\b', text, re.IGNORECASE)
    if m:
        mo, yy = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 14 <= yy <= 39:
            return f'20{yy:02d}-{mo:02d}'
    # Fiscal-year markers like 2021-22 — assume Mar-end of latter year,
    # but only when the years are consecutive (so "1-44" never matches).
    m = re.search(r'\b(20\d{2})\s*-\s*(\d{2})\b', text)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        if y2 == (y1 + 1) % 100:
            return f'20{y2:02d}-03'
    return None


# ── Rotated-page recovery (from extract_telangana_cqr.py) ──────────────
def _is_reversed_page(text: str) -> bool:
    """Detect pages where text is character-reversed (180°-rotated TG PDFs)."""
    if not text:
        return False
    up = text.upper()
    # 'ANNEXURE', 'DISTRICT', 'TELANGANA SLBC' reversed
    return ('ERUXENNA' in up or 'TCIRTSID' in up or 'ANAGNALET' in up
            and 'TELANGANA' not in up)


def _maybe_reverse_table(table, reversed_page: bool):
    """If page is rotated 180°: reverse each cell's characters, transpose
    the grid (rows<->cols swap), then reverse row order."""
    if not reversed_page:
        return table
    rev = [[(None if c is None else str(c)[::-1]) for c in row] for row in table]
    n_cols = max((len(r) for r in rev), default=0)
    transposed = []
    for col in range(n_cols):
        transposed.append([r[col] if col < len(r) else None for r in rev])
    transposed.reverse()
    return transposed


def cell_text(c) -> str:
    return ('' if c is None else str(c)).strip().replace('\n', ' ')


# ── Core per-PDF extraction ────────────────────────────────────────────
def _find_district_column(table) -> tuple[int, list[str]] | None:
    """Return (col_idx, unique_districts) for the first early column that
    matches the district-wise criteria, else None.

    Criteria: >= 8 unique resolved districts AND matched-district rows are
    a clear majority (>= 60%) of the data rows (rows from the first
    district-bearing row onward that have any content)."""
    ncols = max((len(r) for r in table), default=0)
    for col in range(min(4, ncols)):
        matched_rows = 0
        uniq: dict[str, None] = {}
        first_match_ri = None
        for ri, r in enumerate(table):
            if col < len(r):
                d = canon_district(cell_text(r[col]))
                if d:
                    matched_rows += 1
                    uniq[d] = None
                    if first_match_ri is None:
                        first_match_ri = ri
        if len(uniq) < 8 or first_match_ri is None:
            continue
        data_rows = 0
        for r in table[first_match_ri:]:
            if any(cell_text(c) for c in r):
                data_rows += 1
        if data_rows and matched_rows / data_rows >= 0.6:
            return col, list(uniq)
    return None


def _page_title(text: str) -> str:
    """First few non-empty text lines of the page (the annexure header)."""
    lines = [ln.strip() for ln in (text or '').split('\n') if ln.strip()]
    return ' / '.join(lines[:4])[:200]


def extract_tables_from_pdf(pdf_path: Path) -> dict:
    """Walk every page, capture ALL qualifying district-wise tables.

    Returns {'tables': [per-table dicts], 'reversedPagesHandled': n,
             'reversedPagesSeen': m}."""
    import pdfplumber
    found = []
    reversed_seen = 0
    reversed_handled = 0
    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages):
            text = page.extract_text() or ''
            reversed_page = _is_reversed_page(text)
            if reversed_page:
                reversed_seen += 1
                rev_lines = [ln[::-1] for ln in text.split('\n')]
                text = '\n'.join(rev_lines[::-1])
            tables = page.extract_tables() or []
            page_had_hit = False
            for t in tables:
                if not t or len(t) < 4:
                    continue
                t = _maybe_reverse_table(t, reversed_page)
                hit = _find_district_column(t)
                if not hit:
                    continue
                col, districts = hit
                # Header rows = rows before the first district-bearing row
                header_end = 0
                for ri, r in enumerate(t):
                    if col < len(r) and canon_district(cell_text(r[col])):
                        header_end = ri
                        break
                title = _page_title(text) or pdf_path.stem.replace('_', ' ')
                period = infer_period(title) or infer_period(text[:400]) \
                    or infer_period(pdf_path.stem)
                found.append({
                    'title': title,
                    'inferredPeriod': period,
                    'districtColumn': col,
                    'districts': districts,
                    'pageIndex': pi,
                    'headers': [[cell_text(c) for c in row] for row in t[:header_end]],
                    'rows': [[cell_text(c) for c in row] for row in t[header_end:]],
                })
                page_had_hit = True
            if reversed_page and page_had_hit:
                reversed_handled += 1
    return {
        'tables': found,
        'reversedPagesSeen': reversed_seen,
        'reversedPagesHandled': reversed_handled,
    }


# ── Per-PDF wall-clock timeout guard (pattern from extract_uttar_pradesh.py) ──
def _extract_worker(conn, pdf_path_str: str):
    try:
        result = extract_tables_from_pdf(Path(pdf_path_str))
        conn.send(('ok', result))
    except Exception as e:                                  # noqa: BLE001
        conn.send(('error', f'{type(e).__name__}: {e}'))
    finally:
        conn.close()


def _run_extract_with_timeout(pdf_path: Path, timeout_s: float):
    """Run extract_tables_from_pdf in a worker process with a hard
    wall-clock timeout. Returns (status, result) — 'ok'|'timeout'|'error'."""
    import multiprocessing as mp
    ctx = mp.get_context('spawn')  # safe on macOS
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    p = ctx.Process(target=_extract_worker, args=(child_conn, str(pdf_path)))
    p.start()
    child_conn.close()
    deadline = time.time() + timeout_s
    result = None
    while time.time() < deadline:
        remaining = max(0.0, deadline - time.time())
        if parent_conn.poll(min(remaining, 1.0)):
            try:
                result = parent_conn.recv()
            except EOFError:
                result = None
            break
        if not p.is_alive():
            if parent_conn.poll(0.1):
                try:
                    result = parent_conn.recv()
                except EOFError:
                    pass
            break
    parent_conn.close()
    if p.is_alive():
        p.terminate()
        p.join(5)
        if p.is_alive():
            p.kill()
        if result is None:
            return ('timeout', None)
    p.join(5)
    if result is None:
        return ('error', 'worker exited without result')
    return result


# ── Main ───────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only-district-wise', action='store_true',
                    help='Skip PDFs without district/cqr/annex/cd-ratio hints '
                         'in the filename (faster).')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--timeout', type=float, default=PDF_TIME_BUDGET_S,
                    help='Per-PDF wall-clock budget in seconds.')
    args = ap.parse_args()

    manifest_path = WAYBACK_DIR / 'manifest.json'
    if not manifest_path.exists():
        print(f'ERROR: {manifest_path} missing — run fetch_wayback_pdfs.py first',
              file=sys.stderr)
        sys.exit(1)
    manifest = json.loads(manifest_path.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pdfs_total = len(manifest['files'])
    skipped_truncated = 0
    missing = 0
    candidates = []
    for entry in manifest['files']:
        # Skip files Wayback truncated at capture (CLAUDE.md gotcha #87).
        if entry.get('status') == 'truncated':
            skipped_truncated += 1
            continue
        local = ROOT / entry.get('localPath', '')
        if not local.exists():
            missing += 1
            continue
        if args.only_district_wise:
            nl = local.name.lower()
            if not any(k in nl for k in ('district', 'distt', 'dist-', 'dw_',
                                         'cqr', 'annex', 'cd_ratio', 'cd-ratio',
                                         'cdratio', 'acp')):
                continue
        candidates.append(entry)
    if args.limit:
        candidates = candidates[: args.limit]

    print(f'{pdfs_total} manifest entries; skipping {skipped_truncated} truncated, '
          f'{missing} missing; examining {len(candidates)} PDF(s)', flush=True)

    out_count = 0
    no_table = 0
    errors = 0
    timeouts = 0
    tables_total = 0
    rev_seen_total = 0
    rev_handled_total = 0
    used_names: dict[str, str] = {}   # out-stem (lower) → sourcePdf

    for entry in candidates:
        local = ROOT / entry['localPath']
        t0 = time.time()
        status, result = _run_extract_with_timeout(local, args.timeout)
        elapsed = time.time() - t0
        if status == 'timeout':
            print(f'  TIMEOUT {local.name[:70]} after {elapsed:.0f}s', flush=True)
            timeouts += 1
            continue
        if status == 'error':
            print(f'  ERR {local.name[:70]}: {result}', file=sys.stderr)
            errors += 1
            continue
        rev_seen_total += result['reversedPagesSeen']
        rev_handled_total += result['reversedPagesHandled']
        tables = result['tables']
        if not tables:
            no_table += 1
            continue

        # basename collision guard (same filename in two year dirs)
        stem = local.stem
        key = stem.lower()
        if key in used_names and used_names[key] != entry['localPath']:
            stem = f'{local.parent.name}_{stem}'
            key = stem.lower()
        used_names[key] = entry['localPath']

        first = tables[0]
        payload = {
            'sourcePdf': str(local.relative_to(ROOT)),
            'originalUrl': entry.get('originalUrl'),
            'snapshotTimestamp': entry.get('snapshotTimestamp'),
            **first,
            'tablesTotal': len(tables),
            'moreTables': tables[1:],
        }
        (OUT_DIR / (stem + '.json')).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2))
        tables_total += len(tables)
        periods = sorted({t['inferredPeriod'] for t in tables if t['inferredPeriod']})
        print(f'  OK  {local.name[:60]:60} → {len(tables)} table(s), '
              f'periods={periods or [None]}, {elapsed:.1f}s', flush=True)
        out_count += 1

    print(f'\npdfs_total={pdfs_total} skipped_truncated={skipped_truncated} '
          f'missing={missing} examined={len(candidates)}')
    print(f'extracted={out_count} (tables={tables_total}) no_table={no_table} '
          f'errors={errors} timeouts={timeouts}')
    print(f'reversed pages: seen={rev_seen_total} handled={rev_handled_total}')
    print(f'output: {OUT_DIR.relative_to(ROOT)}/')


if __name__ == '__main__':
    main()
