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

## Known auditor notes

- `qk()` buckets any month into its calendar quarter, so it tolerates the ~219
  non-standard period labels (April/Nov/Feb/… in HP & Kerala) instead of
  crashing. Those labels are themselves a minor arrangement finding.
- Hygiene: `public/slbc-data/tamil-nadu/` carries a stray second master file
  (`tamilnadu_complete.json` alongside `tamil-nadu_complete.json`); the site
  loads the hyphenated one. The other inflates the table count by ~33.
