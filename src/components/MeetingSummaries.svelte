<script>
  import { onMount } from 'svelte';

  let allSummaries = $state([]);
  let loading = $state(true);

  const base = typeof window !== 'undefined' && window.__FINER_BASE ? window.__FINER_BASE : '/';

  const STATES = [
    { slug: 'assam', name: 'Assam', color: '#b8603e' },
    { slug: 'meghalaya', name: 'Meghalaya', color: '#3d7a8e' },
    { slug: 'manipur', name: 'Manipur', color: '#5a7a3a' },
    { slug: 'mizoram', name: 'Mizoram', color: '#8b6914' },
    { slug: 'nagaland', name: 'Nagaland', color: '#7a5095' },
    { slug: 'arunachal-pradesh', name: 'Arunachal Pradesh', color: '#c44830' },
  ];

  const MONTH_ORDER = { March: 3, June: 6, September: 9, December: 12, Unknown: 0 };

  function quarterSortKey(q) {
    const parts = q.split(' ');
    if (parts.length === 2) return parseInt(parts[1]) * 100 + (MONTH_ORDER[parts[0]] || 0);
    return 0;
  }

  // Per-state: sorted latest-first, current index for flashcard
  let stateData = $derived.by(() => {
    const map = {};
    for (const st of STATES) {
      const items = allSummaries
        .filter(s => s.state_slug === st.slug)
        .sort((a, b) => quarterSortKey(b.quarter) - quarterSortKey(a.quarter));
      if (items.length > 0) map[st.slug] = items;
    }
    return map;
  });

  let cardIndex = $state({});
  let flipped = $state({});
  let touchStartX = $state({});

  function getIdx(slug) { return cardIndex[slug] || 0; }
  function isFlipped(slug) { return flipped[slug] || false; }

  function prev(slug) {
    const idx = getIdx(slug);
    if (idx > 0) {
      cardIndex = { ...cardIndex, [slug]: idx - 1 };
      flipped = { ...flipped, [slug]: false };
    }
  }
  function next(slug) {
    const items = stateData[slug];
    const idx = getIdx(slug);
    if (items && idx < items.length - 1) {
      cardIndex = { ...cardIndex, [slug]: idx + 1 };
      flipped = { ...flipped, [slug]: false };
    }
  }
  function flipCard(slug) {
    flipped = { ...flipped, [slug]: !isFlipped(slug) };
  }

  function handleTouchStart(e, slug) {
    touchStartX = { ...touchStartX, [slug]: e.touches[0].clientX };
  }
  function handleTouchEnd(e, slug) {
    const startX = touchStartX[slug];
    if (startX == null) return;
    const endX = e.changedTouches[0].clientX;
    const diff = startX - endX;
    if (Math.abs(diff) > 50) {
      if (diff > 0) next(slug);
      else prev(slug);
    }
    touchStartX = { ...touchStartX, [slug]: null };
  }

  onMount(async () => {
    try {
      const res = await fetch(`${base}slbc-data/ne-meeting-summaries.json`);
      if (res.ok) {
        const data = await res.json();
        allSummaries = data.summaries || [];
      }
    } catch (e) {
      console.error('Failed to load meeting summaries:', e);
    } finally {
      loading = false;
    }
  });
</script>

