#!/usr/bin/env python3
"""Ingest NFHS-6 (2023-24) district health-insurance coverage into FINER.

Adds NFHS-6 as the third wave of the `nfhs_health_insurance` indicator
(alongside NFHS-4 2015-16 and NFHS-5 2019-21). No SQLite dependency — reads a
district-level CSV directly and resolves districts to LGD codes via
public/district_lgd_codes.json (same alias layer the rest of FINER uses).

INPUT (pick one):
  --csv  <path>   a district-level NFHS-6 CSV (e.g. the harmonised Zenodo
                  "NFHS India Explorer" file, or any wide CSV with a district
                  name, a state name, and a health-insurance % column).
  --url  <url>    download first (only works when network egress allows the host;
                  zenodo.org / nfhsiips.in are NOT in this container's allowlist).

The CSV schema is auto-detected but can be pinned:
  --district-col / --state-col / --value-col   exact header overrides.
  --round-col --round-value                     if the file is long-format with a
                                                round column (keep rows where
                                                round == 6 / 'NFHS-6').

OUTPUT:
  public/indicators/nfhs_health_insurance/2024-03.json   (NFHS-6 wave, pct)
  public/indicators/nfhs_health_insurance/static.json    (adds nfhs6_pct)
  + patches the frontend timeline/citation ONLY after data is written
    (so the repo never references NFHS-6 before the data exists).

ASSUMPTIONS (flagged per operating principles):
  * NFHS-6 reference period 2023-24 is encoded as quarter '2024-03', matching the
    existing convention (NFHS-4 -> 2016-03, NFHS-5 -> 2021-03).
  * Manipur was NOT surveyed in NFHS-6; its districts are left absent (the map
    falls back to NFHS-5), never written as 0.
  * The health-insurance indicator is "households with any usual member covered
    under a health insurance/financing scheme (%)".
"""
import argparse, csv, json, os, re, sys, io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IND_DIR = os.path.join(ROOT, 'public', 'indicators', 'nfhs_health_insurance')
QUARTER = '2024-03'

# ---- LGD resolver (self-contained mirror of insights/lib/finer.py) ----
def _ns(s):
    if s is None: return ''
    s = s.lower().strip().replace('&', ' and ')
    s = re.sub(r'[^a-z0-9]+', '', s)
    return s.replace('and', '')

def _nd(d):
    if d is None: return ''
    return re.sub(r'[^a-z0-9]+', '', d.lower().strip())

# full state name -> FINER slug (covers all 36 states/UTs)
FULL_SLUG = {
    'andaman and nicobar islands':'andaman-nicobar','andhra pradesh':'andhra-pradesh',
    'arunachal pradesh':'arunachal-pradesh','assam':'assam','bihar':'bihar',
    'chandigarh':'chandigarh','chhattisgarh':'chhattisgarh','delhi':'delhi','goa':'goa',
    'gujarat':'gujarat','haryana':'haryana','himachal pradesh':'himachal-pradesh',
    'jammu and kashmir':'jammu-kashmir','jharkhand':'jharkhand','karnataka':'karnataka',
    'kerala':'kerala','ladakh':'ladakh','lakshadweep':'lakshadweep','madhya pradesh':'madhya-pradesh',
    'maharashtra':'maharashtra','manipur':'manipur','meghalaya':'meghalaya','mizoram':'mizoram',
    'nagaland':'nagaland','odisha':'odisha','puducherry':'puducherry','punjab':'punjab',
    'rajasthan':'rajasthan','sikkim':'sikkim','tamil nadu':'tamil-nadu','telangana':'telangana',
    'the dadra and nagar haveli and daman and diu':'dadra-nagar-haveli','tripura':'tripura',
    'uttar pradesh':'uttar-pradesh','uttarakhand':'uttarakhand','west bengal':'west-bengal',
}

def build_index():
    raw = json.load(open(os.path.join(ROOT, 'public', 'district_lgd_codes.json')))['districts']
    by_sd, by_d, meta = {}, {}, {}
    for r in raw:
        lgd, st = r['lgd_code'], r['state']
        slug = FULL_SLUG.get(st.lower(), _ns(st))
        meta[lgd] = {'district': r['district'], 'state': st, 'slug': slug}
        sn = _ns(st)
        for nm in [r['district']] + (r.get('aliases') or []):
            dn = _nd(nm)
            by_sd[(sn, dn)] = lgd
            by_d.setdefault(dn, set()).add(lgd)
    return by_sd, by_d, meta

