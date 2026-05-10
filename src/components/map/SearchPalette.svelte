<script lang="ts">
  /**
   * SearchPalette.svelte — Atlas ⌘K search modal.
   *
   * Listens for `finer:open-search` (fired by IndicatorStrip search pill)
   * and global Cmd/Ctrl+K. Shows a centered modal with a search input and
   * district autocomplete. Selecting a district fires:
   *   - `finer:stateFilterChange` with the parent state (focuses the state)
   *   - `finer:focusDistrict` with district + state (existing focus mode trigger)
   *
   * Loads district list from {base}district_lgd_codes.json.
   */
  import { onMount, tick } from 'svelte';

  interface DistrictRow {
    name: string;       // canonical district name
    state: string;      // STATE_UT uppercase
    lgd?: string;
  }

  let isOpen = $state(false);
  let query = $state('');
  let districts: DistrictRow[] = $state([]);
  let activeIdx = $state(0);
  let inputEl: HTMLInputElement | null = $state(null);

  const base = import.meta.env.BASE_URL || '/';

  // Filter + rank: prefix matches first, then substring
  const results = $derived.by(() => {
    if (!query.trim()) return [] as DistrictRow[];
    const q = query.trim().toLowerCase();
    const prefix: DistrictRow[] = [];
    const sub: DistrictRow[] = [];
    for (const d of districts) {
      const n = d.name.toLowerCase();
      if (n.startsWith(q)) prefix.push(d);
      else if (n.includes(q)) sub.push(d);
      if (prefix.length + sub.length > 80) break;
    }
    return prefix.concat(sub).slice(0, 12);
  });

  function titleCase(s: string): string {
    return s.split(' ').map(w => w[0] + w.slice(1).toLowerCase()).join(' ');
  }

  async function open() {
    isOpen = true;
    await tick();
    inputEl?.focus();
  }
  function close() {
    isOpen = false;
    query = '';
    activeIdx = 0;
  }

  function pick(d: DistrictRow) {
    // Focus the state first, then nudge focus mode for the district
    window.dispatchEvent(new CustomEvent('finer:stateFilterChange', {
      detail: { state: d.state.toUpperCase() },
    }));
    window.dispatchEvent(new CustomEvent('finer:focusDistrict', {
      detail: { district: d.name, state: d.state.toUpperCase() },
    }));
    close();
  }

  function handleKeydown(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      isOpen ? close() : open();
      return;
    }
    if (!isOpen) return;
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (results.length) activeIdx = (activeIdx + 1) % results.length;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (results.length) activeIdx = (activeIdx - 1 + results.length) % results.length;
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (results[activeIdx]) pick(results[activeIdx]);
    }
  }

  onMount(() => {
    // Load district list (try district_lgd_codes.json which has aliases too)
    fetch(`${base}district_lgd_codes.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        const out: DistrictRow[] = [];
        const seen = new Set<string>();
        // The file is shaped as { districts: [{name, state, lgd, ...}], aliases: {...} }
        const arr = Array.isArray(data) ? data : (data.districts || []);
        for (const row of arr) {
          const name = row.name || row.DISTRICT || row.district;
          const state = (row.state || row.STATE_UT || row.state_ut || '').toUpperCase();
          if (!name || !state) continue;
          const k = `${name}|${state}`;
          if (seen.has(k)) continue;
          seen.add(k);
          out.push({ name: titleCase(name), state, lgd: row.lgd });
        }
        out.sort((a, b) => a.name.localeCompare(b.name));
        districts = out;
      })
      .catch(() => {});

    function onOpen() { open(); }
    window.addEventListener('finer:open-search', onOpen);
    window.addEventListener('keydown', handleKeydown);

    return () => {
      window.removeEventListener('finer:open-search', onOpen);
      window.removeEventListener('keydown', handleKeydown);
    };
  });

  $effect(() => {
    // Reset active row when query changes
    void query;
    activeIdx = 0;
  });
</script>

{#if isOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="sp-backdrop" onclick={close} role="presentation"></div>

  <div class="sp-panel" role="dialog" aria-modal="true" aria-label="Search districts">
    <div class="sp-input-wrap">
      <span class="sp-glass" aria-hidden="true">⌕</span>
      <input
        bind:this={inputEl}
        bind:value={query}
        type="text"
        class="sp-input"
        placeholder={districts.length
          ? `Search ${districts.length.toLocaleString()} districts…`
          : 'Search districts…'}
        autocomplete="off"
        spellcheck="false"
      />
      <span class="sp-esc">ESC</span>
    </div>

    {#if results.length}
      <div class="sp-results" role="listbox">
        {#each results as d, i}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <div
            class="sp-row"
            class:active={i === activeIdx}
            onclick={() => pick(d)}
            onmouseenter={() => (activeIdx = i)}
            role="option"
            aria-selected={i === activeIdx}
          >
            <span class="sp-name">{d.name}</span>
            <span class="sp-state">{titleCase(d.state)}</span>
          </div>
        {/each}
      </div>
    {:else if query.trim().length}
      <div class="sp-empty">
        <span class="sp-empty-eye">No district matches</span>
        <p class="sp-empty-lede">
          Try a partial name (e.g. <em>“gomati”</em>, <em>“24 paraganas”</em>) or check spelling.
        </p>
      </div>
    {:else}
      <div class="sp-hint">
        <span class="sp-hint-row"><span class="sp-kbd">↑↓</span> navigate</span>
        <span class="sp-hint-row"><span class="sp-kbd">↵</span> open</span>
        <span class="sp-hint-row"><span class="sp-kbd">esc</span> close</span>
      </div>
    {/if}
  </div>
{/if}

<style>
  .sp-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(27, 20, 14, 0.45);
    z-index: 1600;
    animation: fadeIn 200ms ease;
  }
  .sp-panel {
    position: fixed;
    top: 18%;
    left: 50%;
    transform: translateX(-50%);
    width: min(560px, calc(100vw - 32px));
    max-height: 60vh;
    overflow: hidden;
    background: #F4EFE6;
    border: 1px solid #1B140E;
    border-radius: 4px;
    box-shadow:
      0 32px 80px rgba(27, 20, 14, 0.4),
      0 8px 20px rgba(27, 20, 14, 0.15);
    z-index: 1601;
    animation: dropIn 260ms cubic-bezier(0.20, 0.80, 0.20, 1.00);
    display: flex;
    flex-direction: column;
  }

  .sp-input-wrap {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 18px 14px;
    border-bottom: 1px solid #D9D2C5;
  }
  .sp-glass {
    font-size: 16px;
    color: #6E665E;
    line-height: 1;
  }
  .sp-input {
    flex: 1;
    border: 0;
    background: transparent;
    outline: none;
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 17px;
    color: #1B140E;
  }
  .sp-input::placeholder { color: #9A9089; font-style: italic; }
  .sp-esc {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    color: #6E665E;
    background: #ECE5D6;
    border: 1px solid #D9D2C5;
    padding: 3px 7px;
    border-radius: 3px;
    letter-spacing: 0.08em;
  }

  .sp-results {
    overflow-y: auto;
    max-height: 360px;
  }
  .sp-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 10px 18px;
    cursor: pointer;
    border-left: 2px solid transparent;
    transition: background 80ms ease, border-color 80ms ease;
  }
  .sp-row:hover, .sp-row.active {
    background: #ECE5D6;
    border-left-color: #B84A2E;
  }
  .sp-name {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 400;
    font-variation-settings: 'opsz' 60;
    font-size: 15px;
    letter-spacing: -0.01em;
    color: #1B140E;
  }
  .sp-row.active .sp-name { color: #8E331E; }
  .sp-state {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5px;
    color: #6E665E;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .sp-empty {
    padding: 22px 22px 26px;
  }
  .sp-empty-eye {
    font-family: 'Inter', sans-serif;
    font-size: 9.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: #B84A2E;
    display: block;
    margin-bottom: 8px;
  }
  .sp-empty-lede {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 13px;
    color: #3D332A;
    line-height: 1.6;
  }
  .sp-empty-lede em { color: #1B140E; font-style: italic; }

  .sp-hint {
    padding: 14px 18px;
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 12px;
    color: #6E665E;
  }
  .sp-hint-row { display: inline-flex; align-items: center; gap: 6px; }
  .sp-kbd {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    background: #ECE5D6;
    border: 1px solid #D9D2C5;
    padding: 2px 6px;
    border-radius: 3px;
    color: #3D332A;
    letter-spacing: 0.04em;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  @keyframes dropIn {
    from {
      opacity: 0;
      transform: translateX(-50%) translateY(-12px);
    }
    to {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }
  }

  @media (max-width: 760px) {
    .sp-panel { top: 12%; }
    .sp-input { font-size: 15px; }
    .sp-name { font-size: 14px; }
  }
</style>
