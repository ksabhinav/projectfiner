# Methodology and release policy

## 1. Scope and status

Project FINER assembles district-level financial-inclusion material published by State Level Bankers' Committees (SLBCs), Union Territory Level Bankers' Committees and related public sources. The project converts difficult source formats into searchable pages and downloadable files.

The current site is a **research preview**. Breadth of collection is not evidence that every field is comparable, complete or analysis-ready. The machine-readable [`release-manifest.json`](https://projectfiner.com/release-manifest.json) is authoritative for the files in a release.

## 2. Publication layers

FINER separates publication status from file availability.

### Raw / experimental

Raw files are source-derived extraction outputs. They are retained because they are useful for inspection, recovery and further cleaning. Their field names, units, missing-value tokens and district coverage may vary by state and period. A raw label is a warning, not a claim that the file is unusable.

### Standardized preview

A standardized preview has a governed row shape and stable identifiers, but unresolved evidence or semantic issues remain. The current Meghalaya preview:

- contains 3,494 direct observations for 13 registered indicators;
- maps source district labels to Meghalaya LGD codes;
- preserves the original cell text as `source_value`;
- records geographic vintage and row-level quality flags;
- does not derive totals, back-cast boundaries or silently correct ambiguous values;
- is marked `not-certified`, with all rows `suspect` while source-document and page references are incomplete.

### Certified / Gold

Gold is reserved for a future release that passes all applicable schema, identity, provenance, semantic, reproducibility, rights and review gates. No current FINER distribution is Gold or certified.

## 3. Source acquisition and extraction

SLBC publications differ substantially across states and periods. Existing state-specific scripts and preserved source material are used to extract tables into quarterly structures. The broad raw collection predates the canonical contract and should be treated as an extraction workspace.

The release does not imply that every raw row has been checked against its original PDF. Where the source PDF, archive URL or page is unavailable, the limitation must remain visible rather than being replaced with invented provenance.

For the Meghalaya preview, the common source artifact is `public/slbc-data/meghalaya/meghalaya_complete.json`. The selected values are copied only from fields registered in `public/data-contracts/meghalaya-indicator-registry.json`.

## 4. Observation model

The canonical direction is one row per:

> release × geography × period × indicator

The standardized contract uses stable state and district LGD codes, an ISO period, a canonical indicator ID, a typed value and unit, the original source representation, a source ID and machine-readable quality fields. The complete field dictionary is on the [data dictionary page](https://projectfiner.com/data-dictionary/).

Wide files remain available for convenience but are not the canonical schema. Browser-generated indicator and quarter exports inherit the variability of raw source tables.

## 5. Geography

District names are resolved within their stated state. Cross-state fallback is prohibited. Canonical pages use the LGD registry, while known legacy name variants redirect to a canonical district page.

The map treats period and boundary fallbacks as data status, not as invisible display logic. Its legend reports the composition of the displayed view by source period, counts suspect and unclassified observations, and excludes values inherited from a pre-reorganisation parent district by default. Readers may opt in to those parent proxies; when enabled they are styled and exported as `proxy`, with the parent district recorded. The map export contains the requested period, actual source period, proxy source, row-level quality status, quality flags and boundary vintage for every displayed observation. The current boundary file has no documented as-of date, so the interface and export state its vintage as `undocumented` rather than implying that it matches the selected observation period.

LGD identity does not by itself make observations comparable through a boundary change. The Meghalaya standardized preview records two source-geography vintages around the creation of Eastern West Khasi Hills in June 2022. West Khasi Hills and Eastern West Khasi Hills rows carry `boundary_not_harmonised`. No historical split or combined harmonised series is currently asserted.

## 6. Time and measures

Quarterly observations use the source's `as_on_date`, normalised to ISO `YYYY-MM-DD`. Amounts and counts are treated as reported at that date unless an indicator definition states otherwise. Source labels remain in the indicator registry so that a canonical field can be audited back to the extracted table.

Numeric parsing removes presentation separators for `value` but retains the unmodified source text in `source_value`. Missing or ambiguous values must not be converted to zero. The broader raw collection still contains legacy missing-value tokens; those files remain raw until rebuilt under the canonical contract.

## 7. Quality status and flags

Standardized observations carry a `quality_status` and zero or more controlled `quality_flags`.

- `verified`: the observation has passed the defined checks and evidence review for its tier.
- `suspect`: the value is retained but a provenance, semantic, coverage or comparability issue remains.
- `quarantined`: the observation is excluded from clean/default analytical use but retained for audit.

The Meghalaya preview currently uses:

- `source_document_unlinked` for incomplete PDF/page provenance;
- `partial_period_coverage` for the two one-district PMJDY periods in 2019;
- `boundary_not_harmonised` for districts affected by the 2022 split;
- `semantic_scope_review_required` for 75 district-period groups where authenticated CASA exceeds Aadhaar-seeded CASA under the reported labels.

A flag is a disposition, not proof that the upstream value is wrong.

## 8. Release identity and integrity

`db/build_release_manifest.py` deterministically inventories every public distribution. The release ID is derived from the canonical manifest payload. Each distribution records its path, byte size, SHA-256 hash, encoding, media type, schema version, quality tier, source IDs and rights status.

Broad archive URLs remain mutable when a new release replaces a file. The Meghalaya standardized preview is also published under the immutable version ID `meghalaya-standardized-preview-v1`; its descriptor records exact hashes and certification blockers. A changed snapshot requires a new release ID.

## 9. Validation and waivers

Deployment applies two different controls:

1. `validate_data.py` detects domain and extraction anomalies. Known critical legacy findings are allowed only by exact fingerprint in an expiring waiver ledger. A new critical identity fails even when aggregate counts do not rise.
2. `db/validate_release_data.py` validates declared public distributions, including file existence, path safety, UTF-8 encoding, hashes, CSV structure and JSON parsing. Structural release failures cannot be baselined.

The Meghalaya, release-manifest and versioned-release builders have deterministic `--check` modes. Python and JavaScript contract tests cover canonical geography, safe rendering, release metadata and the standardized preview.

## 10. Reproduction

From a clean checkout with Node.js 22.12+ and Python 3.12+:

```bash
npm ci
python3 db/build_meghalaya_standardized.py --check
python3 db/build_release_manifest.py --check
python3 db/build_versioned_release.py --check
python3 db/validate_release_data.py
npm test
npm run build
```

Run the exact-waiver domain gate separately:

```bash
python3 validate_data.py --waivers .github/validation-waivers
```

The full historical extraction pipeline is not yet reproducible from one command on a fresh machine. Several extractors still require state-specific inputs and review. This limitation is why raw breadth is not called certified.

## 11. Rights, citation and corrections

No blanket data licence is asserted. A public source or download link does not establish permission to reuse or redistribute the material. Consult the [source rights page](https://projectfiner.com/data-rights/) and the upstream publisher.

When citing a distribution, record the FINER release ID, file SHA-256, access date and upstream source. Follow [`CITATION.cff`](https://github.com/ksabhinav/projectfiner/blob/main/CITATION.cff) and the source attribution in the manifest.

Suspected errors are handled under the [correction policy](https://projectfiner.com/corrections/). Changes to published observations require a reason, source evidence where available, validation and a changelog entry.