def resolve(state, district, idx):
    by_sd, by_d, meta = idx
    sn, dn = _ns(state), _nd(district)
    if (sn, dn) in by_sd: return by_sd[(sn, dn)]
    cands = [l for l in by_d.get(dn, set()) if _ns(meta[l]['state']) == sn]
    if len(cands) == 1: return cands[0]
    g = by_d.get(dn, set())
    return next(iter(g)) if len(g) == 1 else None

# ---- column auto-detection ----
DIST_PATS  = [r'^district$', r'district.*name', r'^dist(rict)?_?name$', r'^area_name$', r'^name$']
STATE_PATS = [r'^state', r'state.*ut', r'^state_?name$', r'state.*union']
# NFHS factsheet wording for the household health-insurance indicator
VAL_PATS   = [r'health\s*insur', r'health.*financ', r'insurance.*scheme', r'covered.*insurance',
              r'\bnfhs6\b', r'nfhs.?6.*insur', r'insur.*nfhs.?6']

def pick(headers, pats, override=None):
    if override:
        if override in headers: return override
        sys.exit(f"ERROR: column '{override}' not in CSV headers: {headers}")
    low = {h: h.lower() for h in headers}
    for p in pats:
        for h in headers:
            if re.search(p, low[h]): return h
    return None

def to_float(x):
    if x is None: return None
    x = str(x).strip().replace('%','').replace(',','')
    if x in ('', 'na', 'nan', '-', '*', '(*)', 'NA'): return None
    try: return float(x)
    except ValueError: return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv'); ap.add_argument('--url')
    ap.add_argument('--district-col'); ap.add_argument('--state-col'); ap.add_argument('--value-col')
    ap.add_argument('--round-col'); ap.add_argument('--round-value', default='6')
    ap.add_argument('--encoding', default='utf-8-sig')
    ap.add_argument('--dry-run', action='store_true', help='report match rate, write nothing')
    a = ap.parse_args()

    path = a.csv
    if a.url and not path:
        import urllib.request
        path = os.path.join(ROOT, 'db', '_nfhs6_download.csv')
        print(f'Downloading {a.url} ...')
        try:
            urllib.request.urlretrieve(a.url, path)
        except Exception as e:
            sys.exit(f"ERROR: download failed ({e}). This container's egress is "
                     f"allowlisted; add the host or use --csv with a local file.")
    if not path or not os.path.exists(path):
        sys.exit("ERROR: provide --csv <path> (or --url once egress allows the host).")

    with open(path, encoding=a.encoding, newline='') as f:
        rdr = csv.DictReader(f)
        headers = rdr.fieldnames or []
        rows = list(rdr)
    print(f'Loaded {len(rows)} rows; headers: {headers}')

    dcol = pick(headers, DIST_PATS, a.district_col)
    scol = pick(headers, STATE_PATS, a.state_col)
    vcol = pick(headers, VAL_PATS, a.value_col)
    print(f'Detected -> district={dcol!r} state={scol!r} value={vcol!r}')
    if not (dcol and vcol):
        sys.exit("ERROR: could not auto-detect district/value columns. Re-run with "
                 "--district-col / --state-col / --value-col (see headers above).")

    if a.round_col and a.round_col in headers:
        rows = [r for r in rows if str(r.get(a.round_col,'')).strip().lstrip('NFHS-').strip() == str(a.round_value)]
        print(f'Filtered to round {a.round_value}: {len(rows)} rows')

    idx = build_index()
    out, unmatched, manipur = {}, [], 0
    for r in rows:
        dist = (r.get(dcol) or '').strip()
        state = (r.get(scol) or '').strip() if scol else ''
        val = to_float(r.get(vcol))
        if not dist or val is None: continue
        if _ns(state) == _ns('Manipur'):
            manipur += 1; continue   # not surveyed in NFHS-6
        lgd = resolve(state, dist, idx)
        if lgd is None:
            unmatched.append(f'{state}/{dist}'); continue
        m = idx[2][lgd]
        out[lgd] = {'district': m['district'], 'state': m['slug'], 'pct': round(val, 1)}

    n = len(out)
    print(f'\nMatched {n} districts. Unmatched {len(unmatched)} (Manipur skipped: {manipur}).')
    if unmatched[:20]:
        print('  e.g. unmatched:', ', '.join(sorted(set(unmatched))[:20]))
    if a.dry_run:
        print('\n[dry-run] no files written.'); return
    if n < 300:
        sys.exit(f"ABORT: only {n} matched (<300). Likely wrong value column or schema; "
                 f"inspect headers and pass explicit --*-col overrides.")

    # 1) write the NFHS-6 wave file
    os.makedirs(IND_DIR, exist_ok=True)
    wave = {'indicator': 'nfhs_health_insurance', 'quarter': QUARTER,
            'label': 'Health Insurance Coverage', 'description':
            'Households with any usual member covered under a health insurance/financing scheme (%). NFHS-6 (2023-24).',
            'districts': sorted(out.values(), key=lambda x: (x['state'], x['district']))}
    with open(os.path.join(IND_DIR, f'{QUARTER}.json'), 'w') as f:
        json.dump(wave, f, separators=(',', ':'))
    print(f'  wrote {QUARTER}.json ({n} districts)')

    # 2) merge nfhs6_pct into static.json
    sp = os.path.join(IND_DIR, 'static.json')
    static = json.load(open(sp))
    bylgd = {}
    for d in static['districts']:
        lgd = resolve(d['state'], d['district'], idx)
        if lgd is not None: bylgd[lgd] = d
    added = 0
    for lgd, rec in out.items():
        if lgd in bylgd:
            bylgd[lgd]['nfhs6_pct'] = rec['pct']; added += 1
        else:
            static['districts'].append({'district': rec['district'], 'state': rec['state'],
                                        'nfhs4_pct': None, 'nfhs5_pct': None, 'nfhs6_pct': rec['pct']})
            added += 1
    static['description'] = ('Households with any member covered under health insurance/financing scheme (%). '
                             'NFHS-4 (2015-16), NFHS-5 (2019-21), NFHS-6 (2023-24).')
    with open(sp, 'w') as f:
        json.dump(static, f, separators=(',', ':'))
    print(f'  updated static.json (nfhs6_pct on {added} districts)')

    patch_frontend()
    print('\nDONE. Next: rebuild district pages + RAG if desired '
          '(db/build_district_pages.py; scripts/rag/ingest_indicator_files.py).')

