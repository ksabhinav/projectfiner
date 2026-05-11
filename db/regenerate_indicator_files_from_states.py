#!/usr/bin/env python3
"""Rebuild public/indicators/{indicator}/{quarter}.json directly from
public/slbc-data/{state}/{state}_fi_timeseries.json files.

This is a no-DB alternative to db/export_indicator_files.py. It exists because
many state _fi_timeseries.json files store the same data under category and
field aliases that the original CROSS_CATEGORY_FALLBACKS chain did not cover —
the result was sparse indicator files (e.g. social_security latest quarter had
only 2 states; pmegp had 6) even though the underlying state files had data
for 15+ states.

This script applies a much broader fallback chain (both at category and at
field-tail level) and re-emits the per-indicator quarter files.

PhonePe digital_transactions data (sourced from a separate pipeline) is left
untouched — only SLBC-sourced indicators are regenerated.

Usage: python3 db/regenerate_indicator_files_from_states.py
"""
from __future__ import annotations
import json
import os
import re
import sys
from collections import defaultdict


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STATES_DIR = os.path.join(ROOT, 'public', 'slbc-data')
OUT_DIR = os.path.join(ROOT, 'public', 'indicators')


MONTH_LOOKUP = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12',
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'jun': '06',
    'jul': '07', 'aug': '08', 'sep': '09', 'sept': '09', 'oct': '10',
    'nov': '11', 'dec': '12',
}


def normalize_period(p: str) -> str | None:
    if not p:
        return None
    if re.match(r'^\d{4}-\d{2}$', p):
        return p
    parts = p.strip().lower().split()
    if len(parts) == 2 and parts[0] in MONTH_LOOKUP and parts[1].isdigit():
        return f'{parts[1]}-{MONTH_LOOKUP[parts[0]]}'
    return None


def format_quarter_label(code: str) -> str:
    parts = code.split('-')
    months = {'01': 'January', '02': 'February', '03': 'March', '04': 'April',
              '05': 'May', '06': 'June', '07': 'July', '08': 'August',
              '09': 'September', '10': 'October', '11': 'November', '12': 'December'}
    return f'{months.get(parts[1], parts[1])} {parts[0]}'


