#!/usr/bin/env python3
"""
Bihar SLBC Agenda Book Extractor v2
Extracts ALL district-wise tables from 12 Bihar SLBC agenda PDFs (82nd-95th).
Outputs: bihar_complete.json, bihar_fi_timeseries.json, bihar_fi_timeseries.csv, quarterly CSVs.
"""

import pdfplumber
import json
import csv
import os
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict

# ─── Bihar's 38 districts (canonical names) ───
BIHAR_DISTRICTS = [
    "Araria", "Arwal", "Aurangabad", "Banka", "Begusarai", "Bhagalpur",
    "Bhojpur", "Buxar", "Darbhanga", "Gaya", "Gopalganj", "Jamui",
    "Jehanabad", "Kaimur (Bhabua)", "Katihar", "Khagaria", "Kishanganj",
    "Lakhisarai", "Madhepura", "Madhubani", "Munger", "Muzaffarpur",
    "Nalanda", "Nawada", "Pashchim Champaran", "Patna", "Purbi Champaran",
    "Purnia", "Rohtas", "Saharsa", "Samastipur", "Saran", "Sheikhpura",
    "Sheohar", "Sitamarhi", "Siwan", "Supaul", "Vaishali"
]

DISTRICT_ALIASES = {}
# Build aliases: UPPER, Title, common variations
for d in BIHAR_DISTRICTS:
    DISTRICT_ALIASES[d.upper()] = d
    DISTRICT_ALIASES[d] = d

# Additional aliases
_extra = {
    "KAIMUR(BHABUA)": "Kaimur (Bhabua)", "KAIMUR": "Kaimur (Bhabua)",
    "KAIMUR (BHABHUA)": "Kaimur (Bhabua)", "KAIMUR(BHABHUA)": "Kaimur (Bhabua)",
    "PASCHIM CHAMPARAN": "Pashchim Champaran", "WEST CHAMPARAN": "Pashchim Champaran",
    "PASHCHIMI CHAMPARAN": "Pashchim Champaran", "P. CHAMPARAN": "Pashchim Champaran",
    "EAST CHAMPARAN": "Purbi Champaran", "PURBA CHAMPARAN": "Purbi Champaran",
    "E. CHAMPARAN": "Purbi Champaran", "PURNEA": "Purnia", "PURNEIA": "Purnia",
    "SHEKHPURA": "Sheikhpura", "SEKHPURA": "Sheikhpura",
    "KAIMUR (BHABUA )": "Kaimur (Bhabua)",
    "Kaimur": "Kaimur (Bhabua)", "Kaimur(Bhabua)": "Kaimur (Bhabua)",
    "Pashchimi Champaran": "Pashchim Champaran",
    "Purba Champaran": "Purbi Champaran", "Purnea": "Purnia",
}
DISTRICT_ALIASES.update(_extra)


# ─── Category detection: (keywords_list, category_name, field_names) ───
# field_names map extracted table columns to standardized field names
# Order matters — first match wins, so put more specific patterns first

