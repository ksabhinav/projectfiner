<script lang="ts">
  /**
   * IndicatorPicker.svelte — Atlas identity (320px sub-grouped dropdown)
   *
   * Opens from the "What" cell of IndicatorStrip. Categories as small pills
   * along the top, indicators in three subgroups with vermillion left-border
   * for the active item.
  */

  import { onMount, tick } from 'svelte';
  import {
    ATLAS_INDICATORS,
    ATLAS_CATEGORIES,
    ATLAS_SUBGROUPS,
    atlasIndicatorsByCategory,
    type AtlasIndicator,
    type AtlasCategory,
  } from '../../lib/map-indicators';

  interface Props {
    selected: AtlasIndicator;
    onSelect: (ind: AtlasIndicator) => void;
    onClose: () => void;
  }
  let { selected, onSelect, onClose }: Props = $props();

  let activeCat = $state<AtlasCategory>(selected.category);
  let panelEl: HTMLDivElement | null = $state(null);

  const visible = $derived(atlasIndicatorsByCategory(activeCat));
  const grouped = $derived(
    ATLAS_SUBGROUPS.map((g) => ({
      ...g,
      items: visible.filter((i) => i.subgroup === g.id),
    })).filter((g) => g.items.length > 0)
  );

  const counts = $derived.by(() => {
    const c: Record<AtlasCategory, number> = {
      banking: 0, credit: 0, schemes: 0, digital: 0, 'capital-markets': 0, demographics: 0,
    };
    for (const ind of ATLAS_INDICATORS) c[ind.category]++;
    return c;
  });

  function handleListKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
      return;
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return;
    const options = Array.from(
      panelEl?.querySelectorAll<HTMLButtonElement>('[role="option"]') || [],
    );
    if (!options.length) return;
    e.preventDefault();
    const current = Math.max(0, options.indexOf(document.activeElement as HTMLButtonElement));
    const next = e.key === 'Home'
      ? 0
      : e.key === 'End'
        ? options.length - 1
        : e.key === 'ArrowDown'
          ? (current + 1) % options.length
          : (current - 1 + options.length) % options.length;
    options[next].focus();
  }

  onMount(async () => {
    await tick();
    panelEl?.querySelector<HTMLElement>('[aria-selected="true"]')?.focus();
  });
</script>

<div bind:this={panelEl} id="indicator-picker" class="picker-panel" role="dialog" aria-label="Choose a map indicator">
  <div class="pills" aria-label="Filter indicators by category">
    {#each ATLAS_CATEGORIES as cat}
      <button
        class="pill"
        class:active={activeCat === cat.id}
        onclick={() => (activeCat = cat.id)}
        aria-pressed={activeCat === cat.id}
      >
        {cat.label} <span class="ct">{counts[cat.id]}</span>
      </button>
    {/each}
  </div>

  <div class="list" role="listbox" aria-label="Map indicators" onkeydown={handleListKeydown}>
    {#each grouped as group}
      <div class="group-eye">{group.label}</div>
      {#each group.items as ind}
        <button
          class="item"
          class:active={ind.key === selected.key}
          onclick={() => onSelect(ind)}
          role="option"
          aria-selected={ind.key === selected.key}
        >
          <span class="name">{ind.name}</span>
          <span class="units">{ind.units}</span>
        </button>
      {/each}
    {/each}
  </div>
</div>

<!-- CSS lives in src/styles/global.css under "Atlas IndicatorPicker"
     because Astro+Svelte 5 silently drops nested-component scoped CSS from
     the bundled output (.picker-panel rules went missing in compiled
     index@_@astro.*.css). Global rules ship reliably. -->
