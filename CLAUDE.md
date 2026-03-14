# Project FINER — CLAUDE.md

## What This Project Is

**Project FINER** (Financial Inclusion in the North East Region) is a static data platform focused on financial inclusion in India, with emphasis on the North East region. It publishes interactive maps, charts, and downloadable datasets covering banking infrastructure, credit access, government schemes, and capital markets.

- **Hosted on**: GitHub Pages at `ksabhinav.github.io/projectfiner`
- **Repo**: `https://github.com/ksabhinav/projectfiner.git`
- **Branch**: `main`
- **Framework**: Astro 6 + Svelte 5 (static site generation)
- **Deployment**: GitHub Actions (`.github/workflows/deploy.yml`) — builds with `npm run build`, deploys to GitHub Pages
- **Base URL**: `/projectfiner/` (trailing slash required — set in `astro.config.mjs`)

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

Preview at `http://localhost:8090/projectfiner/`.

## Repository Structure

```
projectfiner/
├── astro.config.mjs                        # Astro config (base: '/projectfiner/', static output)
├── package.json                            # Dependencies: astro, @astrojs/svelte, svelte, d3, plotly, xlsx
├── .github/workflows/deploy.yml            # GitHub Actions: build + deploy to Pages
│
├── src/
│   ├── layouts/
│   │   ├── BaseLayout.astro                # Base HTML shell (fonts, global CSS, <slot />)
│   │   └── PageLayout.astro                # Extends BaseLayout with Header + Footer
│   │
│   ├── components/
│   │   ├── Header.astro                    # Shared nav bar (Map, SLBC Data, Downloads, Analysis)
│   │   ├── Footer.astro                    # Simple footer with dynamic year
│   │   ├── MeghalayaDownload.svelte        # SLBC download UI (indicator/quarter tabs, CSV/Excel)
│   │   ├── DownloadManager.svelte          # Capital markets download cards (CDSL/NSDL/MFD)
│   │   └── analysis/
│   │       └── DataExplorer.svelte         # Interactive data explorer (Plotly charts, correlation, CSV upload)
│   │
│   ├── pages/
│   │   ├── index.astro                     # HOMEPAGE — Full-screen Leaflet capital markets map
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
    │   └── district_boundaries.geojson     # District boundaries with capital markets counts
    ├── pincode_coords.json                 # Pincode → [lat, lng] lookup
    ├── slbc-data/meghalaya/
    │   ├── meghalaya_complete.json          # Master JSON (~3MB) — all quarters, all indicators
    │   ├── meghalaya_fi_timeseries.csv      # Wide-format CSV: all districts × all quarters
    │   ├── quarterly/                      # 18 folders (YYYY-MM format), 606 CSVs total
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
- `import.meta.env.BASE_URL` returns `/projectfiner/` (with trailing slash)
- All hrefs in Astro templates use `${base}path` (no extra `/` needed since base has trailing slash)
- Inline scripts access base via `window.__FINER_BASE` set by a `define:vars` script block

## Two Main Data Sections

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

**Currently available**: Meghalaya (other NE states listed as "coming soon")
**Source**: [SLBC NE - Meghalaya Booklets](https://slbcne.nic.in/meghalaya/booklet.php)

**Coverage**:
- 18 quarters: June 2020 — September 2025
- 12 districts (all Meghalaya districts)
- 44 indicator categories per quarter (for 2022 onwards; 2021 has fewer — Excel-only)
- 606 CSV files total
- All monetary values in **Rs. Lakhs** (1 Lakh = ₹100,000)

**JSON structure** (`meghalaya_complete.json`):
```json
{
  "source": "...",
  "state": "Meghalaya",
  "quarters": {
    "june_2020": {
      "period": "June 2020",
      "fy": "2020-21",
      "tables": {
        "branch_network": {
          "fields": ["Branches Rural", "Branches Semi-Urban", ...],
          "districts": {
            "East Garo Hills": { "Branches Rural": "23", ... }
          }
        }
      }
    }
  }
}
```

**Important**: Quarter keys in the JSON use snake_case (`june_2020`, `sept_2025`), while folder names on disk use `YYYY-MM` format (`2020-06`, `2025-09`). Mapped via `QUARTER_FOLDERS` and `QUARTER_LABELS` in `src/lib/slbc-categories.ts`.

### 3. Analysis / Data Explorer

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

1. **Base URL trailing slash**: `base` in `astro.config.mjs` must be `/projectfiner/` (with trailing slash) or all `${base}path` links break.
2. **`define:vars` IIFE**: Astro wraps `define:vars` scripts in an IIFE, so variables aren't accessible in subsequent `<script is:inline>` blocks. Use `window.__FINER_BASE` to pass the base URL.
3. **Leaflet kept as inline JS**: The map is ~700 lines of imperative DOM code. Converting to Svelte would be complex and Leaflet has SSR issues. Keep it as `<script is:inline>`.
4. **JSON quarter keys vs folder names**: Master JSON uses `june_2020` but disk folders are `2020-06`. Mapped in `slbc-categories.ts`.
5. **Large JSON files**: Some data files are 15–18MB. They load fine in browser but be aware of GitHub's 100MB file limit.
6. **2021 SLBC quarters have very few tables** (1–2 each) because only Excel ZIP archives were available.
7. **PDF text reversal**: SLBC PDFs have landscape-rotated pages where cell text is stored backwards (`str[::-1]`).
8. **SLBC category classification**: NPS tables must be classified with high-priority rules to avoid false matches from field names containing "Education" and "Loan".
9. **Homepage IS the map**: The capital markets map is the homepage (`/`). Old `/capital-markets/map` redirects to `/`.