CATEGORY_RULES = [
    # Branch network
    {
        "keywords": ["DISTRICT WISE", "BRANCH NETWORK"],
        "not_keywords": ["BANK WISE"],
        "category": "branch_network",
        "fields": ["branches_rural", "branches_semi_urban", "branches_urban", "branches_total"],
    },
    # BC/CSP outlets
    {
        "keywords": ["DISTRICT WISE", "BANKING OUTLET", "BC"],
        "not_keywords": ["BANK WISE"],
        "category": "business_correspondents",
        "fields": ["bc_fixed_point", "bc_other", "bc_total"],
    },
    # ATM network
    {
        "keywords": ["DISTRICT WISE", "ATM", "NETWORK"],
        "not_keywords": ["BANK WISE"],
        "category": "branch_network",  # same category, different sub
        "fields": ["atm_rural", "atm_semi_urban", "atm_urban", "atm_total"],
        "subcategory": "atm_network",
    },
    # POS
    {
        "keywords": ["DISTRICT WISE", "POINT OF SALE"],
        "not_keywords": ["BANK WISE"],
        "category": "branch_network",
        "fields": ["pos_rural", "pos_semi_urban", "pos_urban", "pos_total"],
        "subcategory": "pos_network",
    },
    # Digital transactions
    {
        "keywords": ["DISTRICT", "DIGITAL TRANSACTION"],
        "not_keywords": ["BANK WISE"],
        "category": "digital_transactions",
        "fields": [
            "digital_bhim_upi_no", "digital_bhim_upi_amt",
            "digital_bhim_aadhaar_no", "digital_bhim_aadhaar_amt",
            "digital_bharat_qr_no", "digital_bharat_qr_amt",
            "digital_imps_no", "digital_imps_amt",
            "digital_cards_no", "digital_cards_amt",
            "digital_ussd_no", "digital_ussd_amt",
        ],
    },
    # Aadhaar authentication (district wise)
    {
        "keywords": ["DISTRICT", "AADHAAR", "AUTHENTICATION"],
        "not_keywords": ["BANK WISE"],
        "category": "aadhaar_authentication",
        "fields": ["aadhaar_operative_casa", "aadhaar_seeded_casa", "aadhaar_authenticated_casa"],
    },
    # Deposit and advance / CD ratio
    {
        "keywords": ["DISTRICT WISE", "DEPOSIT", "ADVANCE"],
        "not_keywords": ["BANK WISE"],
        "category": "credit_deposit_ratio",
        "fields": None,  # auto-detect since column count varies across PDFs
    },
    # Agriculture disbursement
    {
        "keywords": ["DISTRICT WISE", "AGRICULTURE", "DISBURSEMENT"],
        "not_keywords": ["BANK WISE", "NPA", "OUTSTANDING"],
        "category": "agri_outstanding",
        "fields": [
            "agri_crop_loan_no", "agri_crop_loan",
            "agri_term_loan_no", "agri_term_loan",
            "agri_total_farm_credit_no", "agri_total_farm_credit",
            "agri_infrastructure_no", "agri_infrastructure",
            "agri_ancillary_no", "agri_ancillary",
            "agri_total_no", "agri_total",
        ],
        "subcategory": "agri_disbursement",
    },
    # Agriculture outstanding
    {
        "keywords": ["DISTRICT WISE", "AGRICULTURE", "OUTSTANDING"],
        "not_keywords": ["BANK WISE", "NPA"],
        "category": "agri_outstanding",
        "fields": [
            "agri_crop_loan_no", "agri_crop_loan",
            "agri_term_loan_no", "agri_term_loan",
            "agri_total_farm_credit_no", "agri_total_farm_credit",
            "agri_infrastructure_no", "agri_infrastructure",
            "agri_ancillary_no", "agri_ancillary",
            "agri_total_no", "agri_total",
        ],
    },
    # Agriculture NPA outstanding
    {
        "keywords": ["DISTRICT WISE", "AGRICULTURE", "NPA"],
        "not_keywords": ["BANK WISE"],
        "category": "agri_npa",
        "fields": [
            "agri_npa_crop_loan_no", "agri_npa_crop_loan",
            "agri_npa_term_loan_no", "agri_npa_term_loan",
            "agri_npa_total_farm_credit_no", "agri_npa_total_farm_credit",
            "agri_npa_infrastructure_no", "agri_npa_infrastructure",
            "agri_npa_ancillary_no", "agri_npa_ancillary",
            "agri_npa_total_no", "agri_npa_total",
        ],
    },
    # MSME disbursement (district wise ACP)
    {
        "keywords": ["DISTRICT WISE", "ACP", "MSME", "DISBURSEMENT"],
        "not_keywords": ["BANK WISE"],
        "category": "msme_outstanding",
        "fields": [
            "msme_micro_no", "msme_micro_amt",
            "msme_small_no", "msme_small_amt",
            "msme_medium_no", "msme_medium_amt",
            "msme_other_no", "msme_other_amt",
            "msme_total_no", "msme_total_amt",
        ],
        "subcategory": "msme_disbursement",
    },
    # MSME NPA outstanding
    {
        "keywords": ["DISTRICT WISE", "MSME", "NPA", "OUTSTANDING"],
        "not_keywords": ["BANK WISE"],
        "category": "msme_npa",
        "fields": [
            "msme_npa_micro_no", "msme_npa_micro_amt",
            "msme_npa_small_no", "msme_npa_small_amt",
            "msme_npa_medium_no", "msme_npa_medium_amt",
            "msme_npa_other_no", "msme_npa_other_amt",
            "msme_npa_total_no", "msme_npa_total_amt",
        ],
    },
    # MSME - micro enterprises disbursement
    {
        "keywords": ["DISTRICT WISE", "MICRO ENTERPRISES"],
        "not_keywords": ["BANK WISE", "NPA"],
        "category": "msme_outstanding",
        "fields": ["msme_micro_target", "msme_micro_disbursed_no", "msme_micro_disbursed_amt", "msme_micro_pct"],
        "subcategory": "msme_micro_disbursement",
    },
    # MSME - small enterprises disbursement
    {
        "keywords": ["DISTRICT WISE", "SMALL ENTERPRISES"],
        "not_keywords": ["BANK WISE", "NPA"],
        "category": "msme_outstanding",
        "fields": ["msme_small_target", "msme_small_disbursed_no", "msme_small_disbursed_amt", "msme_small_pct"],
        "subcategory": "msme_small_disbursement",
    },
    # MSME - medium enterprises disbursement
    {
        "keywords": ["DISTRICT WISE", "MEDIUM ENTERPRISES"],
        "not_keywords": ["BANK WISE", "NPA"],
        "category": "msme_outstanding",
        "fields": ["msme_medium_target", "msme_medium_disbursed_no", "msme_medium_disbursed_amt", "msme_medium_pct"],
        "subcategory": "msme_medium_disbursement",
    },
    # MSME - medium enterprises (misspelling variant)
    {
        "keywords": ["DISTRICT WISE", "MIDIUM ENTERPRISES"],
        "not_keywords": ["BANK WISE", "NPA"],
        "category": "msme_outstanding",
        "fields": ["msme_medium_target", "msme_medium_disbursed_no", "msme_medium_disbursed_amt", "msme_medium_pct"],
        "subcategory": "msme_medium_disbursement",
    },
    # Education loan
    {
        "keywords": ["DISTRICT WISE", "EDUCATION LOAN"],
        "not_keywords": ["BANK WISE"],
        "category": "education_loan",
        "fields": None,  # will auto-detect
    },
    # Housing loan
    {
        "keywords": ["DISTRICT WISE", "HOUSING LOAN"],
        "not_keywords": ["BANK WISE"],
        "category": "housing_pmay",
        "fields": None,
    },
    # Other priority sector
    {
        "keywords": ["DISTRICT WISE", "OTHER PRIORITY"],
        "not_keywords": ["BANK WISE"],
        "category": "other_ps_outstanding",
        "fields": None,
    },
    # Weaker section advance
    {
        "keywords": ["DISTRICT WISE", "WEAKER SECTION"],
        "not_keywords": ["BANK WISE"],
        "category": "weaker_section_os",
        "fields": None,
    },
    # Minority advance
    {
        "keywords": ["DISTRICT WISE", "MINORITY"],
        "not_keywords": ["BANK WISE"],
        "category": "minority_outstanding",
        "fields": None,
    },
    # Export credit
    {
        "keywords": ["DISTRICT WISE", "EXPORT CREDIT"],
        "not_keywords": ["BANK WISE"],
        "category": "export_credit",
        "fields": None,
    },
    # PMJDY
    {
        "keywords": ["DISTRICT WISE", "PMJDY"],
        "not_keywords": ["BANK WISE"],
        "category": "pmjdy",
        "fields": [
            "pmjdy_total_accounts", "pmjdy_opened_fy",
            "pmjdy_zero_balance", "pmjdy_deposits_held",
            "pmjdy_rupay_cards_issued", "pmjdy_rupay_cards_activated",
            "pmjdy_aadhaar_seeded",
        ],
    },
    # Social security claim status (district wise)
    {
        "keywords": ["DISTRICT WISE", "SOCIAL SECURITY", "CLAIM"],
        "not_keywords": ["BANK WISE"],
        "category": "social_security",
        "fields": [
            "social_pmjjby_claims_received", "social_pmjjby_total_claims",
            "social_pmjjby_claims_settled", "social_pmjjby_total_settled",
            "social_pmsby_claims_received", "social_pmsby_total_claims",
            "social_pmsby_claims_settled", "social_pmsby_total_settled",
        ],
    },
    # Social security progress (SURAKSHA BIMA YOJANA - district wise)
    {
        "keywords": ["DISTRICT WISE", "SURAKSHA BIMA"],
        "not_keywords": ["BANK WISE"],
        "category": "social_security",
        "fields": [
            "social_pmjjby_enrolment", "social_pmjjby_total_enrolment",
            "social_pmjjby_eligible", "social_pmjjby_renewals",
            "social_pmsby_enrolment", "social_pmsby_total_enrolment",
            "social_pmsby_eligible", "social_pmsby_renewals",
            "social_apy_enrolment", "social_apy_total_enrolment",
        ],
    },
    # MUDRA / PMMY disbursement
    {
        "keywords": ["DISTRICT WISE", "MUDRA"],
        "not_keywords": ["BANK WISE", "NPA", "OUTSTANDING"],
        "category": "mudra",
        "fields": None,
    },
    {
        "keywords": ["DISTRICT WISE", "PMMY", "DISBURSEMENT"],
        "not_keywords": ["BANK WISE", "NPA", "OUTSTANDING"],
        "category": "mudra",
        "fields": None,
    },
    # Stand Up India
    {
        "keywords": ["DISTRICT WISE", "STAND UP INDIA"],
        "not_keywords": ["BANK WISE"],
        "category": "sui",
        "fields": None,
    },
    # PM SVANidhi
    {
        "keywords": ["DISTRICT WISE", "SVANIDHI"],
        "not_keywords": ["BANK WISE"],
        "category": "pm_svanidhi",
        "fields": None,
    },
    # KCC progress (district wise)
    {
        "keywords": ["DISTRICT WISE", "KCC", "PROGRESS"],
        "not_keywords": ["BANK WISE", "ANIMAL", "FISHERIES"],
        "category": "kcc",
        "fields": None,  # complex multi-col, auto-detect
    },
    # SHG
    {
        "keywords": ["DISTRICT WISE", "SHG"],
        "not_keywords": ["BANK WISE"],
        "category": "shg",
        "fields": None,
    },
    {
        "keywords": ["DISTRICT WISE", "SELF HELP GROUP"],
        "not_keywords": ["BANK WISE"],
        "category": "shg",
        "fields": None,
    },
    # NPA - Total
    {
        "keywords": ["DISTRICT WISE", "TOTAL", "NPA", "OUTSTANDING"],
        "not_keywords": ["BANK WISE", "AGRICULTURE", "MSME", "SECTOR"],
        "category": "npa_recovery",
        "fields": None,
        "subcategory": "total_npa",
    },
    # NPA various sectors
    {
        "keywords": ["DISTRICT WISE", "NON PERFORMING ASSETS", "VARIOUS SECTOR"],
        "not_keywords": ["BANK WISE"],
        "category": "npa_recovery",
        "fields": None,
        "subcategory": "npa_all_sectors",
    },
    # CD ratio standalone
    {
        "keywords": ["DISTRICT WISE", "CD RATIO"],
        "not_keywords": ["BANK WISE"],
        "category": "credit_deposit_ratio",
        "fields": None,
    },
    # ACP performance
    {
        "keywords": ["DISTRICT WISE", "PERFORMANCE", "ANNUAL CREDIT PLAN"],
        "not_keywords": ["BANK WISE"],
        "category": "acp_target_achievement",
        "fields": None,
    },
    # ACP priority sector disbursement
    {
        "keywords": ["DISTRICT WISE", "DISBURSEMENT", "ANNUAL CREDIT PLAN", "PRIORITY"],
        "not_keywords": ["BANK WISE", "NON PRIORITY"],
        "category": "priority_sector_analysis",
        "fields": None,
    },
    # KCC animal husbandry
    {
        "keywords": ["DISTRICT WISE", "KCC", "ANIMAL HUSBANDRY"],
        "not_keywords": ["BANK WISE"],
        "category": "kcc_animal_husbandry",
        "fields": None,
    },
    # KCC fisheries
    {
        "keywords": ["DISTRICT WISE", "KCC", "FISHER"],
        "not_keywords": ["BANK WISE"],
        "category": "kcc_fishery",
        "fields": None,
    },
    # PMEGP
    {
        "keywords": ["DISTRICT WISE", "PMEGP"],
        "not_keywords": ["BANK WISE"],
        "category": "pmegp",
        "fields": None,
    },
    # RSETI
    {
        "keywords": ["DISTRICT WISE", "RSETI"],
        "not_keywords": ["BANK WISE"],
        "category": "rseti",
        "fields": None,
    },
    # PM Vishwakarma
    {
        "keywords": ["DISTRICT WISE", "VISHWAKARMA"],
        "not_keywords": ["BANK WISE"],
        "category": "pm_vishwakarma",
        "fields": None,
    },
    # PM Surya Ghar
    {
        "keywords": ["DISTRICT WISE", "SURYA GHAR"],
        "not_keywords": ["BANK WISE"],
        "category": "pm_surya_ghar",
        "fields": None,
    },
    # Certificate cases / SARFAESI
    {
        "keywords": ["DISTRICT WISE", "CERTIFICATE CASES"],
        "not_keywords": ["BANK WISE"],
        "category": "recovery_bakijai",
        "fields": None,
    },
    {
        "keywords": ["DISTRICT WISE", "SARFAESI"],
        "not_keywords": ["BANK WISE"],
        "category": "sarfaesi",
        "fields": None,
    },
    # Finance to women
    {
        "keywords": ["DISTRICT WISE", "WOMEN"],
        "not_keywords": ["BANK WISE"],
        "category": "women_finance",
        "fields": None,
    },
    # SC/ST
    {
        "keywords": ["DISTRICT WISE", "SC/ST"],
        "not_keywords": ["BANK WISE"],
        "category": "sc_st_finance",
        "fields": None,
    },
    # DCC/BLBC meetings
    {
        "keywords": ["DISTRICT WISE", "DCC", "MEETING"],
        "not_keywords": ["BANK WISE"],
        "category": "dcc_meetings",
        "fields": None,
    },
    {
        "keywords": ["DISTRICT WISE", "BLBC", "MEETING"],
        "not_keywords": ["BANK WISE"],
        "category": "dcc_meetings",
        "fields": None,
        "subcategory": "blbc_meeting",
    },
    # Non-priority sector
    {
        "keywords": ["DISTRICT WISE", "NON PRIORITY"],
        "not_keywords": ["BANK WISE"],
        "category": "non_ps_outstanding",
        "fields": None,
    },
    # PMFME
    {
        "keywords": ["DISTRICT WISE", "PMFME"],
        "not_keywords": ["BANK WISE"],
        "category": "pmfme",
        "fields": None,
    },
    # Saturation campaign
    {
        "keywords": ["DISTRICT WISE", "SATURATION"],
        "not_keywords": ["BANK WISE"],
        "category": "fi_kcc",
        "fields": None,
    },
    # PMJDY - also match "Progress under PMJDY"
    {
        "keywords": ["DISTRICT", "PROGRESS", "PMJDY"],
        "not_keywords": ["BANK WISE"],
        "category": "pmjdy",
        "fields": None,
    },
    # KCC progress report
    {
        "keywords": ["DISTRICT", "KCC", "PROGRESS", "REPORT"],
        "not_keywords": ["BANK WISE", "ANIMAL", "FISHER"],
        "category": "kcc",
        "fields": None,
    },
    # KCC outstanding, NPA & RuPay
    {
        "keywords": ["DISTRICT", "KCC", "OUTSTANDING"],
        "not_keywords": ["BANK WISE", "ANIMAL", "FISHER"],
        "category": "kcc",
        "fields": None,
        "subcategory": "kcc_outstanding",
    },
    # KCC AH saturation
    {
        "keywords": ["KCC", "AH", "SATURATION"],
        "not_keywords": ["BANK WISE"],
        "category": "fi_kcc",
        "fields": None,
        "subcategory": "kcc_ah_saturation",
    },
    # KCC fisheries saturation
    {
        "keywords": ["KCC", "FISHERIES", "SATURATION"],
        "not_keywords": ["BANK WISE"],
        "category": "fi_kcc",
        "fields": None,
        "subcategory": "kcc_fish_saturation",
    },
    # SHG / JLG
    {
        "keywords": ["DISTRICT WISE", "JLG"],
        "not_keywords": ["BANK WISE"],
        "category": "shg",
        "fields": None,
        "subcategory": "jlg",
    },
    # PMMY / MUDRA disbursement
    {
        "keywords": ["DISTRICT WISE", "PMMY"],
        "not_keywords": ["BANK WISE", "NPA"],
        "category": "mudra",
        "fields": None,
    },
    # MUDRA outstanding & NPA
    {
        "keywords": ["DISTRICT WISE", "MUDRA"],
        "not_keywords": ["BANK WISE"],
        "category": "mudra",
        "fields": None,
        "subcategory": "mudra_outstanding",
    },
    # Dairy
    {
        "keywords": ["DISTRICT WISE", "DAIRY"],
        "not_keywords": ["BANK WISE"],
        "category": "dairy",
        "fields": None,
    },
    # Poultry
    {
        "keywords": ["DISTRICT WISE", "POULTRY"],
        "not_keywords": ["BANK WISE"],
        "category": "poultry",
        "fields": None,
    },
    # Fisheries progress
    {
        "keywords": ["DISTRICT WISE", "FISHERIES"],
        "not_keywords": ["BANK WISE", "KCC", "SATURATION"],
        "category": "fisheries",
        "fields": None,
    },
    # Agri term loan progress
    {
        "keywords": ["DISTRICT WISE", "AGRI TERM LOAN"],
        "not_keywords": ["BANK WISE"],
        "category": "agri_term_loan",
        "fields": None,
    },
    # Crop loan progress
    {
        "keywords": ["DISTRICT WISE", "CROP LOAN"],
        "not_keywords": ["BANK WISE"],
        "category": "crop_loan",
        "fields": None,
    },
    # Agri infrastructure
    {
        "keywords": ["DISTRICT WISE", "AGRI INFRASTRUCTURE"],
        "not_keywords": ["BANK WISE"],
        "category": "agri_infrastructure",
        "fields": None,
    },
    # Agri ancillary
    {
        "keywords": ["DISTRICT WISE", "AGRI ANCILLARY"],
        "not_keywords": ["BANK WISE"],
        "category": "agri_ancillary",
        "fields": None,
    },
    # Other disbursement
    {
        "keywords": ["DISTRICT WISE", "OTHER", "DISBURSEMENT"],
        "not_keywords": ["BANK WISE", "MSME"],
        "category": "other_disbursement",
        "fields": None,
    },
    # Other outstanding
    {
        "keywords": ["DISTRICT WISE", "OTHER", "OUTSTANDING"],
        "not_keywords": ["BANK WISE", "NPA", "MSME"],
        "category": "other_outstanding",
        "fields": None,
    },
    # Other NPA outstanding
    {
        "keywords": ["DISTRICT WISE", "OTHER", "NPA"],
        "not_keywords": ["BANK WISE"],
        "category": "other_npa",
        "fields": None,
    },
    # Non-priority sector disbursement
    {
        "keywords": ["DISTRICT WISE", "NON PRIORITY", "DISBURSEMENT"],
        "not_keywords": ["BANK WISE"],
        "category": "non_ps_disbursement",
        "fields": None,
    },
    # Non-priority sector NPA
    {
        "keywords": ["DISTRICT WISE", "NON PRIORITY", "NPA"],
        "not_keywords": ["BANK WISE"],
        "category": "non_ps_npa",
        "fields": None,
    },
    # MSME other finance
    {
        "keywords": ["DISTRICT", "OTHER FINANCE", "MSME"],
        "not_keywords": ["BANK WISE"],
        "category": "msme_other_finance",
        "fields": None,
    },
    # MSME outstanding
    {
        "keywords": ["DISTRICT WISE", "MSME", "OUTSTANDING"],
        "not_keywords": ["BANK WISE", "NPA"],
        "category": "msme_outstanding",
        "fields": None,
    },
    # PM Surya Ghar (since inception)
    {
        "keywords": ["SURYA GHAR", "SINCE INCEPTION"],
        "not_keywords": ["BANK WISE"],
        "category": "pm_surya_ghar",
        "fields": None,
        "subcategory": "pm_surya_ghar_inception",
    },
    # SC/ST loans
    {
        "keywords": ["DISTRICT WISE", "SC/ST"],
        "not_keywords": ["BANK WISE"],
        "category": "sc_st_finance",
        "fields": None,
    },
    # FL camps / financial literacy
    {
        "keywords": ["DISTRICT", "FL CAMPS"],
        "not_keywords": ["BANK WISE"],
        "category": "financial_literacy",
        "fields": None,
    },
    {
        "keywords": ["DISTRICT", "COLLECTING", "FL"],
        "not_keywords": ["BANK WISE"],
        "category": "financial_literacy",
        "fields": None,
    },
    # DEAF (Depositor Education Awareness Fund)
    {
        "keywords": ["DISTRICT", "DEAF"],
        "not_keywords": ["BANK WISE"],
        "category": "deaf",
        "fields": None,
    },
    # FI schemes saturation campaign
    {
        "keywords": ["DISTRICT WISE", "SATURATION", "FI SCHEMES"],
        "not_keywords": ["BANK WISE"],
        "category": "fi_saturation",
        "fields": None,
    },
    {
        "keywords": ["DISTRICT WISE", "SATURATION CAMPAIGN"],
        "not_keywords": ["BANK WISE"],
        "category": "fi_saturation",
        "fields": None,
    },
    # RSETI
    {
        "keywords": ["RSETI"],
        "not_keywords": ["BANK WISE"],
        "category": "rseti",
        "fields": None,
    },
    # Catch-all for any remaining district-wise tables
    # (will use auto-detected headers)
]


