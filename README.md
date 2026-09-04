# Project FINER

Project FINER (Financial Inclusion in the North East Region) is a public research project that assembles district-level financial-inclusion material from State Level Bankers' Committee publications and related sources.

The project is in a **research-preview** stage. Most public files are source-derived **raw / experimental** artifacts with uneven schemas and unresolved quality issues. The Meghalaya long-format product is a **standardized preview**, not a certified dataset. No FINER distribution is currently labelled Gold or certified.

The authoritative broad inventory is [`public/release-manifest.json`](public/release-manifest.json). Immutable product releases are listed in [`public/releases/index.json`](public/releases/index.json). The current candidate, [`meghalaya-standardized-preview-v1`](public/releases/meghalaya-standardized-preview-v1/release.json), records its exact files, hashes and certification blockers.

## Start here

- [Methodology and release policy](METHODOLOGY.md)
- [Versioned Meghalaya release candidate](https://projectfiner.com/releases/meghalaya-standardized-preview-v1/)
- [Canonical district directory](https://projectfiner.com/districts/)
- [Data dictionary](DATA_DICTIONARY.md)
- [Data rights and reuse](https://projectfiner.com/data-rights/)
- [Correction policy](CORRECTIONS.md)
- [Changelog](CHANGELOG.md)
- [Citation metadata](CITATION.cff)
- [Privacy notice](PRIVACY.md)
- [Security policy](SECURITY.md)
- [Contribution guide](CONTRIBUTING.md)

## Public data tiers

| Tier | Meaning | Current use |
|---|---|---|
| Raw / experimental | Source-derived files that preserve useful extraction output but may contain schema drift, OCR artifacts, missing provenance and non-comparable fields. | Default tier for state and capital-market downloads. |
| Standardized preview | A deterministic long-format contract with canonical identities, units, source values and explicit quality flags. It has not passed the evidence and review gates for certification. | Meghalaya's 13-indicator preview. |
| Certified / Gold | A future tier requiring complete source provenance, reviewed definitions, resolved semantic checks, reproducibility and release sign-off. | No current distribution. |

Public availability is not a grant of reuse rights. Source terms have not been legally reviewed across the release; see the [rights matrix](https://projectfiner.com/data-rights/) and [`LICENSE`](LICENSE).

CSV is the canonical browser-download format. Generated Excel downloads were retired because their browser-side dependency had unresolved high-severity advisories.

## Local development

Requirements:

- Node.js 22.12 or newer
- Python 3.12 or newer

Install and verify:

```bash
npm ci
npm test
python3 validate_data.py --waivers .github/validation-waivers --no-report
python3 db/build_meghalaya_standardized.py --check
python3 db/build_release_manifest.py --check
python3 db/build_versioned_release.py --check
python3 db/validate_release_data.py
npm run build
python3 scripts/validate_built_site.py dist
```

The GitHub Pages workflow runs these unit, data-quality, release and built-site gates on pull requests. It also blocks critical production dependency advisories and produces a dependency SBOM. Deployment runs only after the same quality job succeeds on `main`.

The legacy validation report is generated output. Do not treat its prose summary as the release contract; CI evaluates observation-level critical fingerprints from the expiring waiver ledger without rewriting the report.

## Repository map

| Path | Purpose |
|---|---|
| `public/release-manifest.json` | Content-addressed public release inventory. |
| `public/releases/` | Immutable product snapshots, release descriptors and catalog. |
| `public/slbc-data/` | State-level raw source-derived JSON and wide CSV files. |
| `public/data-contracts/` | Standardized preview artifacts and indicator registries. |
| `public/district_lgd_codes.json` | Canonical LGD geography registry and aliases. |
| `db/` | Release builders, extract/import utilities and structural validators. |
| `src/` | Astro/Svelte public interface. |
| `tests/` | JavaScript and Python contract tests. |
| `.github/validation-waivers/` | Expiring exact fingerprints for known critical legacy findings. |

## Current limitations

- State schemas are not harmonised across the broad raw collection.
- Many observations cannot yet be traced to an exact source document and page.
- District boundary changes are not generally harmonised through time.
- Rights metadata is incomplete and no blanket data licence is asserted.
- Analytical and Ask interfaces may use broader experimental material than the standardized preview.
- Broad archive URLs remain mutable; versioned product files under `public/releases/` are immutable.

Use the release manifest and row-level quality status when deciding whether material is suitable for analysis.

## Corrections and contributions

Report a suspected data error through the [data-correction issue form](https://github.com/ksabhinav/projectfiner/issues/new?template=data-correction.yml). Include the state, district, period, indicator/source label, observed value and source evidence where possible. Security vulnerabilities should be reported privately as described in [`SECURITY.md`](SECURITY.md).

Contribution expectations and required checks are documented in [`CONTRIBUTING.md`](CONTRIBUTING.md).
