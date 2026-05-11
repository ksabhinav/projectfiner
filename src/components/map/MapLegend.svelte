<script lang="ts">
  import { onMount } from 'svelte';
  import { onFiner, getFinerState } from '../../lib/map-bridge';
  import { fmtNum } from '../../lib/format-utils';

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

  function syncFromGlobal() {
    const s = getFinerState();
    if (!s) return;
    if (typeof s.stateFilter === 'string') stateFilter = s.stateFilter;
    if (s.legendData) {
      legendTitle = s.legendData.title;
      legendBreaks = s.legendData.breaks;
      legendRamp = s.legendData.ramp;
      legendUnit = s.legendData.unit;
    }
  }

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

    const unsubs = [
      onFiner('legendUpdate', (detail) => {
        legendTitle = detail.title;
        legendBreaks = detail.breaks;
        legendRamp = detail.ramp;
        legendUnit = detail.unit;
      }),
      onFiner('stateUpdate', () => {
        syncFromGlobal();
      }),
    ];

    return () => unsubs.forEach(fn => fn());
  });
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
      <div class="legend-meta">Adaptive — recomputed from visible districts on each filter change.</div>
      <a href="{baseUrl}/about#sources" class="legend-source-link" title="View data sources &amp; citations">SOURCES →</a>
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
    width: 280px;
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

  .legend-meta {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid var(--rule-soft, #E8E2D5);
    font-family: var(--font-body, 'Source Serif 4', Georgia, serif);
    font-style: italic;
    font-size: 11px;
    color: var(--mist, #6E665E);
    line-height: 1.4;
  }

  /* .no-data-row, .lr, .ldot styles removed with capital-markets dot/choro modes. */

  .legend-source-link {
    display: block;
    margin-top: 6px;
    font-family: var(--font-mono, 'IBM Plex Mono', monospace);
    font-size: 9px;
    font-weight: 500;
    color: var(--mist, #6E665E);
    text-decoration: none;
    letter-spacing: 0.06em;
    transition: color 0.15s;
  }
  .legend-source-link:hover {
    color: var(--vermillion, #B84A2E);
  }

  /* ── Mobile ── */
  @media (max-width: 640px) {
    .legend-wrap {
      display: none;
    }

    .legend-box {
      padding: 6px 10px;
      border-radius: 8px;
      max-width: 180px;
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
  }
</style>
