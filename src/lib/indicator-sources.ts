// Per-indicator source citations for the choropleth legend.
//
// Returns a short citation string + optional URL for the currently displayed
// indicator, quarter and state filter. The legend renders this inline so a
// reader can see exactly where a particular district number came from.
//
// For SLBC indicators the citation varies by state (each state's SLBC has its
// own portal/PDF source). For pan-India sources (RBI DBIE, NRLM MIS, PhonePe
// Pulse, NFHS, SHRUG, UIDAI) the citation is fixed.

export interface SourceCitation {
  /** Short one-line label, e.g. "SLBC Bihar · Sep 2025" */
  label: string;
  /** Optional URL to the canonical source (state SLBC portal, dataset page, etc.) */
  url?: string;
  /** Longer attribution when no URL fits, e.g. SHRUG citations */
  attribution?: string;
}

// ── SLBC per-state portals (booklets, agendas, online data) ────────────────
// Where two URLs are listed in CLAUDE.md (online portal + PDF), we link the
// primary published-data source. NE-portal states show the online portal.
const SLBC_STATE_URLS: Record<string, { name: string; url: string }> = {
  'andhra-pradesh':     { name: 'Andhra Pradesh',  url: 'https://web.archive.org/web/2025*/slbcap.nic.in' },
  'arunachal-pradesh':  { name: 'Arunachal Pradesh', url: 'https://onlineslbcne.nic.in' },
  'assam':              { name: 'Assam',           url: 'https://onlineslbcne.nic.in' },
  'bihar':              { name: 'Bihar',           url: 'https://www.slbcbihar.com/SlBCHeldMeeting.aspx' },
  'chhattisgarh':       { name: 'Chhattisgarh',    url: 'https://slbcchhattisgarh.com' }, // Dedicated SLBC CG site, Excel data-tables per meeting
  'gujarat':            { name: 'Gujarat',         url: 'https://slbcgujarat.in' },
  'haryana':            { name: 'Haryana',         url: 'https://slbcharyana.pnb.bank.in' },
  'jharkhand':          { name: 'Jharkhand',       url: 'https://onlineslbcne.nic.in' },
  'karnataka':          { name: 'Karnataka',       url: 'https://slbckarnataka.com' },
  'kerala':             { name: 'Kerala',          url: 'https://slbckerala.com' },
  'madhya-pradesh':     { name: 'Madhya Pradesh',  url: 'https://www.slbcmadhyapradesh.in/slbc-meeting.aspx' },
  'maharashtra':        { name: 'Maharashtra',     url: 'https://bankofmaharashtra.bank.in' },
  'manipur':            { name: 'Manipur',         url: 'https://onlineslbcne.nic.in' },
  'meghalaya':          { name: 'Meghalaya',       url: 'https://onlineslbcne.nic.in' },
  'mizoram':            { name: 'Mizoram',         url: 'https://onlineslbcne.nic.in' },
  'nagaland':           { name: 'Nagaland',        url: 'https://onlineslbcne.nic.in' },
  'odisha':             { name: 'Odisha',          url: 'https://onlineslbcne.nic.in' }, // sourced through NE-style extraction
  'rajasthan':          { name: 'Rajasthan',       url: 'https://slbcrajasthan.in' },
  'sikkim':             { name: 'Sikkim',          url: 'https://onlineslbcne.nic.in' },
  'tamil-nadu':         { name: 'Tamil Nadu',      url: 'https://slbctn.com' },
  'telangana':          { name: 'Telangana',       url: 'https://telanganaslbc.com' },
  'tripura':            { name: 'Tripura',         url: 'https://slbctripura.pnb.bank.in/Back_Paper_Quarterly.asp' },
  'uttarakhand':        { name: 'Uttarakhand',     url: 'https://slbcuttarakhand.com' },
  'west-bengal':        { name: 'West Bengal',     url: 'https://slbcwb.com' },
  'uttar-pradesh':      { name: 'Uttar Pradesh',   url: 'https://slbcup.com' },
};

