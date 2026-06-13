#!/usr/bin/env python3
"""
Normalize the Rajasthan Wayback haul into FINER canonical schema.

Mirrors db/normalize_wayback_hp.py / _bihar_2016.py / _kerala_cdratio.py.
Reads raw extracts at slbc-data/rajasthan/wayback/extracted/ (produced by
db/extract_wayback_rajasthan.py) and merges 31 new historical periods
(Dec 2013 → Jun 2025) into:

  public/slbc-data/rajasthan/rajasthan_fi_timeseries.json
  public/slbc-data/rajasthan/rajasthan_complete.json   (Rajasthan shape:
        quarters[key] = {period, as_on_date, fy, tables{cat:{fields,
        districts: {NAME: {field: value}}}}})
  public/slbc-data/rajasthan/rajasthan_fi_timeseries.csv  (wide, rebuilt)
  public/slbc-data/rajasthan/rajasthan_fi_slim.json       (rebuilt)

Rajasthan live data previously had only Sep 2025 + Dec 2025.

CATEGORIES (same names as the live v2-extractor data):
  credit_deposit_ratio  total_deposit / total_advances / overall_cd_ratio
  acp_accounts          modern A/C+AMT ACP achievement annexes (2020-12 →)
  acp_summary           older Target/Achievement ACP annexes (2013-12 → 2018-06)
  pmjdy                 pmjdy_total_ac / pmjdy_total_deposit / rupay / aadhaar…
  apy                   apy_branches / apy_annual_target / … (Jun 2025)

UNITS — canonical FINER unit is Rs. Lakhs. Per-file unit decided from
VERBATIM in-file evidence, cross-checked against value magnitude:
  * "Amt in Rs. Lacs"        → stored as-is.
  * "Amt in Thousands"       → ÷100 to Lakhs. Verified per file via the
    agri amount-per-account ratio (genuine Thousands files run 100-160
    thousand/acct ≈ ₹1-1.6 lakh/acct; Lakhs files run 1-2 lakh/acct).
  * acpmar24 says "Thousands" but the amt/ac ratio (1.67) and the FY
    trajectory prove the values are ALREADY Lakhs (Haryana-style
    mislabel, cf. CLAUDE.md Haryana 156th/160th) → stored as-is.
  * Files without a printed unit (acpdec13/14, acpsept15, acpjune18,
    Annex II Dec 2024) were pinned by exact target identity with a
    labelled sibling of the same FY, or by quarter-adjacent series
    continuity with labelled files. Details in the BATCHES comments.
  * PMJDY deposits: Dec 2024 header says "(Rs. In Crores)"; Jun 2025
    prints actual rupees. NOTE: the LIVE Rajasthan quarters (Sep/Dec
    2025, from the v2 XLSX extractor) store pmjdy_total_deposit in
    ACTUAL RUPEES (verbatim from source, e.g. Jaipur Dec 2025 =
    24,056,234,311). To keep the field's time series continuous we
    store wayback PMJDY deposits in actual rupees too (Crores ×1e7).
    Every other monetary field is in Lakhs.

DISTRICTS: resolved to the 33 canonical names used by the live data
(note live uses 'Ganganagar', 'Jalore', 'Dholpur', 'Sawai Madhopur').
Total/Grand-Total rows dropped. Post-2023 reorg districts (Balotra,
Beawar, Phalodi, Jaipur Gramin/Urban, …) are NOT in the live site data
→ their rows are dropped and reported (see --dry-run output).

DEDUPE: live site wins (existing period+district+field kept untouched);
when two snapshots cover the same file the later snapshot is used
(the *__2025.json variants).

After this runs:
  python3 db/regenerate_indicator_files_from_states.py
  python3 validate_data.py --state rajasthan
(Do NOT run build_district_pages.py here — separate consolidated step.)
"""
from __future__ import annotations
import argparse
import calendar
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = 'rajasthan'
WAYBACK_DIR = ROOT / 'slbc-data' / STATE / 'wayback' / 'extracted'
PUB = ROOT / 'public/slbc-data' / STATE
TIMESERIES_PATH = PUB / f'{STATE}_fi_timeseries.json'
COMPLETE_PATH = PUB / f'{STATE}_complete.json'
CSV_PATH = PUB / f'{STATE}_fi_timeseries.csv'
SLIM_PATH = PUB / f'{STATE}_fi_slim.json'

