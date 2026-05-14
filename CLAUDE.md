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
│   │   ├── BaseLayout.astro                # Base HTML shell (fonts, global CSS, OG meta tags, canonical URL, JSON-LD, <slot />)
│   │   └── PageLayout.astro                # Extends BaseLayout with Header + Footer; accepts activeSubNav + description props
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
│   │   │   ├── MapLegend.svelte            # Choropleth legend + live source citation (per indicator/quarter/state)
│   │   │   ├── FocusOverlay.svelte         # District focus: SVG shape + value overlay on double-click (258 lines)
│   │   │   ├── InfoTooltip.svelte          # Hover (i) popover with indicator/metric descriptions (88 lines)
│   │   │   ├── IndicatorStrip.svelte       # Top strip (What/When/Where cells) — hosts the FindingButton
│   │   │   ├── FindingButton.svelte        # Vermillion "A finding" pill — fires finer:show-finding
│   │   │   └── FactCard.svelte             # Modal that cycles through public/findings.json entries
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
│   │   ├── insights-data.ts                # 13 curated Insight objects with real SLBC data (legacy /analysis/insights/ page)
│   │   ├── findings-data.ts                # 25 typed Finding entries (mirrors public/findings.json) for future programmatic use
│   │   └── indicator-sources.ts            # getSourceCitation(indicator, quarter, state) → label/url/attribution; powers MapLegend citation
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
    ├── findings.json                        # 25 curated finding entries — backs the FactCard "A finding" modal
    ├── sitemap.xml                          # Static sitemap (25 canonical pages), referenced by robots.txt + GSC
    ├── robots.txt                           # Allow HTML, disallow heavy data dirs, sitemap pointer
    ├── BingSiteAuth.xml                     # Bing Webmaster Tools verification token
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
│   ├── aggregate_banking_outlets.py       # Raw outlets → district_counts.json
│   └── regenerate_indicator_files_from_states.py   # No-DB regenerator: reads _fi_timeseries.json directly, applies broad fallback chain, writes public/indicators/*.json
│
├── validate_data.py                        # Automated data quality checks (7 validators)
├── DATA_COMPLETENESS.md                    # Coverage matrix: 9 indicators × 22 states
├── DATA_VALIDATION_REPORT.md               # Latest validation findings
├── AUDIT_REPORT.md                         # Full data-quality audit: staleness, outliers, missing states, refresh queue
└── SEO_CHECKLIST.md                        # One-time manual SEO steps (GSC verify, sitemap submit, Bing, backlinks)
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

### State-level focus (inset navigator)

Bottom-right of the main map renders a **clickable state navigator** (200×180 px Leaflet inset). Click any state to focus on it:

- **Main map** flies to state bounds (`flyToBounds` with padding 40)
- **Non-focus states** render in dim grey (18% opacity, `#d8d3ca` fill) — kept as visual context, not hidden
- **Color ramp** is recomputed from the focused state's distribution only, so within-state contrast pops (a moderate district nationally can show as the brightest in a poor state)
- **Legend label** is suffixed with state name, e.g. `"Total Deposits (₹ Lakhs) · Uttarakhand"`
- **"All India" reset button** appears beneath the inset, clears focus and flies back to all-India bounds
- **Click a dim state on the main map** also focuses it (alt entry path)
- **URL persistence**: `?state=<slug>` for shareable views; auto-applied on page load

**Files involved**:
- `scripts/build_state_bounds.py` — precomputes per-state bounds + LGD codes from `public/data/india_states.geojson` joined to `db/finer.db.states`. Output: `public/state-bounds.json` (11 KB, all 35 states/UTs).
- `public/state-bounds.json` — keyed by 2-letter state code (e.g. `UK`, `KA`), each entry has `bounds`, `centroid`, `lgd`, `slug`, `finer_name`.
- `public/data/india_states.geojson` — 35-feature state outlines used by both the inset and (potentially) the main map.
- All inset rendering + focus logic lives inline in `src/pages/index.astro` under the "Section 5a — State inset map" comment block.

**Event protocol**: a focus change dispatches a `finer:stateFilterChange` CustomEvent on `window` with `detail: { state: '<UPPERCASE STATE_UT>' or '' }`. The empty string means "All India". Both the inset click handlers and the URL-load logic dispatch this event; the main map's choropleth subscriber reads `bankingStateFilter` (a module-level variable) and rebuilds.

**Mobile**: inset is `display: none` on screens < 768px (existing top-bar legend layout prevails).

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

### Source citation (legend footer)

`MapLegend.svelte` renders a live citation under the colour ramp:
- **SLBC indicators**: `Source: SLBC <State> · <Quarter>` linking to the state's SLBC portal (e.g. `slbcrajasthan.in`). All-India view collapses to `Source: SLBC quarterly booklets · <Quarter>`.
- **PhonePe**: `PhonePe Pulse · <Quarter>` → `github.com/PhonePe/pulse`.
- **RBI / NRLM / NFHS / UIDAI / Capital markets / SHRUG**: full attribution with proper licence note (CC BY-NC-SA for SHRUG layers).

Centralised in `src/lib/indicator-sources.ts`. The legend listens for `finer:indicatorChange`, `finer:quarterChange`, `finer:stateFilterChange` events and re-derives the citation immediately. Long attribution shows on hover as `title` tooltip. **Do not add the per-state SLBC URL map anywhere else** — single source of truth.

### "A finding" feature (FactCard modal)

