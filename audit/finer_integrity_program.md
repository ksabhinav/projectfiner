# Project FINER — Data Integrity Program
## Full audit and repair plan: per-file, ground-truth verified, units resolved

**Horizon:** ~20 weeks of evenings and weekends
**Objective:** every published table has a known unit, a traceable source, a measured error rate, and cannot silently regress.

---

## 0. Operating principles

1. **Nothing is trusted until verified against source.** Internal consistency is not correctness. A table can pass every structural check and be entirely fabricated by a bad parse.
2. **Unverified ≠ wrong, but unverified ≠ publishable.** Default posture is quarantine, not publish-with-caveat.
3. **Automate verification, reserve humans for adjudication.** ~330 tables at 45 min attended each is 250 hours. That plan fails. The human touches only what automation flags.
4. **Tier by consequence.** A table feeding a published index earns deep verification; an archive table earns a spot check.
5. **Repair only what you can re-verify.** Fixing before the verifier exists means you cannot prove the fix worked.
6. **Every phase ships a durable artifact**, not just a cleaner dataset — a registry, a manifest, a dictionary, a gate. Those are what stop this recurring.

**Definitions**

| Term | Meaning |
|---|---|
| *Table* | One state × one indicator, all quarters (the unit of work) |
| *Cell* | One (table, quarter, district, column) value |
| *Verified* | Cell value matched against the source document by an independent method |
| *Error rate* | Verified-mismatched cells ÷ cells sampled, with a 95% upper bound |
| *Canonical unit* | Rs. lakh (chosen because SLBC granularity rarely goes finer) |
| *Disposition* | publish / publish-degraded / quarantine / deprecate |

---

## 1. Program architecture — the five durable artifacts

Build these first. Everything else writes into them.

### 1.1 `registry.csv` — the spine
One row per table. This tracks work, drives prioritisation, and becomes the public provenance layer.

```
table_id            odisha__acp_msme
state               odisha
indicator           acp_msme
file                data/odisha/acp_district_msme.csv
codepath            A | B | hybrid | unified
quarters_present    7
usable_run          6          # longest contiguous run, single column
fill_pct            100.0
districts_obs       30
districts_expected  30
unit_declared       crore      # from source caption
unit_source         caption | inferred | external_anchor | unknown
unit_confidence     high | medium | low
source_doc          sources/odisha/slbc_2025Q3.pdf
source_page         47
source_sha256       ...
tier                A | B | C
verify_n            60
verify_errors       1
error_rate_ub95     6.1%
last_verified       2026-08-14
disposition         publish | publish-degraded | quarantine | deprecate
owner_notes         free text
```

### 1.2 `units.yaml` — the unit manifest
Per table, per column. Resolution is *not* guesswork; see §4.

```yaml
odisha__acp_msme:
  default_unit: crore
  evidence: "caption p47: '(Amount in Rs. Crore)'"
  confidence: high
  columns:
    total_msme_t:   {unit: crore, kind: money}
    total_msme_a:   {unit: crore, kind: money}
    total_msme_pct: {unit: percent, kind: ratio}
    micro_no:       {unit: count,  kind: count}
```

### 1.3 `concepts.yaml` — the definitional crosswalk
Maps every vintage-specific column in every state onto a canonical concept. This is what makes cross-state and cross-quarter work legitimate.

```yaml
crop_loan_target:
  canonical_unit: lakh
  definition: "Annual ACP target, crop loan sub-head, district level"
  aliases:
    kerala: ["TARGET", "AG\nTARGET", "Target"]
    odisha: ["crop_loan_t"]
  caveats:
    kerala: "FY23 onward includes KCC-linked term loans; not comparable pre-FY23"
```

The `caveats` field matters more than the aliases. Two states can report "MSME outstanding" and mean different things; a unit conversion does not fix that.

### 1.4 `verification_log.jsonl` — the evidence trail
One record per sampled cell. Append-only. This is what lets you claim an error rate and re-run the claim later.

```json
{"table_id":"odisha__acp_msme","quarter":"March 2025","district":"Angul",
 "column":"total_msme_t","published":2406.87,"source_value":2406.87,
 "method":"dual_extract","match":true,"checked_at":"2026-08-14",
 "source_doc":"...","source_page":47}
```

### 1.5 `sources/` — the archived corpus
Every SLBC PDF, downloaded, SHA-256 hashed, never re-fetched live. **Do this early.** SLBC sites rotate and delete; link rot mid-programme would end the verification effort.

---

