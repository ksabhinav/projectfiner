# NFHS-6 (2023-24) ingestion runbook

NFHS-6 was released **29 May 2026** (ref. period 2023-24; 715 districts; all
States/UTs **except Manipur**). National household health-insurance coverage rose
**41% (NFHS-5) → 60.2% (NFHS-6)**. This adds it as the third wave of FINER's
`nfhs_health_insurance` indicator.

`db/ingest_nfhs6.py` is **ready to run** the moment the district-level data is
reachable. It is no-DB (reads a CSV, resolves to LGD via `district_lgd_codes.json`)
and tested end-to-end (749/765 districts matched on a synthetic schema, Manipur
correctly skipped, 0 unmatched).

## Why it isn't already loaded
This container's network egress is **allowlisted**; `zenodo.org`, `nfhsiips.in`,
`data.opencity.in` are not on it, so the source file can't be pulled from here.
Resolve either by adding the host to the egress allowlist, or by dropping the CSV
into the repo manually.

## Source options (district-level)
1. **Zenodo — harmonised NFHS-3→6 district fact-sheet DB** (`zenodo.org/records/20460015`)
   — CSV, cleanest path.
2. **IIPS official fact sheets** (`nfhsiips.in/nfhsuser/nfhs6.php`) — PDF (needs extraction).
3. **data.opencity.in/dataset/nfhs-6-2023-24** — community CKAN mirror.

## Run
```bash
# A) host allowlisted:
python3 db/ingest_nfhs6.py --url "<zenodo CSV url>"
# B) CSV dropped locally:
python3 db/ingest_nfhs6.py --csv path/to/nfhs6_districts.csv --dry-run   # inspect match rate first
python3 db/ingest_nfhs6.py --csv path/to/nfhs6_districts.csv             # write

# if auto-detection misses the columns, pin them (headers are printed):
python3 db/ingest_nfhs6.py --csv f.csv \
  --district-col "District Name" --state-col "State/UT" \
  --value-col "Households with health insurance ... (%)"
# long-format file with a round column:
python3 db/ingest_nfhs6.py --csv f.csv --round-col round --round-value 6
```

## What it does
- writes `public/indicators/nfhs_health_insurance/2024-03.json` (NFHS-6 wave, `pct`);
- merges `nfhs6_pct` into `static.json`;
- **after** data is written, patches the frontend: slider `timePoints`
  → `['2024-03','2021-03','2016-03']` in `src/pages/index.astro`, and the
  citation in `src/lib/indicator-sources.ts`. (Nothing in the live frontend
  references NFHS-6 until real data exists.)
- aborts if <300 districts match (wrong column/schema guard); `--dry-run` writes nothing.

## After ingest
- `python3 db/build_district_pages.py && python3 db/build_district_polygons.py` — refresh district pages.
- `python3 scripts/rag/ingest_indicator_files.py` + rebuild/upload RAG index — so `/ask` knows NFHS-6.
- Spot-check: national mean of `2024-03.json` `pct` should be ≈60 (matches the 60.2% headline).

## Assumptions (verify against the real file)
- 2023-24 encoded as quarter `2024-03` (convention: NFHS-4→2016-03, NFHS-5→2021-03).
- Manipur absent (map falls back to NFHS-5), never written as 0.
- Indicator = "households with any usual member covered under a health
  insurance/financing scheme (%)" — confirm the column matches before trusting values.
- NFHS-6 has 715 districts vs FINER's 637 in this indicator; the LGD alias layer
  absorbs most post-2017 carves, the rest are appended to `static.json` with null
  NFHS-4/5.
