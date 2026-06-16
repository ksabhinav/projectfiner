"""Analysis 5: institutional vs economic determinants of district credit; convergence robustness; figures."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import pandas as pd, numpy as np
from scipy import stats
import statsmodels.formula.api as smf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

D=os.path.join(os.path.dirname(__file__),'..','data')
FIG=os.path.join(os.path.dirname(__file__),'..','figures')
os.makedirs(FIG,exist_ok=True)
c=pd.read_csv(os.path.join(D,'cross_section.csv'))
p=pd.read_csv(os.path.join(D,'cdr_panel.csv')); p=p[(p.cdr>=1)&(p.cdr<=400)].copy(); p['year']=p.quarter.str[:4].astype(int)

print('#'*70); print('HORSE RACE: what explains district CD ratio?')
g=c.dropna(subset=['cdr_latest','rwi_mean','nl_2023','elev_mean','irrig_pct','rbi_total']).copy()
g=g[(g.cdr_latest>=1)&(g.cdr_latest<=400)]
g['lnl']=np.log1p(g.nl_2023); g['lrbi']=np.log1p(g.rbi_total)
m_econ=smf.ols('cdr_latest ~ rwi_mean + lnl + elev_mean + irrig_pct + lrbi', data=g).fit()
m_state=smf.ols('cdr_latest ~ C(state)', data=g).fit()
m_both=smf.ols('cdr_latest ~ rwi_mean + lnl + elev_mean + irrig_pct + lrbi + C(state)', data=g).fit()
print(f' n={len(g)}')
print(f'  ECON only  (wealth,lights,elev,irrig,banking): R2={m_econ.rsquared:.3f}')
print(f'  STATE only (administration dummies):          R2={m_state.rsquared:.3f}')
print(f'  BOTH:                                          R2={m_both.rsquared:.3f}')
print(f'  => state identity explains {m_state.rsquared/m_both.rsquared*100:.0f}% as much variance as the full model;')
print(f'     economic structure adds {(m_both.rsquared-m_state.rsquared)*100:.1f}pp over state alone.')

print('\n'+'#'*70); print('CONVERGENCE ROBUSTNESS')
def last_in_year(yr): return p[p.year==yr].sort_values('quarter').groupby('lgd').last()
def betasigma(y0,y1,exclude=None,winsor=False):
    a=last_in_year(y0); b=last_in_year(y1); common=a.index.intersection(b.index)
    x=a.loc[common,'cdr'].copy(); y=b.loc[common,'cdr'].copy(); st=b.loc[common,'state']
    if exclude is not None:
        keep=~st.isin(exclude); x=x[keep]; y=y[keep]
    if winsor:
        lo,hi=x.quantile([.02,.98]); x=x.clip(lo,hi); lo,hi=y.quantile([.02,.98]); y=y.clip(lo,hi)
    gth=np.log(y/x); lr=stats.linregress(np.log(x),gth)
    return lr.slope,lr.pvalue,np.std(np.log(x)),np.std(np.log(y)),len(x)
for lbl,kw in [('base',{}),('drop TN+TG+AP high-CDR',{'exclude':['tamil-nadu','telangana','andhra-pradesh']}),
               ('winsor 2/98',{'winsor':True}),('2021->2025',{'y0':2021})]:
    y0=kw.pop('y0',2020); sl,pv,s0,s1,n=betasigma(y0,2025,**kw)
    print(f'  {lbl:26s} beta={sl:+.3f} p={pv:.1e}  sigma {s0:.3f}->{s1:.3f} ({"DIVERGE" if s1>s0 else "converge"})  n={n}')

# ---- FIGURES ----
# Fig1: dormancy by wealth quintile
m=c.dropna(subset=['pmjdy_total','pmjdy_zerobal','rwi_mean']).copy(); m=m[m.pmjdy_total>0]
m['zb']=m.pmjdy_zerobal/m.pmjdy_total*100; m=m[(m.zb>=0.1)&(m.zb<=80)]
m['wq']=pd.qcut(m.rwi_mean,5,labels=['Q1\npoorest','Q2','Q3','Q4','Q5\nrichest'])
fig,ax=plt.subplots(figsize=(6,4))
med=m.groupby('wq',observed=True).zb.median()
ax.bar(range(5),med.values,color='#b8603e')
ax.set_xticks(range(5)); ax.set_xticklabels(med.index)
ax.set_ylabel('Median PMJDY zero-balance account share (%)')
ax.set_title('Dormancy rises with district wealth\n(richer districts = more idle Jan Dhan accounts)')
for i,v in enumerate(med.values): ax.text(i,v+0.1,f'{v:.1f}%',ha='center',fontsize=9)
plt.tight_layout(); plt.savefig(os.path.join(FIG,'fig1_dormancy_wealth.png'),dpi=130); plt.close()

# Fig2: econ vs state R2
fig,ax=plt.subplots(figsize=(5.5,4))
ax.bar(['Economic\nstructure','State\nadministration','Both'],
       [m_econ.rsquared,m_state.rsquared,m_both.rsquared],color=['#3d7a8e','#b8603e','#5a7a3a'])
ax.set_ylabel('R² (share of district CD-ratio variation explained)')
ax.set_title('Which state you are in explains district credit\nfar better than your district’s economy')
for i,v in enumerate([m_econ.rsquared,m_state.rsquared,m_both.rsquared]): ax.text(i,v+0.005,f'{v:.2f}',ha='center')
plt.tight_layout(); plt.savefig(os.path.join(FIG,'fig2_state_vs_econ.png'),dpi=130); plt.close()

# Fig3: beta convergence scatter
a=last_in_year(2020); b=last_in_year(2025); common=a.index.intersection(b.index)
x=np.log(a.loc[common,'cdr']); y=np.log(b.loc[common,'cdr']/a.loc[common,'cdr'])
fig,ax=plt.subplots(figsize=(6,4))
ax.scatter(x,y,s=12,alpha=.5,color='#3d7a8e')
lr=stats.linregress(x,y); xs=np.linspace(x.min(),x.max(),50)
ax.plot(xs,lr.intercept+lr.slope*xs,color='#b8603e',lw=2)
ax.axhline(0,color='grey',lw=.7,ls='--')
ax.set_xlabel('log CD ratio 2020 (initial)'); ax.set_ylabel('log growth in CD ratio 2020→2025')
ax.set_title(f'Beta-convergence in credit (slope={lr.slope:+.2f}, p={lr.pvalue:.1g})\nlaggards grow faster — yet dispersion still widens')
plt.tight_layout(); plt.savefig(os.path.join(FIG,'fig3_convergence.png'),dpi=130); plt.close()
print('\n figures written to insights/figures/')
