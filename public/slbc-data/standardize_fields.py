#!/usr/bin/env python3
"""
Standardize field/column names across all 8 NE Indian states' SLBC data
so cross-state comparison is possible.

Addresses 5 systemic issues:
  1. Manipur spacing/merged-word errors
  2. Meghalaya reversed word order
  3. Abbreviation inconsistencies
  4. Typos and spelling errors
  5. Singular/plural standardization

Updates ALL data formats:
  - *_fi_timeseries.csv  (snake_case category__field columns)
  - *_fi_timeseries.json (snake_case category__field keys)
  - *_complete.json      (human-readable field keys in district data)
  - quarterly/YYYY-MM/*.csv (human-readable column headers)
"""

import csv
import io
import json
import os
import re
import sys
from collections import defaultdict, Counter
from pathlib import Path

BASE_DIR = Path(__file__).parent
STATES = ['assam', 'meghalaya', 'manipur', 'arunachal-pradesh', 'mizoram', 'tripura', 'nagaland', 'sikkim']

# ─── Statistics tracking ───
stats = {
    'manipur_spacing': 0,
    'meghalaya_reorder': 0,
    'abbreviation': 0,
    'typo': 0,
    'singular_plural': 0,
    'merges': 0,
    'renames_per_state': defaultdict(int),
    'fields_before': defaultdict(int),
    'fields_after': defaultdict(int),
}


def to_snake(s):
    """Convert human-readable field name to snake_case."""
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = s.strip('_')
    return s


# ═══════════════════════════════════════════════════════════════════════
# ISSUE 1: Manipur spacing/merged-word fixes (snake_case level)
# ═══════════════════════════════════════════════════════════════════════

MANIPUR_SNAKE_FIXES = {
    'noofoperative_casa': 'no_of_operative_casa',
    'number_ofoperative_casa': 'number_of_operative_casa',
    'noofcoveredvillages': 'no_of_covered_villages',
    'noofuncoveredvillages': 'no_of_uncovered_villages',
    'total_noofcoveredvillages': 'total_no_of_covered_villages',
    'noofwomen_shgs': 'no_of_women_shgs',
    'no_ofhouse_holds': 'no_of_households',
    'no_ofkcc': 'no_of_kcc',
    'total_no_ofkcc': 'total_no_of_kcc',
    'of_householdscovered': 'of_households_covered',
    'loanstoweaker': 'loans_to_weaker',
    'loanstoweaker_a_c': 'loans_to_weaker_a_c',
    'loanstoweaker_no': 'loans_to_weaker_no',
    'no_of_male_accountto_sc': 'no_of_male_account_to_sc',
    'no_of_male_accountto_st': 'no_of_male_account_to_st',
    'sumof_male_amountto_sc': 'sum_of_male_amount_to_sc',
    'sumof_male_amountto_st': 'sum_of_male_amount_to_st',
    'current_year_no_of_male_accountto_sc': 'current_year_no_of_male_account_to_sc',
    'current_year_no_of_male_accountto_st': 'current_year_no_of_male_account_to_st',
    'current_year_sumof_male_amountto_sc': 'current_year_sum_of_male_amount_to_sc',
    'current_year_sumof_male_amountto_st': 'current_year_sum_of_male_amount_to_st',
    'ofwhichgirlstudent_disb_amt': 'of_which_girl_student_disb_amt',
    'ofwhichgirlstudent_disb_no': 'of_which_girl_student_disb_no',
    'ofwhichgirlstudent_o_s_amt': 'of_which_girl_student_o_s_amt',
    'ofwhichgirlstudent_o_s_no': 'of_which_girl_student_o_s_no',
    'ofwhichgirlstudent_sanctioned_amt': 'of_which_girl_student_sanctioned_amt',
    'ofwhichgirlstudent_sanctioned_no': 'of_which_girl_student_sanctioned_no',
    'enrolmentunder_apy': 'enrolment_under_apy',
    'enrolmentunder_pmjjby': 'enrolment_under_pmjjby',
    'enrolmentunder_pmsby': 'enrolment_under_pmsby',
    'renewalsunder_pmjjby': 'renewals_under_pmjjby',
    'renewalsunder_pmsby': 'renewals_under_pmsby',
    'othersunder_msmes_a_c': 'others_under_msmes_a_c',
    'othersunder_msmes_amt': 'others_under_msmes_amt',
    'othersunder_msmes_no': 'others_under_msmes_no',
    'othersunder_no': 'others_under_no',
    'housing_loan_eligibleunder_pmay_o_s_amt': 'housing_loan_eligible_under_pmay_o_s_amt',
    'housing_loan_eligibleunder_pmay_o_s_no': 'housing_loan_eligible_under_pmay_o_s_no',
    'rupay_cardactivein_pmjdy': 'rupay_card_active_in_pmjdy',
    'rupay_cardissuedin_kcc': 'rupay_card_issued_in_kcc',
    'sumof_female_amt': 'sum_of_female_amt',
    'current_year_sumof_female_amt': 'current_year_sum_of_female_amt',
    'tota_l_o_s_a_c': 'total_o_s_a_c',
    'tota_l_sanc_a_c': 'total_sanc_a_c',
    'cy_ki_shor_e_amt': 'cy_kishore_amt',
    'cy_kish_ore_no': 'cy_kishore_no',
    'cy_sis_hu_amt': 'cy_sishu_amt',
    'cy_ta_run_amt': 'cy_tarun_amt',
    'cy_taru_n_no': 'cy_tarun_no',
    'dateof_dcc_meeting_1st_qtr': 'date_of_dcc_meeting_1st_qtr',
    'datesof_dlrc_meeting_1st_qtr': 'dates_of_dlrc_meeting_1st_qtr',
    'duringthe_quarter_credit_linked': 'during_the_quarter_credit_linked',
    'duringthe_quarter_credit_linked_amt': 'during_the_quarter_credit_linked_amt',
    'duringthe_quarter_credit_linked_no': 'during_the_quarter_credit_linked_no',
    'duringthe_quarter_savings_linked': 'during_the_quarter_savings_linked',
    'duringthe_quarter_savings_linked_amt': 'during_the_quarter_savings_linked_amt',
    'duringthe_quarter_savings_linked_no': 'during_the_quarter_savings_linked_no',
    'no_of_shgsformed': 'no_of_shgs_formed',
    'no_of_shgstakenupeconomicactivities': 'no_of_shgs_taken_up_economic_activities',
    'smalland_marginal_farmers_no': 'small_and_marginal_farmers_no',
    'smalland_marginal_farmers_amt': 'small_and_marginal_farmers_amt',
    'smalland_marginal_no': 'small_and_marginal_no',
    'minoritycommunities_no': 'minority_communities_no',
    'minoritycommunities_amt': 'minority_communities_amt',
    'womenbeneficiaries_no': 'women_beneficiaries_no',
    'womenbeneficiaries_amt': 'women_beneficiaries_amt',
    'targetfor_individual_enterprises': 'target_for_individual_enterprises',
    'targetfor_shg_bank_linkage': 'target_for_shg_bank_linkage',
    'outstandingamount': 'outstanding_amount',
    'ah_outstandingamount': 'ah_outstanding_amount',
    'fishery_outstandingamount': 'fishery_outstanding_amount',
    'current_year_number_of_cardsissued': 'current_year_number_of_cards_issued',
    'o_s_position_number_of_cardsissued': 'o_s_position_number_of_cards_issued',
    'farm_productionamt': 'farm_production_amt',
    'farm_mechanisationn_no': 'farm_mechanisation_no',
    'dairyno': 'dairy_no',
    'kishoreno': 'kishore_no',
    'sishuamt': 'sishu_amt',
    'kccsfor_ah_and_allied_activities_no': 'kccs_for_ah_and_allied_activities_no',
    'kccsfor_ah_and_allied_activities_amt': 'kccs_for_ah_and_allied_activities_amt',
    'kccsfor_ah_and_no': 'kccs_for_ah_and_no',
    'kccsfor_ah_no': 'kccs_for_ah_no',
    'rupaycard_issued': 'rupay_card_issued',
    'total_otherpriority_no': 'total_other_priority_no',
    'name_of_villagewithpopulation_5000': 'name_of_village_with_population_5000',
    'sep_gno': 'sep_g_no',
    'business_figureason_31_03_2019_deposit': 'business_figures_on_31_03_2019_deposit',
    'amountof_cases_addduringthe_quarter': 'amount_of_cases_add_during_the_quarter',
    'amountof_casessettledduringthequarter': 'amount_of_cases_settled_during_the_quarter',
    'amountof_pending_cases_atthe_beginning_ofthe_quarter': 'amount_of_pending_cases_at_the_beginning_of_the_quarter',
    'amountof_pending_casesattheclaseofthe_quarter': 'amount_of_pending_cases_at_the_close_of_the_quarter',
    'number_of_cases_settledduring_the_quarter': 'number_of_cases_settled_during_the_quarter',
    'number_of_casesaddduring_the_quarter': 'number_of_cases_add_during_the_quarter',
    'number_of_pending_cases_atthe_beginning_ofthe_quarter': 'number_of_pending_cases_at_the_beginning_of_the_quarter',
    'number_of_pending_casesatthecloseofthe_quarter': 'number_of_pending_cases_at_the_close_of_the_quarter',
}