# ─── PDF file list ───
PDF_FILES = [
    # 82nd-89th are scanned images without text layer (OCR'd versions have poor quality)
    # "82nd_agenda.pdf",
    # "83rd_84th_agenda.pdf",
    # "85th_86th_agenda.pdf",
    # "87th_agenda.pdf",
    # "88th_dec23.pdf",
    # "89th_mar24.pdf",
    # Text-extractable PDFs (native digital tables):
    "90th_jun24.pdf",
    "91st_sep24.pdf",
    "92nd_dec24.pdf",
    "93rd_agenda.pdf",
    "94th_agenda.pdf",
    "95th_agenda.pdf",
]


def normalize_district(name):
    """Normalize a district name to canonical form."""
    if not name:
        return None
    name = name.strip()
    # Remove leading/trailing dots, commas
    name = name.strip('.,;: ')
    # Direct lookup
    if name in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[name]
    upper = name.upper().strip()
    if upper in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[upper]
    # Strip leading serial number
    clean = re.sub(r'^\d+[\.\s]+', '', name).strip()
    upper_clean = clean.upper()
    if upper_clean in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[upper_clean]
    # Try removing extra spaces
    compressed = re.sub(r'\s+', ' ', upper_clean)
    if compressed in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[compressed]
    return None


def parse_number(val):
    """Parse a number string, handling commas, percentages, etc."""
    if val is None:
        return ""
    val = str(val).strip()
    if val in ('', '-', 'NA', 'N/A', 'NIL', '--', '…', '.', '*'):
        return ""
    # Remove commas
    val = val.replace(',', '')
    # Remove percentage sign
    val = val.replace('%', '')
    # Handle parentheses for negatives
    if val.startswith('(') and val.endswith(')'):
        val = '-' + val[1:-1]
    try:
        float(val)
        return val
    except ValueError:
        return val


