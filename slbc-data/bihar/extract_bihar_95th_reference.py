#!/usr/bin/env python3
"""
Bihar 95th SLBC Agenda Reference Book Extractor

Extracts district-wise tables from the 273-page reference book PDF for Sep-2025
(quarter ending 30.09.2025). Produces bihar_95th_reference_2025-09.json with
{period, tables: {cat: {fields, districts: {District: {field: value}}}}} shape
matching the existing Bihar extractor's naming convention.

The PDF text has duplicated/echoed glyphs from rotated render-order, so cell
text is post-processed to dedupe.
"""

import pdfplumber
import json
import os
import re
import sys
import warnings
import logging

warnings.filterwarnings("ignore")
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("pdfplumber").setLevel(logging.ERROR)


# Silence noisy "Could not get FontBBox" stderr spam
class _DevNull:
    def write(self, *a, **kw):
        pass
    def flush(self):
        pass


# Bihar's 38 canonical districts (same as extract_bihar_v2.py).
BIHAR_DISTRICTS = [
    "Araria", "Arwal", "Aurangabad", "Banka", "Begusarai", "Bhagalpur",
    "Bhojpur", "Buxar", "Darbhanga", "Gaya", "Gopalganj", "Jamui",
    "Jehanabad", "Kaimur (Bhabua)", "Katihar", "Khagaria", "Kishanganj",
    "Lakhisarai", "Madhepura", "Madhubani", "Munger", "Muzaffarpur",
    "Nalanda", "Nawada", "Pashchim Champaran", "Patna", "Purbi Champaran",
    "Purnia", "Rohtas", "Saharsa", "Samastipur", "Saran", "Sheikhpura",
    "Sheohar", "Sitamarhi", "Siwan", "Supaul", "Vaishali",
]

DISTRICT_ALIASES = {}
for d in BIHAR_DISTRICTS:
    DISTRICT_ALIASES[d.upper()] = d
    DISTRICT_ALIASES[d] = d

DISTRICT_ALIASES.update({
    "KAIMUR(BHABUA)": "Kaimur (Bhabua)", "KAIMUR": "Kaimur (Bhabua)",
    "KAIMUR (BHABHUA)": "Kaimur (Bhabua)", "KAIMUR(BHABHUA)": "Kaimur (Bhabua)",
    "KAIMUR (BHABUA )": "Kaimur (Bhabua)",
    "PASCHIM CHAMPARAN": "Pashchim Champaran", "WEST CHAMPARAN": "Pashchim Champaran",
    "PASHCHIMI CHAMPARAN": "Pashchim Champaran", "P. CHAMPARAN": "Pashchim Champaran",
    "EAST CHAMPARAN": "Purbi Champaran", "PURBA CHAMPARAN": "Purbi Champaran",
    "E. CHAMPARAN": "Purbi Champaran",
    "PURNEA": "Purnia", "PURNEIA": "Purnia",
    "SHEKHPURA": "Sheikhpura", "SEKHPURA": "Sheikhpura",
    # observed scrambled variants from PDF echo
    "ARARAI": "Araria", "ARARAIARARIA": "Araria",
    "ALWAR": "Arwal", "ALWARARWAL": "Arwal", "ARWALARWAL": "Arwal",
    "AURANABAD": "Aurangabad", "AURANABADGAURANGABAD": "Aurangabad",
    "BHALAGPUR": "Bhagalpur",
    "BAHGALPUR": "Bhagalpur",
    "BAHJPUR": "Bhojpur", "BHOPUR": "Bhojpur",
})


