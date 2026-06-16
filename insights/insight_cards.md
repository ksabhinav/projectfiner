# Insight cards — ranked non-obvious findings

Three findings cleared the four-part bar (surprise · narrative tension · data-dependence ·
robustness). Two are bulletproof leads; one is a solid secondary. Everything that failed is
in `hypothesis_log.md`.

---

## #1 — District credit is decided by **administration, not economics**

**Headline.** How much banks lend in an Indian district is governed far more by *which
state's banking administration it sits under* than by anything measurable about the
district's own economy — wealth, brightness, terrain, irrigation, or banking density.

**What the data shows.** Regressing latest district CD ratio (n=483) on the district's
full economic-structural profile — Meta Relative Wealth Index, VIIRS nightlights, SRTM
elevation, Census irrigation %, and RBI outlet count — yields **R² = 0.049**. Replace all
of that with *state dummies alone* and **R² = 0.585**; adding the economic variables on top
lifts it by just **2.6 percentage points** (to 0.611). A degrees-of-freedom-free check —
between/within variance decomposition of 632 districts in 2024–25 — agrees: **60% of
district CD-ratio variation is between states, only 40% within.** Concretely, median CD
ratio runs 167% (Tamil Nadu), 187% (Telangana), 171% (AP) versus 33% (Himachal), 40%
(Jharkhand), 44% (Arunachal) — and a district's position is predicted overwhelmingly by
that state label, not by how rich or economically active the district itself is.

**Why it is non-obvious.** The working model of financial inclusion is economic: develop a
district's economy and credit will follow. The data says the single strongest predictor of
local credit is an administrative boundary. Two districts with near-identical satellite
wealth and nightlights can differ by 100+ points of CD ratio purely by being on opposite
sides of a state line. It also kills the intuitive "positive-deviant" hunt: a structural
model of CD ratio has essentially no explanatory power (R²=0.056), so apparent over- and
under-performers are just state effects in disguise.

**Why it needs good data.** Invisible at state level (where you only see the state means)
and invisible in any single RBI table. It requires district granularity *linked* to
exogenous satellite/census measures of the local economy (RWI, VIIRS, SRTM, Census VD) so
that "economic fundamentals" can be held up against "administration" in the same horse race
— exactly FINER's cross-source linkage.

**Confidence.** High. The R² gap (0.049 vs 0.585) is enormous and corroborated by the
df-free decomposition. *Caveats:* CD ratio is one (important) credit metric; state dummies
absorb genuine economy-of-scale and sectoral differences that satellites measure
imperfectly, so "administration" is shorthand for *everything that travels with the state*
— lead-bank culture, SLBC targets, PSL enforcement, state microfinance/SHG ecosystems — not
proof that the boundary itself is causal.

**So what.** Financial-inclusion policy is organised around *states and districts as units
of need*; this says the *state banking administration* is the unit of **causation** for
credit flow. A lagging district may be lagging because of how its state's lead bank and SLBC
operate, not because of its own economy — so the lever is institutional reform, not (only)
local economic development. **Follow-up:** do districts that switched states or lead-bank
convenors show a CD-ratio break at the switch? That would turn this correlation into an
identification.

**Reproduce.** `python3 insights/scripts/a5_horserace.py` (horse race + Fig 2);
`a4_variance.py` (between/within). Figure: `insights/figures/fig2_state_vs_econ.png`.

---

## #2 — The **dormancy–wealth reversal**: idle Jan Dhan accounts cluster in *richer* districts

**Headline.** Dormant (zero-balance) PMJDY accounts are proportionally **more** common in
wealthier districts, not poorer ones — the opposite of the "dormancy is a problem of the
poor and unbanked" assumption.

**What the data shows.** Across 317 districts in 14 states, the PMJDY zero-balance share
rises monotonically with district wealth: **7.1% in the poorest RWI quintile → 10.1% in the
richest** (Spearman rho = +0.20, p = 3×10⁻⁴). It holds *within* states (11 of 13 states with
n≥8 have positive rho; strongest in Uttar Pradesh +0.48 and Bihar +0.42), survives state
fixed effects (RWI coefficient +3.1, t=2.8, p=0.005) and leave-one-state-out (rho stays
+0.08…+0.27, never flips). Mechanism evidence: districts with more *pre-existing* formal
banking (bank branches per Jan Dhan account) have higher dormancy (rho=+0.16, p=0.005) —
consistent with PMJDY accounts in better-banked, richer places being **secondary/duplicate**
accounts opened for scheme access and then left idle, while in poorer districts the Jan Dhan
account is the household's primary, actively-used account.

