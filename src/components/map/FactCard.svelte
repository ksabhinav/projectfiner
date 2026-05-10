<script lang="ts">
  /**
   * FactCard.svelte — Atlas "A finding" modal.
   *
   * Listens for `finer:show-finding` (fired by FindingButton).
   * Loads findings from {base}findings.json.
   *
   * Three actions:
   *   - Open in map  → fires camelCase events the inline JS listens to
   *                     (finer:indicatorChange + finer:quarterChange + finer:stateFilterChange)
   *   - Read note    → /fact/<slug-or-id> (page need not exist yet — graceful 404)
   *   - Another →    → next finding
   */
  import { onMount } from 'svelte';

  interface Finding {
    id: string;
    eyebrow: string;
    headline: string;
    statValue: string;
    statUnit?: string;
    statLabel: string;
    statDelta?: string;
    lede: string;
    source: string;
    indicator: string;       // existing key, e.g. 'kcc'
    metricIdx?: number;       // optional — defaults to 0
    quarter: string;          // e.g. 'Sep 2025' or '2025-09'
    scope: string;            // e.g. 'Bihar' or 'All India'
    notePath?: string;
  }

  // Light fallback if findings.json fails to load
  const SAMPLE: Finding[] = [
    {
      id: '014',
      eyebrow: 'Did you notice',
      headline: 'Bihar issued <em>42% fewer</em> Kisan Credit Cards this year than two years ago — even as its branch network expanded.',
      statValue: '−42',
      statUnit: '%',
      statLabel: 'KCC ISSUED · BIHAR · DEC 2023 → SEP 2025',
      statDelta: '▼ STEEPEST FALL IN 5 YEARS',
      lede: 'The drop is concentrated in Purnia, Katihar, and Madhepura — the same districts where new branches opened. So they have more counters and fewer farmers using them. <em>Curious.</em>',
      source: 'SOURCE · SLBC BIHAR · 92ND–95TH MEETINGS · n = 38 DISTRICTS',
      indicator: 'kcc',
      quarter: '2025-09',
      scope: 'BIHAR',
      notePath: 'bihar-kcc-paradox',
    },
  ];

  let findings = $state<Finding[]>(SAMPLE);
  let isOpen = $state(false);
  let currentIdx = $state(0);
  const current = $derived(findings[currentIdx % findings.length]);

  const base = (import.meta.env.BASE_URL || '/');

  // Quarter normalization: accept "Sep 2025" or "2025-09" or "September 2025"
  function normalizeQuarter(q: string): string {
    if (!q) return '';
    if (/^\d{4}-\d{2}$/.test(q)) return q;
    const months: Record<string, string> = {
      jan: '01', feb: '02', mar: '03', apr: '04', may: '05', jun: '06',
      jul: '07', aug: '08', sep: '09', oct: '10', nov: '11', dec: '12',
      january: '01', february: '02', march: '03', april: '04', june: '06',
      july: '07', august: '08', september: '09', october: '10', november: '11', december: '12',
    };
    const m = q.toLowerCase().match(/([a-z]+)\s+(\d{4})/);
    if (m && months[m[1]]) return `${m[2]}-${months[m[1]]}`;
    return q;
  }
  function normalizeScope(s: string): string {
    if (!s || /^all\s*india$/i.test(s)) return '';
    return s.toUpperCase();
  }

  onMount(() => {
    fetch(`${base}findings.json`)
      .then((r) => (r.ok ? r.json() : SAMPLE))
      .then((data: Finding[]) => {
        if (Array.isArray(data) && data.length) findings = data;
      })
      .catch(() => {});

    function show() { isOpen = true; }
    function close(e: KeyboardEvent) {
      if (e.key === 'Escape' && isOpen) isOpen = false;
    }
    window.addEventListener('finer:show-finding', show);
    window.addEventListener('keydown', close);
    return () => {
      window.removeEventListener('finer:show-finding', show);
      window.removeEventListener('keydown', close);
    };
  });

  function next() {
    currentIdx = (currentIdx + 1) % findings.length;
  }

  function applyToMap() {
    const f = current;
    // Use the existing camelCase event protocol
    window.dispatchEvent(new CustomEvent('finer:indicatorChange', {
      detail: { indicator: f.indicator, metricIdx: f.metricIdx ?? 0 },
    }));
    const qNorm = normalizeQuarter(f.quarter);
    window.dispatchEvent(new CustomEvent('finer:quarterChange', {
      detail: { quarter: qNorm, idx: 0 },
    }));
    const stNorm = normalizeScope(f.scope);
    window.dispatchEvent(new CustomEvent('finer:stateFilterChange', {
      detail: { state: stNorm },
    }));
    isOpen = false;
  }

  function readNote() {
    if (!current) return;
    const slug = current.notePath || current.id;
    window.location.href = `${base}fact/${slug}`;
  }

  const today = new Date().toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
  }).toUpperCase();
</script>

