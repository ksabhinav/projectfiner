<script lang="ts">
  /**
   * IndicatorStrip.svelte — Atlas identity (56px horizontal strip)
   *
   * Three semantic cells (What / When / Where), keyboard ⌘K hint, and a search
   * pill. Replaces the old left-side MapPanel.
   *
   * Event protocol — fires the SAME camelCase events the inline Leaflet script
   * already listens to, so the inline JS doesn't need to change:
   *   - finer:indicatorChange   { indicator: <key>, metricIdx: 0 }
   *   - finer:quarterChange     { quarter: <YYYY-MM>, idx: <number> }
   *   - finer:stateFilterChange { state: <STATE_UT uppercase> | '' }
   *
   * Subscribes to:
   *   - finer:quartersReady     to populate the When dropdown
   *   - finer:indicatorsReady   for current state
   *   - finer:stateFilterChange to track state focus changes from inset map
   */

  import { onMount } from 'svelte';
  import IndicatorPicker from './IndicatorPicker.svelte';
  import FindingButton from './FindingButton.svelte';
  import {
    ATLAS_INDICATORS,
    atlasIndicatorByKey,
    type AtlasIndicator,
  } from '../../lib/map-indicators';

  // === State ===
  let indicator = $state<AtlasIndicator>(
    atlasIndicatorByKey('digital_transactions') ?? ATLAS_INDICATORS[0]
  );
  let quarter = $state<string>('2025-12');                  // YYYY-MM key
  let scope = $state<string>('All India');                  // human label
  let scopeStateUT = $state<string>('');                    // empty = all India
  let availableQuarters: string[] = $state([]);             // YYYY-MM keys
  let openCell = $state<'what' | 'when' | 'where' | null>(null);

  const STATES_LIST = [
    'All India',
    'ANDHRA PRADESH','ARUNACHAL PRADESH','ASSAM','BIHAR','CHHATTISGARH','GUJARAT',
    'HARYANA','JHARKHAND','KARNATAKA','KERALA','MAHARASHTRA','MANIPUR',
    'MEGHALAYA','MIZORAM','NAGALAND','ODISHA','RAJASTHAN','SIKKIM','TAMIL NADU',
    'TELANGANA','TRIPURA','UTTARAKHAND','WEST BENGAL',
  ];

  // === Helpers ===
  function fmtQuarter(q: string): string {
    if (!q || q.length < 7) return q || '—';
    const [y, m] = q.split('-');
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const idx = parseInt(m, 10) - 1;
    return `${months[idx] ?? m} ${y}`;
  }
  function titleCaseState(ut: string): string {
    if (!ut) return 'All India';
    return ut.split(' ').map(w => w[0] + w.slice(1).toLowerCase()).join(' ');
  }
  function dispatch<T>(name: string, detail: T) {
    window.dispatchEvent(new CustomEvent(name, { detail }));
  }

  // === Selectors ===
  function selectIndicator(ind: AtlasIndicator) {
    indicator = ind;
    openCell = null;
    // Resolve the underlying indicator key + metric index. Synthetic Atlas
    // entries (e.g. capital_markets_mfdi) carry indicatorKey/metricIdx; for
    // a normal entry these default to the key itself + 0.
    const indKey = ind.indicatorKey ?? ind.key;
    const mIdx = ind.metricIdx ?? 0;
    dispatch('finer:indicatorChange', { indicator: indKey, metricIdx: mIdx });
    // Also push the Atlas indicator into a global so MapLegend can read rampKey
    if ((window as any).__FINER) {
      (window as any).__FINER.atlasIndicator = ind;
    }
    dispatch('finer:atlasIndicatorChange', { indicator: ind });
  }
  function selectQuarter(q: string) {
    quarter = q;
    openCell = null;
    const idx = availableQuarters.indexOf(q);
    dispatch('finer:quarterChange', { quarter: q, idx: idx >= 0 ? idx : 0 });
  }
  function selectScope(label: string) {
    scope = label === 'All India' ? 'All India' : titleCaseState(label);
    scopeStateUT = label === 'All India' ? '' : label;
    openCell = null;
    dispatch('finer:stateFilterChange', { state: scopeStateUT });
  }

  // === Lifecycle ===
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && openCell) { openCell = null; e.preventDefault(); }
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      dispatch('finer:open-search', {});
    }
  }
  function handleOutsideClick(e: MouseEvent) {
    const t = e.target as HTMLElement;
    if (!t.closest('.strip') && !t.closest('.picker-panel') && !t.closest('.simple-panel')) {
      openCell = null;
    }
  }

  onMount(() => {
    // Read initial state if inline script set it
    const w = window as any;
    if (w.__FINER) {
      if (w.__FINER.indicator) {
        const ind = atlasIndicatorByKey(w.__FINER.indicator);
        if (ind) indicator = ind;
      }
      if (w.__FINER.quarter) quarter = w.__FINER.quarter;
      if (Array.isArray(w.__FINER.sortedQuarters) && w.__FINER.sortedQuarters.length) {
        availableQuarters = w.__FINER.sortedQuarters.slice();
        if (!quarter) quarter = availableQuarters[0];
      }
    }

    const onQuartersReady = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (Array.isArray(detail?.quarters)) {
        availableQuarters = detail.quarters.slice();
        if (!availableQuarters.includes(quarter)) {
          quarter = availableQuarters[0] || '';
        }
      }
    };
    const onStateFilter = (e: Event) => {
      const st: string = (e as CustomEvent).detail?.state ?? '';
      // Avoid loop — if it matches what we already have, skip
      if (st === scopeStateUT) return;
      scopeStateUT = st;
      scope = st ? titleCaseState(st) : 'All India';
    };
    const onAtlasInit = () => {
      // Push initial indicator into global for legend
      if ((window as any).__FINER) (window as any).__FINER.atlasIndicator = indicator;
    };

    window.addEventListener('finer:quartersReady', onQuartersReady);
    window.addEventListener('finer:stateFilterChange', onStateFilter);
    window.addEventListener('keydown', handleKeydown);
    onAtlasInit();

    return () => {
      window.removeEventListener('finer:quartersReady', onQuartersReady);
      window.removeEventListener('finer:stateFilterChange', onStateFilter);
      window.removeEventListener('keydown', handleKeydown);
    };
  });

  $effect(() => {
    if (openCell) {
      window.addEventListener('click', handleOutsideClick);
      return () => window.removeEventListener('click', handleOutsideClick);
    }
  });
