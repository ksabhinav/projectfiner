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
  'facebook_rwi',
  'pmgsy_roads',
  'viirs_nightlights',
  'elevation_terrain',
  'crop_production',
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


/* ==========================================================================
   Atlas identity catalog (used by IndicatorStrip + IndicatorPicker)
   ========================================================================== */

export type AtlasCategory =
  | 'banking' | 'credit' | 'schemes' | 'digital' | 'capital-markets' | 'demographics' | 'insurance';

export type AtlasSubgroup = 'headline' | 'inclusion' | 'scheme';

export type AtlasRamp = 'vermillion' | 'sage' | 'peacock' | 'saffron' | 'burgundy';

export interface AtlasIndicator {
  /**
   * Unique Atlas picker id. Usually matches public/indicators/{key}/, but can
   * be a synthetic id (e.g. `capital_markets_mfdi`) when one underlying
   * indicator is split into multiple picker entries by metricIdx.
   */
  key: string;
  /**
   * Underlying indicator key (matches public/indicators/{indicatorKey}/).
   * Defaults to `key` when omitted.
   */
  indicatorKey?: string;
  /** Metric index within the underlying indicator. Defaults to 0. */
  metricIdx?: number;
  /** Display name (Fraunces) */
  name: string;
  /** Short unit suffix (% / ₹ L / no.) */
  units: string;
  /** Picker tab */
  category: AtlasCategory;
  /** Picker subgroup within tab */
  subgroup: AtlasSubgroup;
  /** Atlas ramp family */
  rampKey: AtlasRamp;
}

export const ATLAS_CATEGORIES: { id: AtlasCategory; label: string }[] = [
  { id: 'banking',         label: 'Banking Infra' },
  { id: 'credit',          label: 'Credit' },
  { id: 'schemes',         label: 'Schemes' },
  { id: 'digital',         label: 'Payments' },
  { id: 'insurance',       label: 'Insurance' },
  { id: 'capital-markets', label: 'Capital markets' },
  { id: 'demographics',    label: 'Demographics' },
];

export const ATLAS_SUBGROUPS: { id: AtlasSubgroup; label: string }[] = [
  { id: 'headline',  label: 'Headline' },
  { id: 'inclusion', label: 'Inclusion lending' },
  { id: 'scheme',    label: 'Schemes' },
];

/**
 * Keys match the existing public/indicators/{key}/ directories AND the keys
 * used in src/pages/index.astro's INDICATORS object. Names mirror the
 * canonical titles from index.astro — DO NOT rename (the picker, legend,
 * and tooltip all surface these strings).
 *
 * For multi-metric indicators, the headline keeps the bare key and metricIdx 0.
 * Sub-metric entries use a synthetic key + indicatorKey + metricIdx pointer.
 */