# Human-readable versions of Manipur fixes (for quarterly CSVs and complete.json)
MANIPUR_HR_FIXES = {
    'Number ofoperative CASA': 'Number of Operative CASA',
    'Noofoperative CASA': 'No. of Operative CASA',
    'Noofcoveredvillages': 'No. of Covered Villages',
    'Noofuncoveredvillages': 'No. of Uncovered Villages',
    'Total Noofcoveredvillages': 'Total No. of Covered Villages',
    'Noofwomen SHGs': 'No. of Women SHGs',
    'Loanstoweaker A/C': 'Loans to Weaker A/C',
    'Loanstoweaker No.': 'Loans to Weaker No.',
    'Loanstoweaker No': 'Loans to Weaker No.',
    'ofwhichgirlstudent Disb Amt': 'Of Which Girl Student Disb Amt',
    'ofwhichgirlstudent Disb No.': 'Of Which Girl Student Disb No.',
    'ofwhichgirlstudent O/S Amt': 'Of Which Girl Student O/S Amt',
    'ofwhichgirlstudent O/S No.': 'Of Which Girl Student O/S No.',
    'ofwhichgirlstudent Sanctioned Amt': 'Of Which Girl Student Sanctioned Amt',
    'ofwhichgirlstudent Sanctioned No.': 'Of Which Girl Student Sanctioned No.',
    'Enrolmentunder APY': 'Enrolment Under APY',
    'Enrolmentunder PMJJBY': 'Enrolment Under PMJJBY',
    'Enrolmentunder PMSBY': 'Enrolment Under PMSBY',
    'renewalsunder PMJJBY': 'Renewals Under PMJJBY',
    'renewalsunder PMSBY': 'Renewals Under PMSBY',
    'Othersunder MSMEs A/C': 'Others Under MSMEs A/C',
    'Othersunder MSMEs Amt': 'Others Under MSMEs Amt',
    'Othersunder MSMEs No.': 'Others Under MSMEs No.',
    'Othersunder No.': 'Others Under No.',
    'Rupay Cardactivein PMJDY': 'Rupay Card Active in PMJDY',
    'Rupay Cardissuedin KCC': 'Rupay Card Issued in KCC',
    'Duringthe Quarter Credit Linked': 'During the Quarter Credit Linked',
    'Duringthe Quarter Credit Linked Amt': 'During the Quarter Credit Linked Amt',
    'Duringthe Quarter Credit Linked No.': 'During the Quarter Credit Linked No.',
    'Duringthe Quarter Savings Linked': 'During the Quarter Savings Linked',
    'Duringthe Quarter Savings Linked Amt': 'During the Quarter Savings Linked Amt',
    'Duringthe Quarter Savings Linked No.': 'During the Quarter Savings Linked No.',
    'No. of SHGsformed': 'No. of SHGs Formed',
    'No. of SHGstakenupeconomicactivities': 'No. of SHGs Taken Up Economic Activities',
    'Smalland Marginal Farmers No.': 'Small and Marginal Farmers No.',
    'Smalland Marginal Farmers Amt': 'Small and Marginal Farmers Amt',
    'Smalland Marginal No.': 'Small and Marginal No.',
    'Minoritycommunities No.': 'Minority Communities No.',
    'Minoritycommunities Amt': 'Minority Communities Amt',
    'Womenbeneficiaries No.': 'Women Beneficiaries No.',
    'Womenbeneficiaries Amt': 'Women Beneficiaries Amt',
    'Targetfor Individual Enterprises': 'Target for Individual Enterprises',
    'Targetfor SHG Bank Linkage': 'Target for SHG Bank Linkage',
    'KCCSfor AH and Allied Activities No.': 'KCCS for AH and Allied Activities No.',
    'KCCSfor AH and Allied Activities Amt': 'KCCS for AH and Allied Activities Amt',
    'KCCSfor AH and No.': 'KCCS for AH and No.',
    'KCCSfor AH No.': 'KCCS for AH No.',
    'Dateof DCC Meeting 1st Qtr': 'Date of DCC Meeting 1st Qtr',
    'Datesof DLRC Meeting 1st Qtr': 'Dates of DLRC Meeting 1st Qtr',
}


