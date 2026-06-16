"""Analysis 6: NFHS health-insurance trajectory across THREE waves
(NFHS-4 2015-16 -> NFHS-5 2019-21 -> NFHS-6 2023-24).

Ready to run now. If NFHS-6 has not been ingested yet (no nfhs6_pct in
static.json), it prints a clear notice and exits 0 — so it slots straight into
the pipeline once `db/ingest_nfhs6.py` has run.

Questions it answers:
  * Trajectory typology: monotonic gainers vs gained-then-stalled vs reversers.
  * Does the wealth gradient of *change* differ between the two transitions
    (was the 2016->21 pro-poor convergence sustained into 2021->24)?
  * Meghalaya bright-spot re-test on the full three-wave path.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import json
import pandas as pd, numpy as np
from scipy import stats
import finer

ROOT = finer.ROOT
STATIC = os.path.join(ROOT, 'public', 'indicators', 'nfhs_health_insurance', 'static.json')

d = json.load(open(STATIC))['districts']
df = pd.DataFrame(d)
for col in ['nfhs4_pct', 'nfhs5_pct', 'nfhs6_pct']:
    if col not in df.columns:
        df[col] = np.nan
    df[col] = pd.to_numeric(df[col], errors='coerce')

if df['nfhs6_pct'].notna().sum() == 0:
    print('NFHS-6 not yet ingested (no nfhs6_pct in static.json).')
    print('Run db/ingest_nfhs6.py first, then re-run this script. Exiting cleanly.')
    sys.exit(0)

# attach LGD + wealth
df['lgd'] = [finer.resolve_lgd(r.state, r.district) for r in df.itertuples()]
cs = pd.read_csv(os.path.join(os.path.dirname(__file__), '..', 'data', 'cross_section.csv'))
df = df.merge(cs[['lgd', 'rwi_mean']], on='lgd', how='left')

print('#'*70); print('THREE-WAVE NFHS HEALTH-INSURANCE TRAJECTORY')
print(f' national means: NFHS-4 {df.nfhs4_pct.mean():.1f} | NFHS-5 {df.nfhs5_pct.mean():.1f} | NFHS-6 {df.nfhs6_pct.mean():.1f}')
g = df.dropna(subset=['nfhs4_pct', 'nfhs5_pct', 'nfhs6_pct']).copy()
g['d1'] = g.nfhs5_pct - g.nfhs4_pct   # 2016->21
g['d2'] = g.nfhs6_pct - g.nfhs5_pct   # 2021->24
print(f' districts with all three waves: {len(g)}')

def kind(r):
    if r.d1 > 0 and r.d2 > 0: return 'monotonic gain'
    if r.d1 > 0 and r.d2 <= 0: return 'gained then stalled/fell'
    if r.d1 <= 0 and r.d2 > 0: return 'late gainer'
    return 'persistent decline'
g['traj'] = g.apply(kind, axis=1)
print('\n trajectory mix:')
print((g.traj.value_counts(normalize=True)*100).round(0).astype(int).astype(str).add('%').to_string())

print('\n'+'#'*70); print('WEALTH GRADIENT OF CHANGE — did pro-poor convergence persist?')
gg = g.dropna(subset=['rwi_mean']).copy()
gg['wq'] = pd.qcut(gg.rwi_mean, 5, labels=['Q1poor','Q2','Q3','Q4','Q5rich'])
print(' median gain (pp) by wealth quintile:')
print(gg.groupby('wq', observed=True)[['d1','d2']].median().round(1).to_string())
for lbl, col in [('2016->21', 'd1'), ('2021->24', 'd2')]:
    r, p = stats.spearmanr(gg.rwi_mean, gg[col])
    print(f'  Spearman(RWI, {lbl} change) rho={r:+.3f} p={p:.1e}')

print('\n'+'#'*70); print('GAINED-THEN-STALLED leaders (largest 2021->24 reversal after a 2016->21 gain)')
stalled = g[g.traj == 'gained then stalled/fell'].nsmallest(12, 'd2')
print(stalled[['district','state','nfhs4_pct','nfhs5_pct','nfhs6_pct','d1','d2']].to_string(index=False))

print('\n'+'#'*70); print('MEGHALAYA three-wave re-test')
me = g[g.state == 'meghalaya'][['district','nfhs4_pct','nfhs5_pct','nfhs6_pct','d1','d2','traj']]
if len(me):
    print(me.to_string(index=False))
    print(f' ME mean trajectory: {me.nfhs4_pct.mean():.1f} -> {me.nfhs5_pct.mean():.1f} -> {me.nfhs6_pct.mean():.1f}')
else:
    print(' (no Meghalaya districts with all three waves)')
