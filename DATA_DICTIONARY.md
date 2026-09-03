# Data dictionary

This dictionary describes FINER's standardized observation contract. It does not retroactively standardize the broad raw/experimental files, whose source-specific headers remain variable.

The machine-readable Meghalaya registry is [`meghalaya-indicator-registry.json`](https://projectfiner.com/data-contracts/meghalaya-indicator-registry.json).

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
| `source_table` | string | Source table/category key. |
| `source_page` | string | Source page reference; blank where unavailable. |
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
