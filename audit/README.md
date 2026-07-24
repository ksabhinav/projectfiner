# FINER Data Integrity Audit

Tooling, results, and program plan for the data-integrity workstream. Everything
here is analysis/scaffolding — it does not touch published data.

## Files

| File | What it is |
|---|---|
| `finer_integrity_program.md` | The ~20-week program plan (phases, artifacts, definition of done). |
| `finer_project_audit.md` | Narrative audit findings (originally written against a 17-file sample). |
| `generate_panels.py` | Rebuilds the site's per-indicator **download surface** for every state × category from `_complete.json`. |
| `finer_audit.py` | The auditor: three independent 0–100 scores per table (integrity / usefulness / arrangement). |
| `disambiguate.py` | The fix for the duplicate-header collapse (pairs each repeated `a`/`pct`/`amt` with its parent column). Not yet wired into extractors. |
| `build_source_catalogue.py` | **Phase 1** — mines portals (indicator-sources.ts), Wayback snapshots (wayback.json), and extractor URLs into `source_catalogue.csv` + `source_coverage.csv` with orphan/rot-risk buckets. No network. |
| `harvest.py` | **Phase 1** — catalogue-driven fetch + SHA-256 + manifest engine (retry/backoff, HTML-stub reject, Wayback truncation detection, `id_/` raw fetch, resumable). Writes PDFs to `sources/` (gitignored) and provenance to `source_manifest.csv`. |
| `test_harvest.py` | Pure-logic tests for the harvester (hashing, stub/truncation detection, CDX parse, filenames). No network. |
| `source_catalogue.csv` | Every located source, one row each (state, kind, url/host, evidence). |
| `source_coverage.csv` | **Toward artifact 1.5** — per-state source rollup + coverage bucket (ok / archive_only / live_only_fragile / ORPHAN). |
| `verify.py` | **Phase 3** — reconciliation (ratio / area-sum / achievement%), stratified sampler, error-rate stats, and the dual-extraction `diff_tables()` core. Writes `reconciliation.csv`, backfills recon columns into `registry.csv`, and emits per-table sample worklists. |
| `triage.py` | Classifies every reconciliation failure into a root cause (header_collapse / parse_misalign / garbage_ratio_field / unit_mismatch / marginal_definitional) with a fix + priority. Writes `triage.csv` + `triage_rows.csv`. |
| `repair_odisha_acp.py` | **Repair** — recovers the collapsed Odisha ACP per-subcategory a/pct from the quarterly CSVs (gated, lossless) and rewrites complete.json / timeseries.json / timeseries.csv. Cut reconciliation failures 540 → 129. |
| `repair_headers.py` | **Generalised repair** — same gated procedure for any state × any dup-header categories (`--cats "*ALLDUPS*"` sweeps all collapsed tables); auto-detects fixed columns; keep-last disambiguation preserves canonical field names. |
| `triage.csv` / `triage_rows.csv` | Per-cause rollup and per-cell classification of the 540 reconciliation failures. |
| `test_verify.py` | Pure-logic tests for the verification harness. No PDFs. |
| `reconciliation.csv` | Per (table, check) internal-consistency results with fail rate, Wilson UB, and example failures. |
| `flag_cd_ratio_issues.py` | **Quarantine register** — classifies the 129 CD-ratio reconciliation failures by root cause/severity/action into `known_issues.csv` and flags `cd_ratio_defects` per table in `registry.csv`. No data changed. |
| `known_issues.csv` | The CD-ratio quarantine register: every failing cell with deposit/advance/reported-vs-raw ratio, cause, severity, disposition, action. |
| `unit_resolver.py` | **Phase 2** — resolves each column's unit by caption → magnitude → doctrine. Writes `units.yaml` + `unit_findings.csv` and backfills unit columns into `registry.csv`. |
| `test_unit_resolver.py` | Tests for the resolver's PDF-independent tiers (caption parsing, kind classifier, magnitude). Run anywhere. |
| `units.yaml` | **Artifact 1.2** — per state: `default_money_scale`, source, confidence, `to_canonical_factor`; per column: `kind` (money/count/percent) + unit. |
| `unit_findings.csv` | Per-state scale verdict, method, anchor median, deposit/branch ratio, and the conflict-vs-lakh flag. |
| `registry.csv` | **Artifact 1.1** — all 837 audited tables seeded: codepath, quarters, usable_run, fill, scores, issue flags. `unit_declared`/`unit_source` filled by `unit_resolver.py`; `tier`/`verify_n`/`error_rate_ub95`/`disposition` blank to fill during the program. |
| `finer_audit_report.json` | Full per-table auditor output. |

## Reproduce the repo-wide run

