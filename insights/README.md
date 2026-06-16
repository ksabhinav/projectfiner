# insights/ — non-obvious findings hunt

Reproducible analysis hunting for non-obvious financial-inclusion insights in FINER's
district-level panel. Read order: `MEMO.md` (2-page brief) → `insight_cards.md` (ranked
findings) → `hypothesis_log.md` (everything tested, incl. failures) → `DATA_OVERVIEW.md`
/ `DATA_QUALITY.md` (Phase 0/1).

## Reproduce end to end
```bash
pip install pandas numpy scipy statsmodels scikit-learn matplotlib
python3 insights/scripts/build_master.py      # assemble cdr_panel.csv + cross_section.csv
python3 insights/scripts/a1_cdratio.py        # CD-ratio gradient, Simpson, convergence
python3 insights/scripts/a2_access_usage.py   # dormancy, BC effectiveness, NFHS insurance
python3 insights/scripts/a3_robust.py         # dormancy robustness + positive deviants
python3 insights/scripts/a4_variance.py       # within/between variance, net-export dynamics
python3 insights/scripts/a5_horserace.py      # institutional-vs-economic horse race + figures
```
`insights/lib/finer.py` is the loader/LGD-join library (reused by every script).

## Layout
- `lib/finer.py` — robust LGD resolver + indicator loaders (91–100% match across sources)
- `scripts/` — `build_master.py` + `a1`–`a5` analyses
- `data/` — generated CSVs (cdr_panel, cross_section, cdr_residuals)
- `figures/` — fig1 dormancy×wealth · fig2 state-vs-economy R² · fig3 convergence

## Three lead findings
1. **District credit is institutional, not economic** — state explains R²=0.585 vs
   economic structure R²=0.049 (12× ; 60/40 between/within).
2. **Dormancy–wealth reversal** — idle zero-balance Jan Dhan accounts are *more* common in
   richer districts (rho=+0.20, robust to state FE + leave-one-out).
3. **Beta-convergence without sigma-narrowing** — laggard districts catch up, but the
   overall credit-access spread does not shrink.