export const ATLAS_INDICATORS: AtlasIndicator[] = [
  // ===== Banking ==========================================================
  // Branch Network (SLBC, quarterly time-series, ~300 districts coverage)
  { key: 'branch_network',                name: 'Branch Network',                units: 'no.',  category: 'banking', subgroup: 'headline',  rampKey: 'vermillion' },
  // RBI snapshot: comprehensive (700+ districts) but no time-series — ATM not
  // available here (RBI Banking Outlet Locator covers branches/BC/CSP/offices).
  // For ATM/CSP time-series, the SLBC branch_network indicator is the source
  // but coverage is sparser (~55%); kept under the headline rather than a
  // separate picker pick.
  { key: 'rbi_banking_outlets',           name: 'Banking Infrastructure (RBI · snapshot)',           units: 'no.',  category: 'banking', subgroup: 'headline',  rampKey: 'vermillion' },
  { key: 'rbi_branches',                  indicatorKey: 'rbi_banking_outlets', metricIdx: 1, name: 'Bank Branches (RBI · snapshot)',         units: 'no.', category: 'banking', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'rbi_bc',                        indicatorKey: 'rbi_banking_outlets', metricIdx: 2, name: 'Business Correspondents (RBI · snapshot)', units: 'no.', category: 'banking', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'rbi_csp',                       indicatorKey: 'rbi_banking_outlets', metricIdx: 3, name: 'CSPs (RBI · snapshot)',                  units: 'no.', category: 'banking', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'rbi_rural',                     indicatorKey: 'rbi_banking_outlets', metricIdx: 4, name: 'Rural Outlets (RBI · snapshot)',         units: 'no.', category: 'banking', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'aadhaar_authentication',        name: 'Aadhaar Authentication',        units: 'no.',  category: 'banking', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'aadhaar_authentication_used',   indicatorKey: 'aadhaar_authentication',  metricIdx: 2, name: 'Aadhaar Authenticated CASA',    units: 'no.', category: 'banking', subgroup: 'inclusion', rampKey: 'vermillion' },

  // ===== Credit ===========================================================
  // Credit-Deposit Ratio
  { key: 'credit_deposit_ratio',          name: 'Credit-Deposit Ratio',          units: '%',    category: 'credit', subgroup: 'headline',  rampKey: 'sage' },
  { key: 'cd_total_deposits',             indicatorKey: 'credit_deposit_ratio',    metricIdx: 1, name: 'Total Deposits',                units: '₹ L', category: 'credit', subgroup: 'headline',  rampKey: 'sage' },
  { key: 'cd_total_advances',             indicatorKey: 'credit_deposit_ratio',    metricIdx: 2, name: 'Total Advances',                units: '₹ L', category: 'credit', subgroup: 'headline',  rampKey: 'vermillion' },

  // RBI BSR-1
  { key: 'rbi_bsr_credit',                name: 'Bank Credit Accounts (BSR-1)',  units: 'no.',  category: 'credit', subgroup: 'headline',  rampKey: 'vermillion' },
  { key: 'bsr_credit_outstanding',        indicatorKey: 'rbi_bsr_credit',          metricIdx: 1, name: 'Bank Credit Outstanding (BSR-1)', units: '₹ L', category: 'credit', subgroup: 'headline', rampKey: 'vermillion' },
  { key: 'bsr_agri_accounts',             indicatorKey: 'rbi_bsr_credit',          metricIdx: 2, name: 'Agriculture Credit Accounts',   units: 'no.', category: 'credit', subgroup: 'headline',  rampKey: 'vermillion' },
  { key: 'bsr_personal_loans',            indicatorKey: 'rbi_bsr_credit',          metricIdx: 3, name: 'Personal Loan Accounts',        units: 'no.', category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'bsr_rural_credit',              indicatorKey: 'rbi_bsr_credit',          metricIdx: 4, name: 'Rural Credit Accounts',         units: 'no.', category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },

  // KCC
  { key: 'kcc',                           name: 'Kisan Credit Card',             units: 'no.',  category: 'credit', subgroup: 'headline',  rampKey: 'vermillion' },
  { key: 'kcc_outstanding_amt',           indicatorKey: 'kcc',                     metricIdx: 1, name: 'KCC Outstanding Amount',        units: '₹ L', category: 'credit', subgroup: 'headline',  rampKey: 'vermillion' },
  { key: 'kcc_activated',                 indicatorKey: 'kcc',                     metricIdx: 3, name: 'KCC Cards Activated',           units: 'no.', category: 'credit', subgroup: 'headline',  rampKey: 'vermillion' },

  // SC/ST Lending — split SC and ST
  { key: 'sc_st_finance',                 indicatorKey: 'sc_st_finance',           metricIdx: 0, name: 'SC Lending (Disbursed)',        units: 'no.', category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'sc_disbursement_amt',           indicatorKey: 'sc_st_finance',           metricIdx: 1, name: 'SC Lending (Amount)',           units: '₹ L', category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'st_lending_no',                 indicatorKey: 'sc_st_finance',           metricIdx: 2, name: 'ST Lending (Disbursed)',        units: 'no.', category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'st_lending_amt',                indicatorKey: 'sc_st_finance',           metricIdx: 3, name: 'ST Lending (Amount)',           units: '₹ L', category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },

  // Women's Credit
  { key: 'women_finance',                 name: "Women's Credit (Outstanding)",  units: 'no.',  category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'women_finance_amt',             indicatorKey: 'women_finance',           metricIdx: 1, name: "Women's Credit (Amount)",       units: '₹ L', category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },

  // Education Loans
  { key: 'education_loan',                name: 'Education Loans (Sanctioned)',  units: 'no.',  category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'education_loan_amt',            indicatorKey: 'education_loan',          metricIdx: 1, name: 'Education Loans (Amount)',      units: '₹ L', category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },
  { key: 'education_loan_girl',           indicatorKey: 'education_loan',          metricIdx: 2, name: 'Education Loans (Girl Students)', units: 'no.', category: 'credit', subgroup: 'inclusion', rampKey: 'vermillion' },

  // SHG
  { key: 'shg',                           name: 'SHG (Savings Linked)',          units: 'no.',  category: 'credit', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'shg_credit_linked',             indicatorKey: 'shg',                     metricIdx: 1, name: 'SHG (Credit Linked)',           units: 'no.', category: 'credit', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'shg_outstanding_amt',           indicatorKey: 'shg',                     metricIdx: 2, name: 'SHG Outstanding Amount',        units: '₹ L', category: 'credit', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'nrlm_shg',                      name: 'NRLM SHGs (Total)',             units: 'no.',  category: 'credit', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'nrlm_members',                  indicatorKey: 'nrlm_shg',                metricIdx: 1, name: 'NRLM SHG Members',              units: 'no.', category: 'credit', subgroup: 'scheme',    rampKey: 'saffron' },

  // MUDRA
  { key: 'pmmy_mudra_disbursement',       indicatorKey: 'pmmy_mudra_disbursement', metricIdx: 6, name: 'MUDRA / PMMY (Total)',          units: 'no.', category: 'credit', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'mudra_total_amt',               indicatorKey: 'pmmy_mudra_disbursement', metricIdx: 7, name: 'MUDRA / PMMY (Amount)',         units: '₹ L', category: 'credit', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'mudra_shishu',                  indicatorKey: 'pmmy_mudra_disbursement', metricIdx: 0, name: 'MUDRA Shishu (≤ ₹50K)',         units: 'no.', category: 'credit', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'mudra_kishore',                 indicatorKey: 'pmmy_mudra_disbursement', metricIdx: 2, name: 'MUDRA Kishore (₹50K–5L)',       units: 'no.', category: 'credit', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'mudra_tarun',                   indicatorKey: 'pmmy_mudra_disbursement', metricIdx: 4, name: 'MUDRA Tarun (₹5–20L)',          units: 'no.', category: 'credit', subgroup: 'scheme',    rampKey: 'saffron' },

  // ===== Schemes ==========================================================
  { key: 'pmjdy',                         name: 'PM Jan Dhan Yojana',            units: 'no.',  category: 'schemes', subgroup: 'headline',  rampKey: 'vermillion' },
  { key: 'pmjdy_zero_balance',            indicatorKey: 'pmjdy',                   metricIdx: 1, name: 'PMJDY Zero-Balance Accounts',   units: 'no.', category: 'schemes', subgroup: 'headline',  rampKey: 'vermillion' },
  { key: 'pmjdy_female',                  indicatorKey: 'pmjdy',                   metricIdx: 4, name: 'PMJDY Female Accounts',         units: 'no.', category: 'schemes', subgroup: 'headline',  rampKey: 'vermillion' },
  { key: 'pmjdy_rural',                   indicatorKey: 'pmjdy',                   metricIdx: 5, name: 'PMJDY Rural Accounts',          units: 'no.', category: 'schemes', subgroup: 'headline',  rampKey: 'vermillion' },

  { key: 'social_security',               indicatorKey: 'social_security',         metricIdx: 3, name: 'Social Security (Total)',       units: 'no.', category: 'schemes', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'social_pmsby',                  indicatorKey: 'social_security',         metricIdx: 0, name: 'PMSBY (Accident Insurance)',    units: 'no.', category: 'insurance', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'social_pmjjby',                 indicatorKey: 'social_security',         metricIdx: 1, name: 'PMJJBY (Life Insurance)',       units: 'no.', category: 'insurance', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'social_apy',                    indicatorKey: 'social_security',         metricIdx: 2, name: 'APY (Atal Pension)',            units: 'no.', category: 'schemes', subgroup: 'scheme',    rampKey: 'saffron' },

  { key: 'housing_pmay',                  name: 'Rural Housing Loans',           units: 'no.',  category: 'schemes', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'pmay_loans',                    indicatorKey: 'housing_pmay',            metricIdx: 2, name: 'PMAY Loans',                    units: 'no.', category: 'schemes', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'pmegp',                         name: 'PMEGP (Disbursed)',             units: 'no.',  category: 'schemes', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'pmegp_amt',                     indicatorKey: 'pmegp',                   metricIdx: 1, name: 'PMEGP (Amount)',                units: '₹ L', category: 'schemes', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'sui',                           name: 'Stand Up India (Women)',        units: 'no.',  category: 'schemes', subgroup: 'scheme',    rampKey: 'saffron' },
  { key: 'sui_outstanding_amt',           indicatorKey: 'sui',                     metricIdx: 2, name: 'Stand Up India (Amount)',       units: '₹ L', category: 'schemes', subgroup: 'scheme',    rampKey: 'saffron' },

  // ===== Digital ==========================================================
  { key: 'digital_transactions',          name: 'UPI Transactions (PhonePe)',    units: 'no.',  category: 'digital', subgroup: 'headline',  rampKey: 'vermillion' },
  { key: 'upi_transaction_amount',        indicatorKey: 'digital_transactions',    metricIdx: 1, name: 'UPI Amount (PhonePe)',           units: '₹ L', category: 'digital', subgroup: 'headline',  rampKey: 'vermillion' },
  { key: 'sb_digital_coverage',           indicatorKey: 'digital_transactions',    metricIdx: 2, name: 'SB Digital Coverage',            units: '%',   category: 'digital', subgroup: 'inclusion', rampKey: 'peacock' },

  // ===== Capital markets ==================================================
  { key: 'capital_markets_access',        indicatorKey: 'capital_markets_access',  metricIdx: 0, name: 'Capital Markets Access (Total)', units: 'no.', category: 'capital-markets', subgroup: 'headline',  rampKey: 'peacock' },
  { key: 'capital_markets_cdsl',          indicatorKey: 'capital_markets_access',  metricIdx: 1, name: 'CDSL Service Centres',          units: 'no.', category: 'capital-markets', subgroup: 'inclusion', rampKey: 'peacock' },
  { key: 'capital_markets_nsdl',          indicatorKey: 'capital_markets_access',  metricIdx: 2, name: 'NSDL Service Centres',          units: 'no.', category: 'capital-markets', subgroup: 'inclusion', rampKey: 'peacock' },
  { key: 'capital_markets_mfdi',          indicatorKey: 'capital_markets_access',  metricIdx: 3, name: 'MF Distributors (Individual)',  units: 'no.', category: 'capital-markets', subgroup: 'inclusion', rampKey: 'peacock' },
  { key: 'capital_markets_mfdc',          indicatorKey: 'capital_markets_access',  metricIdx: 4, name: 'MF Distributors (Corporate)',   units: 'no.', category: 'capital-markets', subgroup: 'inclusion', rampKey: 'peacock' },

  // ===== Demographics =====================================================
  { key: 'nfhs_health_insurance',         name: 'Health Insurance (NFHS)',       units: '%',    category: 'insurance', subgroup: 'headline', rampKey: 'sage' },
  { key: 'aadhaar_enrollment',            name: 'Aadhaar Enrolment (UIDAI)',     units: 'no.',  category: 'demographics', subgroup: 'headline', rampKey: 'vermillion' },
  { key: 'facebook_rwi',                  name: 'Relative Wealth Index (Meta)',  units: 'idx',  category: 'demographics', subgroup: 'headline', rampKey: 'sage' },
  { key: 'pmgsy_roads',                   name: 'PMGSY Rural Roads',             units: 'no.',  category: 'demographics', subgroup: 'headline', rampKey: 'saffron' },
  { key: 'viirs_nightlights',             name: 'Nightlights (VIIRS)',           units: 'idx',  category: 'demographics', subgroup: 'headline', rampKey: 'saffron' },
  { key: 'elevation_terrain',             name: 'Elevation & Ruggedness (SRTM)', units: 'm',    category: 'demographics', subgroup: 'headline', rampKey: 'peacock' },
  { key: 'crop_production',               name: 'Agricultural Land & Irrigation (Census)', units: 'ha', category: 'credit', subgroup: 'inclusion', rampKey: 'sage' },
  { key: 'crop_irrigation_pct',           indicatorKey: 'crop_production', metricIdx: 2, name: 'Irrigation Coverage (Census)', units: '%', category: 'credit', subgroup: 'inclusion', rampKey: 'sage' },
];

