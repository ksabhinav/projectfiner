/**
 * Bridge between Svelte components and the Leaflet inline JS on the homepage.
 *
 * Svelte components dispatch events via dispatchFiner().
 * Inline JS listens via window.addEventListener().
 * Inline JS updates window.__FINER state and dispatches events back.
 * Svelte reads initial state from window.__FINER in onMount().
 */

// ── Event helpers ──

export function dispatchFiner(name: string, detail: any = {}) {
  window.dispatchEvent(new CustomEvent('finer:' + name, { detail }));
}

export function onFiner(name: string, callback: (detail: any) => void): () => void {
  const handler = (e: Event) => callback((e as CustomEvent).detail);
  window.addEventListener('finer:' + name, handler);
  return () => window.removeEventListener('finer:' + name, handler);
}

// ── Shared state (owned by inline JS, read by Svelte) ──

export interface FinerState {
  // Current selections
  mode: 'capital' | 'banking';
  scope: 'india' | 'ne';
  indicator: string;
  metricIdx: number;
  quarter: string;
  stateFilter: string;

  // Timeline
  sortedQuarters: string[];

  // Stats (updated after choropleth rebuild)
  stats: {
    total: number;
    withData: number;
    avg: string;
    min: string;
    max: string;
    indicatorTitle: string;
    metricLabel: string;
    unit: string;
  };
  capitalStats: {
    cdsl: number;
    nsdl: number;
    mfdi: number;
    mfdc: number;
    total: number;
    drilldownDistrict: string;
  };

  // Legend
  legendData: {
    title: string;
    breaks: number[];
    ramp: string[];
    unit: string;
  };

  // Focus mode
  focus: {
    active: boolean;
    district: string;
    state: string;
    svgPath: string;
    svgViewBox: string;
    fillColor: string;
    strokeColor: string;
    metricLabel: string;
    value: string;
    quarter: string;
  };

  // Layer visibility
  showCDSL: boolean;
  showNSDL: boolean;
  showMFDI: boolean;
  showMFDC: boolean;
  outletsEnabled: boolean;
  showBranch: boolean;
  showBC: boolean;
  showCSP: boolean;
  capitalView: 'choro' | 'dots';
  drilldownActive: boolean;

  // Indicator definitions (for dropdowns)
  indicators: Record<string, any>;
  manifest: { indicators: string[]; quarters: string[]; latest_quarter: string } | null;
}

export function getFinerState(): FinerState | null {
  return (window as any).__FINER || null;
}

// ── Event detail types ──

export interface ModeChangeDetail { mode: 'capital' | 'banking' }
export interface ScopeChangeDetail { scope: 'india' | 'ne' }
export interface IndicatorChangeDetail { indicator: string; metricIdx: number }
export interface QuarterChangeDetail { quarter: string; idx: number }
export interface StateFilterDetail { state: string }
export interface ViewChangeDetail { view: 'choro' | 'dots' }
export interface LayerToggleDetail { layer: string; visible: boolean }
export interface OutletToggleDetail { enabled: boolean }
export interface SearchDetail { query: string }
export interface FlyToDetail { lat: number; lng: number; name?: string }
export interface LegendUpdateDetail { title: string; breaks: number[]; ramp: string[]; unit: string }
export interface StatsUpdateDetail { banking?: any; capital?: any }
export interface FocusUpdateDetail {
  active: boolean;
  district: string;
  state: string;
  svgPath: string;
  svgViewBox: string;
  fillColor: string;
  strokeColor: string;
  metricLabel: string;
  value: string;
  quarter: string;
}
export interface QuartersReadyDetail { quarters: string[] }
export interface DrilldownDetail { district: string; state: string }