# ═══════════════════════════════════════════════════════════════════════
# ISSUE 2: Meghalaya reversed word order (snake_case)
# ═══════════════════════════════════════════════════════════════════════

MEGHALAYA_SNAKE_FIXES = {
    # credit_deposit_ratio
    'cd_ratio_overall': 'overall_cd_ratio',
    'cd_ratio_rural': 'cdr_rural',
    'cd_ratio_semi_urban': 'cdr_semi_urban',
    'cd_ratio_urban': 'cdr_urban',
    'advances_rural': 'adv_rural',
    'advances_semi_urban': 'adv_semi_urban',
    'advances_urban': 'adv_urban',
    'deposits_semi_urban': 'dep_semi_urban',
    'deposits_urban': 'dep_urban',
    'total_deposits': 'total_deposit',

    # acp_disbursement_agri
    'crop_amt_loan': 'crop_loan_amt',
    'loan_crop_a_c': 'crop_loan_a_c',
    'a_c_nos_plantation_horticulture': 'plantation_horticulture_a_c_no',
    'a_c_wasteland_forestry_nos_and_dev': 'forestry_and_wasteland_dev_a_c_no',
    'amt_wasteland_forestry_and_dev': 'forestry_and_wasteland_dev_amt',
    'water_amount_resource': 'water_resource_amt',

    # acp_disbursement_msme
    'kvic_term_loan_a_c': 'kvic_tl_a_c',
    'kvic_term_loan_amt': 'kvic_tl_amt',
    'kvic_working_capital_a_c': 'kvic_wc_a_c',
    'kvic_working_capital_amt': 'kvic_wc_amt',
    'medium_term_loan_a_c': 'medium_tl_a_c',
    'medium_term_loan_amt': 'medium_tl_amt',
    'medium_working_capital_a_c': 'medium_wc_a_c',
    'medium_working_capital_amt': 'medium_wc_amt',
    'micro_term_loan_a_c': 'micro_tl_a_c',
    'micro_term_loan_amt': 'micro_tl_amt',
    'micro_working_capital_a_c': 'micro_wc_a_c',
    'micro_working_capital_amt': 'micro_wc_amt',
    'small_term_loan_a_c': 'small_tl_a_c',
    'small_term_loan_amt': 'small_tl_amt',
    'small_working_capital_a_c': 'small_wc_a_c',
    'small_working_capital_amt': 'small_wc_amt',
    'total_msme_disbursement_amt_ps': 'total_msme_ps_disb_amt',
    'total_msme_disbursement_no_ps': 'total_msme_ps_disb_no',

    # acp_disbursement_non_ps
    'a_c_nps_education': 'education_nps_a_c',
    'a_c_nps_others': 'others_nps_a_c',
    'agriculture_amt_nps': 'agriculture_nps_amt',
    'agriculture_no_nps': 'agriculture_nps_no',
    'amt_nps_education': 'education_nps_amt',
    'education_a_c_nps': 'education_nps_a_c',
    'housing_a_c_nps': 'housing_nps_a_c',
    'housing_amt_nps': 'housing_nps_amt',
    'msme_amt_nps': 'msme_nps_amt',
    'msme_no_nps': 'msme_nps_no',
    'personal_loans_a_c_nps': 'personal_loans_under_nps_a_c',
    'personal_loans_amt_nps': 'personal_loans_under_nps_amt',
    'total_acp_disbursement_amt_nps': 'total_acp_nps_disb_amt',
    'total_acp_disbursement_no_nps': 'total_acp_nps_disb_no',

    # acp_disbursement_other_ps
    'education_a_c_ps': 'education_ps_a_c',
    'housing_a_c_ps': 'housing_ps_a_c',
    'housing_amt_ps': 'housing_ps_amt',
    'total_other_ps_disbursement_amt': 'total_other_ps_disb_amt',
    'total_other_ps_disbursement_no': 'total_other_ps_disb_no',
    'weaker_section_loans': 'loans_to_weaker',
    'weaker_section_loans_amt': 'loans_to_weaker_amt',
    'weaker_section_loans_no': 'loans_to_weaker_no',

    # acp_priority_sector_os_npa
    'agri_amt_infra': 'agri_infra_amt',
    'agri_no_infra': 'agri_infra_no',
    'agri_amt_npa': 'agri_npa_amt',
    'amt_ancillary': 'ancillary_amt',
    'crop_farm_amt_credit': 'farm_credit_crop_amt',
    'farm_crop_no_credit': 'farm_credit_crop_no',
    'term_farm_amt_loan_credit': 'farm_credit_term_loan_amt',
    'term_farm_no_loan_credit': 'farm_credit_term_loan_no',
    'out_allied_credit_of_amt_total_farm': 'out_of_farm_credit_total_allied_amt',
    'out_allied_credit_of_no_total_farm': 'out_of_farm_credit_total_allied_no',
    'amt_npa_pct_msme': 'msme_npa_pct',
    'total_agri_npa_amt_ps': 'total_agri_ps_npa_amt',
    'total_agri_npa_no_ps': 'total_agri_ps_npa_no',
    'total_agri_o_s_amt_ps': 'total_agri_ps_o_s_amt',
    'total_agri_o_s_no_ps': 'total_agri_ps_o_s_no',
    'total_msme_npa_amt_ps': 'total_msme_ps_npa_amt',
    'total_msme_npa_no_ps': 'total_msme_ps_npa_no',
    'total_msme_o_s_amt_ps': 'total_msme_ps_o_s_amt',
    'total_msme_o_s_no_ps': 'total_msme_ps_o_s_no',
    'other_ps_total_npa_amt': 'total_other_ps_npa_amt',
    'other_ps_total_npa_no': 'total_other_ps_npa_no',

    # acp_target_achievement
    'agri_achieved_no_ps': 'agri_ps_achieved_no',
    'agri_amount_achieved_ps': 'agri_ps_achieved_amt',
    'agri_target_amount_ps': 'agri_ps_target_amt',
    'agri_target_no_ps': 'agri_ps_target_no',
    'amount_achievement_pct_agri_ps': 'agri_ps_achievement_pct_amt',
    'crop_amount_achieved_loan': 'crop_loan_achieved_amt',
    'crop_amount_achievement_pct_loan': 'crop_loan_achievement_pct_amt',
    'crop_target_amount_loan': 'crop_loan_target_amt',
    'msme_target_no_ps': 'msme_ps_target_no',
    'ps_amount_msme_target': 'msme_ps_target_amt',

    # agri_outstanding
    'farm_crop_credit_amt': 'farm_credit_crop_amt',
    'farm_crop_credit_no': 'farm_credit_crop_no',
    'farm_term_loan_credit_amt': 'farm_credit_term_loan_amt',
    'farm_term_loan_credit_no': 'farm_credit_term_loan_no',
    'amt_ah_allied_kccs_and_activities_for': 'kccs_for_ah_and_allied_activities_amt',
    'ah_allied_activities_kccs_no': 'kccs_for_ah_and_allied_activities_no',
    'amt_clinic': 'clinic_amt',
    'amt_dairy': 'dairy_amt',
    'amt_farm_mechanisation': 'farm_mechanisation_amt',
    'amt_fisheries': 'fisheries_amt',
    'amt_godown': 'godown_amt',
    'amt_other': 'other_amt',
    'amt_poultry': 'poultry_amt',
    'no_farm_mechanisation': 'farm_mechanisation_no',
    'no_godown': 'godown_no',
    'total_agri_o_s_amt': 'agri_total_o_s_amt',
    'total_agri_o_s_no': 'agri_total_o_s_no',

    # digital_transactions
    'debit_credit_cards_a_c': 'cards_debit_credit_a_c',
    'debit_credit_cards_amt': 'cards_debit_credit_amt',

    # fi_kcc
    'active_rupay_card_in_pmjdy': 'rupay_card_active_in_pmjdy',

    # education_loan
    'disbursed_amt': 'disb_amt',
    'disbursed_no': 'disb_no',
    'education_loan_amt_ps': 'education_ps_amt',
    'education_loan_no_ps': 'education_ps_no',
    'girl_student_disbursed_amt': 'of_which_girl_student_disb_amt',
    'girl_student_disbursed_no': 'of_which_girl_student_disb_no',
    'girl_student_outstanding_amt': 'of_which_girl_student_o_s_amt',
    'girl_student_outstanding_no': 'of_which_girl_student_o_s_no',
    'girl_student_sanctioned_amt': 'of_which_girl_student_sanctioned_amt',
    'girl_student_sanctioned_no': 'of_which_girl_student_sanctioned_no',
    'housing_loan_amt_nps': 'housing_nps_amt',
    'housing_loan_amt_ps': 'housing_ps_amt',
    'housing_loan_no_nps': 'housing_nps_no',
    'housing_loan_no_ps': 'housing_ps_no',
    'total_non_priority_sector_npa_amt': 'total_non_priority_npa_amt',
    'total_non_priority_sector_npa_no': 'total_non_priority_npa_no',

    # housing_pmay
    'housing_loan_o_s_amt_nps': 'housing_loan_nps_o_s_amt',
    'housing_loan_o_s_amt_ps': 'housing_loan_ps_o_s_amt',
    'housing_loan_o_s_no_nps': 'housing_loan_nps_o_s_no',
    'housing_loan_o_s_no_ps': 'housing_loan_ps_o_s_no',
    'pmay_current_year_disbursed_amt': 'current_year_disbursed_under_pmay_amt',
    'pmay_current_year_disbursed_no': 'current_year_disbursed_under_pmay_no',
    'pmay_eligible_housing_loan_o_s_amt': 'housing_loan_eligible_under_pmay_o_s_amt',
    'pmay_eligible_housing_loan_o_s_no': 'housing_loan_eligible_under_pmay_o_s_no',

    # investment_credit_agri_disbursement & outstanding
    'ah_allied_activities_kccs_amt': 'kccs_for_ah_and_allied_activities_amt',
    'total_ic_agri_disbursement_amt': 'total_ic_agri_disb_amt',
    'total_ic_agri_disbursement_no': 'total_ic_agri_disb_no',

    # jlg
    'current_year_disbursement_amt': 'cy_disbursement_amt',
    'current_year_disbursement_no': 'cy_disbursement_no',

    # msme_npa
    'total_msme_npa_amt_ps': 'total_msme_ps_npa_amt',
    'total_msme_npa_no_ps': 'total_msme_ps_npa_no',

    # msme_outstanding
    'total_msme_o_s_amt': 'msme_total_o_s_amt',
    'total_msme_o_s_no': 'msme_total_o_s_no',

    # non_ps_npa
    'loan_amt_personal': 'personal_loan_amt',
    'loan_no_personal': 'personal_loan_no',
    'total_non_priority_npa_amt': 'total_non_priority_npa_amt',
    'sec_tot_npa_non_no_priorityrityrity': 'total_non_priority_npa_no',

    # non_ps_outstanding
    'nps_amt_npa': 'nps_npa_amt',
    'tot_npa_priorityrityrity_no_sec_non': 'total_nps_npa_no',

    # nrlm
    'no_nrlm_npa': 'nrlm_npa_no',
    'self_help_group_current_year_amt': 'current_year_self_help_group_amt',
    'self_help_group_current_year_no': 'current_year_self_help_group_no',

    # nulm
    'nulm_current_year_total_disbursement_amt': 'total_current_year_nulm_disb_amt',
    'nulm_current_year_total_disbursement_no': 'total_current_year_nulm_disb_no',
    'no_ciary_beneficiary_of_shg': 'shg_no_of_beneficiary',
    'no_ciary_beneficiary_of_shg_women': 'women_shg_no_of_beneficiary',
    'no_sep_i': 'sep_i_no',
    'shg_beneficiary_no': 'shg_no_of_beneficiary',
    'women_shg_beneficiary_no': 'women_shg_no_of_beneficiary',

    # other_ps_npa
    'tot_ps_amt_npa_other': 'total_other_ps_npa_amt',
    'tot_ps_no_npa_other': 'total_other_ps_npa_no',

    # other_ps_outstanding
    'total_other_ps_o_s_amt': 'ops_total_o_s_amt',
    'total_other_ps_o_s_no': 'ops_total_o_s_no',

    # pmjdy
    'aadhaar_seeded_no': 'no_of_aadhaar_seeded',
    'deposits_held_in_a_c_amt': 'amt_deposits_held_in_the_a_c',
    'rupay_card_activated': 'no_of_rupay_card_activated',
    'rupay_card_issued_no': 'no_of_rupay_card_issued',
    'total_no_pmjdy': 'total_pmjdy_no',
    'zero_balance_a_c_no': 'no_of_zero_balance_a_c',

    # pmmy_mudra_disbursement
    'tarun_amt_plus': 'tarun_plus_amt',
    'total_mudra_disbursement_amt': 'total_mudra_disb_amt',
    'total_mudra_disbursement_no': 'total_mudra_disb_no',

    # pmmy_mudra_os_npa
    'amt_npa_sishu': 'sishu_npa_amt',
    'amt_o_s_sishu': 'sishu_o_s_amt',
    'no_npa_sishu': 'sishu_npa_no',
    'no_o_s_sishu': 'sishu_o_s_no',
    'npa_amt_mudra': 'mudra_npa_amt',

    # sc_st_finance
    'sc_disbursement_amt': 'sc_disb_amt',
    'sc_disbursement_no': 'sc_disb_no',
    'sc_outstanding_amt': 'sc_o_s_amt',
    'sc_outstanding_no': 'sc_o_s_no',
    'st_disbursement_amt': 'st_disb_amt',
    'st_disbursement_no': 'st_disb_no',
    'st_outstanding_amt': 'st_o_s_amt',
    'st_outstanding_no': 'st_o_s_no',

    # shg
    'credit_current_amount_fy_linked': 'current_fy_credit_linked_amt',
    'credit_during_amount_quarter_the_linked': 'during_the_quarter_credit_linked_amt',
    'credit_linked_amt_quarter': 'during_the_quarter_credit_linked_amt',
    'credit_linked_no_current_fy': 'current_fy_credit_linked_no',
    'credit_linked_no_cy': 'cy_credit_linked_no',
    'credit_linked_no_quarter': 'during_the_quarter_credit_linked_no',
    'linked_quarter_during_the_amount_savings': 'during_the_quarter_savings_linked_amt',
    'savings_current_amount_fy_linked': 'current_fy_savings_linked_amt',
    'savings_linked_amt_quarter': 'during_the_quarter_savings_linked_amt',
    'savings_linked_no_current_fy': 'current_fy_savings_linked_no',
    'savings_linked_no_cy': 'cy_savings_linked_no',
    'savings_linked_no_quarter': 'during_the_quarter_savings_linked_no',

    # social_security
    'apy_enrolment': 'enrolment_under_apy',
    'pmjjby_enrolment': 'enrolment_under_pmjjby',
    'pmsby_enrolment': 'enrolment_under_pmsby',
    'pmjjby_renewals': 'renewals_under_pmjjby',
    'pmsby_renewals': 'renewals_under_pmsby',
    'pmjjby_eligible_cases': 'eligible_cases_under_pmjjby',
    'pmsby_eligible_cases': 'eligible_cases_under_pmsby',

    # sui
    'female_account_amt': 'sum_of_female_amt',
    'female_account_amt_cy': 'current_year_sum_of_female_amt',
    'female_account_no': 'no_of_female_account',
    'female_account_no_cy': 'current_year_no_of_female_account',
    'sc_male_account_amt': 'sum_of_male_amount_to_sc',
    'sc_male_account_amt_cy': 'current_year_sum_of_male_amount_to_sc',
    'sc_male_account_no': 'no_of_male_account_to_sc',
    'sc_male_account_no_cy': 'current_year_no_of_male_account_to_sc',
    'st_male_account_amt': 'sum_of_male_amount_to_st',
    'st_male_account_amt_cy': 'current_year_sum_of_male_amount_to_st',
    'st_male_account_no': 'no_of_male_account_to_st',
    'st_male_account_no_cy': 'current_year_no_of_male_account_to_st',
    'sui_total_disbursement_amt_cy': 'total_current_year_sui_disb_amt',
    'sui_total_disbursement_no_cy': 'total_current_year_sui_disb_no',

    # minority
    'total_minority_disbursement_amt': 'total_minority_disb_amt',
    'total_minority_disbursement_no': 'total_minority_disb_no',
    'total_minority_o_s_loan_amt': 'total_loan_to_minority_o_s_amt',
    'total_minority_o_s_loan_no': 'total_loan_to_minority_o_s_no',

    # weaker_section_os
    'total_weaker_section_o_s_amt': 'total_weaker_sec_o_s_amt',
    'total_weaker_section_o_s_no': 'total_weaker_sec_o_s_no',
    'small_marginal_farmers_amt': 'small_and_marginal_farmers_amt',
    'small_marginal_farmers_no': 'small_and_marginal_farmers_no',

    # women_finance
    'cy_disbursed_amt': 'cy_disb_amt',
    'cy_disbursed_no': 'cy_disb_no',

    # kcc
    'total_kcc_o_s_amt': 'total_o_s_kcc_amt',
    'total_kcc_o_s_no': 'total_o_s_kcc_no',
    'kcc_animal_husbandry_disbursed_amt': 'kcc_for_animal_husbandry_amt',
    'kcc_animal_husbandry_issued_no_incl_renewal': 'kcc_animal_husbandry_issued_incl_renewal',
    'kcc_animal_husbandry_new_issued_no': 'kcc_ah_new_issued_no',
    'kcc_fishery_disbursed_amt': 'kcc_for_fishery_amt',
    'kcc_fishery_issued_no_incl_renewal': 'kcc_fisheries_issued_incl_renewal',

    # crop_insurance
    'loan_current_amount_year_achievement_crop': 'current_year_crop_loan_achievement_amt',

    # fi_village_banking
    'no_of_allotted_village': 'no_of_villages',
    'villages_with_banking_outlets': 'no_of_covered_villages',

    # rseti/ldm
    'name_s_ldm_of_counsellor_s_fl': 'name_s_of_fl_counsellor',
    'date_opening_of': 'date_of_opening',
    'no_s_contact': 'contact_no_s',
    'lead_name_bank': 'lead_bank_name',

    # pmegp
    'pmegp_disbursed_amt_cy': 'cy_disbursed_amt',
    'pmegp_disbursed_no_cy': 'cy_disbursed_no',
    'pmegp_sanction_amt_cy': 'cy_sanction_amt',
    'pmegp_sanction_no_cy': 'cy_sanction_no',
}

