"""Analysis 3: robustness of the dormancy-wealth result + mechanism + positive deviants."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import pandas as pd, numpy as np
from scipy import stats
import statsmodels.formula.api as smf

D = os.path.join(os.path.dirname(__file__), '..', 'data')
c = pd.read_csv(os.path.join(D, 'cross_section.csv'))

print('#'*70); print('DORMANCY ROBUSTNESS')
m = c.dropna(subset=['pmjdy_total','pmjdy_zerobal','rwi_mean']).copy()
m = m[m.pmjdy_total>0]
m['zbshare'] = m.pmjdy_zerobal/m.pmjdy_total*100
m = m[(m.zbshare>=0.1)&(m.zbshare<=80)]   # drop exact-0 (likely missing) & impossible
print(f' base n={len(m)}  states={m.state.nunique()}')
r,pv=stats.spearmanr(m.rwi_mean,m.zbshare); print(f' base Spearman rho={r:+.3f} p={pv:.1e}')

# state breakdown - how many states individually show positive
print('\n per-state Spearman (states with n>=8):')
pos=0; tot=0
for st,g in m.groupby('state'):
    if len(g)<8: continue
    rr,pp=stats.spearmanr(g.rwi_mean,g.zbshare); tot+=1; pos+= (rr>0)
    print(f'   {st:22s} n={len(g):3d} rho={rr:+.3f} p={pp:.2f}')
print(f' -> {pos}/{tot} states have POSITIVE rho (wealth->dormancy within state)')

# leave-one-state-out: does any single state drive it?
print('\n leave-one-state-out Spearman range:')
rhos=[]
for st in m.state.unique():
    g=m[m.state!=st]; rr,_=stats.spearmanr(g.rwi_mean,g.zbshare); rhos.append((rr,st))
rhos.sort()
print(f'   min {rhos[0][0]:+.3f} (drop {rhos[0][1]})  max {rhos[-1][0]:+.3f} (drop {rhos[-1][1]})')

# multivariate with state fixed effects + branch density control
print('\n OLS: zbshare ~ rwi + log(branch density) + C(state)')
m['lbranch']=np.log(m.rbi_branch.replace(0,np.nan))
mm=m.dropna(subset=['lbranch'])
try:
    res=smf.ols('zbshare ~ rwi_mean + lbranch + C(state)', data=mm).fit()
    print(f'   rwi coef={res.params["rwi_mean"]:+.2f} (t={res.tvalues["rwi_mean"]:.2f}, p={res.pvalues["rwi_mean"]:.3f})  n={int(res.nobs)}')
    print(f'   lbranch coef={res.params["lbranch"]:+.2f} (t={res.tvalues["lbranch"]:.2f}, p={res.pvalues["lbranch"]:.3f})')
except Exception as e:
    print('   OLS err', e)

# mechanism: dormancy vs pre-existing banking (branch density) controlling wealth
print('\n MECHANISM: zbshare vs branch-per-account (pre-existing formal banking)')
m['branch_per_100k_acct']=m.rbi_branch/(m.pmjdy_total/1e5)
mb=m.dropna(subset=['branch_per_100k_acct'])
r,pv=stats.spearmanr(mb.branch_per_100k_acct, mb.zbshare)
print(f'   Spearman(branch per 100k PMJDY acct, zbshare) rho={r:+.3f} p={pv:.1e} n={len(mb)}')

print('\n'+'#'*70); print('POSITIVE DEVIANTS: CDR residual model')
g = c.dropna(subset=['cdr_latest','rwi_mean','nl_2023','elev_mean','irrig_pct']).copy()
g = g[(g.cdr_latest>=1)&(g.cdr_latest<=400)]
g['lnl']=np.log1p(g.nl_2023)
res=smf.ols('cdr_latest ~ rwi_mean + lnl + elev_mean + irrig_pct', data=g).fit()
g['resid']=res.resid
print(f' model n={int(res.nobs)} R2={res.rsquared:.3f}')
print(' TOP positive deviants (lend far above structural expectation):')
print(g.nlargest(8,'resid')[['district','state','cdr_latest','resid']].to_string(index=False))
print(' TOP negative deviants (lend far below):')
print(g.nsmallest(8,'resid')[['district','state','cdr_latest','resid']].to_string(index=False))
g[['lgd','state','district','cdr_latest','resid']].to_csv(os.path.join(D,'cdr_residuals.csv'),index=False)