def detect_category(text):
    """Match page text to a category rule. Returns (category, subcategory, fields) or None."""
    upper = text.upper()

    # Skip bank-wise tables
    if "BANK WISE" in upper and "DISTRICT WISE" not in upper:
        return None

    for rule in CATEGORY_RULES:
        keywords = rule["keywords"]
        not_keywords = rule.get("not_keywords", [])

        # All keywords must match
        if not all(kw in upper for kw in keywords):
            continue

        # Check NOT keywords
        if any(nk in upper for nk in not_keywords):
            continue

        cat = rule["category"]
        subcat = rule.get("subcategory", cat)
        fields = rule.get("fields")
        return cat, subcat, fields

    return None


def extract_date_from_text(text):
    """Extract 'AS ON dd.mm.yyyy' date from page text."""
    if not text:
        return None
    # Various date patterns
    patterns = [
        r'AS\s+ON\s+(\d{2})[.\-/](\d{2})[.\-/](\d{4})',
        r'(\d{2})[.\-/](\d{2})[.\-/](\d{4})',
    ]
    for pat in patterns:
        m = re.search(pat, text.upper())
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2018 <= year <= 2030 and 1 <= month <= 12:
                return day, month, year
    return None


def date_to_quarter(day, month, year):
    """Convert a date to quarter key and label."""
    if month <= 3:
        return f"{year}-03", f"March {year}"
    elif month <= 6:
        return f"{year}-06", f"June {year}"
    elif month <= 9:
        return f"{year}-09", f"September {year}"
    else:
        return f"{year}-12", f"December {year}"


