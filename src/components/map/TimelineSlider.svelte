<script lang="ts">
  import { onMount } from 'svelte';
  import { onFiner, dispatchFiner, getFinerState } from '../../lib/map-bridge';
  import { periodLabel } from '../../lib/format-utils';

  let visible = $state(true);
  let quarters: string[] = $state([]);
  let currentIdx = $state(0);
  let currentQuarter = $state('');
  let accentColor = $state('#b8603e');
  let accentRGB = $derived(() => {
    const c = accentColor;
    return {
      r: parseInt(c.slice(1, 3), 16),
      g: parseInt(c.slice(3, 5), 16),
      b: parseInt(c.slice(5, 7), 16),
    };
  });

  let dragging = false;
  let sliderTimer: ReturnType<typeof setTimeout> | null = null;
  let trackEl: HTMLDivElement;

  // Computed
  let pct = $derived(quarters.length > 1 ? (currentIdx / (quarters.length - 1)) * 100 : 0);
  let startYear = $derived(quarters.length > 0 ? quarters[0].substring(0, 4) : '');
  let endYear = $derived(quarters.length > 0 ? quarters[quarters.length - 1].substring(0, 4) : '');
  let startOpacity = $derived(pct < 15 ? 0 : 1);
  let endOpacity = $derived(pct > 85 ? 0 : 1);
  let label = $derived(currentQuarter ? periodLabel(currentQuarter) : '');

  // Dot data
  interface DotData { pct: number; isYearDot: boolean; idx: number }
  let dots: DotData[] = $derived.by(() => {
    const result: DotData[] = [];
    let prevYear = '';
    for (let i = 0; i < quarters.length; i++) {
      const q = quarters[i];
      const p = quarters.length > 1 ? (i / (quarters.length - 1)) * 100 : 0;
      const yr = q.substring(0, 4);
      const isNewYear = yr !== prevYear;
      prevYear = yr;
      result.push({ pct: p, isYearDot: isNewYear, idx: i });
    }
    return result;
  });

  function posToIdx(clientY: number): number {
    if (!trackEl) return 0;
    const rect = trackEl.getBoundingClientRect();
    const p = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
    return Math.round(p * (quarters.length - 1));
  }

  function setPosition(idx: number) {
    if (idx < 0 || idx >= quarters.length) return;
    currentIdx = idx;
    currentQuarter = quarters[idx];
  }

  function emitQuarterChange() {
    if (sliderTimer) clearTimeout(sliderTimer);
    sliderTimer = setTimeout(() => {
      dispatchFiner('quarterChange', { quarter: currentQuarter, idx: currentIdx });
    }, 120);
  }

  function handleDotClick(idx: number) {
    setPosition(idx);
    emitQuarterChange();
  }

  function handleTrackMousedown(e: MouseEvent) {
    dragging = true;
    const idx = posToIdx(e.clientY);
    setPosition(idx);
    emitQuarterChange();
  }

  function handleThumbMousedown(e: MouseEvent) {
    dragging = true;
    e.preventDefault();
  }

  onMount(() => {
    // Read initial state
    const state = getFinerState();
    if (state) {
      quarters = state.sortedQuarters || [];
      currentIdx = 0;
      currentQuarter = quarters[0] || '';
      visible = state.mode === 'banking';
    }

    // Listen for quarters from inline JS
    const unsub1 = onFiner('quartersReady', (detail: { quarters: string[] }) => {
      quarters = detail.quarters;
      currentIdx = 0;
      currentQuarter = quarters[0] || '';
    });

    // Listen for mode changes
    const unsub2 = onFiner('stateUpdate', () => {
      const s = getFinerState();
      if (s) {
        visible = s.mode === 'banking';
        if (s.sortedQuarters && s.sortedQuarters.length > 0 && quarters.length === 0) {
          quarters = s.sortedQuarters;
          currentIdx = 0;
          currentQuarter = quarters[0] || '';
        }
      }
    });

    // Listen for color ramp changes
    const unsub3 = onFiner('timelineColor', (detail: { color: string }) => {
      accentColor = detail.color;
    });

    // Global mouse/touch handlers for drag
    const handleMouseMove = (e: MouseEvent) => {
      if (!dragging || quarters.length === 0) return;
      e.preventDefault();
      const idx = posToIdx(e.clientY);
      if (idx !== currentIdx) {
        setPosition(idx);
        emitQuarterChange();
      }
    };
    const handleMouseUp = () => { dragging = false; };
    const handleSelectStart = (e: Event) => { if (dragging) e.preventDefault(); };
    const handleTouchMove = (e: TouchEvent) => {
      if (!dragging || quarters.length === 0) return;
      const idx = posToIdx(e.touches[0].clientY);
      if (idx !== currentIdx) {
        setPosition(idx);
        emitQuarterChange();
      }
    };
    const handleTouchEnd = () => { dragging = false; };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('selectstart', handleSelectStart);
    document.addEventListener('touchmove', handleTouchMove);
    document.addEventListener('touchend', handleTouchEnd);

    return () => {
      unsub1(); unsub2(); unsub3();
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('selectstart', handleSelectStart);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  });
</script>

{#if visible && quarters.length > 0}
<div class="time-slider" id="time-slider">
  <div class="tl-bound" style:opacity={startOpacity}>{startYear}</div>
  <div
    class="timeline-track"
    bind:this={trackEl}
    onmousedown={handleTrackMousedown}
    ontouchstart={(e) => { dragging = true; const idx = posToIdx(e.touches[0].clientY); setPosition(idx); emitQuarterChange(); }}
  >
    <div
      class="timeline-fill"
      style:height="{pct}%"
      style:background="rgba({accentRGB().r},{accentRGB().g},{accentRGB().b},0.35)"
    ></div>
    <div class="timeline-dots">
      {#each dots as dot}
        <div
          class="tl-dot"
          class:year-dot={dot.isYearDot}
          class:active={dot.idx === currentIdx}
          style:top="{dot.pct}%"
          onclick={() => handleDotClick(dot.idx)}
        ></div>
      {/each}
    </div>
    <div
      class="timeline-thumb"
      style:top="{pct}%"
      style:background={accentColor}
      onmousedown={handleThumbMousedown}
      ontouchstart={(e) => { dragging = true; e.preventDefault(); }}
    >
      <div class="quarter-label" style:color={accentColor}>{label}</div>
    </div>
  </div>
  <div class="tl-bound" style:opacity={endOpacity}>{endYear}</div>
</div>
{/if}

<style>
  .time-slider {
    position: absolute;
    right: 16px;
    top: 50%;
    transform: translateY(-50%);
    z-index: 1000;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    user-select: none;
    -webkit-user-select: none;
  }
  .tl-bound {
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 500;
    letter-spacing: 0.04em;
    color: #bbb5ad;
    text-align: center;
    transition: opacity 0.2s;
  }
  .timeline-track {
    position: relative;
    width: 3px;
    height: 160px;
    background: rgba(200, 192, 184, 0.5);
    border-radius: 2px;
    cursor: pointer;
  }
  .timeline-fill {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    border-radius: 2px;
    transition: height 0.15s ease;
  }
  .timeline-dots {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
  }
  .tl-dot {
    position: absolute;
    left: 50%;
    width: 7px;
    height: 3px;
    margin-left: -3.5px;
    margin-top: -1.5px;
    background: transparent;
    cursor: pointer;
    transition: all 0.15s;
    border-radius: 0;
  }
  .tl-dot:hover {
    background: rgba(184, 96, 62, 0.3);
  }
  .tl-dot.active {
    background: transparent;
  }
  .tl-dot.year-dot {
    width: 9px;
    height: 1px;
    margin-left: -4.5px;
    margin-top: -0.5px;
    background: rgba(170, 160, 154, 0.4);
  }
  .tl-dot.year-dot.active {
    background: rgba(184, 96, 62, 0.4);
  }
  .timeline-thumb {
    position: absolute;
    left: 50%;
    width: 11px;
    height: 3px;
    margin-left: -5.5px;
    margin-top: -1.5px;
    background: #b8603e;
    border-radius: 1px;
    cursor: grab;
    transition: top 0.15s ease;
    z-index: 2;
  }
  .timeline-thumb:hover {
    height: 4px;
    margin-top: -2px;
    box-shadow: 0 0 8px rgba(184, 96, 62, 0.3);
  }
  .timeline-thumb:active {
    cursor: grabbing;
    box-shadow: 0 0 10px rgba(184, 96, 62, 0.4);
  }
  .quarter-label {
    position: absolute;
    right: 18px;
    top: 50%;
    transform: translateY(-50%);
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 600;
    color: #b8603e;
    letter-spacing: 0.03em;
    white-space: nowrap;
    pointer-events: none;
    text-transform: uppercase;
  }

  /* Focus mode z-index boost */
  :global(body:has(.district-focus.active)) .time-slider {
    z-index: 1300 !important;
  }

  @media (max-width: 640px) {
    .time-slider { right: 6px; }
    .timeline-track { height: 80px; }
    .tl-bound { font-size: 7px; }
    .quarter-label { font-size: 9px; right: 14px; }
    .timeline-thumb { width: 9px; margin-left: -4.5px; }
  }
</style>