# Per-indicator config. Each metric has a `field` (canonical) plus broad
# `fallbacks` covering every variant observed across the 23 state extractors.
# `categories` lists every category prefix the metric data has been seen under.
INDICATORS = {
    'credit_deposit_ratio': {
        'categories': ['credit_deposit_ratio', 'cd_ratio', 'key_indicators', 'district_misc'],
        'metrics': [
            {'field': 'overall_cd_ratio',
             'fallbacks': ['cd_ratio', 'current_c_d_ratio', 'cdr', 'overall', 'cd_ratio_incl_pou']},
            {'field': 'total_deposit',
             'fallbacks': ['deposit', 'deposits_rural', 'september_2025_total_deposit', 'total_deposits']},
            {'field': 'total_advance',
             'fallbacks': ['advance', 'advances', 'total_advance_utilized_in_the_state', 'total_advances']},
            {'field': 'total_branch',
             'fallbacks': ['total', 'no_of_brs', 'total_branches']},
        ],
    },
    'pmjdy': {
        'categories': ['pmjdy', 'pmjdy_p2', 'pmjdy_p3', 'pmjdy_p4', 'pmjdy_2', 'pmjdy_3',
                       'social_security_schemes'],
        'metrics': [
            {'field': 'total_pmjdy_no',
             'fallbacks': ['total_no_pmjdy', 'pmjdy_no', 'total_no', 'no_of_pmjdy_accounts',
                           'pmjdy', 'total', 'number_of_pmjdy_accounts_rural', 'total_pmjdy_a_c',
                           'total_no_pmjdy_a_c', 'total_a_c', 'sum_of_total_a_c',
                           'pmjdy_total_accounts']},
            {'field': 'no_of_zero_balance_a_c',
             'fallbacks': ['zero_balance', 'zero_balance_a_c', 'zero_balance_account_2',
                           'zero_balance_account']},
            {'field': 'no_of_aadhaar_seeded',
             'fallbacks': ['aadhaar_seeded', 'aadhaar_seeding_pct', 'sum_of_aadhaar_seeded']},
            {'field': 'no_of_rupay_card_issued',
             'fallbacks': ['rupay_card_issued', 'rupaycard_account', 'rupay_card_account',
                           'ar_cu_psaycard_issued']},
            {'field': 'female_no',
             'fallbacks': ['no_of_women_pmjdy_accounts', 'female', 'female_a_c',
                           'sum_of_female_a_c']},
            {'field': 'rural_no',
             'fallbacks': ['rural', 'rural_a_c', 'sum_of_rural_a_c']},
        ],
    },
    'branch_network': {
        'categories': ['branch_network', 'branch_network_p2', 'branch_network_p3',
                       'branch_network_p4', 'atm_network', 'business_correspondents',
                       'credit_deposit_ratio', 'kcc', 'fi_kcc', 'digital_transactions'],
        'metrics': [
            {'field': 'total_branch',
             'fallbacks': ['total', 'no_of_branches', 'total_no_of_br', 'total_branche_s',
                           'total_branches', 'total_branch_es', 'branches_total']},
            {'field': 'branch_rural',
             'fallbacks': ['atm_rural', 'rural', 'branches_rural']},
            {'field': 'branch_semi_urban',
             'fallbacks': ['semi_urban', 'branches_semi_urban']},
            {'field': 'branch_urban',
             'fallbacks': ['urban', 'branches_urban']},
            {'field': 'total_atm',
             'fallbacks': ['no_of_atm', 'total_atms', 'atm_total']},
            {'field': 'total_csp',
             'fallbacks': ['bc_total', 'total_bc']},
        ],
    },
    'kcc': {
        'categories': ['kcc', 'fi_kcc', 'kcc_animal_husbandry', 'kcc_fishery',
                       'kcc_fisheries', 'kcc_outstanding', 'kcc_outstanding_2',
                       'kcc_outstanding_3', 'kcc_outstanding_4'],
        'metrics': [
            {'field': 'total_no_of_kcc',
             'fallbacks': ['no_of_kcc', 'kcc_no', 'total_kcc_no', 'total_no',
                           'o_s_position_no_of_cards_issued', 'cum_no_app_sanc',
                           'no_of_kcc_issued_during_quarter_including_renewal',
                           'rupay_card_issued_in_kcc', 'target_no',
                           'outstanding_at_the_end_of_reporting_quarter_no',
                           'outstanding_at_the_end_of_reporting_quarter_number',
                           'kcc_card_activated_number', 'no_of_applications_sanctioned',
                           'kcc_new_target_no', 'kcc_outstanding_as_on', 'no_of_kcc_issued']},
            {'field': 'outstanding_amt',
             'fallbacks': ['total_outstanding', 'total_o_s_kcc_amt', 'kcc_outstanding',
                           'o_s_position_limit_sanctioned', 'kcc_limit_sanctioned_in_rs_lakhs',
                           'amount', 'outstanding_at_the_end_of_reporting_quarter_amt',
                           'amt', 'amount_disbursed']},
            {'field': 'no_of_rupay_card_issued',
             'fallbacks': ['rupay_card_issued',
                           'out_of_total_kcc_issued,_no_of_rupay_cards_issued_number',
                           'out_of_total_kcc_issued,_no_of_rupay_cards_issued_no']},
            {'field': 'kcc_card_activated',
             'fallbacks': ['card_activated', 'kcc_card_activated_no', 'kcc_card_activated_number']},
        ],
    },
    'shg': {
        'categories': ['shg', 'shg_nrlm', 'nrlm', 'shg_p2', 'shg_p3', 'jlg'],
        'metrics': [
            {'field': 'savings_linked_no',
             'fallbacks': ['savings_linked', 'credit_linked_no', 'credit_linked',
                           'current_fy_savings_linked_no', 'no_of_shgs',
                           'deposit_linkage_no_of_groups', 'total_sanction_no',
                           'total_sanctioned',
                           'total_shgs_repeat_renewals_enhancement_fy_2025_26',
                           'disburdsement_target_no_of_shgs',
                           'no_of_shgs_credit_linked_as_on_31st_march_2023',
                           'cumulative_achievement_physical_7', 'target_physical_3',
                           'disbursement_no', 'outstanding_no',
                           'sanctioned_upto_dec25_no', 'sanctioned_upto_sep25_no',
                           'sanctioned_upto_jun25_no', 'sanctioned_upto_mar25_no',
                           'target_fy_2025_26_no']},
            {'field': 'credit_linked_no',
             'fallbacks': ['credit_linked', 'current_fy_credit_linked_no',
                           'credit_linkage_loan_given_by_banks_no', 'total_disbursement_no']},
            {'field': 'shg_o_s_amt',
             'fallbacks': ['outstanding_amt', 'shg_o_s', 'outstanding_accounts',
                           'total_outsanding_no', 'total_outstanding_amt_rs_in_lakh']},
            {'field': 'shg_npa_pct', 'fallbacks': []},
        ],
    },
    'digital_transactions': {
        'categories': ['digital_transactions', 'digital_transactions_2', 'phonepe_upi',
                       'digital_payments', 'digital_coverage_savings',
                       'digital_coverage_savings_p2', 'digital_coverage_savings_p3',
                       'digital_coverage_savings_p4', 'digital_coverage_business',
                       'women_finance'],
        'metrics': [
            # transaction_count / transaction_amount come from PhonePe (not SLBC) —
            # we never overwrite the existing files for those; see preserve logic below.
            {'field': 'coverage_sb_pct',
             'fallbacks': ['coverage_pct', 'achievement', 'pct_coverage', 'pct_coverag_e_h',
                           'pct_coverage_9688',
                           'of_such_accounts_out_of_total_operative_savings_accounts']},
            {'field': 'digital_coverage_sb_a_c',
             'fallbacks': ['total_operative_sb_a_c',
                           'no_of_operative_sb_a_c_covered_with_at_least_one_digital_mode',
                           'debit_rupay_cards_coverage_total_no_of_accounts_covered',
                           'debit_rupay_cards_coverage_total_no_of_accounts_covered_g',
                           'coverage_with_at_least_one_of_the_digital_modes_of_payment_debit_rupay_cards,_in']},
            {'field': 'bhim_upi_a_c',
             'fallbacks': ['bhim_upi', 'bhim_aadhaar_a_c', 'digital_bhim_upi_no']},
            {'field': 'imps_a_c',
             'fallbacks': ['imps', 'digital_imps_no']},
            {'field': 'cards_debit_credit_a_c',
             'fallbacks': ['debit_credit_cards_a_c', 'cards_debit_credit', 'cards_debit',
                           'digital_cards_no']},
            {'field': 'ussd_a_c',
             'fallbacks': ['ussd', 'digital_ussd_no']},
        ],
    },
    'aadhaar_authentication': {
        'categories': ['aadhaar_authentication', 'pmjdy', 'pmjdy_2', 'pmjdy_3',
                       'pmjdy_p2', 'pmjdy_p3', 'pmjdy_p4'],
        'metrics': [
            {'field': 'no_of_aadhaar_seeded_casa',
             'fallbacks': ['aadhaar_seeded_casa', 'number_of_aadhaar_seeded_casa',
                           'no_of_aadhaar_seeded', 'aadhaar_seeded', 'pct_aadhaar_seeding',
                           'pct_of_casa_aadhaar_seeding']},
            {'field': 'no_of_operative_casa',
             'fallbacks': ['operative_casa', 'number_of_operative_casa',
                           'aadhaar_operative_casa', 'operative_sb']},
            {'field': 'no_of_authenticated_casa',
             'fallbacks': ['authenticated_casa', 'number_of_authenticated_casa',
                           'aadhaar_authenticated_casa', 'number_of_authenticated']},
        ],
    },
    'social_security': {
        'categories': ['social_security', 'social_security_2', 'social_security_3',
                       'social_security_schemes', 'social_security_schemes_2',
                       'social_security_claims', 'social_security_claims_2',
                       'apy', 'apy_2', 'pmsby', 'pmsby_2', 'pmjjby', 'pmjjby_2'],
        'metrics': [
            {'field': 'enrolment_under_pmsby',
             'fallbacks': ['pmsby_enrolment', 'pmsby_enrolment_current', 'pmsby_cumml_no',
                           'pmsby_no', 'total_no_of_pmsby',
                           'eligible_cases_under_pmsby', 'renewals_under_pmsby',
                           'pmsby_sourced', 'total_no_of_enrolment_under_pmsby']},
            {'field': 'enrolment_under_pmjjby',
             'fallbacks': ['pmjjby_enrolment', 'pmjjby_enrolment_current', 'pmjjby_cumml_no',
                           'pmjjby_no', 'total_no_of_pmjjby',
                           'eligible_cases_under_pmjjby', 'renewals_under_pmjjby',
                           'pmjjby_sourced', 'total_no_of_enrolment_under_pmjjby']},
            {'field': 'enrolment_under_apy',
             'fallbacks': ['apy_enrolment', 'apy_cumml_no', 'apy_no', 'total_no_of_apy',
                           'cumulative_apy_accounts_opened_since_inception',
                           'apy_accounts_opened_in_current_fy',
                           'apy_accounts_opened_in_current_fy_2024_25',
                           'apy_accounts_opened_in_current_fy_2025_26',
                           'apy_cumulative', 'apy_opened_fy',
                           'apy_current_fy_achievement',
                           'aapb_achieved_in_current_fy']},
            {'field': 'total_enrolment_no',
             'fallbacks': ['total_enrolment_uner_social_security_schemes']},
        ],
    },
    'pmegp': {
        'categories': ['pmegp', 'pmegp_2', 'pmegp_3', 'pmegp_4', 'pmegp_outstanding'],
        'metrics': [
            {'field': 'cy_disbursed_no',
             'fallbacks': ['disbursed', 'cy_disbursed_a_c_no', 'disbursement_no',
                           'mm_disbursed_no_of_prj', 'pmegp_mm_disbursed_no',
                           'pmegp_sanctioned_no', 'achievement_mm_disbursed_no',
                           'achievement_no_wise',
                           'disbursement_made_by_nodal_branches_no_of']},
            {'field': 'cy_disbursed_amt',
             'fallbacks': ['disbursement_amt', 'cy_sanction_amt', 'sanction',
                           'pmegp_mm_disbursed_amt', 'pmegp_sanctioned_mm',
                           'pmegp_mm_claimed_amt']},
            {'field': 'os_no',
             'fallbacks': ['pmegp_o_s_no', 'cy_sanction_no', 'no',
                           'pmegp_pending_no']},
            {'field': 'os_amt',
             'fallbacks': ['pmegp_o_s_amt', 'amt', 'pmegp_pending_amt']},
            {'field': 'npa_pct',
             'fallbacks': ['pmegp_npa_pct']},
        ],
    },
    'housing_pmay': {
        'categories': ['housing_pmay', 'housing_pmay_2', 'housing_pmay_p2',
                       'housing_finance', 'housing_loan'],
        'metrics': [
            {'field': 'rural_housing_loan_o_s_no',
             'fallbacks': ['rural_number', 'rural_no']},
            {'field': 'rural_housing_loan_o_s_amt',
             'fallbacks': ['rural_amt']},
            {'field': 'pmay_o_s_no',
             'fallbacks': ['current_year_disbursed_under_pmay_no']},
            {'field': 'pmay_o_s_amt',
             'fallbacks': ['current_year_disbursed_under_pmay_amt']},
            {'field': 'housing_loan_ps_o_s_no',
             'fallbacks': ['total_number', 'housing_loan_eligible_under_pmay_o_s_no']},
            {'field': 'housing_loan_ps_o_s_amt',
             'fallbacks': ['total_amt', 'housing_loan_eligible_under_pmay_o_s_amt']},
        ],
    },
    'sui': {
        'categories': ['sui', 'sui_2', 'stand_up_india', 'stand_up_india_2',
                       'stand_up_india_p2'],
        'metrics': [
            {'field': 'no_of_female_account',
             'fallbacks': ['current_year_no_of_female_account', 'female_account_no']},
            {'field': 'sui_o_s_no',
             'fallbacks': ['total_current_year_sui_disb_no', 'sui_npa_no', 'sanctioned_no',
                           'total_no_of_a_cs']},
            {'field': 'sui_o_s_amt',
             'fallbacks': ['total_current_year_sui_disb_amt', 'sanctioned_amt',
                           'disbursement_amt', 'disbursed_amt', 'sumof_female_amt',
                           'sum_of_female_amt', 'current_year_sum_of_female_amt']},
            {'field': 'sui_npa_pct', 'fallbacks': []},
        ],
    },
    'sc_st_finance': {
        'categories': ['sc_st_finance', 'sc_st_finance_2', 'sc_st_finance_p2',
                       'sc_st_lending', 'sc_st_loans', 'weaker_section', 'weaker_section_os'],
        'metrics': [
            {'field': 'sc_disbursement_no',
             'fallbacks': ['sc_disb_no', 'scheduled_castes_no', 'sc_disb_accounts',
                           'sc_applications_no']},
            {'field': 'sc_disbursement_amt',
             'fallbacks': ['sc_disb_amt', 'scheduled_castes_amt']},
            {'field': 'st_disbursement_no',
             'fallbacks': ['st_disb_no', 'scheduled_tribes_no', 'st_disb_accounts']},
            {'field': 'st_disbursement_amt',
             'fallbacks': ['st_disb_amt', 'scheduled_tribes_amt']},
            {'field': 'sc_outstanding_no',
             'fallbacks': ['sc_o_s_no', 'sc_os_accounts']},
            {'field': 'st_outstanding_no',
             'fallbacks': ['st_o_s_no', 'st_os_accounts']},
        ],
    },
    'women_finance': {
        'categories': ['women_finance', 'women_finance_2', 'women_finance_p2'],
        'metrics': [
            {'field': 'o_s_no',
             'fallbacks': ['cy_disb_no', 'outstanding_loans_to_women_a_c',
                           'outstanding_loans_to_women_a_cs', 'individual_women_a_cs',
                           'disb_no', 'disbursement_no']},
            {'field': 'o_s_amt',
             'fallbacks': ['cy_disb_amt', 'amt', 'amount',
                           'disb_amt', 'disbursement_amt']},
            {'field': 'cy_disb_no',
             'fallbacks': ['loans_disbursed_to_women_a_c', 'loans_disbursed_to_women_a_cs',
                           'disb_no']},
            {'field': 'cy_disb_amt',
             'fallbacks': ['disb_amt']},
        ],
    },
    'education_loan': {
        'categories': ['education_loan', 'education_loan_2'],
        'metrics': [
            {'field': 'sanctioned_no',
             'fallbacks': ['disb_no', 'disb_number', 'o_s_no', 'outstanding_no',
                           'eduloan_priority_ach_accounts', 'eduloan_total_ach_accounts',
                           'eduloan_priority_target_accounts',
                           'eduloan_total_target_accounts']},
            {'field': 'sanctioned_amt',
             'fallbacks': ['disb_amt', 'o_s_amt', 'amt', 'amount', 'outstanding_amt',
                           'eduloan_priority_ach_amt', 'eduloan_total_ach_amt',
                           'eduloan_priority_target_amt', 'eduloan_total_target_amt']},
            {'field': 'of_which_girl_student_disb_no',
             'fallbacks': ['of_which_girl_student_sanctioned_no',
                           'of_which_girl_student_o_s_no']},
            {'field': 'of_which_girl_student_disb_amt',
             'fallbacks': ['of_which_girl_student_sanctioned_amt',
                           'of_which_girl_student_o_s_amt']},
        ],
    },
    'pmmy_mudra_disbursement': {
        'categories': ['pmmy_mudra_disbursement', 'pmmy_mudra_disbursement_2',
                       'pmmy_mudra_os_npa', 'pmmy_mudra', 'pmmy', 'mudra', 'mudra_2',
                       'mudra_outstanding'],
        'metrics': [
            {'field': 'sishu_no',
             'fallbacks': ['shishu_no', 'cy_sishu_no', 'sishu_o_s_no', 'sishu',
                           'pmmy_shishu_ac', 'mudra_shishu_accounts']},
            {'field': 'sishu_amt',
             'fallbacks': ['shishu_amt', 'sishu_o_s_amt',
                           'pmmy_shishu_amt', 'mudra_shishu_amt']},
            {'field': 'kishore_no',
             'fallbacks': ['kishor_no', 'cy_kishore_no', 'kishore_o_s_no', 'kishore',
                           'pmmy_kishore_ac', 'mudra_kishore_accounts',
                           'kishore_no_of_a_cs']},
            {'field': 'kishore_amt',
             'fallbacks': ['kishor_amt', 'kishore_o_s_amt',
                           'pmmy_kishore_amt', 'mudra_kishore_amt']},
            {'field': 'tarun_no',
             'fallbacks': ['cy_tarun_no', 'tarun_o_s_no', 'tarun_plus_no', 'tarun',
                           'pmmy_tarun_ac', 'mudra_tarun_accounts']},
            {'field': 'tarun_amt',
             'fallbacks': ['tarun_o_s_amt', 'tarun_amt_plus',
                           'pmmy_tarun_amt', 'mudra_tarun_amt']},
            {'field': 'total_mudra_disb_no',
             'fallbacks': ['total_mudra_o_s_no', 'total_mudra_no', 'total_mudra',
                           'pmmy_total_ac', 'mudra_total_accounts']},
            {'field': 'total_mudra_disb_amt',
             'fallbacks': ['total_mudra_o_s_amt', 'total_o_s_amt',
                           'mudra_total_disbursed', 'mudra_total_sanctioned',
                           'pmmy_total_amt', 'disbursement_amt']},
        ],
    },
}