def patch_frontend():
    """Add NFHS-6 to the slider timePoints + citation. Idempotent; only called
    after the data file is written."""
    idx = os.path.join(ROOT, 'src', 'pages', 'index.astro')
    s = open(idx).read()
    old_tp = "timePoints: ['2021-03', '2016-03'],"
    new_tp = "timePoints: ['2024-03', '2021-03', '2016-03'],"
    if old_tp in s:
        s = s.replace(old_tp, new_tp)
        s = s.replace('Use the timeline slider to compare NFHS-5 (2019–21) vs NFHS-4 (2015–16). Covers 637 districts across India.',
                      'Use the timeline slider to compare NFHS-6 (2023–24), NFHS-5 (2019–21) and NFHS-4 (2015–16). Manipur was not surveyed in NFHS-6.')
        open(idx, 'w').write(s)
        print('  patched index.astro timePoints + description')
    elif new_tp in s:
        print('  index.astro already patched')
    else:
        print('  WARN: could not find NFHS timePoints anchor in index.astro — patch manually:')
        print(f'        replace  {old_tp}\n        with     {new_tp}')

    src = os.path.join(ROOT, 'src', 'lib', 'indicator-sources.ts')
    t = open(src).read()
    anchor = "label: `NFHS-${quarter === '2016-03' ? '4' : '5'} district factsheets`,"
    new = "label: `NFHS-${quarter === '2016-03' ? '4' : quarter === '2021-03' ? '5' : '6'} district factsheets`,"
    if anchor in t:
        t = t.replace(anchor, new)
        t = t.replace('NFHS-5 (2019–21) and NFHS-4 (2015–16). Households with health-insurance member.',
                      'NFHS-6 (2023–24), NFHS-5 (2019–21) and NFHS-4 (2015–16). Households with health-insurance member.')
        open(src, 'w').write(t)
        print('  patched indicator-sources.ts citation')
    elif new in t:
        print('  indicator-sources.ts already patched')
    else:
        print('  WARN: could not patch indicator-sources.ts citation — update manually.')

if __name__ == '__main__':
    main()