# ---------------------------------------------------------------------------
# Districts — exact-key matching only (contains-matching would wrongly fold
# 'Jaipur Gramin' into 'Jaipur'). Keys = lowercase, non-letters stripped.
# Canonical display names = the 33 districts in the live Sep/Dec 2025 data.
# ---------------------------------------------------------------------------
LIVE_33 = ['Ajmer', 'Alwar', 'Banswara', 'Baran', 'Barmer', 'Bharatpur',
           'Bhilwara', 'Bikaner', 'Bundi', 'Chittorgarh', 'Churu', 'Dausa',
           'Dholpur', 'Dungarpur', 'Ganganagar', 'Hanumangarh', 'Jaipur',
           'Jaisalmer', 'Jalore', 'Jhalawar', 'Jhunjhunu', 'Jodhpur',
           'Karauli', 'Kota', 'Nagaur', 'Pali', 'Pratapgarh', 'Rajsamand',
           'Sawai Madhopur', 'Sikar', 'Sirohi', 'Tonk', 'Udaipur']

CANON = {re.sub(r'[^a-z]', '', d.lower()): d for d in LIVE_33}
CANON.update({
    # spelling variants seen in the wayback annexes
    'jhalwar': 'Jhalawar',
    'jhunjunu': 'Jhunjhunu',
    'rajasmand': 'Rajsamand',
    'chittaurgarh': 'Chittorgarh',
    'dhaulpur': 'Dholpur',
    'jalor': 'Jalore',
    'sriganganagar': 'Ganganagar',
    'sganganagar': 'Ganganagar',
    'sawaimadhopur': 'Sawai Madhopur',
    'smadhopur': 'Sawai Madhopur',
    'smadh': 'Sawai Madhopur',          # 'S.MADH' (truncated cell, 2013/14)
    'sawai': 'Sawai Madhopur',           # 'SAWAI' (wrapped cell, 2025 ACP)
})

# Post-2023 reorg districts — present in the 2024/2025 annexes but NOT in
# the live site data. Dropped + reported (task rule: keep only if the
# existing site data has them, else report).
REORG = {
    'anoopgarh': 'Anupgarh', 'anupgarh': 'Anupgarh',
    'balotra': 'Balotra', 'beawar': 'Beawar', 'deeg': 'Deeg',
    'didwana': 'Didwana-Kuchaman', 'didwanakuchaman': 'Didwana-Kuchaman',
    'dudu': 'Dudu', 'gangapurcity': 'Gangapur City',
    'jaipurgramin': 'Jaipur Gramin', 'jaipururban': 'Jaipur Urban',
    'jodhpurgramin': 'Jodhpur Gramin', 'jodhpururban': 'Jodhpur Urban',
    'kekri': 'Kekri',
    'khairthaltijara': 'Khairthal-Tijara',
    'kotputlibehror': 'Kotputli-Behror', 'kotpultibehror': 'Kotputli-Behror',
    'neemkathana': 'Neem Ka Thana', 'phalodi': 'Phalodi',
    'salumbar': 'Salumbar', 'sanchor': 'Sanchore', 'sanchore': 'Sanchore',
    'shahpura': 'Shahpura',
}

DROPPED_REORG: dict[str, set] = {}   # period_key -> set of reorg names


def canon_key(s: str) -> str:
    return re.sub(r'[^a-z]', '', str(s).lower())


def canon_district(s: str, period_key: str | None = None) -> str | None:
    if not s:
        return None
    key = canon_key(s)
    if not key:
        return None
    if key in CANON:
        return CANON[key]
    if key in REORG and period_key:
        DROPPED_REORG.setdefault(period_key, set()).add(REORG[key])
    return None


def parse_num(s) -> str | None:
    """Cleaned numeric string or None. Strips commas / % / currency."""
    if s is None:
        return None
    s = str(s).strip().replace(',', '').replace('%', '').replace('₹', '')
    if not s or s.upper() in {'NA', 'N/A', '-', '—', 'NIL'}:
        return None
    try:
        float(s)
        return s
    except ValueError:
        return None