def normalize_district(name: str) -> str:
    if not name:
        return ''
    out = name.strip()
    # collapse newlines / multi-space
    out = re.sub(r'\s+', ' ', out)
    return out


def resolve_value(record: dict, indicator_def: dict, field: str, fallbacks: list[str]):
    """Try every (category, field|fallback) combination on the flat record."""
    fields = [field] + (fallbacks or [])
    for cat in indicator_def['categories']:
        for f in fields:
            key = f'{cat}__{f}'
            v = record.get(key)
            if v is not None and v != '':
                return v
    return None


def load_state_data(state_slug: str) -> dict:
    """Return {quarter_code: {district_name: {field_key: value}}} for one state.

    Uses _fi_timeseries.json which has already-flattened category__field keys.
    """
    path = os.path.join(STATES_DIR, state_slug, f'{state_slug}_fi_timeseries.json')
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        ts = json.load(f)
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for period in ts.get('periods', []):
        qcode = normalize_period(period.get('period', ''))
        if not qcode:
            continue
        for d in period.get('districts', []):
            dname = normalize_district(d.get('district', ''))
            if not dname:
                continue
            # Strip out the bookkeeping keys
            rec = {k: v for k, v in d.items() if k not in ('district', 'period')}
            out[qcode][dname] = rec
    return out


