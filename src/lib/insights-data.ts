export interface Insight {
  id: string;
  title: string;
  body: string;
  statValue: string;
  statLabel: string;
  category: string;
  tags: string[];
  icon: string;
}

export const INSIGHT_CATEGORIES = [
  'All',
  'CD Ratio',
  'Digital',
  'Branches',
  'KCC',
  'PMJDY',
  'Comparison',
] as const;

export type InsightCategory = (typeof INSIGHT_CATEGORIES)[number];

export const insights: Insight[] = [
  {
    id: 'manipur-cd-ratio-leader',
    title: 'Manipur Leads NE States with CD Ratio Above 100%',
    body: 'Manipur is the only North Eastern state where the average district-level Credit-Deposit ratio exceeds 100%, reaching 100.4% in September 2025. This means banks in Manipur lend out more than they collect in deposits. In contrast, Meghalaya averages just 55.8% and Bihar 58.0%. Thoubal district in Manipur records the highest CD ratio at 175.2%.',
    statValue: '100.4%',
    statLabel: 'Manipur Avg CD Ratio (Sep 2025)',
    category: 'CD Ratio',
    tags: ['manipur', 'cd-ratio', 'leader'],
    icon: '📊',
  },
  {
    id: 'bihar-cd-ratio-growth',
    title: 'Bihar CD Ratio Rose from 42.9% to 58% in Six Years',
    body: 'Bihar\'s average district-level CD ratio climbed from 42.9% in March 2019 to 58.0% by September 2025, a 15 percentage-point improvement reflecting increased credit flow. However, it still falls short of the RBI norm of 60%. Purnia district leads at 96.9%, while Munger lags at 32.3%, revealing significant intra-state disparities.',
    statValue: '+15.1pp',
    statLabel: 'Bihar CD Ratio Gain (2019-2025)',
    category: 'CD Ratio',
    tags: ['bihar', 'cd-ratio', 'growth'],
    icon: '📈',
  },
  {
    id: 'meghalaya-digital-growth',
    title: 'Meghalaya UPI Transactions Surged 127% in Five Years',
    body: 'BHIM UPI transaction volume in Meghalaya grew from roughly 6.8 crore in June 2020 to over 15.4 crore by September 2025 on a cumulative quarterly basis. The sharpest acceleration came after December 2023, when quarterly volumes began consistently exceeding 10 crore, signalling a structural shift toward digital payments even in a small hill state.',
    statValue: '127%',
    statLabel: 'Meghalaya UPI Growth (2020-2025)',
    category: 'Digital',
    tags: ['meghalaya', 'digital', 'upi', 'growth'],
    icon: '💳',
  },
  {
    id: 'kamjong-branch-desert',
    title: 'Kamjong District in Manipur Has Just 1 Bank Branch',
    body: 'As of September 2025, Kamjong district in Manipur has only 1 bank branch to serve its entire population. This makes it the most underbanked district across all surveyed NE states. By comparison, Imphal West has 74 branches. The extreme disparity highlights how new hill districts created after 2016 remain severely underserved by formal banking.',
    statValue: '1',
    statLabel: 'Bank Branches in Kamjong',
    category: 'Branches',
    tags: ['manipur', 'branches', 'outlier', 'kamjong'],
    icon: '🏦',
  },
  {
    id: 'assam-branch-network',
    title: 'Assam Has 2,677 Branches, but South Salmara Has Only 17',
    body: 'Assam has the largest branch network in the NE region with 2,677 total bank branches as of September 2025. Dibrugarh leads with 190 branches. However, South Salmara-Mankachar district has just 17 branches, a stark 11:1 ratio between the most and least banked districts within the same state.',
    statValue: '2,677',
    statLabel: 'Total Bank Branches in Assam',
    category: 'Branches',
    tags: ['assam', 'branches', 'network', 'disparity'],
    icon: '🏛️',
  },
  {
    id: 'bihar-kcc-penetration',
    title: 'Bihar Has 26.7 Lakh Outstanding KCCs, Led by Patna',
    body: 'Bihar has 26,72,147 outstanding Kisan Credit Cards as of September 2025, making it a significant agricultural credit state. Patna district accounts for the most KCCs at 2,75,523, while Sheohar has the fewest at 15,662. The 18:1 ratio between the top and bottom districts reflects uneven access to agricultural credit despite the scheme\'s widespread rollout.',
    statValue: '26.7L',
    statLabel: 'Total Outstanding KCCs in Bihar',
    category: 'KCC',
    tags: ['bihar', 'kcc', 'agriculture'],
    icon: '🌾',
  },
  {
    id: 'assam-kcc-vs-ne',
    title: 'Assam\'s KCC RuPay Cards Outnumber the Rest of NE Combined',
    body: 'Assam has 3,59,259 RuPay cards issued under KCC, compared to 23,043 in Meghalaya, 14,516 in Manipur, and 11,478 in Mizoram. Assam alone accounts for roughly 88% of all KCC RuPay cards in the four surveyed NE states, reflecting both its larger agrarian base and deeper penetration of formal agricultural credit.',
    statValue: '88%',
    statLabel: 'Assam\'s Share of NE KCC RuPay Cards',
    category: 'KCC',
    tags: ['assam', 'kcc', 'comparison', 'ne-states'],
    icon: '🃏',
  },
  {
    id: 'meghalaya-pmjdy-growth',
    title: 'Meghalaya PMJDY Accounts Grew 72% in Under Four Years',
    body: 'Total PM Jan Dhan Yojana accounts in Meghalaya rose from 5,78,637 in March 2022 to 9,98,476 in September 2025, a 72.6% increase. The state is approaching the 10-lakh mark, with rural accounts (7.88 lakh) far outpacing urban ones (2.10 lakh). This steady growth suggests continued financial inclusion efforts are reaching previously unbanked populations.',
    statValue: '9.98L',
    statLabel: 'Meghalaya PMJDY Accounts (Sep 2025)',
    category: 'PMJDY',
    tags: ['meghalaya', 'pmjdy', 'growth', 'financial-inclusion'],
    icon: '🏧',
  },
  {
    id: 'assam-pmjdy-scale',
    title: 'Assam Has 2.35 Crore PMJDY Accounts, Largest in NE',
    body: 'Assam\'s PMJDY account count stands at 2,35,50,781 as of September 2025, dwarfing all other NE states combined. Manipur has 11.06 lakh and Meghalaya 9.98 lakh. The Assam total has grown steadily from 1.75 crore in September 2020, adding roughly 60 lakh accounts over five years while maintaining a strong rural skew of 77%.',
    statValue: '2.35Cr',
    statLabel: 'Assam PMJDY Accounts (Sep 2025)',
    category: 'PMJDY',
    tags: ['assam', 'pmjdy', 'scale'],
    icon: '👥',
  },
  {
    id: 'meghalaya-deposits-growth',
    title: 'Meghalaya Bank Deposits Grew 43% to Rs 40,947 Crore',
    body: 'Total bank deposits in Meghalaya rose from Rs 28,710 crore in September 2020 to Rs 40,947 crore by September 2025, a 42.6% increase over five years. Advances grew even faster, from Rs 12,374 crore to Rs 20,115 crore (62.6% growth), pushing the aggregate CD ratio from 43.1% toward the current 49.1%.',
    statValue: '40,947Cr',
    statLabel: 'Total Deposits in Meghalaya (Sep 2025)',
    category: 'Comparison',
    tags: ['meghalaya', 'deposits', 'growth'],
    icon: '💰',
  },
  {
    id: 'bihar-vs-assam-deposits',
    title: 'Assam Deposits Are 24x Bihar\'s Despite Smaller Population',
    body: 'Assam holds Rs 1,42,815 crore in bank deposits compared to Bihar\'s Rs 5,914 crore as captured in the SLBC data. Even accounting for Bihar\'s data possibly covering a subset of reporting banks, the contrast underscores massive differences in deposit mobilisation. Assam\'s advances (Rs 1,01,832 crore) also far exceed its NE peers.',
    statValue: '1,42,815Cr',
    statLabel: 'Total Deposits in Assam (Sep 2025)',
    category: 'Comparison',
    tags: ['assam', 'bihar', 'deposits', 'comparison'],
    icon: '⚖️',
  },
  {
    id: 'manipur-cd-ratio-climb',
    title: 'Manipur CD Ratio Climbed from 74.7% to 100.4% in Five Years',
    body: 'Manipur\'s average district-level CD ratio rose from 74.7% in September 2020 to a peak of 113.2% in March 2023 before stabilising around 100.4% by September 2025. This sustained above-100% ratio, unique among NE states, suggests strong credit demand possibly driven by government-backed lending and MSME disbursements.',
    statValue: '+25.7pp',
    statLabel: 'Manipur CD Ratio Gain (2020-2025)',
    category: 'CD Ratio',
    tags: ['manipur', 'cd-ratio', 'growth', 'trend'],
    icon: '🚀',
  },
  {
    id: 'east-jaintia-hills-low-cd',
    title: 'East Jaintia Hills Records Lowest CD Ratio at 24.2%',
    body: 'East Jaintia Hills in Meghalaya has the lowest district-level CD ratio among all surveyed districts at just 24.15% in September 2025. For every Rs 100 deposited, banks advance only Rs 24 in credit. By comparison, Ri Bhoi district in the same state has a CD ratio of 116.8%. Mining-heavy districts often see deposits outpace local credit demand.',
    statValue: '24.2%',
    statLabel: 'East Jaintia Hills CD Ratio',
    category: 'CD Ratio',
    tags: ['meghalaya', 'cd-ratio', 'outlier', 'disparity'],
    icon: '📉',
  },
];