</script>

<div id="indicator-strip" class="strip" role="toolbar" aria-label="Map controls">
  <button
    class="cell what"
    class:active={openCell === 'what'}
    onclick={() => (openCell = openCell === 'what' ? null : 'what')}
    aria-haspopup="listbox"
    aria-expanded={openCell === 'what'}
  >
    <span class="k">What</span>
    <span class="v">{indicator.name}</span>
  </button>

  <!-- "When" cell removed — the vertical timeline on the right edge picks the quarter. -->

  <button
    class="cell where"
    class:active={openCell === 'where'}
    onclick={() => (openCell = openCell === 'where' ? null : 'where')}
    aria-haspopup="listbox"
    aria-expanded={openCell === 'where'}
  >
    <span class="k">Where</span>
    <span class="v">{scope}</span>
  </button>

  <span class="spacer"></span>

  <!-- "A finding" button hidden until public/findings.json has 30+ curated entries.
       Re-enable: uncomment <FindingButton /> below + uncomment <FactCard client:load /> in index.astro -->
  <!-- <FindingButton /> -->

  <span class="search" role="button" tabindex="0" onclick={() => dispatch('finer:open-search', {})}>
    <span class="glass" aria-hidden="true">⌕</span>
    Search 800 districts
    <span class="key">⌘K</span>
  </span>
</div>

