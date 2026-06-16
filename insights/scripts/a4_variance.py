"""Analysis 4: within- vs between-state credit inequality, and CD-ratio state structure."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import pandas as pd, numpy as np
from scipy import stats

D = os.path.join(os.path.dirname(__file__), '..', 'data')
p = pd.read_csv(os.path.join(D,'cdr_panel.csv'))
p = p[(p.cdr>=1)&(p.cdr<=400)].copy()
p['year']=p.quarter.str[:4].astype(int)

# latest obs per district in 2024-2025
recent = p[p.year>=2024].sort_values('quarter').groupby('lgd').last().reset_index()
recent = recent[recent.state.notna()]
print('#'*70); print('WITHIN vs BETWEEN STATE inequality of CD ratio (2024-25)')
print(f' n districts={len(recent)} states={recent.state.nunique()}')
grand = recent.cdr.mean()
# variance decomposition (unweighted)
between = recent.groupby('state').cdr.mean()
bn = recent.groupby('state').size()
ss_between = (bn*(between-grand)**2).sum()
ss_within = recent.groupby('state').cdr.apply(lambda s:((s-s.mean())**2).sum()).sum()
ss_total = ((recent.cdr-grand)**2).sum()
print(f' SS_between={ss_between:.0f} ({100*ss_between/ss_total:.0f}%)  SS_within={ss_within:.0f} ({100*ss_within/ss_total:.0f}%)')
print(f' => {100*ss_within/ss_total:.0f}% of district CD-ratio variation is WITHIN states')
# state means/spreads
print('\n state CD ratio: mean and within-state IQR (states n>=10):')
for st,g in recent.groupby('state'):
    if len(g)<10: continue
    print(f'   {st:20s} n={len(g):3d} mean={g.cdr.mean():6.1f} median={g.cdr.median():6.1f} IQR={g.cdr.quantile(.75)-g.cdr.quantile(.25):6.1f} min={g.cdr.min():.0f} max={g.cdr.max():.0f}')

print('\n'+'#'*70); print('NET DEPOSIT EXPORT dynamics 2020->2025 (district-level)')
def last_in_year(yr):
    return p[p.year==yr].sort_values('quarter').groupby('lgd').last()
a=last_in_year(2020); b=last_in_year(2025)
common=a.index.intersection(b.index)
df=pd.DataFrame({'cdr20':a.loc[common,'cdr'],'cdr25':b.loc[common,'cdr'],
                 'dep20':a.loc[common,'deposit'],'dep25':b.loc[common,'deposit'],
                 'adv20':a.loc[common,'advance'],'adv25':b.loc[common,'advance'],
                 'state':b.loc[common,'state'],'district':b.loc[common,'district']})
df=df.dropna()
df['dep_g']=df.dep25/df.dep20-1; df['adv_g']=df.adv25/df.adv20-1
# districts where deposits grew but CD ratio fell (credit didn't keep up) = worsening exporters
worse = df[(df.dep_g>0)&(df.cdr25<df.cdr20)]
print(f' n={len(df)} | districts with deposits UP but CD-ratio DOWN: {len(worse)} ({100*len(worse)/len(df):.0f}%)')
print(' worst worsening net-exporters (largest CDR drop, deposits rising):')
worse2=worse.assign(drop=worse.cdr25-worse.cdr20).nsmallest(10,'drop')
print(worse2[['district','state','cdr20','cdr25','dep_g','adv_g']].round(2).to_string(index=False))
