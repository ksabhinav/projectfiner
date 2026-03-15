<script lang="ts">
  import { onMount } from 'svelte';
  import { CATEGORY_INFO, prettyCategoryName } from '../../lib/slbc-categories';

  interface Props {
    baseUrl?: string;
  }

  let { baseUrl = '/' }: Props = $props();

  const STATES = [
    { name: 'Assam', slug: 'assam' },
    { name: 'Meghalaya', slug: 'meghalaya' },
    { name: 'Manipur', slug: 'manipur' },
    { name: 'Arunachal Pradesh', slug: 'arunachal-pradesh' },
    { name: 'Mizoram', slug: 'mizoram' },
    { name: 'Tripura', slug: 'tripura' },
    { name: 'Nagaland', slug: 'nagaland' },
    { name: 'Sikkim', slug: 'sikkim' },
  ];

  // NPA-related categories where a decrease is good
  const NPA_CATEGORIES = new Set([
    'acp_npa_outstanding', 'agri_npa', 'msme_npa', 'non_ps_npa',
    'other_ps_npa', 'govt_sponsored_npa', 'acp_priority_sector_os_npa',
    'pmmy_mudra_os_npa',
  ]);

  const MONTH_MAP: Record<string, string> = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12',
  };

  function normalizePeriod(p: string): string {
    const parts = p.trim().toLowerCase().split(/\s+/);
    if (parts.length === 2) {
      const month = MONTH_MAP[parts[0]];
      if (month) return `${parts[1]}-${month}`;
    }
    return p;
  }

  function prettyFieldName(field: string): string {
    return field
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase())
      .replace(/\bA C\b/g, 'A/C')
      .replace(/\bO S\b/g, 'O/S')
      .replace(/\bAmt\b/g, 'Amount')
      .replace(/\bNo\b/g, 'No.')
      .replace(/\bDisb\b/g, 'Disbursement')
      .replace(/\bCy\b/g, 'Current Year');
  }

  function formatValue(v: number): string {
    if (v === 0) return '0';
    if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(2) + 'M';
    if (Math.abs(v) >= 1_000) return (v / 1_000).toFixed(1) + 'K';
    if (Number.isInteger(v)) return v.toLocaleString();
    return v.toFixed(2);
  }

  let Plotly: any = $state(null);
  let loading = $state(true);
  let loadingState = $state(false);
  let error = $state('');

  // Raw timeseries data
  let rawData: any = $state(null);

  // User selections
  let selectedState = $state('meghalaya');
  let selectedDistrict = $state('');
  let selectedCategoryFilter = $state('all');
  let expandedCard: string | null = $state(null);

  // Flattened data: array of { district, period, normalizedPeriod, ...fields }
  interface DistrictRecord {
    district: string;
    period: string;
    normalizedPeriod: string;
    [key: string]: any;
  }

  let flatRecords: DistrictRecord[] = $state([]);

  // Derived: sorted unique periods
  let sortedPeriods: string[] = $derived.by(() => {
    const periodMap = new Map<string, string>();
    for (const r of flatRecords) {
      periodMap.set(r.normalizedPeriod, r.period);
    }
    return [...periodMap.keys()].sort();
  });

  // Derived: unique districts
  let districts: string[] = $derived.by(() => {
    const s = new Set<string>();
    for (const r of flatRecords) s.add(r.district);
    return [...s].sort();
  });

  // Derived: records for selected district, sorted by period
  let districtRecords: DistrictRecord[] = $derived.by(() => {
    if (!selectedDistrict) return [];
    return flatRecords
      .filter(r => r.district === selectedDistrict)
      .sort((a, b) => a.normalizedPeriod.localeCompare(b.normalizedPeriod));
  });

  // Derived: all metric fields with their category, grouped
  interface MetricInfo {
    key: string;        // full field key like "credit_deposit_ratio__total_deposit"
    category: string;   // "credit_deposit_ratio"
    field: string;      // "total_deposit"
    label: string;      // "Total Deposit"
    categoryLabel: string;
    values: number[];   // one per sorted period (NaN if missing)
    periods: string[];  // normalized period keys
    latestValue: number;
    prevValue: number;
    qoqChange: number | null;
    isNpa: boolean;
  }

  let allMetrics: MetricInfo[] = $derived.by(() => {
    if (districtRecords.length === 0) return [];

    // Collect all fields that have category__field pattern
    const fieldSet = new Set<string>();
    for (const r of districtRecords) {
      for (const key of Object.keys(r)) {
        if (key.includes('__') && key !== 'as_on_date') {
          fieldSet.add(key);
        }
      }
    }

    const metrics: MetricInfo[] = [];
    for (const key of [...fieldSet].sort()) {
      const sepIdx = key.indexOf('__');
      const category = key.substring(0, sepIdx);
      const field = key.substring(sepIdx + 2);

      // Skip non-numeric or metadata fields
      if (['period', 'district', 'normalizedPeriod', 'as_on_date', 'fy'].includes(field)) continue;

      const values: number[] = [];
      const periods: string[] = [];

      for (const r of districtRecords) {
        const raw = r[key];
        const num = parseFloat(String(raw ?? '').replace(/,/g, ''));
        values.push(isNaN(num) ? NaN : num);
        periods.push(r.normalizedPeriod);
      }

      // Skip if all NaN
      const validValues = values.filter(v => !isNaN(v));
      if (validValues.length === 0) continue;

      // Find latest and previous valid values
      let latestValue = NaN;
      let prevValue = NaN;
      for (let i = values.length - 1; i >= 0; i--) {
        if (!isNaN(values[i])) {
          if (isNaN(latestValue)) {
            latestValue = values[i];
          } else if (isNaN(prevValue)) {
            prevValue = values[i];
            break;
          }
        }
      }

      let qoqChange: number | null = null;
      if (!isNaN(latestValue) && !isNaN(prevValue) && prevValue !== 0) {
        qoqChange = ((latestValue - prevValue) / Math.abs(prevValue)) * 100;
      }

      metrics.push({
        key,
        category,
        field,
        label: prettyFieldName(field),
        categoryLabel: CATEGORY_INFO[category] || prettyCategoryName(category),
        values,
        periods,
        latestValue,
        prevValue,
        qoqChange,
        isNpa: NPA_CATEGORIES.has(category) || field.toLowerCase().includes('npa'),
      });
    }

    return metrics;
  });

  // Derived: available categories from metrics
  let availableCategories: string[] = $derived.by(() => {
    const cats = new Set<string>();
    for (const m of allMetrics) cats.add(m.category);
    return [...cats].sort();
  });

  // Derived: filtered metrics based on category filter
  let filteredMetrics: MetricInfo[] = $derived.by(() => {
    if (selectedCategoryFilter === 'all') return allMetrics;
    return allMetrics.filter(m => m.category === selectedCategoryFilter);
  });

  // Period labels map
  let periodLabels: Map<string, string> = $derived.by(() => {
    const m = new Map<string, string>();
    for (const r of flatRecords) {
      m.set(r.normalizedPeriod, r.period);
    }
    return m;
  });

  // District summary info
  let districtSummary = $derived.by(() => {
    if (!selectedDistrict || districtRecords.length === 0) return null;
    const state = STATES.find(s => s.slug === selectedState);
    const first = districtRecords[0];
    const last = districtRecords[districtRecords.length - 1];
    return {
      district: selectedDistrict,
      state: state?.name || selectedState,
      quarters: districtRecords.length,
      dateRange: `${first.period} - ${last.period}`,
      totalMetrics: allMetrics.length,
    };
  });

  function flattenTimeseries(data: any): DistrictRecord[] {
    const records: DistrictRecord[] = [];
    if (!data?.periods) return records;
    for (const period of data.periods) {
      if (!period.districts) continue;
      for (const dist of period.districts) {
        records.push({
          ...dist,
          normalizedPeriod: normalizePeriod(dist.period || period.period),
        });
      }
    }
    return records;
  }

  async function loadStateData(slug: string) {
    loadingState = true;
    error = '';
    try {
      const res = await fetch(`${baseUrl}slbc-data/${slug}/${slug}_fi_timeseries.json`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      rawData = await res.json();
      flatRecords = flattenTimeseries(rawData);
      selectedDistrict = '';
      selectedCategoryFilter = 'all';
      expandedCard = null;
    } catch (e: any) {
      error = `Failed to load ${slug} data: ${e.message}`;
      rawData = null;
      flatRecords = [];
    }
    loadingState = false;
  }

  // Auto-select first district when districts change
  $effect(() => {
    if (districts.length > 0 && !selectedDistrict) {
      selectedDistrict = districts[0];
    }
  });

  // Reset expanded card when district or category changes
  $effect(() => {
    selectedDistrict;
    selectedCategoryFilter;
    expandedCard = null;
  });

  // Load state data when state changes
  $effect(() => {
    if (selectedState && !loading) {
      loadStateData(selectedState);
    }
  });

  // Render expanded chart when card is expanded
  let expandedChartEl: HTMLDivElement | undefined = $state(undefined);

  $effect(() => {
    if (!expandedCard || !Plotly || !expandedChartEl) return;
    const metric = filteredMetrics.find(m => m.key === expandedCard);
    if (!metric) return;

    const xLabels = metric.periods.map(p => periodLabels.get(p) || p);
    const yValues = metric.values;

    // Filter out NaN pairs
    const validX: string[] = [];
    const validY: number[] = [];
    for (let i = 0; i < yValues.length; i++) {
      if (!isNaN(yValues[i])) {
        validX.push(xLabels[i]);
        validY.push(yValues[i]);
      }
    }

    const trace = {
      x: validX,
      y: validY,
      type: 'scatter',
      mode: 'lines+markers',
      line: { color: '#b8603e', width: 2.5 },
      marker: { size: 7, color: '#b8603e' },
      hovertemplate: '%{x}<br>%{y:,.2f}<extra></extra>',
    };

    const layout = {
      title: {
        text: `${metric.label} (${metric.categoryLabel})`,
        font: { family: 'Georgia, serif', size: 15, color: '#1a1410' },
      },
      xaxis: {
        title: 'Quarter',
        gridcolor: '#e8e5e0',
        zerolinecolor: '#e0ddd8',
        tickangle: -45,
        tickfont: { family: 'Inter, sans-serif', size: 10 },
      },
      yaxis: {
        title: metric.label,
        gridcolor: '#e8e5e0',
        zerolinecolor: '#e0ddd8',
        tickfont: { family: 'IBM Plex Mono, monospace', size: 10 },
      },
      paper_bgcolor: '#fff',
      plot_bgcolor: '#fff',
      font: { family: 'Inter, sans-serif', size: 11, color: '#1a1410' },
      margin: { l: 70, r: 30, t: 50, b: 80 },
      hovermode: 'x unified',
    };

    const config = {
      responsive: true,
      displayModeBar: true,
      toImageButtonOptions: { format: 'png', width: 1200, height: 600, scale: 2 },
    };

    Plotly.newPlot(expandedChartEl, [trace], layout, config);
  });

  function handleCardClick(key: string) {
    expandedCard = expandedCard === key ? null : key;
  }

  onMount(async () => {
    await loadStateData(selectedState);
    loading = false;
  });

  async function ensurePlotly() {
    if (!Plotly) {
      const mod = await import('plotly.js-dist-min');
      Plotly = mod.default || mod;
    }
  }
</script>

{#if loading}
  <div class="loading-msg">Loading timeseries data...</div>
{:else if error}
  <div class="loading-msg error-msg">{error}</div>
{:else}
  <div class="trend-tracker">
    <!-- Sub-navigation -->
    <nav class="sub-nav">
      <a href="{baseUrl}analysis/" class="sub-nav-pill">Explorer</a>
      <a href="{baseUrl}analysis/rankings/" class="sub-nav-pill">Rankings</a>
      <a href="{baseUrl}analysis/trends/" class="sub-nav-pill active">Trends</a>
      <a href="{baseUrl}analysis/insights/" class="sub-nav-pill">Insights</a>
    </nav>

    <!-- Controls row -->
    <div class="controls-row">
      <div class="control-group">
        <label class="ctrl-label" for="state-select">State</label>
        <select id="state-select" bind:value={selectedState} class="select">
          {#each STATES as st}
            <option value={st.slug}>{st.name}</option>
          {/each}
        </select>
      </div>

      <div class="control-group">
        <label class="ctrl-label" for="district-select">District</label>
        <select id="district-select" bind:value={selectedDistrict} class="select">
          {#each districts as d}
            <option value={d}>{d}</option>
          {/each}
        </select>
      </div>

      {#if loadingState}
        <div class="loading-indicator">Loading...</div>
      {/if}
    </div>

    <!-- District summary header -->
    {#if districtSummary}
      <div class="district-header">
        <div class="dh-name">{districtSummary.district}</div>
        <div class="dh-meta">
          <span class="dh-state">{districtSummary.state}</span>
          <span class="dh-sep">/</span>
          <span class="dh-quarters">{districtSummary.quarters} quarters</span>
          <span class="dh-sep">/</span>
          <span class="dh-range">{districtSummary.dateRange}</span>
          <span class="dh-sep">/</span>
          <span class="dh-metrics">{districtSummary.totalMetrics} metrics</span>
        </div>
      </div>
    {/if}

    <!-- Category filter pills -->
    {#if availableCategories.length > 0}
      <div class="category-pills">
        <button
          class="cat-pill"
          class:active={selectedCategoryFilter === 'all'}
          onclick={() => selectedCategoryFilter = 'all'}
        >
          All ({allMetrics.length})
        </button>
        {#each availableCategories as cat}
          {@const count = allMetrics.filter(m => m.category === cat).length}
          <button
            class="cat-pill"
            class:active={selectedCategoryFilter === cat}
            onclick={() => selectedCategoryFilter = cat}
          >
            {CATEGORY_INFO[cat] || prettyCategoryName(cat)} ({count})
          </button>
        {/each}
      </div>
    {/if}

    <!-- Sparkline card grid -->
    {#if filteredMetrics.length === 0}
      <div class="empty-state">
        {#if selectedDistrict}
          No metrics available for this selection.
        {:else}
          Select a district to view trends.
        {/if}
      </div>
    {:else}
      <div class="card-grid">
        {#each filteredMetrics as metric (metric.key)}
          {@const validVals = metric.values.filter(v => !isNaN(v))}
          {@const minVal = Math.min(...validVals)}
          {@const maxVal = Math.max(...validVals)}
          {@const range = maxVal - minVal || 1}
          {@const sparkPoints = metric.values
            .map((v, i) => {
              if (isNaN(v)) return null;
              return { x: i, y: v };
            })
            .filter(Boolean) as { x: number; y: number }[]}
          {@const polyline = sparkPoints
            .map((p, i) => `${(i / Math.max(sparkPoints.length - 1, 1)) * 80},${30 - ((p.y - minVal) / range) * 28}`)
            .join(' ')}

          <button
            class="metric-card"
            class:expanded={expandedCard === metric.key}
            onclick={() => { ensurePlotly(); handleCardClick(metric.key); }}
          >
            <div class="mc-category">{metric.categoryLabel}</div>
            <div class="mc-label">{metric.label}</div>
            <div class="mc-row">
              <div class="mc-value">{formatValue(metric.latestValue)}</div>
              {#if metric.qoqChange !== null}
                {@const isPositive = metric.qoqChange > 0}
                {@const isGood = metric.isNpa ? !isPositive : isPositive}
                <div class="mc-change" class:good={isGood} class:bad={!isGood}>
                  {isPositive ? '\u25B2' : '\u25BC'}
                  {Math.abs(metric.qoqChange).toFixed(1)}%
                </div>
              {/if}
            </div>
            <div class="mc-sparkline">
              {#if sparkPoints.length >= 2}
                <svg width="80" height="30" viewBox="0 0 80 30">
                  <polyline points={polyline} fill="none" stroke="#b8603e" stroke-width="1.5" />
                </svg>
              {:else}
                <span class="mc-no-spark">--</span>
              {/if}
            </div>
          </button>
        {/each}
      </div>

      <!-- Expanded chart area -->
      {#if expandedCard}
        <div class="expanded-chart">
          <div class="ec-header">
            <button class="ec-close" onclick={() => expandedCard = null}>Close</button>
          </div>
          <div bind:this={expandedChartEl} class="plotly-chart"></div>
        </div>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .loading-msg {
    font-family: var(--font-sans);
    font-size: 12px;
    color: var(--label);
    text-align: center;
    padding: 60px;
  }
  .error-msg { color: #c44830; }

  .trend-tracker { display: flex; flex-direction: column; gap: 20px; }

  /* Sub-navigation */
  .sub-nav {
    display: flex;
    gap: 0;
    border: 1px solid var(--border-dark);
    border-radius: 6px;
    overflow: hidden;
    align-self: flex-start;
  }
  .sub-nav-pill {
    padding: 9px 20px;
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    text-decoration: none;
    background: var(--btn-bg);
    border-right: 1px solid var(--border-dark);
    transition: all 0.2s;
  }
  .sub-nav-pill:last-child { border-right: none; }
  .sub-nav-pill:hover { color: var(--text); background: #fff; }
  .sub-nav-pill.active {
    background: var(--text);
    color: #fff;
  }

  /* Controls row */
  .controls-row {
    display: flex;
    gap: 16px;
    align-items: flex-end;
    flex-wrap: wrap;
  }
  .control-group { display: flex; flex-direction: column; gap: 5px; }
  .ctrl-label {
    font-family: var(--font-sans);
    font-size: 8px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--label);
  }
  .select {
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 5px;
    background: #faf9f7;
    font-family: var(--font-sans);
    font-size: 11px;
    color: var(--text);
    cursor: pointer;
    appearance: none;
    min-width: 180px;
  }
  .select:focus { border-color: var(--accent); outline: none; }

  .loading-indicator {
    font-family: var(--font-sans);
    font-size: 10px;
    color: var(--accent);
    padding-bottom: 8px;
  }

  /* District header */
  .district-header {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px 24px;
    box-shadow: var(--card-shadow);
  }
  .dh-name {
    font-family: var(--font-serif);
    font-size: 22px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 6px;
  }
  .dh-meta {
    font-family: var(--font-sans);
    font-size: 11px;
    color: var(--muted);
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  .dh-sep { color: var(--border-dark); }
  .dh-state { font-weight: 600; color: var(--accent); }

  /* Category pills */
  .category-pills {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .cat-pill {
    padding: 6px 14px;
    border: 1px solid var(--border);
    border-radius: 20px;
    background: #fff;
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
  }
  .cat-pill:hover { border-color: var(--accent); color: var(--text); }
  .cat-pill.active {
    background: var(--text);
    color: #fff;
    border-color: var(--text);
  }

  /* Card grid */
  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
  }

  .metric-card {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    box-shadow: var(--card-shadow);
    cursor: pointer;
    transition: all 0.2s;
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-family: inherit;
  }
  .metric-card:hover {
    box-shadow: var(--card-shadow-hover);
    border-color: var(--accent);
  }
  .metric-card.expanded {
    border-color: var(--accent);
    border-width: 2px;
  }

  .mc-category {
    font-family: var(--font-sans);
    font-size: 8px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--label);
    line-height: 1.3;
  }
  .mc-label {
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 600;
    color: var(--text);
    line-height: 1.3;
  }
  .mc-row {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-top: 2px;
  }
  .mc-value {
    font-family: var(--font-mono);
    font-size: 20px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.2;
  }
  .mc-change {
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 700;
    white-space: nowrap;
  }
  .mc-change.good { color: var(--olive); }
  .mc-change.bad { color: #c44830; }

  .mc-sparkline {
    margin-top: 4px;
  }
  .mc-no-spark {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--label);
  }

  /* Expanded chart */
  .expanded-chart {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--card-shadow);
    padding: 16px;
    margin-top: 4px;
  }
  .ec-header {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 8px;
  }
  .ec-close {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    background: var(--btn-bg);
    border: 1px solid var(--border-dark);
    border-radius: 4px;
    padding: 5px 14px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .ec-close:hover { background: var(--text); color: #fff; border-color: var(--text); }

  .plotly-chart { width: 100%; min-height: 400px; }

  .empty-state {
    font-family: var(--font-sans);
    font-size: 12px;
    color: var(--label);
    text-align: center;
    padding: 60px 20px;
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 8px;
  }

  @media (max-width: 768px) {
    .controls-row { flex-direction: column; align-items: stretch; }
    .select { min-width: unset; width: 100%; }
    .card-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); }
    .sub-nav { align-self: stretch; }
    .sub-nav-pill { flex: 1; text-align: center; padding: 9px 10px; }
  }
</style>
