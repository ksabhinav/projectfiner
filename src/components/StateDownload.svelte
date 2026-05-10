<script lang="ts">
  import { CATEGORY_INFO, prettyCategoryName } from '../lib/slbc-categories';

  interface Props {
    stateName: string;
    stateSlug: string;
  }

  let { stateName, stateSlug }: Props = $props();

  const base = import.meta.env.BASE_URL;

  let masterData: any = $state(null);
  let loading = $state(true);
  let error = $state('');
  let activeTab: 'indicator' | 'quarter' = $state('indicator');
  let downloading: Record<string, boolean> = $state({});

  // Convert any quarter key to sortable YYYY-MM format for ordering
  function qkeyToSortable(qkey: string): string {
    if (/^\d{4}-\d{2}$/.test(qkey)) return qkey; // already YYYY-MM
    // Handle snake_case like june_2020, sept_2025, mar_2022, dec_2023
    const monthMap: Record<string, string> = {
      jan: '01', january: '01', feb: '02', february: '02', mar: '03', march: '03',
      apr: '04', april: '04', may: '05', june: '06', jun: '06',
      jul: '07', july: '07', aug: '08', august: '08',
      sept: '09', sep: '09', september: '09', oct: '10', october: '10',
      nov: '11', november: '11', dec: '12', december: '12',
    };
    const parts = qkey.split('_');
    if (parts.length === 2) {
      const m = monthMap[parts[0].toLowerCase()];
      if (m) return `${parts[1]}-${m}`;
    }
    return qkey;
  }

  // Derive quarter order from master JSON, sorted chronologically
  let quarterKeys: string[] = $derived.by(() => {
    if (!masterData?.quarters) return [];
    return Object.keys(masterData.quarters).sort((a, b) => qkeyToSortable(a).localeCompare(qkeyToSortable(b)));
  });

  function quarterLabel(qkey: string): string {
    // First check if master data has a period label
    const q = masterData?.quarters?.[qkey];
    if (q?.period) return q.period;
    // qkey is like "2025-09" -> "Sep 2025"
    const sortable = qkeyToSortable(qkey);
    const [y, m] = sortable.split('-');
    const months: Record<string, string> = {
      '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr',
      '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Aug',
      '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec',
    };
    return `${months[m] || m} ${y}`;
  }

  let allCats: string[] = $derived.by(() => {
    if (!masterData) return [];
    const cats = new Set<string>();
    for (const qkey of quarterKeys) {
      const q = masterData.quarters[qkey];
      if (!q) continue;
      Object.keys(q.tables).forEach(c => cats.add(c));
    }
    return [...cats].sort();
  });

  let quarterData: { qkey: string; label: string; fy: string; numTables: number }[] = $derived.by(() => {
    if (!masterData) return [];
    return quarterKeys.map(qkey => {
      const q = masterData.quarters[qkey];
      return {
        qkey,
        label: quarterLabel(qkey),
        fy: q?.fy || '',
        numTables: q ? Object.keys(q.tables).length : 0,
      };
    });
  });

  async function loadMaster() {
    try {
      const res = await fetch(`${base}slbc-data/${stateSlug}/${stateSlug}_complete.json`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      masterData = await res.json();
    } catch (e: any) {
      error = 'Failed to load data. Please try again.';
    }
    loading = false;
  }

  function buildCsvString(headers: string[], rows: string[][]): string {
    const all = [headers, ...rows];
    return all.map(r => r.map(v => {
      const s = String(v == null ? '' : v).replace(/"/g, '""');
      return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s}"` : s;
    }).join(',')).join('\n');
  }

  function saveBlob(blob: Blob, name: string) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function downloadTimeseries(fmt: 'csv' | 'xlsx') {
    downloading = { ...downloading, [`ts-${fmt}`]: true };
    try {
      const url = `${base}slbc-data/${stateSlug}/${stateSlug}_fi_timeseries.csv`;
      const res = await fetch(url);
      const text = await res.text();

      if (fmt === 'csv') {
        const blob = new Blob(['\ufeff' + text], { type: 'text/csv;charset=utf-8;' });
        saveBlob(blob, `${stateSlug}_fi_timeseries.csv`);
      } else {
        const XLSX = await import('xlsx');
        const lines = text.split('\n').map(l => l.split(',').map(v => v.replace(/^"|"$/g, '')));
        const ws = XLSX.utils.aoa_to_sheet(lines);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, 'Time Series');
        XLSX.writeFile(wb, `${stateSlug}_fi_timeseries.xlsx`);
      }
    } catch (e: any) {
      alert('Download failed: ' + e.message);
    }
    downloading = { ...downloading, [`ts-${fmt}`]: false };
  }

  async function downloadIndicator(cat: string, fmt: 'csv' | 'xlsx') {
    downloading = { ...downloading, [`ind-${cat}-${fmt}`]: true };
    try {
      const quarters = masterData.quarters;
      const allFields = new Set<string>();
      const rows: string[][] = [];

      for (const qkey of quarterKeys) {
        if (!quarters[qkey] || !quarters[qkey].tables[cat]) continue;
        const tbl = quarters[qkey].tables[cat];
        (tbl.fields || []).forEach((f: string) => allFields.add(f));
      }
      const fields = [...allFields];
      const headers = ['quarter', 'as_on_date', 'fy', 'district', ...fields];

      for (const qkey of quarterKeys) {
        if (!quarters[qkey] || !quarters[qkey].tables[cat]) continue;
        const q = quarters[qkey];
        const tbl = q.tables[cat];
        const districts = tbl.districts || tbl.data || {};
        for (const [dist, vals] of Object.entries(districts)) {
          const row = [quarterLabel(qkey), q.as_on_date || qkey, q.fy, dist];
          for (const f of fields) row.push((vals as any)[f] || '');
          rows.push(row);
        }
      }

      if (fmt === 'csv') {
        const csv = buildCsvString(headers, rows);
        const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
        saveBlob(blob, `${stateSlug}_${cat}.csv`);
      } else {
        const XLSX = await import('xlsx');
        const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
        ws['!cols'] = headers.map(h => ({ wch: Math.max(String(h).length + 2, 12) }));
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, cat.substring(0, 31));
        XLSX.writeFile(wb, `${stateSlug}_${cat}.xlsx`);
      }
    } catch (e: any) {
      alert('Download failed: ' + e.message);
    }
    downloading = { ...downloading, [`ind-${cat}-${fmt}`]: false };
  }

  async function downloadQuarter(qkey: string, fmt: 'csv' | 'xlsx') {
    downloading = { ...downloading, [`q-${qkey}-${fmt}`]: true };
    try {
      const q = masterData.quarters[qkey];
      if (!q) throw new Error('Quarter not found');

      if (fmt === 'csv') {
        const allFields = new Set<string>();
        for (const [, tbl] of Object.entries(q.tables) as [string, any][]) {
          (tbl.fields || []).forEach((f: string) => allFields.add(f));
        }
        const fields = [...allFields];
        const headers = ['category', 'district', ...fields];
        const rows: string[][] = [];
        for (const [cat, tbl] of Object.entries(q.tables) as [string, any][]) {
          const districts = tbl.districts || tbl.data || {};
          for (const [dist, vals] of Object.entries(districts)) {
            const row = [cat, dist];
            for (const f of fields) row.push((vals as any)[f] || '');
            rows.push(row);
          }
        }
        const csv = buildCsvString(headers, rows);
        const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
        saveBlob(blob, `${stateSlug}_${qkey}.csv`);
      } else {
        const XLSX = await import('xlsx');
        const wb = XLSX.utils.book_new();
        for (const [cat, tbl] of Object.entries(q.tables) as [string, any][]) {
          const districts = tbl.districts || tbl.data || {};
          const fields = tbl.fields || [];
          const headers = ['district', ...fields];
          const rows: string[][] = [];
          for (const [dist, vals] of Object.entries(districts)) {
            const row = [dist];
            for (const f of fields) row.push((vals as any)[f] || '');
            rows.push(row);
          }
          const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
          ws['!cols'] = headers.map((h: string) => ({ wch: Math.max(String(h).length + 2, 12) }));
          XLSX.utils.book_append_sheet(wb, ws, cat.substring(0, 31));
        }
        XLSX.writeFile(wb, `${stateSlug}_${qkey}.xlsx`);
      }
    } catch (e: any) {
      alert('Download failed: ' + e.message);
    }
    downloading = { ...downloading, [`q-${qkey}-${fmt}`]: false };
  }

  function catQuarterCount(cat: string): number {
    if (!masterData) return 0;
    let count = 0;
    for (const qkey of quarterKeys) {
      if (masterData.quarters[qkey]?.tables[cat]) count++;
    }
    return count;
  }

  loadMaster();