Vermillion **"A finding"** pill on `IndicatorStrip.svelte` (right side, before the ⌘K search) fires `finer:show-finding`. `FactCard.svelte` listens, fetches `public/findings.json` (25 verified entries, each backed by exact numbers from `public/indicators/*.json`), and shows a card with title, hero stat, lede, source, plus three actions:
- **Open in map** → fires `finer:indicatorChange` + `finer:quarterChange` + `finer:stateFilterChange` to deep-link the choropleth to the finding's `(indicator, quarter, state)`
- **Read the note** → `/fact/<slug>` (page doesn't exist yet — graceful 404)
- **Another →** → cycles through the 25 entries

To add a finding: edit `public/findings.json` directly (shape: `Finding` interface in `FactCard.svelte`). Also exists as typed TS in `src/lib/findings-data.ts` for programmatic use, but the JSON is canonical because the FactCard fetches it at runtime.

### SEO infrastructure

Code-side SEO ships through `BaseLayout.astro`:
- `<link rel="canonical">` per page (auto-derived from `Astro.url.pathname`)
- `og:url` matches canonical; `og:locale en_IN`
- Three JSON-LD blocks injected per page: `Organization`, `Dataset` (eligible for Google Dataset Search), `WebSite` with `SearchAction` (in-result search box pointing at `/ask/?q=...`)
- `PageLayout.astro` accepts a `description` prop and forwards to `BaseLayout` — used by 23 pages to surface unique snippets in Google results

Static helpers in `public/`:
- `sitemap.xml` — 25 canonical pages, hand-maintained (add new pages here too)
- `robots.txt` — allows HTML, disallows heavy data dirs (`/indicators/`, `/slbc-data/`, etc) so Google's crawl budget goes to indexable HTML
- `BingSiteAuth.xml` — Bing Webmaster Tools verification token

Manual steps (Google Search Console DNS verify, sitemap submit, URL Inspection, Bing) are documented in `SEO_CHECKLIST.md`.

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

**Currently available**: **31 states/UTs** — 8 NE states (Assam, Meghalaya, Manipur, Arunachal Pradesh, Mizoram, Tripura, Nagaland, Sikkim) + Bihar + West Bengal + Jharkhand + Odisha + Chhattisgarh + Kerala + Karnataka + Tamil Nadu + Rajasthan + Gujarat + Maharashtra + Haryana + Telangana + Uttarakhand + Andhra Pradesh + Madhya Pradesh + Uttar Pradesh + **Punjab** + **Himachal Pradesh** + **Jammu & Kashmir** + **Ladakh** + **Delhi** + **Goa**. All three analysis pickers (Trend Tracker, District Rankings, Data Explorer) share the same 31-state list. The 6 newly added entries above ship with narrower category coverage — most ship only `credit_deposit_ratio` + `branch_network` (Ladakh has only CD ratio for Mar 2026; Punjab covers priority-sector ACP only).
**NE Data Hierarchy (CRITICAL)**:
1. **`onlineslbcne.nic.in`** (online portal) = **PRIMARY/GOLD STANDARD** for all 8 NE states. This structured data must NEVER be overwritten by PDF extraction. It has cleaner, more reliable data.
2. **`slbcne.nic.in`** (PDF booklets) = **FALLBACK** — only used to fill gaps for data/categories not available on the online portal.
**NE Portal Source**: [onlineslbcne.nic.in](https://onlineslbcne.nic.in) — structured data for all 8 NE states
**NE PDF Source**: [SLBC NE - Meghalaya Booklets](https://slbcne.nic.in/meghalaya/booklet.php) — quarterly PDF booklets (fallback)
**Bihar Source**: [SLBC Bihar Agenda Papers](https://www.slbcbihar.com/SlBCHeldMeeting.aspx) (90th–95th meetings) + **95th Reference Book** (sep 2025 thicker extraction, 23k cells via `slbc-data/bihar/extract_bihar_95th_reference.py`) + **Dec 2025 XLSX** direct from `slbcbihar.com/documents/CD Ratio DW 31.12.2025.xlsx`. 82nd–89th are scanned images with unusable OCR and are currently excluded.
**West Bengal Source**: SLBC WB Agenda Papers (130th–171st meetings), PDFs stored in `slbc-data/west-bengal/`
**Jharkhand/Odisha Source**: NE-style extraction from respective SLBC booklets
**Chhattisgarh Source**: [slbcchhattisgarh.com](https://slbcchhattisgarh.com) (migrated May 2026 — dedicated site with per-meeting Excel data-tables, replaces old slbcne.nic.in fallback). 14 quarters (Sep 2022 → Dec 2025). v2 extractor: `slbc-data/chhattisgarh/extract_chhattisgarh_v2.py`.
**Kerala Source**: [SLBC Kerala](https://slbckerala.com) — annexure PDFs from meeting pages
**Karnataka Source**: [SLBC Karnataka](https://slbckarnataka.com) — annexure PDFs from meeting pages
**Tamil Nadu Source**: [SLBC Tamil Nadu](https://slbctn.com) — annexure PDFs from meeting pages
**Rajasthan Source**: [SLBC Rajasthan](https://slbcrajasthan.in) — Excel files (only **2 quarters** publicly available; older PDFs are scanned images, no archive). v2 extractor + audit: `slbc-data/rajasthan/extract_rajasthan_v2.py`, `meetings_audit.txt`.
**Gujarat Source**: [SLBC Gujarat](https://slbcgujarat.in) — ZIP archives per meeting. **36 quarters** (Mar 2017 → Dec 2025) extracted via `slbc-data/gujarat/extract_gujarat_v2.py` (recursive ZIP walker, handles 8 different sheet-naming conventions across years).
**Maharashtra Source**: [Bank of Maharashtra SLBC](https://bankofmaharashtra.bank.in) — PDFs (values in Crores, converted to Lakhs at extract time — already in canonical ₹ Lakhs in our DB)
**Haryana Source**: [SLBC Haryana (PNB)](https://slbcharyana.pnb.bank.in) — Excel/Excel-XLS files. **37 quarters** (Dec 2014 → Dec 2025) via `slbc-data/haryana/extract_haryana_v2.py`. ×100 Crore→Lakh conversion in `is_monetary_field()`. Two source quarters (156th, 160th) label values "Crores" but actually print in Lakhs — auto-detected when median deposit > 100k Cr.
**Telangana Source**: [SLBC Telangana](https://telanganaslbc.com) — PDFs
**Uttarakhand Source**: [SLBC Uttarakhand](https://slbcuttarakhand.com) — PDFs (76th–88th meetings extracted; 61st–75th excluded due to Devanagari font encoding / unusable OCR)
**Andhra Pradesh Source**: archived PDFs on Wayback Machine (`web.archive.org/web/2025*/slbcap.nic.in`) — see dedicated section below
**Madhya Pradesh Source**: [slbcmadhyapradesh.in](https://www.slbcmadhyapradesh.in/slbc-meeting.aspx) — Excel data-tables per meeting. 6 quarters (Mar 2020 + Sep 2023 → Dec 2025) via `slbc-data/madhya-pradesh/scrape_mp_archive.py` + the XLSX parser inline. **MP SLBC publishes district-level data ONLY for CD ratio** — all other metrics are bank-wise. Branch counts for MP come from the RBI Banking Outlets snapshot indicator instead.
**Uttar Pradesh Source**: [slbcup.com](https://slbcup.com) — agenda PDFs. **25 quarters** (Mar 2019 → Dec 2025) via `slbc-data/uttar-pradesh/extract_uttar_pradesh.py` (pdftotext + linear-time tokenizer; see UP Data Pipeline section). Source values in **Crores** — ×100 conversion already applied to `credit_deposit_ratio__total_deposit` / `total_advances` / `total_advance` / etc. for `state_lgd_code=9`.

**Coverage**:
- Quarters range from March 2018 to December 2025 (varies by state — not all states have every quarter)
- 48 indicator categories per quarter for NE (for 2022 onwards; 2021 has fewer); 49 categories for WB
- All monetary values in **Rs. Lakhs** (1 Lakh = ₹100,000)

**State data availability** (latest quarter):
| State | Latest Quarter | Total Quarters | Districts |
|-------|---------------|----------------|-----------|
| Assam | Sep 2025 | 30 | 35 |
| Manipur | Sep 2025 | 39 | 16 |
| Tripura | Dec 2025 | 35 | 8 |
| Bihar | Sep 2025 | 6 | 38 |
| West Bengal | Dec 2025 | 39 | 23 |
| Mizoram | Sep 2025 | 22 | 11 |
| Meghalaya | Sep 2025 | 15 | 12 |
| Arunachal Pradesh | Mar 2025 | 18 | 26 |
| Nagaland | Mar 2025 | 7 | 16 |
| Sikkim | Mar 2025 | 4 | 6 |
| Jharkhand | Sep 2025 | 10 | 24 |
| Odisha | Dec 2025 | 8 | 30 |
| Chhattisgarh | Dec 2025 | 14 | 33 |
| Kerala | Dec 2025 | 23 | 14 |
| Karnataka | Jun 2025 | 7 | 31 |
| Tamil Nadu | Dec 2025 | 10 | 38 |
| Rajasthan | Dec 2025 | 2 | 41 |
| Gujarat | Dec 2025 | 36 | 33 |
| Maharashtra | Dec 2025 | 3 | 36 |
| Haryana | Dec 2025 | 37 | 22 |
| Telangana | Dec 2025 | 13 | 33 |
| Uttarakhand | Dec 2023 | 14 | 13 |
| Andhra Pradesh | Jun 2024 | 20 | 26 |
| Madhya Pradesh | Dec 2025 | 6 | 55 |
| Uttar Pradesh | Dec 2025 | 25 | 75 |

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

**25 Indicators**: Credit-Deposit Ratio, PM Jan Dhan Yojana, Branch Network, Kisan Credit Card, Self Help Groups, Digital Transactions (PhonePe UPI), Aadhaar Authentication, Banking Infrastructure (RBI), Social Security (Atal Pension), PMEGP, Housing/PMAY, Stand Up India, SC/ST Lending, Women's Credit, Education Loans, MUDRA/PMMY, NRLM SHG, RBI BSR Credit, **Health Insurance (NFHS)** — moved to Insurance category, Capital Markets Access, **PMSBY (Accident Insurance)** + **PMJJBY (Life Insurance)** — Insurance category, Aadhaar Enrollment (UIDAI), Meta RWI, PMGSY Roads, VIIRS Nightlights, **Elevation & Terrain Ruggedness (SRTM)**, **Agricultural Land Use & Irrigation (Census 2011 VD)**.

**7 picker categories** (in `ATLAS_CATEGORIES`):
- Banking Infra · Credit · Schemes · Payments · **Insurance** · Capital Markets · Demographics

Category renames during the Atlas refinement (May 2026): Banking → "Banking Infra", Digital → "Payments". A dedicated **Insurance** category was carved out — PMSBY (was Schemes), PMJJBY (was Schemes), Health Insurance NFHS (was Demographics) all moved in. APY (pension) stays in Schemes.

**800+ districts across 36 states/UTs**

**Key architecture decisions**:
- Leaflet core (tile layer, GeoJSON, flyTo, tooltips) kept as inline JS (`<script is:inline>`) in `index.astro` — UI panels are Svelte components connected via `finer:*` event bus (see above)
- **Progressive loading**: on page load only fetches `indicators/manifest.json` (748B) + `district_lgd_codes.json` (138KB); indicator data (~50-100KB per file) fetched on demand when indicator/quarter changes. No longer loads all 22 state timeseries JSONs. See [Progressive Loading](#progressive-loading-indicators) section.
- Uses `normalizePeriod()` to convert "June 2020" → "2020-06" for sorting
- `preferCanvas: true` prevents SVG pixelation during `flyTo` animations
- `zoomSnap: 0` enables fractional zoom so `fitBounds` fills the content area optimally (e.g. zoom 5.22 instead of rounding down to 5)
- India outline GeoJSON simplified with Douglas-Peucker (`tolerance=0.001`, `preserve_topology=True`)

**Map bounds** (expanded for all-India coverage including J&K/Ladakh):
- `ALL_STATES_BOUNDS`: `L.latLngBounds(L.latLng(6.5, 67.5), L.latLng(37.5, 98))` — full India incl. J&K/Ladakh (north ~37.1°N) + Kutch + A&N (south ~6.75°N)
- Desktop `maxBounds`: `L.latLngBounds(L.latLng(2, 50.0), L.latLng(46, 115.0))` — north widened to 46°N so the +72 strip-padding can actually slide content down (with the old 40°N max, `_limitCenter` clamped any padding above ~12px → silent no-op)
- Mobile `maxBounds`: `L.latLngBounds(L.latLng(0, 48.0), L.latLng(45, 115.0))` — kept conservative; bigger numbers added empty whitespace above India on phones
- `flyToNE()` uses `flyToBounds(ALL_STATES_BOUNDS)` on both mobile and desktop
- **Top padding** (`getPanelPadding()`): mobile = header+strip+12, desktop = header+strip+**72** (the latter is needed for J&K/Ladakh's northern fingers to clear the strip's bottom edge; lower values like +36 silently no-op due to maxBounds clamping)

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
- **Indicator → Sub-metric** dropdowns (replaced the 30-pill row in May 2026). Default indicator auto-picks the first available so the page lands on a populated view; picking a specific sub-metric auto-expands its Plotly chart, eliminating the "scroll past 80 cards to reach the chart" pain.
- Click-to-expand any card → loads full Plotly time series chart via dynamic import
- Uses `flattenTimeseries()` and `normalizePeriod()` from inline helpers

#### Pre-built Insights (`/analysis/insights/`)
- **Removed from analysis sub-nav** — page still exists at `/analysis/insights/` but not linked from navigation
- 13 curated data stories with real numbers from SLBC timeseries
- Data defined in `src/lib/insights-data.ts`

## Bihar Data Pipeline

Bihar SLBC data was extracted separately from the NE states:

**Source PDFs**: 12 PDFs in `slbc-data/bihar/` covering the 82nd–95th meetings (`82nd_agenda.pdf` through `95th_agenda.pdf`)
- **Only 6 are actually extracted** — `extract_bihar_v2.py` (line 704) whitelists only the 90th–95th meetings (Jun 2024 → Sep 2025), because those are text-native PDFs
- The 82nd–89th PDFs are scanned images; OCR'd versions had poor quality and are deliberately commented out in the script
- SSL certificate errors on the source site required `curl -sk` (insecure flag)
- To extend coverage backwards, the 82nd–89th PDFs would need re-OCR with a higher-quality engine (Google Document AI, Azure Form Recognizer, or Claude-assisted OCR) before they can be ingested

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

**Data coverage**: 6 quarters from June 2024 to September 2025, 38 districts. (Older meetings exist as scanned PDFs but are not yet extracted — see Source PDFs above.)

## Uttarakhand Data Pipeline

Uttarakhand SLBC data uses a dedicated extractor because its tables have an unusual structure: **each district-wise table contains multiple quarters side-by-side as columns** (e.g. "March 2021 | March 2022 | March 2023 | Dec 2023" all within a single row of Dehradun's values).

**Source PDFs**: 27 PDFs in `slbc-data/uttarakhand/` covering the 61st–88th meetings. Of these, **only 11 are text-native and extracted** (`76th`, `77th`, `78th_spl`, `79th`, `82nd`, `83rd`, `84th_spl`, `85th`, `86th`, `87th`, `88th`). The 16 older PDFs (61st–75th) use custom Devanagari font encoding that yields `(cid:XX)` garbage from pdfplumber; recovering them would require a Devanagari OCR pipeline.

**Extraction script**: `slbc-data/uttarakhand/extract_uttarakhand.py`
- Uses pdfplumber; parses up to 3 header rows to build `column → (category, metric, quarter)` mappings, then emits one record per `(district, quarter)` per table
- Filters out noise-date matches (years <2018 or >2024 from misread prose/page numbers)
- Canonicalizes 13 district aliases: `Hardwar/Hardwar (A)/Haridwar (Asp.)` → `Haridwar`, `U.S. Nagar (A)/Udham Singh Nagar (A)` → `Udham Singh Nagar`, `Tehri` → `Tehri Garhwal`, etc.
- Converts Crore amounts to Lakhs (×100) based on "Cr." / "Crores" hints in table headers
- When the same (district, quarter, field) appears in multiple PDFs, prefers the most recent booklet (88th > 87th > ... > 76th)

**Field standardization**: After extraction, a post-pass renames UK-specific field names to canonical SLBC names that `db/export_indicator_files.py` expects:
- `pmjdy__no_of_active_pmjdy_a_c` → `pmjdy__total_pmjdy_no`
- `pmjdy__no_of_pmjdy_accounts_female/male` → `pmjdy__female_no/male_no`
- `shg__shg_credit_linked_no` → `shg__credit_linked_no`
- `shg__total_no_of_shg` → `shg__savings_linked_no`

**District aliases in SQLite**: The DB has typo'd or differently-spaced UK district names (`Udam Singh Nagar` is missing an 'h', `Rudra Prayag` is spaced, `Uttar Kashi` is spaced). 11 aliases are registered in `district_aliases` to resolve extractor output to the right LGD codes.

**Data coverage**: 14 quarters from March 2019 to December 2023, 13 districts. 7 of 14 quarters are fully populated across the 6 FI categories present in UK source (credit_deposit_ratio, pmjdy, branch_network, kcc, shg, digital_transactions); 4 quarters are sparse due to short agenda booklets. Aadhaar authentication is not present as a separate category in UK source — the frontend's existing `CROSS_CATEGORY_FALLBACKS` maps `aadhaar_authentication → pmjdy` which is where UK's aadhaar seeding/OD data lives anyway.

**Branch counts caveat**: Most UK tables report branches as **"per lakh population" ratios** (e.g. 37 branches/lakh for Dehradun) rather than absolute totals. Only the March 2021 quarter has a table with absolute `total_branch` counts. Other quarters' `branch_network` tables surface ratio metrics, not absolute counts — users should interpret this accordingly when comparing UK to other states.

**Running extraction**:
```bash
cd slbc-data/uttarakhand/
python3 extract_uttarakhand.py
# Outputs: uttarakhand_complete.json, uttarakhand_fi_timeseries.json, uttarakhand_fi_timeseries.csv, quarterly/*/*.csv
# Then: cp outputs to public/slbc-data/uttarakhand/
# Then: DELETE from slbc_data WHERE source_file='uttarakhand'; re-run import_slbc for UK
# Then: python3 db/export_indicator_files.py
```

## Telangana Data Pipeline

Telangana SLBC data uses an unusual extraction path: the **CQR (Comprehensive Quarterly Return) Annexure PDFs**, not the SLBC agendas. The agenda PDFs reference "Annexure-B" for district-wise CD ratio but don't bundle the annexure (a structural difference from AP's agendas, which include district-wise data inline). The CQR Annexures live on a separate page at `telanganaslbc.com/reports.aspx` and contain the clean district-wise tables.

**Source page**: [telanganaslbc.com/reports.aspx → "Quarterly - Comprehensive Quarterly Return"](https://telanganaslbc.com/reports.aspx) — 40+ CQR Annexure PDFs going back to Dec 2015.

**Currently extracted**: 14 PDFs covering Dec 2022 → Dec 2025 (cqr_2022-12.pdf through cqr_2025-12.pdf). Older CQR PDFs (Dec 2015 → Sep 2022) downloadable from same page if backfill is wanted.

**Extraction script**: `slbc-data/telangana/extract_telangana_cqr.py` (~280 lines). Per CQR PDF, processes 5 district-wise annexures:
- Annexure-2 (`branch_network`): Rural/Semi-Urban/Urban/Total branch counts per district
- Annexure-4 (`credit_deposit_ratio`): Branch + Deposits/Advances by area-type + CD ratio
- Annexure-6 (`priority_sector`): Priority Sector Advances breakdown (Crop Loan, Term Loan, Agri-infra, MSME, Education, Housing, etc.)
- Annexure-8 (`non_priority_sector`): Non-priority advances
- Annexure-10 (`acp_achievement`): ACP target vs achievement

PMJDY, KCC, SHG, MUDRA are bank-wise only in CQR (Annexures 17, 18, 19, etc.) — not district-wise. Those would need a separate path (likely the standalone SLBC agendas, which sometimes include them, or RTI for the missing district annexures).

**Rotated-page handling** (Jun 2025 + Sep 2025 PDFs): The CD ratio + Priority Sector pages in those two CQRs are laid out 180° rotated. Cell text is character-reversed (`DABALIDA` = `ADILABAD` reversed) and the table grid is transposed (rows ↔ columns swapped). Extractor detects this via the `_is_reversed_page()` heuristic (looks for "ERUXENNA" / "ANAGNALET CBLS" markers) and applies a transpose + cell-reversal pass. Branch network on these PDFs extracts cleanly; CD ratio on the same PDFs partially recovers but Jun + Sep 2025 still drop CD ratio. The other 11 quarters extract cleanly across all 4 categories.

**District canonicalization**: 33 modern Telangana districts (post-2019). Aliases handle uppercase variants from PDF text plus historical naming changes:
- `JAGTIAL` / `JAGTIYAL` → `Jagitial`
- `WARANGAL URBAN` → `Hanumakonda` (post-2021 rename)
- `WARANGAL RURAL` → `Warangal`
- `RANGAREDDY` / `R.R.` → `Ranga Reddy`
- `KUMARAM BHEEM` / `ASIFABAD` → `Kumuram Bheem Asifabad`
- `MEDCHAL` (alone) → `Medchal Malkajgiri`
- Plus standard variations on multi-word names

**Coverage**:
- `branch_network`: 13/13 quarters (Dec 2022 → Dec 2025), all 33 districts
- `credit_deposit_ratio`: 11/13 quarters (Jun + Sep 2025 missing due to rotation issue)
- `priority_sector`: 11/13 quarters
- `non_priority_sector`: 11/13 quarters

Total: 26,280 rows in `slbc_data` (was 99 before this extraction).

**Future improvements**:
- Fix the rotated-page CD ratio extraction for Jun + Sep 2025
- Backfill from older CQR PDFs (Dec 2015 → Sep 2022, ~26 more quarters available)
- Cross-reference SLBC agendas (36th–48th in `slbc-data/telangana/*_agenda.pdf`) for any district-wise PMJDY/KCC/SHG tables not in the CQRs

## Andhra Pradesh Data Pipeline

Andhra Pradesh SLBC data, comprehensively backfilled across three district-structure eras: post-2014 split (13 districts, 2018-2022) and post-2022 reorganization (26 districts, 2022-2024). Pre-2014 united-AP era is **not** present — the available archived PDFs from that period (166-201, ~2009-2014) only contain bank-wise CD ratio in narrative format, not district-wise tables.

**Source**: The live `slbcap.nic.in` is currently unreachable. ~52 PDFs were downloaded via the Wayback Machine using the `id_/` raw-content URL pattern at the `20250815` snapshot timestamp. CDX query for discovery:
```
https://web.archive.org/cdx/search/cdx?url=slbcap.nic.in&matchType=domain&filter=mimetype:application/pdf
```

**Extraction script**: `slbc-data/andhra-pradesh/extract_andhra_pradesh.py` (~700 lines). Handles the 47-meeting `MEETING_QUARTER` mapping with explicit per-meeting quarter codes (the relationship between meeting number and reported quarter isn't a simple linear mapping — special meetings, missed quarters, and meeting-date-vs-quarter-end offsets all required hand-tuning).

**Coverage**: 20 quarters from June 2018 to June 2024. 1,229 rows in `slbc_data`. Categories:
- `credit_deposit_ratio`: all 20 quarters (12-26 districts each)
- `branch_network`, `priority_sector`, `annual_credit_plan`: 3 quarters each (2020-09, 2021-06, 2021-12 — the meetings that publish a fuller data appendix)
- `shg`: 1 quarter (2019-06)

**Quarter gaps in coverage** (PDFs that were truncated by Wayback or the meeting wasn't archived):
- 2018-09 (205_agenda.pdf — corrupt, EOF error)
- 2018-03 (203 reports same; would only differ if a separate PDF existed)
- 2019-12 → 2020-06 (truncated 9-page archives)
- 2020-12, 2021-03 (missing meetings)
- 2022-06 (220th meeting not in archive)

**District canonicalization** — the AP region has had 3 district structures over time:
- **Pre-2014 (United AP, 23 districts)**: covered both modern AP + 10 Telangana districts. Extractor's `DISTRICT_ALIASES` dict registers all of these and routes per-district to the appropriate `state_slug` (`andhra-pradesh` or `telangana`). However, no extractable district-wise tables were found in the available pre-2014 PDFs from the Wayback archive — they only carry bank-wise summaries. The dual-state plumbing is in place if better source PDFs are obtained later.
- **2014-2022 (13 modern AP districts)**: Anantapur, Chittoor, East Godavari, Guntur, Krishna, Kurnool, Prakasam, Nellore (canonical: Spsr Nellore), Srikakulam, Visakhapatnam (DB has typo: `Visakhapatanam`), Vizianagaram, West Godavari, YSR/Cuddapah/Kadapa (canonical: `Y.s.r.`)
- **2022+ (26 modern AP districts)**: above 13 plus Alluri Sitharama Raju, Anakapalli, Annamayya, Bapatla, Eluru, Kakinada, Konaseema (full name in PDFs: "Dr. B.R.Ambedkar Konaseema"), Nandyal, NTR (canonical: `Ntr`), Palnadu, Parvathipuram Manyam, Sri Sathya Sai, Tirupati

Aliases registered for ~30 spelling/naming variants ("Ananthapuramu" / "Cuddapah" / "Visakhapatnam" / "Mahabubnagar" / etc.) — see `_add()` calls in the extractor.

**Field standardization**: AP's older PDFs (223rd, 224th) use the field name `Convener CD Ratio` which gets snake-cased to `convener_cd_ratio` and then renamed to canonical `cd_ratio` so it matches `db/export_indicator_files.py`'s fallback list.

**Classification fallbacks**: AP page titles are often garbled by overlapping rotated text (e.g. "SL2B.3C D oifs AtrPic t w i s e p o s i t i o n o f C D21 r7a th t Mioe aetsi nogn"). When the page-title classifier returns None, the script falls back to classifying based on the table's own header rows. A `REJECT` sentinel prevents fall-through from header-rejection (e.g. RSETI/SSA tables) into page-text classification on the same page.

**Bank-wise table filter**: `is_bankwise_table()` rejects tables whose first 3 columns match common bank names (SBI, BoB, HDFC, etc.) — filters out per-bank summaries that would otherwise pollute district-wise outputs.

**Min-districts threshold**: Tables with fewer than 10 unique resolved districts after dedup are dropped. Filters out misclassifications like "list of villages without brick-and-mortar branch" tables (rows are villages, same district repeated — only ~5 unique districts).

**Telangana pre-2014 routing**: Extractor's `DISTRICT_ALIASES` dict maps 10 Telangana district aliases to `(district, 'telangana')` tuples. The output writer creates `slbc-data/andhra-pradesh/telangana_pre2014_*.json` files when district-wise pre-2014 data is found. Currently empty — see "no extractable pre-2014 data" caveat above.

**Future improvements**:
- The 220th meeting (Jun 2022) and several Sep 2018-Mar 2021 quarters are missing — could be filled if better PDF sources surface
- Pre-2014 era (1990s-2014) requires a different source; SLBC AP minutes/proceedings might have district-wise summaries that the agendas omit

**Indicator coverage caveats** (significant — AP is much narrower than NE states):
- **PMJDY: 0 quarters** — source agendas don't break out PMJDY by district
- **KCC: 0 quarters** — same; AP agendas only report state-level KCC totals
- **branch_network: 3 quarters only** (Sep 2020, Jun 2021, Dec 2021) — most quarters lack absolute branch counts
- **SHG: 1 quarter only** (Jun 2019)
- **digital_transactions: 0 quarters** — but AP shows up on the homepage's digital indicator via PhonePe (pan-India source), not SLBC
- AP is essentially a **CD-ratio-only state** in our data. 20 quarters CDR vs Assam's 35-quarter cross-indicator coverage. Cross-state comparisons should use CDR.

**Known data fixes applied**:
- AP 2020-09 originally had 7 districts (Krishna, Guntur, Prakasam, Spsr Nellore, Chittoor, Y.s.r., Kurnool) with bogus CD ratios of 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 13.0 — these were the row's S.No. column misaligned as `cd_ratio` in the 213th meeting PDF's multi-table page. Patched post-extraction by deleting those 7 specific (district, period, field) records. The 5 remaining 2020-09 districts (East Godavari, Srikakulam, Visakhapatanam, Vizianagaram, West Godavari) have correct values in the 93-200% range.
- East Godavari Jun 2021 `priority_sector__agr_infra`: extractor pulled `236.33` (an unrelated row), corrected to `126.20` (the value verified against the 216th meeting PDF page 10). Patch applied to both `slbc-data/andhra-pradesh/*.json` and `public/slbc-data/andhra-pradesh/*.json`.

**Validation flags currently unresolved (real PDF values, not bugs)**:
- East Godavari `priority_sector__export` Dec 2021 drop to 0.03 (from 89.12 in Jun 2021) — value is correct in source PDF
- Spsr Nellore + Y.s.r. `priority_sector__export`/`ancillary` Dec 2021 large drops — confirmed correct in source PDFs
- Visakhapatanam `branch_network__branch_urban` Dec 2021 = 38 (from 451 in Sep 2020) — correct in source; 451 was likely the all-area sum (a different field), 38 the urban-only count.

## Uttar Pradesh Data Pipeline

**Live** — 25 quarters across 18 categories, 34k+ rows in `slbc_data` for `state_lgd_code=9`. UP is FINER's 25th state and was the highest-priority missing-SLBC slot (240M pop, 75 districts).

**Source**: [slbcup.com](https://slbcup.com) agenda PDFs. 26 quarterly booklets covering Mar 2019 → Dec 2025 (2025-Q1 = `2025-03_booklet.pdf` is corrupt — pdftotext XRef errors, source-file issue not extractor — and 2025-Q2 was never published by the source).

**Extractor**: `slbc-data/uttar-pradesh/extract_uttar_pradesh.py`. 75-district canonical list + heavy alias map covering OCR artefacts (Allahabad→Prayagraj, Faizabad→Ayodhya, Lakhimpur Kheri→Kheri, "Sonebhadra"→Sonbhadra, "Avraiya"→Auraiya, etc.).

**Two extractor design decisions resolved during build**:
1. **pdftotext (poppler), NOT pdfplumber.** pdfplumber's per-page `extract_text()` on the 100 MB OCR'd UP booklets took ~1 hour per file. `pdftotext -layout` via subprocess does the whole file in ~0.3s — ~12,000× faster. Wall-clock pipeline runtime dropped from "would never complete" to 13.5s for all 26 PDFs.
2. **Linear-time tokenizer, NOT a single combined regex.** The original `parse_data_row()` regex `^\s*(\d{1,3})\s+([A-Za-z…]{2,40}?)\s+((?:[+-]?\d+(?:[\.,]\d+)?\s*){2,})\s*$` had catastrophic backtracking on prose lines that almost-but-not-quite looked like data rows — would CPU-loop indefinitely. Replaced with a per-token validator: split on whitespace, validate each token with anchored `fullmatch` against tiny patterns (`_SNO_RE`, `_NUM_RE`, `_WORD_RE`), then walk: token 0 = sno, walk word tokens to first numeric (capped at 6), remaining must all be numeric/gap markers. Hard caps: line length ≤400 chars, token count ≤60. Also bounded `classify_page` input to 6000 chars.
3. **Per-PDF 60s wall-clock timeout** via `multiprocessing.Pipe` worker (`_run_extract_with_timeout`); failing PDFs are skipped, not fatal. Per-PDF flushed progress prints.

**Critical bug fixed (May 2026)**: original UP extractor had **sticky `current_cat` across pages** — once a page classified as `credit_deposit_ratio`, every subsequent page's `<sno> <district> <num> <num>` rows got accumulated as CD-ratio data even if those pages were about Pending RC / RSETI / etc. Result: Agra Dec 2025 was being stored as `dep=10899 adv=172.65` (from the Pending RC table) which became a bogus 1.5% derived CD ratio. **Fix in `extract_pdf`**: each PDF page must self-classify; `credit_deposit_ratio` pages need ≥10 plausible district rows before commit (rejects title pages, partial bleeds). After the fix, Agra 2024-03 cleanly reads dep=57878 adv=39724 cdr=68.63% — exactly matches the source PDF.

**UNIT CAVEAT**: UP's source booklets carry CD-ratio amounts in **Crores** (the table header says "Amount in Crore"). FINER's canonical unit is **₹ Lakhs**, so `credit_deposit_ratio__total_deposit` / `total_advances` / `total_advance` / etc. for `state_lgd_code=9` are stored after **×100 conversion** to Lakhs. Verified: Lucknow Dec 2024 deposit = ₹28.3M Lakhs = ₹2.83 lakh Cr, in line with other major-city deposits.

**UP 2025-09 + 2025-12 CD-ratio empty**: those quarters' CD-ratio tables have rows split across 2 visual PDF lines (deposits on one line, advances+ratio on the next, district name dangling separately). pdftotext can't reconstruct them. Other categories (PMJDY, MUDRA, SHG, etc.) extract fine for those quarters — only the CD-ratio table has this layout.

**Period-label normalization**: the extractor emits some quarters as `"2023-06"` (raw code) vs older quarters as `"June 2023"` (labeled). `import_slbc.py`'s `normalize_period` expects "Month YYYY" — a post-process pass converts the raw-format labels before import (~9 quarters affected per run). Bake this into the extractor in a future iteration.

## Madhya Pradesh Data Pipeline

**Live** — 6 quarters of district-wise Credit-Deposit Ratio, 55 districts. MP is FINER's 24th state (added before UP).

**Source**: [slbcmadhyapradesh.in](https://www.slbcmadhyapradesh.in/slbc-meeting.aspx) — the MP SLBC publishes clean per-meeting **XLSX data-tables** going back to ~2017 (much cleaner than PDF extraction). The site lists 197 meetings (Dec 2007 → Mar 2026); only the recent 6 ship the district-wise CD-ratio sheet in the format we parse.

**Pipeline**:
- `slbc-data/madhya-pradesh/scrape_mp_archive.py` — walks `/slbc-meeting.aspx`, finds direct XLSX links matching `Slbc-data-{mmm}{yy}-final-*.xlsx`, downloads to `slbc-data/madhya-pradesh/raw/`.
- Inline parser (in the import script) — reads each XLSX's `CD Ratio_3(ii)Dist` sheet, requires `district name` substring in header row (avoids the row-0 title trap "DISTRICT WISE CD RATIO" which also contains those words), extracts `District | Deposits | Advances | CD Ratio` columns.

**Quarters extracted**: Mar 2020, Sep 2023, Mar 2024, Jun 2024, Sep 2025, Dec 2025 — 51-55 districts each (reflects MP's 2023 reorg adding Maihar, Mauganj, Pandhurna).

**3 new districts registered**: Maihar (lgd 779, carved from Satna 2023), Mauganj (780, from Rewa 2024), Pandhurna (781, from Chhindwara 2023). Aliases added: Hoshangabad → Narmadapuram (2022 rename), Agar-malwa → Agar Malwa.

**MP IS A CD-RATIO-ONLY STATE in our data**. The XLSX has 36 sheets but only `CD Ratio_3(ii)Dist` is district-wise — every other sheet (Branches/ATMs, PMJDY, KCC, SHG, MUDRA, PMEGP, PMAY, Aadhaar) is bank-wise (rows = banks). For "branches per MP district" use the `rbi_banking_outlets` snapshot indicator, not `branch_network`.

**Parallel slbcup.com pages** (`CDRatioDistrict.aspx`, etc.) are mostly placeholders, so the agenda PDFs are the canonical UP source.

## Tripura Data Pipeline

Tripura SLBC data was fully re-extracted from source PDFs hosted at `slbctripura.pnb.bank.in/Back_Paper_Quarterly.asp` (PNB is the SLBC convenor for Tripura). The previous data came from a mixture of NE-portal scraping (sparse coverage of older quarters) and partial PDF extraction.

**Source PDFs**: 30 PDFs in `slbc-data/tripura/` covering the 125th–154th SLBC meetings (Jun 2018 → Dec 2025). Naming convention: `{N}{th|st|nd|rd}_{month3}{year}.pdf` (e.g. `131st_dec2019.pdf`, `154th_dec2025_agenda.pdf`).

**Extraction script**: `slbc-data/tripura/extract_tripura.py` (~700 lines, modelled on `extract_uttarakhand.py`).
- Uses pdfplumber. Tripura's recent agendas use the same multi-quarter-per-table format as UK (e.g. CD ratio table in 154th has 5 quarter columns: Dec 2024 → Dec 2025 plus Q-o-Q and Y-o-Y delta columns — the deltas are skipped during parsing).
- Skips non-data tables: TOC pages, bank-wise (vs district-wise) summaries, "ATM allocation by block" rosters, garbled rotated-text artefacts, "Q-o-Q change" / "Y-o-Y change" delta columns.
- Recognises 8 Tripura districts (Dhalai, Gomati, Khowai, North Tripura, Sepahijala, South Tripura, Unakoti, West Tripura) plus aliases like "Sipahijala" and "Dhalai Total" suffix-stripping.
- Quarter de-duplication: same `(district, quarter, field)` may appear in multiple PDFs (e.g. Dec 2024 appears in 5 different tables across 150th-154th); always uses the most recent meeting's value.
- Pulls 3 historical quarters (Mar/Sep/Dec 2017) from multi-quarter tables in the older PDFs that weren't previously extracted.

**Field standardization**: Same canonical-rename pattern as UK. The most impactful renames apply to digital_transactions where TR's verbose field names like `coverage_with_at_least_one_of_the_digital_modes_of_payment_..._pct_coverage` map to `coverage_sb_pct`. CD ratio's `overall_cd_ratio` is already canonical.

**Data coverage**: 35 quarters from March 2017 to December 2025, 8 districts. CD ratio in all 35 quarters; digital_transactions in 11; branch_network in 14; PMJDY in 9; KCC in 7; SHG in 7. Aadhaar authentication absent (frontend cross-category fallback maps to PMJDY).

**KCC caveat**: Tripura PDFs report KCC by **crop season** (Kharif loanee/non-loanee, Rabi loanee/non-loanee), not by cumulative card count. So `kcc__total_no_of_kcc` (the canonical primary field for the KCC indicator) is not populated — TR districts won't appear on the KCC indicator on the homepage. Consider this a structural source limitation rather than an extraction bug.

**Branch caveat (Dec 2025 only)**: The 154th meeting agenda doesn't include absolute branch counts — only BC coverage percentages. Same UK-style caveat. Earlier Tripura quarters (134th-153rd) do have absolute branch_network counts.

**Where the source files live**: `~/Downloads/slbc_tripura_pdfs/` is the original local download cache; for the pipeline they're consolidated into `slbc-data/tripura/` (untracked per `.gitignore` convention).

**Indicator coverage caveats** (TR is sparser than NE-portal states):
- CD ratio: all 35 quarters ✅
- branch_network: 14 quarters
- digital_transactions: 11 quarters
- PMJDY: 9 quarters
- KCC: 7 quarters (reported by crop season only — see KCC caveat above)
- SHG: 7 quarters
- Compare to Assam: 23-35 quarters per indicator. TR's recent agendas (2024+) have shrunk to mostly CD ratio + some digital coverage; historical PMJDY/KCC/SHG coverage was better in 2018-2022 era.

**Field-name pollution cleanup**: TR's `digital_transactions` originally had **114 distinct field names** (many >150 chars long) because the multi-row table headers got concatenated into snake_case keys. Post-extraction prune dropped fields with names >50 chars, retaining the canonical ones (`coverage_sb_pct`, `digital_coverage_sb_a_c`, `total_operative_sb_a_c`) plus reasonable-length fallbacks. Result: 14 distinct field names in DB. Patch is applied at the timeseries JSON level, not the extractor — running `extract_tripura.py` fresh would re-introduce the pollution (would need to bake the prune into the extractor in a future iteration).

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

**No-DB regenerator**: `db/regenerate_indicator_files_from_states.py` is the **canonical path** for rebuilding `public/indicators/*.json` without rebuilding the SQLite DB. It reads each state's `_fi_timeseries.json` directly and applies a much broader category + field fallback chain than `db/export_indicator_files.py` does — covering aliases like `housing_finance`, `housing_loan`, `pmegp_3/4`, `stand_up_india_p2`, `pmmy_mudra`, `mudra_2`, `apy_2`, plus singular/plural field-name variants (`shishu_account` vs `shishu_no`, `pmjdy_total_ac` vs `total_pmjdy_no`, etc.). Run after extending any state's extractor or fixing a field-name bug:
```bash
python3 db/regenerate_indicator_files_from_states.py                       # all 15 SLBC indicators
python3 db/regenerate_indicator_files_from_states.py social_security pmegp # specific indicators
```
The script refuses to write `digital_transactions` quarters that lack PhonePe `transaction_count`/`_amount` (so the headline UPI metric never goes silently missing). PhonePe Pulse currently ceilings at Mar 2024.

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

**Upstream staleness**: PhonePe Pulse currently ships through **Mar 2024** (Q4 FY24) only. Quarters 2024-06 onwards have NO PhonePe data, only SLBC-side digital-coverage fields. The regenerator script refuses to write `digital_transactions` quarter files that lack PhonePe data; selecting Dec 2025 + Digital Transactions falls back automatically to Mar 2024 via the homepage's quarter-fallback chain (window widened to 12 quarters so the 7-quarter gap resolves cleanly). The italic "Data from Mar 2024" hint appears on tooltips. Nothing to do until upstream Pulse refreshes.

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

## SHRUG-derived Indicators

**Five** indicators sourced from the **SHRUG v2.1** dataset (Socioeconomic High-resolution Rural-Urban Geographic Platform, Development Data Lab — devdatalab.org/shrug). Licence: **CC BY-NC-SA 4.0** — non-commercial, requires attribution.

All five share the same join pattern: SHRUG's `(pc11_state_id, pc11_district_id)` (zero-padded 2- and 3-digit) → FINER `(state_lgd, census_2011_code)` after stripping leading zeros. ~98% match rate.

**Shared helper**: `db/shrug/_shared.py` — `build_finer_lookup()` returns the join dict and handles **post-Census-2011 state splits** via `PC11_STATE_ALIASES`:
- Telangana (lgd 36) ← Andhra Pradesh's PC11 code "28" (carved June 2014)
- Ladakh (lgd 37) ← Jammu & Kashmir's PC11 code "01" (carved October 2019)

Without this aliasing, Telangana + Ladakh polygons rendered grey on every SHRUG indicator even though the data sat right there under the parent state's PC11 code. Pre-Census-2011 splits (Chhattisgarh 2000, Jharkhand 2000, Uttarakhand 2000) don't need aliasing — Census 2011 already used the post-split codes.

Coverage post-fix: **10 of 33 Telangana districts** light up (the pre-2014 original 10 — Hyderabad, Adilabad, Karimnagar, Khammam, Mahbubnagar, Medak, Nalgonda, Nizamabad, Rangareddy, Warangal). The 23 newer Telangana districts (carved 2016-2022) didn't exist in Census 2011 boundaries so SHRUG genuinely has no data for them. Same constraint applies to post-2022 AP / Rajasthan reorg districts.

### `facebook_rwi` — Meta Relative Wealth Index 2021
- **Build script**: `db/shrug/build_facebook_rwi.py`
- **Source**: `~/Downloads/finer_data/shrug/facebook-rwi/facebook_rwi_pc11dist.csv` (already district-aggregated by SHRUG from Chi et al. 2022 RWI)
- **Output**: `public/indicators/facebook_rwi/2021-12.json` — 625 districts
- **Metrics**: `rwi_mean` (centred ~0, scale roughly -2 to +2), `rwi_max`, `rwi_min`, `rwi_spread` (max − min, intra-district inequality proxy)

### `pmgsy_roads` — PMGSY rural roads (cumulative through 2015)
- **Build script**: `db/shrug/build_pmgsy_roads.py`
- **Source**: `~/Downloads/finer_data/shrug/pmgsy/pmgsy_2015_shrid.csv` (589k shrids, ~113k with completed roads)
- **Output**: `public/indicators/pmgsy_roads/2015-12.json` — 542 districts
- **Aggregation**: parses `shrid2` format (`XX-YY-ZZZ-...` where YY=pc11 state, ZZZ=pc11 district), counts roads + sums km + sums cost ₹ Lakhs per district. Splits into new vs upgraded.
- **Metrics**: `roads_total`, `km_total`, `roads_new`, `roads_upg`, `cost_total_lakhs`

### `viirs_nightlights` — VIIRS annual nightlights 2012–2023
- **Build script**: `db/shrug/build_viirs_nightlights.py`
- **Source**: `~/Downloads/finer_data/shrug/viirs/viirs_annual_pc11dist.dta` (DTA, district-aggregated). Uses `category=='median-masked'` (more robust than `average-masked` to fires/outliers).
- **Output**: 12 yearly files at `public/indicators/viirs_nightlights/{2012..2023}-12.json`, each ~637 districts, ~70 KB
- **Metrics**: `nl_mean` (mean radiance, nW/cm²/sr), `nl_sum` (total light output, area-weighted), `nl_max` (peak cell — typically the largest urban cluster)
- **Timeline**: `timePoints: ['2023-12','2022-12',...,'2012-12']` — 12 December snapshots

### `elevation_terrain` — Elevation & Terrain Ruggedness (SRTM Feb 2000)
- **Build script**: `db/shrug/build_elevation.py`
- **Source**: `~/Downloads/finer_data/shrug-elevation/elevation_pc11dist.csv` (NASA SRTM 30m DEM, captured Feb 2000, district-aggregated by SHRUG v2.1)
- **Output**: `public/indicators/elevation_terrain/static.json` — 637 districts. Slider locked to `timePoints: ['2000-02']`.
- **Metrics**: `elevation_mean` (m, plain-vs-hill divide), `elevation_max` (m, peak), `elevation_range` (max−min, Riley-style TRI proxy), `elevation_std` (alternate TRI proxy)
- **Picker placement**: Demographics group, peacock ramp. Useful as control variable when explaining banking thinness in Himalayan / NE / J&K districts.
- **Citation**: Farr & Kobrick (2000), Eos 81(48):583-585. DOI 10.1029/EO081i048p00583.

### `crop_production` — Agricultural Land Use & Irrigation (Census 2011 VD)
- **Build script**: `db/shrug/build_crop_production.py`
- **Source**: `~/Downloads/finer_data/shrug-vd11/pc11_vd_clean_pc11dist.tab` (Census 2011 Village Directory land-use, district-aggregated by SHRUG)
- **Why "crop_production" not "ag_output"**: SHRUG v2.1 doesn't publish district-level crop output (rice/wheat tonnes); the closest pc11dist-level dataset is Village Directory land-use stats. Display title is "Agricultural Land Use & Irrigation" (more honest) but the indicator key stays `crop_production`.
- **Output**: `public/indicators/crop_production/static.json` — 580 districts. Slider locked to Census 2011 snapshot.
- **Metrics**: total cropland (ha), irrigated area (ha), irrigation % coverage, canal/tubewell/tank/other irrigation breakdown.
- **Picker placement**: Credit category (inclusion subgroup) — irrigated cropland is the structural driver of KCC + crop-loan demand.

**Manifest discovery**: SHRUG indicators are picked up automatically by the directory-scan logic in `db/export_indicator_files.py:export_manifest()` — no edit needed when adding new SHRUG-style external indicators (Aadhaar/NFHS pattern).

**Datasets considered and skipped**:
- **SECC poverty/consumption (2011)** — superseded by NFHS-5 (2019–21) which already provides modern poverty/asset proxies.
- **SHRUG RBI directory** (~154k branches, mostly pre-2017) — FINER's existing `rbi_banking_outlets` (RBI DBIE, 2.47M outlets, GPS-tagged) is far superior.
- **DMSP nightlights** (1992–2013, low resolution, saturates in cities) — VIIRS replaces it.
- **VCF forest cover, scheduled areas** — not directly relevant to financial inclusion.

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
34. **NE portal scraper currently broken**: `scrape_onlineslbc.py` form submissions to `onlineslbcne.nic.in` get redirected to `error.php` (101-byte JS redirect response). Form page fetches OK (HTTP 200, 5 KB), CSRF token extracted, state cookie set — but the POST is rejected. Form has only `quarter`, `year`, `token`, submit fields visible, so likely a validation rule or hidden field changed server-side. Diagnostic: capture a real browser submission via DevTools → Network → Copy as cURL, replay headers/body, diff against scraper's POST. **Not currently urgent** — all 6 NE-portal states are at Dec 2025 in SQLite; Mar 2026 likely not published yet (May 2026 today).
35. **`.gitignore` convention for SLBC source data**: PDFs, zips, rar, xlsx in both `slbc-data/` and `public/slbc-data/` are deliberately untracked. Only Python extraction scripts and the canonical aggregated outputs in `public/slbc-data/<state>/{state}_fi_timeseries.json|csv|complete.json|fi_slim.json` get committed. Intermediate extracts (`slbc-data/<state>/<state>_complete.json` etc.) and `quarterly/`, `extracted/`, `pdfs/`, `_temp/` subdirs are also ignored. `git add -A` after a fresh clone or pipeline run will appear to want to add hundreds of MBs — those are local-only working files.
36. **`.wrangler/` and `__pycache__/` ignored**: Cloudflare R2 dev cache (~25-50 MB blob files) and Python bytecode never committed.
37. **State-focus URL param `?state=`**: When focused via URL load, the scraper waits up to 4 seconds (40 × 100ms polling) for `distGeoJSON` to load before dispatching the focus event. This is to ensure the choropleth renders before the focus tries to apply.
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
45. **MapPanel scope default must be `'india'`, not `'ne'`**: `MapPanel.svelte` has two places that initialize the scope toggle — `let scope = $state<'india' | 'ne'>('india')` (line ~9) and `scope = s.scope || 'india'` in the global state load fallback (line ~157). Both must default to `'india'`, otherwise the NE focus toggle visually says "NE" while the map still shows all-India bounds (the toggle and the map fall out of sync because the map fits to `ALL_STATES_BOUNDS` regardless of toggle state on initial load).
46. **AP source PDFs are only on Wayback Machine**: `slbcap.nic.in` is unreachable. Use `https://web.archive.org/web/20250815*/slbcap.nic.in` with the `id_/` raw-content URL pattern. CDX query for discovery: `https://web.archive.org/cdx/search/cdx?url=slbcap.nic.in&matchType=domain&filter=mimetype:application/pdf`.
47. **UP scanned-PDF cutoff**: text-native ends at 2022-Q2; 2022-Q3 onwards are scanned. Don't assume mid-2023 is the boundary.
48. **UP CD-ratio: units in Crores, requires ×100 → Lakhs at import time**: The UP booklet's district-wise CD-ratio table header literally says "Amount in Crore". Every other state in FINER stores deposits/advances in ₹ Lakhs. UP's `credit_deposit_ratio__total_deposit` / `total_advances` / `total_advance` / etc. for `state_lgd_code=9` are stored after ×100 conversion. The cd_ratio % field is unitless so no conversion needed.
49. **UP page-isolation in `extract_pdf`**: The extractor must NOT keep `current_cat` sticky across PDF pages. Once a page classifies as `credit_deposit_ratio`, the Pending RC / RSETI / etc. tables on subsequent pages have the same `<sno> <district> <num> <num>` layout and get falsely accumulated as CD-ratio data. Fix: each page must self-classify; `credit_deposit_ratio` pages require ≥10 plausible district rows before commit. Other categories use a softer threshold of ≥4.
50. **UP 2025-09 + 2025-12 CD-ratio empty by design**: The Dec 2025 booklet's CD-ratio table splits each district's row across 2 visual PDF lines (deposits on one line, advances+ratio on the next, district name dangling separately). pdftotext can't reconstruct them into single rows. Better empty than wrong. Other categories extract fine.
51. **Derived CD ratio with sanity bound (5-400%)**: When `overall_cd_ratio` is missing but `total_deposit` and `total_advance` are populated, `db/export_indicator_files.py` computes `advance/deposit*100` — but only commits if the result falls in 5-400%. Outside that range it's almost always a source-unit mismatch (UP's OCR'd booklets sometimes report advances in Lakhs and sometimes in Crores per row; the row-level mismatch produces 1-2% bogus CD ratios). Better no-data than nonsense.
52. **State-qualified district lookup in `resolveLookup`**: District names aren't globally unique — Bilaspur is in HP and Chhattisgarh; Balrampur is in UP and Chhattisgarh; Pratapgarh / Aurangabad / Hamirpur repeat across multiple states. The choropleth's `buildDistrictLookup` keys entries by `"{state_slug}|{district}"` (in addition to a plain-name fallback). `resolveLookup` uses `normStateSlug(STATE_UT)` to compose the lookup key. Without this, Chhattisgarh data was painting onto Himachal's Bilaspur polygon + UP's Balrampur polygon.
53. **12 bogus `source='slbc'` district_aliases purged (May 2026)**: A bad fuzzy-match during ingestion of new districts had registered cross-state aliases — Phalodi → Tamulpur (Assam), Beawar → Annamayya (AP), Salumbar → Tseminyu (Nagaland), and 9 others. These caused Phalodi (Rajasthan) to render with Tamulpur's Assam SLBC data. Deleted from both SQLite and `public/district_lgd_codes.json`. Also state-qualified the canonical-form fallback path in `resolveLookup` so stray future aliases can't recreate the bug.
54. **`NEW_DISTRICT_PARENTS` parent-fallback for post-2020 carved districts**: 31 new districts (16 Rajasthan 2023 — Phalodi/Balotra/Beawar/etc., 13 AP 2022 — Anakapalli/Bapatla/Nandyal/etc., 1 Punjab 2021 — Malerkotla) inherit their pre-reorg parent's choropleth value with `inheritedFrom` tag → tooltip discloses "Reported under <parent> (pre-reorg SLBC structure)". Inline JS only; no SQLite changes.
55. **SHRUG indicators must NOT use the cross-state shared matcher's fuzzy fallback**: The shared matcher in some Python builders maps new-district names by string similarity. Without the `_shared.PC11_STATE_ALIASES` aliasing, Telangana districts had `census_2011_code` populated but `state_lgd_code=36` while SHRUG records sat under `pc11_state_id="28"` (AP) — the join failed silently. Fixed by registering each FINER district under both its current state's PC11 code AND any predecessor state code (Telangana ← AP "28", Ladakh ← J&K "01"). Use `db/shrug/_shared.py:build_finer_lookup()` for all future SHRUG builders.
56. **maxBounds `_limitCenter` silently clamps padding bumps**: With `maxBoundsViscosity: 1.0`, increasing fitBounds top-padding only moves content DOWN if there's room above the bound. With desktop maxBounds.north=40°N at fit-zoom ~5.4, the viewport top was at ~41°N (~1° above 40°N max) and got clamped → any topPad increase silently no-op'd. Fix: widen north to 46°N so the +72 strip-padding can actually slide content down to clear J&K/Ladakh's northern fingers from the strip's bottom edge. Mobile kept at 45°N (bumping it added empty whitespace).
57. **Shareable URLs across map + analysis pages**: `?indicator=&metric=&quarter=&state=` on the homepage; `?state=&category=&quarter=&field=&sort=col:dir` on `/analysis/rankings/`; `?state=&district=&category=` on `/analysis/trends/`. Read on mount, mirrored on every change via `history.replaceState()` (no history-stack pollution). TimelineSlider listens for `finer:quarterChange` so URL hydration of `?quarter=` actually moves the thumb (it didn't, originally — the slider's `quartersReady` handler overwrote the URL-set quarter).
58. **Snapshot indicators lock the slider via `timePoints`**: `rbi_banking_outlets` (May 2026), `capital_markets_access` (May 2025), `nrlm_shg` (Mar 2026), `rbi_bsr_credit` (Mar 2025), `elevation_terrain` (Feb 2000), `crop_production` (Census 2011), `nfhs_health_insurance` (Mar 2021 + Mar 2016), `aadhaar_enrollment` (3 quarters in 2025), `digital_transactions` (Mar 2024 cap due to PhonePe Pulse). When selected, `switchSliderToTimePoints()` replaces the global slider quarters; `restoreSliderToManifest()` restores them on switch-away.
59. **Mobile timeline is horizontal at the bottom**: TimelineSlider.svelte detects `(max-width: 640px)` via matchMedia. On mobile, position flips from `right: 16px; vertical` to `left/right pinned, bottom: 16px; horizontal`. Mobile MapLegend is `display: none`. Mobile FocusOverlay close button is a vermillion pill anchored bottom-center.
60. **OG image regeneration**: `python3 scripts/build_og_image.py` renders `public/og-image.svg` → `public/og-image.png` via cairosvg + brew cairo (needs `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`). The PNG must stay 1200×630 for proper WhatsApp/Twitter card sizing.
61. **`db/regenerate_indicator_files_from_states.py` is the canonical no-DB regenerator**: After extending any state's extractor OR adding a new field-name variant, run this script — NOT `db/export_indicator_files.py`. The regenerator pulls from `public/slbc-data/<state>/<state>_fi_timeseries.json` directly and applies a much broader fallback chain (15 SLBC indicators, ~30 quarters each). The DB-based export script still works but its fallback lists are narrower; running it without first updating its `INDICATORS` dict will silently drop states that the regenerator catches.
62. **DISTRICT_ALIASES maps GeoJSON-name → data-name**: When you add a new alias because data exists but a polygon won't paint, the key is the GeoJSON `DISTRICT` (after `normDist`) and the value is the data-side district name. Reverse direction is wrong and will fail silently. Note this is the polygon-rendering alias and works alongside the state-qualified `resolveLookup` from #52 — both are needed. May 2026 audit additions: LEPA RADA, KAMRUP RURAL, KOCH BIHAR→COOCHBEHAR (one word — WB source uses no space), SOUTH PARGANAS→PARAGANAS SOUTH (word order), Maharashtra renames AHILYANAGAR/CHHATRAPATI SAMBHAJI NAGAR/DHARASHIV → old names AHMEDNAGAR/AURANGABAD/OSMANABAD (SLBC source still uses pre-2023 names), Odisha BALASORE/SUBARNAPUR/JAGATSINGHPUR, Chhattisgarh SARANGARHBILAIGARH, Telangana MEDCHALMALKAJGIRI, Jharkhand EAST SINGHBHUM/SAHIBGANJ. Test: re-run `db/regenerate_indicator_files_from_states.py` then count unpaintable rows — should be 0.
63. **`?state=<slug>` URL focus race during init**: The init `flyToNE` call in `loadBankingData().then()` (around line 1402 of `index.astro`) was unconditional and wiped any URL-driven state focus that landed milliseconds earlier from the polling block in Section 5 (URL parameter support). Fix is in place: the callback now checks `bankingStateFilter` first and either skips `flyToNE` or re-issues `flyToBounds(stateBounds)` to lock in the URL-driven focus. Don't add another unconditional flyTo in the same chain. See also #57 for the broader shareable-URL story.
64. **digital_transactions Mar 2024 ceiling — detail**: Extends gotcha #58. PhonePe Pulse hasn't released data past Q4 FY24. Quarters 2024-06 onwards contain only SLBC digital-coverage fields, no PhonePe `transaction_count`/`_amount` — and the default Digital Transactions metric is "UPI Transaction Count (PhonePe)" so those quarters would render fake-empty. The regenerator (#61) refuses to write `digital_transactions/<quarter>.json` for any quarter lacking PhonePe data. Selecting Dec 2025 + Digital Transactions falls back to Mar 2024 via the 12-quarter fallback window in `loadIndicatorData`. Don't manually generate empty digital_transactions files.
65. **`src/lib/indicator-sources.ts` is the canonical SLBC state-URL map**: When a state's SLBC portal moves or you add a state, edit only this file. MapLegend reads it via `getSourceCitation(indicator, quarter, state)`. The about-page sources section and any other SLBC URL list should be kept in sync but the citation map is authoritative for the legend.
66. **GitHub Pages deploys only on push to `main`**: `.github/workflows/deploy.yml` triggers on `branches: [main]` only. Branch protection on `main` blocks direct pushes — use a PR. The workflow: develop on a feature branch → PR → merge → ~2-3 min until projectfiner.com updates. Don't try `git push origin main` directly; it returns HTTP 403.
67. **Static sitemap at `public/sitemap.xml` — update manually**: When you add a new page under `src/pages/`, append its URL to `public/sitemap.xml`. Chose static over `@astrojs/sitemap` to avoid `package-lock.json` churn — switching later is a one-line `npm install @astrojs/sitemap` + an `astro.config.mjs` integration entry.
68. **Every state needs ALL THREE files in `public/slbc-data/<slug>/`** — `<slug>_fi_timeseries.json` (programmatic), `<slug>_fi_timeseries.csv` (downloads), `<slug>_complete.json` (master quarter→category→district shape). `StateDownload.svelte` fetches all three. If you add a new state and only ship the JSON, every Download button on `/slbc-data/<slug>/download/` returns the GitHub Pages 404 HTML — and the browser dutifully saves it under the requested `.csv` filename, looking like a corrupt file. May 2026 audit caught Ladakh + 9 other states (Gujarat, Haryana, Karnataka, Kerala, MP, Maharashtra, Punjab, Rajasthan, Tamil Nadu) shipping JSON-only. Fix is mechanical: derive CSV (wide format: district, period, every `category__field`) and `_complete.json` (structure mirrors `sikkim_complete.json`) from the canonical `_fi_timeseries.json`.
69. **Analysis-page state pickers — keep in sync with `public/slbc-data/`**: `TrendTracker.svelte`, `DistrictRankings.svelte`, `DataExplorer.svelte` each have a hardcoded `STATES` array. When you add a new state's data, update all three arrays (DistrictRankings prepends an `'All States'` entry — keep that). Same 31-state ordering across all three for consistency: NE (8) → eastern/central plains → southern → western/north → northern UTs.
70. **Punjab "BASICDATAANDNATIONAL" xlsx exports are not Wayback-archivable**: The SLBC Punjab portal hosts persistent quarterly Excel files at `https://slbcpunjab.pnb.in/cyft-uploads/<YYYY>/<MM>/<name>.xlsx` — those URLs are stable and DO show up on Wayback. But the on-the-fly form-driven CD-ratio export (filename like `BASICDATAANDNATIONAL3.xlsx`, varying numeric suffix per session) is generated server-side from form selections; the filename is a per-download counter, not a URL. Wayback won't have copies of those specific files. Source historical Punjab quarters by either (a) the `cyft-uploads/` URL pattern via Wayback CDX, or (b) submitting the form for older quarters in a live browser.

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
