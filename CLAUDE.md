# Project FINER — CLAUDE.md

## What This Project Is

**Project FINER** (Financial Inclusion in the North East Region) is a static data platform focused on financial inclusion in India, with emphasis on the North East region. It publishes interactive maps, charts, and downloadable datasets covering banking infrastructure, credit access, government schemes, and capital markets.

- **Hosted on**: GitHub Pages at `ksabhinav.github.io/projectfiner`
- **Repo**: `https://github.com/ksabhinav/projectfiner.git`
- **Branch**: `main`
- **No build tools**: Plain HTML/CSS/JS files. No framework, no bundler, no package.json. Pages are self-contained single HTML files with inline `<style>` and `<script>`.

## Dev Server

```json
// .claude/launch.json
{
  "name": "finer",
  "runtimeExecutable": "python3",
  "runtimeArgs": ["-m", "http.server", "8090", "--directory", "/Users/abhinav/Downloads/projectfiner"],
  "port": 8090
}
```

Preview at `http://localhost:8090`.

## Repository Structure

```
projectfiner/
├── index.html                              # Homepage (UPI market concentration chart)
│
├── capital-markets/
│   ├── capital_markets_map_v03.html        # Interactive Leaflet map (MAIN map page, v03 is latest)
│   ├── capital-market_access_v01.html      # Older map versions (v01, v02) — kept for reference
│   ├── capital-market_access_v02.html
│   ├── data-download.html                  # Central data download hub (SLBC + capital markets)
│   ├── DPSCs/
│   │   ├── cdsl_dp_centres.json            # 20,612 CDSL DP service centres (~4.4MB)
│   │   └── nsdl_dp_centres.json            # 57,005 NSDL DP service centres (~15.7MB)
│   └── MFDs/
│       └── mfd_individual.json             # 187,254 individual MF distributors (~18MB)
│       # (mfd_corporate.json also exists but not in repo — generated on demand)
│
├── slbc-data/
│   ├── index.html                          # SLBC landing page (lists all NE states)
│   └── meghalaya/
│       ├── download.html                   # Meghalaya SLBC download page (CSV/Excel via XLSX.js)
│       ├── README.md                       # Data documentation (coverage, categories, usage)
│       ├── meghalaya_complete.json          # Master JSON (~3MB) — all quarters, all indicators
│       ├── meghalaya_fi_timeseries.csv      # Wide-format CSV: all districts × all quarters
│       ├── meghalaya_fi_timeseries.json     # Same data as JSON
│       ├── meghalaya_district_fi_profile.json
│       ├── slbc_meghalaya_consolidated.json # Earlier consolidated extraction
│       ├── metadata.json
│       ├── quarterly/                      # 18 folders (YYYY-MM format), 606 CSVs total
│       │   ├── 2020-06/                    # June 2020 (22 tables)
│       │   ├── 2020-09/                    # September 2020 (28 tables)
│       │   ├── ...
│       │   └── 2025-09/                    # September 2025 (44 tables)
│       └── raw-csv/                        # Flat CSVs by category (earlier extraction, kept)
│
├── meghalaya/
│   ├── digital-payments/                   # PhonePe Pulse UPI data (FY22–FY24)
│   │   ├── 2022/, 2023/, 2024/            # Quarter-wise JSON (Trans + User per quarter)
│   │   └── Meghalaya-24-payments.html      # Digital payments visualization
│   ├── SSS/                                # PMEGP data
│   ├── megh-data.csv                       # General Meghalaya data
│   └── megh-map1.html                      # State map
│
├── Maps/                                   # GeoJSON boundary files
│   ├── DISTRICT_BOUNDARY.geojson
│   ├── DISTRICT_HQ.geojson
│   ├── MAJOR_TOWNS.geojson
│   ├── STATE_BOUNDARY.geojson
│   └── STATE_HQ.geojson
│
├── assam/, manipur/, mizoram/,             # State-level data + map HTML files
│   nagaland/, northeast/, sikkim/, tripura/
│
├── news/                                   # News/articles pages
│   ├── finer-news.html
│   └── finer-news-test.html
│
├── data/                                   # india_states.geojson
├── geocode_pincodes.py                     # Utility: geocode pincodes
├── pincode_coords.json                     # Pincode → lat/lng lookup
├── unique_pincodes.json
├── data.csv                                # General data file
├── Megh-digi-slider-orange.html            # Standalone visualization experiments
├── Megh-digi-slider-orange-minimal-exit.html
├── megh-obsi-fs.html
└── meghalaya-obsidian.html
```