def scaled(s, factor: float) -> str | None:
    """parse_num + multiply by factor (1 = passthrough), trimmed string."""
    v = parse_num(s)
    if v is None:
        return None
    if factor == 1:
        return v
    out = float(v) * factor
    return f'{out:.2f}'.rstrip('0').rstrip('.')


def load_raw(name: str) -> dict:
    p = WAYBACK_DIR / f'{name}.json'
    if not p.exists():
        print(f'ERROR: {p} missing — run db/extract_wayback_rajasthan.py first',
              file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text())


def cell(r, i):
    return r[i] if i < len(r) else None


# ---------------------------------------------------------------------------
# Mappers. Each returns {district: {category: {field: value}}}.
# ---------------------------------------------------------------------------

def map_cd_5col(raw, pk, **kw):
    """Sr | District | Deposit | Advance | CD Ratio   (Rs. Lacs)"""
    out = {}
    for r in raw['rows']:
        d = canon_district(cell(r, raw['districtColumn']), pk)
        if not d:
            continue
        dep, adv, cdr = parse_num(cell(r, 2)), parse_num(cell(r, 3)), parse_num(cell(r, 4))
        cat = out.setdefault(d, {}).setdefault('credit_deposit_ratio', {})
        if dep: cat['total_deposit'] = dep
        if adv: cat['total_advances'] = adv
        if cdr: cat['overall_cd_ratio'] = cdr
    return out


def map_cd_annex2(raw, pk, **kw):
    """Sr | District Name | District Code | Total Deposit | Total Credit |
    CD Ratio | Remarks. No printed unit; values sit exactly on the series
    of the 'Rs. Lacs'-labelled Mar/Jun 2025 files and live Sep/Dec 2025
    (Ajmer 3.36M → 3.78M → 3.82M → … Lakhs) → Lakhs."""
    out = {}
    for r in raw['rows']:
        d = canon_district(cell(r, raw['districtColumn']), pk)
        if not d:
            continue
        dep, adv, cdr = parse_num(cell(r, 3)), parse_num(cell(r, 4)), parse_num(cell(r, 5))
        cat = out.setdefault(d, {}).setdefault('credit_deposit_ratio', {})
        if dep: cat['total_deposit'] = dep
        if adv: cat['total_advances'] = adv
        if cdr: cat['overall_cd_ratio'] = cdr
    return out


def map_pmjdy_dec24(raw, pk, **kw):
    """Sr | District | Rural A/C | Urban A/C | Male A/C | Female A/C |
    Total A/C | Total Deposit (Rs. In Crores) | Zero Balance | RupayCard |
    %Rupay | Aadhaar | %Aadhaar.
    Deposit: Crores → ACTUAL RUPEES (×1e7) to match the live series
    convention for pmjdy_total_deposit (see module docstring)."""
    out = {}
    for r in raw['rows']:
        d = canon_district(cell(r, raw['districtColumn']), pk)
        if not d:
            continue
        cat = out.setdefault(d, {}).setdefault('pmjdy', {})
        for idx, f in [(2, 'pmjdy_rural_ac'), (3, 'pmjdy_urban_ac'),
                       (4, 'pmjdy_male_ac'), (5, 'pmjdy_female_ac'),
                       (6, 'pmjdy_total_ac'), (8, 'pmjdy_zero_balance'),
                       (9, 'pmjdy_rupay_issued'), (10, 'pmjdy_rupay_pct'),
                       (11, 'pmjdy_aadhaar_seeded'), (12, 'pmjdy_aadhaar_pct')]:
            v = parse_num(cell(r, idx))
            if v: cat[f] = v
        dep = scaled(cell(r, 7), 1e7)   # Crores → actual rupees
        if dep: cat['pmjdy_total_deposit'] = dep
    return out


def map_pmjdy_jun25(raw, pk, **kw):
    """S.No | Districts | Total A/C | Total Deposit | Zero Balance |
    %Zero | RupayCard | %Rupay | Aadhaar | %Aadhaar.
    Deposit prints actual rupees (Ajmer 8,279,357,396 = ₹827.9 Cr,
    continuous with the Dec 2024 Crores-labelled 739.03 Cr and the live
    Sep 2025 rupee-valued series) → stored as-is (rupees)."""
    out = {}
    for r in raw['rows']:
        d = canon_district(cell(r, raw['districtColumn']), pk)
        if not d:
            continue
        cat = out.setdefault(d, {}).setdefault('pmjdy', {})
        for idx, f in [(2, 'pmjdy_total_ac'), (3, 'pmjdy_total_deposit'),
                       (4, 'pmjdy_zero_balance'), (5, 'pmjdy_zero_balance_pct'),
                       (6, 'pmjdy_rupay_issued'), (7, 'pmjdy_rupay_pct'),
                       (8, 'pmjdy_aadhaar_seeded'), (9, 'pmjdy_aadhaar_pct')]:
            v = parse_num(cell(r, idx))
            if v: cat[f] = v
    return out