```bash
python3 audit/generate_panels.py                       # -> audit/panels/*.csv (837 tables)
FINER_NOW=2026,2 python3 audit/finer_audit.py audit/panels --json
# writes finer_audit_report.json in the cwd
```

`audit/panels/` is regenerated output — not committed (see `.gitignore`).

## Headline (837 tables, 31 states)

| Dimension | Mean score |
|---|---|
| Integrity | 94 / 100 |
| Usefulness | 61 / 100 |
| Arrangement | 48 / 100 |

Two caveats that must travel with these numbers:

1. **These are internal-consistency scores, not accuracy.** Nothing here is
   verified against a source SLBC document. `TRANSIENT_GAP` (161 tables),
   `STALE` (147), `PARTIAL_DISTRICTS` (31) are triage queues — a parse bug and a
   genuine SLBC non-report are indistinguishable until Phase 3 (source
   verification) runs.
2. **`DUP_HEADER` reads low (3) because panels are post-collapse.** The
   duplicate-header disease lives upstream in the raw quarterly CSVs
   (~243 state×category combos, ~160k recoverable cells in Bihar/Jharkhand/
   Odisha) and surfaces in the panels as `ORPHAN_COL` (205 tables). Audit the
   quarterly CSVs directly for the cause; audit panels for the consequence.

## Sources (Phase 1)

```bash
python3 audit/build_source_catalogue.py     # -> source_catalogue.csv + source_coverage.csv (no network)
python3 audit/harvest.py --dry-run          # plan the fetch from the catalogue (no network)
python3 audit/harvest.py --states delhi,haryana        # live portals
python3 audit/harvest.py --wayback --states andhra-pradesh   # from Wayback CDX
python3 audit/test_harvest.py               # no network
```

The catalogue locates **113 sources across 31 states** and sorts each state by
harvest posture:

- **live_only_fragile (15)** — working site, ~no archive: delhi, haryana, hp,
  j&k, karnataka, mp, maharashtra, punjab, rajasthan, tamil-nadu, telangana,
  tripura, up, uttarakhand, west-bengal. **Snapshot these first** — the risk
  register's fatal item is source rot, and these have the least backup.
- **archive_only (1)** — andhra-pradesh: live `slbcap.nic.in` is gone but Wayback
  holds 120 snapshots back to 2010. Harvest from Wayback.
- **ok (15)** — live portal + deep archive.

`harvest.py` writes the corpus to `sources/<state>/` (gitignored) and appends
provenance to `audit/source_manifest.csv` (tracked): state, filename, origin_url,
wayback_ts, retrieved_at, **sha256**, bytes, status. It complements — does not
replace — `db/fetch_wayback_pdfs.py`.

> **Network note:** this managed container's egress policy allows only package
> registries — `web.archive.org` and the SLBC hosts return proxy 403. So the bulk
> harvest must run where those hosts are reachable (and where the ~3.8 GB corpus
> fits). The engine handles the denial gracefully (logs, no partial files); its
> pure logic is unit-tested and the dry-run runs against the real catalogue here.

## Units (Phase 2)

```bash
python3 audit/unit_resolver.py                    # magnitude + doctrine tiers (runs now)
python3 audit/unit_resolver.py --sources sources  # + caption tier, once PDFs are harvested
python3 audit/test_unit_resolver.py               # no PDFs needed
```

**Three tiers, in order of authority:** (1) **caption** — regex the unit band the
SLBC PDF prints above each table (`(Amount in Rs. Crore)`); authoritative, needs
`sources/` from the Phase-1 harvester; built + tested but idle until PDFs exist.
(2) **magnitude** — anchor on per-district total deposits; prefers the
size-invariant **deposit/branch ratio** (crore states cluster ~30–65, lakh
states ~2.7k–27k) and falls back to bare deposit magnitude at low confidence.
(3) **doctrine** — canonical is Rs. lakh; used only to flag conflicts.

**Column kind** (money / count / percent) is classified from the header alone at
high confidence — this is what keeps normalisation from ever touching a count or
a percentage.

**Result (31 states, magnitude tier):** 8 states store money in **crore — 100× off
vs the canonical lakh** (west-bengal, bihar, karnataka, tamil-nadu, andhra-pradesh,
chhattisgarh, telangana, uttar-pradesh; 5 high-confidence via ratio, 3 low pending
caption). 19 confirmed lakh. 4 (goa, odisha, punjab, sikkim) have no CD-ratio
deposit anchor and need the caption tier. **Every cross-state map/ranking built on
the 8 crore states is silently wrong by 100× until normalised.** Confidence is
`high` only where the size-invariant ratio applies; `low` means magnitude alone
can't separate a small state in lakh from a large one in crore — confirm via caption.

