# Project FINER — CLAUDE.md

## What This Project Is

**Project FINER** (Financial Inclusion in the North East Region) is a static data platform focused on financial inclusion in India, with emphasis on the North East region. It publishes interactive maps, charts, and downloadable datasets covering banking infrastructure, credit access, government schemes, and capital markets.

- **Hosted on**: GitHub Pages with custom domain at `projectfiner.com`
- **Repo**: `https://github.com/ksabhinav/projectfiner.git`
- **Branch**: `main`
- **Framework**: Astro 6 + Svelte 5 (static site generation)
- **Deployment**: GitHub Actions (`.github/workflows/deploy.yml`) — builds with `npm run build`, deploys to GitHub Pages
- **Base URL**: `/` (set in `astro.config.mjs`, site: `https://projectfiner.com`)

## Dev Server

```json
// .claude/launch.json
{
  "name": "finer",
  "runtimeExecutable": "npm",
  "runtimeArgs": ["run", "dev", "--", "--port", "8090"],
  "port": 8090
}
```

Preview at `http://localhost:8090/`.

## Repository Structure

```
projectfiner/
├── astro.config.mjs                        # Astro config (base: '/', static output, site: projectfiner.com)
├── package.json                            # Dependencies: astro, @astrojs/svelte, svelte, d3, plotly, xlsx
├── .github/workflows/deploy.yml            # GitHub Actions: build + deploy to Pages
│
├── src/
│   ├── layouts/
│   │   ├── BaseLayout.astro                # Base HTML shell (fonts, global CSS, <slot />)
│   │   └── PageLayout.astro                # Extends BaseLayout with Header + Footer
│   │
│   ├── components/
│   │   ├── Header.astro                    # Shared nav bar (Map, FI Indicators, SLBC Data, Downloads, Analysis)
│   │   ├── Footer.astro                    # Simple footer with dynamic year
│   │   ├── MeghalayaDownload.svelte        # SLBC download UI (indicator/quarter tabs, CSV/Excel)
│   │   ├── DownloadManager.svelte          # Capital markets download cards (CDSL/NSDL/MFD)
│   │   └── analysis/
│   │       └── DataExplorer.svelte         # Interactive data explorer (Plotly charts, correlation, CSV upload)
│   │
│   ├── pages/
│   │   ├── index.astro                     # HOMEPAGE — Full-screen Leaflet capital markets map
│   │   ├── fi-indicators/
│   │   │   └── index.astro                 # FI Indicators choropleth map (7 indicators, all 8 NE states)
│   │   ├── slbc-data/
│   │   │   ├── index.astro                 # State listing (Meghalaya active, 7 coming-soon)
│   │   │   └── meghalaya/
│   │   │       └── download.astro          # Meghalaya SLBC download page
│   │   ├── capital-markets/
│   │   │   ├── map.astro                   # Redirects to homepage (map is now the homepage)
│   │   │   └── data-download.astro         # Download hub for capital markets + SLBC data
│   │   └── analysis/
│   │       └── index.astro                 # Data explorer with Plotly scatter/bar/line charts
│   │
│   ├── lib/
│   │   ├── constants.ts                    # COLORS, CAPITAL_MARKETS_SOURCES, FILE_ICON_SVG
│   │   ├── download.ts                     # saveBlob(), rowsToCsv(), downloadCsv(), downloadXlsx()
│   │   └── slbc-categories.ts              # CATEGORY_INFO (48 cats), QUARTER_ORDER/LABELS/FOLDERS
│   │
│   └── styles/
│       └── global.css                      # Design system CSS custom properties + shared classes
│
└── public/                                 # Static assets (served as-is, fetched at runtime)
    ├── DPSCs/
    │   ├── cdsl_dp_centres.json            # 20,612 CDSL DP service centres
    │   └── nsdl_dp_centres.json            # 57,005 NSDL DP service centres
    ├── MFDs/
    │   ├── mfd_individual.json             # 187,254 individual MF distributors
    │   └── mfd_corporate.json              # 10,760 corporate MF distributors
    ├── Maps/                               # GeoJSON: DISTRICT_BOUNDARY, STATE_BOUNDARY, HQs, etc.
    ├── data/
    │   └── district_boundaries.geojson     # District boundaries (808 total, 131 NE) with capital markets counts
    ├── pincode_coords.json                 # Pincode → [lat, lng] lookup
    ├── slbc-data/{state}/                  # All 8 NE states' SLBC data
    │   ├── {state}_complete.json           # Master JSON — all quarters, all indicators
    │   ├── {state}_fi_timeseries.json      # Timeseries JSON (nested: periods → districts)
    │   ├── {state}_fi_timeseries.csv       # Wide-format CSV: all districts × all quarters
    │   ├── quarterly/                      # Folders (YYYY-MM format), CSVs per category
    │   └── raw-csv/                        # Flat CSVs by category
    └── digital-payments/                   # PhonePe Pulse UPI data (FY22–FY24)
```