# Corresponding human-readable fixes for Meghalaya
MEGHALAYA_HR_FIXES = {
    'CD Ratio Overall': 'Overall CD Ratio',
    'Cd Ratio Overall': 'Overall CD Ratio',
    'Advances Rural': 'Adv Rural',
    'Advances Semi-Urban': 'Adv Semi-Urban',
    'Advances Urban': 'Adv Urban',
    'Deposits Semi-Urban': 'Dep Semi-Urban',
    'Deposits Urban': 'Dep Urban',
    'Total Deposits': 'Total Deposit',
    'Crop Amt Loan': 'Crop Loan Amt',
    'Loan Crop A/C': 'Crop Loan A/C',
    'A/C Nos Plantation horticulture &': 'Plantation Horticulture A/C No.',
    'A/C wasteland Forestry Nos and Dev': 'Forestry and Wasteland Dev A/C No.',
    'Amt wasteland Forestry and Dev': 'Forestry and Wasteland Dev Amt',
    'Water Amount Resource': 'Water Resource Amt',
    'KVIC Term Loan A/C': 'KVIC TL A/C',
    'KVIC Term Loan Amt': 'KVIC TL Amt',
    'KVIC Working Capital A/C': 'KVIC WC A/C',
    'KVIC Working Capital Amt': 'KVIC WC Amt',
    'Medium Term Loan A/C': 'Medium TL A/C',
    'Medium Term Loan Amt': 'Medium TL Amt',
    'Medium Working Capital A/C': 'Medium WC A/C',
    'Medium Working Capital Amt': 'Medium WC Amt',
    'Micro Term Loan A/C': 'Micro TL A/C',
    'Micro Term Loan Amt': 'Micro TL Amt',
    'Micro Working Capital A/C': 'Micro WC A/C',
    'Micro Working Capital Amt': 'Micro WC Amt',
    'Small Term Loan A/C': 'Small TL A/C',
    'Small Term Loan Amt': 'Small TL Amt',
    'Small Working Capital A/C': 'Small WC A/C',
    'Small Working Capital Amt': 'Small WC Amt',
    'Debit Credit Cards A/C': 'Cards (Debit & Credit) A/C',
    'Debit Credit Cards Amt': 'Cards (Debit & Credit) Amt',
    'Active Rupay Card in PMJDY': 'Rupay Card Active in PMJDY',
    'Weaker Section Loans': 'Loans to Weaker',
    'Weaker Section Loans Amt': 'Loans to Weaker Amt',
    'Weaker Section Loans No.': 'Loans to Weaker No.',
}


