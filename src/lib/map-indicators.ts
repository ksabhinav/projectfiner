/**
 * Map indicator definitions for the Banking Access choropleth.
 * Shared between the homepage map (index.astro) and analysis pages.
 *
 * Each indicator has:
 * - title: display name
 * - desc: description for (i) tooltips
 * - metrics: array of { field, label, unit, desc, fallbacks? }
 */

export interface MetricDef {
  field: string;
  label: string;
  unit: '' | '₹' | '%';
  desc: string;
  fallbacks?: string[];
}

export interface IndicatorDef {
  title: string;
  desc: string;
  metrics: MetricDef[];
}

export type IndicatorKey = keyof typeof INDICATORS;

export const INDICATOR_KEYS = [
  'digital_transactions',
  'credit_deposit_ratio',
  'pmjdy',
  'branch_network',
  'kcc',
  'shg',
  'aadhaar_authentication',
  'social_security',
  'pmegp',
  'housing_pmay',
  'sui',
  'sc_st_finance',
  'women_finance',
  'education_loan',
  'pmmy_mudra_disbursement',
  'rbi_banking_outlets',
  'nfhs_health_insurance',
  'aadhaar_enrollment',
] as const;

/**
 * Cross-category fallbacks: when a field isn't found under its primary category,
 * also search these alternative categories. Different states use different category
 * names for the same data.
 */
export const CROSS_CATEGORY_FALLBACKS: Record<string, string[]> = {
  'branch_network': ['branch_network_p2', 'branch_network_p3', 'branch_network_p4'],
  'kcc': ['fi_kcc', 'kcc_animal_husbandry', 'kcc_fishery', 'kcc_fisheries', 'kcc_outstanding', 'kcc_crop',
          'kcc_2', 'kcc_animal_husbandry_2', 'kcc_fishery_2', 'kcc_outstanding_2', 'kcc_outstanding_3', 'kcc_outstanding_4',
          'fi_kcc_2', 'kcc_animal_husbandry_3', 'kcc_animal_husbandry_4'],
  'shg': ['shg_nrlm', 'nrlm', 'shg_p2', 'shg_p3', 'jlg'],
  'pmjdy': ['pmjdy_p2', 'pmjdy_p3', 'pmjdy_p4', 'social_security_schemes', 'pmjdy_2', 'pmjdy_3', 'pmjdy_4',
            'social_security_schemes_2'],
  'digital_transactions': ['digital_payments', 'digital_coverage_savings', 'digital_coverage_savings_p2',
                           'digital_coverage_business', 'digital_transactions_2', 'phonepe_upi'],
  'aadhaar_authentication': ['aadhaar_authentication_2'],
  'social_security': ['social_security_2', 'social_security_schemes', 'social_security_claims', 'apy'],
  'pmegp': ['pmegp_2'],
  'housing_pmay': ['housing_pmay_p2'],
  'sui': ['stand_up_india'],
  'sc_st_finance': ['sc_st_lending', 'weaker_section_os'],
  'women_finance': ['women_finance_2'],
  'education_loan': ['education_loan_2'],
  'pmmy_mudra_disbursement': ['pmmy_mudra_os_npa', 'mudra', 'mudra_2'],
};

/**
 * Color ramps for choropleth rendering.
 */
export const COLOR_RAMPS = {
  default: ['#faf6f0', '#f0e0c8', '#e8c89a', '#d4a06a', '#b8603e', '#8a3a1a'],
  green:   ['#f0f7f0', '#c8e6c8', '#88cc88', '#44aa44', '#228822', '#006600'],
  blue:    ['#f0f4fa', '#c8d8f0', '#88b0e0', '#4488cc', '#2266aa', '#004488'],
};

/**
 * State codes for GeoJSON matching.
 */
export const STATE_NAME_TO_CODE: Record<string, string> = {
  'ANDHRA PRADESH': 'AP', 'ARUNACHAL PRADESH': 'AR', 'ASSAM': 'AS', 'BIHAR': 'BR',
  'CHHATTISGARH': 'CT', 'GOA': 'GA', 'GUJARAT': 'GJ', 'HARYANA': 'HR',
  'HIMACHAL PRADESH': 'HP', 'JHARKHAND': 'JH', 'KARNATAKA': 'KA', 'KERALA': 'KL',
  'MADHYA PRADESH': 'MP', 'MAHARASHTRA': 'MH', 'MANIPUR': 'MN', 'MEGHALAYA': 'ML',
  'MIZORAM': 'MZ', 'NAGALAND': 'NL', 'ODISHA': 'OR', 'PUNJAB': 'PB',
  'RAJASTHAN': 'RJ', 'SIKKIM': 'SK', 'TAMIL NADU': 'TN', 'TELANGANA': 'TS',
  'TRIPURA': 'TR', 'UTTAR PRADESH': 'UP', 'UTTARAKHAND': 'UK', 'WEST BENGAL': 'WB',
  'JAMMU AND KASHMIR': 'JK', 'LADAKH': 'JK', 'DELHI': 'DL', 'CHANDIGARH': 'CH',
  'PUDUCHERRY': 'PY', 'ANDAMAN & NICOBAR': 'AN', 'LAKSHADWEEP': 'LD',
  'DADRA & NAGAR HAVELI & DAMAN & DIU': 'DN',
};

/**
 * Map bounds constants.
 */
export const MAP_BOUNDS = {
  india: { south: 2, west: 62, north: 40, east: 112 },
  indiaMobile: { south: 0, west: 60, north: 45, east: 112 },
  allStates: { south: 8, west: 68, north: 31, east: 97.5 },
  neFocus: { south: 21.5, west: 88, north: 29.5, east: 97.5 },
};

/**
 * NE state codes for Focus NE mode.
 */
export const NE_CODES = ['AS', 'ML', 'MN', 'MZ', 'NL', 'TR', 'AR', 'SK'];
