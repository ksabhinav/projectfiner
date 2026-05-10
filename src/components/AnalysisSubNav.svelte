<script lang="ts">
  /**
   * AnalysisSubNav.svelte
   *
   * Sub-navigation for /analysis/* pages. Mounts inside PageLayout when
   * the layout receives an `activeSubNav` prop.
   *
   * Three tabs: Rankings · Trends · Insights. Atlas-styled — small caps
   * pill row with the active pill in ink-on-paper.
   *
   * Mount example:
   *   <AnalysisSubNav active="rankings" />
   */

  type SubNavId = 'rankings' | 'trends' | 'insights';

  interface Props {
    active: SubNavId;
    base?: string;
  }

  let { active, base = '/' }: Props = $props();

  const tabs: { id: SubNavId; label: string; href: string }[] = [
    { id: 'rankings', label: 'Rankings', href: `${base}analysis/rankings/` },
    { id: 'trends',   label: 'Trends',   href: `${base}analysis/trends/` },
    // Insights tab hidden. Page still reachable at /analysis/insights/.
    // { id: 'insights', label: 'Insights', href: `${base}analysis/insights/` },
  ];
</script>

<nav class="sub-nav" aria-label="Analysis sections">
  <span class="eye">Analysis</span>
  <div class="tabs">
    {#each tabs as tab}
      <a
        class="tab"
        class:active={tab.id === active}
        href={tab.href}
        aria-current={tab.id === active ? 'page' : undefined}
      >
        {tab.label}
      </a>
    {/each}
  </div>
</nav>

<style>
  .sub-nav {
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 14px 0;
    border-bottom: 1px solid var(--rule);
    margin-bottom: 28px;
  }

  .eye {
    font-family: var(--font-ui);
    font-size: 9.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--vermillion);
    flex-shrink: 0;
  }

  .tabs {
    display: flex;
    gap: 4px;
  }

  .tab {
    font-family: var(--font-ui);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding: 8px 14px;
    border-radius: 99px;
    color: var(--ink-soft);
    background: var(--paper);
    border: 1px solid var(--rule);
    text-decoration: none;
    transition:
      background var(--dur-fast) var(--ease-quick),
      color var(--dur-fast) var(--ease-quick),
      border-color var(--dur-fast) var(--ease-quick);
  }
  .tab:hover {
    background: var(--paper-deep);
    border-color: var(--mist-soft);
    color: var(--ink);
  }
  .tab.active {
    background: var(--ink);
    color: var(--paper);
    border-color: var(--ink);
  }

  @media (max-width: 760px) {
    .sub-nav {
      gap: 14px;
      flex-wrap: wrap;
    }
    .tab { padding: 7px 11px; font-size: 9px; }
  }
</style>