## 2. Phase 0 — Freeze and inventory (Weeks 1–2)

**Goal:** know the true size of the problem and stop the bleeding.

1. **Quarantine posture on the live site.** Disable cross-state comparison entirely (units are unresolved — §4). Mark every table `unverified` in the UI. This is not a caveat banner; it is a functional restriction that lifts per-table as verification lands.
2. **Run `finer_audit_tool.py` repo-wide.** Produces the first complete integrity/usefulness/arrangement scores across all ~330 tables.
3. **Generate `registry.csv`** from that run — every table, every structural metric, tier and disposition blank.
4. **Assign tiers:**
   - **Tier A** (~40 tables): feeds a published index, map, or Agency Cost post. Deep verification.
   - **Tier B** (~120): published but standalone. Moderate.
   - **Tier C** (rest): archive. Spot check only.
5. **Immediate deprecations.** Tables with zero data (`kerala_minority_credit`) or single stale quarters (`nagaland_crop_insurance`, March 2019) — deprecate now rather than carrying them through the whole programme.

**Exit:** registry populated, tiers assigned, site restricted, deprecations done.

---

## 3. Phase 1 — Source archive and provenance (Weeks 2–4)

**Goal:** every table can point at the document, page and table it came from.

1. **Harvest and hash** every SLBC PDF referenced by any extractor. Store under `sources/{state}/{yyyyQq}.pdf` with a manifest of SHA-256, retrieval date, origin URL.
2. **Backfill provenance** into the registry: for each table, the doc, page number and table index on that page. Where the extractor did not record it, recover by searching the archived PDF for the table's district column.
3. **Flag orphans** — tables with no locatable source. These cannot be verified and must be quarantined or deprecated; there is no third option.
4. **Add provenance to the extraction contract**: from now on, no table is written without `source_doc`, `source_page`, `source_sha256`.

**Exit:** ≥95% of Tier A/B tables have a resolvable source; orphans quarantined.

**Watch for:** this phase reliably uncovers tables whose source no longer exists online. Budget an extra week; harvesting is slow and rate-limited.

---

## 4. Phase 2 — Units (Weeks 4–7)

**Highest severity work in the programme.** Undeclared units silently corrupt every cross-state artifact by ~100×, and pass every structural check.

**Three-tier resolution, in order of authority:**

1. **Caption extraction (authoritative).** SLBC tables almost always state the unit in the caption or header band: `(Amount in Rs. Crore)`, `(Rs. in lakh)`, `(No. in actuals)`. Regex the text block above each table's bounding box in the archived PDF. This resolves the large majority automatically and gives `confidence: high`.
2. **External anchoring (independent check).** For deposit/credit columns, cross-check district totals against **RBI BSR district-wise deposits and credit** (published quarterly on DBIE) and NABARD state focus papers. This is the only genuinely *external* ground truth in the programme — use it wherever a comparable series exists. A published district deposit figure that matches RBI within a few percent confirms both the unit and the value.
3. **Magnitude plausibility (last resort).** Compare per-district medians against a known-unit peer state of similar economic size. Yields `confidence: low` — flag for manual confirmation, never publish on this basis alone.

**Then:**
4. **Populate `units.yaml`** per column, distinguishing `money` / `count` / `percent` / `ratio`. Percent and count columns must be explicitly typed so normalisation never touches them.
5. **Normalise to canonical.** Store *both* `value_raw` (as published, with its native unit) and `value_lakh` (canonical). Never overwrite the raw value — it is your audit trail against the source.
6. **Re-enable cross-state comparison** only for tables where every money column has `confidence: high|medium`.

**Exit:** 100% of Tier A/B money columns have a declared unit; cross-state features re-enabled for the qualifying subset.

---

## 5. Phase 3 — Ground truth verification harness (Weeks 6–11)

**The core of the programme.** Nothing in FINER has ever compared a published number to its source.

### 5.1 Method: dual independent extraction

Manual checking does not scale. Instead, extract each table a second time with a **structurally different parser** (e.g. if production uses `camelot`, verify with `pdfplumber` word-position clustering, or vice versa), then diff cell by cell.

- **Both agree** → auto-verified. Two independent parsers producing the same value is strong evidence.
- **Disagree** → human review queue, adjudicated against the rendered page image.
- **Second parser fails entirely** → fall back to rasterise-and-read for a sampled subset.

