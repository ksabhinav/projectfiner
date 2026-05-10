<script lang="ts">
  /**
   * FocusOverlay.svelte — Atlas focus mode
   *
   * Full-viewport ink overlay. District rendered as a vermillion silhouette
   * on the left; stat block on the right with the active metric in saffron.
   * ESC hint at the foot, 'X' close in the top-right.
   */
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
    if (target.classList.contains('district-focus')) exitFocus();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && active) exitFocus();
  }

  // Split formatted "73.2%" → number + unit-suffix for typographic styling
  let valNum = $derived.by(() => {
    if (!value) return '';
    const m = String(value).match(/^([^A-Za-z%₹]*[\d.,]+)\s*(.*)$/);
    return m ? m[1].trim() : value;
  });
  let valUnit = $derived.by(() => {
    if (!value) return '';
    const m = String(value).match(/^([^A-Za-z%₹]*[\d.,]+)\s*(.*)$/);
    return m ? m[2].trim() : '';
  });

  function titleCase(s: string): string {
    if (!s) return '';
    return s.split(' ').map(w => w[0] + w.slice(1).toLowerCase()).join(' ');
  }

  onMount(() => {
    const s = getFinerState();
    if (s?.focus?.active) applyUpdate(s.focus);

    const unsubs = [onFiner('focusUpdate', applyUpdate)];
    window.addEventListener('keydown', handleKeydown);

    return () => {
      unsubs.forEach(fn => fn());
      window.removeEventListener('keydown', handleKeydown);
    };
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="district-focus" class:active onclick={handleBackdropClick}>
  <button class="focus-close" onclick={exitFocus} aria-label="Close focus">×</button>

  <div class="focus-grid">
    <div class="focus-shape-col">
      <svg class="focus-svg" viewBox={svgViewBox} preserveAspectRatio="xMidYMid meet">
        <path
          class="focus-path"
          d={svgPath}
          fill="#B84A2E"
          stroke="#8E331E"
          stroke-width="2"
        />
      </svg>
    </div>

    <div class="focus-info-col">
      <div class="focus-eyebrow">A district profile</div>
      <h2 class="focus-name">{district}</h2>
      <div class="focus-state">{titleCase(stateName)}</div>

      <div class="focus-stats">
        <div class="stat active">
          <div class="stat-label">{metricLabel}</div>
          <div class="stat-num">
            {valNum}{#if valUnit}<span class="stat-unit"> {valUnit}</span>{/if}
          </div>
        </div>
      </div>

      <div class="focus-meta">
        <span>{quarter}</span>
        <span class="rule"></span>
        <span>SOURCE · SLBC</span>
      </div>
    </div>
  </div>

  <div class="focus-hint">
    <span class="kbd">ESC</span> to exit
  </div>
</div>

<style>
  .district-focus {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 1200;
    background: rgba(13, 9, 6, 0.99);          /* 99% — near-pure black, kills map bleed */
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    align-items: center;
    justify-content: center;
    padding: 60px 80px;
  }
  .district-focus.active {
    display: flex;
    animation: focusAppear 0.35s cubic-bezier(0.20, 0.80, 0.20, 1.00);
  }
  @keyframes focusAppear {
    0% { opacity: 0; }
    100% { opacity: 1; }
  }

  .focus-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
    gap: 80px;
    align-items: center;
    width: 100%;
    max-width: 1100px;
  }

  .focus-shape-col {
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .focus-svg {
    width: 100%;
    max-width: 460px;
    aspect-ratio: 1;
    filter: drop-shadow(0 12px 32px rgba(184, 74, 46, 0.35));
    overflow: visible;
  }
  .focus-path {
    stroke-linejoin: round;
    transition: fill 0.3s ease;
  }

  .focus-info-col { color: var(--paper, #F4EFE6); }

  .focus-eyebrow {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: #D4A24A;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .focus-eyebrow::after {
    content: '';
    flex: 1;
    height: 1px;
    background: rgba(217, 210, 197, 0.2);
    max-width: 180px;
  }

  .focus-name {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 400;
    font-variation-settings: 'opsz' 144;
    font-size: 64px;
    line-height: 1.0;
    letter-spacing: -0.025em;
    color: #F4EFE6;
    margin-bottom: 6px;
  }
  .focus-state {
    font-family: 'Source Serif 4', Georgia, serif;
    font-style: italic;
    font-size: 18px;
    color: rgba(244, 239, 230, 0.6);
    margin-bottom: 36px;
  }

  .focus-stats {
    border-top: 1px solid rgba(217, 210, 197, 0.18);
    border-bottom: 1px solid rgba(217, 210, 197, 0.18);
    padding: 22px 0;
    margin-bottom: 22px;
  }
  .stat-label {
    font-family: 'Inter', sans-serif;
    font-size: 9.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: rgba(244, 239, 230, 0.55);
    margin-bottom: 6px;
  }
  .stat-num {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 380;
    font-variation-settings: 'opsz' 144;
    font-size: 80px;
    line-height: 0.9;
    letter-spacing: -0.025em;
    color: #D4A24A; /* saffron — Atlas: active stat highlighted */
    font-feature-settings: 'tnum';
  }
  .stat-unit {
    font-size: 32px;
    color: rgba(244, 239, 230, 0.45);
    font-weight: 300;
    margin-left: 6px;
  }

  .focus-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: rgba(244, 239, 230, 0.55);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .focus-meta .rule {
    flex: 0 0 auto;
    width: 28px;
    height: 1px;
    background: rgba(217, 210, 197, 0.3);
  }

  .focus-close {
    position: absolute;
    top: 24px;
    right: 28px;
    width: 38px;
    height: 38px;
    background: transparent;
    border: 1px solid rgba(217, 210, 197, 0.25);
    border-radius: 50%;
    font-size: 22px;
    font-weight: 300;
    color: rgba(244, 239, 230, 0.7);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    line-height: 1;
    transition: background 160ms ease, border-color 160ms ease, color 160ms ease;
    font-family: 'Inter', sans-serif;
  }
  .focus-close:hover {
    background: rgba(244, 239, 230, 0.08);
    border-color: rgba(217, 210, 197, 0.55);
    color: #F4EFE6;
  }

  .focus-hint {
    position: absolute;
    bottom: 28px;
    left: 50%;
    transform: translateX(-50%);
    font-family: 'Source Serif 4', Georgia, serif;
    font-style: italic;
    font-size: 12.5px;
    color: rgba(244, 239, 230, 0.55);
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .kbd {
    font-family: 'IBM Plex Mono', monospace;
    font-style: normal;
    font-size: 10px;
    background: rgba(244, 239, 230, 0.08);
    border: 1px solid rgba(217, 210, 197, 0.2);
    padding: 3px 7px;
    border-radius: 3px;
    color: rgba(244, 239, 230, 0.75);
    letter-spacing: 0.08em;
  }

  /* Mobile: stack columns */
  @media (max-width: 760px) {
    .district-focus { padding: 60px 24px 80px; align-items: flex-start; padding-top: 80px; }
    .focus-grid { grid-template-columns: 1fr; gap: 28px; }
    .focus-svg { max-width: 220px; }
    .focus-name { font-size: 38px; }
    .focus-state { font-size: 14px; margin-bottom: 22px; }
    .stat-num { font-size: 54px; }
    .stat-unit { font-size: 22px; }
    .focus-eyebrow { font-size: 9px; }
  }
</style>
