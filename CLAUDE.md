# Project FINER — CLAUDE.md

## What This Project Is

**Project FINER** (Financial Inclusion in the North East Region) is a data platform mapping financial inclusion across India — 36 states/UTs, 800+ districts, 20 indicators. It publishes interactive maps, charts, and downloadable datasets covering banking infrastructure, credit access, government schemes, digital payments, and capital markets.

- **Hosted on**: GitHub Pages with custom domain at `projectfiner.com`
- **Large data**: Cloudflare R2 at `data.projectfiner.com` (banking outlet point data 1.4 GB + RAG index files ~142 MB)
- **Repo**: `https://github.com/ksabhinav/projectfiner.git`
- **Branch**: `main`
- **Framework**: Astro 6 + Svelte 5 (static site generation)
- **Deployment**: GitHub Actions (`.github/workflows/deploy.yml`) — builds with `npm run build`, deploys to GitHub Pages
- **Base URL**: `/` (set in `astro.config.mjs`, site: `https://projectfiner.com`)
- **Data backbone**: SQLite database (`db/finer.db`, gitignored) for extraction, cleaning, joining. Build with `bash db/build.sh`
- **Contact**: mail@projectfiner.com

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
│   │   ├── BaseLayout.astro                # Base HTML shell (fonts, global CSS, OG meta tags, <slot />)
│   │   └── PageLayout.astro                # Extends BaseLayout with Header + Footer; accepts activeSubNav prop
│   │
│   ├── components/
│   │   ├── Header.astro                    # Shared nav bar with frosted glass capsule buttons + optional analysis sub-nav
│   │   │                                   # Accepts `transparent` prop for floating over the homepage map
│   │   ├── Footer.astro                    # Simple footer with dynamic year
│   │   ├── MeghalayaDownload.svelte        # SLBC download UI (indicator/quarter tabs, CSV/Excel)
│   │   ├── DownloadManager.svelte          # Capital markets download cards (CDSL/NSDL/MFD)
│   │   ├── map/                            # Map components (extracted from index.astro)
│   │   │   ├── MapPanel.svelte             # Left panel: mode toggle, indicator/metric/state dropdowns, outlet toggle, search (612 lines)
│   │   │   ├── TimelineSlider.svelte       # Vertical quarterly timeline with round dot marks, drag/click (321 lines)
│   │   │   ├── MapLegend.svelte            # Color legends for banking + capital markets modes (262 lines)
│   │   │   ├── FocusOverlay.svelte         # District focus: SVG shape + value overlay on double-click (258 lines)
│   │   │   └── InfoTooltip.svelte          # Hover (i) popover with indicator/metric descriptions (88 lines)
│   │   └── analysis/
│   │       ├── DataExplorer.svelte         # Interactive data explorer (Plotly charts, correlation, CSV upload)
│   │       ├── DistrictRankings.svelte     # Sortable leaderboard with traffic-light badges
│   │       └── TrendTracker.svelte         # District profile with sparkline cards + expandable Plotly charts
│   │
│   ├── pages/
│   │   ├── index.astro                     # HOMEPAGE — Full-screen Leaflet choropleth map (20 FI indicators, ~2071 lines)
│   │   ├── about/index.astro               # About page (what FINER is, coverage, data sources, contact)
│   │   ├── ask/index.astro                 # AI chat interface (RAG over SLBC + all indicators via Groq/Llama)
│   │   ├── slbc-data/
│   │   │   ├── index.astro                 # Redirects to data-download
│   │   │   └── {state}/download.astro      # Per-state SLBC download pages
│   │   ├── capital-markets/
│   │   │   ├── map.astro                   # Redirects to homepage
│   │   │   └── data-download.astro         # Download hub for capital markets + SLBC data
│   │   └── analysis/
│   │       ├── index.astro                 # Data Explorer (activeSubNav="explorer")
│   │       ├── rankings/index.astro        # District Rankings (activeSubNav="rankings")
│   │       └── trends/index.astro          # Trend Tracker (activeSubNav="trends")
│   │
│   ├── lib/
│   │   ├── constants.ts                    # COLORS, CAPITAL_MARKETS_SOURCES, FILE_ICON_SVG
│   │   ├── download.ts                     # saveBlob(), rowsToCsv(), downloadCsv(), downloadXlsx()
│   │   ├── slbc-categories.ts              # CATEGORY_INFO (48 cats), QUARTER_ORDER/LABELS/FOLDERS, CATEGORY_DESCRIPTIONS (45 hover tooltips)
│   │   ├── map-bridge.ts                   # TypeScript event bridge for map↔Svelte communication (finer:* custom events)
│   │   ├── map-indicators.ts               # 16 indicator definitions (shared between map and analysis pages)
│   │   ├── format-utils.ts                 # Shared prettyFieldName(), fmtNum(), fmtWithUnit(), normalizePeriod(), periodLabel()
│   │   └── insights-data.ts               # 13 curated Insight objects with real SLBC data
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
    ├── Maps/
    │   ├── india-outline.geojson           # Simplified India outline (Douglas-Peucker tolerance=0.001)
    │   └── ...                             # District/state boundaries, HQs, etc.
    ├── data/
    │   └── district_boundaries.geojson     # District boundaries (808 total) with capital markets counts
    ├── og-image.jpg                         # Open Graph image for social sharing (1200×630, rural banking illustration)
    ├── pincode_coords.json                 # Pincode → [lat, lng] lookup
    ├── district_lgd_codes.json             # 765 districts with LGD codes + 109 aliases
    ├── slbc-data/
    │   ├── standardize_fields.py           # Cross-state field standardization script
    │   └── {state}/                        # All 22 states
    │       ├── {state}_complete.json       # Master JSON — all quarters, all indicators
    │       ├── {state}_fi_timeseries.json  # Timeseries JSON (nested: periods → districts) — used by analysis pages
    │       ├── {state}_fi_slim.json        # Slim timeseries (7 indicator categories only) — used by homepage map (75% smaller)
    │       ├── {state}_fi_timeseries.csv   # Wide-format CSV: all districts × all quarters
    │       ├── quarterly/                  # Folders (YYYY-MM format), CSVs per category
    │       └── raw-csv/                    # Flat CSVs by category
    ├── digital-payments/                   # PhonePe Pulse UPI data (36 states, FY20–FY25)
    │   ├── phonepe_district_timeseries.json  # Consolidated: 14,734 district records, 20 quarters
    │   └── phonepe-pulse/{state}/          # Raw per-state quarterly JSON files (720 files)
    ├── banking-outlets/                    # RBI DBIE Banking Outlet data
    │   ├── district_counts.json            # Aggregated: 774 districts, counts by type (128 KB, in Git)
    │   └── state_counts.json               # State-level summary (3 KB, in Git)
    │   # Per-state outlet JSON files (1.4 GB total) hosted on Cloudflare R2:
    │   # https://data.projectfiner.com/banking-outlets/{state}.json
    ├── district_lgd_codes.json             # 765 districts with LGD codes + 109 aliases
    ├── indicators/
    │   ├── manifest.json                   # {indicators: [...], quarters: [...], latest_quarter}
    │   ├── capital_markets_access/
    │   │   └── static.json                 # 780 districts: cap_total, cap_cdsl, cap_nsdl, cap_mfdi, cap_mfdc
    │   └── {indicator}/                    # One dir per indicator, quarterly JSON files
    └── data/
        └── district_boundaries.geojson     # District boundaries with capital markets counts
