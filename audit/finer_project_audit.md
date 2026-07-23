# Project FINER — Project-Level Audit
## Integrity · Usefulness · Arrangement

**Scope caveat:** this covers the **17 downloaded files across 8 states** available in this session. FINER spans 22+ states and likely several hundred tables. The auditor (`finer_audit.py`) is built to run repo-wide — run it against the full data directory for complete coverage. Findings below are almost certainly representative, not exhaustive.

---

## 1. Headline: the integrity problem is the small one

| Dimension | Mean score | Verdict |
|---|---|---|
| **Integrity** — are the values correct? | **97 / 100** | Nearly clean |
| **Usefulness** — can anyone analyse this? | **58 / 100** | Badly impaired |
| **Arrangement** — is it machine-readable? | **38 / 100** | Worst dimension |

Three evenings of debugging have gone into integrity, which turns out to be the *healthiest* axis: two files carry real defects (WB APY's destroyed row, Kerala's empty file), and everything else passes. Meanwhile more than half the tables can't support a trend line and almost none declare what their numbers mean.

---

## 2. CRITICAL: monetary units are undeclared and inconsistent across states

**No file in the sample declares a unit anywhere** — not in headers, not in a metadata column, not in a sidecar. And the underlying units are demonstrably *not* the same across states. Median per-district values for comparable money columns:

| State | Column | Median | Implied unit |
|---|---|---|---|
| Madhya Pradesh | `total_deposit` | 570,101 | Rs. **lakh** |
| Punjab | `total_ps_target_amt` | 496,676 | Rs. **lakh** |
| Odisha | `total_msme_t` | 1,991 | Rs. **crore** |
| Nagaland | `Msme Total O/S Amt` | 1,538 | Rs. **crore** |
| West Bengal | `amount` (KCC) | 847 | Rs. **crore** |
| Arunachal Pradesh | `Total Agri Disbursement` | 181 | Rs. **crore** |

A ~300–3,000× magnitude gap between state groups. MP's median district deposit of 570,101 is coherent as Rs. lakh (≈Rs. 5,700 crore/district) and absurd as crore. Odisha's MSME target of 1,991 is coherent as crore and far too small as lakh.

**Why this is the worst finding in the audit:** FINER's stated purpose is *mapping district-level financial inclusion across India*. Every cross-state map, ranking, or composite index built on these columns is silently wrong by a factor of 100 — and wrong in a direction that makes poor states look rich or rich states look poor depending on which unit their SLBC happened to use. Unlike a missing district, this failure is **invisible**: the numbers look plausible, the charts render, nothing errors.

This defect passes every integrity check ever written. It is purely a metadata failure.

**Fix:** a required `unit` field per column (or per table) captured at extraction, plus a normalisation step to a single canonical unit before any cross-state artifact is generated. Until then, cross-state comparisons should be disabled, not merely caveated.

---

## 3. Usefulness

| Issue | Files | What it means |
|---|---|---|
| **NO_UNITS** | 10/16 | Values not interpretable (§2) |
| **NO_TREND** | 8/16 | Longest contiguous run on any single column < 4 quarters |
| **SPARSE** | 5/16 | Fill < 50% — same concept re-columned per vintage |
| **STALE** | 2/16 | Last observation ≥ 2 years old |
| **NO_DATA** | 1/16 | Zero measurements (`kerala_minority_credit`) |
| **PARTIAL_DISTRICTS** | 1/16 | Materially fewer districts than the state has |

**Half the tables cannot show a trend.** That's the single most important usefulness statistic, because a time series is the main thing a district-level financial-inclusion platform is *for*. Contiguous-run lengths:

- Goa branch network: **23 quarters** — the only genuinely strong series
- Kerala ACP / crop loan: 17
- MP credit-deposit: 11
- Punjab priority sector: 10
- Odisha MSME: 6
- Arunachal ACP / PMAY: 5
- **Nagaland ×3, WB ×3: 1** — single-quarter snapshots, no series at all

