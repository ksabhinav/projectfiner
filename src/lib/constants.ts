export const COLORS = {
  accent: '#b8603e',
  accentDark: '#8a4a2e',
  teal: '#3d7a8e',
  olive: '#5a7a3a',
  gold: '#8b6914',
  text: '#1a1410',
  muted: '#888078',
  label: '#aaa09a',
  bg: '#f5f4f1',
  border: '#e8e5e0',
} as const;

export const CAPITAL_MARKETS_SOURCES = {
  cdsl: {
    url: 'DPSCs/cdsl_dp_centres.json',
    filename: 'cdsl_dp_service_centres',
    headers: ['Name', 'Address', 'DP ID', 'Pincode', 'Email', 'Website', 'State', 'City'],
    keys: ['n', 'a', 'id', 'p', 'e', 'u', 'st', 'loc'],
  },
  nsdl: {
    url: 'DPSCs/nsdl_dp_centres.json',
    filename: 'nsdl_dp_service_centres',
    headers: ['Name', 'Address', 'DP ID', 'Pincode', 'Email', 'Website', 'Type', 'State', 'City'],
    keys: ['n', 'a', 'id', 'p', 'e', 'u', 't', 'st', 'loc'],
  },
  mfdi: {
    url: 'MFDs/mfd_individual.json',
    filename: 'mfd_individual',
    headers: ['Name', 'ARN', 'Pincode', 'State', 'Location', 'City'],
    keys: ['n', 'arn', 'p', 'st', 'loc', 'c'],
  },
  mfdc: {
    url: 'MFDs/mfd_corporate.json',
    filename: 'mfd_corporate',
    headers: ['Name', 'ARN', 'Pincode', 'State', 'Location', 'City'],
    keys: ['n', 'arn', 'p', 'st', 'loc', 'c'],
  },
} as const;

export const FILE_ICON_SVG = '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 18H7v-2h6v2zm4-4H7v-2h10v2zm0-4H7V10h10v2zM13 9V3.5L18.5 9H13z"/></svg>';