def map_apy_jun25(raw, pk, **kw):
    """S.No | Districts | No. of Branches | Annual Target | opened in FY |
    Target achievement % | Cumulative. All counts/% — no unit conversion."""
    out = {}
    for r in raw['rows']:
        d = canon_district(cell(r, raw['districtColumn']), pk)
        if not d:
            continue
        cat = out.setdefault(d, {}).setdefault('apy', {})
        for idx, f in [(2, 'apy_branches'), (3, 'apy_annual_target'),
                       (4, 'apy_current_fy_achievement'), (5, 'apy_target_pct'),
                       (6, 'apy_cumulative')]:
            v = parse_num(cell(r, idx))
            if v: cat[f] = v
    return out


# modern ACP achievement annexe: Sr | District | AGRI A/C,AMT | MSE A/C,AMT |
# ME A/C,AMT | MSME-total A/C,AMT | OPS A/C,AMT | TPS A/C,AMT | Weaker A/C,AMT
ACP16_FIELDS = [
    (2, 'acp_agri_ac', False), (3, 'acp_agri_amt', True),
    (4, 'acp_mse_ac', False), (5, 'acp_mse_amt', True),
    (6, 'acp_me_ac', False), (7, 'acp_me_amt', True),
    (8, 'acp_msme_ac', False), (9, 'acp_msme_amt', True),
    (10, 'acp_ops_ac', False), (11, 'acp_ops_amt', True),
    (12, 'acp_total_ps_ac', False), (13, 'acp_total_ps_amt', True),
    (14, 'acp_weaker_section_ac', False), (15, 'acp_weaker_section_amt', True),
]


def map_acp16(raw, pk, amt_factor=1, **kw):
    out = {}
    for r in raw['rows']:
        d = canon_district(cell(r, raw['districtColumn']), pk)
        if not d:
            continue
        cat = out.setdefault(d, {}).setdefault('acp_accounts', {})
        for idx, f, is_amt in ACP16_FIELDS:
            v = scaled(cell(r, idx), amt_factor) if is_amt else parse_num(cell(r, idx))
            if v: cat[f] = v
    return out


def map_acp46(raw, pk, amt_factor=1, **kw):
    """acpdec20: same fields as acp16 but spread over 46 sparse columns."""
    idxmap = [(4, 'acp_agri_ac', False), (7, 'acp_agri_amt', True),
              (10, 'acp_mse_ac', False), (13, 'acp_mse_amt', True),
              (16, 'acp_me_ac', False), (19, 'acp_me_amt', True),
              (22, 'acp_msme_ac', False), (25, 'acp_msme_amt', True),
              (28, 'acp_ops_ac', False), (31, 'acp_ops_amt', True),
              (34, 'acp_total_ps_ac', False), (37, 'acp_total_ps_amt', True),
              (40, 'acp_weaker_section_ac', False), (43, 'acp_weaker_section_amt', True)]
    out = {}
    for r in raw['rows']:
        d = canon_district(cell(r, raw['districtColumn']), pk)
        if not d:
            continue
        cat = out.setdefault(d, {}).setdefault('acp_accounts', {})
        for idx, f, is_amt in idxmap:
            v = scaled(cell(r, idx), amt_factor) if is_amt else parse_num(cell(r, idx))
            if v: cat[f] = v
    return out


