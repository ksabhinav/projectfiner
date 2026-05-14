<script lang="ts">
  /**
   * District landing-page body. Renders the headline grid (one card per
   * indicator with latest value + inline sparkline) and a freshness badge
   * that summarises "how stale is this district's data right now".
   */

  interface SeriesPoint { quarter: string; value: number | string; field?: string }
  interface IndicatorBlock {
    label: string;
    unit: string;
    latest: SeriesPoint;
    series: SeriesPoint[];
  }
  interface DistrictData {
    state: string;
    stateLabel: string;
    district: string;
    districtSlug: string;
    latestQuarter: string;
    indicators: Record<string, IndicatorBlock>;
  }

  interface Props {
    data: DistrictData;
    basePath: string;
  }

  let { data, basePath }: Props = $props();

  const indicators = Object.entries(data.indicators);

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
  <!-- Freshness badge: how stale is the most-recent data we have for this district -->
  <div class="freshness-row">
    <span class="freshness {freshnessTone(data.latestQuarter)}">
      Last update: <strong>{fmtQuarter(data.latestQuarter)}</strong>
      <span class="dot">·</span>
      {freshnessText(data.latestQuarter)}
    </span>
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
  .freshness-row { margin-bottom: 18px; }
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
