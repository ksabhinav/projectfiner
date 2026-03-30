<script lang="ts">
  import { onMount } from 'svelte';
  import { dispatchFiner, onFiner, getFinerState } from '../../lib/map-bridge';

  interface Props {}
  let {}: Props = $props();

  // ── State ──
  let scope = $state<'india' | 'ne'>('ne');

  // Banking controls
  let currentIndicator = $state('digital_transactions');
  let currentMetricIdx = $state(0);
  let bankingStateFilter = $state('');

  // Stats
  let statsBankingHTML = $state('Select Banking Access to view FI data');
  let showResetBanking = $state(false);

  // Indicator definitions from window.__FINER
  let indicators: Record<string, any> = $state({});
  let metrics: { field: string; label: string; unit: string; desc: string }[] = $state([]);

  // Scope toggle derived
  let scopeIsNE = $derived(scope === 'ne');

  // Banking states list
  const BANKING_STATES = [
    { value: 'ASSAM', label: 'Assam' },
    { value: 'BIHAR', label: 'Bihar' },
    { value: 'JHARKHAND', label: 'Jharkhand' },
    { value: 'MEGHALAYA', label: 'Meghalaya' },
    { value: 'MANIPUR', label: 'Manipur' },
    { value: 'ARUNACHAL PRADESH', label: 'Arunachal Pradesh' },
    { value: 'MIZORAM', label: 'Mizoram' },
    { value: 'TRIPURA', label: 'Tripura' },
    { value: 'NAGALAND', label: 'Nagaland' },
    { value: 'CHHATTISGARH', label: 'Chhattisgarh' },
    { value: 'ODISHA', label: 'Odisha' },
    { value: 'SIKKIM', label: 'Sikkim' },
    { value: 'WEST BENGAL', label: 'West Bengal' },
    { value: 'GUJARAT', label: 'Gujarat' },
    { value: 'HARYANA', label: 'Haryana' },
    { value: 'KARNATAKA', label: 'Karnataka' },
    { value: 'KERALA', label: 'Kerala' },
    { value: 'MAHARASHTRA', label: 'Maharashtra' },
    { value: 'RAJASTHAN', label: 'Rajasthan' },
    { value: 'TAMIL NADU', label: 'Tamil Nadu' },
    { value: 'TELANGANA', label: 'Telangana' },
    { value: 'UTTARAKHAND', label: 'Uttarakhand' },
  ];

  const NE_STATES_SET = new Set(['ASSAM','MEGHALAYA','MANIPUR','ARUNACHAL PRADESH','MIZORAM','TRIPURA','NAGALAND','SIKKIM']);

  let filteredBankingStates = $derived(
    scope === 'ne'
      ? BANKING_STATES.filter(s => NE_STATES_SET.has(s.value))
      : BANKING_STATES
  );

  // Indicator dropdown options
  const INDICATOR_OPTIONS = [
    { value: 'digital_transactions', label: 'Digital Transactions' },
    { value: 'credit_deposit_ratio', label: 'Credit-Deposit Ratio' },
    { value: 'pmjdy', label: 'PM Jan Dhan Yojana' },
    { value: 'branch_network', label: 'Branch Network' },
    { value: 'kcc', label: 'Kisan Credit Card' },
    { value: 'shg', label: 'Self Help Groups' },
    { value: 'aadhaar_authentication', label: 'Aadhaar Authentication' },
    { value: 'social_security', label: 'Social Security (PMSBY/PMJJBY/APY)' },
    { value: 'pmegp', label: 'PM Employment Generation' },
    { value: 'housing_pmay', label: 'Housing / PMAY' },
    { value: 'sui', label: 'Stand Up India' },
    { value: 'sc_st_finance', label: 'SC/ST Lending' },
    { value: 'women_finance', label: "Women's Credit" },
    { value: 'education_loan', label: 'Education Loans' },
    { value: 'pmmy_mudra_disbursement', label: 'MUDRA / PMMY' },
    { value: 'rbi_banking_outlets', label: 'Banking Infrastructure (RBI)' },
    { value: 'nrlm_shg', label: 'Self-Help Groups (NRLM)' },
    { value: 'rbi_bsr_credit', label: 'Bank Credit (RBI BSR-1)' },
    { value: 'nfhs_health_insurance', label: 'Health Insurance (NFHS-5)' },
    { value: 'capital_markets_access', label: 'Capital Markets Access' },
  ];

  // ── Handlers ──

  function handleScopeToggle() {
    const newScope = scope === 'ne' ? 'india' : 'ne';
    scope = newScope;
    // Reset banking state filter if current filter is outside NE
    if (newScope === 'ne' && bankingStateFilter && !NE_STATES_SET.has(bankingStateFilter)) {
      bankingStateFilter = '';
    }
    dispatchFiner('scopeChange', { scope: newScope });
  }

  function handleIndicatorChange(e: Event) {
    const val = (e.target as HTMLSelectElement).value;
    currentIndicator = val;
    currentMetricIdx = 0;
    updateMetrics();
    dispatchFiner('indicatorChange', { indicator: val, metricIdx: 0 });
  }

  function handleMetricChange(e: Event) {
    currentMetricIdx = parseInt((e.target as HTMLSelectElement).value);
    dispatchFiner('metricChange', { metricIdx: currentMetricIdx });
  }

  function handleBankingStateChange(e: Event) {
    bankingStateFilter = (e.target as HTMLSelectElement).value;
    showResetBanking = !!bankingStateFilter;
    dispatchFiner('stateFilterChange', { state: bankingStateFilter });
  }

  // Info buttons
  function showInfo(type: 'indicator' | 'metric', e: MouseEvent | TouchEvent) {
    if (e.type === 'touchstart') e.preventDefault();
    const btn = e.currentTarget as HTMLElement;
    const rect = btn.getBoundingClientRect();
    const ind = indicators[currentIndicator];
    let text = '';
    if (type === 'indicator') {
      text = ind?.desc || '';
    } else {
      const metric = ind?.metrics?.[currentMetricIdx];
      text = metric?.desc || '';
    }
    dispatchFiner('showInfo', { text, rect });
  }

  // Reset buttons
  function resetBanking() {
    bankingStateFilter = '';
    showResetBanking = false;
    dispatchFiner('resetBanking', {});
  }

  // Update metrics dropdown from indicators data
  function updateMetrics() {
    const ind = indicators[currentIndicator];
    if (!ind) { metrics = []; return; }
    metrics = ind.metrics || [];
    if (currentMetricIdx >= metrics.length) currentMetricIdx = 0;
  }

  // ── Lifecycle ──

  onMount(() => {
    // Read initial state from window.__FINER
    const s = getFinerState();
    if (s) {
      scope = s.scope || 'ne';
      currentIndicator = s.indicator || 'digital_transactions';
      currentMetricIdx = s.metricIdx || 0;
      bankingStateFilter = s.stateFilter || '';
      showResetBanking = !!bankingStateFilter;
      if (s.indicators) {
        indicators = s.indicators;
        updateMetrics();
      }
    }

    const unsubs = [
      onFiner('stateUpdate', () => {
        const st = getFinerState();
        if (!st) return;
        scope = st.scope || scope;
        if (st.indicators && Object.keys(st.indicators).length > 0) {
          indicators = st.indicators;
          updateMetrics();
        }
      }),
      onFiner('statsUpdate', () => {
        const st = getFinerState();
        if (!st) return;
        if (st.stats?.html) statsBankingHTML = st.stats.html;
        showResetBanking = !!bankingStateFilter;
      }),
      onFiner('indicatorsReady', (detail: { indicators: Record<string, any> }) => {
        indicators = detail.indicators;
        updateMetrics();
      }),
      onFiner('bankingStatsUpdate', (detail: { html: string; showReset: boolean }) => {
        statsBankingHTML = detail.html;
        showResetBanking = detail.showReset ?? !!bankingStateFilter;
      }),
    ];

    // Mobile bottom sheet
    if (typeof window !== 'undefined' && window.innerWidth <= 640) {
      const panel = document.getElementById('panel');
      if (panel) {
        panel.classList.add('collapsed');

        const handle = document.getElementById('panel-handle');
        const head = document.getElementById('panel-head');

        if (handle) {
          handle.addEventListener('click', () => panel.classList.toggle('collapsed'));
        }
        if (head) {
          head.addEventListener('click', () => panel.classList.toggle('collapsed'));
        }

        let startY = 0, startTime = 0;
        panel.addEventListener('touchstart', (e: TouchEvent) => {
          startY = e.touches[0].clientY;
          startTime = Date.now();
        }, { passive: true });
        panel.addEventListener('touchend', (e: TouchEvent) => {
          const dy = e.changedTouches[0].clientY - startY;
          const dt = Date.now() - startTime;
          if (dt < 400) {
            if (dy > 40) panel.classList.add('collapsed');
            else if (dy < -40) panel.classList.remove('collapsed');
          }
        }, { passive: true });

        // Collapse when map is tapped
        const mapEl = document.getElementById('map');
        if (mapEl) {
          mapEl.addEventListener('click', () => {
            if (!panel.classList.contains('collapsed')) {
              panel.classList.add('collapsed');
            }
          });
        }
      }
    }

    return () => {
      unsubs.forEach(fn => fn());
    };
  });
