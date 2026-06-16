# Hypothesis log (Phases 2–5)

Every hypothesis tested, including failures. Scripts in `insights/scripts/`.
SURVIVE = passed the 4-part bar + robustness; KILL = failed; WEAK = real but thin.

## Baseline narrative (Phase 2)
Established before hunting: (i) strong S→N/E gradient — TN/TG/AP CD ratio ~170–183 vs
Jharkhand/HP/Arunachal ~40–44; (ii) PMJDY near-universal account access; (iii) CD ratios
rose broadly post-COVID 2020→2025; (iv) BC-led "branchless" expansion (84% of outlets are
BCs). Everything below is a search for departures from this.

| # | Hypothesis | Method (script) | Result | Verdict |
|---|---|---|---|---|
| H1 | CD ratio rises with district wealth (rich districts absorb more credit) | Spearman CDR×RWI, ×nightlights, wealth quintiles (`a1`) | rho=+0.10 (RWI), +0.04 (lights, n.s.). Essentially **flat**. Wealth barely predicts credit absorption. | KILL as stated → reframed into H8 |
| H2 | Large-deposit districts are the worst capital exporters (low CD ratio) | CDR × log deposit quintiles (`a1`) | rho=−0.03, n.s. No monotonic capital-flight-by-size gradient. | KILL |
| H3 | National CD-ratio rise hides district deterioration (Simpson) | value-weighted aggregate vs district-median trend (`a1`,`a4`) | Both rose (agg +11pp, median +17pp); only 10–18% of districts fell. No reversal. | KILL |
| H4 | CD ratio shows **beta-convergence** 2020→2025 | regress log-growth on log-initial (`a1`,`a5`) | slope −0.076, p=0.005; robust across windows, winsor, and dropping high-CDR states (−0.14, p<1e-6). | **SURVIVE** (secondary) |
| H5 | …and **sigma-convergence** (dispersion shrinks) | sd(log CDR) endpoints (`a5`) | base sd 0.549→0.562 (DIVERGES); converges only when southern states dropped/2021 start. Ambiguous. | WEAK — beta w/o robust sigma is the honest story |
| H6 | PMJDY **dormancy is a poor-district problem** | zero-balance share × RWI (`a2`,`a3`) | **OPPOSITE**: rho=+0.20 (p=3e-4); Q5-rich 10.1% vs Q1-poor 7.1%. Survives state FE (rwi coef +3.1, p=0.005), leave-one-state-out (+0.08…+0.27), 11/13 states positive. | **SURVIVE — lead finding** |
| H7 | Dormancy mechanism = pre-existing formal banking (duplicate accounts) | zero-bal × branch-per-PMJDY-account (`a3`) | rho=+0.16, p=0.005 — denser prior banking ⇒ more idle PMJDY a/c. Supports "secondary account" channel. | SURVIVE (mechanism) |
| H8 | District credit is **institutional, not economic** | R² horse race: econ vars vs state dummies vs both (`a5`); cross-checked by between/within variance decomp (`a4`) | State R²=0.585 vs economic-structure R²=0.049; econ adds 2.6pp over state. Df-free decomp: 60% between-state / 40% within. | **SURVIVE — co-lead finding** |
| H9 | BC infrastructure is placed where wealth is low | BC-share × RWI (`a2`) | rho=−0.43 (p=2e-26) — strongly pro-poor placement. | SURVIVE (supporting) |
| H10 | …and heavy-BC districts still lend less (infra ≠ credit) | BC-share × CDR (`a2`) | rho=−0.18 (p=7e-6). Outlets without credit outcomes. | SURVIVE (supporting, confounded by wealth/state) |
| H11 | Health insurance (NFHS4→5) is pro-poor convergent | change × wealth quintile (`a2`) | Poor quintiles +14pp vs rich +7pp; pro-poor. BUT **20% of districts regressed** (uniform across wealth). | WEAK/SURVIVE (context finding) |
| H12 | Districts increasingly become net deposit-exporters over time | deposit-growth vs CDR-drop 2020→25 (`a4`) | Only 10% fit; list dominated by tiny NE districts. Noisy. | KILL |
| H13 | Within-state credit inequality dominates between-state | SS decomposition (`a4`) | 40% within / 60% between — between dominates. (Feeds H8, not a standalone reversal.) | KILL as stated |
| H14 | Structural factors predict positive-deviant lenders | OLS residuals of CDR on structural vars (`a3`) | model R²=0.056 — near-zero; "deviants" are just state effects (TN cluster). | KILL → evidence for H8 |

## Multiple-testing note
~14 hypothesis families tested. The two lead findings (H6, H8) have p-values orders of
magnitude below any reasonable Bonferroni/BH threshold (3e-4 and an R² gap of 0.049 vs
0.585) and survive structural robustness checks, so they are not multiple-comparison
artefacts. The weaker results (H4/H5, H9–H11) are reported with explicit caveats and not
over-claimed.

## Phase 4 (SLBC text) — limited
RAG corpus is on R2, not in-repo. Using `ne-meeting-summaries.json`: NE SLBC minutes
repeatedly flag dormant/inoperative accounts as action items (e.g. Aug-2025 directive:
"Banks to submit inoperative accounts and unclaimed deposit data to SLBC by Sept 20,
2025"; another: "dormant zero-balance accounts to be automatically re-activated,
especially PMJDY accounts"). Confirms dormancy is a live committee concern — but the
*gradient* (worse in richer districts) is invisible in the minutes and only emerges from
the linked structured data.
