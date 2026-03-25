<script lang="ts">
  import { onMount } from 'svelte';
  import { onFiner, getFinerState } from '../../lib/map-bridge';
  import { fmtNum } from '../../lib/format-utils';

  interface Props {}
  let {}: Props = $props();

  // Current map state
  let mode = $state<'capital' | 'banking'>('banking');
  let capitalView = $state<'choro' | 'dots'>('choro');
  let drilldownActive = $state(false);

  // Banking legend data (dynamic)
  let legendTitle = $state('');
  let legendBreaks: number[] = $state([]);
  let legendRamp: string[] = $state([]);
  let legendUnit = $state('');

  // Which legend to show
  let showDotLegend = $derived(mode === 'capital' && capitalView === 'dots' && !drilldownActive);
  let showCapitalChoro = $derived(mode === 'capital' && capitalView === 'choro');
  let showBankingChoro = $derived(mode === 'banking');

  function syncFromGlobal() {
    const s = getFinerState();
    if (!s) return;
    mode = s.mode;
    capitalView = s.capitalView;
    drilldownActive = s.drilldownActive;
    if (s.legendData) {
      legendTitle = s.legendData.title;
      legendBreaks = s.legendData.breaks;
      legendRamp = s.legendData.ramp;
      legendUnit = s.legendData.unit;
    }
  }

  function formatLabel(val: number, unit: string): string {
    if (unit === '%') return val.toFixed(1) + '%';
    return fmtNum(val);
  }

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

{#if showDotLegend}
  <div class="legend-wrap">
    <div class="legend-box">
      <div class="lr"><div class="ldot" style="background:#b8603e"></div>CDSL service centre</div>
      <div class="lr"><div class="ldot" style="background:#3d7a8e"></div>NSDL service centre</div>
      <div class="lr"><div class="ldot" style="background:#5a7a3a"></div>MFD individual</div>
      <div class="lr"><div class="ldot" style="background:#8b6914"></div>MFD corporate</div>
    </div>
  </div>
{/if}

{#if showCapitalChoro}
  <div class="legend-wrap">
    <div class="legend-box">
      <div class="legend-title">Total access points per district</div>
      <div class="choro-scale">
        <div class="choro-swatch" style="background:#f7f4ef"></div>
        <div class="choro-swatch" style="background:#e8d5b7"></div>
        <div class="choro-swatch" style="background:#d4a96a"></div>
        <div class="choro-swatch" style="background:#b8603e"></div>
        <div class="choro-swatch" style="background:#7a2010"></div>
      </div>
      <div class="choro-labels"><span>0</span><span>10</span><span>100</span><span>1k</span><span>10k+</span></div>
      <div class="no-data-row">
        <div class="no-data-swatch"></div>
        <span class="no-data-label">No coverage</span>
      </div>
    </div>
  </div>
{/if}

{#if showBankingChoro && legendRamp.length > 0}
  <div class="legend-wrap">
    <div class="legend-box">
      <div class="legend-title">{legendTitle}</div>
      <div class="choro-scale">
        {#each legendRamp as color}
          <div class="choro-swatch" style="background:{color}"></div>
        {/each}
      </div>
      <div class="choro-labels">
        {#each legendBreaks as brk}
          <span>{formatLabel(brk, legendUnit)}</span>
        {/each}
      </div>
      <div class="no-data-row">
        <div class="no-data-swatch"></div>
        <span class="no-data-label">No data</span>
      </div>
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
    background: rgba(255,255,255,0.94);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(224,221,216,0.5);
    padding: 14px 18px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    border-radius: 10px;
  }

  .lr {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 500;
    color: #555048;
    letter-spacing: 0.02em;
  }
  .lr:last-child { margin-bottom: 0; }

  .ldot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .legend-title {
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #888078;
    margin-bottom: 6px;
  }

  .choro-scale {
    display: flex;
    gap: 2px;
    margin-top: 6px;
    align-items: center;
  }

  .choro-swatch {
    height: 14px;
    flex: 1;
    border-radius: 3px;
    min-width: 28px;
  }

  .choro-labels {
    display: flex;
    justify-content: space-between;
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 500;
    color: #aaa09a;
    margin-top: 4px;
    letter-spacing: 0.03em;
  }

  .no-data-row {
    display: flex;
    align-items: center;
    gap: 5px;
    margin-top: 6px;
    padding-top: 5px;
    border-top: 1px solid #e8e5e0;
  }

  .no-data-swatch {
    width: 12px;
    height: 12px;
    background: #e8e4dc;
    border: 1px solid #ccc8c0;
    flex-shrink: 0;
  }

  .no-data-label {
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    color: #aaa09a;
    letter-spacing: 0.03em;
  }

  /* ── Mobile ── */
  @media (max-width: 640px) {
    .legend-wrap {
      bottom: auto;
      top: 8px;
      left: 8px;
    }

    .legend-box {
      padding: 6px 10px;
      border-radius: 8px;
      max-width: 180px;
    }

    .lr {
      margin-bottom: 3px;
      font-size: 9px;
      gap: 6px;
    }

    .ldot {
      width: 7px;
      height: 7px;
    }

    .legend-title {
      font-size: 8px !important;
      margin-bottom: 3px !important;
    }

    .choro-swatch {
      height: 8px;
      min-width: 16px;
    }

    .choro-labels {
      font-size: 7px;
      margin-top: 2px;
    }

    .choro-scale {
      margin-top: 3px;
      gap: 1px;
    }

    /* Hide "No data" row on mobile */
    .no-data-row {
      display: none !important;
    }
  }
</style>
