export const CATEGORY_INFO: Record<string, string> = {
  aadhaar_authentication:              'Aadhaar-enabled transactions',
  acp_disbursement_agri:               'ACP disbursement - Agriculture',
  acp_disbursement_msme:               'ACP disbursement - MSME',
  acp_disbursement_non_ps:             'ACP disbursement - Non-Priority Sector',
  acp_disbursement_other_ps:           'ACP disbursement - Other Priority Sector',
  acp_npa_outstanding:                 'ACP NPA outstanding',
  acp_priority_sector_os_npa:          'Priority sector outstanding & NPA',
  acp_target_achievement:              'ACP targets vs achievement',
  agri_npa:                            'Agriculture NPA',
  agri_outstanding:                    'Agriculture outstanding',
  branch_network:                      'Bank branches, ATMs, CSPs',
  credit_deposit_ratio:                'Deposits, advances, CD ratio',
  crop_insurance:                      'Crop insurance (PMFBY)',
  dcc_meetings:                        'DCC/DLRC meetings',
  digital_transactions:                'Digital transactions (UPI, IMPS, BHIM)',
  education_loan:                      'Education loans',
  fi_kcc:                              'FI & KCC progress',
  flc_report:                          'Financial Literacy Centre report',
  fi_village_banking:                  'Village banking outlets',
  govt_sponsored_npa:                  'Government sponsored schemes NPA',
  housing_pmay:                        'Housing loans / PMAY',
  investment_credit_agri_disbursement: 'Investment credit (agri) - disbursement',
  investment_credit_agri_outstanding:  'Investment credit (agri) - outstanding',
  jlg:                                 'Joint Liability Groups',
  kcc:                                 'Kisan Credit Card',
  kcc_crop:                            'KCC crop-wise details',
  ldm_details:                         'Lead District Manager details',
  minority:                             'Lending to minorities',
  minority_disbursement:               'Lending to minorities - disbursement',
  minority_outstanding:                'Lending to minorities - outstanding',
  msme_npa:                            'MSME NPA',
  msme_outstanding:                    'MSME outstanding',
  non_ps_npa:                          'Non-Priority Sector NPA',
  non_ps_outstanding:                  'Non-Priority Sector outstanding',
  nrlm:                                'National Rural Livelihoods Mission',
  nulm:                                'National Urban Livelihoods Mission',
  other_ps_npa:                        'Other Priority Sector NPA',
  other_ps_outstanding:                'Other Priority Sector outstanding',
  pmegp:                               'PM Employment Generation Programme',
  pmjdy:                               'PM Jan Dhan Yojana',
  pmmy_mudra_disbursement:             'PMMY/Mudra disbursement',
  pmfme:                               'PM Formalisation of Micro Food Enterprises',
  pmmy_mudra_os_npa:                   'PMMY/Mudra outstanding & NPA',
  priority_sector_analysis:            'Priority sector lending analysis',
  recovery_bakijai:                    'Recovery & Bakijai',
  rseti:                               'Rural Self Employment Training',
  sc_st_finance:                       'Lending to SC/ST',
  shg:                                 'Self Help Groups',
  social_security:                     'Social security (PMSBY, PMJJBY, APY)',
  sui:                                 'Stand Up India',
  segregation_advances:                'Segregation of advances',
  tea_garden_labourers:                'Tea garden labourers',
  uncategorized:                       'Other / Uncategorized',
  weaker_section_os:                   'Weaker section lending',
  women_finance:                       'Lending to women',
  // West Bengal specific categories
  acp_priority_sector:                 'ACP Priority Sector targets & achievement',
  aif:                                 'Agriculture Infrastructure Fund',
  apy:                                 'Atal Pension Yojana',
  digital_payments:                    'Digital payments ecosystem',
  financial_literacy:                  'Financial Literacy Centres & camps',
  kcc_animal_husbandry:                'KCC Animal Husbandry',
  kcc_fishery:                         'KCC Fishery',
  mudra:                               'MUDRA loans (Shishu, Kishor, Tarun)',
  msme:                                'MSME clusters & credit linkage',
  nlm:                                 'National Livestock Mission',
  npa_recovery:                        'NPA & recovery position',
  sarfaesi:                            'SARFAESI recovery',
  shg_nrlm:                            'SHG credit linkage (NRLM)',
  shg_nulm:                            'SHG credit linkage (NULM)',
  social_security_schemes:             'Social security schemes (PMJJBY, PMSBY, APY)',
  svskp:                               'Swarnjayanti Gram Swarozgar Yojana',
  farm_sector:                         'Farm sector lending',
  non_farm_sector:                     'Non-farm sector lending',
  weaker_section:                      'Weaker section lending',
  housing_loan:                        'Housing loans',
};

