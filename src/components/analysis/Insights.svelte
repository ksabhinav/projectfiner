<script lang="ts">
  import { insights, INSIGHT_CATEGORIES, type InsightCategory } from '../../lib/insights-data';

  interface Props {
    baseUrl: string;
  }

  let { baseUrl }: Props = $props();

  let selectedCategory: InsightCategory = $state('All');

  // Track which cards are flipped
  let flippedCards: Set<string> = $state(new Set());

  let filteredInsights = $derived(
    selectedCategory === 'All'
      ? insights
      : insights.filter(i => i.category === selectedCategory)
  );

  const categoryColors: Record<string, string> = {
    'CD Ratio': '#b8603e',
    'Digital': '#3d7a8e',
    'Branches': '#5a7a3a',
    'KCC': '#8b6914',
    'PMJDY': '#b8603e',
    'Comparison': '#4682b4',
  };

  const categoryBgs: Record<string, string> = {
    'CD Ratio': 'linear-gradient(135deg, #b8603e, #d4845f)',
    'Digital': 'linear-gradient(135deg, #3d7a8e, #5a9aae)',
    'Branches': 'linear-gradient(135deg, #5a7a3a, #7a9a5a)',
    'KCC': 'linear-gradient(135deg, #8b6914, #b08a34)',
    'PMJDY': 'linear-gradient(135deg, #b8603e, #d4845f)',
    'Comparison': 'linear-gradient(135deg, #4682b4, #6aa2d4)',
  };

  function getCategoryColor(cat: string): string {
    return categoryColors[cat] || '#888078';
  }

  function getCategoryBg(cat: string): string {
    return categoryBgs[cat] || 'linear-gradient(135deg, #888078, #aaa09a)';
  }

  function toggleCard(id: string) {
    const next = new Set(flippedCards);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    flippedCards = next;
  }

  function isFlipped(id: string): boolean {
    return flippedCards.has(id);
  }
</script>