**Known limit, state it in the docs:** parser agreement validates *cell values*, not *structure*. Both parsers can misalign the same merged header identically. So dual extraction must be paired with the structural checks (header integrity, row counts, reconciliation) — it does not replace them. The WB APY eaten-row bug would be caught by row-count checks, not by cell diffs.

### 5.2 Sampling and how many cells you actually need

Error rate claims need statistical backing. Using the rule of three (zero observed failures in *n* trials gives a 95% upper bound of 3/n):

| Cells sampled | 95% upper bound on error rate if 0 errors found |
|---|---|
| 20 | 15% |
| 30 | 10% |
| **60** | **5%** |
| 100 | 3% |
| 300 | 1% |

**Therefore:** Tier A = 60 cells minimum (supports a "<5% error" claim). Tier B = 30. Tier C = 10 spot check. Note that dual extraction makes these cheap — the sample is only the *adjudication* budget; the diff itself runs over all cells.

**Stratify the sample, don't randomise flat.** Deliberately over-sample where parsers fail:
- First and last district row (boundary/header-bleed errors)
- Total rows (catches the reconciliation defects)
- Highest-magnitude cells (worst downstream impact)
- Cells adjacent to merged headers
- One cell per quarter (catches format drift mid-series)
- Remainder random

### 5.3 Output
Every sampled cell appends to `verification_log.jsonl`. Registry gets `verify_n`, `verify_errors`, `error_rate_ub95`, `last_verified`.

**Exit:** all Tier A tables verified; Tier B in progress; per-table error rates published.

---

## 6. Phase 4 — Codepath unification and re-extraction (Weeks 10–15)

Now that repairs can be *proved*, fix the source of the defects.

1. **Collapse Path A and Path B into one extractor.** Neither is correct: A keeps raw PDF headers (`% Ach.`, `AG\nTARGET`, blank names, redundant `District`), B normalises headers but drops `fy` and degrades `as_on_date` to a slug.
2. **Header contract**, enforced at emit time:
   - unique names (`disambiguate.py` — pairs each repeated `a`/`pct`/`amt` with its parent)
   - snake_case, no newlines, no blanks, no embedded values
   - no orphan sub-columns
3. **Header/data boundary guard.** The WB APY bug: a candidate header row consisting mostly of numeric cells is data, not header. Reject and re-detect. Corroborate with row-count stability across quarters.
4. **Positional row loading.** Read with `csv.reader`, not `DictReader` — the Odisha/Bihar/Jharkhand collapse happens the instant a raw-headed row becomes a dict.
5. **Key contract:** ISO `as_on_date`, populated `fy`, single `district` column, stable district naming.
6. **Re-extract in tier order**, verifying each batch before moving on:
   - Bihar (~82k recoverable cells), Jharkhand (~58k), Odisha (~20k) — duplicate-header collapse
   - WB APY (June 2024, North + South 24 Parganas — destroyed, needs genuine re-parse)
   - Kerala crop loan (four header generations, newline fragmentation)

**Exit:** one codepath; all Tier A/B re-extracted and re-verified; recovered cells confirmed present.

---

## 7. Phase 5 — Harmonisation (Weeks 14–18)

Strictly speaking this is usefulness work, but it belongs here because harmonising unverified data would mean redoing it.

1. **Build `concepts.yaml`** — map every vintage column onto a canonical concept, with per-state caveats where definitions genuinely differ.
2. **Vintage becomes a value, not a column name.** `TARGET` / `Target` / `AG\nTARGET` all become `crop_loan_target` with the vintage recorded in a column.
3. **Regenerate** `_complete.json`, `_fi_timeseries.*`, `_fi_slim.json` from harmonised, unit-normalised, verified inputs.
4. **Expect fill rates to jump** from ~30–60% to near 100%, and 8 no-trend tables to become real series.

**Exit:** trends computable on all Tier A tables; concept dictionary covers every published column.

---

## 8. Phase 6 — The gate and republication (Weeks 17–20)

Without this, everything above decays by next quarter.

1. **Pre-publish CI gate.** No artifact ships unless: unit declared, source resolvable, structural checks pass, tier-appropriate verification current (< 2 quarters old).
2. **Harden the validator** — fix the two false positives found in this audit:
   - transient vs monotone district absence (present→gone→present is a bug; absent→present is real district creation, e.g. Malerkotla 2021, Maihar/Mauganj/Pandhurna 2023-24)
   - vintage labels vs absorbed values (`atm_mar_20` is legitimate; require a corroborating row-count drop before flagging `HEADER_ATE_ROW`)
