"""Build master analytical datasets from public/indicators.
Outputs (insights/data/):
  cdr_panel.csv        district x quarter CD-ratio panel (deposit, advance, cdr)
  cross_section.csv    one row per LGD district: structural + latest SLBC flows
"""
import sys, os, csv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import finer
from finer import to_float, resolve_lgd, lgd_index

OUT = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(OUT, exist_ok=True)
_, _, META = lgd_index()

# ---------- 1. CD-ratio panel (all quarters) ----------
cdr = finer.load_indicator('credit_deposit_ratio')  # dict q->recs
rows = []
for q, recs in cdr.items():
    for r in recs:
        lgd = r['lgd_code']
        dep = to_float(r.get('total_deposit')); adv = to_float(r.get('total_advance'))
        cd = to_float(r.get('overall_cd_ratio'))
        if cd is None and dep and adv and dep > 0:
            cd = adv / dep * 100
        rows.append({'lgd': lgd, 'quarter': q, 'state': r.get('state'),
                     'district': r.get('district'), 'deposit': dep, 'advance': adv, 'cdr': cd})
with open(os.path.join(OUT, 'cdr_panel.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['lgd','quarter','state','district','deposit','advance','cdr'])
    w.writeheader(); w.writerows(rows)
print('cdr_panel.csv rows=', len(rows), 'quarters=', len(cdr))

# ---------- 2. Cross-section ----------
# helper to pull latest-quarter value per lgd for a field
def latest_by_lgd(ind, field, want_q=None):
    data = finer.load_indicator(ind)
    qs = sorted(data.keys())
    out = {}
    for q in qs:  # ascending so later overwrites -> latest wins
        if want_q and q != want_q: continue
        for r in data[q]:
            v = to_float(r.get(field))
            if r['lgd_code'] is not None and v is not None:
                out[r['lgd_code']] = v
    return out

cs = {}  # lgd -> dict
def put(name, d):
    for lgd, v in d.items():
        cs.setdefault(lgd, {})[name] = v

# structural cross-sections
put('rwi_mean', latest_by_lgd('facebook_rwi', 'rwi_mean'))
put('rwi_spread', latest_by_lgd('facebook_rwi', 'rwi_spread'))
put('nl_2023', latest_by_lgd('viirs_nightlights', 'nl_mean', '2023-12'))
put('nl_2012', latest_by_lgd('viirs_nightlights', 'nl_mean', '2012-12'))
put('elev_mean', latest_by_lgd('elevation_terrain', 'elevation_mean'))
put('elev_range', latest_by_lgd('elevation_terrain', 'elevation_range'))
put('nfhs4_ins', latest_by_lgd('nfhs_health_insurance', 'nfhs4_pct'))
put('nfhs5_ins', latest_by_lgd('nfhs_health_insurance', 'nfhs5_pct'))
put('irrig_pct', latest_by_lgd('crop_production', 'irrigation_pct'))
put('rbi_total', latest_by_lgd('rbi_banking_outlets', 'rbi_outlets__total'))
put('rbi_bc', latest_by_lgd('rbi_banking_outlets', 'rbi_outlets__bc'))
put('rbi_branch', latest_by_lgd('rbi_banking_outlets', 'rbi_outlets__branch'))
put('rbi_rural', latest_by_lgd('rbi_banking_outlets', 'rbi_outlets__rural'))
put('cap_total', latest_by_lgd('capital_markets_access', 'cap_total'))
put('nrlm_shg', latest_by_lgd('nrlm_shg', 'shg_total'))
put('pmgsy_roads', latest_by_lgd('pmgsy_roads', 'roads_total'))

# latest SLBC flows
put('cdr_latest', latest_by_lgd('credit_deposit_ratio', 'overall_cd_ratio'))
put('deposit_latest', latest_by_lgd('credit_deposit_ratio', 'total_deposit'))
put('advance_latest', latest_by_lgd('credit_deposit_ratio', 'total_advance'))
put('pmjdy_total', latest_by_lgd('pmjdy', 'total_pmjdy_no'))
put('pmjdy_zerobal', latest_by_lgd('pmjdy', 'no_of_zero_balance_a_c'))
put('pmjdy_rural', latest_by_lgd('pmjdy', 'rural_no'))
put('pmjdy_rupay', latest_by_lgd('pmjdy', 'no_of_rupay_card_issued'))
put('pmjdy_female', latest_by_lgd('pmjdy', 'female_no'))
put('kcc_total', latest_by_lgd('kcc', 'total_no_of_kcc'))
put('digi_cov_pct', latest_by_lgd('digital_transactions', 'coverage_sb_pct'))

# write
cols = ['lgd','state','district','rwi_mean','rwi_spread','nl_2023','nl_2012','elev_mean','elev_range',
        'nfhs4_ins','nfhs5_ins','irrig_pct','rbi_total','rbi_bc','rbi_branch','rbi_rural','cap_total',
        'nrlm_shg','pmgsy_roads','cdr_latest','deposit_latest','advance_latest','pmjdy_total',
        'pmjdy_zerobal','pmjdy_rural','pmjdy_rupay','pmjdy_female','kcc_total','digi_cov_pct']
with open(os.path.join(OUT, 'cross_section.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(cols)
    for lgd in sorted(cs):
        m = META.get(lgd, {})
        row = [lgd, m.get('state'), m.get('district')]
        row += [cs[lgd].get(c) for c in cols[3:]]
        w.writerow(row)
print('cross_section.csv rows=', len(cs))