# ─── Category detection rules ────────────────────────────────────────────
# Each rule maps {keywords required, keywords forbidden} → category + optional
# explicit field names. Order matters; first match wins.
CATEGORY_RULES = [
    # Branch Network
    {"any_in": "BRANCH NETWORK", "not_in": "BANK WISE",
     "category": "branch_network",
     "fields": ["branch_rural", "branch_semi_urban", "branch_urban", "total_branch"]},
    # Banking outlet BC/CSP
    {"any_in": "BANKING OUTLET", "not_in": "BANK WISE",
     "category": "business_correspondents",
     "fields": ["bc_fixed_point", "bc_other", "bc_total"]},
    # ATM
    {"any_in": "ATM NETWORK", "not_in": "BANK WISE",
     "category": "branch_network",
     "subcategory": "atm_network",
     "fields": ["atm_rural", "atm_semi_urban", "atm_urban", "atm_total"]},
    # POS
    {"any_in": "POINT OF SALE", "not_in": "BANK WISE",
     "category": "branch_network",
     "subcategory": "pos_network",
     "fields": ["pos_rural", "pos_semi_urban", "pos_urban", "pos_total"]},
    # Digital transactions
    {"any_in": "DIGITAL TRANSAC", "not_in": "BANK WISE",
     "category": "digital_transactions",
     "fields": ["bhim_upi_no", "bhim_upi_amt",
                "bhim_aadhaar_no", "bhim_aadhaar_amt",
                "bharat_qr_no", "bharat_qr_amt",
                "imps_no", "imps_amt",
                "cards_no", "cards_amt",
                "ussd_no", "ussd_amt"]},
    # AADHAAR authentication
    {"any_in": "AADHAAR AUTHENTICATION", "not_in": "BANK WISE",
     "category": "aadhaar_authentication",
     "fields": ["aadhaar_operative_casa", "aadhaar_seeded_casa", "aadhaar_authenticated_casa"]},
    # PMJDY
    {"any_in": "PROGRESS UNDER PMJDY", "not_in": "BANK WISE",
     "category": "pmjdy",
     "fields": ["pmjdy_total_no", "pmjdy_opened_fy_no", "pmjdy_zero_balance_no",
                "pmjdy_deposits_held", "pmjdy_rupay_issued_no",
                "pmjdy_rupay_activated_no", "pmjdy_aadhaar_seeded_no"]},
    # Social security (Suraksha Bima Yojna) → PMSBY/PMJJBY/APY enrollment
    {"any_in": "SURAKSHA BIMA YOJNA", "not_in": "BANK WISE",
     "category": "social_security",
     "subcategory": "suraksha_bima_enrolment"},
    # Social security claim status
    {"any_in": "SOCIAL SECURITY CLAIM", "not_in": "BANK WISE",
     "category": "social_security",
     "subcategory": "social_security_claim_status"},
    # ACP Performance
    {"any_in": "PERFORMANCE UNDER ANNUAL CREDIT PLAN", "not_in": "BANK WISE",
     "category": "acp_target_achievement"},
    {"any_in": "PERFORMANCE UNDER ACP", "not_in": "BANK WISE",
     "category": "acp_target_achievement"},
    # ACP priority sector disbursement
    {"any_in": "ACP) PRIORITY SECTOR", "not_in": "BANK WISE",
     "category": "priority_sector_analysis"},
    {"any_in": "ACP - MSME DISBURSEMENT", "not_in": "BANK WISE",
     "category": "msme_outstanding",
     "subcategory": "msme_disbursement",
     "fields": [
         "msme_micro_no", "msme_micro_amt",
         "msme_small_no", "msme_small_amt",
         "msme_medium_no", "msme_medium_amt",
         "msme_other_finance_no", "msme_other_finance_amt",
         "msme_total_no", "msme_total_amt",
     ]},
    # MSME micro/small/medium disbursement - 4 cols: target, disbursed, amt, pct
    {"any_in": "MICRO ENTERPRISES", "not_in": "BANK WISE",
     "category": "msme_outstanding",
     "subcategory": "msme_micro_disbursement",
     "fields": ["msme_micro_target_no", "msme_micro_disbursed_no", "msme_micro_disbursed_amt", "msme_micro_pct"]},
    {"any_in": "SMALL ENTERPRISES", "not_in": "BANK WISE",
     "category": "msme_outstanding",
     "subcategory": "msme_small_disbursement",
     "fields": ["msme_small_target_no", "msme_small_disbursed_no", "msme_small_disbursed_amt", "msme_small_pct"]},
    {"any_in": "MIDIUM ENTERPRISES", "not_in": "BANK WISE",
     "category": "msme_outstanding",
     "subcategory": "msme_medium_disbursement",
     "fields": ["msme_medium_target_no", "msme_medium_disbursed_no", "msme_medium_disbursed_amt", "msme_medium_pct"]},
    {"any_in": "MEDIUM ENTERPRISES", "not_in": "BANK WISE",
     "category": "msme_outstanding",
     "subcategory": "msme_medium_disbursement",
     "fields": ["msme_medium_target_no", "msme_medium_disbursed_no", "msme_medium_disbursed_amt", "msme_medium_pct"]},
    # Other Finance to MSMEs
    {"any_in": "OTHER FINANCE TO MSME", "not_in": "BANK WISE",
     "category": "msme_other_finance",
     "fields": ["msme_other_target_no", "msme_other_disbursed_no", "msme_other_disbursed_amt", "msme_other_pct"]},
    {"any_in": "MSME OUTSTANDING", "not_in": "BANK WISE",
     "category": "msme_outstanding",
     "fields": [
         "msme_micro_no", "msme_micro_amt",
         "msme_small_no", "msme_small_amt",
         "msme_medium_no", "msme_medium_amt",
         "msme_other_finance_no", "msme_other_finance_amt",
         "msme_total_no", "msme_total_amt",
     ]},
    {"any_in": "MSME NPA OUTSTANDING", "not_in": "BANK WISE",
     "category": "msme_npa",
     "fields": [
         "msme_npa_micro_no", "msme_npa_micro_amt",
         "msme_npa_small_no", "msme_npa_small_amt",
         "msme_npa_medium_no", "msme_npa_medium_amt",
         "msme_npa_other_finance_no", "msme_npa_other_finance_amt",
         "msme_npa_total_no", "msme_npa_total_amt",
     ]},
    # Agriculture disbursement & outstanding & NPA
    {"any_in": "AGRICULTURE DISBURSEMENT", "not_in": "BANK WISE",
     "category": "agri_outstanding",
     "subcategory": "agri_disbursement",
     "fields": [
         "agri_crop_loan_no", "agri_crop_loan_amt",
         "agri_term_loan_no", "agri_term_loan_amt",
         "agri_total_farm_credit_no", "agri_total_farm_credit_amt",
         "agri_infrastructure_no", "agri_infrastructure_amt",
         "agri_ancillary_no", "agri_ancillary_amt",
         "agri_total_no", "agri_total_amt",
     ]},
    {"any_in": "AGRICULTURE OUTSTANDING", "not_in": "BANK WISE",
     "category": "agri_outstanding",
     "fields": [
         "agri_crop_loan_no", "agri_crop_loan_amt",
         "agri_term_loan_no", "agri_term_loan_amt",
         "agri_total_farm_credit_no", "agri_total_farm_credit_amt",
         "agri_infrastructure_no", "agri_infrastructure_amt",
         "agri_ancillary_no", "agri_ancillary_amt",
         "agri_total_no", "agri_total_amt",
     ]},
    {"any_in": "ACP - AGRICULTURE OUTSTANDING", "not_in": "BANK WISE",
     "category": "agri_outstanding",
     "fields": [
         "agri_crop_loan_no", "agri_crop_loan_amt",
         "agri_term_loan_no", "agri_term_loan_amt",
         "agri_total_farm_credit_no", "agri_total_farm_credit_amt",
         "agri_infrastructure_no", "agri_infrastructure_amt",
         "agri_ancillary_no", "agri_ancillary_amt",
         "agri_total_no", "agri_total_amt",
     ]},
    {"any_in": "AGRICULTURE NPA OUTSTANDING", "not_in": "BANK WISE",
     "category": "agri_npa",
     "fields": [
         "agri_npa_crop_loan_no", "agri_npa_crop_loan_amt",
         "agri_npa_term_loan_no", "agri_npa_term_loan_amt",
         "agri_npa_total_farm_credit_no", "agri_npa_total_farm_credit_amt",
         "agri_npa_infrastructure_no", "agri_npa_infrastructure_amt",
         "agri_npa_ancillary_no", "agri_npa_ancillary_amt",
         "agri_npa_total_no", "agri_npa_total_amt",
     ]},
    # KCC progress / outstanding
    {"any_in": "KCC PROGRESS REPORT", "not_in": "BANK WISE",
     "category": "kcc",
     "fields": [
         "kcc_new_target_no", "kcc_new_target_amt",
         "kcc_new_disbursed_no", "kcc_new_disbursed_amt",
         "kcc_new_achievement_pct_no", "kcc_new_achievement_pct_amt",
         "kcc_renew_target_no", "kcc_renew_target_amt",
         "kcc_renew_disbursed_no", "kcc_renew_disbursed_amt",
         "kcc_renew_achievement_pct_no", "kcc_renew_achievement_pct_amt",
         "kcc_total_target_no", "kcc_total_target_amt",
         "kcc_total_disbursed_no", "kcc_total_disbursed_amt",
         "kcc_total_achievement_pct_no", "kcc_total_achievement_pct_amt",
     ]},
    {"any_in": "KCC OUTSTANDING", "not_in": "BANK WISE",
     "category": "kcc",
     "subcategory": "kcc_outstanding",
     "fields": [
         "kcc_os_no", "kcc_os_amt",
         "kcc_npa_no", "kcc_npa_amt",
         "kcc_npa_pct_no", "kcc_npa_pct_amt",
         "kcc_rupay_issued_no", "kcc_rupay_issued_amt",
     ]},
    # KCC Animal Husbandry
    {"any_in": "KCC (ANIMAL HUSBANDRY)", "not_in": "BANK WISE",
     "category": "kcc_animal_husbandry"},
    {"any_in": "KCC FOR ANIMAL HUSBANDRY", "not_in": "BANK WISE",
     "category": "kcc_animal_husbandry",
     "subcategory": "kcc_ah_outstanding"},
    {"any_in": "ANIMAL HUSBANDRY (KCC -АН)", "not_in": "BANK WISE",
     "category": "kcc_animal_husbandry"},
    # KCC Fisheries
    {"any_in": "KCC (FISHERIES)", "not_in": "BANK WISE",
     "category": "kcc_fishery"},
    {"any_in": "KCC FISHERIES (KCC-FISH)", "not_in": "BANK WISE",
     "category": "kcc_fishery",
     "subcategory": "kcc_fish_outstanding"},
    # Dairy / Poultry / Fisheries
    {"any_in": "PROGRESS UNDER DAIRY", "not_in": "BANK WISE",
     "category": "dairy"},
    {"any_in": "PROGRESS UNDER POULTRY", "not_in": "BANK WISE",
     "category": "poultry"},
    {"any_in": "PROGRESS UNDER FISHERIES", "not_in": "BANK WISE",
     "category": "fisheries"},
    # Agri term loan / Crop loan / Infra / Ancillary
    {"any_in": "PROGRESS UNDER AGRI TERM LOAN", "not_in": "BANK WISE",
     "category": "agri_term_loan"},
    {"any_in": "PROGRESS UNDER CROP LOAN", "not_in": "BANK WISE",
     "category": "crop_loan"},
    {"any_in": "PROGRESS UNDER AGRI INFRASTRUCTURE", "not_in": "BANK WISE",
     "category": "agri_infrastructure"},
    {"any_in": "AGRI ANCILLARY ACTIVITIES", "not_in": "BANK WISE",
     "category": "agri_ancillary"},
    # JLG
    {"any_in": "DISTRICT WISE JLG", "not_in": "BANK WISE",
     "category": "shg",
     "subcategory": "jlg"},
    # Other disbursement / outstanding / NPA
    {"any_in": "ACP - OTHER DISBURSEMENT", "not_in": "BANK WISE",
     "category": "other_disbursement"},
    {"any_in": "OTHER DISBURSEMENT", "not_in": "BANK WISE",
     "category": "other_disbursement"},
    {"any_in": "OTHER OUTSTANDING", "not_in": "BANK WISE",
     "category": "other_outstanding"},
    {"any_in": "ACP - OTHER NPA OUTSTANDING", "not_in": "BANK WISE",
     "category": "other_npa"},
    # Non Priority Sector
    {"any_in": "NON PRIORITY SECTOR DISBURSEMENT", "not_in": "BANK WISE",
     "category": "non_ps_disbursement"},
    {"any_in": "NON PRIORITY SECTOR OUTSTANDING", "not_in": "BANK WISE",
     "category": "non_ps_outstanding"},
    {"any_in": "NON PRIORITY SECTOR NPA OUTSTANDING", "not_in": "BANK WISE",
     "category": "non_ps_npa"},
    # Education / Housing priority sector
    {"any_in": "EDUCATION LOAN PRIORITY SECTOR", "not_in": "BANK WISE",
     "category": "education_loan",
     "fields": [
         "edu_target_no", "edu_target_amt",
         "edu_disbursed_no", "edu_disbursed_amt",
         "edu_achievement_pct_no", "edu_achievement_pct_amt",
         "edu_outstanding_no", "edu_outstanding_amt",
         "edu_npa_no", "edu_npa_amt",
         "edu_npa_pct_no", "edu_npa_pct_amt",
     ]},
    {"any_in": "HOUSING LOAN PRIORITY SECTOR", "not_in": "BANK WISE",
     "category": "housing_pmay",
     "fields": [
         "housing_target_no", "housing_target_amt",
         "housing_disbursed_no", "housing_disbursed_amt",
         "housing_achievement_pct_no", "housing_achievement_pct_amt",
         "housing_outstanding_no", "housing_outstanding_amt",
         "housing_npa_no", "housing_npa_amt",
         "housing_npa_pct_no", "housing_npa_pct_amt",
     ]},
    # Weaker section & small marginal farmer
    {"any_in": "WEAKER SECTION & SMALL MARGINAL FARMER DISBURSEMENT", "not_in": "BANK WISE",
     "category": "weaker_section_os",
     "subcategory": "weaker_smf_disbursement"},
    {"any_in": "WEAKER SECTION & SMALL MARGINAL FARMER OUTSTANDING", "not_in": "BANK WISE",
     "category": "weaker_section_os"},
    # SC/ST
    {"any_in": "LOANS DISBURSEMENT TO SC/ST", "not_in": "BANK WISE",
     "category": "sc_st_finance"},
    # Minority
    {"any_in": "LOANS DISBURSEMENT TO MINORITY COMMUNITIES", "not_in": "BANK WISE",
     "category": "minority_outstanding",
     "subcategory": "minority_disbursement"},
    {"any_in": "LOANS OUTSTANDING TO MINORITY COMMUNITIES", "not_in": "BANK WISE",
     "category": "minority_outstanding"},
    # Women
    {"any_in": "FINANCE TO WOMEN", "not_in": "BANK WISE",
     "category": "women_finance"},
    # MUDRA / PMMY
    {"any_in": "PMMY -DISBURSEMENT", "not_in": "BANK WISE",
     "category": "mudra",
     "fields": [
         "mudra_shishu_no", "mudra_shishu_amt",
         "mudra_kishor_no", "mudra_kishor_amt",
         "mudra_tarun_no", "mudra_tarun_amt",
         "mudra_tarun_plus_no", "mudra_tarun_plus_amt",
         "mudra_total_no", "mudra_total_amt",
     ]},
    {"any_in": "PMMY DISBURSEMENT", "not_in": "BANK WISE",
     "category": "mudra",
     "fields": [
         "mudra_shishu_no", "mudra_shishu_amt",
         "mudra_kishor_no", "mudra_kishor_amt",
         "mudra_tarun_no", "mudra_tarun_amt",
         "mudra_tarun_plus_no", "mudra_tarun_plus_amt",
         "mudra_total_no", "mudra_total_amt",
     ]},
    {"any_in": "PROGRESS UNDER PMMY", "not_in": "BANK WISE",
     "category": "mudra",
     "fields": [
         "mudra_shishu_no", "mudra_shishu_amt",
         "mudra_kishor_no", "mudra_kishor_amt",
         "mudra_tarun_no", "mudra_tarun_amt",
         "mudra_tarun_plus_no", "mudra_tarun_plus_amt",
         "mudra_total_no", "mudra_total_amt",
     ]},
    {"any_in": "PRADHAN MANTRI MUDRA", "not_in": "BANK WISE",
     "category": "mudra",
     "subcategory": "mudra_outstanding"},
    # PMEGP
    {"any_in": "PMEGP DATA DISTRICT WISE (1ST LOAN", "not_in": "BANK WISE",
     "category": "pmegp",
     "subcategory": "pmegp_1st_loan"},
    {"any_in": "PMEGP DATA DISTRICT WISE 2ND LOAN", "not_in": "BANK WISE",
     "category": "pmegp",
     "subcategory": "pmegp_2nd_loan"},
    # PMFME
    {"any_in": "PMFME DATA", "not_in": "BANK WISE",
     "category": "pmfme"},
    # PM Vishwakarma
    {"any_in": "PM VISHWAKARMA STATUS", "not_in": "BANK WISE",
     "category": "pm_vishwakarma"},
    # PM Surya Ghar
    {"any_in": "PM SURYA GHAR MUFT BIJLI YOJNA AS ON 30.09.2025 (SINCE INCEPTION", "not_in": "BANK WISE",
     "category": "pm_surya_ghar",
     "subcategory": "pm_surya_ghar_inception"},
    {"any_in": "PM SURYA GHAR", "not_in": "BANK WISE",
     "category": "pm_surya_ghar"},
    # CD Ratio
    {"any_in": "DISTRICT WISE CD RATIO", "not_in": "BANK WISE",
     "category": "credit_deposit_ratio",
     "fields": ["total_branch", "total_deposit", "total_advance", "overall_cd_ratio"]},
    # NPA in various sectors
    {"any_in": "NON PERFORMING ASSETS IN VARIOUS SECTOR", "not_in": "BANK WISE",
     "category": "npa_recovery",
     "subcategory": "npa_all_sectors"},
    # SARFAESI / Certificate cases
    {"any_in": "SARFAESI", "not_in": "BANK WISE",
     "category": "sarfaesi"},
    {"any_in": "CERTIFICATE CASES", "not_in": "BANK WISE",
     "category": "recovery_bakijai"},
    # RSETI
    {"any_in": "RSETI", "not_in": "BANK WISE",
     "category": "rseti"},
    # DCC / BLBC
    {"any_in": "DISTRICT CONSULTATIVE COMMITTEE (DCC)", "not_in": "BANK WISE",
     "category": "dcc_meetings"},
    {"any_in": "BLOCK LEVEL BANKER'S COMMITTEE (BLBC)", "not_in": "BANK WISE",
     "category": "dcc_meetings",
     "subcategory": "blbc_meeting"},
    # KCC AH / Fisheries Saturation
    {"any_in": "KCC (AH) SATURATION DATA", "not_in": "BANK WISE",
     "category": "fi_kcc",
     "subcategory": "kcc_ah_saturation"},
    {"any_in": "KCC (FISHERIES) SATURATION DATA", "not_in": "BANK WISE",
     "category": "fi_kcc",
     "subcategory": "kcc_fish_saturation"},
    # 3-month saturation campaign for FI schemes
    {"any_in": "3 MONTHS SATURATION CAMPAIGN", "not_in": "BANK WISE",
     "category": "fi_saturation",
     "subcategory": "saturation_3month"},
    # DEAF / DEAA
    {"any_in": "DEPOSITOR EDUCATION AWARNESS FUND (DEAF)", "not_in": "BANK WISE",
     "category": "deaf"},
    # FL camps
    {"any_in": "COLLECTING -DISTRICT WISE FL CAMPS", "not_in": "BANK WISE",
     "category": "financial_literacy"},
    {"any_in": "FL CAMPS", "not_in": "BANK WISE",
     "category": "financial_literacy"},
]


