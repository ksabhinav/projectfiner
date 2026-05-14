<script lang="ts">
  /**
   * Lightweight nav grid: lists every district in a state and links to its
   * /district/<state>/<district>/ landing page. Renders on the state download
   * pages so visitors discover the per-district pages.
   *
   * Pulls public/districts/index.json once on mount.
   */
  interface Props {
    stateSlug: string;
    stateName: string;
  }

  let { stateSlug, stateName }: Props = $props();

  const base = import.meta.env.BASE_URL;

  interface Row { state: string; district: string; districtSlug: string; latestQuarter: string; indicatorCount: number }
  let districts: Row[] = $state([]);
  let loading = $state(true);

  $effect(() => {
    fetch(`${base}districts/index.json`)
      .then((r) => r.json())
      .then((d) => {
        districts = (d.districts as Row[]).filter((row) => row.state === stateSlug);
        loading = false;
      })
      .catch(() => { loading = false; });
  });

  function fmtQuarter(q: string): string {
    if (!q || !/^\d{4}-\d{2}$/.test(q)) return q;
    const [y, m] = q.split('-');
    const month = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][parseInt(m)];
    return `${month} ${y}`;
  }
</script>

{#if !loading && districts.length > 0}
  <div class="sd-section-eye">District pages</div>
  <p class="dd-blurb">Latest headline numbers per district — credit-deposit ratio, PMJDY, branches and more.</p>
  <div class="dd-grid">
    {#each districts as d}
      <a class="dd-card" href="{base}district/{d.state}/{d.districtSlug}/">
        <div class="dd-name">{d.district}</div>
        <div class="dd-meta">{d.indicatorCount} indicators · {fmtQuarter(d.latestQuarter)}</div>
      </a>
    {/each}
  </div>
{/if}

<style>
  .sd-section-eye {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--mist, #6E665E);
    text-transform: uppercase;
    margin-top: 36px;
    margin-bottom: 10px;
  }
  .dd-blurb {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 13px;
    font-style: italic;
    color: var(--mist, #6E665E);
    margin: 0 0 14px 0;
  }
  .dd-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: 8px;
  }
  .dd-card {
    border: 1px solid var(--rule-soft, #E8E2D5);
    background: rgba(255,255,255,0.55);
    border-radius: 6px;
    padding: 10px 12px;
    text-decoration: none;
    color: var(--ink, #1B140E);
    transition: border-color 0.15s, transform 0.1s;
  }
  .dd-card:hover {
    border-color: var(--vermillion, #B84A2E);
    color: var(--vermillion, #B84A2E);
    transform: translateY(-1px);
  }
  .dd-name {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 16px;
    font-weight: 500;
    line-height: 1.15;
  }
  .dd-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.03em;
    color: var(--mist, #6E665E);
    margin-top: 4px;
  }
</style>