## Verification (Phase 3)

```bash
python3 audit/verify.py                                  # reconcile all tables
python3 audit/verify.py --sample odisha:acp_district_msme --tier A   # worklist
python3 audit/test_verify.py                             # no PDFs
```

True verification is *dual independent extraction* — read each table a second
time with a structurally different parser (or a VLM) and diff. That needs the
Phase-1 corpus, so `diff_tables()` is the built + tested pluggable core awaiting
the second reading. What runs **now**:

- **Reconciliation** — internal-consistency checks needing no source: `advance/
  deposit == CD ratio`, `rural+semi_urban+urban == total`, `achievement/target
  == pct`. Across **10,174 checkable cells, 540 fail (5.3%)**. Hotspots:
  odisha ACP `achievement_pct` (99% / 97% in agri_allied / ancillary — the
  collapsed a/pct latched onto the wrong target), jharkhand CD ratio (25%),
  delhi (7.7%), uttar-pradesh (6.9%, incl. a 4603% garbage ratio — gotcha #51),
  chhattisgarh (5.8%). Most states reconcile at 0%. (Run `triage.py` to sort
  these by root cause — see below.)
- **Stratified sampler** — the cells a human/second-extractor checks against the
  page image, over-sampling where parsers break (quarter boundaries, total rows,
  highest-magnitude cells, merged-header-adjacent orphans). Tier A/B/C = 60/30/10.
- **Error-rate stats** — Wilson + rule-of-three upper bound, so "0 errors in 60"
  becomes a defensible "<5%".

### Triage of the 540 failures (`triage.py`)

| Root cause | Cells | Tables | Recoverable? | Fix | Priority |
|---|---|---|---|---|---|
| **header_collapse** | 411 | odisha agri_allied, ancillary | yes | disambiguate → re-derive | HIGH |
| **parse_misalign** | 61 | jharkhand, delhi, chhattisgarh, up, kerala CD ratio | needs re-extract | re-extract + source verify | HIGH |
| **marginal_definitional** | 31 | haryana, tripura, delhi, jharkhand, chhattisgarh | accept? | adjudicate vs source | LOW |
| **unit_mismatch** | 20 | chhattisgarh, jharkhand, up, uttarakhand | yes | per-row crore→lakh (Phase 2) | MEDIUM |
| **garbage_ratio_field** | 17 | chhattisgarh, up | partial | derive ratio from adv/dep, sanity-bounded | MEDIUM |

### Repair applied — Odisha ACP (`repair_odisha_acp.py`)

The 411 header_collapse cells are **fixed**. `repair_odisha_acp.py` reads the
quarterly CSVs, disambiguates the duplicate `a`/`pct` headers, and surgically
rewrites the 5 ACP tables in `complete.json` / `timeseries.json` / `timeseries.csv`
— gated so it only proceeds where a naive re-collapse of the CSV reproduces the
current data exactly (proof it adds columns without altering any value).

| Metric | Before | After |
|---|---|---|
| Reconciliation failures (all states) | 540 | **129** |
| Odisha failures | 411 | **0** |
| Reconcilable cells | 10,174 | **12,341** |
| Per-subcategory ACP triplets reconciling | — | **6942 / 6942 (100%)** |

Guarantees verified: non-ACP content deep-equal before/after (0 diffs in
complete.json and every non-ACP CSV cell); 239 rows preserved; slim.json
untouched. The recovered data is not just present but correct — every
subcategory's `a/target*100 == pct` now holds. Note: `complete.json` self-declares
`amount_unit: "Rs. Crore (ACP, advances)…"`, independently confirming the crore
classification from Phase 2.

**Bihar + Jharkhand ACP** (`repair_headers.py`, the generalised tool): same
gated, lossless procedure. Bihar `acp_target_achievement` recovered ~1,332
previously-collapsed cells; Jharkhand's 9 ACP categories (`amt`/`_no`/
`achv_pct_amt` dup pattern) recovered ~20,252 across 133 new columns. Verified
identically: non-ACP tables deep-equal (0 diffs), all rows preserved, gates all
pass, reconciliation unchanged at 129 (these tables use no a/pct check, so the
recovery adds data without adding checks). Remaining dup-header categories in
these states (mudra, stand_up_india, branch_network area-splits, …) are the next
tranche of the same mechanism.