# ─── Helpers ─────────────────────────────────────────────────────────────

_NUM_CLEAN_RE = re.compile(r"^[\-+]?\d{1,3}(,\d{3})*(\.\d+)?$|^[\-+]?\d+(\.\d+)?$")

def dedupe_echoed_text(s):
    """The PDF renders each cell glyph twice due to overlap of two text layers,
    so a cell text often arrives as 'value value' or 'value\nvalue' or even
    interleaved characters. Dedupe to get the clean atomic value.
    """
    if s is None:
        return ""
    s = str(s).strip()
    if not s:
        return ""
    # remove '|' which appears in many cells from grid separators
    s = s.replace("|", " ").strip()
    # normalize whitespace
    s = re.sub(r"\s+", " ", s)
    # collapse exact dup "X X" → "X"
    parts = s.split(" ")
    if len(parts) >= 2 and len(parts) % 2 == 0:
        half = len(parts) // 2
        if parts[:half] == parts[half:]:
            return " ".join(parts[:half])
    # collapse dup with newlines were already replaced
    # Try halving exact-string dup: "abc\nabc"-style original
    # also try first half == second half on substring
    n = len(s)
    if n % 2 == 0 and s[: n // 2] == s[n // 2 :]:
        return s[: n // 2]
    return s


def parse_number(val):
    if val is None:
        return ""
    v = dedupe_echoed_text(val)
    if v in ("", "-", "NA", "N/A", "NIL", "--", "…", ".", "*"):
        return ""
    v = v.replace(",", "")
    v = v.replace("%", "")
    if v.startswith("(") and v.endswith(")"):
        v = "-" + v[1:-1]
    if _NUM_CLEAN_RE.match(v):
        return v
    # Echo-mangled cells often contain a clean number as a substring inside
    # interleaved glyph noise. Strategy:
    #   1. If the cell is of form 'X X' where both halves are valid numbers, X
    #      is the value (this is already handled by dedupe_echoed_text upstream
    #      via the half-string check).
    #   2. Find all candidate number substrings (including overlapping ones)
    #      and pick the one that appears AT THE END of the string (anchored)
    #      since the cell text typically ends with a clean instance.
    #   3. If still ambiguous, return the longest substring.
    overlapping = []
    for m in re.finditer(r"(?=(\d+(?:\.\d+)?))", v):
        overlapping.append((m.start(1), m.group(1)))
    if overlapping:
        # find the substring ending exactly at end of string with the longest length
        end_pos = len(v.rstrip(" %.|"))
        ends_at_end = [(s, n) for s, n in overlapping if s + len(n) == end_pos]
        if ends_at_end:
            ends_at_end.sort(key=lambda x: -len(x[1]))
            return ends_at_end[0][1]
        # fallback to longest
        overlapping.sort(key=lambda x: -len(x[1]))
        return overlapping[0][1]
    return v  # keep raw if not numeric


_UPPER_KNOWN = sorted(
    {k for k in DISTRICT_ALIASES if k.isupper()},
    key=lambda x: -len(x),
)


def normalize_district(name):
    if not name:
        return None
    raw = dedupe_echoed_text(name)
    if not raw:
        return None
    raw = raw.strip(".,;: ")
    # try exact + uppercase
    if raw in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[raw]
    u = raw.upper()
    if u in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[u]
    # strip leading serial number
    clean = re.sub(r"^\d+[\.\s]+", "", raw).strip()
    u2 = clean.upper()
    if u2 in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[u2]
    # remove all internal whitespace and try matching against compressed names
    comp = re.sub(r"\s+", "", u2)
    for k, v in DISTRICT_ALIASES.items():
        if re.sub(r"\s+", "", k) == comp:
            return v
    # last-resort: substring search of any canonical UPPER district name
    # inside the echo-mangled text. Longest matches preferred to avoid
    # false hits like KAIMUR matching inside another long name.
    comp_no_space = comp
    for k in _UPPER_KNOWN:
        if len(k) < 5:
            continue
        if k.replace(" ", "") in comp_no_space:
            return DISTRICT_ALIASES[k]
    return None


def _clean_header_text(t):
    """For headers like 'Numboeo pr feraitveNumber of operative\nCASACASA',
    return the rightmost clean english sentence by splitting on newlines and
    keeping the unscrambled side of each segment.
    """
    if not t:
        return ""
    pieces = []
    for line in str(t).splitlines():
        line = line.strip()
        if not line:
            continue
        # split into alpha-token groups
        groups = re.findall(r"[A-Za-z][A-Za-z\s&/()+\-.]*", line)
        if not groups:
            continue
        # The echo pattern is "scrambled_word + clean_word" so the LAST group
        # is usually the clean version. Pick the longest of the last 2 groups.
        cand = groups[-2:]
        # pick the one with more spaces (more english-like multi-word)
        cand.sort(key=lambda s: (s.count(" "), len(s)), reverse=True)
        chosen = cand[0].strip()
        pieces.append(chosen)
    return " ".join(pieces)


def make_field_name(header):
    if not header:
        return "unknown"
    t = dedupe_echoed_text(header)
    cleaned = _clean_header_text(t)
    if not cleaned:
        cleaned = t
    lower = cleaned.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", lower)
    t = re.sub(r"\s+", "_", t.strip()).strip("_")
    # collapse repeated double substrings like "casacasa" → "casa"
    n = len(t)
    if n % 2 == 0 and t[: n // 2] == t[n // 2 :]:
        t = t[: n // 2]
    if len(t) > 60:
        t = t[:60].rstrip("_")
    return t or "unknown"


def page_title_text(page):
    """Extract title-region uppercase text used for category classification."""
    text = page.extract_text() or ""
    # build a normalized variant from first ~2500 chars
    head = text[:2500].upper()
    # collapse the echoed glyph noise: insert a space between case transitions
    head = re.sub(r"\s+", " ", head)
    return head


def detect_category(page):
    title = page_title_text(page)
    for rule in CATEGORY_RULES:
        kw = rule.get("any_in", "")
        nk = rule.get("not_in", "")
        if kw and kw not in title:
            continue
        if nk and nk in title:
            continue
        cat = rule["category"]
        sub = rule.get("subcategory", cat)
        fields = rule.get("fields")
        return cat, sub, fields
    return None


def extract_district_rows(table):
    """Find rows whose first-or-second cell is a district name. Returns
    list of (canonical_district, [cleaned_values])."""
    rows = []
    seen = set()
    for r in table:
        if not r or len(r) < 3:
            continue
        # try cells 0..2 for district name
        d = None
        start = None
        for ci in range(min(3, len(r))):
            cell = r[ci]
            if cell is None:
                continue
            txt = dedupe_echoed_text(cell)
            if not txt:
                continue
            # skip pure SR.No.
            if re.match(r"^\d+\.?$", txt):
                continue
            dist = normalize_district(txt)
            if dist:
                d = dist
                start = ci + 1
                # If the next cell is *also* a district name, the layout has
                # serial+scrambled-district in col[ci] and the clean name in
                # col[ci+1]. Values start one column further right.
                if start < len(r):
                    next_cell = r[start]
                    next_txt = dedupe_echoed_text(next_cell or "")
                    if next_txt and normalize_district(next_txt):
                        start += 1
                break
        if not d:
            continue
        # avoid duplicate row (table may have a stray repeated row)
        if d in seen:
            continue
        seen.add(d)
        values = [parse_number(c) for c in r[start:]]
        rows.append((d, values))
    return rows


def extract_headers(table):
    """Pull header rows above the first district row to build column names."""
    header_rows = []
    for r in table:
        if not r:
            continue
        first = dedupe_echoed_text(r[0] or "")
        # detect district-data row by checking col 0 or 1 for serial+district
        is_data = False
        for ci in range(min(3, len(r))):
            cell = dedupe_echoed_text(r[ci] or "")
            if normalize_district(cell):
                is_data = True
                break
        if is_data:
            break
        header_rows.append(r)
    if not header_rows:
        return []
    ncols = max(len(r) for r in header_rows)
    headers = []
    for col in range(ncols):
        parts = []
        for hr in header_rows:
            if col < len(hr) and hr[col]:
                t = dedupe_echoed_text(hr[col])
                if not t:
                    continue
                if t.upper() in ("SR.", "SR.NO.", "SR. NO.", "S.NO.", "SL.NO.",
                                  "NAME OF DISTRICT", "DISTRICT NAME",
                                  "NAME OF BANK"):
                    continue
                if t not in parts:
                    parts.append(t)
        headers.append(" ".join(parts).strip())
    return headers


# ─── Main extraction ─────────────────────────────────────────────────────

def extract_pdf(pdf_path):
    pdf = pdfplumber.open(pdf_path)
    print(f"Pages: {len(pdf.pages)}", file=sys.stderr)

    extracted = []  # list of dicts
    for i, page in enumerate(pdf.pages):
        page_num = i + 1
        cat_result = detect_category(page)
        if not cat_result:
            continue
        category, subcategory, predefined_fields = cat_result
        tables = page.extract_tables()
        if not tables:
            continue
        table = max(tables, key=lambda t: len(t))
        if len(table) < 10:
            continue
        district_rows = extract_district_rows(table)
        if len(district_rows) < 15:
            continue
        # Trim trailing columns that are empty for ALL district rows (these are
        # spurious extra cells produced by the pdf cell splitter).
        if district_rows:
            longest = max(len(v) for _, v in district_rows)
            while longest > 0:
                if all(
                    (len(v) < longest) or (v[longest - 1] in ("", None))
                    for _, v in district_rows
                ):
                    longest -= 1
                else:
                    break
            district_rows = [(d, v[:longest]) for d, v in district_rows]
        max_vals = max((len(v) for _, v in district_rows), default=0)
        if max_vals == 0:
            continue
        raw_headers = extract_headers(table)
        # skip SR.No / district headers
        skip = 0
        for h in raw_headers:
            hu = h.upper()
            if any(x in hu for x in ("SR", "SL", "S.N", "DISTRICT", "NAME OF")):
                skip += 1
            else:
                break
        if skip < 2:
            skip = 2
        value_headers = raw_headers[skip:]
        if predefined_fields and len(predefined_fields) >= max_vals:
            fields = predefined_fields[:max_vals]
        elif value_headers and len(value_headers) >= max_vals:
            fields = [make_field_name(h) for h in value_headers[:max_vals]]
        else:
            # fall back to col_1.. but still try to derive names
            fields = [
                make_field_name(value_headers[i]) if i < len(value_headers) else f"col_{i+1}"
                for i in range(max_vals)
            ]
        # dedupe duplicate field names
        seen = {}
        unique_fields = []
        for f in fields:
            base = f
            n = seen.get(base, 0)
            if n:
                f = f"{base}_{n+1}"
            seen[base] = n + 1
            unique_fields.append(f)
        fields = unique_fields
        # build district map
        districts = {}
        for dist, vals in district_rows:
            while len(vals) < len(fields):
                vals.append("")
            districts[dist] = dict(zip(fields, vals[: len(fields)]))
        extracted.append({
            "page": page_num,
            "category": category,
            "subcategory": subcategory,
            "fields": fields,
            "districts": districts,
        })
        print(
            f"  P{page_num:>3}: {subcategory:<35} ({len(districts)} districts, "
            f"{len(fields)} cols)",
            file=sys.stderr,
        )
    pdf.close()
    return extracted


def build_output(extracted, period_label="September 2025"):
    out = {
        "source": "SLBC Bihar 95th Agenda Reference Book",
        "state": "Bihar",
        "period": period_label,
        "amount_unit": "Rs. Crore",
        "tables": {},
    }
    for e in extracted:
        key = e["subcategory"]
        base = key
        n = 2
        while key in out["tables"]:
            key = f"{base}_{n}"
            n += 1
        out["tables"][key] = {
            "category": e["category"],
            "subcategory": e["subcategory"],
            "page": e["page"],
            "fields": e["fields"],
            "num_districts": len(e["districts"]),
            "districts": e["districts"],
        }
    return out


def main():
    pdf_path = "/Users/abhinav/Downloads/95th SLBC Agenda Reference Book.pdf"
    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "bihar_95th_reference_2025-09.json",
    )
    # redirect FontBBox / cropbox warnings
    sys.stderr_real = sys.stderr
    sys.stderr = _DevNull()
    try:
        extracted = extract_pdf(pdf_path)
    finally:
        sys.stderr = sys.stderr_real

    print(f"\nExtracted {len(extracted)} district-wise tables")
    out = build_output(extracted)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved → {out_path}")
    # summary
    n_cells = sum(
        sum(1 for v in row.values() if v not in ("", None))
        for tbl in out["tables"].values()
        for row in tbl["districts"].values()
    )
    print(f"Total non-empty (district, field) cells: {n_cells}")


if __name__ == "__main__":
    main()