**Why it is non-obvious.** It inverts the headline dormancy narrative. The project's own
curated facts note dormancy as a *poor-NE* phenomenon ("1-in-4 Mizoram accounts never used");
the gradient across all districts runs the other way once you control for state. It reframes
account dormancy from a *failure of inclusion* (poor people with unused accounts) to a
*by-product of over-inclusion* (already-banked people accumulating redundant accounts).

**Why it needs good data.** Needs district-level zero-balance counts *joined* to an
independent wealth measure (Meta RWI) and to pre-existing branch density — three sources, one
district key. A state-level or national PMJDY dormancy figure shows none of this; the
reversal only appears district-by-district within states.

**Confidence.** High for the pattern, medium for the mechanism. *Caveats:* zero-balance
share is a snapshot and partly reflects reporting practice; the duplicate-account channel is
strongly suggested, not proven (no account-linkage data); coverage is 14 states.

**So what.** Re-activation campaigns (which SLBC minutes are actively running — see below)
aimed at the poorest blocks may be chasing the wrong target: a large share of idle accounts
sits in *better-off, better-banked* districts as redundant second accounts. **Follow-up:**
are these zero-balance accounts disproportionately the *second+* account of a holder who
already banks elsewhere? Account-seeding/PAN linkage would settle it.

**Triangulation.** NE SLBC minutes repeatedly action dormant accounts — e.g. an Aug-2025
directive, "Banks to submit inoperative accounts and unclaimed deposit data to SLBC," and
another to "automatically re-activate dormant zero-balance accounts, especially PMJDY." The
*concern* is in the room; the *wealth gradient* is not — it only surfaces in the linked data.

**Reproduce.** `python3 insights/scripts/a2_access_usage.py` (a) and `a3_robust.py`.
Figure: `insights/figures/fig1_dormancy_wealth.png`.

---

## #3 — Credit **converges at the bottom but does not narrow overall** (beta without sigma)

**Headline.** Laggard districts are reliably catching up on CD ratio — yet the *spread* of
credit access across districts is not shrinking, and on the raw data is slightly widening.

**What the data shows.** For 274 districts present in both 2020 and 2025, regressing CD-ratio
growth on initial level gives **beta = −0.076 (p=0.005)** — robust convergence, strengthening
to −0.14 (p<10⁻⁶) when the high-CD southern states are excluded and for a 2021 start. But
**sigma** (sd of log CD ratio) moves 0.549 → 0.562 — it *widens* in the base case and only
narrows under some subsamples. So the bottom is catching up while the top keeps pulling away.

**Why it is non-obvious.** "Laggards are converging" is the reassuring headline; people read
beta-convergence as "the gap is closing." Here the two diverge — a textbook Galton-fallacy
trap — so the optimistic read is wrong: mean-reversion at the bottom is being offset by
continued dispersion at the top, and a district in the middle is no more likely to sit in a
tighter pack than five years ago.

**Why it needs good data.** Requires a multi-year district panel of the *same* districts
(LGD-stable, both endpoints) — state-level series would smear it, and a single cross-section
can't show convergence at all.

**Confidence.** Medium. Beta-convergence is robust; the sigma direction is subsample-
sensitive, so the honest claim is "convergence at the bottom, **no** robust narrowing of the
whole distribution," not "divergence."

**So what.** Targeting the lowest-CD districts is working *for those districts*, but it is
not closing the national credit-access gap, because dispersion at the top is unmanaged.
**Follow-up:** is top-end dispersion driven by a handful of microfinance-saturated southern
districts pushing CD ratios past 250%? If so, "access" at the top is a different (over-
lending) phenomenon than "access" at the bottom.

**Reproduce.** `python3 insights/scripts/a1_cdratio.py` and `a5_horserace.py`.
Figure: `insights/figures/fig3_convergence.png`.

---

### Supporting context (did not reach lead-finding status)
- **BC infrastructure is strongly pro-poor placed** (BC-share × RWI rho=−0.43) yet
  heavily-BC districts still show *lower* CD ratios (rho=−0.18) — "outlets without credit."
  Confounded by wealth/state, so reported as context, not a standalone causal claim.
- **NFHS health insurance 2016→2021 is pro-poor convergent** (+14pp poorest vs +7pp richest)
  but **~20% of districts regressed**, roughly evenly across the wealth spectrum.
