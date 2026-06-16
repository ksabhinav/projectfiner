"""
FINER analysis library: robust loaders + LGD join infrastructure.

The repository ships indicator panels under public/indicators/<ind>/<quarter>.json.
Three different geo-key conventions are used across sources:
  - SLBC indicators : state = slug ('arunachal-pradesh'), district = TitleCase
  - rbi_banking_outlets : state/district = UPPERCASE
  - structural (rwi/viirs/elevation/nfhs/crop/pmgsy/nrlm) : carry district_lgd directly

This module resolves every row to an LGD code so all sources join cleanly.
"""
import json, os, re, glob
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IND = os.path.join(ROOT, 'public', 'indicators')

def _norm_state(s):
    if s is None: return ''
    s = s.lower().strip()
    s = s.replace('&', ' and ')
    s = re.sub(r'[^a-z0-9]+', '', s)          # drop spaces/hyphens/and-words handled below
    return s

def _norm_state2(s):
    """canonical: strip the word 'and' too so 'jammu-kashmir' == 'Jammu and Kashmir'."""
    s = _norm_state(s)
    s = s.replace('and', '')
    return s

def _norm_dist(d):
    if d is None: return ''
    d = d.lower().strip()
    # strip leading serial numbers like '12 ' but keep '24 paraganas'
    d = re.sub(r'[^a-z0-9]+', '', d)
    return d

# manual slug -> canonical full-state for the SLBC slugs
SLUG_FULL = {
    'andhra-pradesh':'Andhra Pradesh','arunachal-pradesh':'Arunachal Pradesh','assam':'Assam',
    'bihar':'Bihar','chhattisgarh':'Chhattisgarh','delhi':'Delhi','goa':'Goa','gujarat':'Gujarat',
    'haryana':'Haryana','himachal-pradesh':'Himachal Pradesh','jammu-kashmir':'Jammu and Kashmir',
    'jharkhand':'Jharkhand','karnataka':'Karnataka','kerala':'Kerala','ladakh':'Ladakh',
    'madhya-pradesh':'Madhya Pradesh','maharashtra':'Maharashtra','manipur':'Manipur',
    'meghalaya':'Meghalaya','mizoram':'Mizoram','nagaland':'Nagaland','odisha':'Odisha',
    'punjab':'Punjab','rajasthan':'Rajasthan','sikkim':'Sikkim','tamil-nadu':'Tamil Nadu',
    'telangana':'Telangana','tripura':'Tripura','uttar-pradesh':'Uttar Pradesh',
    'uttarakhand':'Uttarakhand','west-bengal':'West Bengal',
}

@lru_cache(maxsize=1)
def lgd_index():
    """Return dicts: (state_norm,dist_norm)->lgd, dist_norm->set(lgd), lgd->meta."""
    raw = json.load(open(os.path.join(ROOT,'public','district_lgd_codes.json')))['districts']
    by_sd = {}            # (state_norm2, dist_norm) -> lgd
    by_d = {}             # dist_norm -> set(lgd)
    meta = {}             # lgd -> {district,state,state_lgd_code,census}
    for r in raw:
        lgd = r['lgd_code']; st = r['state']
        meta[lgd] = {'district': r['district'], 'state': st,
                     'state_lgd': r.get('state_lgd_code'), 'census': r.get('census_2011_code')}
        sn = _norm_state2(st)
        names = [r['district']] + (r.get('aliases') or [])
        for nm in names:
            dn = _norm_dist(nm)
            by_sd[(sn, dn)] = lgd
            by_d.setdefault(dn, set()).add(lgd)
    return by_sd, by_d, meta

def resolve_lgd(state, district):
    """Resolve (state, district) -> lgd code or None. State may be slug/upper/full."""
    by_sd, by_d, meta = lgd_index()
    sn = _norm_state2(SLUG_FULL.get(str(state).lower(), state))
    dn = _norm_dist(district)
    if (sn, dn) in by_sd:
        return by_sd[(sn, dn)]
    # state-qualified fuzzy: same state, startswith
    cands = [lgd for lgd in by_d.get(dn, set()) if _norm_state2(meta[lgd]['state']) == sn]
    if len(cands) == 1:
        return cands[0]
    # plain name fallback only if globally unique
    g = by_d.get(dn, set())
    if len(g) == 1:
        return next(iter(g))
    return None

def load_indicator(ind, quarter=None):
    """Load one indicator/quarter -> list of dicts with lgd_code attached.
    If quarter None, returns dict quarter->records. 'static' files handled."""
    d = os.path.join(IND, ind)
    files = sorted(glob.glob(d + '/*.json'))
    out = {}
    for f in files:
        q = os.path.basename(f)[:-5]
        if quarter is not None and q != quarter:
            continue
        j = json.load(open(f))
        recs = []
        for r in j.get('districts', []):
            lgd = r.get('district_lgd')
            if lgd is None:
                lgd = resolve_lgd(r.get('state'), r.get('district'))
            rr = dict(r); rr['lgd_code'] = lgd; rr['quarter'] = q
            recs.append(rr)
        out[q] = recs
    if quarter is not None:
        return out.get(quarter, [])
    return out

def to_float(x):
    if x is None: return None
    try:
        return float(str(x).replace(',', '').strip())
    except Exception:
        return None

def quarters(ind):
    d = os.path.join(IND, ind)
    return sorted(os.path.basename(f)[:-5] for f in glob.glob(d + '/*.json'))