export const QUARTER_ORDER = [
  'june_2020','sept_2020','dec_2020',
  'june_2021','sept_2021','dec_2021',
  'mar_2022','june_2022','sept_2022','dec_2022',
  'mar_2023','sept_2023','dec_2023',
  'june_2024','sept_2024','dec_2024',
  'june_2025','sept_2025',
];

export const QUARTER_LABELS: Record<string, string> = {
  june_2020:'Jun 2020', sept_2020:'Sep 2020', dec_2020:'Dec 2020',
  june_2021:'Jun 2021', sept_2021:'Sep 2021', dec_2021:'Dec 2021',
  mar_2022:'Mar 2022', june_2022:'Jun 2022', sept_2022:'Sep 2022', dec_2022:'Dec 2022',
  mar_2023:'Mar 2023', sept_2023:'Sep 2023', dec_2023:'Dec 2023',
  june_2024:'Jun 2024', sept_2024:'Sep 2024', dec_2024:'Dec 2024',
  june_2025:'Jun 2025', sept_2025:'Sep 2025',
};

export const QUARTER_FOLDERS: Record<string, string> = {
  june_2020:'2020-06', sept_2020:'2020-09', dec_2020:'2020-12',
  june_2021:'2021-06', sept_2021:'2021-09', dec_2021:'2021-12',
  mar_2022:'2022-03', june_2022:'2022-06', sept_2022:'2022-09', dec_2022:'2022-12',
  mar_2023:'2023-03', sept_2023:'2023-09', dec_2023:'2023-12',
  june_2024:'2024-06', sept_2024:'2024-09', dec_2024:'2024-12',
  june_2025:'2025-06', sept_2025:'2025-09',
};

export function prettyCategoryName(cat: string): string {
  return cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    .replace(/Acp /,'ACP ').replace(/Npa/,'NPA').replace(/Pmjdy/,'PMJDY')
    .replace(/Pmmy/,'PMMY').replace(/Msme/,'MSME').replace(/Kcc/,'KCC')
    .replace(/Shg/,'SHG').replace(/Jlg/,'JLG').replace(/Nrlm/,'NRLM')
    .replace(/Nulm/,'NULM').replace(/Pmegp/,'PMEGP').replace(/Sui/,'SUI')
    .replace(/Sc St/,'SC/ST').replace(/Pmay/,'PMAY').replace(/Fi /,'FI ')
    .replace(/Ldm/,'LDM').replace(/Rseti/,'RSETI').replace(/ Os$/,' O/S')
    .replace(/ Ps /,' PS ').replace(/ Ps$/,' PS').replace(/ Nps/,' NPS')
    .replace(/Dcc/,'DCC').replace(/Flc/,'FLC').replace(/Pmfme/,'PMFME')
    .replace(/Pmfby/,'PMFBY').replace(/Blbc/,'BLBC')
    .replace(/Aif/,'AIF').replace(/Apy/,'APY').replace(/Nlm/,'NLM')
    .replace(/Mudra/,'MUDRA').replace(/Sarfaesi/,'SARFAESI');
}