# ═══════════════════════════════════════════════════════════════════════
# ISSUE 4: Typos (substring replacement, all states)
# ═══════════════════════════════════════════════════════════════════════

TYPO_FIXES_SNAKE = {
    'ancillaryy': 'ancillary',
    'rene_wals': 'renewals',
    'zoro_astrians': 'zoroastrians',
    'zorastrians': 'zoroastrians',
    'accou_nts': 'accounts',
    'buddhi_sts': 'buddhists',
    'farm_mechanisationn': 'farm_mechanisation',
    'non_prio_rity': 'non_priority',
    'priorityrityrity': 'priority',
    'achived': 'achieved',
}

TYPO_FIXES_HR = {
    'Ancillaryy': 'Ancillary',
    'ancillaryy': 'ancillary',
    'Rene wals': 'Renewals',
    'rene wals': 'renewals',
    'Zoro astrians': 'Zoroastrians',
    'Zorastrians': 'Zoroastrians',
    'Accou nts': 'Accounts',
    'accou nts': 'accounts',
    'Buddhi sts': 'Buddhists',
    'buddhi sts': 'buddhists',
    'farm mechanisationn': 'farm mechanisation',
    'Farm Mechanisationn': 'Farm Mechanisation',
    'Non Prio rity': 'Non Priority',
    'non prio rity': 'non priority',
}