## Architecture Notes

### Astro + Svelte
- **Astro pages** (`.astro`) handle layout, routing, and static HTML generation
- **Svelte components** (`.svelte`) handle interactive UI (download managers, data explorer)
- Svelte uses **Svelte 5 runes**: `$state`, `$derived`, `$effect`, `onMount`
- **Leaflet map** on homepage is kept as `<script is:inline>` (too imperative for Svelte)
- `define:vars={{ base }}` passes Astro variables to inline scripts via `window.__FINER_BASE`

### Data Fetching
- All data in `public/` is fetched at runtime via `import.meta.env.BASE_URL` + relative path
- XLSX.js is dynamically imported (`import('xlsx')`) to avoid SSR issues
- Plotly.js loaded dynamically in DataExplorer via `import('plotly.js-dist-min')`

### Base URL
- `import.meta.env.BASE_URL` returns `/` (with trailing slash) for the custom domain `projectfiner.com`
- All hrefs in Astro templates use `${base}path` (no extra `/` needed since base has trailing slash)
- Inline scripts access base via `window.__FINER_BASE` set by a `define:vars` script block

## Three Main Data Sections

### 1. Capital Markets Access

Interactive map (homepage) + downloadable data on capital markets infrastructure across India.

**Data sources** (scraped from official websites):
- **CDSL** — Depository Participant service centres (20,612 records)
- **NSDL** — Depository Participant service centres (57,005 records)
- **AMFI** — Mutual Fund Distributors, Individual (187,254 records)
- **AMFI** — Mutual Fund Distributors, Corporate (10,760 records)

**JSON format**: Compressed single-character keys to reduce file size:
```
n = name, a = address, id = DP ID, p = pincode, e = email,
u = website, st = state, loc = city/location, t = type, arn = ARN, c = city
```

**Homepage map features**:
- Leaflet + MarkerCluster with 260k+ access points
- Choropleth view (district-level density) and Points view (clustered markers)
- Layer toggles for CDSL, NSDL, MFD Individual, MFD Corporate
- District drilldown on click, state filtering, location search (Photon geocoder)
- Panel includes "Project FINER" branding + nav pills to other sections

### 2. SLBC Data — District-Level Financial Inclusion

Machine-readable datasets extracted from State Level Bankers' Committee (SLBC) quarterly PDF booklets.