def map_acp_ta(raw, pk, idxmap=None, pct_idx=None, amt_factor=1, **kw):
    """Older Target/Achievement ACP annexes → acp_summary.
    idxmap: list of (target_idx, achiev_idx, sector) with sector in
    {agri, mse, me, ops, total_ps}."""
    out = {}
    for r in raw['rows']:
        d = canon_district(cell(r, raw['districtColumn']), pk)
        if not d:
            continue
        cat = out.setdefault(d, {}).setdefault('acp_summary', {})
        for t_idx, a_idx, sector in idxmap:
            t = scaled(cell(r, t_idx), amt_factor)
            a = scaled(cell(r, a_idx), amt_factor)
            if t: cat[f'acp_{sector}_target'] = t
            if a: cat[f'acp_{sector}_achievement'] = a
        if pct_idx is not None:
            p = parse_num(cell(r, pct_idx))
            if p: cat['acp_total_ps_pct'] = p
    return out


MAPPERS = {
    'cd_5col': map_cd_5col,
    'cd_annex2': map_cd_annex2,
    'pmjdy_dec24': map_pmjdy_dec24,
    'pmjdy_jun25': map_pmjdy_jun25,
    'apy_jun25': map_apy_jun25,
    'acp16': map_acp16,
    'acp46': map_acp46,
    'acp_ta': map_acp_ta,
}

# Column maps for the Target/Achievement era formats (verified row-by-row:
# TPS target == sum of component targets in every format).
TA9 = [(1, 2, 'agri'), (3, 4, 'mse'), (5, 6, 'ops'), (7, 8, 'total_ps')]
TA11 = [(2, 3, 'agri'), (4, 5, 'mse'), (6, 7, 'ops'), (8, 9, 'total_ps')]
TA12 = [(2, 3, 'agri'), (4, 5, 'mse'), (6, 7, 'me'), (8, 9, 'ops'),
        (10, 11, 'total_ps')]
TA14 = [(2, 3, 'agri'), (4, 6, 'mse'), (7, 8, 'me'), (10, 11, 'ops'),
        (12, 13, 'total_ps')]
TA21 = [(1, 2, 'agri'), (5, 6, 'mse'), (9, 10, 'ops'), (13, 14, 'total_ps')]
TA31 = [(2, 4, 'agri'), (8, 10, 'mse'), (14, 16, 'ops'), (20, 22, 'total_ps')]
TA36 = [(6, 9, 'agri'), (12, 15, 'mse'), (18, 21, 'me'), (24, 27, 'ops'),
        (30, 33, 'total_ps')]

