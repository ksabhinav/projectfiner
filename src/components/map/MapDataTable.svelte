<script lang="ts">
  import { onMount } from 'svelte';
  import { getFinerState, onFiner } from '../../lib/map-bridge';

  type MapRow = {
    district?: string;
    state?: string;
    value?: number | string | null;
    requested_period?: string;
    source_period?: string;
    status?: string;
    proxy_from?: string;
    quality_status?: string;
  };

  let rows: MapRow[] = $state([]);
  let metric = $state('District value');
  let unit = $state('');
  let open = $state(false);
  let query = $state('');
  let dialog: HTMLDivElement;
  let search: HTMLInputElement;
  let trigger: HTMLButtonElement;

  const visibleRows = $derived.by(() => {
    const needle = query.trim().toLocaleLowerCase();
    return rows
      .filter((row) => !needle || `${row.district || ''} ${row.state || ''}`.toLocaleLowerCase().includes(needle))
      .toSorted((a, b) => `${a.state || ''}\u0000${a.district || ''}`.localeCompare(`${b.state || ''}\u0000${b.district || ''}`));
  });

  function sync(detail?: any) {
    const legend = detail || getFinerState()?.legendData;
    if (!legend) return;
    rows = (legend.rows || []) as MapRow[];
    metric = legend.title || 'District value';
    unit = legend.unit || '';
  }

  function showTable() {
    open = true;
    requestAnimationFrame(() => search?.focus());
  }

  function closeTable() {
    open = false;
    query = '';
    requestAnimationFrame(() => trigger?.focus());
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeTable();
      return;
    }
    if (event.key !== 'Tab' || !dialog) return;
    const focusable = Array.from(dialog.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function focusDistrict(row: MapRow) {
    window.dispatchEvent(new CustomEvent('finer:focusDistrict', {
      detail: { district: row.district || '', state: (row.state || '').toUpperCase() },
    }));
    closeTable();
  }

  function formatValue(row: MapRow): string {
    if (row.value === null || row.value === undefined || row.value === '') return 'No data';
    const value = Number(row.value);
    if (!Number.isFinite(value)) return String(row.value);
    const formatted = value.toLocaleString('en-IN', { maximumFractionDigits: 2 });
    return unit === '%' ? `${formatted}%` : unit === '₹' ? `₹${formatted} lakh` : formatted;
  }

  onMount(() => {
    sync();
    return onFiner('legendUpdate', sync);
  });
</script>

<button bind:this={trigger} class="table-trigger" type="button" onclick={showTable} disabled={!rows.length}>
  View data table
</button>

{#if open}
  <button class="backdrop" type="button" aria-label="Close district data table" onclick={closeTable}></button>
  <div bind:this={dialog} class="table-dialog" role="dialog" aria-modal="true" aria-labelledby="map-table-title" onkeydown={onKeydown}>
    <header>
      <div>
        <p class="eyebrow">Accessible map view</p>
        <h2 id="map-table-title">District data table</h2>
        <p>{metric}</p>
      </div>
      <button class="close" type="button" aria-label="Close district data table" onclick={closeTable}>×</button>
    </header>

    <label for="map-table-search">Filter by district or state</label>
    <input bind:this={search} id="map-table-search" type="search" bind:value={query} autocomplete="off" />
    <p class="result-count" aria-live="polite">Showing {visibleRows.length} of {rows.length} districts.</p>

    <div class="table-scroll" tabindex="0" aria-label="Scrollable district data">
      <table>
        <caption>{metric}. Requested and source periods are shown separately where older observations are displayed.</caption>
        <thead>
          <tr>
            <th scope="col">District</th>
            <th scope="col">State</th>
            <th scope="col">Value</th>
            <th scope="col">Source period</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {#each visibleRows as row}
            <tr>
              <th scope="row">
                <button type="button" onclick={() => focusDistrict(row)}>{row.district || 'Unnamed district'}</button>
              </th>
              <td>{row.state || 'Unknown'}</td>
              <td>{formatValue(row)}</td>
              <td>{row.source_period || row.requested_period || 'Not available'}</td>
              <td>{row.status || 'unclassified'}{row.proxy_from ? ` — inherited from ${row.proxy_from}` : ''}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
{/if}

<style>
  .table-trigger { position:fixed;right:74px;bottom:16px;z-index:900;border:1px solid var(--ink,#1B140E);border-radius:4px;background:var(--paper,#F4EFE6);color:var(--ink,#1B140E);padding:9px 13px;font:600 10px/1 var(--font-ui,'Inter',sans-serif);letter-spacing:.08em;text-transform:uppercase;cursor:pointer;box-shadow:0 4px 18px rgba(27,20,14,.08) }
  .table-trigger:disabled { opacity:.5;cursor:wait }
  .table-trigger:focus-visible,.close:focus-visible,th button:focus-visible,input:focus-visible,.table-scroll:focus-visible { outline:3px solid var(--ochre,#D4A24A);outline-offset:3px }
  .backdrop { position:fixed;inset:0;z-index:1990;border:0;background:rgba(27,20,14,.52);cursor:default }
  .table-dialog { position:fixed;inset:5vh 5vw;z-index:2000;display:flex;flex-direction:column;box-sizing:border-box;max-width:1100px;margin:auto;padding:24px;background:var(--paper,#F4EFE6);border:1px solid var(--ink,#1B140E);border-radius:6px;box-shadow:0 24px 70px rgba(27,20,14,.28);color:var(--ink,#1B140E) }
  header { display:flex;justify-content:space-between;gap:20px;margin-bottom:18px }
  h2 { margin:0;font:400 clamp(25px,4vw,42px)/1.05 var(--font-display,'Fraunces',Georgia,serif) }
  header p { margin:5px 0 0;color:var(--mist,#6E665E) }
  .eyebrow { font:600 9px/1 var(--font-ui,'Inter',sans-serif);letter-spacing:.14em;text-transform:uppercase;color:var(--vermillion,#B84A2E) }
  .close { align-self:flex-start;border:0;background:none;color:inherit;font:300 34px/1 sans-serif;cursor:pointer }
  label { font:600 10px/1.4 var(--font-ui,'Inter',sans-serif);letter-spacing:.08em;text-transform:uppercase }
  input { box-sizing:border-box;width:min(460px,100%);margin:7px 0 5px;padding:10px 12px;border:1px solid var(--rule,#D9D2C5);border-radius:3px;background:#fff;font:16px/1.3 var(--font-ui,'Inter',sans-serif) }
  .result-count { margin:0 0 12px;color:var(--mist,#6E665E);font:11px/1.4 var(--font-mono,'IBM Plex Mono',monospace) }
  .table-scroll { min-height:0;overflow:auto;border:1px solid var(--rule,#D9D2C5);background:#fff }
  table { width:100%;border-collapse:collapse;font:13px/1.4 var(--font-ui,'Inter',sans-serif) }
  caption { padding:12px;text-align:left;color:var(--mist,#6E665E);font-family:var(--font-body,'Source Serif 4',Georgia,serif) }
  th,td { padding:10px 12px;border-top:1px solid var(--rule-soft,#E8E2D5);text-align:left;vertical-align:top }
  thead th { position:sticky;top:0;background:var(--paper-deep,#E8E2D5);font-size:10px;letter-spacing:.07em;text-transform:uppercase }
  tbody th { font-weight:600 }
  th button { border:0;background:none;padding:0;color:var(--vermillion,#8E331E);font:inherit;text-align:left;text-decoration:underline;text-underline-offset:3px;cursor:pointer }
  td:nth-child(3),td:nth-child(4) { font-family:var(--font-mono,'IBM Plex Mono',monospace);font-size:11px;white-space:nowrap }
  @media (max-width:640px) {
    .table-trigger { right:12px;bottom:88px }
    .table-dialog { inset:2vh 10px;padding:16px }
    th,td { padding:8px }
  }
</style>