{#if openCell === 'what'}
  <IndicatorPicker
    selected={indicator}
    onSelect={selectIndicator}
    onClose={() => (openCell = null)}
  />
{/if}

{#if openCell === 'where'}
  <div class="simple-panel where">
    {#each STATES_LIST as s}
      <button
        class="picker-item"
        class:active={(s === 'All India' && !scopeStateUT) || s === scopeStateUT}
        onclick={() => selectScope(s)}
      >
        {s === 'All India' ? s : titleCaseState(s)}
      </button>
    {/each}
  </div>
{/if}

<style>
  .strip {
    position: fixed;
    left: 0; right: 0;
    top: var(--header-h, 52px);
    height: var(--strip-h, 56px);
    background: var(--paper, #F4EFE6);
    border-bottom: 1px solid var(--rule, #D9D2C5);
    display: flex;
    align-items: stretch;
    z-index: 1010;
    /* Subtle gradient hairline tying to header gradient */
  }
  .strip::after {
    content: '';
    position: absolute;
    left: 0; right: 0; bottom: -1px;
    height: 1px;
    background: linear-gradient(90deg, var(--vermillion) 0%, var(--saffron) 100%);
    opacity: 0.18;
  }

  .cell {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 9px 20px;
    cursor: pointer;
    border: 0;
    border-right: 1px solid var(--rule-soft, #E8E2D5);
    background: transparent;
    color: inherit;
    text-align: left;
    transition: background 160ms ease;
  }
  .cell:hover, .cell.active { background: var(--paper-deep, #ECE5D6); }

  .cell .k {
    font-family: var(--font-ui, 'Inter', sans-serif);
    font-size: 8.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--mist, #6E665E);
    margin-bottom: 3px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .cell .k::before {
    content: '';
    width: 5px; height: 5px;
    border-radius: 50%;
    background: var(--mist-soft, #9A9089);
  }
  .cell.what  .k::before { background: var(--vermillion, #B84A2E); }
  .cell.when  .k::before { background: var(--peacock,    #1E4960); }
  .cell.where .k::before { background: var(--saffron-d,  #A07A30); }

  .cell .v {
    font-family: var(--font-display, 'Fraunces', Georgia, serif);
    font-weight: 400;
    font-variation-settings: 'opsz' 60;
    font-size: 16px;
    letter-spacing: -0.015em;
    color: var(--ink, #1B140E);
    line-height: 1.05;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .cell .v::after {
    content: '⌄';
    color: var(--mist, #6E665E);
    font-size: 13px;
    margin-top: -2px;
  }
  .cell.what .v { color: var(--vermillion-d, #8E331E); }
  .cell.what  { min-width: 240px; }
  .cell.when, .cell.where { min-width: 158px; }

  .spacer { flex: 1; }

  .search {
    align-self: center;
    margin-right: 90px; /* leave room for Leaflet zoom controls top-right */
    font-family: var(--font-mono, 'IBM Plex Mono', monospace);
    font-size: 10px;
    color: var(--mist, #6E665E);
    padding: 7px 12px;
    background: var(--paper-deep, #ECE5D6);
    border: 1px solid var(--rule, #D9D2C5);
    border-radius: 99px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    transition: border-color 160ms ease;
  }
  .search:hover { border-color: var(--ink, #1B140E); }
  .search .key {
    background: var(--paper, #F4EFE6);
    border: 1px solid var(--rule, #D9D2C5);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 9px;
  }

  /* Simple dropdowns for When and Where */
  .simple-panel {
    position: fixed;
    top: calc(var(--header-h, 52px) + var(--strip-h, 56px) + 6px);
    background: var(--paper, #F4EFE6);
    border: 1px solid var(--ink, #1B140E);
    border-radius: 6px;
    box-shadow: 0 24px 48px rgba(27, 20, 14, 0.18);
    padding: 6px 0;
    min-width: 180px;
    max-height: 380px;
    overflow-y: auto;
    z-index: 1100;
    animation: drop 260ms cubic-bezier(0.32, 0.72, 0.40, 1.00);
  }
  .simple-panel.where { left: 282px; }

  .picker-item {
    display: block;
    width: 100%;
    padding: 7px 16px;
    text-align: left;
    border: 0;
    background: transparent;
    font-family: var(--font-body, 'Source Serif 4', Georgia, serif);
    font-size: 13px;
    color: var(--ink, #1B140E);
    cursor: pointer;
    white-space: nowrap;
  }
  .picker-item:hover { background: var(--paper-deep, #ECE5D6); }
  .picker-item.active { color: var(--vermillion, #B84A2E); font-weight: 500; }

  .empty {
    padding: 12px 16px;
    font-family: var(--font-body, 'Source Serif 4', Georgia, serif);
    font-size: 12px;
    font-style: italic;
    color: var(--mist, #6E665E);
  }

  @keyframes drop {
    from { opacity: 0; transform: translateY(-6px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  @media (max-width: 760px) {
    .strip { height: 50px; }
    .search { display: none; }
    .spacer { display: none; }
    /* Two cells (What, Where) split the strip evenly */
    .cell {
      flex: 1 1 0;
      min-width: 0 !important;
      padding: 6px 12px;
      overflow: hidden;
    }
    .cell .k { font-size: 8px; margin-bottom: 2px; }
    .cell .v {
      font-size: 13px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .cell .v::after { font-size: 11px; }
    /* Where dropdown follows the cell, full-width */
    .simple-panel.where { left: 8px; right: 8px; min-width: 0; }
  }
</style>
