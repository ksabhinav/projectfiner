<script>
  import { onMount } from 'svelte';

  let summaries = $state([]);
  let loading = $state(true);
  let selectedState = $state('all');
  let expandedId = $state(null);

  const base = typeof window !== 'undefined' && window.__FINER_BASE ? window.__FINER_BASE : '/';

  const STATES = [
    { slug: 'all', name: 'All States' },
    { slug: 'assam', name: 'Assam' },
    { slug: 'meghalaya', name: 'Meghalaya' },
    { slug: 'manipur', name: 'Manipur' },
    { slug: 'mizoram', name: 'Mizoram' },
    { slug: 'nagaland', name: 'Nagaland' },
    { slug: 'arunachal-pradesh', name: 'Arunachal Pradesh' },
  ];

  let filtered = $derived(
    selectedState === 'all'
      ? summaries
      : summaries.filter(s => s.state_slug === selectedState)
  );

  function toggle(id) {
    expandedId = expandedId === id ? null : id;
  }

  onMount(async () => {
    try {
      const res = await fetch(`${base}slbc-data/ne-meeting-summaries.json`);
      if (res.ok) {
        const data = await res.json();
        summaries = data.summaries || [];
      }
    } catch (e) {
      console.error('Failed to load meeting summaries:', e);
    } finally {
      loading = false;
    }
  });
</script>

<div class="summaries-section">
  <div class="section-header">
    <div class="section-label">SLBC NE Meeting Summaries</div>
    <p class="section-desc">AI-generated summaries of {summaries.length} SLBC meeting minutes across 6 North East states. Key decisions, performance highlights, and action items from each meeting.</p>
  </div>

  {#if loading}
    <div class="loading">Loading summaries...</div>
  {:else if summaries.length === 0}
    <div class="loading">No summaries available yet.</div>
  {:else}
    <div class="filter-row">
      {#each STATES as st}
        <button
          class="filter-pill"
          class:active={selectedState === st.slug}
          onclick={() => selectedState = st.slug}
        >{st.name}</button>
      {/each}
    </div>

    <div class="count">{filtered.length} meetings</div>

    <div class="summary-list">
      {#each filtered as item, i}
        {@const id = `${item.state_slug}-${item.quarter}-${i}`}
        <div class="summary-card" class:expanded={expandedId === id}>
          <button class="card-header" onclick={() => toggle(id)}>
            <div class="card-meta">
              <span class="state-badge">{item.state}</span>
              <span class="quarter">{item.quarter}</span>
              <span class="type-badge">Minutes</span>
            </div>
            <span class="chevron">{expandedId === id ? '−' : '+'}</span>
          </button>
          {#if expandedId === id}
            <div class="card-body">
              <div class="summary-text">{item.summary}</div>
              <div class="card-footer">
                <span class="filename">{item.filename}</span>
                {#if item.pages > 0}
                  <span class="pages">{item.pages} pages</span>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .summaries-section {
    margin-top: 40px;
    padding-top: 32px;
    border-top: 1px solid var(--border, #e8e5e0);
  }

  .section-label {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--label, #aaa09a);
    margin-bottom: 8px;
  }
  .section-desc {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 11px;
    color: var(--muted, #888078);
    line-height: 1.7;
    margin-bottom: 20px;
  }

  .loading {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 12px;
    color: var(--muted, #888078);
    padding: 24px 0;
  }

  .filter-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 16px;
  }
  .filter-pill {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 10px;
    font-weight: 500;
    padding: 5px 12px;
    border: 1px solid var(--border, #e8e5e0);
    border-radius: 16px;
    background: #fff;
    color: var(--muted, #888078);
    cursor: pointer;
    transition: all 0.2s;
  }
  .filter-pill:hover {
    border-color: var(--accent, #b8603e);
    color: var(--text, #1a1410);
  }
  .filter-pill.active {
    background: var(--text, #1a1410);
    border-color: var(--text, #1a1410);
    color: #fff;
  }

  .count {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 10px;
    color: var(--label, #aaa09a);
    margin-bottom: 12px;
  }

  .summary-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .summary-card {
    border: 1px solid var(--border, #e8e5e0);
    border-radius: 8px;
    background: #fff;
    overflow: hidden;
    transition: border-color 0.2s;
  }
  .summary-card:hover {
    border-color: #d0cdc8;
  }
  .summary-card.expanded {
    border-left: 3px solid var(--accent, #b8603e);
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 12px 16px;
    background: none;
    border: none;
    cursor: pointer;
    text-align: left;
    font-family: inherit;
  }
  .card-meta {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .state-badge {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 11px;
    font-weight: 600;
    color: var(--text, #1a1410);
  }
  .quarter {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 11px;
    color: var(--muted, #888078);
  }
  .type-badge {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 9px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--accent, #b8603e);
    background: rgba(184, 96, 62, 0.08);
    padding: 2px 6px;
    border-radius: 3px;
  }
  .chevron {
    font-size: 16px;
    color: var(--label, #aaa09a);
    font-weight: 300;
  }

  .card-body {
    padding: 0 16px 14px;
  }
  .summary-text {
    font-family: Georgia, serif;
    font-size: 13px;
    line-height: 1.7;
    color: var(--text, #1a1410);
    white-space: pre-wrap;
  }
  .card-footer {
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid rgba(232, 229, 224, 0.5);
    display: flex;
    gap: 12px;
  }
  .filename, .pages {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 10px;
    color: var(--label, #aaa09a);
  }

  @media (max-width: 768px) {
    .filter-pill { font-size: 9px; padding: 4px 10px; }
    .state-badge { font-size: 10px; }
    .quarter { font-size: 10px; }
  }
</style>