export function atlasIndicatorByKey(key: string): AtlasIndicator | undefined {
  return ATLAS_INDICATORS.find(i => i.key === key);
}

export function atlasIndicatorsByCategory(cat: AtlasCategory): AtlasIndicator[] {
  return ATLAS_INDICATORS.filter(i => i.category === cat);
}

export function atlasRampGradient(key: AtlasRamp): string {
  switch (key) {
    case 'vermillion': return 'linear-gradient(90deg, #F4E1D6 0%, #E0A88E 50%, #B84A2E 100%)';
    case 'sage':       return 'linear-gradient(90deg, #E8E8DC 0%, #B8C4A0 50%, #5E7A4A 100%)';
    case 'peacock':    return 'linear-gradient(90deg, #D4DCE0 0%, #8AAEC0 50%, #1E4960 100%)';
    case 'saffron':    return 'linear-gradient(90deg, #F8E8C4 0%, #E0C684 50%, #D4A24A 100%)';
    case 'burgundy':   return 'linear-gradient(90deg, #E8D8D4 0%, #C4928A 50%, #8C2E20 100%)';
  }
}

export function atlasRampStops(key: AtlasRamp): string[] {
  switch (key) {
    case 'vermillion': return ['#F4E1D6', '#E0A88E', '#B84A2E'];
    case 'sage':       return ['#E8E8DC', '#B8C4A0', '#5E7A4A'];
    case 'peacock':    return ['#D4DCE0', '#8AAEC0', '#1E4960'];
    case 'saffron':    return ['#F8E8C4', '#E0C684', '#D4A24A'];
    case 'burgundy':   return ['#E8D8D4', '#C4928A', '#8C2E20'];
  }
}
