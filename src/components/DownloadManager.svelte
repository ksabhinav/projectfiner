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

<div class="datasets">
  {#each [
    { id: 'cdsl', color: '#b8603e', title: 'CDSL DP Service Centres', count: '20,612 records', desc: 'Depository Participant service centres registered with Central Depository Services Limited.', source: 'CDSL website, as on 14 March 2026', fields: ['Name','Address','DP ID','Pincode','Email','Website','State','City'] },
    { id: 'nsdl', color: '#3d7a8e', title: 'NSDL DP Service Centres', count: '57,005 records', desc: 'Depository Participant service centres registered with National Securities Depository Limited.', source: 'NSDL website, as on 14 March 2026', fields: ['Name','Address','DP ID','Pincode','Email','Website','Type','State','City'] },
    { id: 'mfdi', color: '#5a7a3a', title: 'MF Distributors — Individual', count: '187,254 records', desc: 'Individual Mutual Fund Distributors registered with AMFI.', source: 'AMFI website, as on 14 March 2026', fields: ['Name','ARN','Pincode','State','Location','City'] },
    { id: 'mfdc', color: '#8b6914', title: 'MF Distributors — Corporate', count: '10,760 records', desc: 'Corporate Mutual Fund Distributors registered with AMFI.', source: 'AMFI website, as on 14 March 2026', fields: ['Name','ARN','Pincode','State','Location','City'] },
  ] as ds}
    <div class="dataset">
      <div class="dataset-inner" style="border-left-color: {ds.color}">
        <div class="dataset-head">
          <h2><span class="dataset-dot" style="background: {ds.color}"></span>{ds.title}</h2>
          <span class="badge" style="color: {ds.color}; border-color: {ds.color}">{ds.count}</span>
        </div>
        <div class="meta">
          {ds.desc}<br>Source: {ds.source}
        </div>
        <div class="fields">
          Fields: {#each ds.fields as f}<code>{f}</code> {/each}
        </div>
        <div class="btn-row">
          <button class="btn" class:downloading={downloading[`${ds.id}-csv`]} onclick={() => download(ds.id, 'csv')}>
            {@render fileIcon()}CSV
          </button>
          <button class="btn" class:downloading={downloading[`${ds.id}-xlsx`]} onclick={() => download(ds.id, 'xlsx')}>
            {@render fileIcon()}Excel
          </button>
        </div>
      </div>
    </div>
  {/each}
</div>

<style>
  .dataset { background: #fff; border: 1px solid var(--border); margin-bottom: 16px; border-radius: 8px; box-shadow: var(--card-shadow); overflow: hidden; transition: box-shadow 0.2s; }
  .dataset:hover { box-shadow: var(--card-shadow-hover); }
  .dataset-inner { padding: 24px 28px; border-left: 3px solid transparent; }
  .dataset-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }
  h2 { font-size: 15px; font-weight: 700; color: var(--text); letter-spacing: 0.01em; }
  .dataset-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; vertical-align: middle; }
  .meta { font-family: var(--font-sans); font-size: 11px; font-weight: 400; color: var(--muted); line-height: 1.8; margin-bottom: 14px; }
  .fields { font-family: var(--font-sans); font-size: 10px; color: var(--muted); margin-bottom: 16px; line-height: 1.8; }
  .fields code { background: #f4f2ee; padding: 2px 7px; font-size: 10px; color: #555048; border-radius: 3px; font-weight: 500; }
  .btn-row { display: flex; gap: 10px; flex-wrap: wrap; }
</style>