<div class="summaries-section">
  <div class="section-label">SLBC NE Meeting Summaries</div>
  <p class="section-desc">AI-generated summaries of {allSummaries.length} SLBC meeting minutes across 6 North East states. Tap a card to read the summary, swipe or use arrows to browse meetings.</p>

  {#if loading}
    <div class="loading">Loading summaries...</div>
  {:else}
    <div class="states-grid">
      {#each STATES as st}
        {#if stateData[st.slug]}
          {@const items = stateData[st.slug]}
          {@const idx = getIdx(st.slug)}
          {@const item = items[idx]}
          {@const flip = isFlipped(st.slug)}
          <div class="state-capsule">
            <div class="capsule-header" style="border-color: {st.color}">
              <span class="capsule-name" style="color: {st.color}">{st.name}</span>
              <span class="capsule-count">{items.length} meetings</span>
            </div>

            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
              class="flashcard-wrapper"
              ontouchstart={(e) => handleTouchStart(e, st.slug)}
              ontouchend={(e) => handleTouchEnd(e, st.slug)}
            >
              <div class="flashcard" class:flipped={flip} onclick={() => flipCard(st.slug)}>
                <!-- Front: quarter + key stat -->
                <div class="card-face card-front" style="border-top: 3px solid {st.color}">
                  <div class="front-quarter">{item.quarter}</div>
                  <div class="front-filename">{item.filename}</div>
                  {#if item.pages > 0}
                    <div class="front-pages">{item.pages} pages</div>
                  {/if}
                  <div class="front-preview">
                    {item.summary.split('\n').filter(l => l.startsWith('- ') || l.startsWith('* ') || l.startsWith('\u2022 ')).slice(0, 3).map(l => l.replace(/^[-*\u2022]\s*/, '')).join(' \u00B7 ').slice(0, 150)}{item.summary.length > 150 ? '...' : ''}
                  </div>
                  <div class="tap-hint">tap to read summary</div>
                </div>

                <!-- Back: full summary -->
                <div class="card-face card-back" style="border-top: 3px solid {st.color}">
                  <div class="back-quarter">{item.quarter}</div>
                  <div class="back-summary">{@html item.summary.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')}</div>
                  <a class="pdf-link" href={item.pdf_url} target="_blank" rel="noopener" onclick={(e) => e.stopPropagation()}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                    View Minutes PDF
                  </a>
                  <div class="tap-hint">tap to flip back</div>
                </div>
              </div>
            </div>

            <!-- Navigation -->
            <div class="card-nav">
              <button class="nav-btn" onclick={() => prev(st.slug)} disabled={idx === 0}>&larr;</button>
              <span class="nav-pos">{idx + 1} / {items.length}</span>
              <button class="nav-btn" onclick={() => next(st.slug)} disabled={idx === items.length - 1}>&rarr;</button>
            </div>
          </div>
        {/if}
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
    margin-bottom: 24px;
    max-width: 640px;
  }
  .loading {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 12px;
    color: var(--muted, #888078);
    padding: 24px 0;
  }

  /* State grid: 3 columns breaking out of container, 2 on medium, 1 on small */
  .states-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-left: -80px;
    margin-right: -80px;
  }

  .state-capsule {
    display: flex;
    flex-direction: column;
  }

  .capsule-header {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 2px solid;
  }
  .capsule-name {
    font-family: Georgia, serif;
    font-size: 15px;
    font-weight: 700;
  }
  .capsule-count {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 10px;
    color: var(--muted, #888078);
  }

  /* Flashcard */
  .flashcard-wrapper {
    perspective: 800px;
    height: 210px;
    cursor: pointer;
  }
  .flashcard {
    width: 100%;
    height: 100%;
    position: relative;
    transform-style: preserve-3d;
    transition: transform 0.5s ease;
  }
  .flashcard.flipped {
    transform: rotateY(180deg);
  }

  .card-face {
    position: absolute;
    inset: 0;
    backface-visibility: hidden;
    border-radius: 10px;
    background: #fff;
    border: 1px solid var(--border, #e8e5e0);
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .card-back {
    transform: rotateY(180deg);
    overflow-y: auto;
  }

  /* Front face */
  .front-quarter {
    font-family: Georgia, serif;
    font-size: 20px;
    font-weight: 700;
    color: var(--text, #1a1410);
    margin-bottom: 4px;
  }
  .front-filename {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 10px;
    color: var(--label, #aaa09a);
    margin-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .front-pages {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 10px;
    color: var(--label, #aaa09a);
    margin-bottom: 14px;
  }
  .front-preview {
    font-family: Georgia, serif;
    font-size: 12px;
    line-height: 1.6;
    color: var(--muted, #888078);
    flex: 1;
    overflow: hidden;
  }

  .tap-hint {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--label, #aaa09a);
    text-align: center;
    margin-top: 8px;
  }

  /* Back face */
  .back-quarter {
    font-family: Georgia, serif;
    font-size: 14px;
    font-weight: 700;
    color: var(--text, #1a1410);
    margin-bottom: 10px;
    flex-shrink: 0;
  }
  .back-summary {
    font-family: Georgia, serif;
    font-size: 11px;
    line-height: 1.65;
    color: var(--text, #1a1410);
    flex: 1;
    overflow-y: auto;
  }
  .back-summary :global(strong) {
    font-weight: 700;
    color: var(--text, #1a1410);
  }
  .pdf-link {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 10px;
    font-weight: 600;
    color: var(--accent, #b8603e);
    text-decoration: none;
    margin-top: 10px;
    flex-shrink: 0;
    padding: 4px 0;
  }
  .pdf-link:hover {
    color: var(--accent-dark, #8a4a2e);
    text-decoration: underline;
  }

  /* Navigation arrows */
  .card-nav {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-top: 8px;
  }
  .nav-btn {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 14px;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 1px solid var(--border, #e8e5e0);
    background: #fff;
    color: var(--text, #1a1410);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }
  .nav-btn:hover:not(:disabled) {
    background: var(--text, #1a1410);
    color: #fff;
    border-color: var(--text, #1a1410);
  }
  .nav-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }
  .nav-pos {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 10px;
    color: var(--muted, #888078);
    min-width: 44px;
    text-align: center;
  }

  @media (max-width: 960px) {
    .states-grid { grid-template-columns: repeat(2, 1fr); margin-left: -40px; margin-right: -40px; }
  }
  @media (max-width: 640px) {
    .states-grid { grid-template-columns: 1fr; margin-left: 0; margin-right: 0; }
    .flashcard-wrapper { height: 220px; }
    .front-quarter { font-size: 18px; }
  }
</style>
