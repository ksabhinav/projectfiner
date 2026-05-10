<script lang="ts">
  import { CAPITAL_MARKETS_SOURCES, FILE_ICON_SVG } from '../lib/constants';
  import { downloadCsv, downloadXlsx } from '../lib/download';

  const base = import.meta.env.BASE_URL;
  const cache: Record<string, any[]> = {};

  let downloading: Record<string, boolean> = $state({});

  async function download(id: string, fmt: 'csv' | 'xlsx') {
    const src = CAPITAL_MARKETS_SOURCES[id as keyof typeof CAPITAL_MARKETS_SOURCES];
    if (!src) return;

    downloading = { ...downloading, [`${id}-${fmt}`]: true };

    try {
      if (!cache[id]) {
        const res = await fetch(`${base}${src.url}`);
        cache[id] = await res.json();
      }
      const data = cache[id];
      const rows: string[][] = [src.headers as unknown as string[]];
      for (const r of data) {
        rows.push((src.keys as readonly string[]).map(k => (r as any)[k] || ''));
      }

      if (fmt === 'csv') {
        downloadCsv(rows, src.filename + '.csv');
      } else {
        await downloadXlsx([{ name: 'Data', rows }], src.filename + '.xlsx');
      }
    } catch (e: any) {
      alert('Download failed: ' + e.message);
    }

    downloading = { ...downloading, [`${id}-${fmt}`]: false };
  }
</script>

{#snippet fileIcon()}
  <svg viewBox="0 0 24 24" style="width:14px;height:14px;fill:currentColor">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 18H7v-2h6v2zm4-4H7v-2h10v2zm0-4H7V10h10v2zM13 9V3.5L18.5 9H13z"/>
  </svg>
{/snippet}

<div class="dl-grid">
  {#each [
    { id: 'cdsl', eye: 'CDSL', title: 'Depository participants',          count: '20,612 service centres',  source: 'CDSL website, as on 14 March 2026',  fields: ['Name','Address','DP ID','Pincode','Email','Website','State','City'] },
    { id: 'nsdl', eye: 'NSDL', title: 'Depository participants',          count: '57,005 service centres',  source: 'NSDL website, as on 14 March 2026',  fields: ['Name','Address','DP ID','Pincode','Email','Website','Type','State','City'] },
    { id: 'mfdi', eye: 'AMFI', title: 'MF Distributors — Individual',     count: '187,254 distributors',    source: 'AMFI website, as on 14 March 2026',  fields: ['Name','ARN','Pincode','State','Location','City'] },
    { id: 'mfdc', eye: 'AMFI', title: 'MF Distributors — Corporate',      count: '10,760 distributors',     source: 'AMFI website, as on 14 March 2026',  fields: ['Name','ARN','Pincode','State','Location','City'] },
  ] as ds}
    <div class="dl-card">
      <div class="dl-card-eye">{ds.eye}</div>
      <div class="dl-card-name">{ds.title}</div>
      <div class="dl-card-meta">{ds.count}<br>{ds.source}</div>
      <div class="dl-card-actions">
        <button class="dl-btn primary" class:downloading={downloading[`${ds.id}-csv`]} onclick={() => download(ds.id, 'csv')}>
          CSV
        </button>
        <button class="dl-btn" class:downloading={downloading[`${ds.id}-xlsx`]} onclick={() => download(ds.id, 'xlsx')}>
          XLSX
        </button>
      </div>
    </div>
  {/each}
</div>

<style>
  /* Atlas dl-card pattern — matches /downloads page */
  .dl-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
  }
  .dl-card {
    display: flex;
    flex-direction: column;
    background: var(--paper, #F4EFE6);
    border: 1px solid var(--rule, #D9D2C5);
    border-left: 3px solid var(--peacock, #1E4960);
    border-radius: 4px;
    padding: 16px 16px 14px;
    transition: transform 160ms ease, box-shadow 160ms ease, border-left-color 160ms ease;
  }
  .dl-card:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(27, 20, 14, 0.06);
    border-left-color: var(--peacock-d, #0E2F44);
  }
  .dl-card-eye {
    font-family: 'Inter', sans-serif;
    font-size: 8.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--peacock, #1E4960);
    margin-bottom: 5px;
  }
  .dl-card-name {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 400;
    font-variation-settings: 'opsz' 60;
    font-size: 18px;
    letter-spacing: -0.015em;
    line-height: 1.2;
    color: var(--ink, #1B140E);
    margin-bottom: 8px;
  }
  .dl-card-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5px;
    color: var(--mist, #6E665E);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 14px;
    line-height: 1.6;
  }
  .dl-card-actions {
    margin-top: auto;
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .dl-btn {
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 6px 10px;
    border: 1px solid var(--ink, #1B140E);
    background: var(--paper, #F4EFE6);
    color: var(--ink, #1B140E);
    border-radius: 4px;
    cursor: pointer;
    transition: opacity 160ms ease, transform 160ms ease;
  }
  .dl-btn.primary {
    background: var(--ink, #1B140E);
    color: var(--paper, #F4EFE6);
  }
  .dl-btn:hover { transform: translateY(-1px); }
  .dl-btn.downloading { opacity: 0.5; cursor: wait; }

  @media (max-width: 760px) {
    .dl-grid { grid-template-columns: 1fr; gap: 10px; }
  }
</style>
