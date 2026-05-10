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

<style>
  .picker-panel {
    position: absolute;
    top: calc(var(--header-h, 52px) + var(--strip-h, 56px) + 6px);
    left: 22px;
    width: 320px;
    background: var(--paper);
    border: 1px solid var(--ink);
    border-radius: 6px;
    box-shadow: 0 24px 48px rgba(27, 20, 14, 0.18), 0 4px 12px rgba(27, 20, 14, 0.06);
    z-index: 1100;
    overflow: hidden;
    animation: drop var(--dur-base, 260ms) var(--ease-quick, cubic-bezier(0.32, 0.72, 0.40, 1.00));
  }
  .picker-panel::before {
    content: '';
    position: absolute;
    top: -7px; left: 78px;
    width: 14px; height: 14px;
    background: var(--paper);
    border-top: 1px solid var(--ink);
    border-left: 1px solid var(--ink);
    transform: rotate(45deg);
  }

  .pills {
    padding: 10px 12px 8px;
    display: flex; gap: 4px; flex-wrap: wrap;
    border-bottom: 1px solid var(--rule);
  }
  .pill {
    font-family: var(--font-ui);
    font-size: 9px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em;
    padding: 5px 9px;
    border-radius: 99px;
    background: var(--paper-deep);
    border: 1px solid var(--rule);
    color: var(--ink-soft);
    cursor: pointer;
    transition: background 160ms ease;
  }
  .pill:hover { background: var(--paper); border-color: var(--mist-soft); }
  .pill.active { background: var(--ink); color: var(--paper); border-color: var(--ink); }
  .pill .ct { color: var(--mist); margin-left: 3px; font-weight: 500; }
  .pill.active .ct { color: rgba(244, 239, 230, 0.55); }

  .list { padding: 6px 0 8px; max-height: 340px; overflow-y: auto; }

  .group-eye {
    font-family: var(--font-ui);
    font-size: 8px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.14em;
    color: var(--mist);
    padding: 10px 18px 6px;
    display: flex; align-items: center; gap: 8px;
  }
  .group-eye::after { content: ''; flex: 1; height: 1px; background: var(--rule); }

  .item {
    width: 100%;
    padding: 7px 18px 7px 16px;
    border: 0;
    background: transparent;
    text-align: left;
    cursor: pointer;
    display: flex; justify-content: space-between; align-items: center;
    transition: background 80ms ease;
    border-left: 2px solid transparent;
  }
  .item:hover { background: var(--paper-deep); }
  .item.active {
    background: rgba(184, 74, 46, 0.05);
    border-left-color: var(--vermillion);
  }
  .item .name {
    font-family: var(--font-display);
    font-weight: 400;
    font-variation-settings: 'opsz' 60;
    font-size: 14px;
    letter-spacing: -0.005em;
    color: var(--ink);
  }
  .item.active .name { color: var(--vermillion-d); font-weight: 500; }
  .item .units { font-family: var(--font-mono); font-size: 9px; color: var(--mist); }
  .item.active .units { color: var(--vermillion); opacity: 0.75; }

  @keyframes drop {
    from { opacity: 0; transform: translateY(-6px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  /* Mobile: full-width panel with safe insets, drop the speech-bubble caret
     since the strip cells span the full width and the caret position is
     ambiguous. Limit list height so the panel doesn't eat the whole map. */
  @media (max-width: 760px) {
    .picker-panel {
      left: 8px;
      right: 8px;
      width: auto;
      max-width: none;
    }
    .picker-panel::before { display: none; }
    .pills { padding: 8px 10px 6px; }
    .pill { padding: 4px 8px; font-size: 8.5px; }
    .list { max-height: 60vh; }
    .item { padding: 8px 14px 8px 12px; }
    .item .name { font-size: 13px; }
  }
</style>