<div class="insights-page">
  <!-- Filter pills -->
  <div class="filter-bar">
    {#each INSIGHT_CATEGORIES as cat}
      <button
        class="filter-pill"
        class:active={selectedCategory === cat}
        onclick={() => { selectedCategory = cat; flippedCards = new Set(); }}
        style={selectedCategory === cat ? `background: ${getCategoryColor(cat)}; border-color: ${getCategoryColor(cat)};` : ''}
      >{cat}</button>
    {/each}
  </div>

  <!-- Flashcard grid -->
  <div class="card-grid">
    {#each filteredInsights as insight (insight.id)}
      <div
        class="flashcard-wrapper"
        class:flipped={isFlipped(insight.id)}
        onclick={() => toggleCard(insight.id)}
        role="button"
        tabindex="0"
        onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCard(insight.id); }}}
      >
        <div class="flashcard">
          <!-- FRONT -->
          <div class="card-front">
            <div class="front-accent" style="background: {getCategoryBg(insight.category)}">
              <span class="front-icon">{insight.icon}</span>
              <span class="front-category">{insight.category}</span>
            </div>
            <div class="front-body">
              <div class="front-stat">
                <span class="stat-value" style="color: {getCategoryColor(insight.category)}">{insight.statValue}</span>
                <span class="stat-label">{insight.statLabel}</span>
              </div>
              <h3 class="front-title">{insight.title}</h3>
              <div class="flip-hint">
                <span class="flip-icon">&#8635;</span> Click to read more
              </div>
            </div>
          </div>

          <!-- BACK -->
          <div class="card-back">
            <div class="back-header" style="background: {getCategoryBg(insight.category)}">
              <span class="back-icon">{insight.icon}</span>
              <h3 class="back-title">{insight.title}</h3>
            </div>
            <div class="back-body">
              <p class="back-narrative">{insight.body}</p>
              <div class="back-footer">
                <div class="back-stat-mini">
                  <span class="mini-value">{insight.statValue}</span>
                  <span class="mini-label">{insight.statLabel}</span>
                </div>
                <div class="card-tags">
                  {#each insight.tags as tag}
                    <span class="tag">{tag}</span>
                  {/each}
                </div>
              </div>
              <div class="flip-hint back-hint">
                <span class="flip-icon">&#8635;</span> Click to flip back
              </div>
            </div>
          </div>
        </div>
      </div>
    {/each}
  </div>

  {#if filteredInsights.length === 0}
    <div class="empty-state">No insights found for this category.</div>
  {/if}
</div>

<style>
  .insights-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 40px 60px;
  }

  /* Filter pills */
  .filter-bar {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 32px;
  }
  .filter-pill {
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 7px 16px;
    border: 1px solid var(--border-dark);
    border-radius: 20px;
    background: #fff;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.2s;
  }
  .filter-pill:hover {
    color: var(--text);
    border-color: var(--text);
  }
  .filter-pill.active {
    color: #fff;
  }

  /* Card grid */
  .card-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
  }

  /* Flashcard wrapper — provides perspective */
  .flashcard-wrapper {
    perspective: 1000px;
    cursor: pointer;
    height: 320px;
    outline: none;
  }

  .flashcard {
    position: relative;
    width: 100%;
    height: 100%;
    transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);
    transform-style: preserve-3d;
  }

  .flashcard-wrapper.flipped .flashcard {
    transform: rotateY(180deg);
  }

  /* Both faces */
  .card-front, .card-back {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    backface-visibility: hidden;
    -webkit-backface-visibility: hidden;
    border-radius: 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .card-front {
    background: #fff;
    border: 1px solid var(--border);
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  }
  .card-front:hover {
    box-shadow: 0 6px 24px rgba(0,0,0,0.08);
  }

  .card-back {
    transform: rotateY(180deg);
    background: #fff;
    border: 1px solid var(--border);
    box-shadow: 0 6px 24px rgba(0,0,0,0.08);
  }

  /* ── FRONT FACE ── */
  .front-accent {
    padding: 14px 20px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .front-icon {
    font-size: 18px;
    filter: brightness(10);
  }
  .front-category {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.9);
  }

  .front-body {
    flex: 1;
    padding: 20px 20px 16px;
    display: flex;
    flex-direction: column;
  }

  .front-stat {
    margin-bottom: 14px;
  }
  .stat-value {
    font-family: var(--font-mono);
    font-size: 36px;
    font-weight: 700;
    line-height: 1;
    display: block;
  }
  .stat-label {
    font-family: var(--font-sans);
    font-size: 9.5px;
    font-weight: 500;
    color: var(--label);
    margin-top: 5px;
    letter-spacing: 0.02em;
    display: block;
    line-height: 1.4;
  }

  .front-title {
    font-family: var(--font-serif);
    font-size: 15px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.35;
    flex: 1;
  }

  .flip-hint {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 500;
    color: var(--label);
    letter-spacing: 0.04em;
    margin-top: auto;
    padding-top: 12px;
    display: flex;
    align-items: center;
    gap: 4px;
    opacity: 0.6;
    transition: opacity 0.2s;
  }
  .flashcard-wrapper:hover .flip-hint {
    opacity: 1;
  }
  .flip-icon {
    font-size: 13px;
    display: inline-block;
  }
  .back-hint {
    border-top: 1px solid var(--border);
    padding-top: 10px;
    margin-top: 10px;
    justify-content: center;
  }

  /* ── BACK FACE ── */
  .back-header {
    padding: 16px 20px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }
  .back-icon {
    font-size: 18px;
    filter: brightness(10);
    flex-shrink: 0;
    margin-top: 2px;
  }
  .back-title {
    font-family: var(--font-sans);
    font-size: 12px;
    font-weight: 600;
    color: rgba(255,255,255,0.95);
    line-height: 1.4;
  }

  .back-body {
    flex: 1;
    padding: 18px 20px 14px;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .back-narrative {
    font-family: var(--font-serif);
    font-size: 13px;
    color: var(--text);
    line-height: 1.7;
    flex: 1;
  }

  .back-footer {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
  }

  .back-stat-mini {
    flex-shrink: 0;
  }
  .mini-value {
    font-family: var(--font-mono);
    font-size: 18px;
    font-weight: 700;
    color: var(--accent);
    display: block;
    line-height: 1;
  }
  .mini-label {
    font-family: var(--font-sans);
    font-size: 8px;
    font-weight: 500;
    color: var(--label);
    display: block;
    margin-top: 3px;
    letter-spacing: 0.02em;
  }

  .card-tags {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .tag {
    font-family: var(--font-sans);
    font-size: 8px;
    font-weight: 500;
    color: var(--label);
    background: #faf9f7;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 2px 7px;
    letter-spacing: 0.02em;
  }

  .empty-state {
    font-family: var(--font-sans);
    font-size: 12px;
    color: var(--label);
    text-align: center;
    padding: 60px;
  }

  @media (max-width: 1024px) {
    .card-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
  @media (max-width: 640px) {
    .insights-page {
      padding: 24px 20px 40px;
    }
    .card-grid {
      grid-template-columns: 1fr;
    }
    .flashcard-wrapper {
      height: 300px;
    }
    .stat-value {
      font-size: 28px;
    }
    .front-title {
      font-size: 14px;
    }
  }
</style>