{#if isOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={() => (isOpen = false)} role="presentation"></div>

  <div class="card" role="dialog" aria-modal="true" aria-labelledby="finding-headline">
    <div class="strip"></div>

    <div class="meta">
      <span class="id">FINDING {current.id} / {findings.length.toString().padStart(3, '0')}</span>
      <span>{today}</span>
    </div>

    <div class="body">
      <div class="eye">{current.eyebrow}</div>

      <h2 id="finding-headline" class="head">{@html current.headline}</h2>

      <div class="stat-row">
        <div class="stat">
          {current.statValue}{#if current.statUnit}<span class="unit">{current.statUnit}</span>{/if}
        </div>
        <div class="stat-label">
          {current.statLabel}
          {#if current.statDelta}<br><span class="delta">{current.statDelta}</span>{/if}
        </div>
      </div>

      <div class="lede">{@html current.lede}</div>

      <div class="source">{current.source}</div>

      <div class="actions">
        <button class="btn primary" onclick={applyToMap}>Open in map</button>
        <button class="btn ghost" onclick={readNote}>Read the note</button>
        <button class="btn next" onclick={next}>Another →</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(27, 20, 14, 0.55);
    z-index: 1500;
    animation: fadeIn 260ms cubic-bezier(0.32, 0.72, 0.40, 1.00);
  }

  .card {
    position: fixed;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: min(540px, calc(100vw - 32px));
    max-height: calc(100vh - 64px);
    overflow-y: auto;
    background: #F4EFE6;
    border: 1px solid #1B140E;
    border-radius: 4px;
    box-shadow:
      0 32px 80px rgba(27, 20, 14, 0.4),
      0 8px 20px rgba(27, 20, 14, 0.15);
    z-index: 1501;
    animation: slideUp 400ms cubic-bezier(0.20, 0.80, 0.20, 1.00);
  }
  .strip {
    height: 6px;
    background: linear-gradient(90deg, #B84A2E, #D4A24A);
  }
  .meta {
    padding: 14px 28px 0;
    display: flex; justify-content: space-between;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: #6E665E;
    letter-spacing: 0.05em;
  }
  .meta .id { color: #B84A2E; font-weight: 600; }

  .body { padding: 12px 40px 32px; }

  .eye {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: #B84A2E;
    margin-bottom: 18px;
    display: flex; align-items: center; gap: 10px;
  }
  .eye::after {
    content: '';
    flex: 1; height: 1px;
    background: #D9D2C5;
  }

  .head {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 400;
    font-variation-settings: 'opsz' 144;
    font-size: 30px;
    line-height: 1.18;
    letter-spacing: -0.02em;
    color: #1B140E;
    margin-bottom: 18px;
  }
  .head :global(em) {
    color: #B84A2E;
    font-style: italic;
    font-weight: 320;
  }

  .stat-row {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 22px; align-items: end;
    padding: 16px 0;
    border-top: 1px dashed #D9D2C5;
    border-bottom: 1px dashed #D9D2C5;
    margin-bottom: 16px;
  }
  .stat {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 380;
    font-variation-settings: 'opsz' 144;
    font-size: 60px;
    line-height: 0.85;
    color: #8E331E;
    font-feature-settings: 'tnum';
    letter-spacing: -0.025em;
  }
  .stat .unit {
    font-size: 28px;
    color: #6E665E;
    font-weight: 300;
    margin-left: 4px;
  }
  .stat-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: #3D332A;
    letter-spacing: 0.04em;
    line-height: 1.6;
    text-transform: uppercase;
  }
  .stat-label .delta {
    color: #8C2E20;
    font-weight: 600;
  }

  .lede {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 14.5px;
    line-height: 1.6;
    color: #3D332A;
    margin-bottom: 16px;
  }
  .lede :global(em) { color: #1B140E; font-style: italic; }

  .source {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5px;
    color: #6E665E;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding-bottom: 22px;
    border-bottom: 1px solid #D9D2C5;
    margin-bottom: 22px;
  }

  .actions {
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
  }
  .btn {
    font-family: 'Inter', sans-serif;
    font-size: 9.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding: 11px 16px;
    border: 1px solid #1B140E;
    border-radius: 4px;
    cursor: pointer;
    transition:
      transform 160ms cubic-bezier(0.32, 0.72, 0.40, 1.00),
      box-shadow 160ms cubic-bezier(0.32, 0.72, 0.40, 1.00);
  }
  .btn.primary { background: #1B140E; color: #F4EFE6; }
  .btn.ghost { background: #F4EFE6; color: #1B140E; }
  .btn.next {
    background: #B84A2E;
    color: #F4EFE6;
    border-color: #B84A2E;
    margin-left: auto;
    box-shadow: 0 2px 0 #8E331E;
  }
  .btn:hover { transform: translateY(-1px); }
  .btn:active { transform: translateY(0); transition-duration: 80ms; }

  @keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translate(-50%, calc(-50% + 60px));
    }
    to {
      opacity: 1;
      transform: translate(-50%, -50%);
    }
  }

  @media (max-width: 760px) {
    .body { padding: 8px 24px 24px; }
    .head { font-size: 22px; }
    .stat { font-size: 44px; }
    .stat .unit { font-size: 22px; }
    .lede { font-size: 13px; }
    .actions { gap: 8px; }
    .btn { padding: 9px 12px; font-size: 9px; }
    .btn.next { margin-left: 0; }
  }
</style>
