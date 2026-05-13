# Project FINER — SEO Checklist

This document covers the technical SEO setup baked into the codebase plus the
manual steps you need to complete on Google Search Console and Bing Webmaster
Tools after the first deploy.

## What's already wired up (code-side)

| Item | Where | Effect |
|---|---|---|
| `<title>` per page | `BaseLayout.astro` props | Distinct page titles in search results |
| `<meta name="description">` | `BaseLayout.astro` props | Snippet text under the search result |
| `<link rel="canonical">` | `BaseLayout.astro` (auto) | Prevents duplicate-URL ranking dilution (e.g. `/?state=x` collapsing to `/`) |
| Open Graph + Twitter Card | `BaseLayout.astro` | Rich preview cards on WhatsApp, Twitter, LinkedIn, Facebook |
| `og:locale` `en_IN` | `BaseLayout.astro` | Tells social previews this is India-localised |
| Organization JSON-LD | `BaseLayout.astro` | Sitelinks-eligible knowledge graph entry |
| Dataset JSON-LD | `BaseLayout.astro` | Eligible for Google Dataset Search inclusion |
| WebSite SearchAction JSON-LD | `BaseLayout.astro` | Enables Google's site search box in search results |
| `sitemap.xml` | `public/sitemap.xml` (static) | Lists every page Google should crawl. Update when new pages are added. |
| `robots.txt` | `public/robots.txt` | Points crawlers at the sitemap; excludes heavy data payloads |

## What you must do manually (one-time)

### 1. After the first deploy, verify ownership on Google Search Console

1. Open https://search.google.com/search-console
2. Click "Add property" → pick "Domain" → enter `projectfiner.com`
3. Google gives you a TXT record to add to DNS (looks like `google-site-verification=...`)
4. Add that TXT record on Cloudflare (the DNS provider for `projectfiner.com`):
   - Cloudflare dashboard → Websites → projectfiner.com → DNS → Add record
   - Type: TXT, Name: `@`, Content: the full `google-site-verification=...` string
   - TTL: Auto, Proxy: off (DNS only)
5. Back in Search Console click "Verify". DNS records propagate in 1–5 minutes.
6. **Alternative if you can't do DNS**: switch to "URL prefix" property and use the HTML-tag method. I can add the meta tag to `BaseLayout.astro` if you go that route.

### 2. Submit the sitemap to Google Search Console

After verification, in the GSC left sidebar:
1. Click "Sitemaps"
2. Add `https://projectfiner.com/sitemap.xml`
3. Click "Submit". Google starts crawling within a few hours; first indexing takes 1–7 days.

### 3. Request indexing on the homepage and key pages (faster than waiting)

In GSC's URL Inspection tool, paste each of:
- `https://projectfiner.com/`
- `https://projectfiner.com/about/`
- `https://projectfiner.com/analysis/`
- `https://projectfiner.com/analysis/trends/`
- `https://projectfiner.com/analysis/rankings/`
- `https://projectfiner.com/ask/`
- `https://projectfiner.com/capital-markets/data-download/`

For each: click "Request indexing" → Google pushes it into the priority crawl queue.

### 4. Mirror to Bing Webmaster Tools (free, 5 minutes)

1. Open https://www.bing.com/webmasters
2. Sign in with a Microsoft account, click "Add site" → `https://projectfiner.com`
3. Choose "Import from Google Search Console" — this auto-pulls verification + sitemap. Done.
4. Bing also powers DuckDuckGo, Yahoo, and many AI search products (Copilot, You.com).

### 5. Submit to Google Dataset Search (optional, high ROI)

Google has a dedicated Dataset Search at https://datasetsearch.research.google.com.
Our `Dataset` JSON-LD already makes us eligible. Once GSC starts indexing, Dataset Search picks it up automatically within 1–2 weeks. No separate submission needed.

### 6. Add backlinks from credible sources (organic discovery)

Single biggest SEO lever for a small site. Pitch a one-paragraph blurb + the site link to:
- **IndiaDataPortal** (datameet.org, data.gov.in) — they catalogue open-data projects
- **DevDataLab / SHRUG** — they already publish district-level layers; ask them to cross-link
- **CSEP, NIPFP, BIRD-Lucknow, NIBM** — financial-sector research institutes; many publish district-data digests
- **RBI's "useful links" section** on dbie.rbi.org.in
- **Wikipedia** — citable on individual district / scheme pages (PMJDY, KCC, MUDRA) using the SLBC URLs as sources

Each high-authority backlink moves the needle. PageRank is no longer the dominant signal but referring-domain diversity still helps.

### 7. Track results in GSC after 4 weeks

Look at "Performance" tab in GSC:
- Impressions = how often you show up in search
- Clicks = how often people click through
- Top queries = what users searched to find you

The first month is mostly the homepage and brand-name searches. Indicator and district queries take 2–3 months to mature.

## Pages currently exposed via sitemap

The sitemap is `public/sitemap.xml` (static — update by hand when adding pages). Currently listed:

- `/` (homepage, priority 1.0, daily)
- `/about/`, `/ask/`
- `/analysis/`, `/analysis/rankings/`, `/analysis/trends/`, `/analysis/insights/`
- `/capital-markets/data-download/`
- `/slbc-data/<state>/download/` × 17 states (the ones with a directory under `src/pages/slbc-data/`)

When you add a new page under `src/pages/`, also add it to `public/sitemap.xml` so Google sees it within the next crawl. Alternatively switch to `@astrojs/sitemap` later — just run `npm install @astrojs/sitemap`, commit the updated `package-lock.json`, then add it to `astro.config.mjs`.

## Per-page description improvements (optional, big SEO win)

The BaseLayout fall-back description is generic. Setting a unique, keyword-rich description per page is a 30-minute task that significantly improves click-through rate from search results. Examples:

```astro
<BaseLayout
  title="District Rankings — Project FINER"
  description="Sortable leaderboard of 800+ Indian districts ranked by 20+ financial inclusion indicators: CD ratio, PMJDY accounts, KCC issuance, SHG coverage, digital adoption. Traffic-light status badges flag districts above and below RBI norms."
>
```

Apply to `/analysis/rankings/`, `/analysis/trends/`, `/ask/`, `/about/`, and the per-state SLBC download pages.

## Page speed / Core Web Vitals

Astro static output is already fast. After deploy, run https://pagespeed.web.dev/?url=projectfiner.com and aim for:
- **LCP** (Largest Contentful Paint) < 2.5s — the choropleth map's tile layer is the LCP element. Cloudflare's edge cache + the CDN-hosted Leaflet asset already deliver this.
- **CLS** (Cumulative Layout Shift) < 0.1 — the map's `fitBounds` runs synchronously on init so there's no shift after first paint.
- **INP** (Interaction to Next Paint) < 200ms — Svelte 5 keeps this well under budget.

If anything regresses below those thresholds, GSC's "Core Web Vitals" report flags it within a week.

## What NOT to do

- **Don't** add `noindex` to any HTML page in the sitemap — it'd undo everything above.
- **Don't** disallow `/` or any HTML in robots.txt.
- **Don't** create a `<meta name="robots" content="noindex">` anywhere in the build.
- **Don't** post the live site to a paywalled venue — backlinks from open sources matter much more.