def extract_table_from_page(page, page_num):
    """Use pdfplumber extract_tables() to get structured table data from a page."""
    tables = page.extract_tables()
    if not tables:
        return None

    # Use the largest table
    table = max(tables, key=lambda t: len(t))
    if len(table) < 5:
        return None

    return table


def identify_district_rows(table):
    """From a raw table, identify which rows are district data rows.
    Returns list of (district_name, [values]) tuples.
    """
    results = []
    for row in table:
        if not row or len(row) < 3:
            continue

        # The district name is typically in column 0 or 1
        # Column 0 is often SR.NO.
        district = None
        val_start = None

        for col_idx in range(min(3, len(row))):
            cell = str(row[col_idx] or '').strip()
            # Clean up newlines within cells
            cell = cell.replace('\n', ' ').strip()

            # Skip pure numbers (serial numbers)
            if re.match(r'^\d+$', cell):
                continue

            # Try to match district
            d = normalize_district(cell)
            if d:
                district = d
                val_start = col_idx + 1
                break

        if district and val_start is not None:
            values = []
            for v in row[val_start:]:
                values.append(parse_number(v))
            results.append((district, values))

    return results


def extract_headers_from_table(table):
    """Extract column headers from the table rows before data."""
    header_rows = []
    for row in table:
        if not row:
            continue

        # Check if this is a data row (starts with serial number + district)
        first_cell = str(row[0] or '').strip()
        if re.match(r'^\d+$', first_cell):
            # Check if second cell is a district name
            if len(row) > 1:
                second = str(row[1] or '').strip().replace('\n', ' ')
                if normalize_district(second):
                    break

        # Check if the row itself contains a district name in first cell
        cell0 = first_cell.replace('\n', ' ')
        if normalize_district(cell0):
            break

        header_rows.append(row)

    if not header_rows:
        return []

    # Build composite headers from multi-row headers
    num_cols = max(len(r) for r in header_rows)
    headers = []
    for col_idx in range(num_cols):
        parts = []
        for hr in header_rows:
            if col_idx < len(hr) and hr[col_idx]:
                cell_text = str(hr[col_idx]).strip().replace('\n', ' ')
                if cell_text and cell_text.upper() not in ('', 'SR.NO.', 'SR. NO.', 'SL.NO.',
                    'S.N', 'S.N.', 'SR.NO', 'SR NO', 'SR NO.', 'SR.N O.',
                    'NAME OF DISTRICT', 'DISTRICT NAME', 'NAME OF\nDISTRICT',
                    'DISTRICT\nNAME', 'NAME OFDISTRICT'):
                    if cell_text not in parts:
                        parts.append(cell_text)
        headers.append(' '.join(parts).strip())

    return headers


