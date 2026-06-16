"""Analysis 2: access vs usage, dormancy, BC-infrastructure effectiveness.
Links SLBC flow data to structural wealth (RWI, nightlights) and RBI outlet mix.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import pandas as pd, numpy as np
from scipy import stats

D = os.path.join(os.path.dirname(__file__), '..', 'data')
c = pd.read_csv(os.path.join(D, 'cross_section.csv'))

print('#'*70); print('(a) PMJDY DORMANCY (zero-balance share) vs WEALTH')
m = c.dropna(subset=['pmjdy_total','pmjdy_zerobal','rwi_mean']).copy()
m = m[m.pmjdy_total>0]
m['zbshare'] = m.pmjdy_zerobal/m.pmjdy_total*100
m = m[(m.zbshare>=0)&(m.zbshare<=100)]
r,pv = stats.spearmanr(m.rwi_mean, m.zbshare)
print(f' n={len(m)} median zero-balance share={m.zbshare.median():.1f}%')
print(f' Spearman(RWI, zero-balance share) rho={r:+.3f} p={pv:.1e}')
m['wq']=pd.qcut(m.rwi_mean,5,labels=['Q1poor','Q2','Q3','Q4','Q5rich'])
print(m.groupby('wq',observed=True).zbshare.median().round(1).to_string())

print('\n'+'#'*70); print('(b) BC-INFRASTRUCTURE EFFECTIVENESS')
# RBI outlets: bc share of total; does heavy-BC predict low CD ratio / low usage?
m2=c.dropna(subset=['rbi_total','rbi_bc','rbi_branch']).copy()
m2=m2[m2.rbi_total>0]
m2['bc_share']=m2.rbi_bc/m2.rbi_total*100
m2['outlets_per_branch']=m2.rbi_bc/m2.rbi_branch.replace(0,np.nan)
mm=m2.dropna(subset=['cdr_latest'])
mm=mm[(mm.cdr_latest>=1)&(mm.cdr_latest<=400)]
r,pv=stats.spearmanr(mm.bc_share, mm.cdr_latest)
print(f' Spearman(BC-share-of-outlets, CDR) rho={r:+.3f} p={pv:.1e} n={len(mm)}')
# wealth vs BC share
mw=m2.dropna(subset=['rwi_mean'])
r,pv=stats.spearmanr(mw.rwi_mean, mw.bc_share)
print(f' Spearman(RWI, BC-share) rho={r:+.3f} p={pv:.1e} n={len(mw)}')

print('\n'+'#'*70); print('(c) ACCOUNTS vs CREDIT (access vs credit-usage)')
# pmjdy accounts (access) vs kcc (rural credit usage) per district, controlling wealth
m3=c.dropna(subset=['pmjdy_total','kcc_total']).copy()
m3=m3[(m3.pmjdy_total>0)&(m3.kcc_total>0)]
m3['kcc_per_pmjdy']=m3.kcc_total/m3.pmjdy_total
r,pv=stats.spearmanr(m3.pmjdy_total, m3.kcc_total)
print(f' Spearman(pmjdy accounts, kcc cards) rho={r:+.3f} p={pv:.1e} n={len(m3)}')

print('\n'+'#'*70); print('(d) NFHS4->NFHS5 HEALTH INSURANCE reversals vs wealth')
mi=c.dropna(subset=['nfhs4_ins','nfhs5_ins','rwi_mean']).copy()
mi['ins_change']=mi.nfhs5_ins-mi.nfhs4_ins
print(f' n={len(mi)} median change={mi.ins_change.median():+.1f}pp  share FELL={(mi.ins_change<0).mean()*100:.0f}%')
r,pv=stats.spearmanr(mi.rwi_mean, mi.ins_change)
print(f' Spearman(RWI, insurance change) rho={r:+.3f} p={pv:.1e}')
mi['wq']=pd.qcut(mi.rwi_mean,5,labels=['Q1poor','Q2','Q3','Q4','Q5rich'])
print(' median insurance change (pp) by wealth quintile:')
print(mi.groupby('wq',observed=True).ins_change.median().round(1).to_string())
print(' share of districts where insurance FELL, by wealth quintile:')
print((mi.groupby('wq',observed=True).ins_change.apply(lambda s:(s<0).mean()*100)).round(0).to_string())