</script>

<!-- Full dataset downloads -->
<div class="sd-section-eye">Full dataset</div>
<a class="dataset">
  <div class="dataset-eye">SLBC {stateName}</div>
  <div class="dataset-name">Complete Time-Series</div>
  <div class="dataset-meta">All quarters × all districts × all indicators · wide-format · one row per district per quarter</div>
  <div class="dataset-actions">
    <button class="dl-btn primary" class:downloading={downloading['ts-csv']} onclick={() => downloadTimeseries('csv')}>CSV</button>
    <button class="dl-btn" class:downloading={downloading['ts-xlsx']} onclick={() => downloadTimeseries('xlsx')}>XLSX</button>
  </div>
</a>

<!-- Tabs -->
<div class="sd-section-eye">Individual downloads</div>
<div class="tabs">
  <div class="tab" class:active={activeTab === 'indicator'} onclick={() => activeTab = 'indicator'}>By Indicator</div>
  <div class="tab" class:active={activeTab === 'quarter'} onclick={() => activeTab = 'quarter'}>By Quarter</div>
</div>

{#if loading}
  <div class="loading-msg">Loading data...</div>
{:else if error}
  <div class="loading-msg">{error}</div>
{:else if activeTab === 'indicator'}
  <div class="ind-grid">
    {#each allCats as cat}
      <div class="ind-card">
        <div class="ind-inner">
          <div class="ind-info">
            <div class="ind-name">{prettyCategoryName(cat)}</div>
            <div class="ind-desc">{CATEGORY_INFO[cat] || cat.replace(/_/g, ' ')} · {catQuarterCount(cat)} quarters</div>
          </div>
          <div class="ind-btns">
            <button class="btn-sm" class:downloading={downloading[`ind-${cat}-csv`]} onclick={() => downloadIndicator(cat, 'csv')}>CSV</button>
            <button class="btn-sm" class:downloading={downloading[`ind-${cat}-xlsx`]} onclick={() => downloadIndicator(cat, 'xlsx')}>Excel</button>
          </div>
        </div>
      </div>
    {/each}
  </div>
{:else}
  <div class="q-grid">
    {#each quarterData as qd}
      <div class="q-card">
        <div class="q-label">{qd.label}</div>
        <div class="q-meta">FY {qd.fy} · {qd.numTables} tables</div>
        <div class="q-btns">
          <button class="btn-sm" class:downloading={downloading[`q-${qd.qkey}-csv`]} onclick={() => downloadQuarter(qd.qkey, 'csv')}>CSV</button>
          <button class="btn-sm" class:downloading={downloading[`q-${qd.qkey}-xlsx`]} onclick={() => downloadQuarter(qd.qkey, 'xlsx')}>Excel</button>
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  /* ── Atlas state-download styling ── */

  /* Section eyebrow with trailing rule */
  .sd-section-eye {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--vermillion, #B84A2E);
    margin: 28px 0 14px;
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .sd-section-eye::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--rule, #D9D2C5);
  }
  .sd-section-eye:first-child { margin-top: 8px; }

  /* Hero "Complete Time-Series" card */
  .dataset {
    display: flex;
    flex-direction: column;
    background: var(--paper, #F4EFE6);
    border: 1px solid var(--rule, #D9D2C5);
    border-left: 3px solid var(--vermillion, #B84A2E);
    border-radius: 4px;
    padding: 18px 20px 16px;
    margin-bottom: 24px;
    text-decoration: none;
    color: inherit;
    transition: border-left-color 160ms ease, box-shadow 160ms ease;
  }
  .dataset:hover {
    border-left-color: var(--vermillion-d, #8E331E);
    box-shadow: 0 4px 14px rgba(27, 20, 14, 0.06);
  }
  .dataset-eye {
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--mist, #6E665E);
    margin-bottom: 5px;
  }
  .dataset-name {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 400;
    font-variation-settings: 'opsz' 60;
    font-size: 22px;
    letter-spacing: -0.015em;
    line-height: 1.15;
    color: var(--ink, #1B140E);
    margin-bottom: 8px;
  }
  .dataset-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5px;
    color: var(--mist, #6E665E);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 14px;
    line-height: 1.6;
  }
  .dataset-actions { display: flex; gap: 6px; flex-wrap: wrap; }

  /* Atlas dl-btn (matches /downloads page) */
  .dl-btn {
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 7px 12px;
    border: 1px solid var(--ink, #1B140E);
    background: var(--paper, #F4EFE6);
    color: var(--ink, #1B140E);
    border-radius: 4px;
    cursor: pointer;
    transition: opacity 160ms ease, transform 160ms ease;
  }
  .dl-btn.primary { background: var(--ink, #1B140E); color: var(--paper, #F4EFE6); }
  .dl-btn:hover { transform: translateY(-1px); }
  .dl-btn.downloading { opacity: 0.5; cursor: wait; }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 18px;
  }
  .tab {
    font-family: 'Inter', sans-serif;
    font-size: 9.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding: 8px 14px;
    border-radius: 99px;
    background: var(--paper-deep, #ECE5D6);
    border: 1px solid var(--rule, #D9D2C5);
    color: var(--ink-soft, #3D332A);
    cursor: pointer;
    transition: background 160ms ease, color 160ms ease, border-color 160ms ease;
  }
  .tab:hover { background: var(--paper, #F4EFE6); border-color: var(--mist-soft, #9A9089); color: var(--ink, #1B140E); }
  .tab.active {
    background: var(--ink, #1B140E);
    color: var(--paper, #F4EFE6);
    border-color: var(--ink, #1B140E);
  }

  .loading-msg {
    font-family: 'Source Serif 4', Georgia, serif;
    font-style: italic;
    font-size: 14px;
    color: var(--mist, #6E665E);
    text-align: center;
    padding: 36px;
  }

  /* Indicator list — vertical stack with vermillion left rule on hover */
  .ind-grid { display: flex; flex-direction: column; gap: 0; }
  .ind-card {
    background: transparent;
    border: 0;
    border-bottom: 1px solid var(--rule-soft, #E8E2D5);
    border-left: 2px solid transparent;
    transition: border-left-color 160ms ease, background 160ms ease;
  }
  .ind-card:hover { border-left-color: var(--vermillion, #B84A2E); background: var(--paper-deep, #ECE5D6); }
  .ind-inner {
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
  }
  .ind-info { flex: 1; min-width: 220px; }
  .ind-name {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 400;
    font-variation-settings: 'opsz' 60;
    font-size: 15px;
    color: var(--ink, #1B140E);
    line-height: 1.25;
  }
  .ind-desc {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 12.5px;
    color: var(--ink-soft, #3D332A);
    line-height: 1.55;
    margin-top: 4px;
  }
  .ind-btns { display: flex; gap: 6px; flex-shrink: 0; }
  .btn-sm {
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 6px 10px;
    border: 1px solid var(--ink, #1B140E);
    background: var(--paper, #F4EFE6);
    color: var(--ink, #1B140E);
    cursor: pointer;
    border-radius: 4px;
    transition: transform 160ms ease;
  }
  .btn-sm:hover { transform: translateY(-1px); }
  .btn-sm.downloading { opacity: 0.5; cursor: wait; }

  /* Quarter cards — small Atlas tiles */
  .q-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 10px;
  }
  .q-card {
    background: var(--paper, #F4EFE6);
    border: 1px solid var(--rule, #D9D2C5);
    border-left: 3px solid var(--peacock, #1E4960);
    border-radius: 4px;
    padding: 14px 16px;
    transition: border-left-color 160ms ease, box-shadow 160ms ease;
  }
  .q-card:hover {
    border-left-color: var(--peacock-d, #0E2F44);
    box-shadow: 0 4px 14px rgba(27, 20, 14, 0.06);
  }
  .q-label {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 400;
    font-variation-settings: 'opsz' 60;
    font-size: 16px;
    color: var(--ink, #1B140E);
    letter-spacing: -0.01em;
  }
  .q-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    color: var(--mist, #6E665E);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-top: 4px;
  }
  .q-btns { display: flex; gap: 6px; margin-top: 10px; }

  @media (max-width: 760px) {
    .ind-inner { padding: 12px 14px; }
    .ind-info { min-width: 100%; }
    .ind-btns { width: 100%; }
    .q-grid { grid-template-columns: 1fr; }
  }
</style>
