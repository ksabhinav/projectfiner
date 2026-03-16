# Project FINER — CLAUDE.md

## What This Project Is

**Project FINER** (Financial Inclusion in the North East Region) is a static data platform focused on financial inclusion in India, with emphasis on the North East region and Bihar. It publishes interactive maps, charts, and downloadable datasets covering banking infrastructure, credit access, government schemes, and capital markets.

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
│   │   └── PageLayout.astro                # Extends BaseLayout with Header + Footer; accepts activeSubNav prop
│   │
│   ├── components/
│   │   ├── Header.astro                    # Shared nav bar with frosted glass styling + optional analysis sub-nav
│   │   ├── Footer.astro                    # Simple footer with dynamic year
│   │   ├── MeghalayaDownload.svelte        # SLBC download UI (indicator/quarter tabs, CSV/Excel)
│   │   ├── DownloadManager.svelte          # Capital markets download cards (CDSL/NSDL/MFD)
│   │   └── analysis/
│   │       ├── DataExplorer.svelte         # Interactive data explorer (Plotly charts, correlation, CSV upload)
│   │       ├── DistrictRankings.svelte     # Sortable leaderboard with traffic-light badges
│   │       ├── TrendTracker.svelte         # District profile with sparkline cards + expandable Plotly charts
│   │       └── Insights.svelte            # Curated data stories with category filter pills
│   │
│   ├── pages/
│   │   ├── index.astro                     # HOMEPAGE — Full-screen Leaflet map (capital markets + FI indicators)
│   │   ├── slbc-data/
│   │   │   ├── index.astro                 # State listing with all 9 states + download links
│   │   │   └── {state}/download.astro      # Per-state SLBC download pages
│   │   ├── capital-markets/
│   │   │   ├── map.astro                   # Redirects to homepage
│   │   │   └── data-download.astro         # Download hub for capital markets + SLBC data
│   │   └── analysis/
│   │       ├── index.astro                 # Data Explorer (activeSubNav="explorer")
│   │       ├── rankings/index.astro        # District Rankings (activeSubNav="rankings")
│   │       ├── trends/index.astro          # Trend Tracker (activeSubNav="trends")
│   │       └── insights/index.astro        # Pre-built Insights (activeSubNav="insights")
│   │
│   ├── lib/
│   │   ├── constants.ts                    # COLORS, CAPITAL_MARKETS_SOURCES, FILE_ICON_SVG
│   │   ├── download.ts                     # saveBlob(), rowsToCsv(), downloadCsv(), downloadXlsx()
│   │   ├── slbc-categories.ts              # CATEGORY_INFO (48 cats), QUARTER_ORDER/LABELS/FOLDERS
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
    ├── pincode_coords.json                 # Pincode → [lat, lng] lookup
    ├── slbc-data/
    │   ├── standardize_fields.py           # Cross-state field standardization script
    │   └── {state}/                        # All 10 states (8 NE + Bihar + West Bengal)
    │       ├── {state}_complete.json       # Master JSON — all quarters, all indicators
    │       ├── {state}_fi_timeseries.json  # Timeseries JSON (nested: periods → districts)
    │       ├── {state}_fi_timeseries.csv   # Wide-format CSV: all districts × all quarters
    │       ├── quarterly/                  # Folders (YYYY-MM format), CSVs per category
    │       └── raw-csv/                    # Flat CSVs by category
    └── digital-payments/                   # PhonePe Pulse UPI data (FY22–FY24)
