# DATA_QUALITY — profiling & integrity (Phase 1)

Profiling scripts: `insights/scripts/build_master.py` (assembly) and the per-analysis
scripts, which each print their own n and filters. The project also ships
`validate_data.py` (7 validators) which I treated as the upstream cleaning gate.

## CD-ratio panel
- 10,573 district-quarters; CD ratio: median 68, mean 82 (right-skewed).
- **Impossible / artefact values:** 19 rows with CD ratio >400% or <0 (max 4,603 — a
  unit/column-shift artefact). **99 null** CD ratios. → All analysis clips to **[1, 400]**.
- **Coverage ramp:** <250 districts/yr before 2020; 301 (2020) → 580 (2024). Any
  trend/convergence work is restricted to districts present at both endpoints (balanced
  subset, n≈245–276 for 2020→2025) to avoid composition artefacts.
- **High-CD-ratio states are real, not errors:** Tamil Nadu (mean 170), Telangana (183),
  AP (172) genuinely lend >150% of local deposits (microfinance/PSL hubs). Verified
  against `public/findings.json` ("Barmer 340%", "Arunachal lowest"). Robustness checks
  drop these states to confirm findings don't hinge on them.

## Cross-section completeness (765 districts)
| field | non-null | note |
|---|---|---|
| rwi_mean / nl_2023 / elev_mean | 637 | structural backbone, Census-2011 district frame |
| nfhs4_ins / nfhs5_ins | 634 | two waves, enables change analysis |
| rbi_total | 691 | 91% match; UPPERCASE + post-2022 carves miss |
| cdr_latest | 700 | |
| pmjdy_total / pmjdy_zerobal | 481 / 373 | dormancy denominator |
| digi_cov_pct | 51 | **too sparse — excluded from primary analysis** |

## Integrity checks performed
1. **Zero-balance share sanity:** PMJDY zero-balance/total clipped to (0.1, 80]%. Exact-0
   values treated as missing (likely non-reported, not genuinely zero dormancy). Median
   surviving value 7.8% — consistent with the curated "Mizoram 1-in-4" outlier fact.
2. **Round-number / frozen-series scan:** the convergence balanced subset was checked for
   copy-forward CD ratios across endpoints; none detected in the analysis subset.
3. **Split/rename safety:** all trend work is on LGD-stable districts present at both
   endpoints, so a 2022/2023 carve cannot masquerade as a "new low/high" observation.
4. **Outlier leverage:** every headline result re-run with the most extreme districts /
   states removed and with 2/98 winsorising (see `hypothesis_log.md`).

## Net effect on findings
- The **dormancy–wealth** result excludes exact-zero and >80% zero-balance shares, uses
  state fixed effects, and survives leave-one-state-out → not a cleaning artefact.
- The **institutional-vs-economic** result uses df-free between/within variance
  decomposition as a cross-check on the R² horse race, so it is not a
  degrees-of-freedom illusion.
- **Cleaned, analysis-ready data** is the two CSVs in `insights/data/`; every filter is
  applied in-script and re-runnable.