│
├── scripts/
│   └── rag/
│       ├── build_index.py                  # Build BM25 index from text files → data/rag/index/
│       ├── ingest_structured_data.py       # SLBC _complete.json → text chunks
│       ├── ingest_indicator_files.py       # public/indicators/ → text chunks (all 20 indicators)
│       ├── extract_text.py                 # PDF text extraction
│       └── summarize_minutes.py            # Meeting minutes summariser (uses ANTHROPIC_API_KEY)
│
├── db/                                     # SQLite backbone (data pipeline)
│   ├── finer.db                            # SQLite database (gitignored, ~200 MB, rebuilt via build.sh)
│   ├── build.sh                            # Run full pipeline: init → import → export
│   ├── init_schema.py                      # Create 11 tables
│   ├── import_reference.py                 # States, districts, aliases, periods
│   ├── import_slbc.py                      # 22 states → slbc_data (1.19M rows)
│   ├── import_phonepe.py                   # PhonePe → phonepe_data (14.7K rows)
│   ├── import_nfhs.py                      # NFHS-5 → nfhs_data (73.6K rows)
│   ├── import_aadhaar.py                   # Aadhaar → aadhaar_enrollment (1M rows)
│   ├── match_districts.py                  # Shared district name → LGD code resolver
│   ├── export_timeseries.py               # SQLite → {state}_fi_timeseries.json
│   ├── export_phonepe.py                  # SQLite → phonepe_district_timeseries.json
│   └── aggregate_banking_outlets.py       # Raw outlets → district_counts.json
│
├── validate_data.py                        # Automated data quality checks (7 validators)
├── DATA_COMPLETENESS.md                    # Coverage matrix: 9 indicators × 22 states
└── DATA_VALIDATION_REPORT.md              # Latest validation findings
```

## Architecture Notes

### Astro + Svelte
- **Astro pages** (`.astro`) handle layout, routing, and static HTML generation
- **Svelte components** (`.svelte`) handle interactive UI (download managers, data explorer, analysis tools, and map controls)
- Svelte uses **Svelte 5 runes**: `$state`, `$derived`, `$derived.by`, `$effect`, `$props`, `onMount`
- **Leaflet map core** on homepage is kept as `<script is:inline>` (imperative DOM, SSR-incompatible), but all UI panels are Svelte components communicating via an event bus
- `define:vars={{ base }}` passes Astro variables to inline scripts via `window.__FINER_BASE`

### Homepage Map Architecture (Svelte + Leaflet Hybrid)

The homepage map is a **hybrid** — Leaflet handles canvas/tiles as inline JS, while all UI panels are Svelte components.

**Event bus**: `src/lib/map-bridge.ts` — TypeScript interfaces + `finer:*` CustomEvent dispatchers/listeners
- Svelte components fire events (e.g. `finer:indicator-change`, `finer:quarter-change`, `finer:state-filter`) that the inline map script listens to via `window.addEventListener`
- Map fires back events (e.g. `finer:district-click`, `finer:data-loaded`) that Svelte components subscribe to
- All events dispatched on `window` — no shared module state needed between inline JS and Svelte

**5 Svelte components** mounted with `client:load` in `index.astro`:
1. `MapPanel.svelte` — entire left panel: indicator/metric dropdowns, scope/state filter, outlet toggle, search, mobile bottom sheet with gesture drag
2. `TimelineSlider.svelte` — vertical quarterly timeline with round dot marks (6×6px, `border-radius: 50%`), hover-scale thumb
3. `MapLegend.svelte` — adaptive choropleth legend, rebuilds on each data refresh
4. `FocusOverlay.svelte` — district focus mode: full-viewport overlay with SVG district shape + stats
5. `InfoTooltip.svelte` — hover/tap popover for indicator and metric `(i)` descriptions

**Map centering**: `getPanelPadding()` in `index.astro` reads the panel's actual rendered DOM width and returns `paddingTopLeft: [336, 80]` (panel 290px + 16px offset + 30px gap) and `paddingBottomRight: [90, 20]` (timeline + zoom controls). A polling loop waits for the panel to render before the initial `fitBounds` call.

### Navigation Architecture
- **Header.astro** provides a shared navigation bar across ALL pages (including homepage)
- Nav links render as frosted glass capsule buttons (white bg, backdrop-blur, rounded corners, hover lift)
- Accepts `activeSubNav` prop (`'rankings' | 'trends'`) to render analysis sub-nav tabs (Rankings, Trends)
- Accepts `transparent` prop (boolean) — used on homepage to make the header float over the map with no background
- **PageLayout.astro** passes `activeSubNav` through to Header
- Sub-nav is only rendered on analysis pages; other pages get the header without tabs
- Homepage uses `<Header title="" transparent />` with `position: fixed` to float over the full-screen map
- Nav links: Downloads, Analysis, Ask, About (no Map button — clicking "Project FINER" brand goes home)
- **Important**: Capsule styles must be identical between Header.astro and any page-specific nav. Use the same `font-family: 'Inter', sans-serif; font-size: 10px; font-weight: 600; padding: 10px 18px; line-height: 1; box-sizing: border-box` to prevent size differences across pages

### Data Fetching
- All data in `public/` is fetched at runtime via `import.meta.env.BASE_URL` + relative path
- XLSX.js is dynamically imported (`import('xlsx')`) to avoid SSR issues
- Plotly.js loaded dynamically in DataExplorer and TrendTracker via `import('plotly.js-dist-min')`

### Base URL
- `import.meta.env.BASE_URL` returns `/` (with trailing slash) for the custom domain `projectfiner.com`
- All hrefs in Astro templates use `${base}path` (no extra `/` needed since base has trailing slash)
- Inline scripts access base via `window.__FINER_BASE` set by a `define:vars` script block

### Social Sharing (Open Graph)

`src/layouts/BaseLayout.astro` includes Open Graph and Twitter Card meta tags for rich previews on WhatsApp, Twitter, Facebook, LinkedIn:
```html
<meta property="og:title" content="Project FINER" />
<meta property="og:description" content="Financial Inclusion across India — interactive district-level maps" />
<meta property="og:image" content="https://projectfiner.com/og-image.jpg" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta name="twitter:card" content="summary_large_image" />
```
- **Image**: `public/og-image.jpg` — 1200×630px rural banking illustration, 257 KB JPEG (converted from RGBA PNG via Pillow `im.convert('RGB')` before saving)

## Main Data Sections

### 1. Capital Markets Access

Downloadable data on capital markets infrastructure across India. The raw point data (CDSL/NSDL/MFD individual locations) is available for download on the Downloads page but is **no longer shown as individual markers on the map** — it is now aggregated to district-level counts and exposed as the `capital_markets_access` choropleth indicator.

**Data sources** (scraped from official websites):
- **CDSL** — Depository Participant service centres (20,612 records) — `public/DPSCs/cdsl_dp_centres.json`
- **NSDL** — Depository Participant service centres (57,005 records) — `public/DPSCs/nsdl_dp_centres.json`
- **AMFI** — Mutual Fund Distributors, Individual (187,254 records) — `public/MFDs/mfd_individual.json`
- **AMFI** — Mutual Fund Distributors, Corporate (10,760 records) — `public/MFDs/mfd_corporate.json`

**JSON format**: Compressed single-character keys:
```
n = name, a = address, id = DP ID, p = pincode, e = email,
u = website, st = state, loc = city/location, t = type, arn = ARN, c = city
```

**District-level aggregate**: `public/indicators/capital_markets_access/static.json`
- 780 districts, fields: `cap_total`, `cap_cdsl`, `cap_nsdl`, `cap_mfdi`, `cap_mfdc`
- Source: `district_boundaries.geojson` which has `cdsl_cnt`, `nsdl_cnt`, `mfdi_cnt`, `mfdc_cnt` embedded

### 2. SLBC Data — District-Level Financial Inclusion

Machine-readable datasets extracted from State Level Bankers' Committee (SLBC) quarterly PDF booklets.

**Currently available**: 22 states — 8 NE states (Assam, Meghalaya, Manipur, Arunachal Pradesh, Mizoram, Tripura, Nagaland, Sikkim) + Bihar + West Bengal + Jharkhand + Odisha + Chhattisgarh + Kerala + Karnataka + Tamil Nadu + Rajasthan + Gujarat + Maharashtra + Haryana + Telangana + Uttarakhand
**NE Data Hierarchy (CRITICAL)**:
1. **`onlineslbcne.nic.in`** (online portal) = **PRIMARY/GOLD STANDARD** for all 8 NE states. This structured data must NEVER be overwritten by PDF extraction. It has cleaner, more reliable data.
2. **`slbcne.nic.in`** (PDF booklets) = **FALLBACK** — only used to fill gaps for data/categories not available on the online portal.
**NE Portal Source**: [onlineslbcne.nic.in](https://onlineslbcne.nic.in) — structured data for all 8 NE states
**NE PDF Source**: [SLBC NE - Meghalaya Booklets](https://slbcne.nic.in/meghalaya/booklet.php) — quarterly PDF booklets (fallback)
**Bihar Source**: [SLBC Bihar Agenda Papers](https://www.slbcbihar.com/SlBCHeldMeeting.aspx) (44th–95th meetings)
**West Bengal Source**: SLBC WB Agenda Papers (130th–171st meetings), PDFs stored in `slbc-data/west-bengal/`
**Jharkhand/Odisha/Chhattisgarh Source**: NE-style extraction from respective SLBC booklets
**Kerala Source**: [SLBC Kerala](https://slbckerala.com) — annexure PDFs from meeting pages
**Karnataka Source**: [SLBC Karnataka](https://slbckarnataka.com) — annexure PDFs from meeting pages
**Tamil Nadu Source**: [SLBC Tamil Nadu](https://slbctn.com) — annexure PDFs from meeting pages
**Rajasthan Source**: [SLBC Rajasthan](https://slbcrajasthan.in) — Excel files
**Gujarat Source**: [SLBC Gujarat](https://slbcgujarat.in) — ZIP archives
**Maharashtra Source**: [Bank of Maharashtra SLBC](https://bankofmaharashtra.bank.in) — PDFs (values in Crores, converted to Lakhs)
**Haryana Source**: [SLBC Haryana (PNB)](https://slbcharyana.pnb.bank.in) — Excel files (values in Crores, converted to Lakhs)
**Telangana Source**: [SLBC Telangana](https://telanganaslbc.com) — PDFs
**Uttarakhand Source**: [SLBC Uttarakhand](https://slbcuttarakhand.com) — PDFs

**Coverage**:
- Quarters range from March 2018 to December 2025 (varies by state — not all states have every quarter)
- 48 indicator categories per quarter for NE (for 2022 onwards; 2021 has fewer); 49 categories for WB
- All monetary values in **Rs. Lakhs** (1 Lakh = ₹100,000)

**State data availability** (latest quarter):
| State | Latest Quarter | Total Quarters | Districts |
|-------|---------------|----------------|-----------|
| Assam | Sep 2025 | 30 | 35 |
| Manipur | Sep 2025 | 39 | 16 |
| Tripura | Sep 2025 | 32 | 8 |
| Bihar | Sep 2025 | 25 | 38 |
| West Bengal | Dec 2025 | 39 | 23 |
| Mizoram | Sep 2025 | 22 | 11 |
| Meghalaya | Sep 2025 | 15 | 12 |
| Arunachal Pradesh | Mar 2025 | 18 | 26 |
| Nagaland | Mar 2025 | 7 | 16 |
| Sikkim | Mar 2025 | 4 | 6 |
| Jharkhand | Sep 2025 | 10 | 24 |
| Odisha | Dec 2025 | 8 | 30 |
| Chhattisgarh | Dec 2025 | 12 | 33 |
| Kerala | Dec 2025 | 23 | 14 |
| Karnataka | Jun 2025 | 7 | 31 |
| Tamil Nadu | Dec 2025 | 10 | 38 |
| Rajasthan | Dec 2025 | 2 | 41 |
| Gujarat | Dec 2025 | 10 | 33 |
| Maharashtra | Dec 2025 | 3 | 36 |
| Haryana | Dec 2025 | 13 | 23 |
| Telangana | Dec 2024 | 1 | 33 |
| Uttarakhand | Sep 2021 | 1 | 13 |

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

### 3. FI Indicators Choropleth (homepage)

Full-screen Leaflet choropleth map — the entire homepage. No mode toggle; always shows the FI indicator choropleth. Panel has Indicator / Metric / State dropdowns.

**20 Indicators**: Credit-Deposit Ratio, PM Jan Dhan Yojana, Branch Network, Kisan Credit Card, Self Help Groups, Digital Transactions (incl. PhonePe UPI), Aadhaar Authentication, Banking Infrastructure (RBI), Social Security, PMEGP, Housing/PMAY, Stand Up India, SC/ST Lending, Women's Credit, Education Loans, MUDRA/PMMY, NRLM SHG, RBI BSR Credit, Health Insurance (NFHS), Capital Markets Access

**800+ districts across 36 states/UTs**

**Key architecture decisions**:
- Leaflet core (tile layer, GeoJSON, flyTo, tooltips) kept as inline JS (`<script is:inline>`) in `index.astro` — UI panels are Svelte components connected via `finer:*` event bus (see above)
- **Progressive loading**: on page load only fetches `indicators/manifest.json` (748B) + `district_lgd_codes.json` (138KB); indicator data (~50-100KB per file) fetched on demand when indicator/quarter changes. No longer loads all 22 state timeseries JSONs. See [Progressive Loading](#progressive-loading-indicators) section.
- Uses `normalizePeriod()` to convert "June 2020" → "2020-06" for sorting
- `preferCanvas: true` prevents SVG pixelation during `flyTo` animations
- `zoomSnap: 0` enables fractional zoom so `fitBounds` fills the content area optimally (e.g. zoom 5.22 instead of rounding down to 5)
- India outline GeoJSON simplified with Douglas-Peucker (`tolerance=0.001`, `preserve_topology=True`)

**Map bounds** (expanded for all-India coverage including J&K/Ladakh):
- `ALL_STATES_BOUNDS`: `L.latLngBounds(L.latLng(7.5, 67.5), L.latLng(35.5, 98))` — full India incl. J&K, Kutch, A&N
- Desktop `maxBounds`: `L.latLngBounds(L.latLng(2, 50.0), L.latLng(40, 115.0))` — west extended to 50°E so `fitBounds` padding is not clamped by `_limitCenter`
- Mobile `maxBounds`: `L.latLngBounds(L.latLng(0, 48.0), L.latLng(45, 115.0))`
- `flyToNE()` uses `flyToBounds(ALL_STATES_BOUNDS)` on both mobile and desktop
- **Top padding**: `getPanelPadding()` reads `header.offsetHeight + 20` (≈80px) to clear the fixed 60px header

**Critical maxBounds/fitBounds interaction**: With `maxBoundsViscosity: 1.0`, Leaflet's `_limitCenter` shifts the map center east if the ideal center (accounting for panel padding) would show area west of `maxBounds.west`. Previously `west=62°E` caused India to appear left-shifted behind the panel. Fix: expand `maxBounds` west to 50°E so the left edge at zoom 5.2 (~53°E) stays inside `maxBounds`.

**Critical data matching patterns**:

1. **Quarter fallback**: Not all states have data for every quarter. When the selected quarter (e.g. Sep 2025) isn't available for a state (e.g. AP latest is Mar 2025), the map falls back to the nearest prior quarter. Tooltip shows "Data from Mar 2025" in italic.

2. **Field name fallbacks**: Same indicator is stored under different field names across states. Each metric has a `fallbacks` array:
   ```js
   { field: 'total_no_of_kcc', fallbacks: ['no_of_kcc', 'kcc_no', 'total_kcc_no', 'total_no', ...] }
   ```

3. **Cross-category fallbacks**: Some states store fields under unexpected categories:
   - Assam: `total_branch` is under `credit_deposit_ratio`, not `branch_network`
   - AP: KCC data is under `fi_kcc`, not `kcc`
   - WB: SHG data under `shg_nrlm`, social security under `social_security_schemes`
   - WB: PMJDY district enrolment tables land in `pmjdy_2`, `pmjdy_3`
   ```js
   const CROSS_CATEGORY_FALLBACKS = {
     'branch_network': ['credit_deposit_ratio', 'kcc', 'fi_kcc', 'digital_transactions', 'branch_network_p2', ...],
     'kcc': ['fi_kcc', 'kcc_animal_husbandry', 'kcc_fishery', 'kcc_outstanding'],
     'shg': ['shg_nrlm', 'nrlm', 'shg_p2', 'shg_p3', 'jlg'],
     'pmjdy': ['pmjdy_p2', 'pmjdy_p3', 'pmjdy_p4', 'social_security_schemes', 'pmjdy_2', 'pmjdy_3'],
     'aadhaar_authentication': ['pmjdy'],
   };
   ```

4. **District name aliases**: GeoJSON and SLBC use different spellings for same districts:
   ```js
   const DISTRICT_ALIASES = {
     'PAPUMPARE': 'PAPUM PARE',                    // AP
     'KEYI PANYOR': 'CAPITAL COMPLEX',              // AP
     'DARANG': 'DARRANG',                           // Assam
     'SIBSAGAR': 'SIVASAGAR',                       // Assam
     'KAMJANG': 'KAMJONG',                           // Manipur
     'RIBHOI': 'RI BHOI',                           // Meghalaya
     'GOMTI': 'GOMATI',                              // Tripura
     'PURBA CHAMPARAN': 'PURBI CHAMPARAN',          // Bihar
     'PASHCHIM CHAMPARAN': 'PASHCHIMI CHAMPARAN',   // Bihar
     'KAIMUR (BHABUA)': 'KAIMUR',                    // Bihar
     // ... more
   };
   ```

5. **Adaptive color scale**: Color breaks recompute based on visible (filtered) districts, so single-state views show meaningful variation instead of being washed out by other states' outliers.

**Color ramps**: Green for CD Ratio, blue for Digital Transactions, terracotta for all others.

**GeoJSON property**: District state is stored as `STATE_UT` (not `STATE`) in `district_boundaries.geojson`. District name is `DISTRICT`.

**District Focus Mode**: Double-clicking a district on the Banking Access choropleth opens a full-viewport overlay:
- District shape rendered as SVG (GeoJSON → SVG path via `geoToSVGPath()`)
- Shows district name, state, metric label, formatted value, and current quarter
- Shape filled with the district's choropleth color; text uses white text-shadow for readability
- Timeline slider and indicator panel remain interactive above the overlay (`z-index: 1300`)
- Exit via ESC key, X button, or clicking the backdrop
- `focusDistrict(name, state)` activates, `updateFocusPanel()` refreshes on timeline/indicator change, `exitFocus()` closes
- `doubleClickZoom: false` on the Leaflet map prevents zoom conflict with focus activation
- Panel shows hint: "Double-click a district to focus"

**Slim Timeseries** (`_fi_slim.json`): The homepage loads `_fi_slim.json` instead of `_fi_timeseries.json` for 75% smaller payloads (19 MB vs 76 MB total). Generated by stripping all fields except the 7 indicator categories. Regenerate with `/tmp/slim_timeseries_v2.py` after adding new SLBC data. Analysis pages still use the full `_fi_timeseries.json`.

### 4. Analysis Pages (`/analysis/*`)

Three analysis sub-pages with shared sub-nav tabs (Rankings, Trends):

#### Data Explorer (`/analysis/`)
- Built with Svelte + Plotly.js
- Load SLBC data for any state or upload custom CSV
- Select X/Y fields, chart type (scatter/bar/line), color by district
- Live Pearson correlation coefficient
- Download chart as PNG

#### District Rankings (`/analysis/rankings/`)
- Sortable leaderboard of all districts for any indicator
- Traffic-light status badges: Green/Yellow/Red
  - CD Ratio: fixed thresholds (≥60% green, 40–60% yellow, <40% red)
  - All others: quartile-based (top 25% green, middle 50% yellow, bottom 25% red)
- State/Category/Quarter/Field selectors
- "All States" mode loads all 22 `_complete.json` files
- Stats summary: district count, max, min, median
- **Important**: `availableFields` must be sourced from the selected quarter only (not all quarters), otherwise fields that don't exist in the selected quarter may be chosen as default

#### Trend Tracker (`/analysis/trends/`)
- District profile view with sparkline cards (inline SVG `<polyline>`, no Plotly dependency for cards)
- QoQ change arrows: green ▲ for increase, red ▼ for decrease
- NPA metrics have **inverted logic** (decrease is good → green)
- Category filter pills to narrow visible metrics
- Click-to-expand any card → loads full Plotly time series chart via dynamic import
- Uses `flattenTimeseries()` and `normalizePeriod()` from inline helpers

#### Pre-built Insights (`/analysis/insights/`)
- **Removed from analysis sub-nav** — page still exists at `/analysis/insights/` but not linked from navigation
- 13 curated data stories with real numbers from SLBC timeseries
- Data defined in `src/lib/insights-data.ts`

## Bihar Data Pipeline

Bihar SLBC data was extracted separately from the NE states:

**Source PDFs**: Downloaded from `slbcbihar.com` — 44th through 95th SLBC meeting agenda papers
- Some PDFs are text-native (extractable with pdfplumber)
- Some are scanned images requiring OCR (done via PDF Expert app on macOS)
- SSL certificate errors on the site required `curl -sk` (insecure flag)

**Extraction**: Uses pdfplumber similar to NE states, but Bihar PDFs have different table structures:
- Tables start halfway through the booklet (after narrative sections)
- 38 districts (vs 12 for Meghalaya)
- District names sometimes differ from GeoJSON spellings

**Field Standardization** (`standardize_fields.py`):
- Bihar added to STATES list
- `BIHAR_CATEGORY_RENAMES`: Maps Bihar-specific category names to standard ones (e.g., `cd_ratio` → `credit_deposit_ratio`, `kcc_progress` → `kcc`)
- `BIHAR_SNAKE_FIXES`: 60+ field name mappings for Bihar-specific naming conventions
- `BIHAR_HR_FIXES`: Human-readable name corrections
- All 7 FI indicators resolve correctly after standardization

**Data coverage**: 25 quarters from March 2019 to September 2025, 38 districts

## West Bengal Data Pipeline

West Bengal SLBC data is extracted separately using a dedicated script.

**Source PDFs**: 41 PDFs (130th–171st SLBC meetings) in `slbc-data/west-bengal/` (named `{N}th_agenda.pdf`)
**Extraction script**: `slbc-data/west-bengal/extract_wb.py` (~750 lines)
**23 districts**: Alipurduar, Bankura, Birbhum, Cooch Behar, Dakshin Dinajpur, Darjeeling, Hooghly, Howrah, Jalpaiguri, Jhargram, Kalimpong, Kolkata, Malda, Murshidabad, Nadia, North 24 Parganas, Paschim Bardhaman, Paschim Medinipur, Purba Bardhaman, Purba Medinipur, Purulia, South 24 Parganas, Uttar Dinajpur

**Key differences from NE extraction**:
- WB PDFs are **portrait-oriented** (no text reversal needed, unlike NE landscape PDFs)
- Uses **pdfplumber** table extraction directly (not the NE `extract_everything_v2.py`)
- Has its own **MEETING_TO_QUARTER** mapping (130th="March 2018" through 171st="December 2025")
- **Category rules**: 30+ regex-based classification rules with priority scoring
- Handles **sub-header detection** (multi-row headers common in WB PDFs)
- **Duplicate category handling**: When same category appears multiple times in a PDF, checks field overlap — >50% overlap means multi-page continuation (merge), otherwise creates `category_2`, `category_3` etc.
- **District name aliases**: Extensive mapping for WB-specific variations ("24 Paraganas North" → "North 24 Parganas", "Medinipur East" → "Purba Medinipur", etc.)
- Important: `normalize_district()` checks aliases BEFORE stripping leading serial numbers, because "24 Paraganas North" starts with "24" which would be wrongly stripped as a serial number

**Data coverage**: 39 quarters from March 2018 to December 2025, 49 categories, ~596 quarterly CSVs

**Running extraction**:
```bash
cd slbc-data/west-bengal/
python3 extract_wb.py
# Outputs: west-bengal_complete.json, west-bengal_fi_timeseries.json, west-bengal_fi_timeseries.csv, quarterly/, raw-csv/
# Then copy outputs to public/slbc-data/west-bengal/
```

## SLBC PDF Extraction (for adding new states)

The NE+Sikkim extraction script is at `/Users/abhinav/Downloads/extract_everything_v2.py` (outside the repo).
Bihar and West Bengal have their own dedicated extraction scripts (see sections above).

**Key technical details** (NE extraction):
- Uses **pdfplumber** for table extraction from landscape-oriented PDF pages
- PDF cells contain **reversed text** (due to rotation) — requires `str[::-1]` character reversal
- **Category detection**: keyword matching on table titles with priority-based rules
  - Title-only categorization tried first; falls back to title + field names
  - NPS rules set to priority 9–10 to beat `education_loan` (priority 8)
- **District detection**: identifies districts in table rows using canonical district lists
- **Continuation merging**: multi-page tables are detected and merged
- 2021 quarters extracted from Excel files (ZIP archives), not PDFs — hence fewer tables

**What the dataset does NOT include**: Bank-wise tables and individual bank scorecards. Only district-level aggregates.

## Design System

### Fonts
- **Playfair Display** (serif) — Brand name ("Project FINER"), page titles in Header
- **Georgia** (serif) — Body text, headings, stat numbers
- **Inter** (sans-serif) — UI labels, section labels, buttons, metadata, badges, nav links
- **IBM Plex Mono** (monospace) — Data visualizations

### Color Palette
| Color | Hex | Usage |
|-------|-----|-------|
| Background | `#f5f4f1` | Page background |
| Text | `#1a1410` | Primary text, headings |
| Terracotta | `#b8603e` | Primary accent, CDSL color, active states, links |
| Terracotta dark | `#8a4a2e` | Link hover |
| Terracotta gradient | `#b8603e → #d4845f` | Accent lines (header, panel) |
| Teal | `#3d7a8e` | NSDL color, SLBC link accent, banking mode focus |
| Olive | `#5a7a3a` | MFD Individual color |
| Gold | `#8b6914` | MFD Corporate color |
| Muted text | `#888078` | Secondary text |
| Label text | `#aaa09a` | Section labels, tertiary text, nav links |
| Border | `#e8e5e0` / `#e0ddd8` | Card borders, dividers |

### UI Patterns
- **Cards**: White bg, 1px border, 8px radius, left border accent (3px), hover lift
- **Section labels**: 9px Inter, 600 weight, uppercase, `#aaa09a`
- **Buttons**: 10px Inter, uppercase, hover inverts to dark bg
- **Frosted glass panels**: `rgba(255,255,255,0.94)` + `backdrop-filter: blur(16px)` — used on map panel, header, legends, tooltips
- **Header**: Sticky, frosted glass, Playfair Display brand, terracotta gradient accent line (`::before`)
- **Sub-nav tabs**: Rounded top corners, border with no bottom border, active tab gets white bg + `inset 0 -2px 0 var(--accent)` box-shadow
- **Traffic-light badges**: Green (`#2d7d46`), Yellow (`#b8860b`), Red (`#c44830`) — used in Rankings

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| astro | ^6.0.4 | Static site generator |
| @astrojs/svelte | ^8.0.0 | Svelte integration for Astro |
| svelte | ^5.0.0 | Interactive component framework |
| d3 | ^7.9.0 | Data utilities |
| plotly.js-dist-min | ^3.0.0 | Charts in data explorer and trend tracker |
| xlsx | ^0.18.5 | Client-side Excel generation |

Leaflet and MarkerCluster are loaded via CDN (unpkg) in inline scripts.

## Cloudflare R2 (data.projectfiner.com)

Large data files (>100 MB) are hosted on Cloudflare R2, not GitHub Pages.

- **Bucket**: `projectfiner-data`
- **Custom domain**: `data.projectfiner.com`
- **CORS**: Allows `https://projectfiner.com`, `https://www.projectfiner.com`, `localhost:8090`, `localhost:4321`
- **Upload**: `npx wrangler r2 object put "projectfiner-data/path/file.json" --file=local.json --content-type="application/json" --remote`
- **Currently hosted**: 35 state banking outlet JSON files (2.47M records, 1.4 GB total)
- **Frontend accesses via**: `var R2_BASE = 'https://data.projectfiner.com/';`

**Important**: When adding new CORS origins, use `npx wrangler r2 bucket cors set projectfiner-data --file cors.json --force`. The JSON format requires nested `allowed.origins`, `allowed.methods`, `allowed.headers` — NOT the S3-style flat format.

## SQLite Backbone (db/)

The SQLite database is the canonical data store for all FINER data. It's used at build time for cleaning, joining, and exporting — NOT at runtime (GitHub Pages is static).

**Build**: `cd db && bash build.sh --clean` (rebuilds from scratch in ~30s)

**Schema**: 11 tables
- `states` (36), `districts` (765), `district_aliases` (109), `periods` (48)
- `slbc_fields` (8,513), `slbc_data` (1.19M) — EAV model for SLBC indicators
- `phonepe_data` (14.7K), `nfhs_data` (73.6K), `aadhaar_enrollment` (1M)
- `import_log` — provenance tracking

**District matching**: `match_districts.py` resolves names → LGD codes. Tries: exact name → alias → normalized → cross-state fallback. Unmatched names logged for manual review.

**Export**: `export_timeseries.py` and `export_slim.py` generate JSON files identical to what the frontend expects.

**Extraction CLI**: `db/extract.py` — unified CLI wrapping all 15+ per-state extraction scripts.
```bash
python3 db/extract.py list                    # Show all states with status
python3 db/extract.py run --state meghalaya   # Run extraction
python3 db/extract.py pipeline --state all    # Full: extract → standardize → import → validate → export
python3 db/extract.py validate --state assam  # Run quality checks only
```
Config: `db/state_config.json` — per-state metadata (script paths, PDF dirs, source URLs, notes).

**Field Mappings**: `db/field_mappings.json` — 84 canonical field definitions mapping 543 state-specific variants across 16 indicators. Includes `reverse_lookup` (189 entries) and `haryana_field_map` (24 entries for Haryana's non-standard format).

## Progressive Loading (indicators/)

The homepage map uses **pre-aggregated indicator files** instead of loading all 22 state JSONs. This reduces initial payload from 19 MB to ~150 KB.

**How it works**:
1. Page load → fetch `indicators/manifest.json` (748 bytes) + `district_lgd_codes.json` (138 KB)
2. Indicator/quarter change → fetch `indicators/{indicator_key}/{quarter_code}.json` (~50-100 KB)
3. `buildDistrictLookup()` reads directly from the loaded indicator file

**Generated by**: `python3 db/export_indicator_files.py` (reads from SQLite, outputs to `public/indicators/`)

**File structure**:
```
public/indicators/
├── manifest.json                          # {indicators: [...], quarters: [...], latest_quarter: '...'}
├── credit_deposit_ratio/
│   ├── 2025-12.json                       # {indicator, quarter, districts: [{district, state, field: value, ...}]}
│   ├── 2025-09.json
│   └── ...
├── digital_transactions/
│   └── ...
├── rbi_banking_outlets/
│   └── static.json                        # No quarterly data — single snapshot
├── capital_markets_access/
│   └── static.json                        # 780 districts: cap_total/cdsl/nsdl/mfdi/mfdc
├── nfhs_health_insurance/
│   ├── 2021-03.json                       # NFHS-5 (2019-21), 637 districts, field: pct
│   └── 2016-03.json                       # NFHS-4 (2015-16), 637 districts, field: pct
└── ... (20 indicator directories total)
```

**Static indicators** (no quarterly data, load `static.json`): `rbi_banking_outlets`, `capital_markets_access`

**Per-indicator timePoints** (slider shows only specific time points instead of global quarters): `nfhs_health_insurance` uses `timePoints: ['2021-03', '2016-03']` in the INDICATORS config. When selected, `switchSliderToTimePoints()` replaces the global slider quarters; `restoreSliderToManifest()` restores them on switch-away.

**Important**: When indicator data changes (new SLBC extraction, new PhonePe quarter, etc.), regenerate:
```bash
python3 db/export_indicator_files.py
```
Then also rebuild the RAG index (see Ask/RAG section). The frontend caches loaded indicator files in `indicatorCache` — no duplicate fetches for the same indicator+quarter.

## Shared Modules (src/lib/)

**`format-utils.ts`** — shared formatting for all analysis components + map:
- `fmtNum()` — Indian-style abbreviations (1.2K, 1.2 L, 1.2 Cr)
- `fmtWithUnit()` — adds "₹ Lakhs" or "%" based on unit type
- `prettyFieldName()` — snake_case → Title Case with acronym preservation (CASA, KCC, NPA, etc.)
- `normalizePeriod()` / `periodLabel()` — "June 2020" ↔ "2020-06" conversion

**`map-bridge.ts`** — event bus between Leaflet inline JS and Svelte map components:
- TypeScript interfaces for all `finer:*` event payloads
- `dispatchFinerEvent(type, detail)` — fires a CustomEvent on `window`
- `onFinerEvent(type, handler)` — subscribes, returns an unsubscribe function
- Events fired by Svelte → map: `finer:indicator-change`, `finer:quarter-change`, `finer:state-filter`, `finer:scope-change`, `finer:outlet-toggle`
- Events fired by map → Svelte: `finer:district-click`, `finer:data-loaded`, `finer:quarters-available`

**`map-indicators.ts`** — indicator definitions (shared between map and Svelte components):
- 20 indicator categories with field names, fallbacks, descriptions, units

**Important**: `index.astro`'s `<script is:inline>` CANNOT import TypeScript modules. The inline map script has its own copies of utility functions (fmtNum, normalizePeriod, etc.). The shared TypeScript modules (`format-utils.ts`, `map-bridge.ts`) are used by the 5 Svelte map components and the analysis page components.

## RBI Banking Outlet Data

**2,472,495 banking outlets** across 35 states with exact GPS coordinates, downloaded from RBI DBIE Banking Outlet & ATM Locator API.

**API endpoint**: `https://data.rbi.org.in/CIMS_Gateway_DBIE/GATEWAY/SERVICES/dbie_getBankGetData`
- Session token: `security_generateSessionToken` (no auth, just POST `{"body":{}}`)
- Pagination: `offsetValue` + `limitValue` (up to 5000 per page)
- **Critical**: `statusType` must be `""` (empty string), NOT `"Live"` — "Live" returns 0 results
- Download script: `/tmp/download_rbi_outlets.py`

**Per-record fields**: bank, branch, type (BRANCH/BC/CSP/OFFICE/DBU), lat, lng, district, state, ifsc, populationGroup, address, openDate

**Counts**: 167,960 branches + 2.1M BCs + 147K CSPs = 2.47M total
- Largest: UP (443K), Bihar (260K), Maharashtra (214K)

**On map**: The "Banking Infrastructure (RBI)" indicator shows district-level aggregate counts as a choropleth, loaded from `district_counts.json` (128 KB, in Git). Individual outlet markers are **not shown on the map** — only the choropleth. The per-state outlet JSON files on R2 remain available for download but are not rendered on the homepage map.

## PhonePe Pulse UPI Data

**District-level UPI transaction data** for all 36 Indian states/UTs, 20 quarters (FY20-FY25).

**Source**: PhonePe Pulse GitHub repo (`github.com/PhonePe/pulse`)
- Downloaded via `curl` from `raw.githubusercontent.com/PhonePe/pulse/master/data/map/transaction/hover/country/india/state/{state}/{year}/{q}.json`
- 440 files (22 states × 5 years × 4 quarters), plus 280 more for additional 14 states

**Consolidated file**: `public/digital-payments/phonepe_district_timeseries.json` (2.3 MB)
- 14,734 district records, 20 quarters, 2 metrics per record (transaction_count, transaction_amount in Rs. Lakhs)
- Merged into `slbcData` on the frontend by matching state + district + period

**On map**: Part of "Digital Transactions" indicator group. Default metric when selecting Digital Transactions.

## Aadhaar Enrollment Data (UIDAI)

**New Aadhaar enrollments by district**, Apr–Dec 2025. Source: UIDAI Hackathon 2026 dataset (`aadhaar_enrolment_2025_combined.csv`, 43 MB), imported into SQLite as `aadhaar_enrollment` (1M rows).

**Schema**: `district_lgd`, `state_raw`, `district_raw`, `pincode`, `date` (DD-MM-YYYY), `age_0_5`, `age_5_17`, `age_18_plus`

**On map**: "Aadhaar Enrollment (UIDAI)" indicator — 3 quarterly files generated by `export_aadhaar_enrollment()` in `db/export_indicator_files.py`:
- `public/indicators/aadhaar_enrollment/2025-06.json` — 330 districts (Apr–Jun 2025)
- `public/indicators/aadhaar_enrollment/2025-09.json` — 724 districts (Jul–Sep 2025)
- `public/indicators/aadhaar_enrollment/2025-12.json` — 714 districts (Oct–Dec 2025)

**Quarter grouping** (SQL): daily DD-MM-YYYY dates → months 4–6 → `2025-06`, 7–9 → `2025-09`, 10–12 → `2025-12`

**Fields**: `total_enrolled`, `age_18_plus`, `age_5_17`, `age_0_5`

**Timeline**: uses `timePoints: ['2025-12', '2025-09', '2025-06']` — slider shows only the 3 available quarters when this indicator is selected (same pattern as NFHS health insurance).

**Import script**: `db/import_aadhaar.py` — reads from `~/Downloads/finer_data/aadhaar/aadhaar_enrolment_2025_combined.csv`

## Ask / RAG (`/ask`)

AI chat interface that answers questions about SLBC data and all FINER indicators using retrieval-augmented generation (RAG).

**Frontend**: `src/pages/ask/index.astro` renders an `<AskChat>` Svelte component.

**Backend**: Vercel serverless function at `api/ask.py` (Python, `BaseHTTPRequestHandler`).

### LLM: Llama 3.3 70B via Groq

- **Model**: `llama-3.3-70b-versatile`
- **API**: Groq's OpenAI-compatible endpoint — `https://api.groq.com/openai/v1/chat/completions`
- **Auth**: Bearer token via `GROQ_API_KEY` environment variable (set in Vercel dashboard under project Settings → Environment Variables)
- **Why Groq**: Free tier, fast inference, no cost for the query volume this project receives

### RAG Index (BM25, no embeddings)

- **Algorithm**: BM25 (term frequency × inverse document frequency) — simple, no GPU, no vector DB
- **Index files** stored on **Cloudflare R2** at `data.projectfiner.com/rag/`:
  - `chunks.json` — all text chunks with metadata (state, type, quarter, page range, text)
  - `bm25_params.json` — precomputed idf, per-doc TF, doc lengths, k1/b parameters
- **Cold-start loading**: Both files fetched via `urllib.request.urlopen()` at module load time (once per Vercel function cold start). ~142 MB total.
- **Total chunks**: ~26,107 (22,938 SLBC meeting document chunks + ~2,969 FINER indicator chunks + ~191 trend summary chunks)

### Document Coverage

1. **SLBC meeting documents** (~22,938 chunks): Agenda booklets, minutes, tables extracted from quarterly PDFs for all 22 states. Text files in `data/rag/text/{state}/{type}/`
2. **FINER indicator data** (~2,969 chunks): All 20 indicators × all quarters × all states. One chunk per (indicator, quarter, state), generated from `public/indicators/` JSON files.
3. **Trend summary chunks** (~191 chunks): One chunk per (indicator, state) covering **all quarters in a single document**. Contains the full time-series as a quarter-by-quarter table plus net change. Optimised for "how did X change over time in Y state" queries — BM25 returns the full trend in one hit instead of needing 20+ separate quarter chunks.

### Rebuilding the RAG Index

When indicator data or SLBC data changes, rebuild and redeploy:

```bash
# 1. Regenerate SLBC text chunks (if SLBC data changed)
python3 scripts/rag/ingest_structured_data.py

# 2. Regenerate indicator text chunks (always, since indicators update more often)
python3 scripts/rag/ingest_indicator_files.py
# Output: data/rag/text/{state}/tables/{indicator}_{quarter}.txt (~2,969 files)

# 3. Regenerate trend summary chunks (one per indicator+state, all quarters in one chunk)
python3 scripts/rag/build_trend_summaries.py
# Output: data/rag/text/{state}/tables/{indicator}_trend_summary.txt (~191 files)
# These answer "how did X change in Y" queries without needing 20+ separate chunk retrievals

# 4. Rebuild BM25 index
python3 scripts/rag/build_index.py
# Output: data/rag/index/chunks.json, data/rag/index/bm25_params.json

# 4. Upload to R2
npx wrangler r2 object put "projectfiner-data/rag/chunks.json" \
  --file=data/rag/index/chunks.json --content-type="application/json" --remote
npx wrangler r2 object put "projectfiner-data/rag/bm25_params.json" \
  --file=data/rag/index/bm25_params.json --content-type="application/json" --remote
```

No Vercel redeployment needed — the API reads fresh index from R2 on next cold start.

### Query Pipeline

1. Auto-detect state from query (e.g. "Assam" → `state_filter="Assam"`)
2. BM25 search over all chunks (pre-filtered by state if detected), `top_k=30`
3. Build context: up to 6 chunks, preferring tables for data-oriented queries
4. Send to Llama 3.3 70B via Groq with system prompt instructing it to cite sources
5. Return `{ answer, sources }` — sources include state, type, quarter, page range, snippet

## Data Validation Pipeline

`validate_data.py` — automated quality checks, runs in 0.8s for all 22 states.

**7 validators**:
1. 10x jumps between consecutive quarters
2. Column shifts (field value swaps within category)
3. Count/amount confusion (count fields with amount-like values)
4. Missing districts (disappear then reappear)
5. Duplicate fields (>90% identical values)
6. Outlier values (>3σ from district's own mean)
7. Period coverage gaps

**Run**: `python3 validate_data.py` (all states) or `python3 validate_data.py --state assam`

## Common Gotchas

1. **Base URL**: `base` in `astro.config.mjs` is `/` for the custom domain `projectfiner.com`.
2. **`define:vars` IIFE**: Astro wraps `define:vars` scripts in an IIFE, so variables aren't accessible in subsequent `<script is:inline>` blocks. Use `window.__FINER_BASE` to pass the base URL.
3. **Leaflet kept as inline JS**: Leaflet's tile layer, GeoJSON rendering, flyTo, and tooltips remain as `<script is:inline>` (imperative, SSR-incompatible). The UI panels (MapPanel, TimelineSlider, MapLegend, FocusOverlay, InfoTooltip) are Svelte components communicating with the inline JS via `finer:*` CustomEvents on `window`. See `src/lib/map-bridge.ts`.
4. **JSON quarter keys vs folder names**: Master JSON uses `june_2020` but disk folders are `2020-06`. Mapped in `slbc-categories.ts`.
5. **Large JSON files**: Some data files are 15–18MB. They load fine in browser but be aware of GitHub's 100MB file limit.
6. **2021 SLBC quarters have very few tables** (1–2 each) because only Excel ZIP archives were available.
7. **PDF text reversal**: SLBC PDFs have landscape-rotated pages where cell text is stored backwards (`str[::-1]`).
8. **SLBC category classification**: NPS tables must be classified with high-priority rules to avoid false matches from field names containing "Education" and "Loan".
9. **Homepage IS the FI choropleth map**: There is no mode toggle. The homepage always shows the FI indicator choropleth. Old `/capital-markets/map` redirects to `/`. There is no `/?mode=banking` or `/?mode=capital` — those URL params are ignored.
10. **Timeseries JSON is nested, NOT flat**: Structure is `{ periods: [{ period, districts: [{...}] }] }`. Must flatten before use. The `flattenTimeseries()` function handles this.
11. **Period format mismatch**: Timeseries JSON stores periods as "June 2020", "September 2024" etc., but code normalizes to "2020-06" format. Always use `normalizePeriod()`.
12. **State file naming**: Slug uses hyphens (`arunachal-pradesh`), NOT underscores. File path: `slbc-data/arunachal-pradesh/arunachal-pradesh_fi_timeseries.json`.
13. **GeoJSON uses `STATE_UT`**: The state property in `district_boundaries.geojson` is `STATE_UT`, not `STATE`. District names are in `DISTRICT` property (uppercase).
14. **States have different latest quarters**: AP/Nagaland/Sikkim latest is Mar 2025; WB latest is Dec 2025; others have Sep 2025. The FI indicators page handles this with quarter fallback.
15. **Same indicator, different category names**: KCC data lives under `kcc` in some states and `fi_kcc` in others (e.g. Arunachal Pradesh). WB uses `shg_nrlm` instead of `shg`. Must use cross-category fallbacks.
16. **Same indicator, different field names**: e.g. KCC count is `total_no_of_kcc` in Meghalaya, `rupay_card_issued_in_kcc` in AP, `o_s_position_no_of_cards_issued` in Nagaland. Must use field fallback arrays.
17. **WB district name "24 Paraganas" serial number bug**: The `normalize_district()` function strips leading digits as serial numbers (e.g. "1 Kolkata" → "Kolkata"). But "24 Paraganas North" starts with "24" which is part of the district name, not a serial number. Fix: always try matching against aliases BEFORE stripping the serial number prefix.
18. **WB PMJDY sub-header concatenation**: If `normalize_district()` fails to recognize the first data row as a district, the sub-header detection logic treats it as a sub-header and concatenates its values into the field names (e.g. `rural_a_c_31_57_805` instead of `rural_a_c`). Root cause is always a missing district alias or the serial number stripping bug above.
19. **WB extraction outputs go to slbc-data/west-bengal/, not public/**: After running `extract_wb.py`, must manually copy JSON/CSV outputs to `public/slbc-data/west-bengal/` for the frontend to use them.
20. **Map height 0 bug**: If `body` has `min-height: 100vh` from `global.css`, the flex layout for full-screen maps breaks. Override with `min-height: unset` on map pages.
21. **District name mismatches between GeoJSON and SLBC**: GeoJSON has "PAPUMPARE" but SLBC has "PAPUM PARE", GeoJSON has "DARANG" but SLBC has "DARRANG", Bihar has "PURBA CHAMPARAN" vs "PURBI CHAMPARAN", etc. Always use `DISTRICT_ALIASES` mapping.
22. **Astro scoped CSS and dynamic class names**: Astro's CSS scoping uses `[data-astro-cid-xxx]` attribute selectors. Class names used inside `.map()` expressions or `class:list` may NOT be detected by Astro's static analysis and won't get scoped styles. **Fix**: Use descendant selectors (`.parent a` instead of `.child-class`) or write the elements directly in the template instead of generating them with `.map()`.
23. **Astro dev server CSS caching**: After changing scoped CSS selectors in `.astro` files, the dev server may serve stale CSS. Clear cache with `rm -rf node_modules/.astro node_modules/.vite` and restart the server.
24. **Leaflet SVG pixelation during flyTo/zoom**: Leaflet's SVG renderer CSS-scales elements during animated zooms, causing pixelation. Fixed with `preferCanvas: true` on map initialization. This renders vector layers to `<canvas>` which re-renders at native resolution each frame.
25. **India outline GeoJSON simplification**: The `india-outline.geojson` uses Douglas-Peucker simplification via shapely (`simplify(tolerance=0.001, preserve_topology=True)`). Naive point-skipping (every Nth point) produces jagged edges. Source is datameet india-composite.geojson (10.7MB → ~1.2MB simplified).
26. **HiDPI canvas tiles**: For retina displays, tile layers need `tileSize: 512, zoomOffset: -1` or custom `createTile()` with `window.devicePixelRatio` scaling to avoid blurriness on high-DPI screens.
27. **DistrictRankings availableFields bug**: `availableFields` must derive from the SELECTED quarter's data only (`masterData.quarters[selectedQuarter].tables[selectedCategory].fields`), not from all quarters combined. Otherwise, the default field may not exist in the selected quarter, causing "No data available".
28. **Default field selection in Rankings**: Prefer ratio/percentage fields as defaults (look for fields containing "ratio", "pct", "percentage") since they're more meaningful than raw counts.
29. **Homepage uses Header with `transparent` prop**: The homepage imports Header.astro with `transparent` prop which applies `header-transparent` class (position: fixed, transparent bg). Don't use page-level `!important` overrides for Header styles — Astro's scoped CSS has higher specificity in production builds. Always modify Header.astro's scoped styles instead.
30. **Slim JSON must be regenerated after adding SLBC data**: After extracting new state data or updating existing states, regenerate `_fi_slim.json` files. The slim files only contain fields matching the 7 indicator category prefixes (credit_deposit_ratio, pmjdy, branch_network, kcc, shg, digital_transactions, aadhaar_authentication) plus numbered variants (_2, _3, _p2, etc.).
31. **Double-click zoom disabled on map**: `doubleClickZoom: false` in Leaflet map init to prevent conflict with district focus mode activation.
32. **Map initial position uses fitBounds, not setView**: Map initializes with `fitBounds(ALL_STATES_BOUNDS, { paddingTopLeft: [306, 10] })` to account for the left panel from the first frame. This prevents the visible layout shift that occurred when using a fixed center/zoom followed by `flyToNE()`.
33. **Contact email**: mail@projectfiner.com (configured via GoDaddy email + Cloudflare DNS MX/SPF records).
34. **Unit labels**: Monetary fields show "₹ Lakhs", percentages show "%". On the map: `fmtWithUnit(val, unit)` handles formatting. In analysis pages: `prettyFieldName()` auto-detects from field suffix (`_amt` → ₹ Lakhs, `_pct` → %). All SLBC monetary values are in **Rs. Lakhs** (1 Lakh = ₹100,000).
35. **Acronym preservation in analysis pages**: `prettyFieldName()` in TrendTracker, DistrictRankings, DataExplorer converts snake_case to Title Case then fixes 17 acronyms (CASA, KCC, NPA, PMJDY, SHG, ATM, UPI, IMPS, USSD, PMEGP, NULM, NRLM, SB, CD, CSP, AePS, DBT). Add new acronyms to all 3 files when needed.
36. **Bare→_amt field normalization**: Fields like `crop_loan` and `crop_loan_amt` that represent the same metric across different quarters were normalized to the `_amt` form. Script at `/tmp/normalize_amt_fields.py`. Only merged when a `_no` version exists (confirming bare = amount not count) or values have similar magnitude. 7,470 renames across 11 states.
37. **Info tooltip descriptions**: Each of the 7 indicators and 30+ metrics has a `desc` property in the INDICATORS object. Shown via `(i)` button next to dropdowns. Hover shows a `position:fixed` popover. Touch devices: tap to show, tap elsewhere to hide.
38. **Zoom control position**: `margin-top: 60px!important` on `.leaflet-control-zoom` to avoid overlap with the transparent Header nav capsules on the homepage.
39. **Aadhaar cross-category fallbacks**: Only `pmjdy`, `pmjdy_2`, `pmjdy_3` — NOT `digital_transactions`, `fi_kcc`, `women_finance` (those contain different metrics like BHIM transaction counts and digital coverage, not CASA seeding/authentication).
40. **OG image for social sharing**: `public/og-image.jpg` (1200×630, 257KB) + meta tags in `BaseLayout.astro`. WhatsApp/Telegram cache previews aggressively — share in a new chat or add `?v=2` to force re-scrape. Test at `opengraph.xyz`.
41. **R2 CORS must include both www and non-www origins**: CORS rules at `data.projectfiner.com` must allow both `https://projectfiner.com` AND `https://www.projectfiner.com`. Missing www caused "Failed to fetch" errors for banking outlet loading.
42. **R2 custom domain has no directory listing**: `data.projectfiner.com/` returns 404. Only direct file paths work. This is expected R2 behavior.
43. **LFS + GitHub Pages incompatibility**: Git LFS pointer files are served as-is by GitHub Pages (133 bytes instead of actual data). All large data files must be on Cloudflare R2, not LFS.
44. **Progressive loading fallback threshold**: When the selected quarter has fewer than 300 districts for an indicator, `loadIndicatorData()` falls back to the nearest earlier quarter with ≥300 districts.

## Data Quality Pipeline

SLBC data goes through multiple cleaning passes after PDF extraction:
1. **District cleanup** — Remove bank names, TOC entries, page numbers from district lists using canonical district lists + fuzzy matching
2. **Bank-wise table removal** — Only district-level aggregates are kept
3. **Field normalization** — Standardize AC/A/C, Amt/Amt., case/pluralization variants
4. **Date-embedded field redistribution** — Fields like "CD Ratio March 2024" split into correct quarters
5. **Fuzzy deduplication** — Merge near-duplicate field names (OCR artifacts)
6. **Final comprehensive fix** — Comma number parsing, NPA disambiguation, garbled name fixes, long name shortening
7. **Bare→_amt normalization** — Merge complementary field pairs where `foo` (1 quarter) and `foo_amt` (14 quarters) represent the same amount metric with different names. Safety: only when `_no` version exists confirming bare = amount, or values have similar magnitude. Applied across all 22 states.
8. **Cross-state field standardization** — Run via `public/slbc-data/standardize_fields.py`. Handles:
   - Manipur OCR spacing fixes (`total_bran ch` → `total_branch`)
   - Meghalaya reversed word order (`rural_branch` → `branch_rural`)
   - Bihar category renames (`cd_ratio` → `credit_deposit_ratio`, `kcc_progress` → `kcc`)
   - Bihar-specific field name mapping (60+ rules in `BIHAR_SNAKE_FIXES`)
   - Abbreviation normalization (`term_loan` → `tl`, `tot` → `total`)
   - Typo fixes and singular/plural normalization
   - Applied across timeseries CSV, timeseries JSON, complete JSON, and quarterly CSVs for all 22 states

## FI Indicators — Field Mapping Reference

When adding new states or updating indicators, these are the known field name variations by state:

| Indicator | Standard Field | Variations |
|-----------|---------------|------------|
| CD Ratio | `overall_cd_ratio` | `cd_ratio`, `current_c_d_ratio`, `cdr` |
| PMJDY | `total_pmjdy_no` | `pmjdy_no`, `total_no`, `no_of_pmjdy_accounts`, `total_a_c`, `total_pmjdy_a_c`, `total_no_pmjdy_a_c` |
| Branches | `total_branch` | `total`, `no_of_branches`, `no_of_brs`, `total_branches` |
| KCC | `total_no_of_kcc` | `no_of_kcc`, `total_kcc_no`, `total_no`, `rupay_card_issued_in_kcc`, `o_s_position_no_of_cards_issued`, `target_no` |
| SHG | `savings_linked_no` | `savings_linked`, `credit_linked_no`, `current_fy_savings_linked_no`, `deposit_linkage_no_of_groups`, `total_sanction_no` |
| Digital | `coverage_sb_pct` | `coverage_pct`, `achievement`, `pct_coverage`, `of_such_accounts_out_of_total_operative_savings_accounts` (Sikkim) |
| Aadhaar Seeded | `no_of_aadhaar_seeded_casa` | `aadhaar_seeded_casa`, `number_of_aadhaar_seeded_casa`, `no_of_aadhaar_seeded`, `aadhaar_seeded`, `pct_aadhaar_seeding` |
| Aadhaar Operative | `no_of_operative_casa` | `operative_casa`, `number_of_operative_casa`, `aadhaar_operative_casa`, `operative_sb` |
| Aadhaar Auth | `no_of_authenticated_casa` | `authenticated_casa`, `number_of_authenticated_casa`, `aadhaar_authenticated_casa`, `number_of_authenticated` |

**Category mismatches**: AP uses `fi_kcc` instead of `kcc`; Assam stores `total_branch` under `credit_deposit_ratio` instead of `branch_network`; WB uses `shg_nrlm` instead of `shg`; WB stores Aadhaar seeding data under `pmjdy` category. Aadhaar authentication falls back to `pmjdy`, `pmjdy_2`, `pmjdy_3` categories only (NOT `digital_transactions` or `fi_kcc` — those contain different metrics).

**Known data quality issues**:
- Meghalaya June 2021: deposits appear in Crores instead of Lakhs (40x jump) — unit conversion error in source PDF
- SHG `savings_linked_no`: alternates between cumulative and current-quarter counts across many states/quarters
- Several quarters (June 2021, Sept 2021, March 2021, June 2023, March 2024) extracted from Excel ZIPs have only 117 fields vs 430+ normal — limited table availability in source files
- Assam Baksa PMJDY June 2020 = 3.6M — obvious data entry error in source PDF
