# Data dictionary

This dictionary describes FINER's standardized observation contract. It does not retroactively standardize the broad raw/experimental files, whose source-specific headers remain variable.

The machine-readable Meghalaya registry is [`meghalaya-indicator-registry.json`](https://projectfiner.com/data-contracts/meghalaya-indicator-registry.json). The source and extraction-run registry is [`meghalaya-provenance.json`](https://projectfiner.com/data-contracts/meghalaya-provenance.json).

The [`north-east-indicator-inventory.json`](https://projectfiner.com/data-contracts/north-east-indicator-inventory.json) is a separate standardization-readiness artifact for all eight North-East states. Its IDs are scoped to a state and exact raw source field. Units and measure types remain `not-reviewed`, and exact label matches across states are discovery candidates—not claims of semantic equivalence or comparability.

## North-East field review

The inventory uses schema `north-east-field-inventory-v2`. Its companion [`north-east-field-review.csv`](https://projectfiner.com/data-contracts/north-east-field-review.csv) contains one row per state and raw field, with the same coverage counts and source-artifact SHA-256. Filter this file to find fields with no numeric observations, short reporting histories, missing markers or cells requiring inspection.

| Inventory field | Meaning |
|---|---|
| `presentCount`, `periodCount`, `districtLabelCount` | Raw key presence, including blank and null cells. These legacy counts do not measure numeric coverage. District labels have not been harmonised. |
| `absentCount` | Existing state district-period records that lack the field key. This does not mean the field was expected or applicable in those records. |
| `nonblankCount` | Present cells excluding blank strings and nulls; includes missing markers and text. |
| `numericCount`, `zeroCount` | Cells with accepted numeric syntax, and the subset equal to zero. Zero is retained as a reported value. Numeric syntax does not establish analytical validity. |
| `numericPeriods`, `numericPeriodCount`, `numericDistrictLabelCount` | Reporting months (`YYYY-MM`) and distinct raw district labels with at least one numeric cell. This is observed coverage, not a complete geography or time series. |
| `valueClassCounts` | Mutually exclusive classes for every present cell; their sum equals `presentCount`. |
| `reviewExamples` | Up to two cells per non-numeric class, with raw district labels, ISO reporting months and a JSON Pointer into the hashed local source. Ordinary text is located but not copied. Blank/null examples are omitted. |
| `sourceArtifactSha256`, `sourceGitBlobSha` | Exact local input bytes. The builder rejects changes to a pinned source. These hashes do not establish original source-page provenance. |
| `commonNumericPeriods` | Months with numeric cells in every state holding an exact shared field label. Empty if any such state has no numeric cells. Overlap does not establish semantic comparability. |

The CSV uses snake-case column names. `presence_period_count` corresponds to the legacy `periodCount`; `numeric_periods` joins ISO reporting months with `|`. Counts for each non-numeric class have the suffix `_count`.

| Value class | Treatment |
|---|---|
| `numeric` | Plain decimal or correctly grouped Indian/Western thousands, including signed numbers and zero. No amount scale or unit is inferred. |
| `blank`, `null` | Empty/whitespace string and JSON null are kept distinct. Absent field keys are counted separately. |
| `missing-marker` | Exact `_`, `-`, `NA` or `N/A` tokens, case-insensitive. Their meaning remains unresolved; they are not assigned zero, suppression, unavailability or not-applicable status. |
| `percentage-text` | Numeric syntax followed by `%`; retained separately until the measure and unit are reviewed. |
| `spreadsheet-error` | Formula error token such as `#DIV/0!` or `#N/A`. |
| `split-numeric-tokens` | Multiple whitespace-separated numeric tokens in a single cell; no token is selected or joined. |
| `invalid-numeric-grouping` | Commas would need to be removed from an invalid grouping to produce a number. The inventory does not accept that repair. |
| `non-finite` | Text such as `NaN` or `Infinity`. Non-finite JSON numbers are rejected when loading the source. |
| `text`, `unsupported-type` | Other text (which can be legitimate names, dates or notes), or a boolean/container value. Classification alone is not an error finding. |

Use `python3 db/build_north_east_indicator_inventory.py --check` to verify both files. Neither artifact changes the raw observations, creates a comparable dataset, or clears any existing quarantine.

## Observation fields

| Field | Type | Meaning |
|---|---|---|
| `observation_id` | string | Stable hash-based identity for a release, state, district, period and indicator. |
| `release_id` | string | Product release identifier carried by the observation. |
| `schema_version` | string | Version of the observation row contract. |
| `state_lgd_code` | string/integer ID | Canonical Local Government Directory state or UT code. |
| `district_lgd_code` | string/integer ID | Canonical Local Government Directory district code. |
| `district` | string | Canonical district display name. It is descriptive; use the LGD code as identity. |
| `boundary_version` | string | Named source-geography vintage applicable to the row. |
| `boundary_status` | enum | Whether the district is unaffected or reported before/after a known boundary event. |
| `period` | ISO date | Source observation date in `YYYY-MM-DD`. |
| `financial_year` | string | Financial year label supplied by the source artifact. |
| `periodicity` | enum | Reporting frequency; currently `quarterly` in the Meghalaya preview. |
| `indicator_id` | string | Stable FINER concept identifier defined in the indicator registry. |
| `value` | numeric text | Canonically parsed numeric representation; no thousands separators. |
| `unit` | string | Controlled unit from the indicator registry. |
| `source_value` | string | Original extracted cell representation before numeric normalisation. |
| `source_field_label` | string | Exact selected field label in the consolidated source artifact. |
| `source_id` | string | Foreign key to the source entry in the release manifest. |
| `source_artifact` | path | Consolidated local artifact from which the observation was generated. |
| `source_artifact_sha256` | hexadecimal string | SHA-256 of the exact committed source artifact used to build the row. |
| `extraction_run_id` | string | Deterministic extraction-run identifier recorded in the provenance registry. |
| `source_table` | string | Source table/category key. |
| `source_page` | string | Source page reference; blank where unavailable; blank values remain a certification blocker. |
| `missing_reason` | enum/string | Controlled reason for an empty value; blank when a value is present. |
| `quality_status` | enum | `verified`, `suspect` or `quarantined`. |
| `quality_flags` | pipe-delimited codes | Controlled issue/disposition codes. |

## Meghalaya standardized-preview indicators

All definitions below are deliberately tied to the reported source label. They do not assert a broader regulatory or statistical definition where the source documentation is incomplete.

| Indicator ID | Label | Unit | Value type | Source table / field |
|---|---|---|---|---|
| `credit_deposit_ratio` | Overall credit-deposit ratio | percent | decimal | `credit_deposit_ratio` / `Overall CD Ratio` |
| `total_advances_lakh` | Total advances | INR lakh | decimal | `credit_deposit_ratio` / `Total Advances` |
| `total_deposits_lakh` | Total deposits | INR lakh | decimal | `credit_deposit_ratio` / `Total Deposit` |
| `atm_count` | ATMs | count | integer | `branch_network` / `Total ATM` |
| `csp_count` | Customer service points | count | integer | `branch_network` / `Total CSP` |
| `pmjdy_rural_accounts` | PMJDY rural accounts | count | integer | `pmjdy` / `Rural No` |
| `pmjdy_urban_accounts` | PMJDY urban accounts | count | integer | `pmjdy` / `Urban No` |
| `pmjdy_male_accounts` | PMJDY male accounts | count | integer | `pmjdy` / `Male No` |
| `pmjdy_female_accounts` | PMJDY female accounts | count | integer | `pmjdy` / `Female No` |
| `pmjdy_deposits_lakh` | PMJDY deposits held | INR lakh | decimal | `pmjdy` / `Amt Deposits held in the A/c` |
| `aadhaar_seeded_casa` | Aadhaar-seeded CASA | count | integer | `aadhaar_authentication` / `Number of Aadhaar seeded CASA` |
| `aadhaar_authenticated_casa` | Authenticated CASA | count | integer | `aadhaar_authentication` / `Number of Authenticated CASA` |
| `operative_casa` | Operative CASA | count | integer | `aadhaar_authentication` / `Number of operative CASA` |

No PMJDY total is derived by adding rural and urban or male and female fields. The source does not provide an explicit total in the selected table, and the dimensions may not be safely combined without definition review.

## Quality flags

| Flag | Meaning | Current disposition |
|---|---|---|
| `source_document_unlinked` | The consolidated artifact lacks an exact source PDF URL and page for the cell. | Retain as `suspect`; do not certify. |
| `partial_period_coverage` | The table contains fewer districts than the normal source geography for that period. | Retain as `suspect`; do not impute absent districts. |
| `boundary_not_harmonised` | A district is affected by the June 2022 West Khasi Hills/Eastern West Khasi Hills change. | Retain as reported; do not compare across the split without adjustment. |
| `semantic_scope_review_required` | Authenticated CASA exceeds Aadhaar-seeded CASA for the same district-period. | Retain reported values; require source-definition review. |

## Release-manifest fields

Every distribution includes:

- file path and public URL;
- file format, media type and encoding;
- byte size and SHA-256 hash;
- schema version and quality tier;
- source IDs;
- licence and rights-review status;
- row/column integrity metadata where applicable.

Coverage counts describe source artifacts. They are not a certification that every period contains every district or comparable indicator.