# ═══════════════════════════════════════════════════════════════════════
# ISSUE 5: Singular/plural (snake_case)
# ═══════════════════════════════════════════════════════════════════════

PLURAL_TO_SINGULAR_SNAKE = {
    'total_deposits': 'total_deposit',
    'water_resources': 'water_resource',
    'branches_rural': 'branch_rural',
    'branches_semi_urban': 'branch_semi_urban',
    'branches_urban': 'branch_urban',
    'branches_per_lakh_population': 'branch_per_lakh_population',
    'total_advances': 'total_advance',
}

PLURAL_TO_SINGULAR_HR = {
    'Total Deposits': 'Total Deposit',
    'Water Resources': 'Water Resource',
    'Branches Rural': 'Branch Rural',
    'Branches Semi-Urban': 'Branch Semi-Urban',
    'Branches Urban': 'Branch Urban',
    'Branches Per Lakh Population': 'Branch Per Lakh Population',
    'Total Advances': 'Total Advance',
}


# ═══════════════════════════════════════════════════════════════════════
# ISSUE 3: Abbreviation standardization
# ═══════════════════════════════════════════════════════════════════════

def apply_abbreviation_fixes_snake(field):
    """Apply abbreviation standardization to a snake_case field name."""
    original = field

    # tot_ → total_ (prefix only, and _tot_ in middle)
    if field.startswith('tot_') and not field.startswith('total_'):
        field = 'total_' + field[4:]
    field = re.sub(r'(?<=_)tot_(?!al)', 'total_', field)

    # total_br → total_branch (mizoram)
    field = re.sub(r'\btotal_br\b', 'total_branch', field)

    # term_loan → tl (in compound, not standalone)
    if '_term_loan_' in field or field.startswith('term_loan_') or field.endswith('_term_loan'):
        field = re.sub(r'(?:^|(?<=_))term_loan(?:$|(?=_))', 'tl', field)

    # working_capital → wc
    if '_working_capital_' in field or field.startswith('working_capital_') or field.endswith('_working_capital'):
        field = re.sub(r'(?:^|(?<=_))working_capital(?:$|(?=_))', 'wc', field)

    # disbursement → disb (compound only)
    if '_disbursement_' in field or field.endswith('_disbursement'):
        field = re.sub(r'(?<=_)disbursement(?=_|$)', 'disb', field)
    if field.startswith('disbursement_'):
        field = 'disb_' + field[13:]

    # number_of → no_of
    field = re.sub(r'(?:^|(?<=_))number_of_', 'no_of_', field)

    # amount → amt (compound only)
    if '_amount_' in field or field.endswith('_amount'):
        field = re.sub(r'(?<=_)amount(?=_|$)', 'amt', field)
    if field.startswith('amount_'):
        field = 'amt_' + field[7:]

    if field != original:
        return field, True
    return field, False


