<script lang="ts">
  /**
   * IndicatorPicker.svelte — Atlas identity (320px sub-grouped dropdown)
   *
   * Opens from the "What" cell of IndicatorStrip. Categories as small pills
   * along the top, indicators in three subgroups with vermillion left-border
   * for the active item.
   */

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
</script>

<div class="picker-panel" role="listbox" aria-label="Pick an indicator">
  <div class="pills">
    {#each ATLAS_CATEGORIES as cat}
      <button class="pill" class:active={activeCat === cat.id} onclick={() => (activeCat = cat.id)}>
        {cat.label} <span class="ct">{counts[cat.id]}</span>
      </button>
    {/each}
  </div>

  <div class="list">
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
