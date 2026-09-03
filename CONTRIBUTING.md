# Contributing

Project FINER currently prioritises trust, reproducibility and documentation over new coverage or features.

## Before starting

- Open an issue for a material data correction or architecture change.
- Do not add a state, indicator or analytical claim without a source, definition, unit, geography, period and quality disposition.
- Do not silently repair ambiguous source values.
- Keep raw/source-faithful material distinct from standardized or certified outputs.
- Never describe a distribution as certified unless its declared gates and review have passed.

## Development

Use Node.js 22.12+ and Python 3.12+.

```bash
npm ci
npm test
python3 validate_data.py --waivers .github/validation-waivers --no-report
python3 db/build_meghalaya_standardized.py --check
python3 db/build_release_manifest.py --check
python3 db/validate_release_data.py
npm run build
python3 scripts/validate_built_site.py dist
```

The `--no-report` form checks the reviewed fingerprints without rewriting `DATA_VALIDATION_REPORT.md`.

## Data changes

A data pull request should identify:

- upstream publisher and source document;
- source URL or archive URL, page/table and source date where available;
- affected state, district LGD code, period and indicator;
- original and proposed values;
- whether the change is an upstream revision, extraction correction or interpretation change;
- quality flags added, resolved or retained;
- generated artifacts and manifest hashes changed by the correction.

Builders should be deterministic and idempotent. Generated files must be rebuilt from declared inputs, and unexpected district names, duplicate identities or missing registered fields must fail closed.

## Code changes

- Escape untrusted source/model text before rendering HTML.
- Keep district resolution state-scoped.
- Use release-manifest metadata instead of new hard-coded coverage counts.
- Add regression tests for the concrete failure being fixed.
- Preserve unrelated work and generated source artifacts.

## Pull requests

Keep each remediation slice bounded. Explain user impact, safety boundaries, verification commands and any unresolved limitation. A passing build is necessary but does not establish data validity.

By contributing, you confirm that you have the right to submit your contribution. No contribution changes the repository's current no-licence status unless an authorised maintainer makes an explicit licence decision.