def make_field_name(header_text):
    """Convert a raw header text to a snake_case field name."""
    if not header_text:
        return "unknown"
    t = header_text.lower()
    # Clean up
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    t = re.sub(r'\s+', '_', t.strip())
    t = t.strip('_')
    # Truncate very long names
    if len(t) > 60:
        t = t[:60].rstrip('_')
    return t or "unknown"


def process_pdf(pdf_path):
    """Extract all district-wise tables from a single PDF.
    Returns list of table dicts: {page, title, category, subcategory, date, quarter_key, period, fields, districts}
    """
    print(f"\n{'='*60}")
    print(f"Processing: {os.path.basename(pdf_path)}")

    pdf = pdfplumber.open(pdf_path)
    num_pages = len(pdf.pages)
    print(f"  Pages: {num_pages}")

    results = []
    seen_dates = set()

    for page_idx in range(num_pages):
        page = pdf.pages[page_idx]
        page_num = page_idx + 1

        # Extract text for category detection
        text = page.extract_text()
        if not text:
            continue

        upper_text = text.upper()

        # Must be a district-wise page (not bank-wise)
        if "DISTRICT" not in upper_text[:1500]:
            continue

        # Skip if it's clearly bank-wise
        first_800 = upper_text[:800]
        if "BANK WISE" in first_800 and "DISTRICT WISE" not in first_800:
            continue

        # Additional check: skip pages that have bank names in data rows
        # (bank-wise tables list banks like "STATE BANK OF INDIA" as row entries)
        if "LEAD BANKS" in upper_text[:2000] and "DISTRICT" not in first_800:
            continue

        # Detect category
        cat_result = detect_category(first_800)
        if not cat_result:
            # Try with more text
            cat_result = detect_category(upper_text[:2000])

        if not cat_result:
            # Skip uncategorized
            continue

        category, subcategory, predefined_fields = cat_result

        # Extract date
        date_info = extract_date_from_text(text[:1000])
        if date_info:
            day, month, year = date_info
            quarter_key, period = date_to_quarter(day, month, year)
            seen_dates.add(quarter_key)
        else:
            quarter_key, period = None, None

        # Extract table data
        raw_table = extract_table_from_page(page, page_num)
        if not raw_table:
            continue

        # Get headers
        raw_headers = extract_headers_from_table(raw_table)

        # Get district data
        district_data = identify_district_rows(raw_table)

        if len(district_data) < 20:
            # Too few districts, likely not a proper district table
            continue

        # Determine field names
        # Skip first 2 header entries (SR.NO, District Name)
        value_headers = []
        if raw_headers:
            # Find where value columns start (skip SR.NO and District columns)
            skip = 0
            for h in raw_headers:
                hu = h.upper()
                if any(x in hu for x in ['SR', 'SL', 'S.N', 'NAME', 'DISTRICT']):
                    skip += 1
                else:
                    break
            if skip < 2:
                skip = 2
            value_headers = raw_headers[skip:]

        # How many value columns do we have?
        num_vals = max(len(vals) for _, vals in district_data) if district_data else 0

        if predefined_fields and len(predefined_fields) == num_vals:
            fields = predefined_fields
        elif value_headers and len(value_headers) >= num_vals:
            fields = [make_field_name(h) for h in value_headers[:num_vals]]
        else:
            fields = [f"col_{i+1}" for i in range(num_vals)]

        # Build district dict
        districts = {}
        for dist_name, values in district_data:
            # Pad/trim values to match field count
            while len(values) < len(fields):
                values.append("")
            districts[dist_name] = values[:len(fields)]

        title_lines = text.strip().split('\n')[:5]
        title = ' '.join(l.strip() for l in title_lines if l.strip())

        results.append({
            'page': page_num,
            'title': title[:200],
            'category': category,
            'subcategory': subcategory,
            'quarter_key': quarter_key,
            'period': period,
            'fields': fields,
            'districts': districts,
        })

        print(f"  P{page_num:>3}: {subcategory:<35} ({len(districts)} districts, {len(fields)} cols) q={quarter_key}")

    pdf.close()

    # Fill in missing dates from other tables in same PDF
    if seen_dates:
        default_quarter = sorted(seen_dates)[-1]  # latest date
        for r in results:
            if not r['quarter_key']:
                default_period = date_to_quarter(30, int(default_quarter.split('-')[1]),
                                                  int(default_quarter.split('-')[0]))[1]
                r['quarter_key'] = default_quarter
                r['period'] = default_period

    print(f"  Total tables extracted: {len(results)}")
    return results


