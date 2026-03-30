#!/usr/bin/env python3
"""
Export pre-aggregated indicator files for progressive loading.

Generates:
  public/indicators/{indicator_key}/{quarter_code}.json
  public/indicators/manifest.json

Each indicator file contains ALL districts across ALL states for that
indicator + quarter, so the frontend only loads ~50-200 KB instead of 19 MB.
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'public', 'indicators')
BANKING_OUTLETS_PATH = os.path.join(PROJECT_ROOT, 'public', 'banking-outlets', 'district_counts.json')

# ─── Indicator definitions (mirroring index.astro INDICATORS object) ───
# Each indicator has a primary category and metrics with field + fallbacks.
# The export resolves fallbacks and cross-category fallbacks at export time,
# so the frontend gets a single flat record per district.

INDICATORS = {
    'credit_deposit_ratio': {
        'title': 'Credit-Deposit Ratio',
        'category': 'credit_deposit_ratio',
        'metrics': [
            {'field': 'overall_cd_ratio', 'label': 'Overall CD Ratio (%)', 'unit': '%',
             'fallbacks': ['cd_ratio', 'current_c_d_ratio', 'cdr', 'overall', 'cd_ratio_incl_pou']},
            {'field': 'total_deposit', 'label': 'Total Deposits', 'unit': '₹',
             'fallbacks': ['deposit', 'deposits_rural', 'september_2025_total_deposit', 'total_deposits']},
            {'field': 'total_advance', 'label': 'Total Advances', 'unit': '₹',
             'fallbacks': ['advance', 'advances', 'total_advance_utilized_in_the_state', 'total_advances']},
            {'field': 'total_branch', 'label': 'Total Branches', 'unit': '',
             'fallbacks': ['total', 'no_of_brs', 'total_branches']},
        ],
    },
    'pmjdy': {
        'title': 'PM Jan Dhan Yojana',
        'category': 'pmjdy',
        'metrics': [
            {'field': 'total_pmjdy_no', 'label': 'Total PMJDY Accounts', 'unit': '',
             'fallbacks': ['total_no_pmjdy', 'pmjdy_no', 'total_no', 'no_of_pmjdy_accounts', 'pmjdy', 'total',
                           'number_of_pmjdy_accounts_rural', 'total_pmjdy_a_c', 'total_no_pmjdy_a_c', 'total_a_c',
                           'sum_of_total_a_c', 'pmjdy_total_accounts']},
            {'field': 'no_of_zero_balance_a_c', 'label': 'Zero Balance Accounts', 'unit': '',
             'fallbacks': ['zero_balance', 'zero_balance_a_c', 'zero_balance_account_2', 'zero_balance_account']},
            {'field': 'no_of_aadhaar_seeded', 'label': 'Aadhaar Seeded', 'unit': '',
             'fallbacks': ['aadhaar_seeded', 'aadhaar_seeding_pct', 'sum_of_aadhaar_seeded']},
            {'field': 'no_of_rupay_card_issued', 'label': 'RuPay Cards Issued', 'unit': '',
             'fallbacks': ['rupay_card_issued', 'rupaycard_account', 'rupay_card_account', 'ar_cu_psaycard_issued']},
            {'field': 'female_no', 'label': 'Female Accounts', 'unit': '',
             'fallbacks': ['no_of_women_pmjdy_accounts', 'female', 'female_a_c', 'sum_of_female_a_c']},
            {'field': 'rural_no', 'label': 'Rural Accounts', 'unit': '',
             'fallbacks': ['rural', 'rural_a_c', 'sum_of_rural_a_c']},
        ],
    },
    'branch_network': {
        'title': 'Branch Network',
        'category': 'branch_network',
        'metrics': [
            {'field': 'total_branch', 'label': 'Total Branches', 'unit': '',
             'fallbacks': ['total', 'no_of_branches', 'total_no_of_br', 'total_branche_s', 'total_branches',
                           'total_branch_es', 'branches_total']},
            {'field': 'branch_rural', 'label': 'Rural Branches', 'unit': '',
             'fallbacks': ['atm_rural', 'rural', 'branches_rural']},
            {'field': 'branch_semi_urban', 'label': 'Semi-Urban Branches', 'unit': '',
             'fallbacks': ['semi_urban', 'branches_semi_urban']},
            {'field': 'branch_urban', 'label': 'Urban Branches', 'unit': '',
             'fallbacks': ['urban', 'branches_urban']},
            {'field': 'total_atm', 'label': 'Total ATMs', 'unit': '',
             'fallbacks': ['no_of_atm', 'total_atms', 'atm_total']},
            {'field': 'total_csp', 'label': 'Total CSPs', 'unit': '',
             'fallbacks': ['bc_total', 'total_bc']},
        ],
    },
    'kcc': {
        'title': 'Kisan Credit Card',
        'category': 'kcc',
        'metrics': [
            {'field': 'total_no_of_kcc', 'label': 'Total KCC Issued', 'unit': '',
             'fallbacks': ['no_of_kcc', 'kcc_no', 'total_kcc_no', 'total_no', 'o_s_position_no_of_cards_issued',
                           'cum_no_app_sanc', 'no_of_kcc_issued_during_quarter_including_renewal',
                           'rupay_card_issued_in_kcc', 'target_no',
                           'outstanding_at_the_end_of_reporting_quarter_no',
                           'outstanding_at_the_end_of_reporting_quarter_number',
                           'kcc_card_activated_number', 'no_of_applications_sanctioned',
                           'kcc_new_target_no', 'kcc_outstanding_as_on', 'no_of_kcc_issued']},
            {'field': 'outstanding_amt', 'label': 'Outstanding Amount', 'unit': '₹',
             'fallbacks': ['total_outstanding', 'total_o_s_kcc_amt', 'kcc_outstanding',
                           'o_s_position_limit_sanctioned', 'kcc_limit_sanctioned_in_rs_lakhs', 'amount',
                           'outstanding_at_the_end_of_reporting_quarter_amt', 'amt', 'amount_disbursed']},
            {'field': 'no_of_rupay_card_issued', 'label': 'RuPay Cards Issued', 'unit': '',
             'fallbacks': ['rupay_card_issued',
                           'out_of_total_kcc_issued,_no_of_rupay_cards_issued_number',
                           'out_of_total_kcc_issued,_no_of_rupay_cards_issued_no']},
            {'field': 'kcc_card_activated', 'label': 'Cards Activated', 'unit': '',
             'fallbacks': ['card_activated', 'kcc_card_activated_no', 'kcc_card_activated_number']},
        ],
    },
    'shg': {
        'title': 'Self Help Groups',
        'category': 'shg',
        'metrics': [
            {'field': 'savings_linked_no', 'label': 'Savings Linked SHGs', 'unit': '',
             'fallbacks': ['savings_linked', 'credit_linked_no', 'credit_linked', 'current_fy_savings_linked_no',
                           'no_of_shgs', 'deposit_linkage_no_of_groups', 'total_sanction_no', 'total_sanctioned',
                           'total_shgs_repeat_renewals_enhancement_fy_2025_26',
                           'disburdsement_target_no_of_shgs',
                           'no_of_shgs_credit_linked_as_on_31st_march_2023',
                           'cumulative_achievement_physical_7', 'target_physical_3',
                           'disbursement_no', 'outstanding_no',
                           'sanctioned_upto_dec25_no', 'sanctioned_upto_sep25_no',
                           'sanctioned_upto_jun25_no', 'sanctioned_upto_mar25_no',
                           'target_fy_2025_26_no']},
            {'field': 'credit_linked_no', 'label': 'Credit Linked SHGs', 'unit': '',
             'fallbacks': ['credit_linked', 'current_fy_credit_linked_no',
                           'credit_linkage_loan_given_by_banks_no', 'total_disbursement_no']},
            {'field': 'shg_o_s_amt', 'label': 'Outstanding Amount', 'unit': '₹',
             'fallbacks': ['outstanding_amt', 'shg_o_s', 'outstanding_accounts',
                           'total_outsanding_no', 'total_outstanding_amt_rs_in_lakh']},
            {'field': 'shg_npa_pct', 'label': 'SHG NPA %', 'unit': '%', 'fallbacks': []},
        ],
    },
    'digital_transactions': {
        'title': 'Digital Transactions',
        'category': 'digital_transactions',
        'metrics': [
            # PhonePe UPI fields — NOT in SLBC, come from phonepe_data table
            {'field': 'transaction_count', 'label': 'UPI Transaction Count (PhonePe)', 'unit': '',
             'source': 'phonepe', 'fallbacks': []},
            {'field': 'transaction_amount', 'label': 'UPI Transaction Amount (PhonePe)', 'unit': '₹',
             'source': 'phonepe', 'fallbacks': []},
            # SLBC digital fields
            {'field': 'coverage_sb_pct', 'label': 'SB Digital Coverage %', 'unit': '%',
             'fallbacks': ['coverage_pct', 'achievement', 'pct_coverage', 'pct_coverag_e_h',
                           'pct_coverage_9688',
                           'of_such_accounts_out_of_total_operative_savings_accounts']},
            {'field': 'digital_coverage_sb_a_c', 'label': 'SB A/Cs Digitally Covered', 'unit': '',
             'fallbacks': ['total_operative_sb_a_c',
                           'no_of_operative_sb_a_c_covered_with_at_least_one_digital_mode',
                           'debit_rupay_cards_coverage_total_no_of_accounts_covered',
                           'debit_rupay_cards_coverage_total_no_of_accounts_covered_g',
                           'coverage_with_at_least_one_of_the_digital_modes_of_payment_debit_rupay_cards,_in']},
            {'field': 'bhim_upi_a_c', 'label': 'BHIM/UPI A/Cs (SLBC)', 'unit': '',
             'fallbacks': ['bhim_upi', 'bhim_aadhaar_a_c', 'digital_bhim_upi_no']},
            {'field': 'imps_a_c', 'label': 'IMPS Transactions', 'unit': '',
             'fallbacks': ['imps', 'digital_imps_no']},
            {'field': 'cards_debit_credit_a_c', 'label': 'Card Transactions', 'unit': '',
             'fallbacks': ['cards_debit_credit', 'cards_debit', 'digital_cards_no']},
            {'field': 'ussd_a_c', 'label': 'USSD Transactions', 'unit': '',
             'fallbacks': ['ussd', 'digital_ussd_no']},
        ],
    },
    'aadhaar_authentication': {
        'title': 'Aadhaar Authentication',
        'category': 'aadhaar_authentication',
        'metrics': [
            {'field': 'no_of_aadhaar_seeded_casa', 'label': 'Aadhaar Seeded CASA', 'unit': '',
             'fallbacks': ['aadhaar_seeded_casa', 'number_of_aadhaar_seeded_casa', 'no_of_aadhaar_seeded',
                           'aadhaar_seeded', 'pct_aadhaar_seeding', 'pct_of_casa_aadhaar_seeding']},
            {'field': 'no_of_operative_casa', 'label': 'Operative CASA', 'unit': '',
             'fallbacks': ['operative_casa', 'number_of_operative_casa', 'aadhaar_operative_casa', 'operative_sb']},
            {'field': 'no_of_authenticated_casa', 'label': 'Authenticated CASA', 'unit': '',
             'fallbacks': ['authenticated_casa', 'number_of_authenticated_casa',
                           'aadhaar_authenticated_casa', 'number_of_authenticated']},
        ],
    },
    'social_security': {
        'title': 'Social Security Schemes',
        'category': 'social_security',
        'metrics': [
            {'field': 'enrolment_under_pmsby', 'label': 'PMSBY Enrollment', 'unit': '',
             'fallbacks': ['pmsby_cumml_no', 'pmsby_no', 'eligible_cases_under_pmsby', 'renewals_under_pmsby']},
            {'field': 'enrolment_under_pmjjby', 'label': 'PMJJBY Enrollment', 'unit': '',
             'fallbacks': ['pmjjby_cumml_no', 'pmjjby_no', 'eligible_cases_under_pmjjby', 'renewals_under_pmjjby']},
            {'field': 'enrolment_under_apy', 'label': 'APY Enrollment', 'unit': '',
             'fallbacks': ['apy_cumml_no', 'apy_no', 'cumulative_apy_accounts_opened_since_inception',
                           'apy_accounts_opened_in_current_fy']},
            {'field': 'total_enrolment_no', 'label': 'Total Social Security Enrollment', 'unit': '',
             'fallbacks': []},
        ],
    },
    'pmegp': {
        'title': 'PM Employment Generation',
        'category': 'pmegp',
        'metrics': [
            {'field': 'cy_disbursed_no', 'label': 'Disbursed (Current Year)', 'unit': '',
             'fallbacks': ['disbursed', 'cy_disbursed_a_c_no', 'disbursement_no', 'mm_disbursed_no_of_prj']},
            {'field': 'cy_disbursed_amt', 'label': 'Disbursed Amount (CY)', 'unit': '₹',
             'fallbacks': ['disbursement_amt']},
            {'field': 'os_no', 'label': 'Outstanding Projects', 'unit': '',
             'fallbacks': ['pmegp_o_s_no']},
            {'field': 'os_amt', 'label': 'Outstanding Amount', 'unit': '₹',
             'fallbacks': ['pmegp_o_s_amt']},
            {'field': 'npa_pct', 'label': 'NPA %', 'unit': '%',
             'fallbacks': ['pmegp_npa_pct']},
        ],
    },
    'housing_pmay': {
        'title': 'Housing / PMAY',
        'category': 'housing_pmay',
        'metrics': [
            {'field': 'rural_housing_loan_o_s_no', 'label': 'Rural Housing Loans (O/S)', 'unit': '',
             'fallbacks': ['rural_number', 'rural_no']},
            {'field': 'rural_housing_loan_o_s_amt', 'label': 'Rural Housing Amount (O/S)', 'unit': '₹',
             'fallbacks': ['rural_amt']},
            {'field': 'pmay_o_s_no', 'label': 'PMAY Loans (O/S)', 'unit': '',
             'fallbacks': ['current_year_disbursed_under_pmay_no']},
            {'field': 'pmay_o_s_amt', 'label': 'PMAY Amount (O/S)', 'unit': '₹',
             'fallbacks': ['current_year_disbursed_under_pmay_amt']},
            {'field': 'housing_loan_ps_o_s_no', 'label': 'Housing Priority Sector (O/S)', 'unit': '',
             'fallbacks': ['total_number']},
            {'field': 'housing_loan_ps_o_s_amt', 'label': 'Housing PS Amount (O/S)', 'unit': '₹',
             'fallbacks': ['total_amt']},
        ],
    },
    'sui': {
        'title': 'Stand Up India',
        'category': 'sui',
        'metrics': [
            {'field': 'no_of_female_account', 'label': 'Women Borrowers', 'unit': '',
             'fallbacks': ['current_year_no_of_female_account', 'female_account_no']},
            {'field': 'sui_o_s_no', 'label': 'Outstanding Loans', 'unit': '',
             'fallbacks': ['total_current_year_sui_disb_no']},
            {'field': 'sui_o_s_amt', 'label': 'Outstanding Amount', 'unit': '₹',
             'fallbacks': ['total_current_year_sui_disb_amt']},
            {'field': 'sui_npa_pct', 'label': 'NPA %', 'unit': '%', 'fallbacks': []},
        ],
    },
    'sc_st_finance': {
        'title': 'SC/ST Lending',
        'category': 'sc_st_finance',
        'metrics': [
            {'field': 'sc_disbursement_no', 'label': 'SC Disbursement (No.)', 'unit': '',
             'fallbacks': ['sc_disb_no', 'scheduled_castes_no']},
            {'field': 'sc_disbursement_amt', 'label': 'SC Disbursement (₹ Lakhs)', 'unit': '₹',
             'fallbacks': ['sc_disb_amt', 'scheduled_castes_amt']},
            {'field': 'st_disbursement_no', 'label': 'ST Disbursement (No.)', 'unit': '',
             'fallbacks': ['st_disb_no', 'scheduled_tribes_no']},
            {'field': 'st_disbursement_amt', 'label': 'ST Disbursement (₹ Lakhs)', 'unit': '₹',
             'fallbacks': ['st_disb_amt', 'scheduled_tribes_amt']},
            {'field': 'sc_outstanding_no', 'label': 'SC Outstanding (No.)', 'unit': '',
             'fallbacks': ['sc_o_s_no']},
            {'field': 'st_outstanding_no', 'label': 'ST Outstanding (No.)', 'unit': '',
             'fallbacks': ['st_o_s_no']},
        ],
    },
    'women_finance': {
        'title': "Women's Credit",
        'category': 'women_finance',
        'metrics': [
            {'field': 'o_s_no', 'label': 'Outstanding Loans (No.)', 'unit': '',
             'fallbacks': ['cy_disb_no']},
            {'field': 'o_s_amt', 'label': 'Outstanding Amount', 'unit': '₹',
             'fallbacks': ['cy_disb_amt']},
            {'field': 'cy_disb_no', 'label': 'Disbursed (Current Year)', 'unit': '', 'fallbacks': []},
            {'field': 'cy_disb_amt', 'label': 'Disbursed Amount (CY)', 'unit': '₹', 'fallbacks': []},
        ],
    },
    'education_loan': {
        'title': 'Education Loans',
        'category': 'education_loan',
        'metrics': [
            {'field': 'sanctioned_no', 'label': 'Sanctioned (No.)', 'unit': '',
             'fallbacks': ['disb_no', 'o_s_no']},
            {'field': 'sanctioned_amt', 'label': 'Sanctioned Amount', 'unit': '₹',
             'fallbacks': ['disb_amt', 'o_s_amt', 'amt']},
            {'field': 'of_which_girl_student_disb_no', 'label': 'Girl Student Loans', 'unit': '',
             'fallbacks': ['of_which_girl_student_sanctioned_no', 'of_which_girl_student_o_s_no']},
            {'field': 'of_which_girl_student_disb_amt', 'label': 'Girl Student Amount', 'unit': '₹',
             'fallbacks': ['of_which_girl_student_sanctioned_amt', 'of_which_girl_student_o_s_amt']},
        ],
    },
    'pmmy_mudra_disbursement': {
        'title': 'MUDRA / PMMY',
        'category': 'pmmy_mudra_disbursement',
        'metrics': [
            {'field': 'sishu_no', 'label': 'Shishu Loans (No.)', 'unit': '',
             'fallbacks': ['shishu_no']},
            {'field': 'sishu_amt', 'label': 'Shishu Amount', 'unit': '₹',
             'fallbacks': ['shishu_amt']},
            {'field': 'kishore_no', 'label': 'Kishore Loans (No.)', 'unit': '',
             'fallbacks': ['kishor_no']},
            {'field': 'kishore_amt', 'label': 'Kishore Amount', 'unit': '₹',
             'fallbacks': ['kishor_amt']},
            {'field': 'tarun_no', 'label': 'Tarun Loans (No.)', 'unit': '', 'fallbacks': []},
            {'field': 'tarun_amt', 'label': 'Tarun Amount', 'unit': '₹', 'fallbacks': []},
            {'field': 'total_mudra_disb_no', 'label': 'Total MUDRA Disbursed', 'unit': '',
             'fallbacks': ['total_mudra_o_s_no']},
            {'field': 'total_mudra_disb_amt', 'label': 'Total MUDRA Amount', 'unit': '₹',
             'fallbacks': ['total_mudra_o_s_amt']},
        ],
    },
    'rbi_banking_outlets': {
        'title': 'Banking Infrastructure (RBI)',
        'category': None,  # Static data, not from SLBC
        'source': 'rbi_outlets',
        'metrics': [
            {'field': 'rbi_outlets__total', 'label': 'Total Banking Outlets', 'unit': ''},
            {'field': 'rbi_outlets__branch', 'label': 'Bank Branches', 'unit': ''},
            {'field': 'rbi_outlets__bc', 'label': 'Business Correspondents', 'unit': ''},
            {'field': 'rbi_outlets__csp', 'label': 'Customer Service Points', 'unit': ''},
            {'field': 'rbi_outlets__rural', 'label': 'Rural Outlets', 'unit': ''},
            {'field': 'rbi_outlets__semi_urban', 'label': 'Semi-Urban Outlets', 'unit': ''},
            {'field': 'rbi_outlets__urban', 'label': 'Urban Outlets', 'unit': ''},
            {'field': 'rbi_outlets__metro', 'label': 'Metropolitan Outlets', 'unit': ''},
        ],
    },
    'nfhs_health_insurance': {
        'title': 'Health Insurance Coverage (NFHS-5)',
        'category': None,  # Static data from NFHS-5 district factsheets
        'source': 'nfhs_district',
        'metrics': [
            {'field': 'nfhs5_pct', 'label': 'NFHS-5 Coverage (%)', 'unit': '%'},
            {'field': 'nfhs4_pct', 'label': 'NFHS-4 Coverage (%)', 'unit': '%'},
        ],
    },
}

# Cross-category fallbacks: when the primary category doesn't have a field,
# try these alternative categories (mirrors index.astro CROSS_CATEGORY_FALLBACKS)
CROSS_CATEGORY_FALLBACKS = {
    'branch_network': ['credit_deposit_ratio', 'kcc', 'fi_kcc', 'digital_transactions',
                       'branch_network_p2', 'branch_network_p3', 'branch_network_p4',
                       'atm_network', 'business_correspondents'],
    'credit_deposit_ratio': ['key_indicators', 'district_misc', 'cd_ratio'],
    'kcc': ['fi_kcc', 'kcc_animal_husbandry', 'kcc_fishery', 'kcc_outstanding', 'kcc_fisheries'],
    'shg': ['shg_nrlm', 'nrlm', 'shg_p2', 'shg_p3', 'jlg'],
    'digital_transactions': ['phonepe_upi', 'digital_payments', 'digital_coverage_savings',
                             'digital_coverage_savings_p2', 'digital_coverage_business', 'women_finance'],
    'social_security': ['social_security_schemes', 'social_security_claims', 'social_security_2', 'apy'],
    'pmjdy': ['pmjdy_p2', 'pmjdy_p3', 'pmjdy_p4', 'social_security_schemes', 'pmjdy_2', 'pmjdy_3'],
    'aadhaar_authentication': ['pmjdy', 'pmjdy_2', 'pmjdy_3'],
    'pmegp': ['pmegp_2'],
    'housing_pmay': ['housing_pmay_p2'],
    'sui': ['stand_up_india'],
    'sc_st_finance': ['sc_st_lending', 'weaker_section_os'],
    'women_finance': ['women_finance_2'],
    'education_loan': ['education_loan_2'],
    'pmmy_mudra_disbursement': ['pmmy_mudra_os_npa', 'mudra', 'mudra_2'],
}

# Quarter labels for display
QUARTER_LABELS = {
    '01': 'January', '02': 'February', '03': 'March', '04': 'April',
    '05': 'May', '06': 'June', '07': 'July', '08': 'August',
    '09': 'September', '10': 'October', '11': 'November', '12': 'December',
}


def format_quarter_label(code):
    """Convert '2025-09' to 'September 2025'."""
    parts = code.split('-')
    month = QUARTER_LABELS.get(parts[1], parts[1])
    return f'{month} {parts[0]}'


def load_all_slbc_data(db):
    """
    Load all SLBC data into a nested dict:
      data[quarter_code][(district_name, state_slug)][field_key] = value_text

    field_key in the DB is "{category}__{field_name}", which is exactly
    how the frontend stores it after flattening timeseries JSON.
    """
    print('Loading SLBC data from database...')
    cur = db.execute('''
        SELECT p.code, d.name, s.slug, sf.field_key, sd.value_text
        FROM slbc_data sd
        JOIN slbc_fields sf ON sd.field_id = sf.id
        JOIN districts d ON sd.district_lgd = d.lgd_code
        JOIN states s ON sd.state_lgd_code = s.lgd_code
        JOIN periods p ON sd.period_id = p.id
        WHERE sd.value_text IS NOT NULL AND sd.value_text != ''
    ''')

    data = defaultdict(lambda: defaultdict(dict))
    count = 0
    for quarter, district, state, field_key, value in cur:
        data[quarter][(district, state)][field_key] = value
        count += 1

    print(f'  Loaded {count:,} SLBC values across {len(data)} quarters')
    return data


def load_phonepe_data(db):
    """
    Load PhonePe data into:
      data[quarter_code][(district_name_raw, state_slug)] = {transaction_count, transaction_amount}
    """
    print('Loading PhonePe data...')
    cur = db.execute('''
        SELECT p.code, ph.district_name_raw, ph.state_slug,
               ph.transaction_count, ph.transaction_amount
        FROM phonepe_data ph
        JOIN periods p ON ph.period_id = p.id
    ''')

    data = defaultdict(dict)
    count = 0
    for quarter, district, state, txn_count, txn_amount in cur:
        data[quarter][(district, state)] = {
            'transaction_count': str(txn_count) if txn_count is not None else None,
            'transaction_amount': str(round(txn_amount, 2)) if txn_amount is not None else None,
        }
        count += 1

    print(f'  Loaded {count:,} PhonePe records across {len(data)} quarters')
    return data


def load_rbi_outlets():
    """Load RBI banking outlet district counts (static snapshot)."""
    print('Loading RBI banking outlet data...')
    if not os.path.exists(BANKING_OUTLETS_PATH):
        print(f'  WARNING: {BANKING_OUTLETS_PATH} not found, skipping RBI outlets')
        return {}

    with open(BANKING_OUTLETS_PATH) as f:
        raw = json.load(f)

    # Build lookup: (district_upper, state_upper) -> counts
    outlets = {}
    for d in raw.get('districts', []):
        # Clean nbsp from source data
        state = d['state'].replace('\xa0', ' ').strip()
        district = d['district'].replace('\xa0', ' ').strip()
        outlets[(district, state)] = {
            'rbi_outlets__total': str(d.get('total', 0)),
            'rbi_outlets__branch': str(d.get('branch', 0)),
            'rbi_outlets__bc': str(d.get('bc', 0)),
            'rbi_outlets__csp': str(d.get('csp', 0)),
            'rbi_outlets__rural': str(d.get('rural', 0)),
            'rbi_outlets__semi_urban': str(d.get('semi_urban', 0)),
            'rbi_outlets__urban': str(d.get('urban', 0)),
            'rbi_outlets__metro': str(d.get('metro', 0)),
        }

    print(f'  Loaded {len(outlets)} districts with RBI outlet data')
    return outlets


def resolve_metric_value(record, category, field, fallbacks):
    """
    Resolve a metric value from a district record, trying:
    1. Primary category + primary field
    2. Primary category + fallback fields
    3. Cross-category fallback categories + primary field
    4. Cross-category fallback categories + fallback fields

    Returns the value string or None.
    """
    # Try primary category + field
    key = f'{category}__{field}'
    if key in record:
        return record[key]

    # Try primary category + fallbacks
    if fallbacks:
        for fb in fallbacks:
            key = f'{category}__{fb}'
            if key in record:
                return record[key]

    # Try cross-category fallbacks
    cross_cats = CROSS_CATEGORY_FALLBACKS.get(category, [])
    for cross_cat in cross_cats:
        key = f'{cross_cat}__{field}'
        if key in record:
            return record[key]
        if fallbacks:
            for fb in fallbacks:
                key = f'{cross_cat}__{fb}'
                if key in record:
                    return record[key]

    return None


def export_slbc_indicator(indicator_key, indicator_def, slbc_data, phonepe_data, quarters):
    """Export all quarter files for a single SLBC-based indicator."""
    category = indicator_def['category']
    metrics = indicator_def['metrics']
    out_dir = os.path.join(OUTPUT_DIR, indicator_key)
    os.makedirs(out_dir, exist_ok=True)

    files_written = 0
    for quarter in quarters:
        quarter_slbc = slbc_data.get(quarter, {})
        quarter_phonepe = phonepe_data.get(quarter, {})

        districts = []
        # Collect all district keys from SLBC for this quarter
        seen_keys = set()
        for (district, state) in quarter_slbc:
            seen_keys.add((district, state))

        # For digital_transactions, also include PhonePe-only districts
        if indicator_key == 'digital_transactions':
            for (district, state) in quarter_phonepe:
                seen_keys.add((district, state))

        for (district, state) in sorted(seen_keys):
            record = quarter_slbc.get((district, state), {})
            entry = {'district': district, 'state': state}

            has_data = False
            for metric in metrics:
                field = metric['field']
                source = metric.get('source')

                if source == 'phonepe':
                    # PhonePe UPI data
                    pp = quarter_phonepe.get((district, state), {})
                    val = pp.get(field)
                else:
                    # SLBC data with fallback resolution
                    fallbacks = metric.get('fallbacks', [])
                    val = resolve_metric_value(record, category, field, fallbacks)

                if val is not None:
                    entry[field] = val
                    has_data = True

            if has_data:
                districts.append(entry)

        if not districts:
            continue

        out = {
            'indicator': indicator_key,
            'quarter': quarter,
            'label': format_quarter_label(quarter),
            'districts': districts,
        }

        path = os.path.join(out_dir, f'{quarter}.json')
        with open(path, 'w') as f:
            json.dump(out, f, separators=(',', ':'), ensure_ascii=False)
        files_written += 1

    return files_written


def export_rbi_outlets(rbi_data):
    """
    Export RBI banking outlets as a single 'static' file.
    Since this is a static snapshot (not quarterly), we output one file: 'static.json'.
    """
    out_dir = os.path.join(OUTPUT_DIR, 'rbi_banking_outlets')
    os.makedirs(out_dir, exist_ok=True)

    districts = []
    for (district, state), counts in sorted(rbi_data.items()):
        entry = {'district': district, 'state': state}
        entry.update(counts)
        districts.append(entry)

    out = {
        'indicator': 'rbi_banking_outlets',
        'quarter': 'static',
        'label': 'RBI DBIE (Latest)',
        'districts': districts,
    }

    path = os.path.join(out_dir, 'static.json')
    with open(path, 'w') as f:
        json.dump(out, f, separators=(',', ':'), ensure_ascii=False)

    return 1


def export_nfhs_health_insurance(db):
    """
    Export NFHS-5 health insurance district data as a single 'static' file.
    Source: nfhs_data table, indicator 'Households with any usual member covered
    under a health insurance/financing scheme (%)'
    """
    out_dir = os.path.join(OUTPUT_DIR, 'nfhs_health_insurance')
    os.makedirs(out_dir, exist_ok=True)

    rows = db.execute("""
        SELECT
            d.name AS district_name,
            s.slug AS state_slug,
            nd.nfhs5_numeric,
            nd.nfhs4_numeric
        FROM nfhs_data nd
        JOIN nfhs_indicators ni ON nd.indicator_id = ni.id
        LEFT JOIN districts d ON nd.district_lgd = d.lgd_code
        LEFT JOIN states s ON d.state_lgd_code = s.lgd_code
        WHERE ni.name LIKE '%health insurance%'
        AND nd.district_lgd IS NOT NULL
        ORDER BY s.slug, d.name
    """).fetchall()

    districts = []
    for district_name, state_slug, nfhs5, nfhs4 in rows:
        entry = {
            'district': district_name,
            'state': state_slug,
        }
        if nfhs5 is not None:
            entry['nfhs5_pct'] = nfhs5
        if nfhs4 is not None:
            entry['nfhs4_pct'] = nfhs4
        districts.append(entry)

    out = {
        'indicator': 'nfhs_health_insurance',
        'quarter': 'static',
        'label': 'NFHS-5 (2019-21)',
        'description': 'Households with any usual member covered under a health insurance/financing scheme (%)',
        'districts': districts,
    }

    path = os.path.join(out_dir, 'static.json')
    with open(path, 'w') as f:
        json.dump(out, f, separators=(',', ':'), ensure_ascii=False)

    return 1


def export_manifest(slbc_quarters, phonepe_quarters):
    """Generate the manifest.json with available indicators and quarters."""
    # Combine all quarters that have any data
    all_quarters = sorted(set(slbc_quarters) | set(phonepe_quarters), reverse=True)

    manifest = {
        'indicators': list(INDICATORS.keys()),
        'quarters': all_quarters,
        'latest_quarter': all_quarters[0] if all_quarters else None,
    }

    path = os.path.join(OUTPUT_DIR, 'manifest.json')
    with open(path, 'w') as f:
        json.dump(manifest, f, separators=(',', ':'), ensure_ascii=False)

    print(f'\nManifest: {len(manifest["indicators"])} indicators, {len(all_quarters)} quarters')
    print(f'Latest quarter: {manifest["latest_quarter"]}')
    return path


def main():
    if not os.path.exists(DB_PATH):
        print(f'ERROR: Database not found at {DB_PATH}')
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    db = sqlite3.connect(DB_PATH)
    db.execute('PRAGMA journal_mode=WAL')

    # Load all data
    slbc_data = load_all_slbc_data(db)
    phonepe_data = load_phonepe_data(db)
    rbi_data = load_rbi_outlets()

    slbc_quarters = sorted(slbc_data.keys())
    phonepe_quarters = sorted(phonepe_data.keys())

    # Export each indicator
    total_files = 0
    total_size = 0

    for indicator_key, indicator_def in INDICATORS.items():
        if indicator_def.get('source') == 'rbi_outlets':
            # Static RBI outlet data
            n = export_rbi_outlets(rbi_data)
            total_files += n
            fpath = os.path.join(OUTPUT_DIR, indicator_key, 'static.json')
            sz = os.path.getsize(fpath) if os.path.exists(fpath) else 0
            total_size += sz
            print(f'  {indicator_key}: 1 file ({sz / 1024:.1f} KB)')
        elif indicator_def.get('source') == 'nfhs_district':
            # Static NFHS district data
            n = export_nfhs_health_insurance(db)
            total_files += n
            fpath = os.path.join(OUTPUT_DIR, indicator_key, 'static.json')
            sz = os.path.getsize(fpath) if os.path.exists(fpath) else 0
            total_size += sz
            print(f'  {indicator_key}: 1 file ({sz / 1024:.1f} KB)')
        else:
            # SLBC-based indicator (may include PhonePe for digital_transactions)
            # Determine which quarters to process
            if indicator_key == 'digital_transactions':
                quarters = sorted(set(slbc_quarters) | set(phonepe_quarters))
            else:
                quarters = slbc_quarters

            n = export_slbc_indicator(indicator_key, indicator_def, slbc_data, phonepe_data, quarters)
            total_files += n

            # Measure total size for this indicator
            ind_dir = os.path.join(OUTPUT_DIR, indicator_key)
            ind_size = sum(
                os.path.getsize(os.path.join(ind_dir, f))
                for f in os.listdir(ind_dir) if f.endswith('.json')
            )
            total_size += ind_size
            print(f'  {indicator_key}: {n} files ({ind_size / 1024:.1f} KB total)')

    # Export manifest
    export_manifest(slbc_quarters, phonepe_quarters)
    manifest_size = os.path.getsize(os.path.join(OUTPUT_DIR, 'manifest.json'))
    total_size += manifest_size

    print(f'\n=== Summary ===')
    print(f'Total files: {total_files} indicator files + 1 manifest')
    print(f'Total size: {total_size / 1024:.1f} KB ({total_size / (1024 * 1024):.2f} MB)')
    print(f'Output: {OUTPUT_DIR}/')

    db.close()


if __name__ == '__main__':
    main()