# ---------------------------------------------------------------------------
# Batches. One entry per (source file, period). The *__2025 variants are the
# later Wayback snapshots of the same upstream file — preferred per the
# "later snapshot wins" rule (contents verified identical to the originals).
# UNIT EVIDENCE quoted verbatim from each file's title.
# ---------------------------------------------------------------------------
BATCHES = [
    # ---- ACP Target/Achievement era (acp_summary), all Rs. Lakhs --------
    # acpdec13: no printed unit (Devanagari heading). FY2013-14 Ajmer TPS
    # target 268240 → as Thousands it'd be ₹26.8 Cr (absurd, 100× below
    # the labelled FY2014-15 'Amt in Lacs' target 346759); as Crores it'd
    # exceed the state economy. Lakhs by magnitude elimination.
    dict(source='acpdec13__2025', period='2013-12', mapper='acp_ta',
         idxmap=TA11, pct_idx=10),
    # acpsept14: "(Amt in Lacs)" verbatim.
    dict(source='acpsept14__2025', period='2014-09', mapper='acp_ta', idxmap=TA21),
    # acpdec14: no printed unit, but FY2014-15 targets (Ajmer 195076 /
    # 75800 / 75883 / 346759) are EXACTLY the targets in the
    # "(Amt in Lacs)"-labelled acpsept14 → Lakhs.
    dict(source='acpdec14__2025', period='2014-12', mapper='acp_ta', idxmap=TA31),
    # acpjune15 + acpdec15: "(Amt in Rs. Lacs)" verbatim.
    dict(source='acpjune15__2025', period='2015-06', mapper='acp_ta', idxmap=TA9),
    # acpsept15: no printed unit; FY2015-16 targets (Ajmer 257756/78601/
    # 73907/410264) exactly match the labelled acpdec15/acpjune15 → Lakhs.
    dict(source='acpsept15__2025', period='2015-09', mapper='acp_ta', idxmap=TA9),
    dict(source='acpdec15__2025', period='2015-12', mapper='acp_ta', idxmap=TA9),
    # 2016-2018: "(Amt in Rs. Lacs)" / "Amt. in Rs. Lacs" verbatim.
    dict(source='acpmar16__2025', period='2016-03', mapper='acp_ta', idxmap=TA12),
    dict(source='acpjune16__2025', period='2016-06', mapper='acp_ta', idxmap=TA12),
    dict(source='acpsept16__2025', period='2016-09', mapper='acp_ta', idxmap=TA12),
    dict(source='acpmar17__2025', period='2017-03', mapper='acp_ta', idxmap=TA14),
    dict(source='acpsept17__2025', period='2017-09', mapper='acp_ta', idxmap=TA14),
    dict(source='acpmar18', period='2018-03', mapper='acp_ta', idxmap=TA36),
    # acpjune18: unit line lost in extraction; FY2018-19 Ajmer agri target
    # 336634 is continuous with the labelled FY2017-18 'Rs. Lacs' target
    # 329106 (same magnitude; Thousands/Crores off by 100×) → Lakhs.
    dict(source='acpjune18__2025', period='2018-06', mapper='acp_ta', idxmap=TA12),

    # ---- ACP achievement A/C+AMT era (acp_accounts) ---------------------
    # acpdec20: "Amt in Rs. Lacs" verbatim (agri amt/ac ratio 1.25 ✓).
    # NOTE: source table page captured only districts Ajmer→Jhunjhunu (24).
    dict(source='acpdec20', period='2020-12', mapper='acp46'),
    # acpmar21: "Amt in Rs. Lacs" verbatim (ratio 1.39 ✓). 22 districts.
    dict(source='acpmar21', period='2021-03', mapper='acp16'),
    # 2021-06 → 2023-12: "Amt in Thousand(s)" verbatim; agri amt/ac ratio
    # 108-162 (₹1.1-1.6 lakh/acct) confirms genuine Thousands → ÷100.
    dict(source='acpjune21__2025', period='2021-06', mapper='acp16', amt_factor=0.01),
    dict(source='acpsept21__2025', period='2021-09', mapper='acp16', amt_factor=0.01),
    dict(source='acpdec21__2025', period='2021-12', mapper='acp16', amt_factor=0.01),
    dict(source='acpmar22__2025', period='2022-03', mapper='acp16', amt_factor=0.01),
    dict(source='acpsept22__2025', period='2022-09', mapper='acp16', amt_factor=0.01),
    dict(source='ACPachievementDec22__2025', period='2022-12', mapper='acp16',
         amt_factor=0.01),
    dict(source='acpmar23__2025', period='2023-03', mapper='acp16', amt_factor=0.01),
    dict(source='acpjune23__2025', period='2023-06', mapper='acp16', amt_factor=0.01),
    dict(source='acpsept23__2025', period='2023-09', mapper='acp16', amt_factor=0.01),
    dict(source='ACPachievementDec23__2025', period='2023-12', mapper='acp16',
         amt_factor=0.01),
    # acpmar24: title says "Amt in Thousands" but values are ALREADY Lakhs —
    # agri amt/ac ratio 1.67 (vs 100-160 in genuine Thousands files) and the
    # FY trajectory (Ajmer agri 560370 vs Mar 2025 'Rs. Lacs' 479862)
    # prove a source mislabel → stored as-is (Lakhs).
    dict(source='acpmar24__2025', period='2024-03', mapper='acp16'),
    # 2024-06 → 2025-06: "Amt in Rs. Lacs" verbatim (ratios 1.1-1.9 ✓).
    dict(source='acpjune24__2025', period='2024-06', mapper='acp16'),
    dict(source='acpsept24__2025', period='2024-09', mapper='acp16'),
    dict(source='District_wise_ACP_Dec_2024', period='2024-12', mapper='acp16'),
    # ACP.json (snap 2025-07-25) preferred over the identical
    # ACP_PROGRESS_SUMMARY.json (snap 2025-07-11).
    dict(source='ACP', period='2025-03', mapper='acp16'),
    dict(source='District_ACP', period='2025-06', mapper='acp16'),

    # ---- Credit-Deposit ratio -------------------------------------------
    # Annex II Dec 2024: no printed unit — Lakhs by series continuity with
    # the labelled Mar/Jun 2025 files + live Sep/Dec 2025 (see mapper doc).
    # NOTE: Udaipur is genuinely absent from this source table.
    dict(source='Annex._II-31st_Dec_2024', period='2024-12', mapper='cd_annex2'),
    # "Amt in Rs. Lacs" verbatim. C_D_RATIO_1_ (snap 2025-07-25) preferred
    # over identical C_D_RATIO (snap 2025-07-11).
    dict(source='C_D_RATIO_1_', period='2025-03', mapper='cd_5col'),
    dict(source='CD_Ratio', period='2025-06', mapper='cd_5col'),

    # ---- PMJDY ------------------------------------------------------------
    dict(source='PMJDYNew', period='2024-12', mapper='pmjdy_dec24'),
    dict(source='PMJDY_30.06.2025', period='2025-06', mapper='pmjdy_jun25'),

    # ---- APY --------------------------------------------------------------
    dict(source='APY_30.06.2025', period='2025-06', mapper='apy_jun25'),
]