def build_complete_json(all_tables):
    """Build bihar_complete.json from all extracted tables."""
    complete = {
        "source": "SLBC Bihar",
        "state": "Bihar",
        "description": "Complete district-wise banking & financial inclusion data",
        "amount_unit": "Rs. Crore",
        "quarters": {}
    }

    for t in all_tables:
        qk = t['quarter_key']
        if not qk:
            continue

        if qk not in complete['quarters']:
            complete['quarters'][qk] = {
                "period": t['period'],
                "tables": {}
            }

        cat_key = t['subcategory']

        # If category already exists for this quarter, make a unique key
        base_key = cat_key
        counter = 2
        while cat_key in complete['quarters'][qk]['tables']:
            cat_key = f"{base_key}_{counter}"
            counter += 1

        table_data = {
            "fields": t['fields'],
            "num_districts": len(t['districts']),
            "districts": {}
        }

        for dist, values in t['districts'].items():
            row = {}
            for i, f in enumerate(t['fields']):
                if i < len(values):
                    row[f] = values[i]
                else:
                    row[f] = ""
            table_data["districts"][dist] = row

        complete['quarters'][qk]['tables'][cat_key] = table_data

    return complete


def build_timeseries(complete_json):
    """Build timeseries data from complete.json.
    Returns list of dicts (one per district per quarter) with flattened field names.
    """
    records = []

    for qk in sorted(complete_json['quarters'].keys()):
        q_data = complete_json['quarters'][qk]
        period = q_data['period']

        # Collect all data for this quarter by district
        district_records = defaultdict(dict)

        for cat_key, table in q_data['tables'].items():
            fields = table['fields']
            for dist_name, row in table['districts'].items():
                for field_name, value in row.items():
                    # Create composite key: category__field
                    composite = f"{cat_key}__{field_name}"
                    district_records[dist_name][composite] = value

        for dist_name in sorted(district_records.keys()):
            rec = {
                "state": "Bihar",
                "district": dist_name,
                "quarter": qk,
                "period": period,
            }
            rec.update(district_records[dist_name])
            records.append(rec)

    return records


