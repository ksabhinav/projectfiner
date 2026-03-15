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
<div class="section-label">Full Dataset</div>
<div class="dataset">
  <div class="dataset-inner" style="border-left-color: #b8603e">
    <div class="dataset-head">
      <h2><span class="dataset-dot" style="background: #b8603e"></span>Complete Time-Series</h2>
      <span class="badge" style="color: #b8603e; border-color: #b8603e">All quarters × all districts × all indicators</span>
    </div>
    <div class="meta">Wide-format table: one row per district per quarter, all indicator fields as columns.</div>
    <div class="btn-row">
      <button class="btn" class:downloading={downloading['ts-csv']} onclick={() => downloadTimeseries('csv')}>
        <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 18H7v-2h6v2zm4-4H7v-2h10v2zm0-4H7V10h10v2zM13 9V3.5L18.5 9H13z"/></svg>
        CSV
      </button>
      <button class="btn" class:downloading={downloading['ts-xlsx']} onclick={() => downloadTimeseries('xlsx')}>
        <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 18H7v-2h6v2zm4-4H7v-2h10v2zm0-4H7V10h10v2zM13 9V3.5L18.5 9H13z"/></svg>
        Excel
      </button>
    </div>
  </div>
</div>

<!-- Tabs -->
<div class="section-label">Individual Downloads</div>
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
  .dataset { background: #fff; border: 1px solid var(--border); margin-bottom: 10px; border-radius: 8px; box-shadow: var(--card-shadow); overflow: hidden; transition: box-shadow 0.2s; }
  .dataset:hover { box-shadow: var(--card-shadow-hover); }
  .dataset-inner { padding: 20px 24px; border-left: 3px solid transparent; }
  .dataset-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
  h2 { font-size: 14px; font-weight: 700; color: var(--text); letter-spacing: 0.01em; }
  .dataset-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; vertical-align: middle; }
  .meta { font-family: var(--font-sans); font-size: 11px; font-weight: 400; color: var(--muted); line-height: 1.7; margin-top: 8px; }
  .btn-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
  .btn svg { width: 13px; height: 13px; fill: currentColor; }

  .tabs { display: flex; gap: 0; margin-bottom: 20px; border-bottom: 1px solid var(--border-dark); }
  .tab { font-family: var(--font-sans); font-size: 10px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; padding: 10px 20px; cursor: pointer; color: var(--muted); border-bottom: 2px solid transparent; transition: all 0.2s; }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--text); border-bottom-color: var(--accent); }

  .loading-msg { font-family: var(--font-sans); font-size: 11px; color: var(--label); text-align: center; padding: 40px; }

  .ind-grid { display: grid; grid-template-columns: 1fr; gap: 8px; }
  .ind-card { background: #fff; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; transition: box-shadow 0.2s; }
  .ind-card:hover { box-shadow: var(--card-shadow-hover); }
  .ind-inner { padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
  .ind-info { flex: 1; min-width: 200px; }
  .ind-name { font-family: var(--font-sans); font-size: 12px; font-weight: 600; color: var(--text); }
  .ind-desc { font-family: var(--font-sans); font-size: 10px; color: var(--muted); margin-top: 2px; }
  .ind-btns { display: flex; gap: 6px; flex-shrink: 0; }
  .btn-sm { font-family: var(--font-sans); font-size: 9px; font-weight: 600; padding: 6px 12px; border: 1px solid var(--border-dark); background: var(--btn-bg); color: var(--text); cursor: pointer; letter-spacing: 0.04em; text-transform: uppercase; transition: all 0.2s; border-radius: 4px; }
  .btn-sm:hover { background: var(--text); color: #fff; border-color: var(--text); }
  .btn-sm.downloading { opacity: 0.5; cursor: wait; }

  .q-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
  .q-card { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 16px 20px; transition: box-shadow 0.2s; }
  .q-card:hover { box-shadow: var(--card-shadow-hover); }
  .q-label { font-family: var(--font-sans); font-size: 12px; font-weight: 600; color: var(--text); }
  .q-meta { font-family: var(--font-sans); font-size: 9px; color: var(--label); margin-top: 2px; }
  .q-btns { display: flex; gap: 6px; margin-top: 10px; }
</style>