MONTH_NAMES = {1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May',
               6: 'June', 7: 'July', 8: 'August', 9: 'September',
               10: 'October', 11: 'November', 12: 'December'}


def period_label(pk: str) -> str:
    y, m = pk.split('-')
    return f'{MONTH_NAMES[int(m)]} {y}'


def as_on_date(pk: str) -> str:
    y, m = int(pk[:4]), int(pk[5:7])
    return f'{calendar.monthrange(y, m)[1]:02d}-{m:02d}-{y}'


def fy_of(pk: str) -> str:
    y, m = int(pk[:4]), int(pk[5:7])
    start = y if m >= 4 else y - 1
    return f'{start}-{str(start + 1)[-2:]}'


def merge_district_data(into: dict, addition: dict):
    for d, cats in addition.items():
        into.setdefault(d, {})
        for cat, fields in cats.items():
            into[d].setdefault(cat, {}).update(fields)


def build_period_entry(district_data: dict, label: str) -> dict:
    rows = []
    for d in sorted(district_data.keys()):
        flat = {'district': d, 'period': label}
        for cat in sorted(district_data[d].keys()):
            for f, v in district_data[d][cat].items():
                flat[f'{cat}__{f}'] = v
        rows.append(flat)
    return {'period': label, 'districts': rows}


def build_complete_entry(district_data: dict, pk: str) -> dict:
    """Rajasthan _complete shape: tables{cat: {fields, districts: {NAME: {...}}}}"""
    by_cat: dict[str, dict] = {}
    for d in sorted(district_data.keys()):
        for cat, fields in district_data[d].items():
            by_cat.setdefault(cat, {})[d] = dict(fields)
    tables = {}
    for cat, dists in by_cat.items():
        fnames, seen = [], set()
        for row in dists.values():
            for k in row:
                if k not in seen:
                    fnames.append(k)
                    seen.add(k)
        tables[cat] = {'fields': fnames, 'districts': dists}
    return {'period': period_label(pk), 'as_on_date': as_on_date(pk),
            'fy': fy_of(pk), 'tables': tables}


def period_sort_key(p: dict):
    m = re.match(r'([A-Za-z]+)\s+(\d{4})', p.get('period', ''))
    if not m:
        return ('0000', '00')
    months = {v: f'{k:02d}' for k, v in MONTH_NAMES.items()}
    return (m.group(2), months.get(m.group(1), '00'))


# Slim keeps the category prefixes present in the live slim file plus the
# canonical 7 indicator prefixes (cf. CLAUDE.md gotcha #30).
SLIM_PREFIXES = ('credit_deposit_ratio', 'pmjdy', 'branch_network', 'kcc',
                 'shg', 'digital_transactions', 'aadhaar_authentication',
                 'pmegp')
_SLIM_RE = re.compile(
    r'^(' + '|'.join(SLIM_PREFIXES) + r')(_p?\d+)?__')