def build_fi_timeseries(complete_json):
    """Build FI-focused timeseries matching the format used by the frontend.
    Structure: { periods: [ { period: "...", districts: [ {...} ] } ] }
    """
    periods_data = []

    for qk in sorted(complete_json['quarters'].keys()):
        q_data = complete_json['quarters'][qk]
        period = q_data['period']

        districts_list = []

        # Collect all data per district
        district_records = defaultdict(dict)

        for cat_key, table in q_data['tables'].items():
            for dist_name, row in table['districts'].items():
                for field_name, value in row.items():
                    composite = f"{cat_key}__{field_name}"
                    district_records[dist_name][composite] = value

        for dist_name in sorted(district_records.keys()):
            rec = {
                "district": dist_name,
                "period": period,
            }
            rec.update(district_records[dist_name])
            districts_list.append(rec)

        periods_data.append({
            "period": period,
            "districts": districts_list
        })

    return {"periods": periods_data}


def save_quarterly_csvs(complete_json, output_dir):
    """Save quarterly CSVs in output_dir/quarterly/YYYY-MM/category.csv format."""
    count = 0
    for qk in sorted(complete_json['quarters'].keys()):
        q_data = complete_json['quarters'][qk]

        for cat_key, table in q_data['tables'].items():
            fields = table['fields']
            quarter_dir = os.path.join(output_dir, 'quarterly', qk)
            os.makedirs(quarter_dir, exist_ok=True)

            csv_path = os.path.join(quarter_dir, f"{cat_key}.csv")
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['district'] + fields)

                for dist in BIHAR_DISTRICTS:
                    if dist in table['districts']:
                        row_data = table['districts'][dist]
                        writer.writerow([dist] + [row_data.get(f, '') for f in fields])

            count += 1

    print(f"  Saved {count} quarterly CSV files")


def save_timeseries_csv(records, output_path):
    """Save wide-format timeseries CSV."""
    if not records:
        print("  No timeseries records to save")
        return

    # Collect all field names
    all_fields = set()
    for rec in records:
        all_fields.update(rec.keys())

    # Sort fields: meta first, then alphabetically
    meta_fields = ['state', 'district', 'quarter', 'period']
    data_fields = sorted(all_fields - set(meta_fields))
    all_cols = meta_fields + data_fields

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=all_cols, extrasaction='ignore')
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)

    print(f"  Saved timeseries CSV: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Extract Bihar SLBC data from PDFs')
    parser.add_argument('--all', action='store_true', help='Process all 12 PDFs')
    parser.add_argument('--pdf', type=str, help='Process a single PDF')
    parser.add_argument('--output-dir', type=str, default='../../public/slbc-data/bihar',
                        help='Output directory')
    parser.add_argument('--pdf-dir', type=str, default='.', help='Directory containing PDFs')
    args = parser.parse_args()

    # Resolve paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_dir = os.path.join(script_dir, args.pdf_dir) if not os.path.isabs(args.pdf_dir) else args.pdf_dir
    output_dir = os.path.join(script_dir, args.output_dir) if not os.path.isabs(args.output_dir) else args.output_dir

    os.makedirs(output_dir, exist_ok=True)

    # Determine which PDFs to process
    if args.pdf:
        pdf_paths = [os.path.join(pdf_dir, args.pdf)]
    elif args.all:
        pdf_paths = [os.path.join(pdf_dir, f) for f in PDF_FILES]
    else:
        print("Specify --all or --pdf <filename>")
        sys.exit(1)

    # Process all PDFs
    all_tables = []
    for pdf_path in pdf_paths:
        if not os.path.exists(pdf_path):
            print(f"WARNING: {pdf_path} not found, skipping")
            continue
        tables = process_pdf(pdf_path)
        all_tables.extend(tables)

    print(f"\n{'='*60}")
    print(f"Total tables extracted across all PDFs: {len(all_tables)}")

    # Count unique quarters
    quarters = set(t['quarter_key'] for t in all_tables if t['quarter_key'])
    print(f"Quarters found: {sorted(quarters)}")

    # Build complete.json
    print("\nBuilding bihar_complete.json...")
    complete = build_complete_json(all_tables)

    complete_path = os.path.join(output_dir, 'bihar_complete.json')
    with open(complete_path, 'w') as f:
        json.dump(complete, f, indent=2)
    print(f"  Saved: {complete_path}")
    print(f"  Quarters: {len(complete['quarters'])}")
    for qk in sorted(complete['quarters'].keys()):
        num_tables = len(complete['quarters'][qk]['tables'])
        print(f"    {qk}: {num_tables} tables")

    # Build FI timeseries JSON (nested format for frontend)
    print("\nBuilding bihar_fi_timeseries.json...")
    fi_ts = build_fi_timeseries(complete)
    fi_ts_path = os.path.join(output_dir, 'bihar_fi_timeseries.json')
    with open(fi_ts_path, 'w') as f:
        json.dump(fi_ts, f, indent=2)
    print(f"  Saved: {fi_ts_path}")
    print(f"  Periods: {len(fi_ts['periods'])}")

    # Build flat timeseries records for CSV
    print("\nBuilding bihar_fi_timeseries.csv...")
    ts_records = build_timeseries(complete)
    ts_csv_path = os.path.join(output_dir, 'bihar_fi_timeseries.csv')
    save_timeseries_csv(ts_records, ts_csv_path)

    # Save quarterly CSVs
    print("\nSaving quarterly CSVs...")
    save_quarterly_csvs(complete, output_dir)

    # Summary
    print(f"\n{'='*60}")
    print("EXTRACTION COMPLETE")
    print(f"  Total tables: {len(all_tables)}")
    print(f"  Quarters: {len(quarters)}")
    print(f"  Output directory: {output_dir}")
    print(f"  Files created:")
    print(f"    - bihar_complete.json")
    print(f"    - bihar_fi_timeseries.json")
    print(f"    - bihar_fi_timeseries.csv")
    print(f"    - quarterly/YYYY-MM/category.csv")


if __name__ == '__main__':
    main()