## Two Main Data Sections

### 1. Capital Markets Access

Interactive map + downloadable data on capital markets infrastructure across India.

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

**Key pages**:
- `capital-markets/capital_markets_map_v03.html` — Main interactive map (Leaflet + MarkerCluster)
  - Panel with layer toggles for DPSC and MFD layers
  - View modes: Cluster / Heatmap
  - Location/pincode/state filtering
  - "Download Data" button links to `data-download.html`
- `capital-markets/data-download.html` — Download hub
  - SLBC section at top (Meghalaya link card)
  - Capital Markets section below (4 dataset cards with CSV/Excel buttons)
  - Downloads are client-side: fetches JSON from GitHub raw, converts via XLSX.js

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

**Key pages**:
- `slbc-data/index.html` — Landing page listing all NE states
- `slbc-data/meghalaya/download.html` — Download page with 3 views:
  - Full Dataset (time-series CSV/Excel)
  - By Indicator tab (44 indicator cards, each with CSV/Excel)
  - By Quarter tab (18 quarter cards, each with CSV/Excel)
  - Excel downloads get one sheet per category

**JSON structure** (`meghalaya_complete.json`):
```json
{
  "source": "...",
  "state": "Meghalaya",
  "description": "...",
  "amount_unit": "Rs. Lakhs",
  "quarters": {
    "june_2020": {
      "period": "June 2020",
      "as_on_date": "30.06.2020",
      "fy": "2020-21",
      "tables": {
        "branch_network": {
          "page": 45,
          "fields": ["Branches Rural", "Branches Semi-Urban", ...],
          "num_districts": 12,
          "districts": {
            "East Garo Hills": { "Branches Rural": "23", ... },
            ...
          }
        },
        ...44 categories...
      }
    },
    ...18 quarters...
  }
}
```

**Important**: Quarter keys in the JSON use snake_case (`june_2020`, `sept_2025`), while folder names on disk use `YYYY-MM` format (`2020-06`, `2025-09`). The download page maps between these via `QUARTER_FOLDERS` and `QUARTER_LABELS` objects.

**44 indicator categories** (full list in `slbc-data/meghalaya/README.md`):
- Banking Infrastructure: branch_network, credit_deposit_ratio
- Annual Credit Plan: acp_target_achievement, acp_disbursement_agri/msme/other_ps/non_ps, acp_npa_outstanding, acp_priority_sector_os_npa
- Sector Outstanding & NPA: agri_outstanding/npa, msme_outstanding/npa, other_ps_outstanding/npa, non_ps_outstanding/npa, weaker_section_os, govt_sponsored_npa
- Credit Schemes: kcc, kcc_crop, education_loan, housing_pmay, crop_insurance
- Government Programmes: pmjdy, pmmy_mudra_disbursement/os_npa, sui, pmegp, social_security, nrlm, nulm
- Special Groups: minority_disbursement/outstanding, sc_st_finance, women_finance, shg, jlg
- Financial Inclusion & Digital: fi_village_banking, fi_kcc, digital_transactions, aadhaar_authentication, investment_credit_agri_disbursement/outstanding
- Administrative: rseti, ldm_details

## SLBC PDF Extraction (for adding new states)

The extraction script is at `/Users/abhinav/Downloads/extract_everything_v2.py` (outside the repo).

**Key technical details**:
- Uses **pdfplumber** for table extraction from landscape-oriented PDF pages
- PDF cells contain **reversed text** (due to rotation) — requires `str[::-1]` character reversal
- **Category detection**: keyword matching on table titles with priority-based rules
  - Title-only categorization tried first; falls back to title + field names
  - This prevents false matches from field names (e.g., NPS tables have "Education" and "Loan" in field names, which would incorrectly match `education_loan`)
  - NPS rules set to priority 9–10 to beat `education_loan` (priority 8)
- **District detection**: identifies the 12 Meghalaya districts in table rows
- **Continuation merging**: multi-page tables are detected and merged
- 2021 quarters extracted from Excel files (ZIP archives), not PDFs — hence fewer tables