Note the divergence between *quarters present* and *usable run*: Kerala crop loan has 21 quarters but its measures are split across four column generations, so the longest usable run is 17 and the fill rate is 29%. WB financial inclusion has 4 quarters and a run of 1. **Quarters-in-file is not coverage** — this is the metric to put on the site, not row counts.

**Analytically strongest tables:** Goa branch network, MP credit-deposit ratio, Punjab priority sector, Arunachal ACP/PMAY. These four are fit for publication today (modulo units).

**Weakest:** Kerala minority credit (empty), Nagaland crop insurance (one quarter, 2019), Nagaland aadhaar/MSME (2 quarters), WB ×3.

---

## 4. Arrangement — the worst-scoring dimension

| Issue | Files | Detail |
|---|---|---|
| **REDUNDANT_COL** | 10/16 | `District` byte-identical to `district`, 100% of rows |
| **HEADER_STYLE** | 10/16 | Non-snake_case headers (`% Ach.`, `Msme Total O/S Amt`, `Crop Loan`) |
| **ORPHAN_COL** | 6/16 | Sub-columns stripped of parent (`a`, `pct`, `amount`, `atm`, `mar_21`) |
| **DATE_FORMAT** | 5/16 | `as_on_date` is a slug (`december_2023`), not parseable |
| **FY_NULL** | 5/16 | `fy` present but 100% empty |
| **NULL_COL** | 4/16 | All-null columns shipped |
| **BLANK_HEADER** | 3/16 | Unnamed column `''` (all Kerala files) |
| **HEADER_NEWLINE** | 1/16 | `AG\nTARGET`, `RICULTURE)\nACHIEVEMENT` |

**Root cause remains the two-codepath split** (10 files Path A / 5 Path B / 1 hybrid). Every arrangement defect maps to one path or the other:

- Path A keeps raw PDF headers → `HEADER_STYLE`, `HEADER_NEWLINE`, `BLANK_HEADER`, `REDUNDANT_COL`
- Path B normalises headers but drops metadata → `DATE_FORMAT`, `FY_NULL`

Neither path is right. Unifying them fixes ~80% of the arrangement findings in one change.

**Format posture:** the files are *nearly* tidy-long on `(quarter, district)` — good choice, keep it — but wide on measures with vintage-specific column names, which is what produces the sparsity. The fix is to keep the long key and make measures canonical, storing vintage as a value rather than encoding it in column names.

---

## 5. Revised priority

The earlier roadmap sequenced on integrity. The scores say re-order:

1. **Units** (§2) — highest severity, silently corrupts the platform's core cross-state function, cheapest to fix. Disable cross-state comparison until done.
2. **Harmonisation** — converts 8 no-trend tables into usable series; no data at risk. This is the biggest jump in what FINER can *show*.
3. **Codepath unification** — fixes ~80% of arrangement defects at source and stops recurrence.
4. **Validator as pre-publish gate** — none of the above stays fixed without it.
5. **Integrity repairs** — WB APY re-extract, Kerala minority credit, Odisha `a`/`pct` collapse. Real, but 2 files and a recoverable-cell problem.
6. **Coverage/provenance surfacing** — publish per-table usable-run, fill, unit and last-refreshed.

---

## 6. What this audit could not check

Honest limits, all requiring the repo or source documents:

- **Accuracy against source.** Nothing here verifies a number matches the SLBC PDF. Integrity checks are internal-consistency only. This is the largest unaudited risk.
- **The other ~14 states**, including Bihar and Jharkhand — known from earlier work to carry the duplicate-header collapse at larger scale than Odisha.
- **Whether coverage gaps are extractor misses or genuine SLBC non-publication.** Only the source archive can settle this.
- **The RAG layer and derived indices** built on top of these tables — any composite index inherits the unit defect.
- **Definitional comparability.** Even with units fixed, "MSME outstanding" in Nagaland and Odisha may not be the same measure. Cross-state work needs a definitional crosswalk, not just a unit conversion.
