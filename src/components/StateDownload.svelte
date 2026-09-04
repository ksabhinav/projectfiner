<script lang="ts">
  import { CATEGORY_INFO, prettyCategoryName } from '../lib/slbc-categories';
  import DistrictDirectory from './DistrictDirectory.svelte';

  interface Props {
    stateName: string;
    stateSlug: string;
  }

  let { stateName, stateSlug }: Props = $props();

  const base = import.meta.env.BASE_URL;

  let masterData: any = $state(null);
  let releaseManifest: any = $state(null);
  let releaseMetadata: any = $state(null);
  let loading = $state(true);
  let error = $state('');
  let activeTab: 'indicator' | 'quarter' = $state('indicator');
  let downloading: Record<string, boolean> = $state({});

  let releaseSource: any = $derived.by(() => {
    const sourceId = releaseMetadata?.sourceIds?.[0];
    return releaseManifest?.sources?.find((source: any) => source.id === sourceId);
  });

  let standardizedPreview: any = $derived.by(() =>
    releaseMetadata?.distributions?.find(
      (distribution: any) => distribution.role === 'observations'
        && distribution.qualityTier === 'standardized-preview'
    )
  );

  let indicatorRegistry: any = $derived.by(() =>
    releaseMetadata?.distributions?.find(
      (distribution: any) => distribution.role === 'indicator-registry'
        && distribution.productId === standardizedPreview?.productId
    )
  );

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
      const [dataResponse, manifestResponse] = await Promise.all([
        fetch(`${base}slbc-data/${stateSlug}/${stateSlug}_complete.json`),
        fetch(`${base}release-manifest.json`),
      ]);
      if (!dataResponse.ok) throw new Error(`Dataset HTTP ${dataResponse.status}`);
      if (!manifestResponse.ok) throw new Error(`Manifest HTTP ${manifestResponse.status}`);
      masterData = await dataResponse.json();
      releaseManifest = await manifestResponse.json();
      releaseMetadata = releaseManifest.states?.find((state: any) => state.slug === stateSlug);
      if (!releaseMetadata) throw new Error('State is missing from release manifest');
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

  async function downloadTimeseries() {
    downloading = { ...downloading, 'ts-csv': true };
    try {
      const url = `${base}slbc-data/${stateSlug}/${stateSlug}_fi_timeseries.csv`;
      const res = await fetch(url);
      const text = await res.text();

      const blob = new Blob([text], { type: 'text/csv;charset=utf-8;' });
      saveBlob(blob, `${stateSlug}_fi_timeseries.csv`);
    } catch (e: any) {
      alert('Download failed: ' + e.message);
    }
    downloading = { ...downloading, 'ts-csv': false };
  }

  async function downloadIndicator(cat: string) {
    downloading = { ...downloading, [`ind-${cat}-csv`]: true };
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

      const csv = buildCsvString(headers, rows);
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      saveBlob(blob, `${stateSlug}_${cat}.csv`);
    } catch (e: any) {
      alert('Download failed: ' + e.message);
    }
    downloading = { ...downloading, [`ind-${cat}-csv`]: false };
  }

  async function downloadQuarter(qkey: string) {
    downloading = { ...downloading, [`q-${qkey}-csv`]: true };
    try {
      const q = masterData.quarters[qkey];
      if (!q) throw new Error('Quarter not found');

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
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      saveBlob(blob, `${stateSlug}_${qkey}.csv`);
    } catch (e: any) {
      alert('Download failed: ' + e.message);
    }
    downloading = { ...downloading, [`q-${qkey}-csv`]: false };
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

<!-- District directory: links to /district/<state>/<district> landing pages -->
<DistrictDirectory stateSlug={stateSlug} stateName={stateName} />

{#if releaseMetadata}
  <aside class="release-notice">
    <div class="release-heading"><span>Raw / experimental</span> {releaseManifest.releaseId}</div>
    <p>
      {releaseMetadata.coverage.periodCount} periods · {releaseMetadata.coverage.districtCount} source labels · {releaseMetadata.coverage.categoryCount} categories.
      Counts describe the source-derived files and are not a certification of comparable district coverage.
    </p>
    <p>
      Source: <a href={releaseSource?.url} target="_blank" rel="noopener">{releaseSource?.publisher}</a>.
      Rights have not been reviewed; public availability does not establish reuse permission.
      <a href={`${base}data-rights/`}>Rights</a> ·
      <a href={`${base}methodology/`}>Methodology</a> ·
      <a href={`${base}data-dictionary/`}>Dictionary</a> ·
      <a href={`${base}corrections/`}>Corrections</a>
    </p>
  </aside>
{/if}

{#if standardizedPreview}
  <div class="sd-section-eye">Standardized data contract</div>
  <div class="dataset preview-dataset">
    <div class="dataset-eye"><span class="preview-badge">Standardized preview</span> Not certified</div>
    <div class="dataset-name">Meghalaya long-format observations</div>
    <div class="dataset-meta">
      {standardizedPreview.rowCount.toLocaleString()} observations · {standardizedPreview.indicatorCount} registered indicators · LGD district IDs · source values retained
    </div>
    <p class="preview-note">
      Directly reported fields only. Unlinked source pages, the 2022 district split, partial coverage, and Aadhaar scope conflicts are carried as row-level quality flags.
    </p>
    <div class="dataset-actions">
      <a class="dl-btn primary" href={`${base}${standardizedPreview.path}`} download>Long CSV</a>
      {#if indicatorRegistry}
        <a class="dl-btn" href={`${base}${indicatorRegistry.path}`} download>Data dictionary</a>
      {/if}
    </div>
  </div>
{/if}

<!-- Raw dataset downloads -->
<div class="sd-section-eye">Raw / experimental downloads</div>
<a class="dataset">
  <div class="dataset-eye">SLBC {stateName}</div>
  <div class="dataset-name">Complete Time-Series</div>
  <div class="dataset-meta">
    {releaseMetadata
      ? `${releaseMetadata.coverage.periodCount} periods × ${releaseMetadata.coverage.districtCount} source labels × ${releaseMetadata.coverage.categoryCount} categories`
      : 'Coverage metadata loading'} · wide-format CSV
  </div>
  <div class="dataset-actions">
    <button class="dl-btn primary" class:downloading={downloading['ts-csv']} onclick={downloadTimeseries}>CSV</button>
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
            <button class="btn-sm" class:downloading={downloading[`ind-${cat}-csv`]} onclick={() => downloadIndicator(cat)}>CSV</button>
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
          <button class="btn-sm" class:downloading={downloading[`q-${qd.qkey}-csv`]} onclick={() => downloadQuarter(qd.qkey)}>CSV</button>
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  /* ── Atlas state-download styling ── */

  .release-notice {
    margin: 22px 0 28px;
    padding: 14px 16px;
    border: 1px solid var(--rule, #D9D2C5);
    border-left: 3px solid var(--gold, #8B6914);
    background: var(--paper-deep, #ECE5D6);
    color: var(--ink-soft, #3D332A);
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 13.5px;
    line-height: 1.5;
  }
  .release-heading {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink, #1B140E);
  }
  .release-heading span {
    display: inline-block;
    margin-right: 7px;
    padding: 2px 6px;
    border-radius: 2px;
    background: var(--gold, #8B6914);
    color: white;
    font-weight: 700;
  }
  .release-notice p { margin: 7px 0 0; }
  .release-notice a { color: var(--vermillion-d, #8E331E); }

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
  .preview-dataset { border-left-color: var(--peacock, #1E4960); }
  .preview-badge {
    display: inline-block;
    margin-right: 7px;
    padding: 2px 6px;
    border-radius: 2px;
    background: var(--peacock, #1E4960);
    color: white;
  }
  .preview-note {
    max-width: 820px;
    margin: 0 0 14px;
    color: var(--ink-soft, #3D332A);
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 13.5px;
    line-height: 1.5;
  }

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
  a.dl-btn { display: inline-block; text-decoration: none; }

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