**Currently available**: All 8 NE states — Assam, Meghalaya, Manipur, Arunachal Pradesh, Mizoram, Tripura, Nagaland, Sikkim
**Source**: [SLBC NE - Meghalaya Booklets](https://slbcne.nic.in/meghalaya/booklet.php)

**Coverage**:
- Quarters range from March 2018 to September 2025 (varies by state — not all states have every quarter)
- 48 indicator categories per quarter (for 2022 onwards; 2021 has fewer)
- All monetary values in **Rs. Lakhs** (1 Lakh = ₹100,000)

**State data availability** (latest quarter):
| State | Latest Quarter | Total Quarters |
|-------|---------------|----------------|
| Assam | Sep 2025 | 30 |
| Manipur | Sep 2025 | 39 |
| Tripura | Sep 2025 | 32 |
| Mizoram | Sep 2025 | 22 |
| Meghalaya | Sep 2025 | 15 |
| Arunachal Pradesh | Mar 2025 | 18 |
| Nagaland | Mar 2025 | 7 |
| Sikkim | Mar 2025 | 4 |

**Timeseries JSON structure** (`{state}_fi_timeseries.json`):
```json
{
  "periods": [
    {
      "period": "June 2020",
      "districts": [
        {
          "district": "East Garo Hills",
          "period": "June 2020",
          "credit_deposit_ratio__total_deposit": 12345.67,
          "branch_network__total_branch": 23,
          ...
        }
      ]
    }
  ]
}
```
**Important**: This is a nested structure (NOT a flat array). Must flatten with `periods → districts` before use.

**Complete JSON structure** (`{state}_complete.json`):
```json
{
  "quarters": {
    "june_2020": {
      "period": "June 2020",
      "tables": {
        "branch_network": {
          "fields": ["total_branch", "branch_rural", ...],
          "districts": { "East Garo Hills": { "total_branch": "23", ... } }
        }
      }
    }
  }
}
```

**Important**: Quarter keys in the JSON use snake_case (`june_2020`, `sept_2025`), while folder names on disk use `YYYY-MM` format (`2020-06`, `2025-09`). Mapped via `QUARTER_FOLDERS` and `QUARTER_LABELS` in `src/lib/slbc-categories.ts`.

### 3. FI Indicators Choropleth (`/fi-indicators`)

Full-screen Leaflet choropleth map showing 7 key financial inclusion indicators across all 8 NE states at the district level.

**7 Indicators**: Credit-Deposit Ratio, PM Jan Dhan Yojana, Branch Network, Kisan Credit Card, Self Help Groups, Digital Transactions, Aadhaar Authentication

**Key architecture decisions**:
- Built as inline JS (`<script is:inline>`) in an Astro page — NOT Svelte — because Leaflet is too imperative
- Loads all 8 state timeseries JSONs in parallel via `Promise.all()`
- Uses `flattenTimeseries()` to handle nested JSON structure
- Uses `normalizePeriod()` to convert "June 2020" → "2020-06" for sorting

**Critical data matching patterns**:

1. **Quarter fallback**: Not all states have data for every quarter. When the selected quarter (e.g. Sep 2025) isn't available for a state (e.g. AP latest is Mar 2025), the map falls back to the nearest prior quarter. Tooltip shows "Data from Mar 2025" in italic.

2. **Field name fallbacks**: Same indicator is stored under different field names across states. Each metric has a `fallbacks` array:
   ```js
   { field: 'total_no_of_kcc', fallbacks: ['no_of_kcc', 'kcc_no', 'total_kcc_no', 'total_no', ...] }
   ```

3. **Cross-category fallbacks**: Some states store fields under unexpected categories:
   - Assam: `total_branch` is under `credit_deposit_ratio`, not `branch_network`
   - AP: KCC data is under `fi_kcc`, not `kcc`
   ```js
   const CROSS_CATEGORY_FALLBACKS = {
     'branch_network': ['credit_deposit_ratio', 'kcc', 'fi_kcc', 'digital_transactions'],
     'kcc': ['fi_kcc'],
   };
   ```

4. **District name aliases**: GeoJSON and SLBC use different spellings for same districts:
   ```js
   const DISTRICT_ALIASES = {
     'PAPUMPARE': 'PAPUM PARE',       // AP
     'KEYI PANYOR': 'CAPITAL COMPLEX', // AP
     'DARANG': 'DARRANG',             // Assam
     'SIBSAGAR': 'SIVASAGAR',         // Assam
     'KAMJANG': 'KAMJONG',            // Manipur
     'RIBHOI': 'RI BHOI',            // Meghalaya
     'GOMTI': 'GOMATI',              // Tripura
     // ... more
   };
   ```

5. **Adaptive color scale**: Color breaks recompute based on visible (filtered) districts, so single-state views show meaningful variation instead of being washed out by other states' outliers.

**Color ramps**: Green for CD Ratio, blue for Digital Transactions, terracotta for all others.

**GeoJSON property**: District state is stored as `STATE_UT` (not `STATE`) in `district_boundaries.geojson`. District name is `DISTRICT`.

### 4. Analysis / Data Explorer

Interactive data exploration page (`/analysis`) built with Svelte + Plotly.js:
- Load SLBC Meghalaya data or upload custom CSV
- Select X/Y fields, chart type (scatter/bar/line), color by district
- Live Pearson correlation coefficient
- Download chart as PNG

## SLBC PDF Extraction (for adding new states)

The extraction script is at `/Users/abhinav/Downloads/extract_everything_v2.py` (outside the repo).

**Key technical details**:
- Uses **pdfplumber** for table extraction from landscape-oriented PDF pages
- PDF cells contain **reversed text** (due to rotation) — requires `str[::-1]` character reversal
- **Category detection**: keyword matching on table titles with priority-based rules
  - Title-only categorization tried first; falls back to title + field names
  - NPS rules set to priority 9–10 to beat `education_loan` (priority 8)
- **District detection**: identifies the 12 Meghalaya districts in table rows
- **Continuation merging**: multi-page tables are detected and merged
- 2021 quarters extracted from Excel files (ZIP archives), not PDFs — hence fewer tables

**What the dataset does NOT include**: Bank-wise tables and individual bank scorecards. Only district-level aggregates.

## Design System

### Fonts
- **Georgia** (serif) — Body text, headings, stat numbers
- **Inter** (sans-serif) — UI labels, section labels, buttons, metadata, badges
- **IBM Plex Mono** (monospace) — Data visualizations

### Color Palette
| Color | Hex | Usage |
|-------|-----|-------|
| Background | `#f5f4f1` | Page background |
| Text | `#1a1410` | Primary text, headings |
| Terracotta | `#b8603e` | Primary accent, CDSL color, active states, links |
| Terracotta dark | `#8a4a2e` | Link hover |
| Teal | `#3d7a8e` | NSDL color, SLBC link accent |
| Olive | `#5a7a3a` | MFD Individual color |
| Gold | `#8b6914` | MFD Corporate color |
| Muted text | `#888078` | Secondary text |
| Label text | `#aaa09a` | Section labels, tertiary text |
| Border | `#e8e5e0` / `#e0ddd8` | Card borders, dividers |

### UI Patterns
- **Cards**: White bg, 1px border, 8px radius, left border accent (3px), hover lift
- **Section labels**: 9px Inter, 600 weight, uppercase, `#aaa09a`
- **Buttons**: 10px Inter, uppercase, hover inverts to dark bg
- **Frosted glass panels** (map): `rgba(255,255,255,0.92)` + `backdrop-filter: blur(12px)`

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| astro | ^6.0.4 | Static site generator |
| @astrojs/svelte | ^8.0.0 | Svelte integration for Astro |
| svelte | ^5.0.0 | Interactive component framework |
| d3 | ^7.9.0 | Data utilities |
| plotly.js-dist-min | ^3.0.0 | Charts in data explorer |
| xlsx | ^0.18.5 | Client-side Excel generation |

Leaflet and MarkerCluster are loaded via CDN (unpkg) in inline scripts.

## Common Gotchas

1. **Base URL**: `base` in `astro.config.mjs` is `/` for the custom domain `projectfiner.com`.
2. **`define:vars` IIFE**: Astro wraps `define:vars` scripts in an IIFE, so variables aren't accessible in subsequent `<script is:inline>` blocks. Use `window.__FINER_BASE` to pass the base URL.
3. **Leaflet kept as inline JS**: Both maps (homepage + FI indicators) are imperative DOM code. Converting to Svelte would be complex and Leaflet has SSR issues. Keep as `<script is:inline>`.
4. **JSON quarter keys vs folder names**: Master JSON uses `june_2020` but disk folders are `2020-06`. Mapped in `slbc-categories.ts`.
5. **Large JSON files**: Some data files are 15–18MB. They load fine in browser but be aware of GitHub's 100MB file limit.
6. **2021 SLBC quarters have very few tables** (1–2 each) because only Excel ZIP archives were available.
7. **PDF text reversal**: SLBC PDFs have landscape-rotated pages where cell text is stored backwards (`str[::-1]`).
8. **SLBC category classification**: NPS tables must be classified with high-priority rules to avoid false matches from field names containing "Education" and "Loan".
9. **Homepage IS the map**: The capital markets map is the homepage (`/`). Old `/capital-markets/map` redirects to `/`.
10. **Timeseries JSON is nested, NOT flat**: Structure is `{ periods: [{ period, districts: [{...}] }] }`. Must flatten before use. The `flattenTimeseries()` function handles this.
11. **Period format mismatch**: Timeseries JSON stores periods as "June 2020", "September 2024" etc., but code normalizes to "2020-06" format. Always use `normalizePeriod()`.
12. **State file naming**: Slug uses hyphens (`arunachal-pradesh`), NOT underscores. File path: `slbc-data/arunachal-pradesh/arunachal-pradesh_fi_timeseries.json`.
13. **GeoJSON uses `STATE_UT`**: The state property in `district_boundaries.geojson` is `STATE_UT`, not `STATE`. District names are in `DISTRICT` property (uppercase).
14. **States have different latest quarters**: AP/Nagaland/Sikkim latest is Mar 2025; others have Sep 2025. The FI indicators page handles this with quarter fallback.
15. **Same indicator, different category names**: KCC data lives under `kcc` in some states and `fi_kcc` in others (e.g. Arunachal Pradesh). Must use cross-category fallbacks.
16. **Same indicator, different field names**: e.g. KCC count is `total_no_of_kcc` in Meghalaya, `rupay_card_issued_in_kcc` in AP, `o_s_position_no_of_cards_issued` in Nagaland. Must use field fallback arrays.
17. **Map height 0 bug**: If `body` has `min-height: 100vh` from `global.css`, the flex layout for full-screen maps breaks. Override with `min-height: unset` on map pages.
18. **District name mismatches between GeoJSON and SLBC**: GeoJSON has "PAPUMPARE" but SLBC has "PAPUM PARE", GeoJSON has "DARANG" but SLBC has "DARRANG", etc. Always use `DISTRICT_ALIASES` mapping.

## Data Quality Pipeline

SLBC data goes through multiple cleaning passes after PDF extraction:
1. **District cleanup** — Remove bank names, TOC entries, page numbers from district lists using canonical district lists + fuzzy matching
2. **Bank-wise table removal** — Only district-level aggregates are kept
3. **Field normalization** — Standardize AC/A/C, Amt/Amt., case/pluralization variants
4. **Date-embedded field redistribution** — Fields like "CD Ratio March 2024" split into correct quarters
5. **Fuzzy deduplication** — Merge near-duplicate field names (OCR artifacts)
6. **Final comprehensive fix** — Comma number parsing, NPA disambiguation, garbled name fixes, long name shortening
7. **Cross-state field standardization** — Run via `public/slbc-data/standardize_fields.py`. Handles:
   - Manipur OCR spacing fixes (`total_bran ch` → `total_branch`)
   - Meghalaya reversed word order (`rural_branch` → `branch_rural`)
   - Abbreviation normalization (`term_loan` → `tl`, `tot` → `total`)
   - Typo fixes and singular/plural normalization
   - Applied across timeseries CSV, timeseries JSON, complete JSON, and quarterly CSVs for all 8 states

## FI Indicators — Field Mapping Reference

When adding new states or updating indicators, these are the known field name variations by state:

| Indicator | Standard Field | Variations |
|-----------|---------------|------------|
| CD Ratio | `overall_cd_ratio` | `cd_ratio`, `current_c_d_ratio`, `cdr` |
| PMJDY | `total_pmjdy_no` | `pmjdy_no`, `total_no`, `no_of_pmjdy_accounts` |
| Branches | `total_branch` | `total`, `no_of_branches`, `no_of_brs` |
| KCC | `total_no_of_kcc` | `no_of_kcc`, `total_kcc_no`, `total_no`, `rupay_card_issued_in_kcc`, `o_s_position_no_of_cards_issued` |
| SHG | `savings_linked_no` | `savings_linked`, `credit_linked_no`, `current_fy_savings_linked_no`, `deposit_linkage_no_of_groups` |
| Digital | `bhim_upi_a_c` | `bhim_upi`, `coverage_pct` |
| Aadhaar | `no_of_aadhaar_seeded_casa` | `aadhaar_seeded_casa` |

**Category mismatches**: AP uses `fi_kcc` instead of `kcc`; Assam stores `total_branch` under `credit_deposit_ratio` instead of `branch_network`.