3. **Golden fixtures** per state — a frozen input/expected-output pair that fails loudly on regression.
4. **Publish provenance to users.** Per-table badge: unit, usable run, fill, error rate, source document, last verified. This is the visible payoff of the whole programme and the thing that distinguishes FINER from a scraped CSV dump.
5. **Lift quarantine** table by table as each passes.

---

## 9. The per-file loop

Every table passes through this. Steps 3–6 are automated; 7 is where your time goes.

```
1  TRIAGE      registry row exists; tier assigned
2  SOURCE      locate doc + page; hash; record provenance
3  RE-EXTRACT  unified codepath; unique headers; ISO dates; fy populated
4  UNIT        caption → external anchor → magnitude; write units.yaml
5  STRUCTURE   dup headers, transient gaps, dup keys, reconciliation, null cols
6  VERIFY      dual extract, diff all cells, sample per tier
7  ADJUDICATE  human resolves disagreements against page image   ← the real cost
8  HARMONISE   map columns to concepts.yaml; vintage → value
9  GATE        all checks pass?
10 DISPOSE     publish / publish-degraded / quarantine / deprecate
```

**Disposition rules**
- **publish** — verified at tier threshold, unit high/medium confidence, gate green
- **publish-degraded** — verified, unit known, but sparse or short run; visible warning, excluded from indices
- **quarantine** — unverifiable, no source, or error rate above threshold; retained, not served
- **deprecate** — no data, or stale beyond usefulness; removed with a tombstone explaining why

---

## 10. Throughput and sequencing

~330 tables. Batch **by state**, not by phase — a state's tables share a source document, a caption convention and a parser quirk, so per-table cost drops sharply after the first one in a state.

**Order states by:** Tier A table count first, then known damage (Bihar, Jharkhand, Odisha carry the largest recoverable-cell counts), then everything else.

Realistic pace once the harness exists: **one state per weekend session**, faster for small states (Goa: 2 districts; Nagaland: 16). 22 states ≈ 5–6 months at that rate, which is why Tier A must come first — the top ~8 states should be done by roughly week 14, and the tail can continue past the formal programme.

**Front-load the harness.** Weeks 1–9 build tooling and produce little visible improvement. That is correct and worth expecting, because per-table cost after week 9 is a fraction of what it would be before.

---

## 11. Definition of done

The programme ends — deliberately, on a date — when:

- [ ] Every published table has a declared unit with confidence ≥ medium
- [ ] Every published table resolves to an archived, hashed source document and page
- [ ] Tier A tables: ≥60 cells verified, error rate upper bound < 5%
- [ ] Tier B tables: ≥30 cells verified, upper bound < 10%
- [ ] Zero tables published with unknown units, unresolvable sources, or failing structural checks
- [ ] CI gate live and blocking
- [ ] Golden fixtures for every state
- [ ] Provenance badges visible to users
- [ ] `registry.csv`, `units.yaml`, `concepts.yaml`, `verification_log.jsonl` complete for Tier A/B

**Explicitly out of scope** (name these now, or the programme never ends): Tier C deep verification, pre-2020 backfill, new state onboarding, new indicators, RAG layer rework, site redesign.

---

## 12. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Source PDFs disappear mid-programme | High | Fatal to verification | Harvest and hash **everything in weeks 2–4**, before any other work |
| Dual extraction agrees on a shared structural error | Medium | Silent false confidence | Pair with structural checks; state the limit explicitly in docs |
| Verification adjudication swamps available time | High | Programme stalls | Strict tiering; automate diff; cap Tier C at spot checks |
| Units unresolvable for some states | Medium | Those tables stay quarantined | External anchoring via RBI BSR; accept permanent quarantine over guessing |
| Scope creep into harmonisation/features | High | Never finishes | §11 out-of-scope list; harmonisation gated behind verification |
| Motivation decay (months of invisible work) | High | Abandonment | Ship provenance badges early for finished states — visible progress |
| Definitions differ across states even after unit fix | Medium | Cross-state analysis still invalid | `concepts.yaml` caveats; suppress non-comparable pairs in UI |

---

## 13. What to build first

In order, week 1:

1. `registry.csv` generator from `finer_audit_tool.py` output — everything else keys off it
2. Source harvester and hasher — the time-critical one; sources rot
3. Site quarantine switch — stops publishing wrong numbers today
4. Caption-unit extractor — highest severity defect, and mostly automatable

The verification harness (§5) is the biggest build and the one with no existing scaffolding. It is worth starting only once the registry and source archive exist, because it depends on both.
