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
  let isMobile = $state(false);

  // Computed
  let pct = $derived(quarters.length > 1 ? (currentIdx / (quarters.length - 1)) * 100 : 0);
  // Mobile (horizontal): latest quarter at RIGHT, so visual left% = 100 - pct
  let posPct = $derived(isMobile ? 100 - pct : pct);
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

  function posToIdx(clientX: number, clientY: number): number {
    if (!trackEl) return 0;
    const rect = trackEl.getBoundingClientRect();
    let p: number;
    if (isMobile) {
      // Horizontal: latest quarter (idx 0) anchored RIGHT, oldest (idx n-1) LEFT
      // so dragging right → newer time. quarters[] is latest-first.
      p = Math.max(0, Math.min(1, 1 - (clientX - rect.left) / rect.width));
    } else {
      // Vertical: latest at top, oldest at bottom
      p = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
    }
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
    const idx = posToIdx(e.clientX, e.clientY);
    setPosition(idx);
    emitQuarterChange();
  }

  function handleThumbMousedown(e: MouseEvent) {
    dragging = true;
    e.preventDefault();
  }

  onMount(() => {
    // Track orientation for mobile horizontal layout
    const mq = window.matchMedia('(max-width: 640px)');
    isMobile = mq.matches;
    const onResize = (e: MediaQueryListEvent) => { isMobile = e.matches; };
    mq.addEventListener('change', onResize);

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
      const idx = posToIdx(e.clientX, e.clientY);
      if (idx !== currentIdx) {
        setPosition(idx);
        emitQuarterChange();
      }
    };
    const handleMouseUp = () => { dragging = false; };
    const handleSelectStart = (e: Event) => { if (dragging) e.preventDefault(); };
    const handleTouchMove = (e: TouchEvent) => {
      if (!dragging || quarters.length === 0) return;
      // Claim the gesture so the page doesn't scroll while scrubbing.
      // Must be a non-passive listener for preventDefault to work — see
      // the addEventListener call below.
      if (e.cancelable) e.preventDefault();
      const idx = posToIdx(e.touches[0].clientX, e.touches[0].clientY);
      if (idx !== currentIdx) {
        setPosition(idx);
        emitQuarterChange();
      }
    };
    const handleTouchEnd = () => { dragging = false; };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('selectstart', handleSelectStart);
    // passive:false is required so handleTouchMove can preventDefault and
    // stop the page from scrolling while the user scrubs the slider.
    document.addEventListener('touchmove', handleTouchMove, { passive: false });
    document.addEventListener('touchend', handleTouchEnd);

    return () => {
      unsub1(); unsub2(); unsub3();
      mq.removeEventListener('change', onResize);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('selectstart', handleSelectStart);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  });
</script>