def list_state_slugs() -> list[str]:
    return sorted([
        d for d in os.listdir(STATES_DIR)
        if os.path.isdir(os.path.join(STATES_DIR, d)) and not d.startswith('_')
        and os.path.exists(os.path.join(STATES_DIR, d, f'{d}_fi_timeseries.json'))
    ])


def regenerate_indicator(indicator_key: str, indicator_def: dict,
                          all_state_data: dict, preserve_phonepe: bool) -> tuple[int, int]:
    """Rebuild every quarter file for one indicator.

    Returns (files_written, districts_total).
    """
    out_dir = os.path.join(OUT_DIR, indicator_key)
    os.makedirs(out_dir, exist_ok=True)

    # Gather all quarter codes seen across states
    quarters: set[str] = set()
    for state_slug, qdata in all_state_data.items():
        quarters.update(qdata.keys())

    files_written = 0
    districts_total = 0
    for qcode in sorted(quarters, reverse=True):
        rows = []
        seen = set()
        for state_slug, qdata in all_state_data.items():
            quarter_records = qdata.get(qcode, {})
            for dname, record in quarter_records.items():
                entry = {'district': dname, 'state': state_slug}
                has_any = False
                for metric in indicator_def['metrics']:
                    v = resolve_value(record, indicator_def,
                                      metric['field'], metric.get('fallbacks', []))
                    if v is not None:
                        entry[metric['field']] = v
                        has_any = True
                if has_any:
                    key = (state_slug, dname.upper())
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(entry)

        # For digital_transactions: merge with existing PhonePe transaction_*
        # values from the existing file so we don't drop those.
        if preserve_phonepe and indicator_key == 'digital_transactions':
            existing_path = os.path.join(out_dir, f'{qcode}.json')
            if os.path.exists(existing_path):
                with open(existing_path) as f:
                    prev = json.load(f)
                # index previous entries by (state, district upper)
                prev_idx = {}
                for r in prev.get('districts', []):
                    prev_idx[(r.get('state'), str(r.get('district', '')).upper())] = r
                # add transaction_count/_amount to existing rows
                new_idx = {(r['state'], r['district'].upper()): r for r in rows}
                for k, prev_r in prev_idx.items():
                    txn_keys = {kk: vv for kk, vv in prev_r.items()
                                if kk in ('transaction_count', 'transaction_amount')}
                    if not txn_keys:
                        continue
                    if k in new_idx:
                        new_idx[k].update(txn_keys)
                    else:
                        merged = {'district': prev_r['district'], 'state': prev_r['state']}
                        merged.update(txn_keys)
                        rows.append(merged)
                        new_idx[k] = merged

        if not rows:
            continue

        rows.sort(key=lambda r: (r['state'], r['district']))
        out = {
            'indicator': indicator_key,
            'quarter': qcode,
            'label': format_quarter_label(qcode),
            'districts': rows,
        }
        path = os.path.join(out_dir, f'{qcode}.json')
        with open(path, 'w') as f:
            json.dump(out, f, separators=(',', ':'), ensure_ascii=False)
        files_written += 1
        districts_total += len(rows)

    return files_written, districts_total


def main():
    slugs = list_state_slugs()
    print(f'Loading data for {len(slugs)} states...')
    state_data: dict[str, dict] = {}
    for s in slugs:
        state_data[s] = load_state_data(s)

    # Total quarter coverage
    all_quarters: set[str] = set()
    for qd in state_data.values():
        all_quarters.update(qd.keys())
    print(f'  → {len(all_quarters)} distinct quarters across states')

    indicators = sys.argv[1:] if len(sys.argv) > 1 else list(INDICATORS.keys())

    for ind in indicators:
        if ind not in INDICATORS:
            print(f'Skip unknown indicator: {ind}')
            continue
        files, districts = regenerate_indicator(ind, INDICATORS[ind], state_data,
                                                 preserve_phonepe=True)
        print(f'{ind:30s}: {files:3d} files, {districts:6d} district-rows')


if __name__ == '__main__':
    main()
