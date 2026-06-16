# DATA_OVERVIEW — Project FINER analytical base (Phase 0)

## What I worked from
The canonical SQLite store (`db/finer.db`) is gitignored and **absent** from a fresh
clone, so all analysis is built from the committed **pre-aggregated indicator panels**
in `public/indicators/<indicator>/<quarter>.json`. These are the same files the live
homepage map consumes, so they are the production-grade, cleaned outputs.

Reproduce the analytical base:
```
python3 insights/scripts/build_master.py
```
Outputs `insights/data/cdr_panel.csv` and `insights/data/cross_section.csv`.

## Join infrastructure (`insights/lib/finer.py`)
Three geo-key conventions coexist:
| source family | state key | district key |
|---|---|---|
| SLBC flows (CDR, PMJDY, KCC, …) | slug (`arunachal-pradesh`) | TitleCase |
| `rbi_banking_outlets` | UPPERCASE | UPPERCASE |
| structural (RWI, VIIRS, elevation, NFHS, crop, PMGSY, NRLM) | full name + `district_lgd` | TitleCase |

`finer.resolve_lgd(state, district)` normalises all three to the **LGD district code**
using `public/district_lgd_codes.json` (765 districts + 109 aliases), with
state-qualified matching so non-unique names (Bilaspur HP/CG, Balrampur UP/CG) resolve
correctly. **Match rates: 91–100%** across every indicator (lowest is RBI outlets at
91%, from post-2022 carved districts in UPPERCASE).

## The two working datasets
**`cdr_panel.csv`** — credit-deposit panel. 10,573 rows, **704 districts × 55 quarters**
(2010-10 → 2026-03). Fields: deposit, advance, CD ratio (derived as advance/deposit×100
where the reported ratio is missing). Thin before 2020 (13–200 districts), thickens to
**300–580 districts 2020–2025** — the usable analytical window.

**`cross_section.csv`** — one row per LGD district (765), latest value of each indicator:
- *Structural / exogenous:* Meta Relative Wealth Index (`rwi_mean`, 637), VIIRS
  nightlights 2012 & 2023 (637), SRTM elevation (637), Census-2011 irrigation %
  (580), NFHS-4 & NFHS-5 health-insurance % (634), PMGSY roads (553).
- *Banking infrastructure:* RBI DBIE outlet counts — total/branch/BC/CSP/rural (691).
- *SLBC flows (latest):* CD ratio (700), PMJDY total/zero-balance/rural/female (481/373),
  KCC cards (409), digital coverage % (51 — too sparse, not used as a primary).

## Indicator catalogue (district × time)
26 indicators. Deepest panels: `credit_deposit_ratio` (55 q), `pmjdy` (37 q),
`kcc` (37 q), `pmmy_mudra` (36 q), `social_security` (33 q), `shg` (32 q),
`digital_transactions` (23 q). Static cross-sections: RBI outlets, capital-markets
access, NRLM SHG, elevation, RWI, crop, PMGSY. Two-wave: NFHS insurance (2016 & 2021).

## Coverage map & hazards (full detail in DATA_QUALITY.md)
- **31 states/UTs** have SLBC district data; latest quarter varies (Mar 2025 → Mar 2026).
- **District splits/renames** are the main hazard; absorbed by the alias layer and LGD codes.
- **CD ratio** carries ~19 impossible values (>400% or <0) and a few thousand-percent
  outliers — filtered to [1, 400] for all analysis.
- **Single-category states** (Goa = branches only; Punjab = priority-sector only; AP/MP/J&K
  = CD-ratio-dominant) mean cross-indicator coverage is uneven; analyses state their n.
- **PhonePe digital** ceilings at Mar 2024 upstream — not used in time-trend work.
- **Phase-4 caveat:** the SLBC RAG text corpus lives on Cloudflare R2, not in the repo.
  Triangulation here uses the one committed text resource
  (`public/slbc-data/ne-meeting-summaries.json`, 141 NE meeting summaries).