```

## Architecture Notes

### Astro + Svelte
- **Astro pages** (`.astro`) handle layout, routing, and static HTML generation
- **Svelte components** (`.svelte`) handle interactive UI (download managers, data explorer, analysis tools)
- Svelte uses **Svelte 5 runes**: `$state`, `$derived`, `$derived.by`, `$effect`, `$props`, `onMount`
- **Leaflet map** on homepage is kept as `<script is:inline>` (too imperative for Svelte)
- `define:vars={{ base }}` passes Astro variables to inline scripts via `window.__FINER_BASE`

### Navigation Architecture
- **Header.astro** provides a shared frosted glass navigation bar across all non-map pages
- Accepts `activeSubNav` prop (`'explorer' | 'rankings' | 'trends' | 'insights'`) to render analysis sub-nav tabs
- **PageLayout.astro** passes `activeSubNav` through to Header
- Sub-nav is only rendered on analysis pages; other pages get the header without tabs
- Sub-nav was previously duplicated inside each Svelte component — now centralized in Header

### Data Fetching
- All data in `public/` is fetched at runtime via `import.meta.env.BASE_URL` + relative path
- XLSX.js is dynamically imported (`import('xlsx')`) to avoid SSR issues
- Plotly.js loaded dynamically in DataExplorer and TrendTracker via `import('plotly.js-dist-min')`

### Base URL
- `import.meta.env.BASE_URL` returns `/` (with trailing slash) for the custom domain `projectfiner.com`
- All hrefs in Astro templates use `${base}path` (no extra `/` needed since base has trailing slash)
- Inline scripts access base via `window.__FINER_BASE` set by a `define:vars` script block

## Main Data Sections

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
- `preferCanvas: true` on map init to avoid SVG pixelation during zoom/flyTo
- Choropleth view (district-level density) and Points view (clustered markers)
- Layer toggles for CDSL, NSDL, MFD Individual, MFD Corporate
- District drilldown on click, state filtering, location search (Photon geocoder)
- Panel includes "Project FINER" branding + nav pills to other sections
- Mode toggle: "Banking Access" (FI indicators choropleth) and "Capital Market Access" (points/choropleth)
- Vertical timeline slider for quarter selection (latest at top, oldest at bottom)

### 2. SLBC Data — District-Level Financial Inclusion

Machine-readable datasets extracted from State Level Bankers' Committee (SLBC) quarterly PDF booklets.

**Currently available**: 10 states — 8 NE states (Assam, Meghalaya, Manipur, Arunachal Pradesh, Mizoram, Tripura, Nagaland, Sikkim) + Bihar + West Bengal
**NE Source**: [SLBC NE - Meghalaya Booklets](https://slbcne.nic.in/meghalaya/booklet.php)
**Bihar Source**: [SLBC Bihar Agenda Papers](https://www.slbcbihar.com/SlBCHeldMeeting.aspx) (44th–95th meetings)
**West Bengal Source**: SLBC WB Agenda Papers (130th–171st meetings), PDFs stored in `slbc-data/west-bengal/`

**Coverage**:
- Quarters range from March 2018 to December 2025 (varies by state — not all states have every quarter)
- 48 indicator categories per quarter for NE (for 2022 onwards; 2021 has fewer); 49 categories for WB
- All monetary values in **Rs. Lakhs** (1 Lakh = ₹100,000)

**State data availability** (latest quarter):
| State | Latest Quarter | Total Quarters |
|-------|---------------|----------------|
| Assam | Sep 2025 | 30 |
| Manipur | Sep 2025 | 39 |
| Tripura | Sep 2025 | 32 |
| Bihar | Sep 2025 | 25 |
| West Bengal | Dec 2025 | 39 |
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

### 3. FI Indicators Choropleth (homepage, Banking Access mode)

Full-screen Leaflet choropleth map showing 7 key financial inclusion indicators across all 9 states (8 NE + Bihar) at the district level. Accessed via the homepage "Banking Access" mode toggle or `/?mode=banking`.

**7 Indicators**: Credit-Deposit Ratio, PM Jan Dhan Yojana, Branch Network, Kisan Credit Card, Self Help Groups, Digital Transactions, Aadhaar Authentication

**182 districts across 10 states**: 121 NE districts + 38 Bihar districts + 23 West Bengal districts

**Key architecture decisions**:
- Built as inline JS (`<script is:inline>`) in `index.astro` — NOT Svelte — because Leaflet is too imperative
- Loads all 9 state timeseries JSONs in parallel via `Promise.all()`
- Uses `flattenTimeseries()` to handle nested JSON structure
- Uses `normalizePeriod()` to convert "June 2020" → "2020-06" for sorting
- `preferCanvas: true` prevents SVG pixelation during `flyTo` animations
- India outline GeoJSON simplified with Douglas-Peucker (`tolerance=0.001`, `preserve_topology=True`)

**Map bounds** (expanded for Bihar):
- `NE_BOUNDS`: `L.latLngBounds(L.latLng(21.5, 83.5), L.latLng(29.5, 97.5))`
- `NE_CENTER`: `[25.5, 90.0]`

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

### 4. Analysis Pages (`/analysis/*`)

Four analysis sub-pages with shared sub-nav tabs (Explorer, Rankings, Trends, Insights):

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
- "All States" mode loads all 9 `_complete.json` files
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
- 13 curated data stories with real numbers from SLBC timeseries
- Data defined in `src/lib/insights-data.ts`
- Category filter pills (CD Ratio, Digital, Branches, KCC, PMJDY, Comparison)
- 2-column card grid with terracotta left border accent
- Each card shows: category badge, headline stat, title, narrative, tags

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

## Common Gotchas

1. **Base URL**: `base` in `astro.config.mjs` is `/` for the custom domain `projectfiner.com`.
2. **`define:vars` IIFE**: Astro wraps `define:vars` scripts in an IIFE, so variables aren't accessible in subsequent `<script is:inline>` blocks. Use `window.__FINER_BASE` to pass the base URL.
3. **Leaflet kept as inline JS**: Both maps (homepage capital markets + FI indicators) are imperative DOM code. Converting to Svelte would be complex and Leaflet has SSR issues. Keep as `<script is:inline>`.
4. **JSON quarter keys vs folder names**: Master JSON uses `june_2020` but disk folders are `2020-06`. Mapped in `slbc-categories.ts`.
5. **Large JSON files**: Some data files are 15–18MB. They load fine in browser but be aware of GitHub's 100MB file limit.
6. **2021 SLBC quarters have very few tables** (1–2 each) because only Excel ZIP archives were available.
7. **PDF text reversal**: SLBC PDFs have landscape-rotated pages where cell text is stored backwards (`str[::-1]`).
8. **SLBC category classification**: NPS tables must be classified with high-priority rules to avoid false matches from field names containing "Education" and "Loan".
9. **Homepage IS the map**: The capital markets map is the homepage (`/`). Old `/capital-markets/map` redirects to `/`. FI indicators are accessed via `/?mode=banking` or the "Banking Access" toggle.
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
   - Bihar category renames (`cd_ratio` → `credit_deposit_ratio`, `kcc_progress` → `kcc`)
   - Bihar-specific field name mapping (60+ rules in `BIHAR_SNAKE_FIXES`)
   - Abbreviation normalization (`term_loan` → `tl`, `tot` → `total`)
   - Typo fixes and singular/plural normalization
   - Applied across timeseries CSV, timeseries JSON, complete JSON, and quarterly CSVs for all 10 states

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
| Aadhaar | `no_of_aadhaar_seeded_casa` | `aadhaar_seeded_casa`, `no_of_aadhaar_seeded` (WB — without `_casa` suffix) |

**Category mismatches**: AP uses `fi_kcc` instead of `kcc`; Assam stores `total_branch` under `credit_deposit_ratio` instead of `branch_network`; WB uses `shg_nrlm` instead of `shg`; WB stores Aadhaar seeding data under `pmjdy` category.
