<script lang="ts">
  import { onMount } from 'svelte';

  interface Props {
    basePath: string;
  }
  let { basePath }: Props = $props();

  // ── State definitions ──
  const STATES = [
    { name: 'Assam', slug: 'assam', color: '#b8603e' },
    { name: 'Meghalaya', slug: 'meghalaya', color: '#3d7a8e' },
    { name: 'Manipur', slug: 'manipur', color: '#5a7a3a' },
    { name: 'Arunachal Pradesh', slug: 'arunachal-pradesh', color: '#8b6914' },
    { name: 'Mizoram', slug: 'mizoram', color: '#6b5b95' },
    { name: 'Tripura', slug: 'tripura', color: '#d4553a' },
    { name: 'Nagaland', slug: 'nagaland', color: '#2a7a5a' },
    { name: 'Sikkim', slug: 'sikkim', color: '#555048' },
  ];

  // ── 7 Key Indicators with metric definitions ──
  const INDICATORS = [
    {
      id: 'credit_deposit_ratio',
      title: 'Credit-Deposit Ratio',
      subtitle: 'How much of deposits are lent back locally',
      icon: '📊',
      metrics: [
        { field: 'overall_cd_ratio', label: 'Overall CD Ratio', unit: '%', primary: true },
        { field: 'total_deposit', label: 'Total Deposits', unit: '₹ Lakh' },
        { field: 'total_advance', label: 'Total Advances', unit: '₹ Lakh' },
        { field: 'total_branch', label: 'Branches', unit: '' },
      ],
      stateSum: false, // CD ratio should be averaged, not summed
    },
    {
      id: 'pmjdy',
      title: 'PM Jan Dhan Yojana',
      subtitle: 'Bank account penetration among the unbanked',
      icon: '🏦',
      metrics: [
        { field: 'total_pmjdy_no', label: 'Total PMJDY Accounts', unit: '', primary: true },
        { field: 'no_of_zero_balance_a_c', label: 'Zero Balance A/C', unit: '' },
        { field: 'no_of_aadhaar_seeded', label: 'Aadhaar Seeded', unit: '' },
        { field: 'no_of_rupay_card_issued', label: 'RuPay Cards Issued', unit: '' },
        { field: 'female_no', label: 'Female Accounts', unit: '' },
        { field: 'rural_no', label: 'Rural Accounts', unit: '' },
      ],
      stateSum: true,
    },
    {
      id: 'branch_network',
      title: 'Branch Network',
      subtitle: 'Physical banking infrastructure',
      icon: '🏢',
      metrics: [
        { field: 'total_branch', label: 'Total Branches', unit: '', primary: true },
        { field: 'branch_rural', label: 'Rural Branches', unit: '' },
        { field: 'branch_semi_urban', label: 'Semi-Urban', unit: '' },
        { field: 'branch_urban', label: 'Urban', unit: '' },
        { field: 'total_atm', label: 'Total ATMs', unit: '' },
        { field: 'total_csp', label: 'Total CSPs', unit: '' },
      ],
      stateSum: true,
    },
    {
      id: 'kcc',
      title: 'Kisan Credit Card',
      subtitle: 'Agricultural credit access',
      icon: '🌾',
      metrics: [
        { field: 'total_no_of_kcc', label: 'Total KCC', unit: '', primary: true, fallbacks: ['no_of_kcc', 'kcc_no', 'total_kcc_no'] },
        { field: 'outstanding_amt', label: 'Outstanding Amt', unit: '₹ Lakh', fallbacks: ['total_outstanding', 'total_o_s_kcc_amt'] },
        { field: 'no_of_rupay_card_issued', label: 'RuPay Cards', unit: '' },
        { field: 'kcc_card_activated', label: 'Cards Activated', unit: '', fallbacks: ['card_activated'] },
      ],
      stateSum: true,
    },
    {
      id: 'shg',
      title: 'Self Help Groups',
      subtitle: 'Women\'s financial inclusion & micro-credit',
      icon: '👥',
      metrics: [
        { field: 'savings_linked_no', label: 'Savings Linked SHGs', unit: '', primary: true, fallbacks: ['credit_linked_no'] },
        { field: 'credit_linked_no', label: 'Credit Linked SHGs', unit: '' },
        { field: 'shg_o_s_amt', label: 'Outstanding Amt', unit: '₹ Lakh', fallbacks: ['outstanding_amt'] },
        { field: 'shg_npa_pct', label: 'SHG NPA %', unit: '%' },
      ],
      stateSum: true,
    },
    {
      id: 'digital_transactions',
      title: 'Digital Transactions',
      subtitle: 'UPI, IMPS, BHIM adoption',
      icon: '📱',
      metrics: [
        { field: 'bhim_upi_a_c', label: 'BHIM/UPI Transactions', unit: '', primary: true, fallbacks: ['bhim_upi'] },
        { field: 'bhim_upi_amt', label: 'UPI Amount', unit: '₹ Lakh' },
        { field: 'imps_a_c', label: 'IMPS Transactions', unit: '', fallbacks: ['imps'] },
        { field: 'cards_debit_credit_a_c', label: 'Card Transactions', unit: '', fallbacks: ['cards_debit_credit', 'cards_debit'] },
      ],
      stateSum: true,
    },
    {
      id: 'aadhaar_authentication',
      title: 'Aadhaar Authentication',
      subtitle: 'Identity-linked banking coverage',
      icon: '🆔',
      metrics: [
        { field: 'no_of_aadhaar_seeded_casa', label: 'Aadhaar Seeded CASA', unit: '', primary: true, fallbacks: ['aadhaar_seeded_casa'] },
        { field: 'no_of_operative_casa', label: 'Operative CASA', unit: '', fallbacks: ['operative_casa'] },
        { field: 'no_of_authenticated_casa', label: 'Authenticated CASA', unit: '', fallbacks: ['authenticated_casa'] },
      ],
      stateSum: true,
    },
  ];

  // ── Reactive state ──
  let stateData: Record<string, any> = $state({});
  let loading = $state(true);
  let error = $state('');
  let selectedQuarter = $state('');
  let selectedIndicator = $state('credit_deposit_ratio');
  let Plotly: any = $state(null);

  // ── Derived: available quarters across all loaded states ──
  let allQuarters: string[] = $derived.by(() => {
    const qSet = new Set<string>();
    for (const st of STATES) {
      const d = stateData[st.slug];
      if (!d) continue;
      for (const rec of d) {
        if (rec.period) qSet.add(rec.period);
      }
    }
    return [...qSet].sort();
  });

  let latestQuarter: string = $derived(allQuarters.length ? allQuarters[allQuarters.length - 1] : '');

  let activeQuarter: string = $derived(selectedQuarter || latestQuarter);

  // ── Derived: indicator config ──
  let currentIndicator = $derived(INDICATORS.find(i => i.id === selectedIndicator)!);

  // ── Helper: get value for a field with fallbacks ──
  function getFieldValue(record: any, category: string, field: string, fallbacks?: string[]): number | null {
    const key = `${category}__${field}`;
    let val = record[key];
    if (val != null && val !== '' && !isNaN(Number(val))) return Number(val);
    if (fallbacks) {
      for (const fb of fallbacks) {
        const fbKey = `${category}__${fb}`;
        val = record[fbKey];
        if (val != null && val !== '' && !isNaN(Number(val))) return Number(val);
      }
    }
    return null;
  }

  // ── Derived: state-level aggregated data for the current indicator + quarter ──
  type StateMetric = { state: typeof STATES[number]; values: Record<string, number | null> };

  let stateMetrics: StateMetric[] = $derived.by(() => {
    if (!activeQuarter) return [];
    const result: StateMetric[] = [];

    for (const st of STATES) {
      const data = stateData[st.slug];
      if (!data || !data.length) continue;

      // Get all records for this quarter
      const qRecords = data.filter((r: any) => r.period === activeQuarter);
      if (!qRecords.length) continue;

      const values: Record<string, number | null> = {};
      for (const metric of currentIndicator.metrics) {
        let nums: number[] = [];
        for (const rec of qRecords) {
          const v = getFieldValue(rec, currentIndicator.id, metric.field, (metric as any).fallbacks);
          if (v !== null) nums.push(v);
        }
        if (nums.length === 0) {
          values[metric.field] = null;
        } else if (metric.unit === '%' || !currentIndicator.stateSum) {
          // Average for percentages/ratios
          values[metric.field] = nums.reduce((a, b) => a + b, 0) / nums.length;
        } else {
          // Sum for counts/amounts
          values[metric.field] = nums.reduce((a, b) => a + b, 0);
        }
      }
      result.push({ state: st, values });
    }
    return result;
  });

  // ── Derived: trend data (primary metric over time per state) ──
  type TrendPoint = { quarter: string; value: number };
  type StateTrend = { state: typeof STATES[number]; points: TrendPoint[] };

  let trendData: StateTrend[] = $derived.by(() => {
    const primaryMetric = currentIndicator.metrics.find(m => m.primary);
    if (!primaryMetric) return [];

    const result: StateTrend[] = [];
    for (const st of STATES) {
      const data = stateData[st.slug];
      if (!data || !data.length) continue;

      const points: TrendPoint[] = [];
      for (const q of allQuarters) {
        const qRecords = data.filter((r: any) => r.period === q);
        if (!qRecords.length) continue;

        let nums: number[] = [];
        for (const rec of qRecords) {
          const v = getFieldValue(rec, currentIndicator.id, primaryMetric.field, (primaryMetric as any).fallbacks);
          if (v !== null) nums.push(v);
        }
        if (nums.length > 0) {
          const val = primaryMetric.unit === '%' || !currentIndicator.stateSum
            ? nums.reduce((a, b) => a + b, 0) / nums.length
            : nums.reduce((a, b) => a + b, 0);
          points.push({ quarter: q, value: val });
        }
      }
      if (points.length > 0) result.push({ state: st, points });
    }
    return result;
  });

  // ── Format numbers ──
  function fmt(n: number | null, unit: string): string {
    if (n === null || n === undefined) return '—';
    if (unit === '%') return n.toFixed(1) + '%';
    if (Math.abs(n) >= 1e7) return (n / 1e7).toFixed(1) + ' Cr';
    if (Math.abs(n) >= 1e5) return (n / 1e5).toFixed(1) + ' L';
    if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    if (n % 1 !== 0) return n.toFixed(1);
    return n.toLocaleString('en-IN');
  }

  function fmtFull(n: number | null): string {
    if (n === null || n === undefined) return '—';
    if (n % 1 !== 0) return n.toFixed(2);
    return n.toLocaleString('en-IN');
  }

  function fmtQuarter(q: string): string {
    // "2024-09" → "Sep 2024"
    const parts = q.split('-');
    if (parts.length !== 2) return q;
    const months: Record<string, string> = { '03': 'Mar', '06': 'Jun', '09': 'Sep', '12': 'Dec' };
    return (months[parts[1]] || parts[1]) + ' ' + parts[0];
  }

  // ── Chart rendering ──
  let barChartEl: HTMLDivElement | null = $state(null);
  let trendChartEl: HTMLDivElement | null = $state(null);

  function renderBarChart() {
    if (!Plotly || !barChartEl || !stateMetrics.length) return;

    const primaryMetric = currentIndicator.metrics.find(m => m.primary);
    if (!primaryMetric) return;

    const states = stateMetrics
      .filter(sm => sm.values[primaryMetric.field] !== null)
      .sort((a, b) => (b.values[primaryMetric.field] ?? 0) - (a.values[primaryMetric.field] ?? 0));

    const trace = {
      x: states.map(s => s.state.name),
      y: states.map(s => s.values[primaryMetric.field]),
      type: 'bar',
      marker: {
        color: states.map(s => s.state.color),
        line: { color: 'rgba(0,0,0,0.05)', width: 1 },
      },
      text: states.map(s => fmt(s.values[primaryMetric.field], primaryMetric.unit)),
      textposition: 'outside',
      textfont: { family: 'Inter, sans-serif', size: 11, color: '#555048' },
      hovertemplate: '%{x}<br>' + primaryMetric.label + ': %{y:,.0f}<extra></extra>',
    };

    const layout = {
      margin: { t: 20, b: 60, l: 60, r: 20 },
      height: 340,
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { family: 'Inter, sans-serif', size: 11, color: '#555048' },
      xaxis: {
        tickangle: -30,
        tickfont: { size: 10, family: 'Inter, sans-serif' },
        gridcolor: 'transparent',
      },
      yaxis: {
        title: primaryMetric.label + (primaryMetric.unit ? ` (${primaryMetric.unit})` : ''),
        gridcolor: '#e8e5e0',
        gridwidth: 1,
        zeroline: true,
        zerolinecolor: '#e8e5e0',
      },
      bargap: 0.35,
    };

    Plotly.newPlot(barChartEl, [trace], layout, { displayModeBar: false, responsive: true });
  }

  function renderTrendChart() {
    if (!Plotly || !trendChartEl || !trendData.length) return;

    const primaryMetric = currentIndicator.metrics.find(m => m.primary);
    if (!primaryMetric) return;

    const traces = trendData.map(st => ({
      x: st.points.map(p => fmtQuarter(p.quarter)),
      y: st.points.map(p => p.value),
      name: st.state.name,
      type: 'scatter',
      mode: 'lines+markers',
      line: { color: st.state.color, width: 2.5 },
      marker: { size: 5, color: st.state.color },
      hovertemplate: st.state.name + '<br>%{x}: %{y:,.0f}<extra></extra>',
    }));

    const layout = {
      margin: { t: 20, b: 70, l: 60, r: 20 },
      height: 380,
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { family: 'Inter, sans-serif', size: 11, color: '#555048' },
      xaxis: {
        tickangle: -45,
        tickfont: { size: 9, family: 'Inter, sans-serif' },
        gridcolor: '#f0ede8',
      },
      yaxis: {
        title: primaryMetric.label + (primaryMetric.unit ? ` (${primaryMetric.unit})` : ''),
        gridcolor: '#e8e5e0',
        gridwidth: 1,
      },
      legend: {
        orientation: 'h',
        y: -0.3,
        x: 0.5,
        xanchor: 'center',
        font: { size: 10 },
      },
      hovermode: 'x unified',
    };

    Plotly.newPlot(trendChartEl, traces, layout, { displayModeBar: false, responsive: true });
  }

  // ── Re-render charts when data changes ──
  $effect(() => {
    stateMetrics;
    activeQuarter;
    selectedIndicator;
    renderBarChart();
  });

  $effect(() => {
    trendData;
    selectedIndicator;
    renderTrendChart();
  });

  // ── Helper: flatten nested timeseries JSON into flat records ──
  function flattenTimeseries(json: any): any[] {
    // JSON structure: { periods: [{ period, districts: [{ district, period, category__field, ... }] }] }
    if (Array.isArray(json)) return json; // already flat
    if (!json || !json.periods) return [];
    const records: any[] = [];
    for (const p of json.periods) {
      if (!p.districts) continue;
      for (const d of p.districts) {
        records.push(d);
      }
    }
    return records;
  }

  // ── Helper: convert period names to sortable format ──
  // "June 2018" → "2018-06", "September 2024" → "2024-09", "March 2022" → "2022-03"
  function normalizePeriod(p: string): string {
    if (/^\d{4}-\d{2}$/.test(p)) return p; // already YYYY-MM
    const monthMap: Record<string, string> = {
      'january': '01', 'february': '02', 'march': '03', 'april': '04',
      'may': '05', 'june': '06', 'july': '07', 'august': '08',
      'september': '09', 'october': '10', 'november': '11', 'december': '12',
      'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
      'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 'sept': '09',
      'oct': '10', 'nov': '11', 'dec': '12',
    };
    const parts = p.trim().toLowerCase().split(/\s+/);
    if (parts.length === 2) {
      const month = monthMap[parts[0]];
      const year = parts[1];
      if (month && year) return `${year}-${month}`;
    }
    return p;
  }

  // ── Load data on mount ──
  onMount(async () => {
    try {
      // Load Plotly and state data in parallel
      const [plotlyMod, ...stateResults] = await Promise.all([
        import('plotly.js-dist-min'),
        ...STATES.map(async (st) => {
          try {
            const url = `${basePath}slbc-data/${st.slug}/${st.slug}_fi_timeseries.json`;
            const res = await fetch(url);
            if (!res.ok) return { slug: st.slug, data: [] };
            const json = await res.json();
            // Flatten and normalize periods
            const flat = flattenTimeseries(json);
            for (const rec of flat) {
              if (rec.period) rec.period = normalizePeriod(rec.period);
            }
            return { slug: st.slug, data: flat };
          } catch {
            return { slug: st.slug, data: [] };
          }
        }),
      ]);

      Plotly = plotlyMod.default || plotlyMod;

      const newData: Record<string, any> = {};
      for (const r of stateResults) {
        newData[r.slug] = r.data;
      }
      stateData = newData;
      loading = false;
    } catch (e: any) {
      error = e.message;
      loading = false;
    }
  });