def slim_row(flat: dict) -> dict:
    out = {}
    for k, v in flat.items():
        if k in ('district', 'period') or _SLIM_RE.match(k):
            out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    # ---- map every batch, merging by period -----------------------------
    by_period: dict[str, dict] = {}
    for b in BATCHES:
        raw = load_raw(b['source'])
        mapper = MAPPERS[b['mapper']]
        kw = {k: v for k, v in b.items() if k not in ('source', 'period', 'mapper')}
        result = mapper(raw, b['period'], **kw)
        merge_district_data(by_period.setdefault(b['period'], {}), result)
        print(f"  {b['period']}  {b['source'][:42]:42s} → {len(result):2d} districts "
              f"({b['mapper']}{', ÷100' if kw.get('amt_factor') == 0.01 else ''})")

    print(f'\nperiods mapped: {len(by_period)}')
    for pk, names in sorted(DROPPED_REORG.items()):
        print(f'  dropped reorg districts {pk}: {sorted(names)}')

    if args.dry_run:
        for pk in sorted(by_period):
            d0 = by_period[pk].get('Jaipur') or next(iter(by_period[pk].values()))
            print(f'\n{pk} sample: {json.dumps(d0, indent=1)[:400]}')
        return

    # ---- timeseries (live site wins on conflict) -------------------------
    fi = json.loads(TIMESERIES_PATH.read_text())
    existing = {p['period']: p for p in fi['periods']}
    for pk in sorted(by_period):
        label = period_label(pk)
        if label in existing:
            # live wins: only add fields/districts not already present
            live_by_d = {d['district']: d for d in existing[label]['districts']}
            for row in build_period_entry(by_period[pk], label)['districts']:
                tgt = live_by_d.get(row['district'])
                if tgt is None:
                    existing[label]['districts'].append(row)
                else:
                    for k, v in row.items():
                        tgt.setdefault(k, v)
            existing[label]['districts'].sort(key=lambda r: r['district'])
        else:
            fi['periods'].append(build_period_entry(by_period[pk], label))
    fi['periods'].sort(key=period_sort_key)
    TIMESERIES_PATH.write_text(json.dumps(fi, ensure_ascii=False, indent=2))
    print(f'\nwrote {TIMESERIES_PATH.relative_to(ROOT)} '
          f'(total periods: {len(fi["periods"])})')

    # ---- complete --------------------------------------------------------
    comp = json.loads(COMPLETE_PATH.read_text())
    for pk in sorted(by_period):
        if pk in comp['quarters']:
            # live wins: merge only missing categories/districts/fields
            live_tables = comp['quarters'][pk]['tables']
            for cat, t in build_complete_entry(by_period[pk], pk)['tables'].items():
                if cat not in live_tables:
                    live_tables[cat] = t
                else:
                    for d, row in t['districts'].items():
                        live_tables[cat]['districts'].setdefault(d, {})
                        for f, v in row.items():
                            live_tables[cat]['districts'][d].setdefault(f, v)
                    for f in t['fields']:
                        if f not in live_tables[cat]['fields']:
                            live_tables[cat]['fields'].append(f)
        else:
            comp['quarters'][pk] = build_complete_entry(by_period[pk], pk)
    comp['quarters'] = dict(sorted(comp['quarters'].items()))
    COMPLETE_PATH.write_text(json.dumps(comp, ensure_ascii=False, indent=2))
    print(f'wrote {COMPLETE_PATH.relative_to(ROOT)} '
          f'(total quarters: {len(comp["quarters"])})')

    # ---- CSV (wide; period-major like the live file) ----------------------
    all_fields, seen = [], set()
    for p in fi['periods']:
        for row in p['districts']:
            for k in row:
                if k not in ('district', 'period') and k not in seen:
                    all_fields.append(k)
                    seen.add(k)
    all_fields.sort()
    lines = ['district,period,' + ','.join(all_fields)]
    for p in fi['periods']:
        for row in p['districts']:
            vals = [str(row.get(f, '')) for f in all_fields]
            lines.append(f"{row['district']},{row['period']}," + ','.join(vals))
    CSV_PATH.write_text('\n'.join(lines) + '\n')
    print(f'wrote {CSV_PATH.relative_to(ROOT)} '
          f'({len(lines) - 1} rows × {len(all_fields)} fields)')

    # ---- slim --------------------------------------------------------------
    slim = json.loads(SLIM_PATH.read_text())
    slim['periods'] = [
        {'period': p['period'],
         'districts': [slim_row(r) for r in p['districts']]}
        for p in fi['periods']
    ]
    SLIM_PATH.write_text(json.dumps(slim, ensure_ascii=False, indent=2))
    print(f'wrote {SLIM_PATH.relative_to(ROOT)} '
          f'(total periods: {len(slim["periods"])})')


if __name__ == '__main__':
    main()
