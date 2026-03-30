<script lang="ts">
  import { onMount } from 'svelte';
  import { dispatchFiner, onFiner, getFinerState } from '../../lib/map-bridge';
  import { fmtNum } from '../../lib/format-utils';

  interface Props {}
  let {}: Props = $props();

  // ── State ──
  let mode = $state<'capital' | 'banking'>('banking');
  let scope = $state<'india' | 'ne'>('ne');
  let capitalView = $state<'choro' | 'dots'>('choro');
  let drilldownActive = $state(false);

  // Banking controls
  let currentIndicator = $state('digital_transactions');
  let currentMetricIdx = $state(0);
  let bankingStateFilter = $state('');

  // Capital controls
  let capitalStateFilter = $state('');
  let dpQuery = $state('');
  let locQuery = $state('');
  let locSuggestions: { name: string; sub: string; lat: number; lon: number }[] = $state([]);
  let showLocSugg = $state(false);

  // Layer visibility (capital)
  let showCDSL = $state(true);
  let showNSDL = $state(true);
  let showMFDI = $state(true);
  let showMFDC = $state(true);
  let dpscOpen = $state(true);
  let mfdOpen = $state(true);

  // Outlet toggle (banking)
  let outletsEnabled = $state(false);
  let showBranch = $state(true);
  let showBC = $state(true);
  let showCSP = $state(true);

  // Stats
  let statsBankingHTML = $state('Select Banking Access to view FI data');
  let statsCapitalHTML = $state('Loading\u2026');
  let showResetBanking = $state(false);
  let showResetCapital = $state(false);

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
  ];

  // Geocoder debounce
  let locTimer: ReturnType<typeof setTimeout> | null = null;

  // ── Handlers ──

  function handleModeChange(newMode: 'capital' | 'banking') {
    mode = newMode;
    dispatchFiner('modeChange', { mode: newMode });
  }

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

  function handleCapitalViewChange(view: 'choro' | 'dots') {
    capitalView = view;
    dispatchFiner('capitalViewChange', { view });
  }

  // Capital layer toggles
  function toggleDPSCGroup() {
    dpscOpen = !dpscOpen;
    showCDSL = dpscOpen;
    showNSDL = dpscOpen;
    dispatchFiner('layerToggle', { layer: 'cdsl', visible: showCDSL });
    dispatchFiner('layerToggle', { layer: 'nsdl', visible: showNSDL });
  }

  function toggleMFDGroup() {
    mfdOpen = !mfdOpen;
    showMFDI = mfdOpen;
    showMFDC = mfdOpen;
    dispatchFiner('layerToggle', { layer: 'mfdi', visible: showMFDI });
    dispatchFiner('layerToggle', { layer: 'mfdc', visible: showMFDC });
  }

  function toggleLayer(layer: string, e: MouseEvent) {
    e.stopPropagation();
    if (layer === 'cdsl') { showCDSL = !showCDSL; dispatchFiner('layerToggle', { layer: 'cdsl', visible: showCDSL }); }
    else if (layer === 'nsdl') { showNSDL = !showNSDL; dispatchFiner('layerToggle', { layer: 'nsdl', visible: showNSDL }); }
    else if (layer === 'mfdi') { showMFDI = !showMFDI; dispatchFiner('layerToggle', { layer: 'mfdi', visible: showMFDI }); }
    else if (layer === 'mfdc') { showMFDC = !showMFDC; dispatchFiner('layerToggle', { layer: 'mfdc', visible: showMFDC }); }
  }

  // Capital search
  function handleDPSearch(e: Event) {
    dpQuery = (e.target as HTMLInputElement).value.trim().toLowerCase();
    dispatchFiner('search', { query: dpQuery });
  }

  // Capital state dropdown
  function handleCapitalStateChange(e: Event) {
    const val = (e.target as HTMLSelectElement).value;
    if (val === '_SEP') {
      (e.target as HTMLSelectElement).value = capitalStateFilter;
      return;
    }
    capitalStateFilter = val;
    dispatchFiner('stateFilterChange', { state: val });
  }

  // Geocoder
  function handleLocInput(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    locQuery = val;
    if (locTimer) clearTimeout(locTimer);
    if (val.length < 2) { showLocSugg = false; return; }
    locTimer = setTimeout(() => {
      fetch('https://photon.komoot.io/api/?q=' + encodeURIComponent(val + ' India') + '&limit=6&lang=en')
        .then(r => r.json())
        .then(data => {
          const fs = (data.features || [])
            .filter((f: any) => {
              const coords = f.geometry.coordinates;
              return coords[0] >= 68 && coords[0] <= 97 && coords[1] >= 6 && coords[1] <= 38;
            })
            .slice(0, 5);
          if (!fs.length) { showLocSugg = false; return; }
          locSuggestions = fs.map((f: any) => {
            const p = f.properties;
            const name = p.name || p.city || p.state || '';
            const sub = [p.city, p.state].filter(Boolean).join(', ');
            const coords = f.geometry.coordinates;
            return { name, sub, lat: coords[1], lon: coords[0] };
          });
          showLocSugg = true;
        })
        .catch(() => { showLocSugg = false; });
    }, 350);
  }

  function handleLocSelect(item: { name: string; lat: number; lon: number }) {
    locQuery = item.name;
    showLocSugg = false;
    dispatchFiner('flyTo', { lat: item.lat, lng: item.lon, name: item.name });
    showResetCapital = true;
  }

  function handleLocKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && locSuggestions.length > 0) {
      handleLocSelect(locSuggestions[0]);
    }
    if (e.key === 'Escape') showLocSugg = false;
  }

  // Outlet toggle
  function handleOutletToggle() {
    outletsEnabled = !outletsEnabled;
    dispatchFiner('outletToggle', { enabled: outletsEnabled });
  }

  function toggleOutletLayer(layer: string, e: MouseEvent) {
    e.stopPropagation();
    if (layer === 'branch') { showBranch = !showBranch; dispatchFiner('outletLayerToggle', { layer: 'branch', visible: showBranch }); }
    else if (layer === 'bc') { showBC = !showBC; dispatchFiner('outletLayerToggle', { layer: 'bc', visible: showBC }); }
    else if (layer === 'csp') { showCSP = !showCSP; dispatchFiner('outletLayerToggle', { layer: 'csp', visible: showCSP }); }
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
  function resetCapital() {
    dpQuery = '';
    capitalStateFilter = '';
    locQuery = '';
    showLocSugg = false;
    showCDSL = showNSDL = showMFDI = showMFDC = true;
    dpscOpen = true;
    mfdOpen = true;
    showResetCapital = false;
    capitalView = 'choro';
    drilldownActive = false;
    dispatchFiner('resetCapital', {});
  }

  function resetBanking() {
    bankingStateFilter = '';
    showResetBanking = false;
    dispatchFiner('resetBanking', {});
  }

  // Back button (capital drilldown)
  function exitDrilldown() {
    drilldownActive = false;
    dispatchFiner('exitDrilldown', {});
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
      mode = s.mode || 'banking';
      scope = s.scope || 'ne';
      capitalView = s.capitalView || 'choro';
      drilldownActive = s.drilldownActive || false;
      currentIndicator = s.indicator || 'digital_transactions';
      currentMetricIdx = s.metricIdx || 0;
      bankingStateFilter = s.stateFilter || '';
      showResetBanking = !!bankingStateFilter;
      if (s.indicators) {
        indicators = s.indicators;
        updateMetrics();
      }
      if (s.showCDSL !== undefined) showCDSL = s.showCDSL;
      if (s.showNSDL !== undefined) showNSDL = s.showNSDL;
      if (s.showMFDI !== undefined) showMFDI = s.showMFDI;
      if (s.showMFDC !== undefined) showMFDC = s.showMFDC;
      if (s.outletsEnabled !== undefined) outletsEnabled = s.outletsEnabled;
    }

    const unsubs = [
      onFiner('stateUpdate', () => {
        const st = getFinerState();
        if (!st) return;
        mode = st.mode || mode;
        scope = st.scope || scope;
        capitalView = st.capitalView || capitalView;
        drilldownActive = st.drilldownActive || false;
        if (st.indicators && Object.keys(st.indicators).length > 0) {
          indicators = st.indicators;
          updateMetrics();
        }
      }),
      onFiner('statsUpdate', () => {
        const st = getFinerState();
        if (!st) return;
        if (st.stats?.html) statsBankingHTML = st.stats.html;
        if (st.capitalStats?.html) statsCapitalHTML = st.capitalStats.html;
        showResetBanking = !!bankingStateFilter;
        showResetCapital = !!(dpQuery || capitalStateFilter || locQuery);
      }),
      onFiner('indicatorsReady', (detail: { indicators: Record<string, any> }) => {
        indicators = detail.indicators;
        updateMetrics();
      }),
      onFiner('capitalStatsUpdate', (detail: { html: string }) => {
        statsCapitalHTML = detail.html;
        showResetCapital = !!(dpQuery || capitalStateFilter || locQuery);
      }),
      onFiner('bankingStatsUpdate', (detail: { html: string; showReset: boolean }) => {
        statsBankingHTML = detail.html;
        showResetBanking = detail.showReset ?? !!bankingStateFilter;
      }),
      onFiner('drilldown', (detail: { active: boolean }) => {
        drilldownActive = detail.active;
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

    // Close location suggestions when clicking outside panel
    const handleDocClick = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('#panel')) {
        showLocSugg = false;
      }
    };
    document.addEventListener('click', handleDocClick);

    return () => {
      unsubs.forEach(fn => fn());
      document.removeEventListener('click', handleDocClick);
    };
  });