</script>

<div class="fi-dashboard">
  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading data from 8 states…</p>
    </div>
  {:else if error}
    <div class="error-state">
      <p>Error loading data: {error}</p>
    </div>
  {:else}
    <!-- Indicator selector pills -->
    <div class="indicator-bar">
      <div class="indicator-pills">
        {#each INDICATORS as ind}
          <button
            class="ind-pill"
            class:active={selectedIndicator === ind.id}
            onclick={() => selectedIndicator = ind.id}
          >
            <span class="ind-icon">{ind.icon}</span>
            <span class="ind-name">{ind.title}</span>
          </button>
        {/each}
      </div>
    </div>

    <!-- Quarter selector -->
    <div class="controls-bar">
      <div class="quarter-selector">
        <span class="ctrl-label">Quarter</span>
        <select bind:value={selectedQuarter} class="ctrl-select">
          <option value="">Latest ({fmtQuarter(latestQuarter)})</option>
          {#each [...allQuarters].reverse() as q}
            <option value={q}>{fmtQuarter(q)}</option>
          {/each}
        </select>
      </div>
      <div class="indicator-desc">
        <h2>{currentIndicator.icon} {currentIndicator.title}</h2>
        <p>{currentIndicator.subtitle}</p>
      </div>
    </div>

    <!-- Main content grid -->
    <div class="dashboard-grid">
      <!-- State comparison cards -->
      <div class="metric-cards">
        <div class="section-label">State Comparison · {fmtQuarter(activeQuarter)}</div>
        <div class="cards-grid">
          {#each stateMetrics.sort((a, b) => {
            const pm = currentIndicator.metrics.find(m => m.primary);
            if (!pm) return 0;
            return (b.values[pm.field] ?? -Infinity) - (a.values[pm.field] ?? -Infinity);
          }) as sm, i}
            {@const primaryMetric = currentIndicator.metrics.find(m => m.primary)}
            <div class="state-card" style="border-left-color: {sm.state.color}">
              <div class="sc-rank">#{i + 1}</div>
              <div class="sc-name" style="color: {sm.state.color}">{sm.state.name}</div>
              {#if primaryMetric}
                <div class="sc-value">{fmtFull(sm.values[primaryMetric.field])}</div>
                <div class="sc-unit">{primaryMetric.label}{primaryMetric.unit ? ` (${primaryMetric.unit})` : ''}</div>
              {/if}
              <div class="sc-details">
                {#each currentIndicator.metrics.filter(m => !m.primary) as metric}
                  {@const val = sm.values[metric.field]}
                  {#if val !== null}
                    <div class="sc-detail">
                      <span class="sc-dlabel">{metric.label}</span>
                      <span class="sc-dval">{fmt(val, metric.unit)}</span>
                    </div>
                  {/if}
                {/each}
              </div>
            </div>
          {/each}
          {#if stateMetrics.length === 0}
            <div class="no-data">No data available for this indicator in {fmtQuarter(activeQuarter)}</div>
          {/if}
        </div>
      </div>

      <!-- Charts -->
      <div class="charts-section">
        <div class="chart-container">
          <div class="section-label">Comparison · {fmtQuarter(activeQuarter)}</div>
          <div class="chart-box" bind:this={barChartEl}></div>
        </div>

        <div class="chart-container">
          <div class="section-label">Trend Over Time</div>
          <div class="chart-box" bind:this={trendChartEl}></div>
        </div>
      </div>

      <!-- Data table -->
      <div class="table-section">
        <div class="section-label">Detailed Data · {fmtQuarter(activeQuarter)}</div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>State</th>
                {#each currentIndicator.metrics as metric}
                  <th>{metric.label}{metric.unit ? ` (${metric.unit})` : ''}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each stateMetrics as sm}
                <tr>
                  <td class="state-name-cell">
                    <span class="state-dot" style="background: {sm.state.color}"></span>
                    {sm.state.name}
                  </td>
                  {#each currentIndicator.metrics as metric}
                    <td class="num-cell">{fmtFull(sm.values[metric.field])}</td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .fi-dashboard {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 24px 60px;
  }

  /* Loading */
  .loading-state, .error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 20px;
    gap: 16px;
    color: var(--muted);
    font-family: var(--font-sans);
    font-size: 13px;
  }
  .spinner {
    width: 28px; height: 28px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Indicator bar */
  .indicator-bar {
    padding: 20px 0 0;
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--bg);
  }
  .indicator-pills {
    display: flex;
    gap: 6px;
    overflow-x: auto;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
    scrollbar-width: thin;
  }
  .ind-pill {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--card);
    cursor: pointer;
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 500;
    color: var(--muted);
    transition: all 0.2s;
    white-space: nowrap;
  }
  .ind-pill:hover {
    border-color: var(--accent);
    color: var(--accent);
  }
  .ind-pill.active {
    background: var(--text);
    color: #fff;
    border-color: var(--text);
  }
  .ind-icon { font-size: 14px; }
  .ind-name { letter-spacing: 0.02em; }

  /* Controls bar */
  .controls-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 0;
    gap: 20px;
    flex-wrap: wrap;
  }
  .quarter-selector {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .ctrl-label {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--label);
  }
  .ctrl-select {
    padding: 7px 12px;
    border: 1px solid var(--border-dark);
    border-radius: 5px;
    background: var(--card);
    font-family: var(--font-serif);
    font-size: 12px;
    color: var(--text);
    cursor: pointer;
    outline: none;
  }
  .ctrl-select:focus { border-color: var(--accent); }
  .indicator-desc h2 {
    font-family: var(--font-serif);
    font-size: 18px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 2px;
  }
  .indicator-desc p {
    font-family: var(--font-sans);
    font-size: 11px;
    color: var(--muted);
  }

  /* Dashboard grid */
  .dashboard-grid {
    display: flex;
    flex-direction: column;
    gap: 32px;
  }

  .section-label {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--label);
    margin-bottom: 12px;
  }

  /* State cards */
  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
  }
  .state-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 8px;
    padding: 16px 18px;
    box-shadow: var(--card-shadow);
    transition: all 0.2s;
    position: relative;
  }
  .state-card:hover {
    box-shadow: var(--card-shadow-hover);
    transform: translateY(-1px);
  }
  .sc-rank {
    position: absolute;
    top: 10px;
    right: 12px;
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 600;
    color: var(--label);
  }
  .sc-name {
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
  }
  .sc-value {
    font-family: var(--font-serif);
    font-size: 22px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.2;
  }
  .sc-unit {
    font-family: var(--font-sans);
    font-size: 9px;
    color: var(--muted);
    margin-bottom: 10px;
  }
  .sc-details {
    border-top: 1px solid var(--border);
    padding-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .sc-detail {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .sc-dlabel {
    font-family: var(--font-sans);
    font-size: 9px;
    color: var(--muted);
  }
  .sc-dval {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 500;
    color: var(--text);
  }

  /* Charts */
  .charts-section {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }
  .chart-container {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    box-shadow: var(--card-shadow);
  }
  .chart-box {
    width: 100%;
    min-height: 340px;
  }

  /* Table */
  .table-section {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    box-shadow: var(--card-shadow);
  }
  .table-wrap {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-sans);
    font-size: 11px;
  }
  thead th {
    text-align: left;
    padding: 8px 12px;
    font-weight: 600;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    border-bottom: 2px solid var(--border-dark);
    white-space: nowrap;
  }
  tbody td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    color: var(--text);
  }
  tbody tr:hover {
    background: rgba(184, 96, 62, 0.03);
  }
  .state-name-cell {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    white-space: nowrap;
  }
  .state-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .num-cell {
    font-family: var(--font-mono);
    font-size: 11px;
    text-align: right;
    white-space: nowrap;
  }

  .no-data {
    grid-column: 1 / -1;
    text-align: center;
    padding: 40px;
    color: var(--muted);
    font-family: var(--font-sans);
    font-size: 13px;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .charts-section {
      grid-template-columns: 1fr;
    }
    .cards-grid {
      grid-template-columns: 1fr 1fr;
    }
    .indicator-pills {
      gap: 4px;
    }
    .ind-pill {
      padding: 6px 10px;
      font-size: 10px;
    }
  }
  @media (max-width: 480px) {
    .cards-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
