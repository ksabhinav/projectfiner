<script lang="ts">
  import { onMount } from 'svelte';
  import { CATEGORY_INFO, prettyCategoryName } from '../../lib/slbc-categories';

  interface Props {
    baseUrl: string;
  }

  let { baseUrl }: Props = $props();

  const STATES = [
    { name: 'All States', slug: 'all' },
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

  const SINGLE_STATES = STATES.filter(s => s.slug !== 'all');

  // State
  let loading = $state(true);
  let loadingData = $state(false);
  let error = $state('');

  let selectedState = $state('assam');
  let selectedCategory = $state('');
  let selectedQuarter = $state('');
  let selectedField = $state('');
  let sortDir: 'desc' | 'asc' = $state('desc');
  let sortCol: 'value' | 'district' | 'state' = $state('value');

  // Loaded data: map of slug -> complete JSON
  let stateDataMap: Record<string, any> = $state({});

  // Current working data (single state or merged)
  let masterData: any = $state(null);
  let isAllStates = $derived(selectedState === 'all');

  // Quarter keys
  let quarterKeys: string[] = $derived.by(() => {
    if (!masterData?.quarters) return [];
    return Object.keys(masterData.quarters).sort();
  });

  function quarterLabel(qkey: string): string {
    const q = masterData?.quarters?.[qkey];
    if (q?.period) return q.period;
    return qkey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  // Available categories from data
  let availableCategories: string[] = $derived.by(() => {
    if (!masterData?.quarters) return [];
    const cats = new Set<string>();
    for (const qkey of quarterKeys) {
      const q = masterData.quarters[qkey];
      if (!q) continue;
      Object.keys(q.tables || {}).forEach(c => cats.add(c));
    }
    return [...cats].sort();
  });

  // Available quarters for selected category
  let availableQuarters: string[] = $derived.by(() => {
    if (!masterData || !selectedCategory) return [];
    return quarterKeys.filter(qkey => masterData.quarters[qkey]?.tables?.[selectedCategory]);
  });

  // Available fields for selected category in the selected quarter
  let availableFields: string[] = $derived.by(() => {
    if (!masterData || !selectedCategory || !selectedQuarter) return [];
    const q = masterData.quarters[selectedQuarter];
    if (!q || !q.tables?.[selectedCategory]) return [];
    const fields = q.tables[selectedCategory].fields || [];
    return fields.filter((f: string) => f.toLowerCase() !== 'district').sort();
  });

  // CD ratio detection
  let isCDRatio = $derived(
    selectedCategory === 'credit_deposit_ratio' &&
    /ratio|c.*d.*ratio/i.test(selectedField)
  );

  // Build ranking rows
  interface RankRow {
    district: string;
    state: string;
    value: number;
    raw: string;
  }

  let rankingRows: RankRow[] = $derived.by(() => {
    if (!masterData || !selectedCategory || !selectedQuarter || !selectedField) return [];

    const q = masterData.quarters[selectedQuarter];
    if (!q || !q.tables?.[selectedCategory]) return [];

    const tbl = q.tables[selectedCategory];
    const distData = tbl.districts || tbl.data || {};
    const rows: RankRow[] = [];

    for (const [dist, vals] of Object.entries(distData as Record<string, any>)) {
      const raw = String(vals[selectedField] || '').replace(/,/g, '');
      const value = parseFloat(raw);
      if (!isNaN(value)) {
        rows.push({
          district: dist,
          state: vals.__state || '',
          value,
          raw: vals[selectedField] || '',
        });
      }
    }

    return rows;
  });

  // Sort rows
  let sortedRows: RankRow[] = $derived.by(() => {
    const rows = [...rankingRows];
    const dir = sortDir === 'desc' ? -1 : 1;

    if (sortCol === 'value') {
      rows.sort((a, b) => (a.value - b.value) * dir);
    } else if (sortCol === 'district') {
      rows.sort((a, b) => a.district.localeCompare(b.district) * dir);
    } else if (sortCol === 'state') {
      rows.sort((a, b) => a.state.localeCompare(b.state) * dir);
    }

    return rows;
  });

  // Max value for bar widths
  let maxValue = $derived(
    sortedRows.length > 0 ? Math.max(...sortedRows.map(r => Math.abs(r.value))) : 1
  );

  // Traffic light logic
  function getStatus(value: number, allValues: number[]): { color: string; label: string } {
    if (isCDRatio) {
      if (value >= 60) return { color: '#5a7a3a', label: 'Good' };
      if (value >= 40) return { color: '#b8960a', label: 'Moderate' };
      return { color: '#c44830', label: 'Low' };
    }

    // Quartile-based
    const sorted = [...allValues].sort((a, b) => a - b);
    const n = sorted.length;
    if (n === 0) return { color: '#aaa09a', label: '--' };

    const q1 = sorted[Math.floor(n * 0.25)];
    const q3 = sorted[Math.floor(n * 0.75)];

    if (value >= q3) return { color: '#5a7a3a', label: 'Top' };
    if (value >= q1) return { color: '#b8960a', label: 'Mid' };
    return { color: '#c44830', label: 'Bottom' };
  }

  let allValues = $derived(rankingRows.map(r => r.value));

  // Format number for display
  function formatValue(v: number): string {
    if (isCDRatio) return v.toFixed(2) + '%';
    if (Math.abs(v) >= 10000) return v.toLocaleString('en-IN', { maximumFractionDigits: 0 });
    if (Math.abs(v) >= 100) return v.toLocaleString('en-IN', { maximumFractionDigits: 1 });
    return v.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  }

  // Pretty field name
  function prettyField(f: string): string {
    return f.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  // Column sort handler
  function toggleSort(col: 'value' | 'district' | 'state') {
    if (sortCol === col) {
      sortDir = sortDir === 'desc' ? 'asc' : 'desc';
    } else {
      sortCol = col;
      sortDir = col === 'value' ? 'desc' : 'asc';
    }
  }

  function sortArrow(col: string): string {
    if (sortCol !== col) return '';
    return sortDir === 'desc' ? ' \u25BC' : ' \u25B2';
  }

  // Data loading
  async function loadSingleState(slug: string): Promise<any> {
    if (stateDataMap[slug]) return stateDataMap[slug];
    const res = await fetch(`${baseUrl}slbc-data/${slug}/${slug}_complete.json`);
    if (!res.ok) throw new Error(`HTTP ${res.status} loading ${slug}`);
    const data = await res.json();
    stateDataMap[slug] = data;
    return data;
  }

  async function loadAllStates(): Promise<any> {
    const results = await Promise.all(
      SINGLE_STATES.map(async (st) => {
        try {
          const data = await loadSingleState(st.slug);
          return { slug: st.slug, name: st.name, data };
        } catch {
          return null;
        }
      })
    );

    // Merge into single masterData structure
    const merged: any = { quarters: {} };

    for (const res of results) {
      if (!res || !res.data?.quarters) continue;
      for (const [qkey, qval] of Object.entries(res.data.quarters as Record<string, any>)) {
        if (!merged.quarters[qkey]) {
          merged.quarters[qkey] = { period: qval.period, tables: {} };
        }
        const mq = merged.quarters[qkey];
        for (const [cat, tbl] of Object.entries(qval.tables as Record<string, any>)) {
          if (!mq.tables[cat]) {
            mq.tables[cat] = { fields: [...(tbl.fields || [])], districts: {} };
          }
          const mt = mq.tables[cat];
          // Merge fields
          for (const f of (tbl.fields || [])) {
            if (!mt.fields.includes(f)) mt.fields.push(f);
          }
          // Merge districts with state tag
          const distData = tbl.districts || tbl.data || {};
          for (const [dist, vals] of Object.entries(distData as Record<string, any>)) {
            const key = `${dist} (${res.name})`;
            mt.districts[key] = { ...vals, __state: res.name };
          }
        }
      }
    }

    return merged;
  }

  async function loadData() {
    loadingData = true;
    error = '';
    try {
      if (selectedState === 'all') {
        masterData = await loadAllStates();
      } else {
        masterData = await loadSingleState(selectedState);
      }
    } catch (e: any) {
      error = `Failed to load data: ${e.message}`;
      masterData = null;
    }
    loadingData = false;
  }

  // Auto-select defaults when category changes
  $effect(() => {
    if (availableCategories.length > 0 && !availableCategories.includes(selectedCategory)) {
      selectedCategory = availableCategories.includes('credit_deposit_ratio')
        ? 'credit_deposit_ratio'
        : availableCategories[0];
    }
  });

  $effect(() => {
    if (availableQuarters.length > 0 && !availableQuarters.includes(selectedQuarter)) {
      selectedQuarter = availableQuarters[availableQuarters.length - 1];
    }
  });

  $effect(() => {
    if (availableFields.length > 0 && !availableFields.includes(selectedField)) {
      // Prefer ratio/percentage fields as default
      const ratioField = availableFields.find(f => /ratio|cd ratio/i.test(f));
      selectedField = ratioField || availableFields[0];
    }
  });

  // Load data when state changes
  $effect(() => {
    selectedState;
    if (!loading) {
      loadData();
    }
  });

  onMount(async () => {
    await loadData();
    loading = false;
  });
</script>

{#if loading}
  <div class="loading-msg">Loading rankings data...</div>
{:else if error}
  <div class="loading-msg error-msg">{error}</div>
{:else}
  <div class="rankings-layout">
    <!-- Controls sidebar -->
    <div class="controls">
      <div class="control-section">
        <div class="ctrl-label">State</div>
        <select bind:value={selectedState} class="select">
          {#each STATES as st}
            <option value={st.slug}>{st.name}</option>
          {/each}
        </select>
        {#if loadingData}
          <div class="load-hint">Loading...</div>
        {/if}
      </div>

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
          {#each availableQuarters as qkey}
            <option value={qkey}>{quarterLabel(qkey)}</option>
          {/each}
        </select>
      </div>

      <div class="control-section">
        <div class="ctrl-label">Metric</div>
        <select bind:value={selectedField} class="select">
          {#each availableFields as f}
            <option value={f}>{prettyField(f)}</option>
          {/each}
        </select>
      </div>

      <!-- Summary stats -->
      {#if sortedRows.length > 0}
        <div class="summary-box">
          <div class="summary-row">
            <span class="summary-label">Districts</span>
            <span class="summary-value">{sortedRows.length}</span>
          </div>
          <div class="summary-row">
            <span class="summary-label">Max</span>
            <span class="summary-value">{formatValue(Math.max(...allValues))}</span>
          </div>
          <div class="summary-row">
            <span class="summary-label">Min</span>
            <span class="summary-value">{formatValue(Math.min(...allValues))}</span>
          </div>
          <div class="summary-row">
            <span class="summary-label">Median</span>
            <span class="summary-value">{formatValue((() => {
              const s = [...allValues].sort((a, b) => a - b);
              const mid = Math.floor(s.length / 2);
              return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
            })())}</span>
          </div>
        </div>
      {/if}
    </div>

    <!-- Table area -->
    <div class="table-area">
      {#if loadingData}
        <div class="loading-msg">Loading data...</div>
      {:else if sortedRows.length === 0}
        <div class="loading-msg">No data available for this selection.</div>
      {:else}
        <div class="table-header-info">
          <span class="result-count">{sortedRows.length} districts</span>
          <span class="metric-label">{prettyField(selectedField)}</span>
        </div>
        <div class="table-scroll">
          <table class="ranking-table">
            <thead>
              <tr>
                <th class="col-rank">#</th>
                <th class="col-district sortable" onclick={() => toggleSort('district')}>
                  District{sortArrow('district')}
                </th>
                {#if isAllStates}
                  <th class="col-state sortable" onclick={() => toggleSort('state')}>
                    State{sortArrow('state')}
                  </th>
                {/if}
                <th class="col-value sortable" onclick={() => toggleSort('value')}>
                  Value{sortArrow('value')}
                </th>
                <th class="col-bar">Distribution</th>
                <th class="col-status">Status</th>
              </tr>
            </thead>
            <tbody>
              {#each sortedRows as row, i}
                {@const status = getStatus(row.value, allValues)}
                {@const barWidth = maxValue > 0 ? (Math.abs(row.value) / maxValue) * 100 : 0}
                <tr>
                  <td class="col-rank rank-num">{i + 1}</td>
                  <td class="col-district">
                    {#if isAllStates}
                      {row.district.replace(/ \(.*\)$/, '')}
                    {:else}
                      {row.district}
                    {/if}
                  </td>
                  {#if isAllStates}
                    <td class="col-state">{row.state}</td>
                  {/if}
                  <td class="col-value mono-value">{formatValue(row.value)}</td>
                  <td class="col-bar">
                    <div class="bar-track">
                      <div
                        class="bar-fill"
                        style="width: {barWidth}%; background-color: {status.color};"
                      ></div>
                    </div>
                  </td>
                  <td class="col-status">
                    <span class="status-badge" style="
                      color: {status.color};
                      background: {status.color}18;
                      border-color: {status.color}40;
                    ">{status.label}</span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  /* Layout */
  .rankings-layout {
    display: grid;
    grid-template-columns: 260px 1fr;
    gap: 24px;
    min-height: 500px;
  }

  /* Loading / error */
  .loading-msg {
    font-family: var(--font-sans);
    font-size: 12px;
    color: var(--label);
    text-align: center;
    padding: 60px;
  }
  .error-msg { color: #c44830; }

  /* Controls */
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
    font-size: 9px;
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

  .load-hint {
    font-family: var(--font-sans);
    font-size: 10px;
    color: var(--olive);
    margin-top: 4px;
  }

  /* Summary */
  .summary-box {
    background: #faf9f7;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    margin-top: 8px;
  }
  .summary-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 3px 0;
  }
  .summary-label {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--label);
  }
  .summary-value {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    color: var(--text);
  }

  /* Table area */
  .table-area {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--card-shadow);
    padding: 16px;
    overflow: hidden;
  }

  .table-header-info {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 12px;
    padding: 0 4px;
  }
  .result-count {
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .metric-label {
    font-family: var(--font-sans);
    font-size: 10px;
    color: var(--label);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }

  .table-scroll {
    overflow-x: auto;
  }

  .ranking-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-sans);
    font-size: 12px;
  }

  .ranking-table thead th {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--label);
    padding: 10px 8px;
    border-bottom: 2px solid var(--border);
    text-align: left;
    white-space: nowrap;
    user-select: none;
  }

  .ranking-table thead th.sortable {
    cursor: pointer;
    transition: color 0.15s;
  }
  .ranking-table thead th.sortable:hover {
    color: var(--text);
  }

  .ranking-table tbody td {
    padding: 9px 8px;
    border-bottom: 1px solid #f0eeea;
    vertical-align: middle;
  }

  .ranking-table tbody tr:hover {
    background: #fdfcfa;
  }

  .col-rank {
    width: 40px;
    text-align: center;
  }
  .rank-num {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--muted);
    font-weight: 500;
  }

  .col-district {
    font-family: var(--font-serif);
    font-size: 13px;
    color: var(--text);
    min-width: 140px;
  }

  .col-state {
    font-family: var(--font-sans);
    font-size: 11px;
    color: var(--muted);
    min-width: 100px;
  }

  .col-value {
    text-align: right;
    min-width: 90px;
  }
  .mono-value {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    color: var(--text);
  }

  .col-bar {
    width: 160px;
    min-width: 120px;
    padding-left: 12px;
    padding-right: 12px;
  }
  .bar-track {
    width: 100%;
    height: 8px;
    background: #f0eeea;
    border-radius: 4px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
  }

  .col-status {
    width: 80px;
    text-align: center;
  }
  .status-badge {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 3px 10px;
    border: 1px solid;
    border-radius: 20px;
    white-space: nowrap;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .rankings-layout { grid-template-columns: 1fr; }
    .controls { position: static; }
    .col-bar { display: none; }
  }
</style>
