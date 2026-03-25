<script lang="ts">
  import { onMount } from 'svelte';
  import { onFiner, dispatchFiner, getFinerState } from '../../lib/map-bridge';
  import type { FocusUpdateDetail } from '../../lib/map-bridge';

  interface Props {}
  let {}: Props = $props();

  let active = $state(false);
  let district = $state('');
  let stateName = $state('');
  let svgPath = $state('');
  let svgViewBox = $state('0 0 400 400');
  let fillColor = $state('#b8603e');
  let strokeColor = $state('#6b4c2a');
  let metricLabel = $state('');
  let value = $state('');
  let quarter = $state('');

  function applyUpdate(detail: FocusUpdateDetail) {
    active = detail.active;
    if (!detail.active) return;
    district = detail.district;
    stateName = detail.state;
    svgPath = detail.svgPath;
    svgViewBox = detail.svgViewBox || '0 0 400 400';
    fillColor = detail.fillColor || '#b8603e';
    strokeColor = detail.strokeColor || '#6b4c2a';
    metricLabel = detail.metricLabel;
    value = detail.value;
    quarter = detail.quarter;
  }

  function exitFocus() {
    active = false;
    dispatchFiner('exitFocus');
  }

  function handleBackdropClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (target.classList.contains('district-focus')) {
      exitFocus();
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && active) {
      exitFocus();
    }
  }

  onMount(() => {
    // Sync from global state if focus is already active
    const s = getFinerState();
    if (s?.focus?.active) {
      applyUpdate(s.focus);
    }

    const unsubs = [
      onFiner('focusUpdate', applyUpdate),
    ];

    window.addEventListener('keydown', handleKeydown);

    return () => {
      unsubs.forEach(fn => fn());
      window.removeEventListener('keydown', handleKeydown);
    };
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="district-focus"
  class:active
  onclick={handleBackdropClick}
>
  <div class="focus-shape-wrap">
    <svg class="focus-svg" viewBox={svgViewBox} preserveAspectRatio="xMidYMid meet">
      <path
        class="focus-path"
        d={svgPath}
        fill={fillColor}
        stroke={strokeColor}
        stroke-width="2"
      />
    </svg>
    <div class="focus-info">
      <div class="focus-name">{district}</div>
      <div class="focus-state">{stateName}</div>
      <div class="focus-metric-label">{metricLabel}</div>
      <div class="focus-value">{value}</div>
      <div class="focus-quarter">{quarter}</div>
    </div>
    <button class="focus-close" onclick={exitFocus}>&times;</button>
  </div>
</div>

<style>
  .district-focus {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 1200;
    background: rgba(245,244,241,0.88);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    align-items: center;
    justify-content: center;
  }

  .district-focus.active {
    display: flex;
    animation: focusAppear 0.35s ease;
  }

  @keyframes focusAppear {
    0% { opacity: 0; }
    100% { opacity: 1; }
  }

  .focus-shape-wrap {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .focus-svg {
    width: 380px;
    height: 380px;
    filter: drop-shadow(4px 6px 12px rgba(0,0,0,0.15));
    overflow: visible;
  }

  .focus-path {
    stroke-width: 3;
    stroke-linejoin: round;
    transition: fill 0.3s ease;
  }

  .focus-info {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
    pointer-events: none;
    width: 80%;
  }

  .focus-name {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 26px;
    font-weight: 700;
    color: #1a1410;
    letter-spacing: -0.01em;
    margin-bottom: 16px;
    text-shadow: -2px -2px 0 #fff, 2px -2px 0 #fff, -2px 2px 0 #fff, 2px 2px 0 #fff, 0 0 8px rgba(255,255,255,0.95);
  }

  .focus-state {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 500;
    color: #aaa09a;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 4px;
    text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 5px rgba(255,255,255,0.9);
  }

  .focus-metric-label {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #1a1410;
    margin-bottom: 6px;
    text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 6px rgba(255,255,255,0.9);
  }

  .focus-value {
    font-family: Georgia, serif;
    font-size: 44px;
    font-weight: 700;
    color: #1a1410;
    line-height: 1;
    margin-bottom: 12px;
    text-shadow: -2px -2px 0 #fff, 2px -2px 0 #fff, -2px 2px 0 #fff, 2px 2px 0 #fff, 0 0 10px rgba(255,255,255,0.95);
  }

  .focus-quarter {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    font-weight: 600;
    color: #888078;
    text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 5px rgba(255,255,255,0.9);
  }

  .focus-close {
    position: absolute;
    top: -16px;
    right: -16px;
    width: 36px;
    height: 36px;
    background: rgba(255,255,255,0.94);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(224,221,216,0.5);
    border-radius: 8px;
    font-size: 20px;
    font-weight: 600;
    color: #555048;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.04);
    transition: all 0.2s;
    line-height: 1;
  }

  .focus-close:hover {
    background: #fff;
    color: #1a1410;
    box-shadow: 0 6px 20px rgba(0,0,0,0.08);
    transform: translateY(-1px);
  }

  /* ── Mobile ── */
  @media (max-width: 640px) {
    .focus-svg {
      width: 260px;
      height: 260px;
    }

    .focus-name {
      font-size: 20px;
    }

    .focus-value {
      font-size: 32px;
    }

    .focus-metric-label {
      font-size: 9px;
    }

    .focus-quarter {
      font-size: 10px;
    }
  }
</style>
