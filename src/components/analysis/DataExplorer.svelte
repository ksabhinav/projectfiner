<script lang="ts">
  import { onMount } from 'svelte';
  import { CATEGORY_INFO, prettyCategoryName } from '../../lib/slbc-categories';

  const base = import.meta.env.BASE_URL;

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
    { name: 'West Bengal', slug: 'west-bengal' },
  ];

  let Plotly: any = $state(null);
  let masterData: any = $state(null);
  let loading = $state(true);
  let loadingState = $state(false);
  let error = $state('');

  // User selections
  let selectedState = $state('meghalaya');
  let selectedCategory = $state('branch_network');
  let selectedFieldX = $state('');
  let selectedFieldY = $state('');
  let selectedQuarter = $state('');
  let chartType: 'scatter' | 'bar' | 'line' = $state('scatter');
  let colorByDistrict = $state(true);

  // Custom data
  let customCsvText = $state('');
  let customData: { headers: string[]; rows: string[][] } | null = $state(null);
  let useCustomData = $state(false);

  // Quarter keys derived from master data
  let quarterKeys: string[] = $derived.by(() => {
    if (!masterData?.quarters) return [];
    return Object.keys(masterData.quarters).sort();
  });

  function quarterLabel(qkey: string): string {
    const q = masterData?.quarters?.[qkey];
    if (q?.period) return q.period;
    // Handle both YYYY-MM and name_year formats
    if (/^\d{4}-\d{2}$/.test(qkey)) {
      const [y, m] = qkey.split('-');
      const months: Record<string, string> = { '01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'May','06':'Jun','07':'Jul','08':'Aug','09':'Sep','10':'Oct','11':'Nov','12':'Dec' };
      return `${months[m] || m} ${y}`;
    }
    // snake_case like june_2020
    return qkey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  // Derived
  let availableCategories: string[] = $derived.by(() => {
    if (!masterData) return [];
    const cats = new Set<string>();
    for (const qkey of quarterKeys) {
      const q = masterData.quarters[qkey];
      if (!q) continue;
      Object.keys(q.tables).forEach(c => cats.add(c));
    }
    return [...cats].sort();
  });

  let availableFields: string[] = $derived.by(() => {
    if (useCustomData && customData) return customData.headers;
    if (!masterData || !selectedCategory) return [];
    const fields = new Set<string>();
    for (const qkey of quarterKeys) {
      const q = masterData.quarters[qkey];
      if (!q || !q.tables[selectedCategory]) continue;
      (q.tables[selectedCategory].fields || []).forEach((f: string) => fields.add(f));
    }
    return [...fields].sort();
  });

  let availableQuarters: string[] = $derived.by(() => {
    if (!masterData || !selectedCategory) return [];
    return quarterKeys.filter(qkey => masterData.quarters[qkey]?.tables[selectedCategory]);
  });

  // Districts derived from data
  let allDistricts: string[] = $derived.by(() => {
    if (!masterData) return [];
    const dists = new Set<string>();
    for (const q of Object.values(masterData.quarters) as any[]) {
      for (const tbl of Object.values(q.tables) as any[]) {
        const dd = tbl.districts || tbl.data || {};
        Object.keys(dd).forEach(d => dists.add(d));
      }
    }
    return [...dists].sort();
  });

  const PALETTE = [
    '#b8603e', '#3d7a8e', '#5a7a3a', '#8b6914', '#d4553a', '#2c6e8a',
    '#7a9a4a', '#a07820', '#c44830', '#4a8a6a', '#6b5e4c', '#9a6040',
    '#8e4585', '#4682b4', '#cd853f', '#6b8e23', '#bc8f8f', '#708090',
    '#b0c4de', '#daa520', '#8fbc8f', '#e9967a', '#5f9ea0', '#d2691e',
    '#9acd32', '#6495ed', '#db7093', '#556b2f', '#ff7f50', '#2e8b57',
    '#a0522d', '#4169e1', '#bdb76b', '#8b4513', '#20b2aa',
  ];

  function getChartData(): { x: number[]; y: number[]; labels: string[]; districts: string[] } {
    if (useCustomData && customData) {
      return getCustomChartData();
    }
    return getSLBCChartData();
  }

  function getSLBCChartData() {
    const x: number[] = [], y: number[] = [], labels: string[] = [], districts: string[] = [];
    if (!masterData || !selectedFieldX || !selectedFieldY) return { x, y, labels, districts };

    const quarters = selectedQuarter ? [selectedQuarter] : availableQuarters;

    for (const qkey of quarters) {
      const q = masterData.quarters[qkey];
      if (!q || !q.tables[selectedCategory]) continue;
      const tbl = q.tables[selectedCategory];
      const distData = tbl.districts || tbl.data || {};

      for (const [dist, vals] of Object.entries(distData)) {
        const xVal = parseFloat(String((vals as any)[selectedFieldX] || '').replace(/,/g, ''));
        const yVal = parseFloat(String((vals as any)[selectedFieldY] || '').replace(/,/g, ''));
        if (!isNaN(xVal) && !isNaN(yVal)) {
          x.push(xVal);
          y.push(yVal);
          labels.push(`${dist} (${quarterLabel(qkey)})`);
          districts.push(dist);
        }
      }
    }
    return { x, y, labels, districts };
  }

  function getCustomChartData() {
    const x: number[] = [], y: number[] = [], labels: string[] = [], districts: string[] = [];
    if (!customData || !selectedFieldX || !selectedFieldY) return { x, y, labels, districts };

    const xi = customData.headers.indexOf(selectedFieldX);
    const yi = customData.headers.indexOf(selectedFieldY);
    if (xi < 0 || yi < 0) return { x, y, labels, districts };

    for (const row of customData.rows) {
      const xVal = parseFloat(String(row[xi] || '').replace(/,/g, ''));
      const yVal = parseFloat(String(row[yi] || '').replace(/,/g, ''));
      if (!isNaN(xVal) && !isNaN(yVal)) {
        x.push(xVal);
        y.push(yVal);
        labels.push(row[0] || `Row ${x.length}`);
        districts.push(row[0] || '');
      }
    }
    return { x, y, labels, districts };
  }

  function computeCorrelation(x: number[], y: number[]): number {
    const n = x.length;
    if (n < 2) return 0;
    const mx = x.reduce((a, b) => a + b, 0) / n;
    const my = y.reduce((a, b) => a + b, 0) / n;
    let num = 0, dx2 = 0, dy2 = 0;
    for (let i = 0; i < n; i++) {
      const dx = x[i] - mx, dy = y[i] - my;
      num += dx * dy;
      dx2 += dx * dx;
      dy2 += dy * dy;
    }
    const denom = Math.sqrt(dx2 * dy2);
    return denom === 0 ? 0 : num / denom;
  }

  let chartEl: HTMLDivElement;
  let correlation = $state(0);

  function renderChart() {
    if (!Plotly || !chartEl) return;
    const { x, y, labels, districts } = getChartData();
    if (x.length === 0) {
      Plotly.purge(chartEl);
      return;
    }

    correlation = computeCorrelation(x, y);

    const layout: any = {
      xaxis: { title: selectedFieldX, gridcolor: '#e8e5e0', zerolinecolor: '#e0ddd8' },
      yaxis: { title: selectedFieldY, gridcolor: '#e8e5e0', zerolinecolor: '#e0ddd8' },
      paper_bgcolor: '#fff',
      plot_bgcolor: '#fff',
      font: { family: 'Inter, sans-serif', size: 11, color: '#1a1410' },
      margin: { l: 60, r: 30, t: 40, b: 50 },
      hovermode: 'closest',
      showlegend: colorByDistrict && !useCustomData,
      legend: { font: { size: 9 }, orientation: 'h', y: -0.2 },
    };

    const config = {
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToAdd: ['downloadSVG'],
      toImageButtonOptions: { format: 'png', width: 1200, height: 800, scale: 2 },
    };

    if (chartType === 'scatter') {
      if (colorByDistrict && !useCustomData) {
        const uniqueDists = allDistricts.filter(d => districts.includes(d));
        const traces = uniqueDists.map((dist, i) => {
          const idx = x.map((_, j) => j).filter(j => districts[j] === dist);
          return {
            x: idx.map(j => x[j]),
            y: idx.map(j => y[j]),
            text: idx.map(j => labels[j]),
            name: dist,
            type: 'scatter' as const,
            mode: 'markers' as const,
            marker: { size: 8, color: PALETTE[i % PALETTE.length], opacity: 0.8 },
          };
        });
        Plotly.newPlot(chartEl, traces, layout, config);
      } else {
        Plotly.newPlot(chartEl, [{
          x, y, text: labels,
          type: 'scatter', mode: 'markers',
          marker: { size: 8, color: '#b8603e', opacity: 0.7 },
        }], layout, config);
      }
    } else if (chartType === 'bar') {
      Plotly.newPlot(chartEl, [{
        x: labels, y,
        type: 'bar',
        marker: { color: '#b8603e' },
      }], { ...layout, xaxis: { ...layout.xaxis, title: '' } }, config);
    } else if (chartType === 'line') {
      if (colorByDistrict && !useCustomData) {
        const uniqueDists = allDistricts.filter(d => districts.includes(d));
        const traces = uniqueDists.map((dist, i) => {
          const idx = x.map((_, j) => j).filter(j => districts[j] === dist);
          return {
            x: idx.map(j => labels[j]),
            y: idx.map(j => y[j]),
            name: dist,
            type: 'scatter' as const,
            mode: 'lines+markers' as const,
            line: { color: PALETTE[i % PALETTE.length], width: 2 },
            marker: { size: 5 },
          };
        });
        Plotly.newPlot(chartEl, traces, layout, config);
      } else {
        Plotly.newPlot(chartEl, [{
          x: labels, y,
          type: 'scatter', mode: 'lines+markers',
          line: { color: '#b8603e', width: 2 },
          marker: { size: 5 },
        }], layout, config);
      }
    }
  }

  function handleCsvUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      customCsvText = reader.result as string;
      parseCsv();
    };
    reader.readAsText(file);
  }

  function parseCsv() {
    if (!customCsvText.trim()) { customData = null; return; }
    const lines = customCsvText.trim().split('\n').map(l =>
      l.split(',').map(v => v.replace(/^"|"$/g, '').trim())
    );
    if (lines.length < 2) return;
    customData = { headers: lines[0], rows: lines.slice(1) };
    useCustomData = true;
    selectedFieldX = customData.headers[0] || '';
    selectedFieldY = customData.headers[1] || '';
  }

  function downloadChart() {
    if (!Plotly || !chartEl) return;
    Plotly.downloadImage(chartEl, { format: 'png', width: 1200, height: 800, scale: 2, filename: 'finer_chart' });
  }

  async function loadStateData(slug: string) {
    loadingState = true;
    try {
      const res = await fetch(`${base}slbc-data/${slug}/${slug}_complete.json`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      masterData = await res.json();
      selectedCategory = 'branch_network';
      selectedQuarter = '';
      selectedFieldX = '';
      selectedFieldY = '';
    } catch (e: any) {
      error = `Failed to load ${slug} data.`;
      masterData = null;
    }
    loadingState = false;
  }

  // Auto-select first fields when category changes
  $effect(() => {
    if (availableFields.length >= 2 && !useCustomData) {
      selectedFieldX = availableFields[0];
      selectedFieldY = availableFields[1];
    }
  });

  $effect(() => {
    if (availableQuarters.length > 0 && !selectedQuarter) {
      selectedQuarter = availableQuarters[availableQuarters.length - 1];
    }
  });

  // Re-render when selections change
  $effect(() => {
    // Touch all reactive deps
    selectedCategory; selectedFieldX; selectedFieldY; selectedQuarter; chartType; colorByDistrict; useCustomData; customData;
    renderChart();
  });

  // Load state data when state changes
  $effect(() => {
    if (selectedState && !loading) {
      loadStateData(selectedState);
    }
  });

  onMount(async () => {
    const [plotlyModule] = await Promise.all([
      import('plotly.js-dist-min'),
    ]);
    Plotly = plotlyModule.default || plotlyModule;
    await loadStateData(selectedState);
    loading = false;
  });
</script>

{#if loading}
  <div class="loading-msg">Loading data and charts...</div>
{:else if error}
  <div class="loading-msg">{error}</div>
{:else}
  <div class="explorer">
    <div class="controls">
      <!-- Data source toggle -->
      <div class="control-section">
        <div class="ctrl-label">Data Source</div>
        <div class="toggle-row">
          <button class="toggle-btn" class:active={!useCustomData} onclick={() => { useCustomData = false; }}>SLBC Data</button>
          <button class="toggle-btn" class:active={useCustomData} onclick={() => { useCustomData = true; }}>Your Data</button>
        </div>
      </div>

      {#if !useCustomData}
        <div class="control-section">
          <div class="ctrl-label">State</div>
          <select bind:value={selectedState} class="select">
            {#each STATES as st}
              <option value={st.slug}>{st.name}</option>
            {/each}
          </select>
          {#if loadingState}
            <div class="file-info">Loading...</div>
          {/if}
        </div>
      {/if}

      {#if useCustomData}
        <div class="control-section">
          <div class="ctrl-label">Upload CSV</div>
          <input type="file" accept=".csv" onchange={handleCsvUpload} class="file-input" />
          {#if customData}
            <div class="file-info">{customData.rows.length} rows × {customData.headers.length} columns</div>
          {/if}
        </div>
      {:else}
        <div class="control-section">
          <div class="ctrl-label">Category</div>
          <select bind:value={selectedCategory} class="select">
            {#each availableCategories as cat}
              <option value={cat}>{prettyCategoryName(cat)}</option>
            {/each}
          </select>
        </div>

        <div class="control-section">
          <div class="ctrl-label">Quarter</div>
          <select bind:value={selectedQuarter} class="select">
            <option value="">All quarters</option>
            {#each availableQuarters as qkey}
              <option value={qkey}>{quarterLabel(qkey)}</option>
            {/each}
          </select>
        </div>
      {/if}

      <div class="control-section">
        <div class="ctrl-label">X Axis</div>
        <select bind:value={selectedFieldX} class="select">
          {#each availableFields as f}
            <option value={f}>{f}</option>
          {/each}
        </select>
      </div>

      <div class="control-section">
        <div class="ctrl-label">Y Axis</div>
        <select bind:value={selectedFieldY} class="select">
          {#each availableFields as f}
            <option value={f}>{f}</option>
          {/each}
        </select>
      </div>

      <div class="control-section">
        <div class="ctrl-label">Chart Type</div>
        <div class="toggle-row">
          <button class="toggle-btn" class:active={chartType === 'scatter'} onclick={() => chartType = 'scatter'}>Scatter</button>
          <button class="toggle-btn" class:active={chartType === 'bar'} onclick={() => chartType = 'bar'}>Bar</button>
          <button class="toggle-btn" class:active={chartType === 'line'} onclick={() => chartType = 'line'}>Line</button>
        </div>
      </div>

      {#if !useCustomData}
        <div class="control-section">
          <label class="checkbox-label">
            <input type="checkbox" bind:checked={colorByDistrict} />
            Color by district
          </label>
        </div>
      {/if}

      <!-- Correlation -->
      {#if selectedFieldX && selectedFieldY && chartType === 'scatter'}
        <div class="stat-box">
          <div class="stat-label">Correlation (r)</div>
          <div class="stat-value" class:positive={correlation > 0} class:negative={correlation < 0}>
            {correlation.toFixed(4)}
          </div>
          <div class="stat-interp">
            {#if Math.abs(correlation) > 0.7}Strong
            {:else if Math.abs(correlation) > 0.4}Moderate
            {:else if Math.abs(correlation) > 0.2}Weak
            {:else}Very weak{/if}
            {correlation >= 0 ? 'positive' : 'negative'} correlation
          </div>
        </div>
      {/if}

      <button class="btn-download" onclick={downloadChart}>
        <svg viewBox="0 0 24 24" style="width:14px;height:14px;fill:currentColor"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
        Download Chart (PNG)
      </button>
    </div>

    <div class="chart-area">
      <div bind:this={chartEl} class="plotly-chart"></div>
    </div>
  </div>
{/if}

<style>
  .loading-msg { font-family: var(--font-sans); font-size: 12px; color: var(--label); text-align: center; padding: 60px; }

  .explorer { display: grid; grid-template-columns: 280px 1fr; gap: 24px; min-height: 600px; }

  .controls {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    box-shadow: var(--card-shadow);
    align-self: start;
    position: sticky;
    top: 20px;
  }

  .control-section { margin-bottom: 16px; }
  .ctrl-label {
    font-family: var(--font-sans);
    font-size: 8px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--label);
    margin-bottom: 6px;
  }

  .select {
    width: 100%;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 5px;
    background: #faf9f7;
    font-family: var(--font-sans);
    font-size: 11px;
    color: var(--text);
    cursor: pointer;
    appearance: none;
  }
  .select:focus { border-color: var(--accent); outline: none; }

  .toggle-row { display: flex; gap: 0; border: 1px solid var(--border-dark); border-radius: 5px; overflow: hidden; }
  .toggle-btn {
    flex: 1;
    padding: 7px 0;
    border: none;
    background: #faf9f7;
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--label);
    cursor: pointer;
    transition: all 0.2s;
    border-right: 1px solid var(--border-dark);
  }
  .toggle-btn:last-child { border-right: none; }
  .toggle-btn.active { background: var(--text); color: #fff; }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: var(--font-sans);
    font-size: 11px;
    color: var(--muted);
    cursor: pointer;
  }

  .file-input {
    width: 100%;
    font-family: var(--font-sans);
    font-size: 10px;
    color: var(--muted);
  }
  .file-info {
    font-family: var(--font-sans);
    font-size: 10px;
    color: var(--olive);
    margin-top: 4px;
  }

  .stat-box {
    background: #faf9f7;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 16px;
    text-align: center;
  }
  .stat-label { font-family: var(--font-sans); font-size: 8px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--label); margin-bottom: 4px; }
  .stat-value { font-family: var(--font-serif); font-size: 24px; font-weight: 700; color: var(--text); }
  .stat-value.positive { color: var(--olive); }
  .stat-value.negative { color: #c44830; }
  .stat-interp { font-family: var(--font-sans); font-size: 10px; color: var(--muted); margin-top: 2px; }

  .btn-download {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px;
    border: 1px solid var(--border-dark);
    background: var(--btn-bg);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border-radius: 5px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-download:hover { background: var(--text); color: #fff; border-color: var(--text); }

  .chart-area {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--card-shadow);
    padding: 16px;
    min-height: 500px;
  }

  .plotly-chart { width: 100%; min-height: 480px; }

  @media (max-width: 768px) {
    .explorer { grid-template-columns: 1fr; }
    .controls { position: static; }
  }
</style>
