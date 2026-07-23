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
| `registry.csv` | **Artifact 1.1** — all 837 audited tables seeded: codepath, quarters, usable_run, fill, scores, issue flags. `unit_declared`/`tier`/`verify_n`/`error_rate_ub95`/`disposition` left blank to fill during the program. |
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

## Known auditor notes

- `qk()` buckets any month into its calendar quarter, so it tolerates the ~219
  non-standard period labels (April/Nov/Feb/… in HP & Kerala) instead of
  crashing. Those labels are themselves a minor arrangement finding.
- Hygiene: `public/slbc-data/tamil-nadu/` carries a stray second master file
  (`tamilnadu_complete.json` alongside `tamil-nadu_complete.json`); the site
  loads the hyphenated one. The other inflates the table count by ~33.
