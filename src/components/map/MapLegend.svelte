<script lang="ts">
  import { onMount } from 'svelte';
  import { onFiner, getFinerState } from '../../lib/map-bridge';
  import { fmtNum } from '../../lib/format-utils';
  import { getSourceCitation } from '../../lib/indicator-sources';
  import { buildMapViewCsv, mapViewFilename } from '../../lib/map-data-status.js';

  interface Props {}
  let {}: Props = $props();

  // Atlas: single banking-mode legend. The legacy two-mode (banking / capital
  // dots / capital choro) variants were removed when the homepage moved to the
  // unified strip — the Capital Markets indicator now renders through the
  // same banking-mode choropleth + ramp pipeline.
  let legendTitle = $state('');
  let legendBreaks: number[] = $state([]);
  let legendRamp: string[] = $state([]);
  let legendUnit = $state('');
  let stateFilter = $state(''); // current state focus, '' = All India
  let currentIndicator = $state('');
  let currentQuarter = $state('');
  let status = $state({ current: 0, stale: 0, proxy: 0, suspect: 0, unclassified: 0, missing: 0, proxyAvailable: 0, periods: [] as Array<{ period: string; count: number }> });
  let exportRows: Array<Record<string, unknown>> = $state([]);
  let showProxies = $state(false);
  let boundaryVintage = $state('undocumented');

  function syncFromGlobal() {
    const s = getFinerState();
    if (!s) return;
    if (typeof s.stateFilter === 'string') stateFilter = s.stateFilter;
    if (typeof s.indicator === 'string') currentIndicator = s.indicator;
    if (typeof s.quarter === 'string') currentQuarter = s.quarter;
    if (s.legendData) {
      legendTitle = s.legendData.title;
      legendBreaks = s.legendData.breaks;
      legendRamp = s.legendData.ramp;
      legendUnit = s.legendData.unit;
      status = s.legendData.status || status;
      exportRows = s.legendData.rows || [];
      showProxies = !!s.legendData.showProxies;
      boundaryVintage = s.legendData.boundaryVintage || 'undocumented';
    }
  }

  // Live citation: recomputes whenever indicator / quarter / state focus changes.
  let citation = $derived(getSourceCitation(currentIndicator, currentQuarter, stateFilter));

  function titleCase(s: string): string {
    if (!s) return '';
    return s.split(' ').map(w => w[0] + w.slice(1).toLowerCase()).join(' ');
  }
  let scopeLabel = $derived(stateFilter ? titleCase(stateFilter) : 'All India');

  // Build a single CSS gradient string from the ramp stops for the bar
  let rampGradient = $derived.by(() => {
    if (!legendRamp || legendRamp.length === 0) return 'linear-gradient(90deg, #F4E1D6 0%, #B84A2E 100%)';
    const n = legendRamp.length;
    const stops = legendRamp.map((c, i) => `${c} ${(i / (n - 1)) * 100}%`).join(', ');
    return `linear-gradient(90deg, ${stops})`;
  });

  function formatLabel(val: number, unit: string): string {
    if (unit === '%') return val.toFixed(1) + '%';
    return fmtNum(val);
  }

  // Compose href that uses Astro's BASE_URL so Sources link works under any base path
  const baseUrl = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');

  onMount(() => {
    syncFromGlobal();

    // The choropleth pipeline fires camelCase events (finer:indicatorChange,
    // finer:quarterChange, finer:stateFilterChange) — listen directly so the
    // citation updates the instant the selection changes, not only after the
    // legend redraw.
    const onChange = () => syncFromGlobal();
    window.addEventListener('finer:indicatorChange', onChange);
    window.addEventListener('finer:quarterChange', onChange);
    window.addEventListener('finer:stateFilterChange', onChange);

    const unsubs = [
      onFiner('legendUpdate', (detail) => {
        legendTitle = detail.title;
        legendBreaks = detail.breaks;
        legendRamp = detail.ramp;
        legendUnit = detail.unit;
        status = detail.status || status;
        exportRows = detail.rows || [];
        showProxies = !!detail.showProxies;
        boundaryVintage = detail.boundaryVintage || 'undocumented';
        syncFromGlobal();
      }),
      onFiner('stateUpdate', () => {
        syncFromGlobal();
      }),
      () => {
        window.removeEventListener('finer:indicatorChange', onChange);
        window.removeEventListener('finer:quarterChange', onChange);
        window.removeEventListener('finer:stateFilterChange', onChange);
      },
    ];

    return () => unsubs.forEach(fn => fn());
  });

  function toggleProxies(event: Event) {
    const visible = (event.currentTarget as HTMLInputElement).checked;
    showProxies = visible;
    window.dispatchEvent(new CustomEvent('finer:proxyVisibilityChange', { detail: { visible } }));
  }

  function exportView() {
    if (!exportRows.length) return;
    const csv = buildMapViewCsv(exportRows);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = mapViewFilename(currentIndicator, currentQuarter);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }
