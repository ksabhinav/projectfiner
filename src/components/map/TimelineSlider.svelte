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
  // Split "Dec 2025" → month "Dec" + year "2025" for the Atlas two-line label
  let labelMonth = $derived(label ? label.split(' ')[0] : '');
  let labelYear = $derived(label ? (label.split(' ')[1] || '') : '');

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
    ></div>
    <div class="timeline-dots">
      {#each dots as dot}
        <div
          class="tl-dot"
          class:year-dot={dot.isYearDot}
          class:past={dot.idx < currentIdx}
          class:active={dot.idx === currentIdx}
          style:top="{dot.pct}%"
          onclick={() => handleDotClick(dot.idx)}
        ></div>
      {/each}
    </div>
    <div
      class="timeline-thumb"
      style:top="{pct}%"
      onmousedown={handleThumbMousedown}
      ontouchstart={(e) => { dragging = true; e.preventDefault(); }}
    ></div>
  </div>
  <div class="tl-bound" style:opacity={endOpacity}>{endYear}</div>
  <div class="tl-current-label">
    {labelMonth}<span class="y">{labelYear}</span>
  </div>
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
    /* Pin column width so longer/shorter labels (Mar vs September) don't
       reflow the column and visually shift the track sideways during scrub. */
    width: 60px;
    user-select: none;
    -webkit-user-select: none;
  }
  .tl-bound {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.05em;
    color: #9a938b;
    text-align: center;
    transition: opacity 0.2s;
  }
  .timeline-track {
    position: relative;
    width: 6px;
    height: 220px;
    background: rgba(200, 192, 184, 0.35);
    border-radius: 3px;
    cursor: pointer;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.08);
  }
  .timeline-fill {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    background: #B84A2E;
    border-radius: 1px;
    /* No height transition — animating during drag causes visible chase */
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
    width: 14px;
    height: 8px;
    margin-left: -7px;
    margin-top: -4px;
    background: transparent;
    cursor: pointer;
    transition: all 0.15s;
    border-radius: 4px;
  }
  .tl-dot:hover {
    background: rgba(184, 96, 62, 0.2);
  }
  .tl-dot.active {
    background: transparent;
  }
  .tl-dot.year-dot {
    width: 6px;
    height: 6px;
    margin-left: -3px;
    margin-top: -3px;
    background: #9A9089;
    border-radius: 50%;
  }
  .tl-dot.year-dot:hover {
    background: #1B140E;
    transform: scale(1.3);
  }
  /* Atlas: past quarters fill in vermillion to show progress */
  .tl-dot.year-dot.past {
    background: #B84A2E;
  }
  .tl-dot.year-dot.active {
    background: #B84A2E;
  }
  /* Atlas: round vermillion thumb with halo ring */
  .timeline-thumb {
    position: absolute;
    left: 50%;
    width: 14px;
    height: 14px;
    margin-left: -7px;
    margin-top: -7px;
    background: #B84A2E;
    border-radius: 50%;
    cursor: grab;
    z-index: 2;
    transition: box-shadow 160ms ease;
    box-shadow:
      0 0 0 4px rgba(184, 74, 46, 0.18),
      0 2px 4px rgba(0, 0, 0, 0.12);
  }
  .timeline-thumb:hover {
    box-shadow:
      0 0 0 5px rgba(184, 74, 46, 0.22),
      0 2px 8px rgba(0, 0, 0, 0.18);
  }
  .timeline-thumb:active { cursor: grabbing; }
  /* Atlas: italic Fraunces label below the track ("Dec / 2025" stacked) */
  .tl-current-label {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 400;
    font-style: italic;
    font-variation-settings: 'opsz' 60;
    font-size: 13px;
    color: #1B140E;
    margin-top: 8px;
    text-align: center;
    line-height: 1.1;
    white-space: nowrap;
  }
  .tl-current-label .y {
    display: block;
    font-family: 'IBM Plex Mono', monospace;
    font-style: normal;
    font-size: 10px;
    color: #6E665E;
    margin-top: 1px;
  }

  /* Focus mode z-index boost */
  :global(body:has(.district-focus.active)) .time-slider {
    z-index: 1300 !important;
  }

  @media (max-width: 640px) {
    .time-slider { right: 8px; gap: 4px; width: 48px; }
    .timeline-track {
      height: calc(100vh - 280px);   /* fill available vertical space */
      max-height: 360px;
      min-height: 180px;
      width: 4px;
    }
    .tl-bound { font-size: 8px; letter-spacing: 0.04em; }
    /* Mobile: round thumb scaled down */
    .timeline-thumb {
      width: 12px;
      height: 12px;
      margin-left: -6px;
      margin-top: -6px;
      box-shadow:
        0 0 0 3px rgba(184, 74, 46, 0.18),
        0 1px 3px rgba(0, 0, 0, 0.12);
    }
    .tl-dot.year-dot { width: 5px; height: 5px; margin-left: -2.5px; margin-top: -2.5px; }
    /* Italic label below the track — smaller, tighter on mobile */
    .tl-current-label { font-size: 11px; margin-top: 6px; }
    .tl-current-label .y { font-size: 9px; }
  }
</style>