def apply_abbreviation_fixes_hr(field):
    """Apply abbreviation fixes to human-readable field names."""
    original = field

    # Tot → Total (at word boundary start)
    field = re.sub(r'\bTot\b(?! )', 'Total', field)
    field = re.sub(r'\bTot ', 'Total ', field)

    # Total Br → Total Branch
    field = re.sub(r'\bTotal Br\b', 'Total Branch', field)

    if field != original:
        return field, True
    return field, False


# ═══════════════════════════════════════════════════════════════════════
# Core standardization functions
# ═══════════════════════════════════════════════════════════════════════

def standardize_snake_field(field, state):
    """Apply all standardization to a snake_case field. Returns (new_field, issues)."""
    original = field
    issues = set()

    # Issue 1: Spacing/merged-word fixes (originally from Manipur PDFs,
    # but the same patterns can appear in other states too)
    if field in MANIPUR_SNAKE_FIXES:
        new = MANIPUR_SNAKE_FIXES[field]
        if new != field:
            field = new
            issues.add('manipur_spacing')

    # Issue 2: Meghalaya reorder
    if state == 'meghalaya' and field in MEGHALAYA_SNAKE_FIXES:
        new = MEGHALAYA_SNAKE_FIXES[field]
        if new != field:
            field = new
            issues.add('meghalaya_reorder')

    # Issue 4: Typos (all states)
    f2 = field
    for typo, fix in TYPO_FIXES_SNAKE.items():
        if typo in f2:
            f2 = f2.replace(typo, fix)
    if f2 != field:
        field = f2
        issues.add('typo')

    # Issue 5: Singular/plural
    if field in PLURAL_TO_SINGULAR_SNAKE:
        field = PLURAL_TO_SINGULAR_SNAKE[field]
        issues.add('singular_plural')

    # Issue 3: Abbreviations
    field, changed = apply_abbreviation_fixes_snake(field)
    if changed:
        issues.add('abbreviation')

    return field, issues


def standardize_hr_field(field, state):
    """Apply standardization to a human-readable field name. Returns (new_field, changed)."""
    original = field
    changed = False

    # Issue 1: Spacing/merged-word HR fixes (apply to all states)
    if field in MANIPUR_HR_FIXES:
        field = MANIPUR_HR_FIXES[field]
        changed = field != original

    # Issue 2: Meghalaya HR fixes
    if state == 'meghalaya' and field in MEGHALAYA_HR_FIXES:
        field = MEGHALAYA_HR_FIXES[field]
        changed = True

    # Issue 4: Typos HR
    for typo, fix in TYPO_FIXES_HR.items():
        if typo in field:
            field = field.replace(typo, fix)
            changed = True

    # Issue 5: Singular/plural HR
    if field in PLURAL_TO_SINGULAR_HR:
        field = PLURAL_TO_SINGULAR_HR[field]
        changed = True

    # Issue 3: Abbreviations HR
    field, abbr_changed = apply_abbreviation_fixes_hr(field)
    if abbr_changed:
        changed = True

    return field, changed


# ═══════════════════════════════════════════════════════════════════════
# Column merge logic
# ═══════════════════════════════════════════════════════════════════════

def merge_duplicate_columns(headers, rows):
    """If renaming causes duplicate columns, merge them. Returns (headers, rows, merge_count)."""
    if len(headers) == len(set(headers)):
        return headers, rows, 0

    col_indices = defaultdict(list)
    for i, h in enumerate(headers):
        col_indices[h].append(i)

    merge_count = 0
    unique_headers = []
    keep_indices = []
    merge_map = {}  # primary_idx -> [secondary indices]

    seen = set()
    for i, h in enumerate(headers):
        if h not in seen:
            seen.add(h)
            unique_headers.append(h)
            keep_indices.append(i)
            if len(col_indices[h]) > 1:
                merge_map[i] = col_indices[h][1:]
                merge_count += len(col_indices[h]) - 1

    new_rows = []
    for row in rows:
        new_row = list(row) + [''] * max(0, len(headers) - len(row))
        for primary_idx, secondary_indices in merge_map.items():
            for sec_idx in secondary_indices:
                if sec_idx < len(new_row):
                    pv = new_row[primary_idx]
                    sv = new_row[sec_idx]
                    if not pv or pv.strip() == '':
                        new_row[primary_idx] = sv

        merged_row = [new_row[idx] if idx < len(new_row) else '' for idx in keep_indices]
        new_rows.append(merged_row)

    return unique_headers, new_rows, merge_count


# ═══════════════════════════════════════════════════════════════════════
# File processing functions
# ═══════════════════════════════════════════════════════════════════════