// All indicators served from SLBC quarterly extraction
const SLBC_INDICATORS = new Set<string>([
  'credit_deposit_ratio', 'pmjdy', 'branch_network', 'kcc', 'shg',
  'aadhaar_authentication', 'social_security', 'pmegp', 'housing_pmay',
  'sui', 'sc_st_finance', 'women_finance', 'education_loan',
  'pmmy_mudra_disbursement',
]);

// "March 2025" style label from "2025-03"
function quarterLabel(q: string): string {
  if (!q || !/^\d{4}-\d{2}$/.test(q)) return q || '';
  const months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const [y, m] = q.split('-');
  return `${months[parseInt(m, 10)] || m} ${y}`;
}

function titleCaseState(slug: string): string {
  return slug.split('-').map(w => w[0].toUpperCase() + w.slice(1)).join(' ');
}

// ── Public API ─────────────────────────────────────────────────────────────

/**
 * Return the source citation for the currently-displayed choropleth view.
 *
 * @param indicator  indicator key (e.g. "credit_deposit_ratio")
 * @param quarter    quarter code "YYYY-MM" (or empty for static indicators)
 * @param stateFilter  state focus slug ("rajasthan", "tamil-nadu", …) or ""
 *                     for the All-India view
 */
export function getSourceCitation(
  indicator: string,
  quarter: string,
  stateFilter: string,
): SourceCitation {
  const q = quarterLabel(quarter);

  // ── PhonePe (digital_transactions has PhonePe UPI as default metric) ────
  // PhonePe Pulse currently publishes through Mar 2024. Later quarters fall
  // back automatically; the legend's quarter label will already reflect that
  // via the existing fallbackQuarter mechanism.
  if (indicator === 'digital_transactions') {
    return {
      label: `PhonePe Pulse · ${q || 'quarterly UPI'}`,
      url: 'https://github.com/PhonePe/pulse',
      attribution: 'PhonePe Pulse, district-level UPI transaction data (MIT License). Currently available through Q4 FY24 (Mar 2024); later quarters await an upstream PhonePe Pulse release.',
    };
  }

  // ── SLBC indicators ────────────────────────────────────────────────────
  if (SLBC_INDICATORS.has(indicator)) {
    if (stateFilter) {
      const slug = stateFilter.toLowerCase().replace(/\s+/g, '-');
      const src = SLBC_STATE_URLS[slug];
      if (src) {
        return {
          label: `SLBC ${src.name} · ${q}`,
          url: src.url,
        };
      }
      // Unknown state – fallback
      return {
        label: `SLBC ${titleCaseState(slug)} · ${q}`,
      };
    }
    // All-India SLBC view
    return {
      label: `SLBC quarterly booklets · ${q}`,
      attribution: 'Aggregated district-level data from State Level Bankers\' Committee booklets across 25 states (including Madhya Pradesh and Uttar Pradesh). Use the state-focus toggle to see a specific state\'s URL.',
    };
  }

  // ── Static / pan-India indicators ──────────────────────────────────────
  switch (indicator) {
    case 'rbi_banking_outlets':
      return {
        label: 'RBI DBIE Banking Outlet & ATM Locator',
        url: 'https://data.rbi.org.in/CIMS_Gateway_DBIE/GATEWAY/SERVICES/dbie_getBankGetData',
        attribution: 'Reserve Bank of India, Database on Indian Economy (DBIE) Banking Outlet & ATM Locator API. 2,472,495 outlets across 35 states, downloaded May 2026.',
      };

    case 'capital_markets_access':
      return {
        label: 'CDSL + NSDL DP centres + AMFI MFD lists',
        attribution: 'CDSL Depository Participant service centres (20,612), NSDL DP centres (57,005), AMFI Mutual Fund Distributor lists — Individual (187,254) and Corporate (10,760). Scraped May 2025.',
      };

    case 'nrlm_shg':
      return {
        label: 'DAY-NRLM MIS',
        url: 'https://nrlm.gov.in',
        attribution: 'Deendayal Antyodaya Yojana — National Rural Livelihoods Mission MIS, district-level SHG snapshot. Ministry of Rural Development.',
      };

    case 'nfhs_health_insurance':
      return {
        label: `NFHS-${quarter === '2016-03' ? '4' : '5'} district factsheets`,
        url: 'https://rchiips.org/nfhs/factsheet_NFHS-5.shtml',
        attribution: 'National Family Health Survey, IIPS Mumbai & Ministry of Health & Family Welfare. NFHS-5 (2019–21) and NFHS-4 (2015–16). Households with health-insurance member.',
      };

    case 'aadhaar_enrollment':
      return {
        label: `UIDAI district enrolments · ${q}`,
        url: 'https://uidai.gov.in',
        attribution: 'Unique Identification Authority of India, Aadhaar Enrolment Hackathon 2026 dataset. District × age-group × pincode × month, April–December 2025.',
      };

    case 'facebook_rwi':
      return {
        label: 'Meta Relative Wealth Index 2021 (CC BY-NC-SA, via SHRUG v2.1)',
        url: 'https://devdatalab.org/shrug',
        attribution: 'Chi, G., Fang, H., Chatterjee, S., & Blumenstock, J. E. (2022). Microestimates of wealth for all low- and middle-income countries. PNAS 119(3). District aggregation via SHRUG v2.1 (Asher, Lunt, Matsuura, Novosad — Development Data Lab). Licence: CC BY-NC-SA 4.0.',
      };

    case 'viirs_nightlights':
      return {
        label: `VIIRS DNB nightlights · ${q.split(' ')[1] || quarter} (EOG/NOAA, via SHRUG v2.1)`,
        url: 'https://eogdata.mines.edu/products/vnl/',
        attribution: 'Earth Observation Group, Payne Institute for Public Policy, Colorado School of Mines / NOAA VIIRS Day–Night Band annual composites (median-masked). District aggregation via SHRUG v2.1 (Asher, Lunt, Matsuura, Novosad — Development Data Lab). Licence: CC BY-NC-SA 4.0.',
      };

    case 'pmgsy_roads':
      return {
        label: 'PMGSY rural roads through 2015 (MoRD, via SHRUG v2.1)',
        url: 'https://omms.nic.in/',
        attribution: 'Pradhan Mantri Gram Sadak Yojana — Online Management, Monitoring and Accounting System (OMMAS), Ministry of Rural Development. Cumulative through 2015. District aggregation via SHRUG v2.1 (Asher, Lunt, Matsuura, Novosad — Development Data Lab). Licence: CC BY-NC-SA 4.0.',
      };

    case 'elevation_terrain':
      return {
        label: 'SRTM elevation, Feb 2000 (NASA, via SHRUG v2.1)',
        url: 'https://www2.jpl.nasa.gov/srtm/',
        attribution: 'NASA Shuttle Radar Topography Mission (SRTM) 30 m DEM, captured February 2000. District aggregation via SHRUG v2.1 (Asher, Lunt, Matsuura, Novosad — Development Data Lab). Within-district std and max−min serve as Riley-style terrain ruggedness proxies. Citation: Farr & Kobrick (2000), Eos 81(48):583-585. Licence: SHRUG CC BY-NC-SA 4.0; SRTM is public domain.',
      };

    case 'crop_production':
      return {
        label: 'Census 2011 Village Directory land use (via SHRUG v2.1)',
        url: 'https://devdatalab.org/shrug',
        attribution: 'Office of the Registrar General & Census Commissioner, India — Population Census 2011 Village Directory land-use accounts. District aggregation via SHRUG v2.1 (Asher, Lunt, Matsuura, Novosad — Development Data Lab). Net Sown Area and Irrigated Area are the canonical agricultural-production proxies at district level; SHRUG does not publish district-level crop-output tonnes for India. Licence: SHRUG CC BY-NC-SA 4.0; Census of India © Government of India.',
      };
  }

  // Unknown indicator
  return {
    label: 'See Sources page',
    url: '/about#sources',
  };
}
