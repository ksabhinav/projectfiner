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

## Known auditor notes

- `qk()` buckets any month into its calendar quarter, so it tolerates the ~219
  non-standard period labels (April/Nov/Feb/… in HP & Kerala) instead of
  crashing. Those labels are themselves a minor arrangement finding.
- Hygiene: `public/slbc-data/tamil-nadu/` carries a stray second master file
  (`tamilnadu_complete.json` alongside `tamil-nadu_complete.json`); the site
  loads the hyphenated one. The other inflates the table count by ~33.