def process_timeseries_csv(state):
    """Process *_fi_timeseries.csv."""
    fpath = BASE_DIR / state / f'{state}_fi_timeseries.csv'
    if not fpath.exists():
        print(f'  [SKIP] timeseries CSV not found')
        return

    with open(fpath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)

    stats['fields_before'][state] = len(headers)
    rename_map = {}

    for col in headers:
        if '__' not in col:
            continue
        cat, field = col.split('__', 1)
        new_field, issues = standardize_snake_field(field, state)
        if new_field != field:
            new_col = f'{cat}__{new_field}'
            rename_map[col] = new_col
            for issue in issues:
                stats[issue] += 1
            stats['renames_per_state'][state] += 1

    if not rename_map:
        stats['fields_after'][state] = len(headers)
        print(f'  [timeseries CSV] No renames needed')
        return

    new_headers = [rename_map.get(h, h) for h in headers]
    new_headers, rows, merge_count = merge_duplicate_columns(new_headers, rows)
    stats['merges'] += merge_count
    stats['fields_after'][state] = len(new_headers)

    print(f'  [timeseries CSV] {len(rename_map)} renames, {merge_count} merges -> {len(new_headers)} cols')

    with open(fpath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(new_headers)
        writer.writerows(rows)


def process_timeseries_json(state):
    """Process *_fi_timeseries.json."""
    fpath = BASE_DIR / state / f'{state}_fi_timeseries.json'
    if not fpath.exists():
        print(f'  [SKIP] timeseries JSON not found')
        return

    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rename_count = 0
    merge_count = 0

    for period in data.get('periods', []):
        for district in period.get('districts', []):
            new_district = {}
            for key, val in district.items():
                if '__' in key:
                    cat, field = key.split('__', 1)
                    new_field, _ = standardize_snake_field(field, state)
                    new_key = f'{cat}__{new_field}'
                    if new_key != key:
                        rename_count += 1
                else:
                    new_key = key

                if new_key in new_district:
                    existing = new_district[new_key]
                    if not existing or existing == '' or existing is None:
                        new_district[new_key] = val
                    merge_count += 1
                else:
                    new_district[new_key] = val

            district.clear()
            district.update(new_district)

    # Update total_fields count
    if 'total_fields' in data:
        all_fields = set()
        for period in data.get('periods', []):
            for district in period.get('districts', []):
                all_fields.update(district.keys())
        data['total_fields'] = len(all_fields)

    print(f'  [timeseries JSON] {rename_count} key renames, {merge_count} merges')

    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def process_complete_json(state):
    """Process *_complete.json - rename human-readable field keys."""
    fpath = BASE_DIR / state / f'{state}_complete.json'
    if not fpath.exists():
        print(f'  [SKIP] complete JSON not found')
        return

    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rename_count = 0

    for q_key, q_val in data.get('quarters', {}).items():
        for table_name, table_data in q_val.get('tables', {}).items():
            # Rename in fields list
            if 'fields' in table_data:
                new_fields = []
                for f_name in table_data['fields']:
                    new_name, changed = standardize_hr_field(f_name, state)
                    new_fields.append(new_name)
                    if changed:
                        rename_count += 1
                table_data['fields'] = new_fields

            # Rename keys in district data
            for dist_name in list(table_data.get('districts', {}).keys()):
                dist_data = table_data['districts'][dist_name]
                new_dist = {}
                for key, val in dist_data.items():
                    new_key, changed = standardize_hr_field(key, state)
                    if changed:
                        rename_count += 1
                    # Handle merge
                    if new_key in new_dist:
                        existing = new_dist[new_key]
                        if not existing or existing == '' or existing is None:
                            new_dist[new_key] = val
                    else:
                        new_dist[new_key] = val
                table_data['districts'][dist_name] = new_dist

    print(f'  [complete JSON] {rename_count} field renames')

    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def process_quarterly_csvs(state):
    """Process quarterly CSV files - rename human-readable column headers."""
    quarterly_dir = BASE_DIR / state / 'quarterly'
    if not quarterly_dir.exists():
        print(f'  [SKIP] quarterly dir not found')
        return

    total_renames = 0
    total_files = 0

    for period_dir in sorted(quarterly_dir.iterdir()):
        if not period_dir.is_dir():
            continue
        for csv_file in sorted(period_dir.glob('*.csv')):
            try:
                with open(csv_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    try:
                        headers = next(reader)
                    except StopIteration:
                        continue
                    rows = list(reader)
            except Exception:
                continue

            file_renames = 0
            new_headers = []
            for h in headers:
                new_h, changed = standardize_hr_field(h, state)
                new_headers.append(new_h)
                if changed:
                    file_renames += 1

            if file_renames > 0:
                # Handle merges
                new_headers, rows, _ = merge_duplicate_columns(new_headers, rows)

                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(new_headers)
                    writer.writerows(rows)

                total_renames += file_renames

            total_files += 1

    print(f'  [quarterly CSVs] {total_files} files, {total_renames} header renames')


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    print('=' * 70)
    print('SLBC Field Name Standardization')
    print('=' * 70)

    for state in STATES:
        state_dir = BASE_DIR / state
        if not state_dir.exists():
            print(f'\n--- {state.upper()} --- [NOT FOUND]')
            continue

        print(f'\n--- {state.upper()} ---')
        process_timeseries_csv(state)
        process_timeseries_json(state)
        process_complete_json(state)
        process_quarterly_csvs(state)

    # Print statistics
    print('\n' + '=' * 70)
    print('STATISTICS')
    print('=' * 70)

    print('\nRenames by issue type (timeseries CSV):')
    print(f'  Manipur spacing/merged:  {stats["manipur_spacing"]}')
    print(f'  Meghalaya reorder:       {stats["meghalaya_reorder"]}')
    print(f'  Abbreviation fixes:      {stats["abbreviation"]}')
    print(f'  Typo fixes:              {stats["typo"]}')
    print(f'  Singular/plural:         {stats["singular_plural"]}')
    print(f'  Column merges:           {stats["merges"]}')

    print('\nPer-state summary (timeseries CSV):')
    for state in STATES:
        before = stats['fields_before'].get(state, 0)
        after = stats['fields_after'].get(state, 0)
        renames = stats['renames_per_state'].get(state, 0)
        if before > 0:
            print(f'  {state:25s}: {renames:4d} renames, {before:5d} -> {after:5d} fields')

    print('\n' + '=' * 70)
    print('Done.')


if __name__ == '__main__':
    main()