**What the dataset does NOT include**: Bank-wise tables and individual bank scorecards from the same SLBC booklets. Only district-level aggregates are extracted.

## Design System

### Fonts
- **Georgia** (serif) — Body text, headings, stat numbers
- **Inter** (sans-serif) — UI labels, section labels, buttons, metadata, badges
- **IBM Plex Mono** (monospace) — Charts, data visualizations (used on index.html)

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
| Muted text | `#888078` | Secondary text, descriptions |
| Label text | `#aaa09a` | Section labels, tertiary text |
| Border | `#e8e5e0` / `#e0ddd8` | Card borders, dividers |
| Card bg | `#fff` | Card backgrounds |
| Button bg | `#faf9f7` | Button default state |

### UI Patterns
- **Cards**: White background, 1px border `#e8e5e0`, 8px border-radius, left border accent (3px colored), subtle shadow `0 1px 3px rgba(0,0,0,0.03)`, hover lift `translateY(-1px)` + stronger shadow
- **Section labels**: 9px Inter, font-weight 600, 0.1em letter-spacing, uppercase, color `#aaa09a`
- **Buttons**: 10px Inter, uppercase, 5px border-radius, hover inverts to dark bg `#1a1410` with white text
- **Badges**: Pill-shaped (20px border-radius), outlined, 9px uppercase, category-colored
- **Stat bars**: White background, centered flex row, large Georgia numbers + tiny uppercase labels
- **Frosted glass panels** (map page): `rgba(255,255,255,0.92)` + `backdrop-filter: blur(12px)`

## External Libraries Used

| Library | CDN | Used In |
|---------|-----|---------|
| Leaflet 1.9.4 | unpkg | capital_markets_map_v03.html |
| Leaflet.markercluster 1.5.3 | unpkg | capital_markets_map_v03.html |
| XLSX.js 0.18.5 | jsdelivr | data-download.html, meghalaya/download.html |
| D3.js 7.8.5 | cdnjs | index.html |

No npm dependencies. All loaded via CDN `<script>` tags.

## Data Serving

All data is served from **GitHub raw content URLs**:
```
https://raw.githubusercontent.com/ksabhinav/projectfiner/main/...
```

Downloads happen entirely client-side:
1. Fetch JSON from GitHub raw
2. Transform to rows/columns in JavaScript
3. Generate CSV string or use XLSX.js to build Excel workbook
4. Trigger browser download via `Blob` + `URL.createObjectURL`

## State-Level Maps (Other NE States)

Each state has a basic directory with:
- `{state}-data.csv` — Data file
- `{state}-map1.html` — Map visualization

States with directories: assam, manipur, mizoram, nagaland, sikkim, tripura, northeast (combined)

## Naming Conventions

- HTML files: kebab-case with version numbers (e.g., `capital_markets_map_v03.html`)
- Data files: snake_case (e.g., `cdsl_dp_centres.json`, `branch_network.csv`)
- SLBC quarterly folders: `YYYY-MM` (e.g., `2020-06`, `2025-09`) — numeric month, not name
- SLBC JSON quarter keys: snake_case month names (e.g., `june_2020`, `sept_2025`) — legacy format
- CSS classes: kebab-case (e.g., `state-link-inner`, `dataset-head`)

## Common Gotchas

1. **JSON quarter keys vs folder names**: The master JSON uses `june_2020` but disk folders are `2020-06`. The download page has explicit mapping objects (`QUARTER_FOLDERS`, `QUARTER_LABELS`).
2. **Large JSON files**: Some data files are 15–18MB. They load fine in browser but be aware of GitHub's 100MB file limit.
3. **No `mfd_corporate.json` in MFDs dir**: The capital-markets download references it but it may be generated separately.
4. **2021 SLBC quarters have very few tables** (1–2 each) because only Excel ZIP archives were available, not full PDF booklets.
5. **PDF text reversal**: SLBC PDFs have landscape-rotated pages where cell text is stored backwards. The extraction script reverses it with `str[::-1]`.
6. **SLBC category classification**: NPS (Non-Priority Sector) tables must be classified with high-priority rules to avoid being caught by `education_loan` rules, because NPS tables have fields containing "Education" and "Loan".