</script>

<div id="panel">
  <div id="panel-handle"><span></span></div>
  <div id="panel-head">
    <h1>Project <em>FINER</em></h1>
    <p class="panel-sub">Financial Inclusion Across India</p>
    <p class="panel-stats">800+ Districts &middot; 36 States &middot; 15 Indicators</p>
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
    <!-- Mode toggle -->
    <div class="mode-row" style="margin-bottom:10px">
      <button class="view-btn" class:active={mode === 'banking'} onclick={() => handleModeChange('banking')}>Banking Access</button>
      <button class="view-btn" class:active={mode === 'capital'} onclick={() => handleModeChange('capital')}>Capital Market Access</button>
    </div>

    <!-- Capital controls -->
    {#if mode === 'capital'}
    <div id="controls-capital">
      <div class="view-row" style="margin-bottom:10px">
        <button class="view-btn" class:active={capitalView === 'choro'} onclick={() => handleCapitalViewChange('choro')}>Access Map</button>
        <button class="view-btn" class:active={capitalView === 'dots'} onclick={() => handleCapitalViewChange('dots')}>Points</button>
      </div>

      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="grp" class:open={dpscOpen} class:dpsc-active={showCDSL || showNSDL}>
        <div class="grp-master" onclick={toggleDPSCGroup}>
          <div class="master-dot"></div>
          <span class="grp-title">DP Service Centres</span>
          <span class="grp-arrow">&#9662;</span>
        </div>
        <div class="grp-subs">
          <button class="sub-btn" class:on-cdsl={showCDSL} class:off={!showCDSL} onclick={(e) => toggleLayer('cdsl', e)}>
            <span class="sub-dot"></span>CDSL
          </button>
          <button class="sub-btn" class:on-nsdl={showNSDL} class:off={!showNSDL} onclick={(e) => toggleLayer('nsdl', e)}>
            <span class="sub-dot"></span>NSDL
          </button>
        </div>
      </div>

      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="grp" class:open={mfdOpen} class:mfd-active={showMFDI || showMFDC}>
        <div class="grp-master" onclick={toggleMFDGroup}>
          <div class="master-dot"></div>
          <span class="grp-title">MF Distributors</span>
          <span class="grp-arrow">&#9662;</span>
        </div>
        <div class="grp-subs">
          <button class="sub-btn" class:on-mfdi={showMFDI} class:off={!showMFDI} onclick={(e) => toggleLayer('mfdi', e)}>
            <span class="sub-dot"></span>Individual
          </button>
          <button class="sub-btn" class:on-mfdc={showMFDC} class:off={!showMFDC} onclick={(e) => toggleLayer('mfdc', e)}>
            <span class="sub-dot"></span>Corporate
          </button>
        </div>
      </div>

      <div style="height:1px;background:#e8e5e0;margin:10px 0"></div>

      <div class="field">
        <span class="flabel">Search</span>
        <input class="finput" type="text" id="search-dp" placeholder="Search by name\u2026" value={dpQuery} oninput={handleDPSearch} />
      </div>
      <div class="field" style="position:relative">
        <span class="flabel">Go to city</span>
        <input class="finput" type="text" id="search-loc" placeholder="e.g. Shillong, Tura\u2026" autocomplete="off"
          value={locQuery} oninput={handleLocInput} onkeydown={handleLocKeydown} />
        {#if showLocSugg && locSuggestions.length > 0}
        <div id="loc-sugg" style="display:block">
          {#each locSuggestions as item}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div class="sugg-item" onclick={() => handleLocSelect(item)}>
              <span>{item.name}</span><small>{item.sub}</small>
            </div>
          {/each}
        </div>
        {/if}
      </div>
      <div class="field">
        <span class="flabel">State</span>
        <select class="finput" id="state-select" value={capitalStateFilter} onchange={handleCapitalStateChange}>
          <option value="">All India</option>
        </select>
      </div>

      <div id="stats-capital">{@html statsCapitalHTML}</div>
      <button id="btn-reset-capital" style:display={showResetCapital ? 'block' : 'none'} onclick={resetCapital}>&#8634; Reset</button>
    </div>
    {/if}

    <!-- Banking controls -->
    {#if mode === 'banking'}
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

      <div style="height:1px;background:#e8e5e0;margin:10px 0"></div>

      <div class="outlet-toggle-row">
        <label class="outlet-toggle-label">
          <input type="checkbox" checked={outletsEnabled} onchange={handleOutletToggle} />
          <span class="outlet-toggle-slider"></span>
        </label>
        <span class="outlet-toggle-text">Show Banking Outlets</span>
      </div>
      {#if outletsEnabled}
      <div id="rbi-outlet-controls">
        <div class="grp-subs" style="margin-top:6px">
          <button class="sub-btn" class:on-branch={showBranch} class:off={!showBranch} onclick={(e) => toggleOutletLayer('branch', e)}>
            <span class="sub-dot" style="background:#2563eb"></span>Branches
          </button>
          <button class="sub-btn" class:on-bc={showBC} class:off={!showBC} onclick={(e) => toggleOutletLayer('bc', e)}>
            <span class="sub-dot" style="background:#16a34a"></span>BCs
          </button>
          <button class="sub-btn" class:on-csp={showCSP} class:off={!showCSP} onclick={(e) => toggleOutletLayer('csp', e)}>
            <span class="sub-dot" style="background:#ea580c"></span>CSPs
          </button>
        </div>
        <div id="rbi-hint" style="font-size:9px;color:#888078;padding:4px 0 0;font-family:var(--font-sans)">Zoom in to see outlet points</div>
      </div>
      {/if}

      <div id="stats-banking">{@html statsBankingHTML}</div>
      <button id="btn-reset-banking" style:display={showResetBanking ? 'block' : 'none'} onclick={resetBanking}>&#8634; Reset</button>
    </div>
    {/if}
  </div>
</div>

{#if drilldownActive}
  <button id="btn-back" style="display:block" onclick={exitDrilldown}>&larr; Back to map</button>
{/if}

<style>
  /* Panel styles are applied globally in index.astro — these are component-scoped overrides */
  /* The id="panel" CSS is in the global stylesheet since inline JS also references it */
</style>
