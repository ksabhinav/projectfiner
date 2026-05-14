<script lang="ts">
  /**
   * District landing-page body. Renders the headline grid (one card per
   * indicator with latest value + inline sparkline), a freshness badge
   * that summarises "how stale is this district's data right now", and
   * a Sources & methods block that lists where every number came from.
   */
  import { getSourceCitation, type SourceCitation } from '../lib/indicator-sources';

  interface SeriesPoint { quarter: string; value: number | string; field?: string }
  interface IndicatorBlock {
    label: string;
    unit: string;
    latest: SeriesPoint;
    series: SeriesPoint[];
  }
  interface DistrictPolygon { path: string; viewBox: string }
  interface DistrictData {
    state: string;
    stateLabel: string;
    district: string;
    districtSlug: string;
    latestQuarter: string;
    indicators: Record<string, IndicatorBlock>;
    /** Pre-projected SVG path string for the district's boundary polygon.
        Built by db/build_district_polygons.py from district_boundaries.geojson.
        Optional: a handful of post-2022 carved districts have no boundary
        in our source GeoJSON yet. */
    polygon?: DistrictPolygon;
  }

  interface WaybackVariant {
    url: string;
    host: string;
    snapshotCount: number | null;
    oldestDate: string | null;
    newestDate: string | null;
    snapshotCalendar: string;
    newestUrl: string | null;
  }
  interface WaybackEntry {
    stateUrl: string;
    snapshotCalendar: string;
    latest?: { timestamp: string; date: string; url: string; variantUrl?: string } | null;
    /** Per-variant audit (when the manifest was built with --audit).
        Lets the page surface the variant with the deepest history when
        the primary domain is new/thin (RBI .bank.in migration). */
    variants?: WaybackVariant[];
    deepestArchive?: {
      host: string;
      snapshotCount: number | null;
      snapshotCalendar: string;
      oldestDate: string | null;
    } | null;
  }

  interface Props {
    data: DistrictData;
    basePath: string;
    /** Wayback snapshot info for this district's state, looked up by the
        Astro page from public/sources/wayback.json. Optional; when absent
        the Sources block falls back to the live URL only. */
    wayback?: WaybackEntry | null;
  }

  let { data, basePath, wayback = null }: Props = $props();

  const indicators = Object.entries(data.indicators);

  /**
   * Group the on-page indicators by their source citation so all SLBC-derived
   * cards collapse to a single row ("SLBC Punjab — covers CD ratio, PMJDY,
   * KCC…") rather than printing the same citation eight times. Each group
   * carries the human labels of the indicators it backs.
   */
  interface SourceGroup { citation: SourceCitation; indicatorLabels: string[] }
  const sourceGroups: SourceGroup[] = (() => {
    const byKey = new Map<string, SourceGroup>();
    for (const [key, ind] of indicators) {
      const cit = getSourceCitation(key, ind.latest.quarter, data.state);
      // Group by label+url; attribution is shown but doesn't split groups.
      const groupKey = `${cit.label}::${cit.url ?? ''}`;
      const existing = byKey.get(groupKey);
      if (existing) {
        existing.indicatorLabels.push(ind.label);
      } else {
        byKey.set(groupKey, { citation: cit, indicatorLabels: [ind.label] });
      }
    }
    return Array.from(byKey.values());
  })();

  /** True if the citation's URL is the state's SLBC portal — i.e. matches
      the Wayback entry. Used to decide whether to render a "Wayback ↗"
      link next to the live URL. */
  function citationMatchesPortal(citUrl: string | undefined): boolean {
    if (!citUrl || !wayback) return false;
    // Trim trailing slashes / paths for a forgiving compare. Most SLBC URLs
    // in indicator-sources.ts are root domain anyway, but a few include a
    // path (e.g. slbcbihar.com/SlBCHeldMeeting.aspx).
    const norm = (u: string) => u.replace(/\/$/, '');
    return norm(citUrl) === norm(wayback.stateUrl);
  }

  // Raw JSON download for this exact district.
  const rawJsonHref = `${basePath}districts/${data.state}/${data.districtSlug}.json`;
  const stateCsvHref = `${basePath}slbc-data/${data.state}/${data.state}_fi_timeseries.csv`;

  function fmtValue(v: number | string, unit: string): string {
    if (v == null || v === '') return '—';
    const n = typeof v === 'number' ? v : parseFloat(String(v));
    if (Number.isNaN(n)) return String(v);
    if (unit === '%') return `${n.toFixed(2)}%`;
    if (unit === '₹') {
      // Source values are already in Rs. Lakhs. Render Cr for readability.
      if (Math.abs(n) >= 100) return `₹${(n / 100).toLocaleString('en-IN', { maximumFractionDigits: 1 })} Cr`;
      return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 1 })} L`;
    }
    if (unit === 'km' || unit === 'm') return `${n.toLocaleString('en-IN', { maximumFractionDigits: 1 })} ${unit}`;
    return n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  }

  function fmtQuarter(q: string): string {
    if (!q || !/^\d{4}-\d{2}$/.test(q)) return q;
    const [y, m] = q.split('-');
    const month = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][parseInt(m)];
    return `${month} ${y}`;
  }

  /**
   * Build a tiny inline SVG sparkline. Returns null when the series has fewer
   * than 2 numeric points (in which case the card just shows the headline value).
   */
  function sparklinePath(series: SeriesPoint[], w = 120, h = 28, pad = 2): string | null {
    const pts: { x: number; y: number; v: number }[] = [];
    const nums = series
      .map((s) => ({ q: s.quarter, n: typeof s.value === 'number' ? s.value : parseFloat(String(s.value)) }))
      .filter((s) => !Number.isNaN(s.n));
    if (nums.length < 2) return null;
    const vals = nums.map((s) => s.n);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const range = max - min || 1;
    const xStep = (w - pad * 2) / (nums.length - 1);
    nums.forEach((s, i) => {
      pts.push({
        x: pad + i * xStep,
        y: h - pad - ((s.n - min) / range) * (h - pad * 2),
        v: s.n,
      });
    });
    return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  }

  /**
   * Freshness badge. Compares the indicator's latest quarter to "today" using
   * a rough quarters-since calculation. Anything older than 4 quarters gets a
   * warning tint; older than 8 quarters is flagged stale.
   */
  function quartersSince(qstr: string): number {
    if (!qstr || !/^\d{4}-\d{2}$/.test(qstr)) return 0;
    const [y, m] = qstr.split('-').map(Number);
    const now = new Date();
    const monthsAgo = (now.getFullYear() - y) * 12 + (now.getMonth() + 1 - m);
    return Math.max(0, Math.floor(monthsAgo / 3));
  }

  function freshnessTone(q: string): 'fresh' | 'aging' | 'stale' {
    const n = quartersSince(q);
    if (n <= 2) return 'fresh';
    if (n <= 5) return 'aging';
    return 'stale';
  }

  function freshnessText(q: string): string {
    const n = quartersSince(q);
    if (n === 0) return 'Up to date';
    if (n === 1) return '1 quarter ago';
    return `${n} quarters ago`;
  }
</script>

<section class="district-page">
  <!-- Top row: freshness badge on the left, district-polygon sticker on the right -->
  <div class="top-row">
    <div class="freshness-row">
      <span class="freshness {freshnessTone(data.latestQuarter)}">
        Last update: <strong>{fmtQuarter(data.latestQuarter)}</strong>
        <span class="dot">·</span>
        {freshnessText(data.latestQuarter)}
      </span>
    </div>
    {#if data.polygon}
      <!-- District polygon sticker. Pre-projected at build time
           (db/build_district_polygons.py) so there's zero runtime cost. -->
      <figure class="poly-sticker">
        <svg viewBox={data.polygon.viewBox} preserveAspectRatio="xMidYMid meet" aria-hidden="true">
          <path d={data.polygon.path} fill="#B84A2E" fill-opacity="0.12" stroke="#B84A2E" stroke-width="1.5" stroke-linejoin="round" />
        </svg>
        <figcaption>{data.district}</figcaption>
      </figure>
    {/if}
  </div>

  <div class="grid">
    {#each indicators as [key, ind]}
      {@const spark = sparklinePath(ind.series)}
      <article class="card" data-key={key}>
        <div class="card-head">
          <span class="card-label">{ind.label}</span>
          <span class="card-quarter">{fmtQuarter(ind.latest.quarter)}</span>
        </div>
        <div class="card-value">{fmtValue(ind.latest.value, ind.unit)}</div>
        {#if spark}
          <svg class="spark" viewBox="0 0 120 28" preserveAspectRatio="none" aria-hidden="true">
            <path d={spark} fill="none" stroke="currentColor" stroke-width="1.5" />
          </svg>
          <div class="spark-meta">{ind.series.length} quarters</div>
        {:else}
          <div class="spark-meta solo">Single observation</div>
        {/if}
      </article>
    {/each}
  </div>

  <div class="actions">
    <a class="action-link" href="{basePath}slbc-data/{data.state}/download/">
      Download all {data.stateLabel} data &rarr;
    </a>
    <a class="action-link secondary" href="{basePath}?state={data.state}">
      View on map &rarr;
    </a>
    <a class="action-link secondary" href="{basePath}analysis/rankings/?state={data.state}">
      District rankings &rarr;
    </a>
  </div>

  <!-- Sources & methods: where every number above came from. Each row links
       to the canonical source (state SLBC portal, dataset page, etc.) plus
       attribution where applicable. Grouping prevents the SLBC entry from
       repeating once per indicator. -->
  <details class="sources" open>
    <summary>
      <span class="src-eye">Sources &amp; methods</span>
      <span class="src-toggle">show / hide</span>
    </summary>
    <ul class="src-list">
      {#each sourceGroups as g}
        <li class="src-item">
          <div class="src-head">
            {#if g.citation.url}
              <a class="src-label" href={g.citation.url} target="_blank" rel="noopener">
                {g.citation.label}
                <span class="src-ext" aria-hidden="true">&nearr;</span>
              </a>
            {:else}
              <span class="src-label">{g.citation.label}</span>
            {/if}
            <span class="src-covers">
              covers: {g.indicatorLabels.join(', ')}
            </span>
          </div>
          {#if citationMatchesPortal(g.citation.url) && wayback}
            <!-- Wayback Machine archive — guarantees the source URL is permanent
                 even when the upstream portal moves, 404s, or overwrites in place
                 (J&K Bank pattern, CLAUDE.md #70). When the manifest carries
                 audit data, also surfaces the legacy variant with the deepest
                 archive (relevant during the RBI .bank.in migration window:
                 new domains are thin in Wayback, legacy domains have years
                 of history). -->
            <p class="src-archive">
              <span class="src-archive-eye">Archive</span>
              {#if wayback.latest}
                <a class="src-link" href={wayback.latest.url} target="_blank" rel="noopener">
                  Wayback snapshot {wayback.latest.date}
                  <span class="src-ext" aria-hidden="true">&nearr;</span>
                </a>
                &nbsp;&middot;&nbsp;
              {/if}
              <a class="src-link" href={wayback.snapshotCalendar} target="_blank" rel="noopener">
                All snapshots
                <span class="src-ext" aria-hidden="true">&nearr;</span>
              </a>
              {#if wayback.deepestArchive && wayback.deepestArchive.host !== (new URL(wayback.stateUrl)).host && wayback.deepestArchive.snapshotCount}
                &nbsp;&middot;&nbsp;
                <a class="src-link" href={wayback.deepestArchive.snapshotCalendar} target="_blank" rel="noopener" title="Domain with the deepest Wayback history — often the legacy site during the RBI .bank.in migration">
                  Deeper history ({wayback.deepestArchive.host}, {wayback.deepestArchive.snapshotCount} snapshots{wayback.deepestArchive.oldestDate ? `, since ${wayback.deepestArchive.oldestDate.slice(0,4)}` : ''})
                  <span class="src-ext" aria-hidden="true">&nearr;</span>
                </a>
              {/if}
            </p>
          {/if}
          {#if g.citation.attribution}
            <p class="src-attr">{g.citation.attribution}</p>
          {/if}
        </li>
      {/each}
    </ul>
    <p class="src-raw">
      Raw data for this district:
      <a class="src-link" href={rawJsonHref}>district JSON</a>
      &middot;
      <a class="src-link" href={stateCsvHref}>{data.stateLabel} full CSV</a>
    </p>
  </details>

  <p class="footer-note">
    Headline values are the latest observation per indicator from SLBC quarterly
    booklets and other open-data layers (RBI DBIE, NFHS, UIDAI, PhonePe Pulse,
    SHRUG). Some indicators are sparser than others — cards only appear when
    data for this district exists.
  </p>
</section>

<style>
  .district-page {
    color: var(--ink, #1B140E);
    font-family: 'Source Serif 4', Georgia, serif;
  }
  .top-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    margin-bottom: 18px;
  }
  .freshness-row { flex: 1 1 auto; }
  /* District polygon sticker — floats to the right of the freshness badge.
     Small, atlas-toned outline; no labels. Falls back to flowing under the
     badge on narrow screens. */
  .poly-sticker {
    flex: 0 0 auto;
    margin: 0;
    width: 160px;
    text-align: center;
  }
  .poly-sticker svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .poly-sticker figcaption {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--mist, #6E665E);
    margin-top: 4px;
  }
  @media (max-width: 540px) {
    .top-row { flex-direction: column; gap: 12px; }
    .poly-sticker { width: 120px; align-self: flex-start; }
  }
  .freshness {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.03em;
    padding: 5px 10px;
    border-radius: 999px;
    border: 1px solid var(--rule-soft, #E8E2D5);
    background: rgba(255,255,255,0.4);
  }
  .freshness strong { font-weight: 600; }
  .freshness .dot { opacity: 0.5; }
  .freshness.fresh { border-color: #6B8F5C; color: #46663A; }
  .freshness.aging { border-color: #B89B45; color: #7A6420; }
  .freshness.stale { border-color: #B84A2E; color: #7A2814; }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 14px;
  }
  .card {
    border: 1px solid var(--rule-soft, #E8E2D5);
    background: rgba(255,255,255,0.55);
    border-radius: 8px;
    padding: 14px 16px;
    color: var(--vermillion, #B84A2E);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
    color: var(--mist, #6E665E);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .card-label { color: var(--ink, #1B140E); font-weight: 500; }
  .card-quarter { color: var(--mist, #6E665E); }
  .card-value {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 26px;
    line-height: 1.05;
    font-variation-settings: 'opsz' 96;
    color: var(--ink, #1B140E);
    word-break: break-word;
  }
  .spark { width: 100%; height: 28px; opacity: 0.65; }
  .spark-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.03em;
    color: var(--mist, #6E665E);
    margin-top: -2px;
  }
  .spark-meta.solo { font-style: italic; }

  .actions {
    margin-top: 24px;
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
  }
  .action-link {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--vermillion, #B84A2E);
    text-decoration: none;
    border-bottom: 1px solid transparent;
    padding-bottom: 2px;
    transition: border-color 0.15s;
  }
  .action-link:hover { border-color: var(--vermillion, #B84A2E); }
  .action-link.secondary { color: var(--ink-soft, #3D332A); }
  .action-link.secondary:hover { border-color: var(--ink-soft, #3D332A); }

  /* Sources & methods block — collapsible. Open by default so the trust
     signal is visible without an extra click. */
  .sources {
    margin-top: 32px;
    border-top: 1px solid var(--rule-soft, #E8E2D5);
    padding-top: 16px;
  }
  .sources summary {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    cursor: pointer;
    list-style: none;
    margin-bottom: 12px;
  }
  .sources summary::-webkit-details-marker { display: none; }
  .src-eye {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink, #1B140E);
    font-weight: 500;
  }
  .src-toggle {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.04em;
    color: var(--mist, #6E665E);
    text-transform: uppercase;
  }
  .src-list {
    list-style: none;
    padding: 0;
    margin: 0 0 12px 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .src-item {
    padding-left: 12px;
    border-left: 2px solid var(--rule-soft, #E8E2D5);
  }
  .src-head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px 14px;
  }
  .src-label {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 14px;
    font-weight: 500;
    color: var(--vermillion, #B84A2E);
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color 0.15s;
  }
  a.src-label:hover { border-bottom-color: var(--vermillion, #B84A2E); }
  .src-ext { font-size: 11px; margin-left: 3px; }
  .src-covers {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.03em;
    color: var(--mist, #6E665E);
  }
  .src-attr {
    margin: 4px 0 0 0;
    font-size: 12px;
    line-height: 1.5;
    color: var(--mist, #6E665E);
    font-style: italic;
    max-width: 680px;
  }
  .src-archive {
    margin: 4px 0 0 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--mist, #6E665E);
    letter-spacing: 0.03em;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px;
  }
  .src-archive-eye {
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 10px;
    color: var(--mist, #6E665E);
    padding: 2px 6px;
    background: rgba(184, 74, 46, 0.08);
    border-radius: 4px;
    margin-right: 4px;
  }
  .src-raw {
    margin: 14px 0 0 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--mist, #6E665E);
    letter-spacing: 0.03em;
  }
  .src-link {
    color: var(--vermillion, #B84A2E);
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color 0.15s;
  }
  .src-link:hover { border-bottom-color: var(--vermillion, #B84A2E); }

  .footer-note {
    margin-top: 22px;
    font-size: 13px;
    line-height: 1.55;
    color: var(--mist, #6E665E);
    font-style: italic;
    max-width: 680px;
  }

  @media (max-width: 600px) {
    .grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
    .card-value { font-size: 22px; }
  }
</style>
