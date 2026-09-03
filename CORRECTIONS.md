# Correction policy

Project FINER welcomes corrections to extracted data, metadata, geography, definitions and public claims. A correction should improve traceability without erasing the source record.

## Report an issue

Use the [data-correction issue form](https://github.com/ksabhinav/projectfiner/issues/new?template=data-correction.yml) or email `mail@projectfiner.com` if public disclosure would expose personal, confidential or security-sensitive information.

Include as much of the following as possible:

- state and district;
- period or source date;
- indicator ID or exact source field label;
- public file/page and current value;
- expected value or problem description;
- upstream document URL, page number and supporting excerpt;
- whether the problem affects one observation or a wider rule.

Do not include personal financial information or credentials.

## Triage

Reports are classified as one or more of:

- source-faithful but semantically unclear;
- extraction or transcription error;
- schema, unit or missingness error;
- geography identity or boundary error;
- provenance or rights-metadata gap;
- public-interface or coverage-claim error;
- not reproducible or outside FINER's scope.

Severity depends on user harm, breadth, whether an incorrect value appears in a default analytical view and whether the problem can contaminate other states or periods.

## Correction rules

1. Preserve the originally extracted representation in Raw or in version history.
2. Do not silently replace ambiguous values. Mark them suspect or quarantine them until evidence supports a correction.
3. Record the source evidence, affected observation identity and reason for every standardized-data change.
4. Regenerate derived files from the corrected source of truth; do not hand-edit downstream artifacts.
5. Run the data, release-integrity, test and build gates before publication.
6. Update the changelog for material corrections and issue a new release identity when a manifest distribution changes.

If the upstream publisher corrects its own data, FINER should distinguish an upstream revision from a FINER extraction correction.

## Publication and notification

Confirmed material corrections are documented in the public [changelog](https://projectfiner.com/changelog/) and linked to the issue or pull request where practical. The public release manifest changes whenever a declared distribution's content, size or hash changes.

FINER does not currently provide immutable version URLs or a formal notification service. Users conducting reproducible work should retain the release manifest and hashes used in their analysis.