</script>

{#if legendRamp.length > 0}
  <div class="legend-wrap">
    <div class="legend-box">
      <div class="legend-title">
        <span class="legend-units">{legendUnit ? legendUnit : (legendTitle || 'Value')}</span>
        <span class="legend-scope">{scopeLabel}</span>
      </div>
      <div class="legend-bar" style="background: {rampGradient};"></div>
      <div class="choro-labels">
        {#each legendBreaks as brk}
          <span>{formatLabel(brk, legendUnit)}</span>
        {/each}
      </div>
      <div class="status-summary" aria-label="Data status for the displayed map">
        <div class="status-heading">Displayed observations</div>
        <div class="status-counts">
          <span><i class="status-mark current"></i>{status.current} selected period</span>
          <span><i class="status-mark stale"></i>{status.stale} different period</span>
          <span><i class="status-mark suspect"></i>{status.suspect} suspect</span>
          <span><i class="status-mark missing"></i>{status.missing} no data</span>
        </div>
        {#if status.periods.length > 1}
          <div class="period-composition">
            {#each status.periods as item}
              <span>{item.period}: {item.count}</span>
            {/each}
          </div>
        {/if}
        {#if status.unclassified > 0}
          <div class="quality-note">Quality status is not classified for {status.unclassified} displayed observations.</div>
        {/if}
        <div class="boundary-note">Boundary vintage: {boundaryVintage}.</div>
        {#if status.proxyAvailable > 0}
          <label class="proxy-toggle">
            <input type="checkbox" checked={showProxies} onchange={toggleProxies} />
            Show {status.proxyAvailable} inherited parent {status.proxyAvailable === 1 ? 'proxy' : 'proxies'}
          </label>
        {/if}
        <button class="export-button" type="button" onclick={exportView} disabled={!exportRows.length}>
          Export displayed data + status
        </button>
      </div>
      <div class="legend-source" title={citation.attribution || citation.label}>
        <span class="legend-source-prefix">Source:</span>
        {#if citation.url}
          <a href={citation.url} target="_blank" rel="noopener noreferrer" class="legend-source-link">{citation.label}</a>
        {:else}
          <span class="legend-source-label">{citation.label}</span>
        {/if}
      </div>
      {#if citation.attribution}
        <div class="legend-attribution">{citation.attribution}</div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .legend-wrap {
    position: fixed;
    bottom: 16px;
    left: 16px;
    z-index: 900;
  }

  .legend-box {
    background: rgba(244, 239, 230, 0.94);
    backdrop-filter: blur(12px);
    border: 1px solid var(--rule, #D9D2C5);
    padding: 12px 16px;
    box-shadow: 0 4px 20px rgba(27, 20, 14, 0.06);
    border-radius: 6px;
    width: 310px;
    max-width: 90vw;
  }

  .legend-title {
    font-family: var(--font-ui, 'Inter', sans-serif);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--mist, #6E665E);
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }
  .legend-units {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .legend-scope { color: var(--vermillion, #B84A2E); }

  .legend-bar {
    width: 100%;
    height: 10px;
    border-radius: 1px;
    transition: background 260ms ease;
  }

  .choro-labels {
    display: flex;
    justify-content: space-between;
    font-family: var(--font-mono, 'IBM Plex Mono', monospace);
    font-size: 9px;
    font-weight: 500;
    color: var(--ink-soft, #3D332A);
    margin-top: 4px;
  }

  .status-summary {
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid var(--rule-soft, #E8E2D5);
    font-family: var(--font-mono, 'IBM Plex Mono', monospace);
    font-size: 9px;
    line-height: 1.45;
    color: var(--ink-soft, #3D332A);
  }
  .status-heading {
    color: var(--mist, #6E665E);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 5px;
  }
  .status-counts {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3px 8px;
  }
  .status-counts span { display: flex; align-items: center; gap: 5px; }
  .status-mark { width: 9px; height: 9px; display: inline-block; border: 1px solid #7A6C5D; }
  .status-mark.current { background: var(--vermillion, #B84A2E); border-color: var(--vermillion, #B84A2E); }
  .status-mark.stale { border-style: dashed; background: #D9D2C5; }
  .status-mark.suspect { border-style: dotted; border-width: 2px; border-color: #8E331E; }
  .status-mark.missing { background: #E8E4DC; border-color: #C8BFB0; }
  .period-composition {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 10px;
    margin-top: 6px;
    color: var(--mist, #6E665E);
  }
  .quality-note {
    margin-top: 6px;
    color: #6E665E;
    font-family: var(--font-body, 'Source Serif 4', Georgia, serif);
    font-style: italic;
    font-size: 10px;
  }
  .boundary-note {
    margin-top: 5px;
    color: #6E665E;
  }
  .proxy-toggle {
    display: flex;
    gap: 6px;
    align-items: center;
    margin-top: 7px;
    cursor: pointer;
  }
  .proxy-toggle input { accent-color: var(--vermillion, #B84A2E); }
  .export-button {
    margin-top: 8px;
    border: 1px solid var(--rule, #D9D2C5);
    border-radius: 3px;
    background: transparent;
    color: var(--vermillion, #B84A2E);
    padding: 5px 7px;
    font: inherit;
    cursor: pointer;
  }
  .export-button:hover { border-color: currentColor; }
  .export-button:disabled { opacity: 0.45; cursor: default; }

  /* Live source citation — replaces the old "Adaptive — recomputed" note + Sources link */
  .legend-source {
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid var(--rule-soft, #E8E2D5);
    font-family: var(--font-mono, 'IBM Plex Mono', monospace);
    font-size: 10px;
    line-height: 1.4;
    color: var(--ink-soft, #3D332A);
  }
  .legend-source-prefix {
    color: var(--mist, #6E665E);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-right: 4px;
    font-size: 9px;
  }
  .legend-source-link {
    color: var(--vermillion, #B84A2E);
    text-decoration: none;
    border-bottom: 1px dotted currentColor;
    transition: color 0.15s;
  }
  .legend-source-link:hover {
    color: var(--vermillion-dark, #8a3a23);
  }
  .legend-source-label {
    color: var(--ink-soft, #3D332A);
  }
  .legend-attribution {
    margin-top: 4px;
    font-family: var(--font-body, 'Source Serif 4', Georgia, serif);
    font-style: italic;
    font-size: 10px;
    color: var(--mist, #6E665E);
    line-height: 1.45;
  }


  /* ── Mobile ── */
  @media (max-width: 640px) {
    .legend-wrap {
      left: 8px;
      bottom: 66px;
    }

    .legend-box {
      padding: 6px 10px;
      border-radius: 8px;
      width: 245px;
      max-width: calc(100vw - 80px);
    }

    .legend-title {
      font-size: 8px !important;
      margin-bottom: 3px !important;
    }

    .legend-bar {
      height: 8px;
    }

    .choro-labels {
      font-size: 7px;
      margin-top: 2px;
    }
    .legend-attribution, .quality-note, .period-composition { display: none; }
    .legend-source { margin-top: 6px; padding-top: 5px; }
    .status-summary { margin-top: 6px; padding-top: 5px; }
  }
</style>
