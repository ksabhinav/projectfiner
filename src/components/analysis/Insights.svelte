<script lang="ts">
  import { insights, INSIGHT_CATEGORIES, type InsightCategory } from '../../lib/insights-data';

  interface Props {
    baseUrl: string;
  }

  let { baseUrl }: Props = $props();

  let selectedCategory: InsightCategory = $state('All');

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

  function getCategoryColor(cat: string): string {
    return categoryColors[cat] || '#888078';
  }

  const NAV_ITEMS = [
    { label: 'Explorer', href: `${baseUrl}analysis/` },
    { label: 'Rankings', href: `${baseUrl}analysis/rankings/` },
    { label: 'Trends', href: `${baseUrl}analysis/trends/` },
    { label: 'Insights', href: `${baseUrl}analysis/insights/` },
  ];
</script>

<div class="insights-page">
  <!-- Sub-nav -->
  <nav class="sub-nav">
    {#each NAV_ITEMS as item}
      <a
        href={item.href}
        class="sub-nav-pill"
        class:active={item.label === 'Insights'}
      >{item.label}</a>
    {/each}
  </nav>

  <!-- Hero -->
  <div class="hero">
    <h2 class="hero-title">Key Findings</h2>
    <p class="hero-desc">
      Curated data stories drawn from SLBC financial inclusion data across Assam, Meghalaya, Manipur, Mizoram, and Bihar.
      Each insight highlights a pattern, disparity, or trend worth exploring further.
    </p>
  </div>

  <!-- Filter pills -->
  <div class="filter-bar">
    {#each INSIGHT_CATEGORIES as cat}
      <button
        class="filter-pill"
        class:active={selectedCategory === cat}
        onclick={() => selectedCategory = cat}
      >{cat}</button>
    {/each}
  </div>

  <!-- Card grid -->
  <div class="card-grid">
    {#each filteredInsights as insight (insight.id)}
      <article class="insight-card">
        <div class="card-accent" style="background: {getCategoryColor(insight.category)}"></div>
        <div class="card-inner">
          <div class="card-top">
            <span class="category-badge" style="color: {getCategoryColor(insight.category)}; border-color: {getCategoryColor(insight.category)}">
              {insight.icon} {insight.category}
            </span>
          </div>
          <div class="stat-block">
            <div class="stat-value">{insight.statValue}</div>
            <div class="stat-label">{insight.statLabel}</div>
          </div>
          <h3 class="card-title">{insight.title}</h3>
          <p class="card-body">{insight.body}</p>
          <div class="card-tags">
            {#each insight.tags as tag}
              <span class="tag">{tag}</span>
            {/each}
          </div>
        </div>
      </article>
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
    padding: 0 40px 60px;
  }

  /* Sub-nav */
  .sub-nav {
    display: flex;
    gap: 6px;
    padding: 20px 0 24px;
  }
  .sub-nav-pill {
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 7px 16px;
    border: 1px solid var(--border-dark);
    border-radius: 20px;
    background: var(--btn-bg);
    color: var(--muted);
    text-decoration: none;
    transition: all 0.2s;
  }
  .sub-nav-pill:hover {
    color: var(--text);
    border-color: var(--text);
  }
  .sub-nav-pill.active {
    background: var(--text);
    color: #fff;
    border-color: var(--text);
  }

  /* Hero */
  .hero {
    margin-bottom: 28px;
  }
  .hero-title {
    font-family: var(--font-serif);
    font-size: 28px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 8px;
  }
  .hero-desc {
    font-family: var(--font-sans);
    font-size: 13px;
    color: var(--muted);
    line-height: 1.7;
    max-width: 640px;
  }

  /* Filter pills */
  .filter-bar {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 28px;
  }
  .filter-pill {
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 6px 14px;
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
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
  }

  /* Card grid */
  .card-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
  }

  /* Insight card */
  .insight-card {
    display: flex;
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--card-shadow);
    overflow: hidden;
    transition: all 0.2s;
  }
  .insight-card:hover {
    box-shadow: var(--card-shadow-hover);
  }

  .card-accent {
    width: 3px;
    flex-shrink: 0;
  }

  .card-inner {
    padding: 20px 24px;
    flex: 1;
    min-width: 0;
  }

  .card-top {
    margin-bottom: 14px;
  }

  .category-badge {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 4px 10px;
    border: 1px solid;
    border-radius: 20px;
    display: inline-block;
  }

  .stat-block {
    margin-bottom: 12px;
  }
  .stat-value {
    font-family: var(--font-mono);
    font-size: 32px;
    font-weight: 700;
    color: var(--accent);
    line-height: 1.1;
  }
  .stat-label {
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 500;
    color: var(--label);
    margin-top: 4px;
    letter-spacing: 0.02em;
  }

  .card-title {
    font-family: var(--font-serif);
    font-size: 16px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.35;
    margin-bottom: 8px;
  }

  .card-body {
    font-family: var(--font-serif);
    font-size: 13.5px;
    color: var(--muted);
    line-height: 1.65;
    margin-bottom: 14px;
  }

  .card-tags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .tag {
    font-family: var(--font-sans);
    font-size: 9px;
    font-weight: 500;
    color: var(--label);
    background: #faf9f7;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 3px 8px;
    letter-spacing: 0.02em;
  }

  .empty-state {
    font-family: var(--font-sans);
    font-size: 12px;
    color: var(--label);
    text-align: center;
    padding: 60px;
  }

  @media (max-width: 768px) {
    .insights-page {
      padding: 0 20px 40px;
    }
    .card-grid {
      grid-template-columns: 1fr;
    }
    .hero-title {
      font-size: 22px;
    }
    .stat-value {
      font-size: 26px;
    }
  }
</style>
