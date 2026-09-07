# Changelog

Material trust-layer, public-contract and data corrections are recorded here. This is not a complete history of every extraction or interface change; consult Git history for that detail.

## Unreleased

- Replaced the PhonePe Pulse history with the upstream-restated January–March 2018 to April–June 2026 series, pinned its source revision and methodology break, and added district registered-merchant coverage.
- Published build identity and release-freshness status in human- and machine-readable forms, with a daily synthetic monitor for core routes, deployment drift, and the stated freshness target.
- Added a searchable, keyboard-operable district data table as a non-visual equivalent to the choropleth, with values, missingness, source periods, proxy disclosure, and direct district focus.
- Rebuilt the live map toolbar popovers with semantic buttons, valid dialog/listbox structure, explicit selection state, arrow/Home/End navigation, and focus return to their trigger controls.
- Added focus trapping and focus restoration to the map search, finding, and district-focus dialogs, replacing click-only dismiss layers and suppressed accessibility warnings with semantic controls.
- Made the live district-ranking filters explicitly labelled, converted sortable table headers to keyboard-operable buttons, and added screen-reader status announcements and table context.
- Added a document-level Content Security Policy and referrer policy to every published HTML page, self-hosted Plotly from the locked dependency tree, and pinned Leaflet CDN assets with integrity hashes.
- Upgraded Astro, the Astro Svelte integration, Svelte and their transitive Vite toolchain beyond known vulnerable releases.
- Removed the vulnerable browser-side `xlsx` package and retired generated Excel downloads; CSV remains the canonical download format.
- Published immutable Meghalaya preview v2 with row-level source-artifact SHA-256 hashes, deterministic extraction-run IDs, an explicit provenance registry, and preserved v1 history; exact PDF/page evidence remains an open certification blocker.
- Added canonical release and district discovery pages, and moved experimental Analysis and Ask tools behind the secondary navigation.

## 3 September 2026 — trust-layer remediation

- Added a deterministic, non-certified Meghalaya standardized preview with 3,494 observations across 13 direct indicators ([#56](https://github.com/ksabhinav/projectfiner/pull/56)).
- Replaced aggregate critical baselines with 29,059 exact, expiring issue fingerprints ([#55](https://github.com/ksabhinav/projectfiner/pull/55)).
- Added structural release validation and repaired malformed Karnataka public CSV rows ([#54](https://github.com/ksabhinav/projectfiner/pull/54)).
- Added the content-addressed release manifest, explicit quality tiers and source-by-source rights status ([#53](https://github.com/ksabhinav/projectfiner/pull/53)).
- Canonicalised district pages by LGD identity and removed alias pages from the sitemap ([#52](https://github.com/ksabhinav/projectfiner/pull/52)).
- Hardened public rendering and prohibited cross-state district fallback ([#51](https://github.com/ksabhinav/projectfiner/pull/51)).

The release remains a research preview. These changes improve safety and traceability but do not certify the broad raw collection.
