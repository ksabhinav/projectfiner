# Changelog

Material trust-layer, public-contract and data corrections are recorded here. This is not a complete history of every extraction or interface change; consult Git history for that detail.

## Unreleased

- Removed the vulnerable browser-side `xlsx` package and retired generated Excel downloads; CSV remains the canonical download format.
- Published the immutable `meghalaya-standardized-preview-v1` release candidate with checksums and machine-enforced certification blockers.
- Added canonical release and district discovery pages, and moved experimental Analysis and Ask tools behind the secondary navigation.

## 3 September 2026 — trust-layer remediation

- Added a deterministic, non-certified Meghalaya standardized preview with 3,494 observations across 13 direct indicators ([#56](https://github.com/ksabhinav/projectfiner/pull/56)).
- Replaced aggregate critical baselines with 29,059 exact, expiring issue fingerprints ([#55](https://github.com/ksabhinav/projectfiner/pull/55)).
- Added structural release validation and repaired malformed Karnataka public CSV rows ([#54](https://github.com/ksabhinav/projectfiner/pull/54)).
- Added the content-addressed release manifest, explicit quality tiers and source-by-source rights status ([#53](https://github.com/ksabhinav/projectfiner/pull/53)).
- Canonicalised district pages by LGD identity and removed alias pages from the sitemap ([#52](https://github.com/ksabhinav/projectfiner/pull/52)).
- Hardened public rendering and prohibited cross-state district fallback ([#51](https://github.com/ksabhinav/projectfiner/pull/51)).

The release remains a research preview. These changes improve safety and traceability but do not certify the broad raw collection.