</script>

<div id="panel">
  <div id="panel-handle"><span></span></div>
  <div id="panel-head">
    <h1>Project <em>FINER</em></h1>
    <p class="panel-sub">Financial Inclusion Across India</p>
    <p class="panel-stats">800+ Districts &middot; 36 States &middot; 20 Indicators</p>
    <p class="panel-hint">Double-click a district to focus</p>
  </div>

  <div id="scope-toggle">
    <span class="scope-label" class:active={scope === 'india'}>All India</span>
    <label class="toggle-switch">
      <input type="checkbox" checked={scopeIsNE} onchange={handleScopeToggle} />
      <span class="toggle-slider"></span>
    </label>
    <span class="scope-label" class:active={scope === 'ne'}>Focus NE</span>
  </div>

  <div id="panel-body">
    <!-- Banking controls -->
    <div id="controls-banking">
      <div class="field">
        <span class="flabel">Indicator</span>
        <div class="select-with-info">
          <select class="finput banking-input" id="sel-indicator" value={currentIndicator} onchange={handleIndicatorChange}>
            {#each INDICATOR_OPTIONS as opt}
              <option value={opt.value}>{opt.label}</option>
            {/each}
          </select>
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <button class="info-btn" type="button"
            onmouseenter={(e) => showInfo('indicator', e)}
            onmouseleave={() => dispatchFiner('hideInfo')}
            ontouchstart={(e) => showInfo('indicator', e)}>i</button>
        </div>
      </div>

      <div class="field">
        <span class="flabel">Metric</span>
        <div class="select-with-info">
          <select class="finput banking-input" id="sel-metric" value={currentMetricIdx} onchange={handleMetricChange}>
            {#each metrics as m, i}
              <option value={i}>{m.label}</option>
            {/each}
          </select>
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <button class="info-btn" type="button"
            onmouseenter={(e) => showInfo('metric', e)}
            onmouseleave={() => dispatchFiner('hideInfo')}
            ontouchstart={(e) => showInfo('metric', e)}>i</button>
        </div>
      </div>

      <div style="height:1px;background:#e8e5e0;margin:10px 0"></div>

      <div class="field">
        <span class="flabel">State</span>
        <select class="finput banking-input" id="sel-state" value={bankingStateFilter} onchange={handleBankingStateChange}>
          <option value="">{scope === 'ne' ? 'All NE States' : 'All States'}</option>
          {#each filteredBankingStates as st}
            <option value={st.value}>{st.label}</option>
          {/each}
        </select>
      </div>

      <div id="stats-banking">{@html statsBankingHTML}</div>
      <button id="btn-reset-banking" style:display={showResetBanking ? 'block' : 'none'} onclick={resetBanking}>&#8634; Reset</button>
    </div>
  </div>
</div>

<style>
  /* Panel styles are applied globally in index.astro — these are component-scoped overrides */
  /* The id="panel" CSS is in the global stylesheet since inline JS also references it */
</style>