**Full dup-header sweep** (`repair_headers.py <state> --cats "*ALLDUPS*"`): every
remaining collapsed category across Odisha (21), Bihar (86) and Jharkhand (41) —
**~95,000 previously-dropped cells recovered** (odisha ~7.7k, bihar ~40.8k,
jharkhand ~46.7k). This tranche includes homepage-linked categories
(credit_deposit_ratio, branch_network, pmjdy, kcc, shg…), so it uses a
**keep-last** disambiguation: where a *canonical* field is itself duplicated
(e.g. Jharkhand `cd_ratio` repeats across area splits), the last occurrence keeps
its original name — matching the incumbent collapse — and only the earlier,
previously-dropped occurrences are recovered under new names. That preserves
every field the indicator regenerator / reconciliation / frontend look up by
name, so the sweep is purely additive.

Verified: reconciliation **unchanged at 129** (proof the canonical `cd_ratio` and
peers survived — a full-rename variant instead dropped it to 78 by making 51
Jharkhand checks unrunnable, and was reverted); 0 canonical fields lost; 0
untouched-category diffs (only actually-collapsed quarters are rebuilt); all rows
preserved. Example recovery: Jharkhand `cd_ratio` = 36.23 kept, with the
area-split `semi_urban_deposit_cd_ratio` = 28.33 restored alongside.

> **Downstream note:** the recovered columns live in `complete.json` /
> `_fi_timeseries.*` (analysis + downloads). `slim.json` and `indicators/*.json`
> are separately generated and were not regenerated here — they keep working via
> the preserved canonical fields; re-running `db/regenerate_indicator_files_from_states.py`
> would additionally surface any recovered columns that map to an indicator.

**80% (431/540) were recoverable without re-extraction.** The dominant cause was
the header collapse — proven, not guessed: in every Odisha ACP table the
surviving `a`/`pct` reconcile exactly with the *last* `_t` column, so they're the
grand-total pair the collapse kept while dropping the per-subcategory ones. The
same `disambiguate.py` fix recovers them from the quarterly CSVs. Only 61 cells
(parse_misalign) genuinely need re-extraction + the dual-extraction check.

Note: reconciliation and triage totals were reconciled at 540 after fixing a
role-cache bug in `reconcile_state` (it keyed on category name, but a category's
columns vary across quarters, so it missed Tripura/Uttarakhand failures).

### The 129 CD-ratio failures — quarantined, not fixed (`flag_cd_ratio_issues.py`)

These are categorically different from the header collapse. The collapse hid data
that was present (recoverable losslessly). These are **source extraction errors —
the correct value isn't in the artifacts**, so they cannot be responsibly
auto-fixed. Deriving `cd_ratio = adv/dep` fails because the amounts are misparsed
too (e.g. Chhattisgarh Dec 2022 districts report `deposit=16`, `advance=15` — off
by ~100× from the state's crore-scale median). So this step registers, it doesn't repair.

| Cause | Cells | Severity | Disposition |
|---|---|---|---|
| parse_misalign | 60 | HIGH | quarantine → re-extract + dual-verify |
| garbage_row | 15 | HIGH | quarantine → whole-row re-extract |
| unit_mismatch | 20 | MEDIUM | quarantine → source: which side is ×100 off |
| definitional | 34 | LOW | accept/review — likely not a defect |

**95 genuine defects** (need the Phase-1 corpus + Phase-3 dual extraction) concentrated
in jharkhand (36), chhattisgarh (25, mostly the Dec 2022 quarter), uttarakhand (13,
per-row unit), delhi (9), up (10), kerala (2). Flagged as `cd_ratio_defects` per
table in `registry.csv`.

**34 reclassified as definitional, not defects:** small (<50%) consistent CD-ratio
gaps across 5 states. SLBCs compute CD ratio on different advance bases (RIDF /
investment inclusion), so the *reported* figure is likely the official one and our
raw `adv/dep` is the wrong benchmark. Reconciliation was strict by design; triage
corrects the interpretation.

This closes the internal-consistency phase honestly: the header-collapse damage is
recovered, and the residual real defects are the ones that genuinely need ground
truth — which is blocked on running the harvester off-container.

**Caveat that must travel with this:** reconciliation catches *inconsistency*,
not *incorrectness* — a row can reconcile and still be wrong (both amounts scaled
identically), and a rare failure can be a legitimate source quirk. A 99% or 29%
fail rate is systematic extraction error; a 0.6% rate needs source adjudication.
Nothing here is yet checked against a source document — that is dual extraction,
pending the corpus.

## Known auditor notes

- `qk()` buckets any month into its calendar quarter, so it tolerates the ~219
  non-standard period labels (April/Nov/Feb/… in HP & Kerala) instead of
  crashing. Those labels are themselves a minor arrangement finding.
- Hygiene: `public/slbc-data/tamil-nadu/` carries a stray second master file
  (`tamilnadu_complete.json` alongside `tamil-nadu_complete.json`); the site
  loads the hyphenated one. The other inflates the table count by ~33.
