"""Analysis 1: CD-ratio structure.
 (a) Baseline gradient: CD ratio vs district wealth (RWI / nightlights).
 (b) Capital-flight reversal: are high-DEPOSIT districts the worst net exporters?
 (c) Simpson / aggregation reversal: aggregate CDR trend vs district-median trend.
 (d) Beta + sigma convergence of CD ratio, 2020->2025.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import pandas as pd, numpy as np
from scipy import stats

D = os.path.join(os.path.dirname(__file__), '..', 'data')
p = pd.read_csv(os.path.join(D, 'cdr_panel.csv'))
c = pd.read_csv(os.path.join(D, 'cross_section.csv'))
# clean impossible
p = p[(p.cdr >= 1) & (p.cdr <= 400)].copy()
p['year'] = p.quarter.str[:4].astype(int)

print('#'*70); print('(a) BASELINE GRADIENT: CD ratio vs wealth')
m = c.dropna(subset=['cdr_latest','rwi_mean']).copy()
m = m[(m.cdr_latest>=1)&(m.cdr_latest<=400)]
r,pv = stats.spearmanr(m.rwi_mean, m.cdr_latest)
print(f' Spearman(RWI, CDR_latest)        rho={r:+.3f} p={pv:.1e} n={len(m)}')
mn = c.dropna(subset=['cdr_latest','nl_2023'])
mn = mn[(mn.cdr_latest>=1)&(mn.cdr_latest<=400)]
r2,pv2 = stats.spearmanr(np.log1p(mn.nl_2023), mn.cdr_latest)
print(f' Spearman(log nightlights, CDR)   rho={r2:+.3f} p={pv2:.1e} n={len(mn)}')
# wealth quintiles
m['wq'] = pd.qcut(m.rwi_mean, 5, labels=['Q1(poor)','Q2','Q3','Q4','Q5(rich)'])
print('\n median CDR by wealth quintile:')
print(m.groupby('wq', observed=True).cdr_latest.median().round(1).to_string())

print('\n'+'#'*70); print('(b) CAPITAL FLIGHT vs DEPOSIT SIZE')
m2 = c.dropna(subset=['deposit_latest','cdr_latest']).copy()
m2 = m2[(m2.cdr_latest>=1)&(m2.cdr_latest<=400)&(m2.deposit_latest>0)]
m2['dq'] = pd.qcut(np.log(m2.deposit_latest), 5, labels=['D1(small)','D2','D3','D4','D5(large)'])
print(' median CDR by deposit-size quintile:')
print(m2.groupby('dq', observed=True).cdr_latest.median().round(1).to_string())
r3,pv3 = stats.spearmanr(np.log(m2.deposit_latest), m2.cdr_latest)
print(f' Spearman(log deposit, CDR) rho={r3:+.3f} p={pv3:.1e} n={len(m2)}')

print('\n'+'#'*70); print('(c) SIMPSON / AGGREGATION REVERSAL of CD-ratio trend')
# balanced-ish panel: districts present in both 2020 and 2025
def yr_cdr(yr):
    sub = p[p.year==yr].sort_values('quarter').groupby('lgd').last()
    return sub
for y0,y1 in [(2020,2025),(2021,2025),(2022,2025)]:
    a=yr_cdr(y0); b=yr_cdr(y1)
    common = a.index.intersection(b.index)
    aa=a.loc[common]; bb=b.loc[common]
    agg0 = aa.advance.sum()/aa.deposit.sum()*100
    agg1 = bb.advance.sum()/bb.deposit.sum()*100
    med0 = aa.cdr.median(); med1 = bb.cdr.median()
    mean0=aa.cdr.mean(); mean1=bb.cdr.mean()
    dn = (bb.cdr.values - aa.cdr.values)
    frac_down = (dn<0).mean()
    print(f' {y0}->{y1} n={len(common):3d} | AGG(value-wtd) {agg0:.1f}->{agg1:.1f} ({agg1-agg0:+.1f}) | '
          f'MEDIAN dist {med0:.1f}->{med1:.1f} ({med1-med0:+.1f}) | mean {mean0:.1f}->{mean1:.1f} | %districts FELL={100*frac_down:.0f}%')

print('\n'+'#'*70); print('(d) CONVERGENCE of CD ratio 2020->2025')
a=yr_cdr(2020); b=yr_cdr(2025)
common=a.index.intersection(b.index)
x=a.loc[common,'cdr']; y=b.loc[common,'cdr']
g = np.log(y/x)  # growth
beta = stats.linregress(np.log(x), g)
print(f' BETA convergence: slope on log(initial)={beta.slope:+.4f} p={beta.pvalue:.1e} (neg=convergence) n={len(common)}')
print(f' SIGMA: sd(log CDR) 2020={np.std(np.log(x)):.3f} -> 2025={np.std(np.log(y)):.3f}')
