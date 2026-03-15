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
    { name: 'Bihar', slug: 'bihar' },
    { name: 'Jharkhand', slug: 'jharkhand' },
    { name: 'Odisha', slug: 'odisha' },
    { name: 'West Bengal', slug: 'west-bengal' },
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
      line: { color: '#b8603e', width: 2.5, shape: 'spline', smoothing: 0.8 },
      marker: { size: 6, color: '#b8603e', line: { color: '#fff', width: 1.5 } },
      hovertemplate: '<b>%{x}</b><br>%{y:,.2f}<extra></extra>',
      fill: 'tozeroy',
      fillcolor: 'rgba(184, 96, 62, 0.06)',
    };

    const layout = {
      xaxis: {
        gridcolor: '#f0eeeb',
        zerolinecolor: '#e0ddd8',
        tickangle: -45,
        tickfont: { family: 'Inter, sans-serif', size: 10, color: '#888078' },
        showline: true,
        linecolor: '#e8e5e0',
        linewidth: 1,
      },
      yaxis: {
        gridcolor: '#f0eeeb',
        zerolinecolor: '#e0ddd8',
        tickfont: { family: 'IBM Plex Mono, monospace', size: 10, color: '#888078' },
        showline: false,
        tickformat: validY.some(v => Math.abs(v) >= 10000) ? ',.0f' : undefined,
      },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif', size: 11, color: '#1a1410' },
      margin: { l: 70, r: 24, t: 16, b: 70 },
      hovermode: 'x unified',
      hoverlabel: {
        bgcolor: '#1a1410',
        font: { family: 'IBM Plex Mono, monospace', size: 12, color: '#fff' },
        bordercolor: 'transparent',
      },
      shapes: validY.length > 0 ? [{
        type: 'line',
        x0: validX[validX.length - 1],
        x1: validX[validX.length - 1],
        y0: 0,
        y1: 1,
        yref: 'paper',
        line: { color: '#b8603e', width: 1, dash: 'dot' },
      }] : [],
      annotations: validY.length > 0 ? [{
        x: validX[validX.length - 1],
        y: validY[validY.length - 1],
        text: `<b>${formatValue(validY[validY.length - 1])}</b>`,
        showarrow: true,
        arrowhead: 0,
        arrowcolor: '#b8603e',
        ax: 40,
        ay: -30,
        font: { family: 'IBM Plex Mono, monospace', size: 12, color: '#b8603e' },
        bgcolor: 'rgba(255,255,255,0.9)',
        bordercolor: '#b8603e',
        borderwidth: 1,
        borderpad: 4,
      }] : [],
    };

    const config = {
      responsive: true,
      displayModeBar: false,
      staticPlot: false,
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

  function downloadChart() {
    if (!Plotly || !expandedChartEl || !expandedCard) return;
    const metric = filteredMetrics.find(m => m.key === expandedCard);
    if (!metric) return;
    Plotly.downloadImage(expandedChartEl, {
      format: 'png',
      width: 1200,
      height: 600,
      scale: 2,
      filename: `${metric.field}_${selectedDistrict}`,
    });
  }
</script>

{#if loading}
  <div class="loading-msg">Loading timeseries data...</div>
{:else if error}
  <div class="loading-msg error-msg">{error}</div>
{:else}
  <div class="trend-tracker">
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
        <div class="dh-left">
          <div class="dh-name">{districtSummary.district}</div>
          <div class="dh-meta">
            <span class="dh-state">{districtSummary.state}</span>
            <span class="dh-sep">·</span>
            <span>{districtSummary.dateRange}</span>
          </div>
        </div>
        <div class="dh-stats">
          <div class="dh-stat">
            <div class="dh-stat-num">{districtSummary.quarters}</div>
            <div class="dh-stat-label">Quarters</div>
          </div>
          <div class="dh-stat">
            <div class="dh-stat-num">{districtSummary.totalMetrics}</div>
            <div class="dh-stat-label">Metrics</div>
          </div>
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
            <div class="mc-top">
              <div class="mc-text">
                <div class="mc-category">{metric.categoryLabel}</div>
                <div class="mc-label">{metric.label}</div>
                <div class="mc-row">
                  <div class="mc-value">{formatValue(metric.latestValue)}</div>
                  {#if metric.qoqChange !== null}
                    {@const isPositive = metric.qoqChange > 0}
                    {@const isGood = metric.isNpa ? !isPositive : isPositive}
                    <div class="mc-change" class:good={isGood} class:bad={!isGood}>
                      <span class="mc-arrow">{isPositive ? '\u25B2' : '\u25BC'}</span>
                      {Math.abs(metric.qoqChange).toFixed(1)}%
                    </div>
                  {/if}
                </div>
              </div>
            </div>
            <div class="mc-sparkline">
              {#if sparkPoints.length >= 2}
                {@const sparkW = 120}
                {@const sparkH = 36}
                {@const pad = 2}
                {@const areaPoints = sparkPoints
                  .map((p, i) => `${pad + (i / Math.max(sparkPoints.length - 1, 1)) * (sparkW - 2 * pad)},${pad + (sparkH - 2 * pad) - ((p.y - minVal) / range) * (sparkH - 2 * pad)}`)
                  .join(' ')}
                {@const lastPt = sparkPoints[sparkPoints.length - 1]}
                {@const lastX = pad + ((sparkPoints.length - 1) / Math.max(sparkPoints.length - 1, 1)) * (sparkW - 2 * pad)}
                {@const lastY = pad + (sparkH - 2 * pad) - ((lastPt.y - minVal) / range) * (sparkH - 2 * pad)}
                {@const firstPt = sparkPoints[0]}
                {@const isUp = lastPt.y >= firstPt.y}
                <svg width={sparkW} height={sparkH} viewBox={`0 0 ${sparkW} ${sparkH}`}>
                  <defs>
                    <linearGradient id={`grad-${metric.key.replace(/[^a-zA-Z0-9]/g, '_')}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color={isUp ? '#b8603e' : '#c44830'} stop-opacity="0.18" />
                      <stop offset="100%" stop-color={isUp ? '#b8603e' : '#c44830'} stop-opacity="0.02" />
                    </linearGradient>
                  </defs>
                  <polygon
                    points={`${pad},${sparkH} ${areaPoints} ${lastX},${sparkH}`}
                    fill={`url(#grad-${metric.key.replace(/[^a-zA-Z0-9]/g, '_')})`}
                  />
                  <polyline points={areaPoints} fill="none" stroke={isUp ? '#b8603e' : '#c44830'} stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" />
                  <circle cx={lastX} cy={lastY} r="2.5" fill={isUp ? '#b8603e' : '#c44830'} />
                </svg>
              {:else}
                <span class="mc-no-spark">—</span>
              {/if}
            </div>
            <div class="mc-expand-hint">{expandedCard === metric.key ? 'Click to collapse' : 'Click to expand chart'}</div>
          </button>
        {/each}
      </div>

      <!-- Expanded chart area -->
      {#if expandedCard}
        {@const ecMetric = filteredMetrics.find(m => m.key === expandedCard)}
        <div class="expanded-chart">
          <div class="ec-header">
            {#if ecMetric}
              <div class="ec-title-area">
                <div class="ec-cat">{ecMetric.categoryLabel}</div>
                <div class="ec-title">{ecMetric.label}</div>
                {#if ecMetric.qoqChange !== null}
                  {@const isPositive = ecMetric.qoqChange > 0}
                  {@const isGood = ecMetric.isNpa ? !isPositive : isPositive}
                  <span class="ec-badge" class:good={isGood} class:bad={!isGood}>
                    {isPositive ? '▲' : '▼'} {Math.abs(ecMetric.qoqChange).toFixed(1)}% QoQ
                  </span>
                {/if}
              </div>
            {/if}
            <div class="ec-actions">
              <button class="ec-download" onclick={downloadChart} title="Download as PNG">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                <span>Download PNG</span>
              </button>
              <button class="ec-close" onclick={() => expandedCard = null}>&times;</button>
            </div>
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

  .trend-tracker { display: flex; flex-direction: column; gap: 24px; }

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
    padding: 8px 14px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: #faf9f7;
    font-family: var(--font-sans);
    font-size: 11px;
    color: var(--text);
    cursor: pointer;
    appearance: none;
    min-width: 190px;
    transition: border-color 0.2s;
  }
  .select:focus { border-color: var(--accent); outline: none; box-shadow: 0 0 0 3px rgba(184,96,62,0.08); }

  .loading-indicator {
    font-family: var(--font-sans);
    font-size: 10px;
    color: var(--accent);
    padding-bottom: 8px;
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

  /* District header */
  .district-header {
    background: #fff;
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 8px;
    padding: 20px 28px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
  }
  .dh-left { flex: 1; min-width: 0; }
  .dh-name {
    font-family: var(--font-serif);
    font-size: 24px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 5px;
    letter-spacing: -0.01em;
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
  .dh-sep { color: var(--label); font-size: 8px; }
  .dh-state { font-weight: 600; color: var(--accent); }
  .dh-stats {
    display: flex;
    gap: 24px;
    flex-shrink: 0;
  }
  .dh-stat { text-align: center; }
  .dh-stat-num {
    font-family: var(--font-mono);
    font-size: 22px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.1;
  }
  .dh-stat-label {
    font-family: var(--font-sans);
    font-size: 8px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--label);
    margin-top: 3px;
  }

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
  .cat-pill:hover { border-color: var(--accent); color: var(--text); background: rgba(184,96,62,0.04); }
  .cat-pill.active {
    background: var(--text);
    color: #fff;
    border-color: var(--text);
  }

  /* Card grid */
  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 14px;
  }

  .metric-card {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 18px 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    cursor: pointer;
    transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 0;
    font-family: inherit;
    position: relative;
    overflow: hidden;
  }
  .metric-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 3px;
    height: 100%;
    background: var(--border);
    transition: background 0.25s;
    border-radius: 10px 0 0 10px;
  }
  .metric-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.07);
    transform: translateY(-2px);
  }
  .metric-card:hover::before {
    background: var(--accent);
  }
  .metric-card.expanded {
    border-color: var(--accent);
    box-shadow: 0 4px 16px rgba(184,96,62,0.12);
  }
  .metric-card.expanded::before {
    background: var(--accent);
  }

  .mc-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
  }
  .mc-text { flex: 1; min-width: 0; }

  .mc-category {
    font-family: var(--font-sans);
    font-size: 8px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--label);
    line-height: 1.3;
    margin-bottom: 3px;
  }
  .mc-label {
    font-family: var(--font-sans);
    font-size: 11.5px;
    font-weight: 600;
    color: var(--text);
    line-height: 1.35;
    margin-bottom: 8px;
  }
  .mc-row {
    display: flex;
    align-items: baseline;
    gap: 10px;
  }
  .mc-value {
    font-family: var(--font-mono);
    font-size: 22px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.1;
    letter-spacing: -0.02em;
  }
  .mc-change {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 700;
    white-space: nowrap;
    padding: 2px 7px;
    border-radius: 10px;
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }
  .mc-change.good { color: #2d7d46; background: rgba(45,125,70,0.08); }
  .mc-change.bad { color: #c44830; background: rgba(196,72,48,0.08); }
  .mc-arrow { font-size: 7px; }

  .mc-sparkline {
    margin-top: 10px;
    display: flex;
    align-items: flex-end;
  }
  .mc-sparkline svg { display: block; width: 100%; height: auto; }
  .mc-no-spark {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--label);
  }

  .mc-expand-hint {
    font-family: var(--font-sans);
    font-size: 8px;
    color: var(--label);
    text-align: right;
    margin-top: 6px;
    opacity: 0;
    transition: opacity 0.2s;
    letter-spacing: 0.02em;
  }
  .metric-card:hover .mc-expand-hint { opacity: 1; }

  /* Expanded chart */
  .expanded-chart {
    background: #fff;
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 10px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06);
    padding: 24px 28px;
    margin-top: 4px;
  }
  .ec-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
  }
  .ec-title-area {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .ec-cat {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--label);
  }
  .ec-title {
    font-family: var(--font-serif);
    font-size: 18px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.3;
  }
  .ec-badge {
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 12px;
    display: inline-flex;
    align-items: center;
    gap: 3px;
    width: fit-content;
    margin-top: 4px;
  }
  .ec-badge.good { color: #2d7d46; background: rgba(45,125,70,0.08); }
  .ec-badge.bad { color: #c44830; background: rgba(196,72,48,0.08); }

  .ec-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
  }
  .ec-download {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--muted);
    background: none;
    border: 1px solid var(--border);
    border-radius: 5px;
    padding: 5px 12px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .ec-download:hover { border-color: var(--accent); color: var(--accent); }
  .ec-close {
    font-family: var(--font-sans);
    font-size: 20px;
    line-height: 1;
    color: var(--muted);
    background: none;
    border: none;
    cursor: pointer;
    transition: all 0.2s;
    padding: 0 4px;
    flex-shrink: 0;
  }
  .ec-close:hover { color: var(--text); transform: scale(1.1); }

  .plotly-chart { width: 100%; min-height: 380px; }

  .empty-state {
    font-family: var(--font-sans);
    font-size: 12px;
    color: var(--label);
    text-align: center;
    padding: 60px 20px;
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 10px;
  }

  @media (max-width: 768px) {
    .controls-row { flex-direction: column; align-items: stretch; }
    .select { min-width: unset; width: 100%; }
    .card-grid { grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); }
    .district-header { flex-direction: column; align-items: flex-start; gap: 16px; }
    .dh-stats { gap: 20px; }
    .expanded-chart { padding: 16px; }
  }
</style>
