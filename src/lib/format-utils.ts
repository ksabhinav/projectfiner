/**
 * Shared formatting utilities for financial data display.
 * Used by the homepage map, TrendTracker, DistrictRankings, and DataExplorer.
 */

/**
 * Format a number with Indian-style abbreviations.
 * 1234 → "1.2K", 12345678 → "1.2 Cr", 123456 → "1.2 L"
 */
export function fmtNum(n: number | string | null | undefined): string {
  if (n === null || n === undefined || n === '') return '—';
  const v = typeof n === 'string' ? parseFloat(n.replace(/,/g, '')) : n;
  if (isNaN(v)) return String(n);
  if (v >= 1e7) return (v / 1e7).toFixed(1) + ' Cr';
  if (v >= 1e5) return (v / 1e5).toFixed(1) + ' L';
  if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  if (v % 1 !== 0) return v.toFixed(2);
  return v.toLocaleString('en-IN');
}

/**
 * Format a value with its unit label.
 * fmtWithUnit(1234, '₹') → "₹1.2K (₹ Lakhs)"
 * fmtWithUnit(94.3, '%') → "94.3%"
 * fmtWithUnit(123, '') → "123"
 */
export function fmtWithUnit(val: number | string, unit: '' | '₹' | '%'): string {
  const formatted = fmtNum(val);
  if (unit === '%') return formatted + '%';
  if (unit === '₹') return formatted + ' (₹ Lakhs)';
  return formatted;
}

/**
 * Convert snake_case field name to human-readable Title Case.
 * Preserves known acronyms (CASA, KCC, NPA, etc.)
 */
const ACRONYMS: Record<string, string> = {
  'casa': 'CASA', 'kcc': 'KCC', 'npa': 'NPA', 'pmjdy': 'PMJDY',
  'shg': 'SHG', 'atm': 'ATM', 'upi': 'UPI', 'imps': 'IMPS',
  'ussd': 'USSD', 'pmegp': 'PMEGP', 'nulm': 'NULM', 'nrlm': 'NRLM',
  'sb': 'SB', 'cd': 'CD', 'csp': 'CSP', 'aeps': 'AePS', 'dbt': 'DBT',
  'pmsby': 'PMSBY', 'pmjjby': 'PMJJBY', 'apy': 'APY', 'pmmy': 'PMMY',
  'pmay': 'PMAY', 'nps': 'Non-Priority Sector', 'ps': 'Priority Sector',
  'bc': 'BC', 'ifsc': 'IFSC', 'dbu': 'DBU', 'slbc': 'SLBC',
  'rbi': 'RBI', 'os': 'O/S', 'cy': 'Current Year', 'fy': 'Financial Year',
};

const ABBREVIATIONS: Record<string, string> = {
  'adv': 'Advances', 'dep': 'Deposits', 'br': 'Branches', 'brs': 'Branches',
  'disb': 'Disbursement', 'sanc': 'Sanctioned', 'ach': 'Achievement',
  'cum': 'Cumulative', 'tl': 'Term Loan', 'wc': 'Working Capital',
  'amt': 'Amount', 'pct': 'Percentage', 'no': 'No.',
};

export function prettyFieldName(field: string): string {
  // Remove category prefix (everything before __)
  const name = field.includes('__') ? field.split('__').pop()! : field;

  // Convert snake_case to words
  let words = name.split('_').filter(Boolean);

  // Expand abbreviations and fix acronyms
  words = words.map(w => {
    const lower = w.toLowerCase();
    if (ACRONYMS[lower]) return ACRONYMS[lower];
    if (ABBREVIATIONS[lower]) return ABBREVIATIONS[lower];
    // Title case
    return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
  });

  let result = words.join(' ');

  // Add unit suffix based on field name
  if (name.endsWith('_amt') || name.endsWith('_amount')) {
    if (!result.includes('Lakhs')) result += ' (₹ Lakhs)';
  } else if (name.endsWith('_pct') || name.endsWith('_percentage')) {
    if (!result.includes('%')) result += ' (%)';
  }

  return result;
}

/**
 * Normalize a period label to sortable code.
 * "June 2020" → "2020-06"
 */
const MONTH_MAP: Record<string, string> = {
  'january': '01', 'february': '02', 'march': '03', 'april': '04',
  'may': '05', 'june': '06', 'july': '07', 'august': '08',
  'september': '09', 'october': '10', 'november': '11', 'december': '12',
};

export function normalizePeriod(label: string): string {
  const parts = label.trim().split(/\s+/);
  if (parts.length === 2) {
    const month = MONTH_MAP[parts[0].toLowerCase()];
    const year = parts[1];
    if (month && /^\d{4}$/.test(year)) return `${year}-${month}`;
  }
  return label;
}

/**
 * Convert a period code back to a label.
 * "2020-06" → "June 2020"
 */
const CODE_TO_MONTH: Record<string, string> = {
  '01': 'January', '02': 'February', '03': 'March', '04': 'April',
  '05': 'May', '06': 'June', '07': 'July', '08': 'August',
  '09': 'September', '10': 'October', '11': 'November', '12': 'December',
};

export function periodLabel(code: string): string {
  const parts = code.split('-');
  if (parts.length === 2) {
    const month = CODE_TO_MONTH[parts[1]];
    if (month) return `${month} ${parts[0]}`;
  }
  return code;
}