{#if visible && quarters.length > 0}
<div class="time-slider" id="time-slider" class:horizontal={isMobile}>
  <!-- On mobile (horizontal): oldest year on the left, latest on the right.
       On desktop (vertical): startYear (latest) on top, endYear (oldest) on bottom. -->
  <div class="tl-bound" style:opacity={isMobile ? endOpacity : startOpacity}>{isMobile ? endYear : startYear}</div>
  <div
    class="timeline-track"
    bind:this={trackEl}
    onmousedown={handleTrackMousedown}
    ontouchstart={(e) => { dragging = true; const t = e.touches[0]; const idx = posToIdx(t.clientX, t.clientY); setPosition(idx); emitQuarterChange(); }}
  >
    <!-- Fill semantics: red = "how recent is the selection".
         Latest quarter = full bar; oldest = empty bar.
         Mobile (horizontal, latest=right): width = posPct, anchored LEFT
           — fills from left edge to thumb. At latest thumb is on the
           right and posPct = 100, so the whole bar is red.
         Desktop (vertical, latest=top): height = 100 - pct, anchored
           BOTTOM — fills from bottom edge up to thumb. At latest thumb
           is on top and (100 - pct) = 100, so the whole bar is red. -->
    <div
      class="timeline-fill"
      style:height={isMobile ? '100%' : `${100 - pct}%`}
      style:width={isMobile ? `${posPct}%` : '100%'}
      style:left="0"
      style:bottom={isMobile ? 'auto' : '0'}
      style:top={isMobile ? '0' : 'auto'}
    ></div>
    <div class="timeline-dots">
      {#each dots as dot}
        <div
          class="tl-dot"
          class:year-dot={dot.isYearDot}
          class:past={dot.idx > currentIdx}
          class:active={dot.idx === currentIdx}
          style:top={isMobile ? '50%' : `${dot.pct}%`}
          style:left={isMobile ? `${100 - dot.pct}%` : '50%'}
          onclick={() => handleDotClick(dot.idx)}
        ></div>
      {/each}
    </div>
    <div
      class="timeline-thumb"
      style:top={isMobile ? '50%' : `${pct}%`}
      style:left={isMobile ? `${posPct}%` : '50%'}
      onmousedown={handleThumbMousedown}
      ontouchstart={(e) => { dragging = true; e.preventDefault(); }}
    ></div>
  </div>
  <div class="tl-bound" style:opacity={isMobile ? startOpacity : endOpacity}>{isMobile ? startYear : endYear}</div>
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
  /* Per-quarter ticks are invisible by default — only year boundaries
     get a visible dot (see .year-dot below). Tried showing every
     quarter as a small tick but the paper-coloured past-ticks on the
     vermillion fill read as ugly white speckle. The thumb position +
     month/year label below the track tell the user where they are. */
  .tl-dot {
    position: absolute;
    left: 50%;
    width: 14px;
    height: 8px;
    margin-left: -7px;
    margin-top: -4px;
    background: transparent;
    cursor: pointer;
    transition: background 0.15s;
    border-radius: 4px;
  }
  .tl-dot:hover {
    background: rgba(184, 96, 62, 0.18);
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

  /* ── Mobile: horizontal slider docked at the bottom of the map ──────────
     Override unconditionally on mobile (no .horizontal class dependency) —
     Svelte 5 + Astro scoped CSS has been unreliable with dynamic class
     modifiers, so we collapse the override to plain media-query selectors. */
  @media (max-width: 640px) {
    .time-slider {
      position: fixed !important;
      left: 12px !important;
      right: 12px !important;
      bottom: 16px !important;
      top: auto !important;
      transform: none !important;
      width: auto !important;
      flex-direction: row !important;
      align-items: center !important;
      gap: 10px !important;
      padding: 10px 14px !important;
      background: rgba(244, 239, 230, 0.94);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--rule, #D9D2C5);
      border-radius: 99px;
      box-shadow: 0 4px 14px rgba(27, 20, 14, 0.08);
      /* Tell the browser we're handling all touch gestures here — no
         horizontal page scroll, no back-swipe, no pull-to-refresh while
         the user is scrubbing the timeline. */
      touch-action: none !important;
    }
    .time-slider .tl-bound {
      font-family: 'IBM Plex Mono', monospace;
      font-size: 9px;
      color: var(--mist, #6E665E);
      flex-shrink: 0;
    }
    .time-slider .timeline-track {
      flex: 1 !important;
      width: auto !important;
      height: 4px !important;
      border-radius: 2px !important;
      background: rgba(200, 192, 184, 0.4) !important;
      box-shadow: none !important;
      /* Larger invisible touch target — the 4px hairline is hard to
         hit on a thumb; pad the track with a transparent ::before
         that captures pointer events across a 28px-tall band. */
      position: relative;
      touch-action: none !important;
    }
    .time-slider .timeline-track::before {
      /* Invisible hit-extender. pointer-events: auto (default for pseudos
         on a positioned parent) so taps on this band still trigger the
         track's mousedown/touchstart handlers. */
      content: '';
      position: absolute;
      left: 0;
      right: 0;
      top: -14px;
      bottom: -14px;
      background: transparent;
    }
    .time-slider .timeline-thumb {
      touch-action: none !important;
    }
    .time-slider .timeline-fill {
      height: 100% !important;
      border-radius: 2px !important;
    }
    .time-slider .timeline-thumb {
      width: 14px !important; height: 14px !important;
      margin-left: -7px !important; margin-top: -7px !important;
      border-radius: 50% !important;
      box-shadow:
        0 0 0 3px rgba(184, 74, 46, 0.18),
        0 1px 3px rgba(0, 0, 0, 0.18) !important;
    }
    /* Mobile: per-quarter ticks stay invisible (large hit target only);
       only year-boundary dots are rendered visibly. */
    .time-slider .tl-dot {
      width: 14px !important; height: 14px !important;
      margin-left: -7px !important; margin-top: -7px !important;
      border-radius: 50% !important;
      background: transparent !important;
    }
    .time-slider .tl-dot.year-dot {
      width: 6px !important; height: 6px !important;
      margin-left: -3px !important; margin-top: -3px !important;
    }
    .time-slider .tl-current-label {
      font-size: 11px !important;
      margin-top: 0 !important;
      flex-shrink: 0;
      min-width: 50px;
      text-align: center;
    }
    .time-slider .tl-current-label .y {
      display: inline !important;
      font-size: 11px;
      margin-left: 3px;
      color: var(--mist, #6E665E);
    }
  }
</style>
