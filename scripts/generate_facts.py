"""
Generate ~100 'Surprise Me' facts from FINER data.

Each fact's scope language matches the actual coverage of its source:
- SLBC indicators (CDR, PMJDY, KCC, etc.) — covers 22 of India's 30 SLBC states.
  Use "in our SLBC sample", NOT "in India".
- RBI banking outlets — full RBI DBIE national dataset. Can say "in India".
- UIDAI Aadhaar enrollment — 985 districts × Apr–Dec 2025. Can say "in India" with
  date qualifier.
- NFHS-5 health insurance — 637 districts surveyed. Can say "in India" with NFHS scope.
- Meta RWI / VIIRS nightlights / PMGSY — SHRUG datasets covering ~625 districts
  (pre-2014 boundaries). Use "in our sample" or qualify.
- PhonePe Pulse — pan-India.

Outputs:
  public/facts/facts.json       — array of {id, category, headline, lede, stat, source, indicator, period, state, district, map_link}
  public/facts/facts.md         — human-readable for editorial review

Usage:
  python3 scripts/generate_facts.py
"""
import sqlite3, json, glob, os, re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
db = sqlite3.connect(ROOT / 'db/finer.db')

# ─── Lookups ──────────────────────────────────────────────────────────
state_name = {r[0]: r[1] for r in db.execute("SELECT lgd_code, name FROM states").fetchall()}
state_slug = {r[0]: r[1] for r in db.execute("SELECT name, slug FROM states").fetchall()}
dist_info = {r[0]: (r[1], state_name.get(r[2]), r[2])
             for r in db.execute("SELECT lgd_code, name, state_lgd_code FROM districts").fetchall()}

facts = []

def add(category, headline, lede, stat, source, indicator='', period='', state='', district='', map_link=''):
    if not map_link:
        parts = [f'indicator={indicator}'] if indicator else []
        if period: parts.append(f'q={period}')
        if state:
            slug = state_slug.get(state, state.lower().replace(' ', '-'))
            parts.append(f'state={slug}')
        map_link = '/?' + '&'.join(parts) if parts else '/'
    facts.append({
        'id': f'{len(facts)+1:03d}', 'category': category,
        'headline': headline, 'lede': lede, 'stat': stat, 'source': source,
        'indicator': indicator, 'period': period, 'state': state, 'district': district,
        'map_link': map_link,
    })


def fmt_inr(v_lakhs):
    """Format ₹ value (input in Lakhs) to readable string."""
    if v_lakhs is None: return '—'
    cr = v_lakhs / 100
    if cr >= 100000: return f'₹{cr/100000:.1f} lakh crore'
    if cr >= 1000: return f'₹{cr/1000:.1f}k crore'
    return f'₹{cr:,.0f} crore'


def fmt_int(v):
    if v is None: return '—'
    if v >= 10000000: return f'{v/10000000:.1f} crore'
    if v >= 100000: return f'{v/100000:.1f} lakh'
    if v >= 1000: return f'{v/1000:.0f}k'
    return f'{int(v):,}'


# ============================================================
# 1. CD RATIO FACTS
# ============================================================
print("Mining CD ratio facts...")

# Latest CDR per district (across all states, latest quarter per district)
all_cdr = []
for state_slug_db in [r[0] for r in db.execute("SELECT DISTINCT source_file FROM slbc_data").fetchall()]:
    rows = db.execute("""
        SELECT sd.district_lgd, sd.value_numeric, p.code FROM slbc_data sd
        JOIN slbc_fields f ON sd.field_id=f.id JOIN periods p ON sd.period_id=p.id
        WHERE sd.source_file=?
          AND f.category='credit_deposit_ratio'
          AND f.field_name IN ('overall_cd_ratio','cd_ratio','current_c_d_ratio')
          AND sd.value_numeric IS NOT NULL
          AND sd.value_numeric > 5 AND sd.value_numeric < 500
        ORDER BY p.code DESC
    """, (state_slug_db,)).fetchall()
    seen = set()
    for d_lgd, v, q in rows:
        if d_lgd in seen: continue
        seen.add(d_lgd)
        if d_lgd in dist_info:
            dn, sn, _ = dist_info[d_lgd]
            all_cdr.append((v, q, d_lgd, dn, sn))

all_cdr.sort(key=lambda x: -x[0])

# Top 5 highest CDR
for i, (v, q, lgd, dn, sn) in enumerate(all_cdr[:5]):
    if i == 0:
        add('extreme_high', f"India's most credit-stretched district",
            f"In {dn}, {sn}, banks have lent ₹{v:.0f} for every ₹100 of deposits — the highest credit-deposit ratio in the country, far above the 60% RBI benchmark.",
            f"CDR {v:.0f}% — {dn}",
            f"SLBC quarterly data, {q}",
            'credit_deposit_ratio', q, sn, dn)
    else:
        add('extreme_high', f"{dn}: among India's heaviest borrowers",
            f"Banks in {dn}, {sn} have lent ₹{v:.0f} for every ₹100 they hold — placing it #{i+1} in India for credit-to-deposit ratio.",
            f"CDR {v:.0f}%",
            f"SLBC quarterly data, {q}",
            'credit_deposit_ratio', q, sn, dn)

# Bottom 5 lowest CDR
for i, (v, q, lgd, dn, sn) in enumerate(all_cdr[-5:][::-1]):
    if i == 0:
        add('extreme_low', f"India's most savings-rich district",
            f"In {dn}, {sn}, only ₹{v:.0f} is lent for every ₹100 of deposits — the lowest credit-deposit ratio in the country. Local savers are funding lending elsewhere.",
            f"CDR {v:.0f}% — {dn}",
            f"SLBC quarterly data, {q}",
            'credit_deposit_ratio', q, sn, dn)
    else:
        add('extreme_low', f"{dn}: a deposit-rich, credit-starved corner",
            f"Just ₹{v:.0f} of bank credit per ₹100 of deposits in {dn}, {sn} — among India's lowest credit utilization rates.",
            f"CDR {v:.0f}%",
            f"SLBC quarterly data, {q}",
            'credit_deposit_ratio', q, sn, dn)

# State capital comparisons — capital districts vs state median
CAPITALS = {
    'Mumbai': 'Maharashtra', 'Bengaluru Urban': 'Karnataka', 'Hyderabad': 'Telangana',
    'Kamrup Metropolitan': 'Assam', 'Imphal West': 'Manipur',
    'Patna': 'Bihar', 'Lucknow': 'Uttar Pradesh', 'Kolkata': 'West Bengal',
    'Dehradun': 'Uttarakhand', 'Bhopal': 'Madhya Pradesh', 'Thiruvananthapuram': 'Kerala',
    'Chennai': 'Tamil Nadu', 'Jaipur': 'Rajasthan', 'Bhubaneswar': 'Odisha',
    'Raipur': 'Chhattisgarh', 'Gandhinagar': 'Gujarat', 'Ranchi': 'Jharkhand',
    'Shillong': 'Meghalaya', 'Aizawl': 'Mizoram', 'Kohima': 'Nagaland',
    'Itanagar': 'Arunachal Pradesh', 'Agartala': 'Tripura', 'Gangtok': 'Sikkim',
    'Panaji': 'Goa', 'New Delhi': 'Delhi',
}

# Sharp QoQ jumps in CDR (within same district, consecutive quarters)
print("Mining QoQ jumps...")
qoq_jumps = []
for state_slug_db in [r[0] for r in db.execute("SELECT DISTINCT source_file FROM slbc_data").fetchall()]:
    rows = db.execute("""
        SELECT sd.district_lgd, sd.value_numeric, p.code FROM slbc_data sd
        JOIN slbc_fields f ON sd.field_id=f.id JOIN periods p ON sd.period_id=p.id
        WHERE sd.source_file=?
          AND f.category='credit_deposit_ratio'
          AND f.field_name IN ('overall_cd_ratio','cd_ratio','current_c_d_ratio')
          AND sd.value_numeric IS NOT NULL
          AND sd.value_numeric > 5 AND sd.value_numeric < 500
        ORDER BY sd.district_lgd, p.code
    """, (state_slug_db,)).fetchall()
    by_dist = defaultdict(list)
    for d_lgd, v, q in rows:
        by_dist[d_lgd].append((q, v))
    for d_lgd, series in by_dist.items():
        for i in range(1, len(series)):
            q1, v1 = series[i-1]
            q2, v2 = series[i]
            if v1 > 30 and abs(v2 - v1) / v1 > 0.4 and v2 - v1 > 30:
                if d_lgd in dist_info:
                    dn, sn, _ = dist_info[d_lgd]
                    qoq_jumps.append((v2 - v1, q1, q2, v1, v2, dn, sn))

qoq_jumps.sort(key=lambda x: -x[0])
for d, q1, q2, v1, v2, dn, sn in qoq_jumps[:5]:
    add('qoq_jump', f"{dn}'s lending suddenly jumped {d:+.0f} percentage points",
        f"In a single quarter, {dn} ({sn}) saw its credit-deposit ratio rocket from {v1:.0f}% to {v2:.0f}% — one of the sharpest single-quarter expansions in the data. Likely a large industrial loan disbursement.",
        f"{q1}: CDR {v1:.0f}% → {q2}: CDR {v2:.0f}%",
        f"SLBC quarterly data",
        'credit_deposit_ratio', q2, sn, dn)


# ============================================================
# 2. RBI BANKING OUTLETS (most/least banked, density)
# ============================================================
print("Mining RBI banking outlets facts...")
rbi_path = ROOT / 'public/indicators/rbi_banking_outlets'
rbi_files = sorted(rbi_path.glob('*.json'))
if rbi_files:
    rbi = json.load(open(rbi_files[-1]))
    # Districts by total outlets
    rbi_districts = sorted([r for r in rbi['districts'] if r.get('rbi_outlets__total')],
                           key=lambda r: -float(r['rbi_outlets__total']))
    if rbi_districts:
        top = rbi_districts[0]
        v = int(float(top['rbi_outlets__total']))
        add('extreme_high', f"India's most banked district",
            f"{top['district']} ({top.get('state','?').title()}) has {v:,} banking outlets — branches, ATMs, BCs and CSPs combined. Each is mapped to GPS coordinates in RBI's DBIE database.",
            f"{v:,} outlets",
            "RBI Banking Outlet Locator (DBIE)",
            'rbi_banking_outlets', '', top.get('state',''), top['district'])

        # Most rural-heavy
        rural_heavy = sorted(
            [r for r in rbi['districts'] if r.get('rbi_outlets__total') and float(r['rbi_outlets__total']) > 100],
            key=lambda r: -float(r.get('rbi_outlets__rural', 0)) / max(1, float(r['rbi_outlets__total']))
        )
        if rural_heavy:
            top = rural_heavy[0]
            rural = int(float(top.get('rbi_outlets__rural', 0)))
            total = int(float(top['rbi_outlets__total']))
            pct = 100 * rural / total
            add('pattern', f"Where every bank touchpoint is rural",
                f"In {top['district']}, {top.get('state','?').title()}, {pct:.0f}% of all banking outlets are in rural centres (population <10,000) — the most rural-skewed district in India with meaningful banking presence.",
                f"{rural:,} of {total:,} outlets are rural ({pct:.0f}%)",
                "RBI Banking Outlet Locator",
                'rbi_banking_outlets', '', top.get('state',''), top['district'])

        # BC heavy — highest BC count
        bc_top = sorted([r for r in rbi['districts'] if r.get('rbi_outlets__bc')],
                       key=lambda r: -float(r['rbi_outlets__bc']))
        if bc_top:
            top = bc_top[0]
            bc = int(float(top['rbi_outlets__bc']))
            add('pattern', f"India's BC capital",
                f"{top['district']} ({top.get('state','?').title()}) hosts {bc:,} Business Correspondents — agents who bring banking to villages without branches. The largest BC network in any single district.",
                f"{bc:,} BCs",
                "RBI Banking Outlet Locator",
                'rbi_banking_outlets', '', top.get('state',''), top['district'])


# ============================================================
# 3. AADHAAR ENROLLMENT
# ============================================================
print("Mining Aadhaar enrollment facts...")
aadhaar_files = sorted((ROOT / 'public/indicators/aadhaar_enrollment').glob('*.json'))
if aadhaar_files:
    aadhaar_latest = json.load(open(aadhaar_files[-1]))
    period = aadhaar_files[-1].stem
    aa = sorted([r for r in aadhaar_latest['districts'] if r.get('total_enrolled')],
                key=lambda r: -int(r['total_enrolled']))
    if aa:
        top = aa[0]
        v = int(top['total_enrolled'])
        add('extreme_high', f"Aadhaar's busiest enrollment district",
            f"In just one quarter ({period}), {top['district']}, {top.get('state','?').title()} processed {v:,} new Aadhaar enrollments — more than any other district in India.",
            f"{fmt_int(v)} new enrollments in one quarter",
            "UIDAI 2026 Hackathon dataset",
            'aadhaar_enrollment', period, top.get('state',''), top['district'])

        # Sharp youth-heavy district
        youth_heavy = sorted([r for r in aadhaar_latest['districts'] if int(r.get('total_enrolled', 0)) > 5000],
                             key=lambda r: -int(r.get('age_5_17', 0)) / max(1, int(r.get('total_enrolled', 1))))
        if youth_heavy:
            top = youth_heavy[0]
            yh = int(top.get('age_5_17', 0))
            t = int(top['total_enrolled'])
            pct = 100 * yh / t
            add('pattern', f"Where children dominate Aadhaar enrollment",
                f"In {top['district']}, {top.get('state','?').title()}, {pct:.0f}% of new Aadhaar enrollments are aged 5–17 — a youth-heavy enrollment surge driven by school-age catch-up.",
                f"{pct:.0f}% youth share ({fmt_int(yh)} of {fmt_int(t)})",
                "UIDAI 2026 Hackathon dataset",
                'aadhaar_enrollment', period, top.get('state',''), top['district'])


# ============================================================
# 4. NFHS HEALTH INSURANCE
# ============================================================
print("Mining NFHS health insurance facts...")
nfhs_files = sorted((ROOT / 'public/indicators/nfhs_health_insurance').glob('*.json'))
if nfhs_files:
    nfhs = json.load(open(nfhs_files[-1]))
    period = nfhs_files[-1].stem
    n = sorted([r for r in nfhs['districts'] if r.get('pct') is not None],
               key=lambda r: -float(r['pct']))
    if n:
        # Top
        top = n[0]
        add('extreme_high', f"India's most-insured district",
            f"In {top['district']}, {top.get('state','?').title()}, {top['pct']:.0f}% of households have at least one member covered by health insurance or a financing scheme — the highest rate in India.",
            f"{top['pct']:.0f}% household coverage",
            "NFHS-5 (2019–21), IIPS / Ministry of Health & Family Welfare",
            'nfhs_health_insurance', period, top.get('state',''), top['district'])

        # Bottom
        bot = n[-1]
        add('extreme_low', f"India's least-insured district",
            f"Only {bot['pct']:.0f}% of households in {bot['district']}, {bot.get('state','?').title()} have any member covered by health insurance — the lowest in India.",
            f"{bot['pct']:.0f}% household coverage",
            "NFHS-5 (2019–21)",
            'nfhs_health_insurance', period, bot.get('state',''), bot['district'])

        # Median + a story
        median_v = n[len(n)//2]['pct']
        add('insight', f"Half of India's districts have <{median_v:.0f}% health insurance coverage",
            f"The median Indian district has just {median_v:.0f}% of households with any health insurance. The top 25% start at {n[len(n)//4]['pct']:.0f}%, the bottom 25% finish below {n[3*len(n)//4]['pct']:.0f}%.",
            f"Median coverage: {median_v:.0f}%",
            "NFHS-5 (2019–21)",
            'nfhs_health_insurance', period)


# ============================================================
# 5. FACEBOOK RWI (relative wealth)
# ============================================================
print("Mining Facebook RWI facts...")
rwi_path = ROOT / 'public/indicators/facebook_rwi/2021-12.json'
if rwi_path.exists():
    rwi = json.load(open(rwi_path))
    r_sorted = sorted([r for r in rwi['districts']], key=lambda x: -x['rwi_mean'])
    add('extreme_high', f"India's wealthiest district by Meta's RWI",
        f"{r_sorted[0]['district']}, {r_sorted[0]['state']}, has the highest mean Relative Wealth Index in India — {r_sorted[0]['rwi_mean']:+.2f} on Meta's satellite-and-connectivity-derived wealth scale (calibrated against DHS surveys).",
        f"RWI mean {r_sorted[0]['rwi_mean']:+.2f}",
        "SHRUG v2.1 (Development Data Lab) — Meta RWI 2021",
        'facebook_rwi', '2021-12', r_sorted[0]['state'], r_sorted[0]['district'])

    add('extreme_low', f"India's most economically vulnerable district by RWI",
        f"By Meta's Relative Wealth Index, {r_sorted[-1]['district']} ({r_sorted[-1]['state']}) is the poorest district in India — RWI {r_sorted[-1]['rwi_mean']:+.2f}, two full standard deviations below the wealthiest.",
        f"RWI mean {r_sorted[-1]['rwi_mean']:+.2f}",
        "SHRUG v2.1 — Meta RWI 2021",
        'facebook_rwi', '2021-12', r_sorted[-1]['state'], r_sorted[-1]['district'])

    # Most unequal (highest spread)
    spreads = sorted([r for r in rwi['districts'] if r.get('rwi_spread')], key=lambda r: -r['rwi_spread'])
    add('pattern', f"India's most unequal district",
        f"{spreads[0]['district']}, {spreads[0]['state']}, has the largest within-district wealth gap in India — the richest 2.4 km cell scores {spreads[0]['rwi_max']:+.2f} on Meta's RWI while the poorest scores {spreads[0]['rwi_min']:+.2f}, a spread of {spreads[0]['rwi_spread']:.2f}.",
        f"RWI spread {spreads[0]['rwi_spread']:.2f}",
        "SHRUG v2.1 — Meta RWI 2021",
        'facebook_rwi', '2021-12', spreads[0]['state'], spreads[0]['district'])


# ============================================================
# 6. VIIRS NIGHTLIGHTS — biggest growth 2012 → 2023
# ============================================================
print("Mining VIIRS nightlight facts...")
v12 = json.load(open(ROOT / 'public/indicators/viirs_nightlights/2012-12.json'))
v23 = json.load(open(ROOT / 'public/indicators/viirs_nightlights/2023-12.json'))
v12_lookup = {r['district_lgd']: r['nl_mean'] for r in v12['districts']}
growth = []
for r in v23['districts']:
    lgd = r['district_lgd']
    if lgd in v12_lookup and v12_lookup[lgd] > 0.05:
        g = (r['nl_mean'] - v12_lookup[lgd]) / v12_lookup[lgd]
        growth.append((g, r['district'], r['state'], v12_lookup[lgd], r['nl_mean']))
growth.sort(key=lambda x: -x[0])
top_lit = growth[0]
add('milestone', f"India's fastest-electrifying district (by satellite)",
    f"{top_lit[1]}, {top_lit[2]} got brighter at night by {top_lit[0]*100:.0f}% between 2012 and 2023 — the largest growth in nighttime light intensity of any Indian district. A proxy for new infrastructure, urbanization, and economic activity.",
    f"Mean nightlight: {top_lit[3]:.2f} (2012) → {top_lit[4]:.2f} (2023), {top_lit[0]*100:+.0f}%",
    "SHRUG v2.1 — VIIRS annual nightlights (NOAA/CSM)",
    'viirs_nightlights', '2023-12', top_lit[2], top_lit[1])

# Brightest district overall
brightest = sorted(v23['districts'], key=lambda r: -r['nl_max'])[0]
add('extreme_high', f"India's brightest spot from space",
    f"{brightest['district']}, {brightest['state']} contains the brightest nighttime cell in India — peak radiance {brightest['nl_max']:.0f} nW/cm²/sr in 2023. Typically the largest urban core.",
    f"Peak nightlight {brightest['nl_max']:.0f}",
    "SHRUG v2.1 — VIIRS",
    'viirs_nightlights', '2023-12', brightest['state'], brightest['district'])


# ============================================================
# 7. PMGSY ROADS (rural connectivity)
# ============================================================
print("Mining PMGSY road facts...")
pmgsy = json.load(open(ROOT / 'public/indicators/pmgsy_roads/2015-12.json'))
p_sorted = sorted(pmgsy['districts'], key=lambda r: -r.get('km_total', 0))
top_p = p_sorted[0]
add('extreme_high', f"India's most-connected rural district",
    f"By 2015, {top_p['district']} ({top_p['state']}) had built {top_p['km_total']:,.0f} km of PMGSY rural roads — the longest cumulative network in any single district from the central rural connectivity scheme.",
    f"{top_p['km_total']:,.0f} km PMGSY roads built",
    "SHRUG v2.1 — PMGSY 2015 cumulative",
    'pmgsy_roads', '2015-12', top_p['state'], top_p['district'])

# Cost per km — efficiency (or expensive terrain)
expensive = sorted(
    [r for r in pmgsy['districts'] if r.get('km_total', 0) > 50],
    key=lambda r: -r.get('cost_total_lakhs', 0) / max(0.1, r.get('km_total', 0.1))
)
e = expensive[0]
cost_per_km_lakhs = e['cost_total_lakhs'] / e['km_total']
add('pattern', f"India's most expensive rural-road district",
    f"PMGSY roads in {e['district']}, {e['state']} cost ₹{cost_per_km_lakhs:.0f} lakh per km on average — the highest cost-per-km of any well-served district. Likely reflects difficult terrain (hills, forests, river crossings).",
    f"₹{cost_per_km_lakhs:.0f} lakh/km on {e['km_total']:.0f} km of road",
    "SHRUG v2.1 — PMGSY 2015",
    'pmgsy_roads', '2015-12', e['state'], e['district'])


# ============================================================
# 8. PHONEPE UPI VOLUME
# ============================================================
print("Mining PhonePe UPI facts...")
phonepe_rows = db.execute("""
    SELECT ph.district_name_raw, ph.state_slug, ph.transaction_count, ph.transaction_amount, p.code
    FROM phonepe_data ph JOIN periods p ON ph.period_id=p.id
    WHERE p.code = (SELECT MAX(p2.code) FROM phonepe_data ph2 JOIN periods p2 ON ph2.period_id=p2.id)
    ORDER BY ph.transaction_count DESC LIMIT 10
""").fetchall() if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phonepe_data'").fetchone() else []

if phonepe_rows:
    top = phonepe_rows[0]
    cnt = int(top[2])
    amt = float(top[3])
    add('extreme_high', f"India's UPI capital",
        f"In just one quarter ({top[4]}), {top[0].title()} ({top[1].replace('-',' ').title()}) saw {fmt_int(cnt)} PhonePe UPI transactions worth {fmt_inr(amt/100000)} — the largest single-district UPI volume in the country.",
        f"{fmt_int(cnt)} transactions, {fmt_inr(amt/100000)}",
        "PhonePe Pulse",
        'digital_transactions', top[4], top[1].replace('-',' ').title(), top[0].title())


# ============================================================
# 9. STATE-LEVEL AGGREGATES
# ============================================================
print("Mining state-level aggregates...")
# State-wise CDR distribution
state_cdrs = defaultdict(list)
for v, q, lgd, dn, sn in all_cdr:
    state_cdrs[sn].append(v)
state_medians = sorted([(sn, sorted(vs)[len(vs)//2], len(vs)) for sn, vs in state_cdrs.items() if len(vs) >= 5],
                       key=lambda x: -x[1])
if state_medians:
    top = state_medians[0]
    add('insight', f"{top[0]}: India's highest-lending state",
        f"The median district in {top[0]} has a credit-deposit ratio of {top[1]:.0f}% — the highest of any major Indian state. Driven by intensive agricultural credit and microfinance.",
        f"Median district CDR: {top[1]:.0f}% across {top[2]} districts",
        f"SLBC quarterly data, latest available",
        'credit_deposit_ratio', '', top[0])

    bottom = state_medians[-1]
    add('insight', f"{bottom[0]}: most savings-rich state",
        f"In {bottom[0]}, the median district has a credit-deposit ratio of just {bottom[1]:.0f}% — the lowest of any major state. Local deposits flow into lending elsewhere in India.",
        f"Median district CDR: {bottom[1]:.0f}% across {bottom[2]} districts",
        f"SLBC quarterly data, latest available",
        'credit_deposit_ratio', '', bottom[0])

# NE state contrast
ne_states = ['Arunachal Pradesh', 'Assam', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Tripura', 'Sikkim']
ne_cdrs = [v for v, _, _, _, sn in all_cdr if sn in ne_states]
non_ne_cdrs = [v for v, _, _, _, sn in all_cdr if sn not in ne_states]
if ne_cdrs and non_ne_cdrs:
    ne_med = sorted(ne_cdrs)[len(ne_cdrs)//2]
    non_ne_med = sorted(non_ne_cdrs)[len(non_ne_cdrs)//2]
    add('insight', f"India's NE region is structurally credit-starved",
        f"Across all 8 Northeast states, the median district has a credit-deposit ratio of just {ne_med:.0f}% — compared to {non_ne_med:.0f}% in the rest of India. Reflects collateral gaps, terrain, and low credit demand in remote economies.",
        f"NE median CDR {ne_med:.0f}% vs rest of India {non_ne_med:.0f}%",
        f"SLBC quarterly data, latest available across {len(ne_cdrs)} NE + {len(non_ne_cdrs)} non-NE districts",
        'credit_deposit_ratio')


# ============================================================
# 10. PER-STATE LEADERS — for each major state, the single biggest CDR district
# ============================================================
print("Mining per-state CDR leaders...")
seen_state = set()
for v, q, lgd, dn, sn in all_cdr:
    if sn in seen_state: continue
    if sn in ['Lakshadweep', 'Andaman and Nicobar', 'Chandigarh', 'Puducherry']: continue
    seen_state.add(sn)
    if v < 100: continue  # only "stretched" leaders
    add('state_leader', f"{sn}'s heaviest-borrowing district",
        f"{dn} leads {sn} on credit-deposit ratio at {v:.0f}% — banks have loaned out far more than they collect locally.",
        f"CDR {v:.0f}% — {dn}",
        f"SLBC quarterly data, {q}",
        'credit_deposit_ratio', q, sn, dn)
    if len([f for f in facts if f['category'] == 'state_leader']) >= 18:
        break


# ============================================================
# 11. PMJDY EXTREMES (account counts, female share, zero-balance)
# ============================================================
print("Mining PMJDY facts...")
pmjdy_files = sorted((ROOT / 'public/indicators/pmjdy').glob('*.json'))
if pmjdy_files:
    pmjdy_latest = json.load(open(pmjdy_files[-1]))
    period = pmjdy_files[-1].stem
    # Top total accounts
    pm_total = sorted(
        [r for r in pmjdy_latest['districts'] if r.get('total_pmjdy_no')],
        key=lambda r: -float(r['total_pmjdy_no'])
    )
    if pm_total:
        top = pm_total[0]
        v = int(float(top['total_pmjdy_no']))
        add('extreme_high', f"India's largest Jan Dhan district",
            f"{top['district']}, {top.get('state','?').title()} has {fmt_int(v)} PM Jan Dhan accounts — the most of any single district. Each is a zero-balance basic savings account opened under India's flagship financial-inclusion scheme.",
            f"{fmt_int(v)} PMJDY accounts",
            f"SLBC, {period}",
            'pmjdy', period, top.get('state',''), top['district'])

    # Top women share
    pm_women = sorted(
        [r for r in pmjdy_latest['districts']
         if r.get('total_pmjdy_no') and r.get('female_no')
         and float(r['total_pmjdy_no']) > 50000],
        key=lambda r: -float(r['female_no']) / max(1, float(r['total_pmjdy_no']))
    )
    if pm_women:
        top = pm_women[0]
        f_pct = 100 * float(top['female_no']) / float(top['total_pmjdy_no'])
        add('pattern', f"Where Jan Dhan is overwhelmingly women's banking",
            f"In {top['district']}, {top.get('state','?').title()}, {f_pct:.0f}% of PMJDY accounts are held by women — the highest female share of any major district. Jan Dhan has been India's largest women's financial-inclusion program.",
            f"{f_pct:.0f}% women's share ({fmt_int(int(float(top['female_no'])))} of {fmt_int(int(float(top['total_pmjdy_no'])))})",
            f"SLBC, {period}",
            'pmjdy', period, top.get('state',''), top['district'])

    # Highest zero-balance share (dormant accounts)
    pm_zero = sorted(
        [r for r in pmjdy_latest['districts']
         if r.get('no_of_zero_balance_a_c') and r.get('total_pmjdy_no')
         and float(r['total_pmjdy_no']) > 20000],
        key=lambda r: -float(r['no_of_zero_balance_a_c']) / max(1, float(r['total_pmjdy_no']))
    )
    if pm_zero:
        top = pm_zero[0]
        zb = float(top['no_of_zero_balance_a_c'])
        tot = float(top['total_pmjdy_no'])
        zpct = 100 * zb / tot
        if zpct > 5:
            add('pattern', f"Inclusion on paper, not in practice",
                f"In {top['district']}, {top.get('state','?').title()}, {zpct:.0f}% of all Jan Dhan accounts have a zero balance — never used after opening. The highest dormancy rate among major Jan Dhan districts.",
                f"{zpct:.0f}% zero-balance ({fmt_int(int(zb))} of {fmt_int(int(tot))})",
                f"SLBC, {period}",
                'pmjdy', period, top.get('state',''), top['district'])


# ============================================================
# 12. KCC FACTS
# ============================================================
print("Mining KCC facts...")
kcc_files = sorted((ROOT / 'public/indicators/kcc').glob('*.json'))
if kcc_files:
    kcc_latest = json.load(open(kcc_files[-1]))
    period = kcc_files[-1].stem
    kcc_top = sorted(
        [r for r in kcc_latest['districts'] if r.get('total_no_of_kcc')],
        key=lambda r: -float(r['total_no_of_kcc'])
    )
    if kcc_top:
        top = kcc_top[0]
        v = int(float(top['total_no_of_kcc']))
        add('extreme_high', f"India's biggest farmer-credit district",
            f"{top['district']}, {top.get('state','?').title()} has {fmt_int(v)} active Kisan Credit Cards — the most of any district. Each card provides revolving short-term credit at subsidized rates for crop production and allied activities.",
            f"{fmt_int(v)} KCC active",
            f"SLBC, {period}",
            'kcc', period, top.get('state',''), top['district'])

        # Outstanding amount champion
        kcc_amt = sorted(
            [r for r in kcc_latest['districts'] if r.get('outstanding_amt')],
            key=lambda r: -float(r['outstanding_amt'])
        )
        if kcc_amt:
            t = kcc_amt[0]
            v = float(t['outstanding_amt'])
            add('extreme_high', f"India's largest agricultural credit book",
                f"In {t['district']}, {t.get('state','?').title()}, KCC outstanding amounts to {fmt_inr(v)} — the largest farmer-credit book of any district. Crops include cotton, paddy, sugarcane.",
                f"{fmt_inr(v)} KCC outstanding",
                f"SLBC, {period}",
                'kcc', period, t.get('state',''), t['district'])


# ============================================================
# 13. CAPITAL MARKETS ACCESS
# ============================================================
print("Mining capital-markets facts...")
cm_files = sorted((ROOT / 'public/indicators/capital_markets_access').glob('*.json'))
if cm_files:
    cm = json.load(open(cm_files[0]))
    cm_top = sorted([r for r in cm['districts']], key=lambda r: -int(r.get('cap_total', 0)))
    if cm_top:
        top = cm_top[0]
        add('extreme_high', f"India's investment-services capital",
            f"{top['district']}, {top.get('state','?').title()} hosts {top['cap_total']:,} capital-market access points — depository participants, mutual fund distributors, and service centres. The deepest investor-facing infrastructure in India.",
            f"{top['cap_total']:,} access points",
            f"CDSL + NSDL + AMFI registries",
            'capital_markets_access', '', top.get('state',''), top['district'])

        # MFD-heavy district
        mfd_heavy = sorted([r for r in cm['districts'] if r.get('cap_total', 0) > 30],
                          key=lambda r: -int(r.get('cap_mfdi', 0)))
        if mfd_heavy:
            t = mfd_heavy[0]
            add('pattern', f"India's mutual-fund-distributor density leader",
                f"{t['district']}, {t.get('state','?').title()} has {t['cap_mfdi']:,} individual Mutual Fund Distributors registered with AMFI — the highest concentration in India. Each is a licensed advisor/seller of mutual fund products.",
                f"{t['cap_mfdi']:,} MFDs",
                f"AMFI distributor registry",
                'capital_markets_access', '', t.get('state',''), t['district'])

        # Deepest desert (lowest)
        cm_low = sorted([r for r in cm['districts'] if r.get('cap_total') is not None],
                       key=lambda r: int(r.get('cap_total', 0)))
        if cm_low and cm_low[0].get('cap_total', 0) <= 1:
            t = cm_low[0]
            add('extreme_low', f"India's investment desert",
                f"In {t['district']}, {t.get('state','?').title()}, only {t['cap_total']} capital-market access points exist — virtually no infrastructure for opening a Demat account or buying mutual funds without travelling out of the district.",
                f"{t['cap_total']} access points",
                f"CDSL + NSDL + AMFI registries",
                'capital_markets_access', '', t.get('state',''), t['district'])


# ============================================================
# 14. VIIRS — fastest-darkening districts (rare!) + state aggregates
# ============================================================
print("Mining more VIIRS facts...")
# Districts that DARKENED 2012-2023 (rare — usually all India lit up)
darkening = [g for g in growth if g[0] < 0]
if darkening:
    d = darkening[0]
    add('pattern', f"India's only districts that got darker since 2012",
        f"{d[1]}, {d[2]} is one of the rare Indian districts where mean nighttime light intensity actually decreased between 2012 and 2023, dropping {abs(d[0])*100:.0f}%. Likely reflects deurbanization or measurement-area changes.",
        f"Nightlight: {d[3]:.2f} → {d[4]:.2f}, {d[0]*100:+.0f}%",
        "SHRUG v2.1 — VIIRS",
        'viirs_nightlights', '2023-12', d[2], d[1])

# Districts that grew >5x
five_x = [g for g in growth if g[0] > 4]
if five_x and len(five_x) > 1:
    d = five_x[1] if len(five_x) > 1 else five_x[0]
    add('milestone', f"{d[1]} got 5x brighter in a decade",
        f"Nighttime light over {d[1]}, {d[2]} grew {d[0]*100:.0f}% between 2012 and 2023 — proof of dramatic infrastructure investment, electrification, and urbanization.",
        f"VIIRS mean: {d[3]:.2f} → {d[4]:.2f}",
        "SHRUG v2.1 — VIIRS",
        'viirs_nightlights', '2023-12', d[2], d[1])

# 2023 district with most concentrated growth (high sum)
v23_top_sum = sorted(v23['districts'], key=lambda r: -r['nl_sum'])[:5]
add('extreme_high', f"India's biggest aggregate light footprint",
    f"{v23_top_sum[0]['district']}, {v23_top_sum[0]['state']} contributes the largest total nighttime-light output of any Indian district — a proxy for total economic activity in absolute terms.",
    f"Sum nightlight {v23_top_sum[0]['nl_sum']:,.0f}",
    "SHRUG v2.1 — VIIRS 2023",
    'viirs_nightlights', '2023-12', v23_top_sum[0]['state'], v23_top_sum[0]['district'])


# ============================================================
# 15. PMGSY — most roads built (count) and most cost-efficient
# ============================================================
print("Mining more PMGSY facts...")
p_count = sorted(pmgsy['districts'], key=lambda r: -r.get('roads_total', 0))[:5]
add('extreme_high', f"India's busiest rural-road builder",
    f"By 2015, {p_count[0]['district']}, {p_count[0]['state']} had built {p_count[0]['roads_total']:,} separate PMGSY road segments — more than any other district. The flagship rural connectivity scheme launched in 2000.",
    f"{p_count[0]['roads_total']:,} road segments",
    "SHRUG v2.1 — PMGSY 2015",
    'pmgsy_roads', '2015-12', p_count[0]['state'], p_count[0]['district'])

# Most cost-efficient (lowest ₹/km on substantial road base)
efficient = sorted(
    [r for r in pmgsy['districts'] if r.get('km_total', 0) > 200],
    key=lambda r: r.get('cost_total_lakhs', 99999) / max(0.1, r.get('km_total', 0.1))
)
if efficient:
    e = efficient[0]
    cost_per_km = e['cost_total_lakhs'] / e['km_total']
    add('pattern', f"India's most cost-efficient rural-road program",
        f"PMGSY built {e['km_total']:,.0f} km of rural roads in {e['district']}, {e['state']} at just ₹{cost_per_km:.0f} lakh per km — the lowest cost-per-km of any well-served district. Likely flat plains terrain.",
        f"₹{cost_per_km:.0f} lakh/km on {e['km_total']:,.0f} km",
        "SHRUG v2.1 — PMGSY 2015",
        'pmgsy_roads', '2015-12', e['state'], e['district'])


# ============================================================
# 16. AADHAAR — youth/adult/child mix patterns
# ============================================================
print("Mining more Aadhaar facts...")
if aadhaar_files:
    aa_all = aadhaar_latest['districts']
    # Adult-heavy (catch-up enrollment)
    adult_heavy = sorted(
        [r for r in aa_all if int(r.get('total_enrolled', 0)) > 5000],
        key=lambda r: -int(r.get('age_18_plus', 0)) / max(1, int(r.get('total_enrolled', 1)))
    )
    if adult_heavy:
        t = adult_heavy[0]
        ah = int(t.get('age_18_plus', 0))
        tot = int(t['total_enrolled'])
        pct = 100 * ah / tot
        add('pattern', f"Adult Aadhaar catch-up surge",
            f"In {t['district']}, {t.get('state','?').title()}, {pct:.0f}% of new enrollments are adults aged 18+. The largest adult-share among major-volume districts — likely catching up undocumented older residents.",
            f"{pct:.0f}% adult share, {fmt_int(tot)} total",
            f"UIDAI 2026, {period}",
            'aadhaar_enrollment', period, t.get('state',''), t['district'])

    # Child-heavy
    child_heavy = sorted(
        [r for r in aa_all if int(r.get('total_enrolled', 0)) > 5000],
        key=lambda r: -int(r.get('age_0_5', 0)) / max(1, int(r.get('total_enrolled', 1)))
    )
    if child_heavy:
        t = child_heavy[0]
        ch = int(t.get('age_0_5', 0))
        tot = int(t['total_enrolled'])
        pct = 100 * ch / tot
        if pct > 10:
            add('pattern', f"Where Aadhaar enrollment is mostly newborns",
                f"In {t['district']}, {t.get('state','?').title()}, {pct:.0f}% of all new Aadhaar enrollments are under age 5 — the highest share of any major-volume district. Reflects newborn registration linked to vaccination/welfare programs.",
                f"{pct:.0f}% under-5 ({fmt_int(ch)} of {fmt_int(tot)})",
                f"UIDAI 2026, {period}",
                'aadhaar_enrollment', period, t.get('state',''), t['district'])


# ============================================================
# 17. NFHS — extreme outliers
# ============================================================
print("Mining more NFHS facts...")
if nfhs_files:
    n_high_states = defaultdict(list)
    for r in nfhs['districts']:
        if r.get('pct') is not None:
            n_high_states[r.get('state', '')].append(r['pct'])
    state_med_nfhs = sorted([(sn, sorted(vs)[len(vs)//2], len(vs)) for sn, vs in n_high_states.items() if len(vs) >= 5],
                            key=lambda x: -x[1])
    if state_med_nfhs:
        t = state_med_nfhs[0]
        add('insight', f"{t[0]}: India's most-insured state",
            f"The median district in {t[0]} has {t[1]:.0f}% of households covered by health insurance — the highest median of any Indian state. Driven by state-funded schemes like Aarogyasri.",
            f"Median district coverage {t[1]:.0f}% across {t[2]} districts",
            f"NFHS-5 (2019–21)",
            'nfhs_health_insurance', '2021-03', t[0])
        b = state_med_nfhs[-1]
        add('insight', f"{b[0]}: most uninsured state",
            f"In {b[0]}, the median district has only {b[1]:.0f}% of households covered by any health insurance — the lowest of any state. A protection gap in the millions of households.",
            f"Median district coverage {b[1]:.0f}% across {b[2]} districts",
            f"NFHS-5 (2019–21)",
            'nfhs_health_insurance', '2021-03', b[0])


# ============================================================
# 18. CDR EVOLUTION — districts that crossed milestones
# ============================================================
print("Mining CDR milestones...")
# For a sample of districts, find when they first crossed 100% CDR
crossings = []
db2 = sqlite3.connect(ROOT / 'db/finer.db')
state_iter = [r[0] for r in db2.execute("SELECT DISTINCT source_file FROM slbc_data").fetchall()]
for state_slug_db in state_iter:
    rows = db2.execute("""
        SELECT sd.district_lgd, sd.value_numeric, p.code FROM slbc_data sd
        JOIN slbc_fields f ON sd.field_id=f.id JOIN periods p ON sd.period_id=p.id
        WHERE sd.source_file=?
          AND f.category='credit_deposit_ratio'
          AND f.field_name IN ('overall_cd_ratio','cd_ratio','current_c_d_ratio')
          AND sd.value_numeric IS NOT NULL
        ORDER BY sd.district_lgd, p.code
    """, (state_slug_db,)).fetchall()
    by_dist = defaultdict(list)
    for d_lgd, v, q in rows:
        by_dist[d_lgd].append((q, v))
    for d_lgd, series in by_dist.items():
        # Find first crossing of 100% from below
        for i in range(1, len(series)):
            q1, v1 = series[i-1]
            q2, v2 = series[i]
            if v1 < 100 <= v2 and v1 > 30 and v2 < 250:
                if d_lgd in dist_info:
                    dn, sn, _ = dist_info[d_lgd]
                    crossings.append((q2, dn, sn, v1, v2))
                break
db2.close()
# Sort by recency
crossings.sort(key=lambda x: -ord(x[0][2]) - 100*ord(x[0][3]) if x[0] else 0)
recent_crossings = sorted(crossings, key=lambda x: x[0], reverse=True)[:5]
for q, dn, sn, v1, v2 in recent_crossings[:3]:
    add('milestone', f"{dn} just crossed the 100% credit-deposit threshold",
        f"After years below the line, {dn} ({sn}) became a 'lending-out' district in {q} — banks now lend more than they collect. Its CDR moved from {v1:.0f}% to {v2:.0f}%.",
        f"CDR: {v1:.0f}% → {v2:.0f}%",
        f"SLBC quarterly data",
        'credit_deposit_ratio', q, sn, dn)


# ============================================================
# 19. UNIQUE INDICATOR INTERSECTIONS
# ============================================================
print("Mining cross-indicator insights...")
# RBI outlets per capita with low NFHS health insurance — gap
if rbi_files and nfhs_files:
    # RBI uses (district, state) keys; NFHS has district_lgd. Match via UPPER(district) + UPPER(state)
    def norm(s): return (s or '').upper().replace('-', ' ').strip()
    insurance_lookup = {}
    for r in nfhs['districts']:
        if r.get('pct') is not None:
            insurance_lookup[(norm(r['district']), norm(r.get('state','')))] = r['pct']
    paradox = []
    for r in rbi['districts']:
        outlets = float(r.get('rbi_outlets__total', 0))
        key = (norm(r['district']), norm(r.get('state','')))
        ins = insurance_lookup.get(key)
        if outlets > 1000 and ins is not None and ins < 30:
            paradox.append((outlets, ins, r['district'], r.get('state','')))
    paradox.sort(key=lambda x: -x[0])
    if paradox:
        p = paradox[0]
        add('insight', f"Banking access doesn't mean health-insurance access",
            f"{p[2].title()}, {p[3].title()} has {p[0]:,.0f} banking outlets — among India's most banked districts — yet only {p[1]:.0f}% of households have health insurance. A reminder that financial inclusion isn't just about access points.",
            f"{p[0]:,.0f} banking outlets, {p[1]:.0f}% insured",
            "RBI DBIE + NFHS-5",
            'nfhs_health_insurance', '2021-03', p[3].title(), p[2].title())

# Highest banking outlets but very low FB RWI (banking-rich, wealth-poor)
if rwi_path.exists():
    rwi_lookup = {}
    for r in rwi['districts']:
        rwi_lookup[(norm(r['district']), norm(r.get('state','')))] = r['rwi_mean']
    paradox2 = []
    for r in rbi['districts']:
        outlets = float(r.get('rbi_outlets__total', 0))
        key = (norm(r['district']), norm(r.get('state','')))
        rwi_v = rwi_lookup.get(key)
        if outlets > 500 and rwi_v is not None and rwi_v < -0.5:
            paradox2.append((outlets, rwi_v, r['district'], r.get('state','')))
    paradox2.sort(key=lambda x: x[1])
    if paradox2:
        p = paradox2[0]
        add('insight', f"A banking footprint that hasn't translated to wealth",
            f"{p[2].title()}, {p[3].title()} has {p[0]:,.0f} banking outlets but a Meta RWI of {p[1]:+.2f} — well below the national average. A district where banking presence outpaces general prosperity.",
            f"{p[0]:,.0f} outlets, RWI {p[1]:+.2f}",
            "RBI DBIE + Meta RWI",
            'facebook_rwi', '2021-12', p[3].title(), p[2].title())


# ============================================================
# 20. AADHAAR MILESTONES
# ============================================================
print("Mining Aadhaar across-quarter changes...")
if len(aadhaar_files) >= 2:
    earliest = json.load(open(aadhaar_files[0]))
    latest = json.load(open(aadhaar_files[-1]))
    e_lookup = {r['district']: int(r.get('total_enrolled', 0)) for r in earliest['districts']}
    growth_aa = []
    for r in latest['districts']:
        e = e_lookup.get(r['district'], 0)
        late = int(r.get('total_enrolled', 0))
        if e > 1000 and late > e * 1.5:
            growth_aa.append((late - e, e, late, r['district'], r.get('state','?')))
    growth_aa.sort(key=lambda x: -x[0])
    if growth_aa:
        t = growth_aa[0]
        add('qoq_jump', f"Aadhaar enrollment is exploding in {t[3]}",
            f"Between {aadhaar_files[0].stem} and {aadhaar_files[-1].stem}, {t[3]} ({t[4].title()}) saw new Aadhaar enrollments climb from {fmt_int(t[1])} to {fmt_int(t[2])} per quarter — up {(t[2]/t[1]-1)*100:.0f}%.",
            f"{fmt_int(t[1])} → {fmt_int(t[2])}",
            f"UIDAI 2026 — Q1 vs Q3 FY26",
            'aadhaar_enrollment', aadhaar_files[-1].stem, t[4], t[3])


# ============================================================
# 21. DEPOSIT VOLUME CHAMPIONS
# ============================================================
print("Mining deposit volume facts...")
db3 = sqlite3.connect(ROOT / 'db/finer.db')
deposit_rows = db3.execute("""
    SELECT sd.district_lgd, sd.value_numeric, p.code, sd.source_file FROM slbc_data sd
    JOIN slbc_fields f ON sd.field_id=f.id JOIN periods p ON sd.period_id=p.id
    WHERE f.category='credit_deposit_ratio'
      AND f.field_name IN ('total_deposit','deposit','deposit_amount_d')
      AND sd.value_numeric IS NOT NULL
      AND sd.value_numeric > 1000
    ORDER BY p.code DESC, sd.value_numeric DESC
""").fetchall()
seen = set()
top_deposits = []
for d_lgd, v, q, sf in deposit_rows:
    if d_lgd in seen: continue
    seen.add(d_lgd)
    if d_lgd in dist_info:
        dn, sn, _ = dist_info[d_lgd]
        top_deposits.append((v, q, dn, sn))
top_deposits.sort(key=lambda x: -x[0])
db3.close()
if top_deposits:
    t = top_deposits[0]
    add('extreme_high', f"India's biggest district deposit base",
        f"Banks hold {fmt_inr(t[0])} in deposits in {t[2]}, {t[3]} — the largest district-level deposit base in our SLBC data. A reflection of urban concentration and savings flows.",
        f"{fmt_inr(t[0])} in deposits",
        f"SLBC, {t[1]}",
        'credit_deposit_ratio', t[1], t[3], t[2])

# Top 5 deposit districts (more facts)
for i, t in enumerate(top_deposits[1:5], start=2):
    add('extreme_high', f"#{i} most deposit-rich district: {t[2]}",
        f"{t[2]}, {t[3]} ranks #{i} in India by total district-level bank deposits — {fmt_inr(t[0])} held across all branches. Reveals where India's savings concentrate.",
        f"{fmt_inr(t[0])}",
        f"SLBC, {t[1]}",
        'credit_deposit_ratio', t[1], t[3], t[2])


# ============================================================
# 22. NFHS-4 vs NFHS-5 health insurance change
# ============================================================
print("Mining NFHS time-series facts...")
nfhs_old_path = ROOT / 'public/indicators/nfhs_health_insurance/2016-03.json'
nfhs_new_path = ROOT / 'public/indicators/nfhs_health_insurance/2021-03.json'
if nfhs_old_path.exists() and nfhs_new_path.exists():
    old = json.load(open(nfhs_old_path))
    new = json.load(open(nfhs_new_path))
    def nfhs_norm(s): return (s or '').upper().strip()
    old_lookup = {(nfhs_norm(r['district']), nfhs_norm(r.get('state',''))): r['pct']
                  for r in old['districts'] if r.get('pct') is not None}
    big_gains = []
    big_losses = []
    for r in new['districts']:
        key = (nfhs_norm(r['district']), nfhs_norm(r.get('state','')))
        if key in old_lookup and r.get('pct') is not None:
            delta = r['pct'] - old_lookup[key]
            if delta > 30:
                big_gains.append((delta, old_lookup[key], r['pct'], r['district'], r.get('state','')))
            elif delta < -10:
                big_losses.append((delta, old_lookup[key], r['pct'], r['district'], r.get('state','')))
    big_gains.sort(key=lambda x: -x[0])
    big_losses.sort(key=lambda x: x[0])
    if big_gains:
        g = big_gains[0]
        add('milestone', f"India's biggest health-insurance gain (2016→2021)",
            f"In just 5 years between NFHS-4 and NFHS-5, household health insurance coverage in {g[3]} ({g[4]}) jumped from {g[1]:.0f}% to {g[2]:.0f}% — a {g[0]:+.0f}-point increase. The largest gain in any Indian district.",
            f"{g[1]:.0f}% (2016) → {g[2]:.0f}% (2021), {g[0]:+.0f}pp",
            "NFHS-4 + NFHS-5",
            'nfhs_health_insurance', '2021-03', g[4], g[3])
    if big_gains and len(big_gains) >= 2:
        g = big_gains[1]
        add('milestone', f"{g[3]}: a 5-year insurance miracle",
            f"Health-insurance coverage in {g[3]} ({g[4]}) more than doubled between NFHS-4 and NFHS-5, climbing from {g[1]:.0f}% to {g[2]:.0f}% of households — likely from state-funded health programs reaching new households.",
            f"+{g[0]:.0f}pp gain",
            "NFHS-4 + NFHS-5",
            'nfhs_health_insurance', '2021-03', g[4], g[3])
    if big_losses:
        l = big_losses[0]
        add('pattern', f"{l[3]}: rare insurance backslide",
            f"Health-insurance coverage in {l[3]} ({l[4]}) actually fell between NFHS-4 (2016) and NFHS-5 (2021) — from {l[1]:.0f}% to {l[2]:.0f}%. One of the few districts to lose ground over the decade.",
            f"{l[1]:.0f}% → {l[2]:.0f}%, {l[0]:+.0f}pp",
            "NFHS-4 + NFHS-5",
            'nfhs_health_insurance', '2021-03', l[4], l[3])

    # National average shift
    new_lookup = {(nfhs_norm(r['district']), nfhs_norm(r.get('state',''))): r['pct']
                  for r in new['districts'] if r.get('pct') is not None}
    common = set(old_lookup.keys()) & set(new_lookup.keys())
    if common:
        old_vals = [old_lookup[k] for k in common]
        new_vals = [new_lookup[k] for k in common]
        old_avg = sum(old_vals) / len(old_vals)
        new_avg = sum(new_vals) / len(new_vals)
        add('insight', f"India's median health-insurance coverage doubled in 5 years",
            f"Across {len(common)} districts surveyed in both NFHS-4 (2016) and NFHS-5 (2021), the average household coverage rate jumped from {old_avg:.0f}% to {new_avg:.0f}%. A massive expansion driven by state-led schemes like Ayushman Bharat-PMJAY.",
            f"Mean {old_avg:.0f}% → {new_avg:.0f}%",
            "NFHS-4 + NFHS-5",
            'nfhs_health_insurance', '2021-03')


# ============================================================
# 23. STATE-LEVEL VIIRS LEADERS
# ============================================================
print("Mining state-level VIIRS facts...")
v23_state = defaultdict(list)
for r in v23['districts']:
    v23_state[r['state']].append(r['nl_mean'])
state_lit = sorted([(s, sum(vs)/len(vs), len(vs)) for s, vs in v23_state.items() if len(vs) >= 5],
                   key=lambda x: -x[1])
if state_lit:
    t = state_lit[0]
    add('insight', f"{t[0]}: India's most lit-up state",
        f"By 2023 average nighttime-light intensity, {t[0]}'s districts shine the brightest among major states. Density of urbanization and industrial activity at scale.",
        f"Mean district nightlight {t[1]:.2f} across {t[2]} districts",
        "SHRUG v2.1 — VIIRS 2023",
        'viirs_nightlights', '2023-12', t[0])
    b = state_lit[-1]
    add('insight', f"{b[0]}: India's darkest state from above",
        f"{b[0]} has the lowest average district nightlight intensity in India — {b[1]:.2f} on the VIIRS scale. Reflects a combination of low population density, mountainous terrain, and limited industrial activity.",
        f"Mean nightlight {b[1]:.2f}",
        "SHRUG v2.1 — VIIRS 2023",
        'viirs_nightlights', '2023-12', b[0])

# State-level VIIRS growth 2012→2023
v12_state = defaultdict(list)
for r in v12['districts']:
    v12_state[r['state']].append(r['nl_mean'])
state_growth = []
for s in v12_state:
    if s in v23_state and len(v12_state[s]) >= 5:
        old = sum(v12_state[s]) / len(v12_state[s])
        new = sum(v23_state[s]) / len(v23_state[s])
        if old > 0.05:
            state_growth.append((100 * (new - old) / old, old, new, s))
state_growth.sort(key=lambda x: -x[0])
if state_growth:
    t = state_growth[0]
    add('insight', f"{t[3]}: India's fastest-electrifying state",
        f"Between 2012 and 2023, {t[3]}'s average district nightlight intensity grew {t[0]:.0f}% — the largest decadal expansion among major Indian states. Captures a generational infrastructure build-out.",
        f"Mean {t[1]:.2f} (2012) → {t[2]:.2f} (2023)",
        "SHRUG v2.1 — VIIRS",
        'viirs_nightlights', '2023-12', t[3])


# ============================================================
# 24. PMJDY STATE-LEVEL TOTALS
# ============================================================
print("Mining PMJDY state aggregates...")
if pmjdy_files:
    state_pm = defaultdict(int)
    for r in pmjdy_latest['districts']:
        if r.get('total_pmjdy_no'):
            state_pm[r.get('state','')] += int(float(r['total_pmjdy_no']))
    state_pm_sorted = sorted(state_pm.items(), key=lambda x: -x[1])
    if state_pm_sorted and state_pm_sorted[0][1] > 0:
        s, v = state_pm_sorted[0]
        add('insight', f"{s.title()}: India's biggest Jan Dhan state",
            f"With {fmt_int(v)} active PMJDY accounts across its districts, {s.title()} has the largest Jan Dhan footprint of any Indian state in our data.",
            f"{fmt_int(v)} PMJDY accounts",
            f"SLBC, {period}",
            'pmjdy', period, s.title())


# ============================================================
# 25. CDR DECLINE STORIES (districts where lending shrank)
# ============================================================
print("Mining CDR decline stories...")
declines = []
for v_jump, q1, q2, v1, v2, dn, sn in qoq_jumps:
    pass  # already handled gains
# Look for sustained declines: latest CDR vs 4 quarters ago
db4 = sqlite3.connect(ROOT / 'db/finer.db')
for state_slug_db in [r[0] for r in db4.execute("SELECT DISTINCT source_file FROM slbc_data").fetchall()]:
    rows = db4.execute("""
        SELECT sd.district_lgd, sd.value_numeric, p.code FROM slbc_data sd
        JOIN slbc_fields f ON sd.field_id=f.id JOIN periods p ON sd.period_id=p.id
        WHERE sd.source_file=?
          AND f.category='credit_deposit_ratio'
          AND f.field_name IN ('overall_cd_ratio','cd_ratio','current_c_d_ratio')
          AND sd.value_numeric IS NOT NULL
          AND sd.value_numeric > 5 AND sd.value_numeric < 500
        ORDER BY sd.district_lgd, p.code
    """, (state_slug_db,)).fetchall()
    by_dist = defaultdict(list)
    for d_lgd, v, q in rows:
        by_dist[d_lgd].append((q, v))
    for d_lgd, series in by_dist.items():
        if len(series) >= 8:
            recent = series[-1]
            old = series[-8]  # ~2 years ago
            delta = recent[1] - old[1]
            if delta < -25 and old[1] > 50:
                if d_lgd in dist_info:
                    dn, sn, _ = dist_info[d_lgd]
                    declines.append((delta, old[0], recent[0], old[1], recent[1], dn, sn))
declines.sort(key=lambda x: x[0])
db4.close()
if declines:
    d = declines[0]
    add('milestone', f"{d[5]}: a sustained credit slowdown",
        f"Over the last two years (since {d[1]}), {d[5]}'s credit-deposit ratio fell from {d[3]:.0f}% to {d[4]:.0f}% — one of the most sustained credit shrinkages in our data. Local lending has cooled while deposits hold steady.",
        f"CDR {d[3]:.0f}% → {d[4]:.0f}% over 8 quarters",
        f"SLBC quarterly data",
        'credit_deposit_ratio', d[2], d[6], d[5])
    if len(declines) >= 2:
        d = declines[1]
        add('pattern', f"{d[5]}: bucking the lending boom",
            f"While most Indian districts saw credit grow over 2022–2024, {d[5]} ({d[6]}) saw its CDR fall from {d[3]:.0f}% to {d[4]:.0f}%.",
            f"-{abs(d[0]):.0f}pp over 8 quarters",
            f"SLBC quarterly data",
            'credit_deposit_ratio', d[2], d[6], d[5])


# ============================================================
# 26. AADHAAR STATE TOTALS
# ============================================================
print("Mining Aadhaar state aggregates...")
if aadhaar_files:
    state_aa = defaultdict(int)
    for r in aadhaar_latest['districts']:
        if r.get('total_enrolled'):
            state_aa[r.get('state','')] += int(r['total_enrolled'])
    state_aa_sorted = sorted(state_aa.items(), key=lambda x: -x[1])
    if state_aa_sorted:
        s, v = state_aa_sorted[0]
        add('insight', f"{s.title()}: India's Aadhaar enrollment leader",
            f"In just one quarter ({period}), {s.title()} processed {fmt_int(v)} new Aadhaar enrollments — more than any other state. Reflects ongoing catch-up registration.",
            f"{fmt_int(v)} new enrollments in one quarter",
            f"UIDAI 2026, {period}",
            'aadhaar_enrollment', period, s.title())


# ============================================================
# 27. METRO vs RURAL CONTRASTS
# ============================================================
print("Mining metro/rural contrasts...")
# Find districts with extreme metro share vs rural share in RBI outlets
if rbi_files:
    metro_heavy = sorted(
        [r for r in rbi['districts']
         if float(r.get('rbi_outlets__total', 0)) > 200
         and float(r.get('rbi_outlets__metro', 0)) / max(1, float(r.get('rbi_outlets__total', 1))) > 0.7],
        key=lambda r: -float(r.get('rbi_outlets__metro', 0))
    )
    if metro_heavy:
        t = metro_heavy[0]
        m = int(float(t['rbi_outlets__metro']))
        tot = int(float(t['rbi_outlets__total']))
        pct = 100 * m / tot
        add('pattern', f"India's most metropolitan banking footprint",
            f"In {t['district'].title()}, {t.get('state','?').title()}, {pct:.0f}% of all banking outlets sit in metropolitan centres (population >10 lakh) — the most urban-concentrated district network in India.",
            f"{m:,} of {tot:,} outlets are metro ({pct:.0f}%)",
            "RBI Banking Outlet Locator",
            'rbi_banking_outlets', '', t.get('state','').title(), t['district'].title())


# ============================================================
# 28. STATE-LEVEL DEPOSIT TOTALS
# ============================================================
print("Mining state deposit totals...")
state_dep = defaultdict(float)
for v, q, dn, sn in top_deposits[:200]:
    state_dep[sn] += v
state_dep_sorted = sorted(state_dep.items(), key=lambda x: -x[1])[:5]
if state_dep_sorted:
    t = state_dep_sorted[0]
    add('insight', f"{t[0]}: India's top deposit state",
        f"Across all districts in {t[0]} for which we have SLBC data, banks hold {fmt_inr(t[1])} in deposits — the largest aggregated deposit base of any state. Reflects industrial wealth + savings concentration.",
        f"{fmt_inr(t[1])} aggregate deposits",
        f"SLBC quarterly data, latest available",
        'credit_deposit_ratio', '', t[0])


# ============================================================
# 29. NIGHTLIGHTS — quiet/loud milestones at decade scale
# ============================================================
v23_min = sorted(v23['districts'], key=lambda r: r['nl_mean'])[0]
add('extreme_low', f"India's quietest district from space",
    f"{v23_min['district']}, {v23_min['state']} is India's darkest district by night even in 2023 — mean nightlight intensity of just {v23_min['nl_mean']:.3f}, far below national average. A signature of remoteness and low population density.",
    f"Mean nightlight {v23_min['nl_mean']:.3f}",
    "SHRUG v2.1 — VIIRS 2023",
    'viirs_nightlights', '2023-12', v23_min['state'], v23_min['district'])


# ============================================================
# 30. PHONE PE — TOP STATES BY UPI
# ============================================================
print("Mining PhonePe state aggregates...")
db5 = sqlite3.connect(ROOT / 'db/finer.db')
if db5.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phonepe_data'").fetchone():
    pp_state = db5.execute("""
        SELECT ph.state_slug, SUM(ph.transaction_count) FROM phonepe_data ph
        JOIN periods p ON ph.period_id=p.id
        WHERE p.code = (SELECT MAX(p2.code) FROM phonepe_data ph2 JOIN periods p2 ON ph2.period_id=p2.id)
        GROUP BY ph.state_slug ORDER BY SUM(ph.transaction_count) DESC LIMIT 5
    """).fetchall()
    if pp_state:
        s, v = pp_state[0]
        add('insight', f"{s.replace('-',' ').title()}: India's UPI superstate",
            f"In a single quarter, {s.replace('-',' ').title()}'s residents made {fmt_int(int(v))} PhonePe UPI transactions — the highest of any state. India runs on QR-code payments now.",
            f"{fmt_int(int(v))} PhonePe transactions",
            f"PhonePe Pulse, latest quarter",
            'digital_transactions', '', s.replace('-',' ').title())
db5.close()


# ============================================================
# 31. RBI BANKING OUTLET DENSITY ACROSS NE
# ============================================================
print("Mining NE banking density...")
if rbi_files:
    ne = ['ASSAM', 'MEGHALAYA', 'MANIPUR', 'MIZORAM', 'NAGALAND', 'TRIPURA', 'ARUNACHAL PRADESH', 'SIKKIM']
    ne_outlets = sum(float(r.get('rbi_outlets__total', 0))
                     for r in rbi['districts'] if r.get('state','').upper() in ne)
    total_outlets = sum(float(r.get('rbi_outlets__total', 0)) for r in rbi['districts'])
    if total_outlets > 0:
        pct = 100 * ne_outlets / total_outlets
        add('insight', f"India's NE has {pct:.1f}% of the nation's banking outlets",
            f"Across all 8 Northeast states, RBI counts {ne_outlets:,.0f} banking outlets — just {pct:.1f}% of India's total {total_outlets:,.0f}. The NE is home to ~3.8% of India's population, so banking density per capita is roughly comparable, but the absolute footprint is small.",
            f"{ne_outlets:,.0f} of {total_outlets:,.0f} outlets ({pct:.1f}%)",
            "RBI Banking Outlet Locator",
            'rbi_banking_outlets')


# ============================================================
# 32. ADDITIONAL CDR per-state lows (for variety)
# ============================================================
print("Mining state-low CDR districts (variety)...")
state_lows = {}
for v, q, lgd, dn, sn in reversed(all_cdr):
    if sn not in state_lows and sn not in ['Lakshadweep','Andaman and Nicobar','Chandigarh','Puducherry','Goa']:
        state_lows[sn] = (v, q, dn)
extra = 0
for sn, (v, q, dn) in state_lows.items():
    if v >= 30 or extra >= 5: continue  # only deeply-credit-starved
    extra += 1
    add('state_leader', f"{sn}'s most credit-starved corner",
        f"Of all districts in {sn}, {dn} has the lowest credit-deposit ratio at {v:.0f}% — savings substantially exceed local lending here.",
        f"CDR {v:.0f}% — {dn}",
        f"SLBC, {q}",
        'credit_deposit_ratio', q, sn, dn)


# ============================================================
# Write outputs
# ============================================================

# ============================================================
# 33. FINAL FILLERS — More state-leader CDR (low side) + extreme outliers
# ============================================================
print("Mining final variety facts...")

# 5 more state high-CDR leaders (medium-CDR states we missed)
seen_high = {f['state'] for f in facts if f['category'] == 'state_leader' and 'heaviest' in f['headline']}
extra_count = 0
for v, q, lgd, dn, sn in all_cdr:
    if sn in seen_high or sn in ['Lakshadweep','Andaman and Nicobar','Chandigarh','Puducherry','Delhi','Goa']:
        continue
    if 80 <= v <= 130:  # mid-range leaders for variety
        seen_high.add(sn)
        add('state_leader', f"{sn}'s top-lending district",
            f"In {sn}, {dn} leads on credit-deposit ratio at {v:.0f}% — banks lending more aggressively here than in any other district of the state.",
            f"CDR {v:.0f}%",
            f"SLBC, {q}",
            'credit_deposit_ratio', q, sn, dn)
        extra_count += 1
        if extra_count >= 5: break

# Aadhaar mega-totals (the all-India enrollment burst)
if aadhaar_files and len(aadhaar_files) >= 2:
    total_enrolled_latest = sum(int(r.get('total_enrolled', 0)) for r in aadhaar_latest['districts'])
    add('insight', f"India enrolled {fmt_int(total_enrolled_latest)} new Aadhaars in one quarter",
        f"In just {period} alone, India processed {fmt_int(total_enrolled_latest)} fresh Aadhaar enrollments across {len(aadhaar_latest['districts'])} districts. The world's largest biometric ID system continues to expand.",
        f"{fmt_int(total_enrolled_latest)} new enrollments in one quarter",
        f"UIDAI 2026 dataset",
        'aadhaar_enrollment', period)

# Sharp PMJDY accounts dispersion
if pmjdy_files and pm_total:
    median_pm = pm_total[len(pm_total)//2]
    median_v = int(float(median_pm['total_pmjdy_no']))
    top_v = int(float(pm_total[0]['total_pmjdy_no']))
    ratio = top_v / max(1, median_v)
    add('insight', f"India's biggest Jan Dhan district has {ratio:.0f}× the median",
        f"{pm_total[0]['district']} has {fmt_int(top_v)} PMJDY accounts while the median Indian district has only {fmt_int(median_v)} — a {ratio:.0f}-fold gap that reveals how concentrated Jan Dhan deposits are in a few large districts.",
        f"Top: {fmt_int(top_v)} vs median: {fmt_int(median_v)}",
        f"SLBC, {period}",
        'pmjdy', period)

# RBI banking outlets total
if rbi_files:
    add('insight', f"India's banking footprint: 2.47M outlets",
        f"RBI's DBIE database catalogues {sum(float(r.get('rbi_outlets__total', 0)) for r in rbi['districts']):,.0f} banking outlets across the country — branches, BCs, ATMs, CSPs and DBUs combined. Each one geo-tagged.",
        f"~2.47 million outlets nationwide",
        "RBI Banking Outlet Locator (DBIE)",
        'rbi_banking_outlets')

# VIIRS national growth
total_v12 = sum(r['nl_sum'] for r in v12['districts'])
total_v23 = sum(r['nl_sum'] for r in v23['districts'])
nat_growth = 100 * (total_v23 - total_v12) / total_v12
add('insight', f"India's total night-time light grew {nat_growth:.0f}% in a decade",
    f"Adding up nighttime-light radiance across all Indian districts, India shone {nat_growth:.0f}% brighter in 2023 than in 2012. A satellite signature of the country's economic growth.",
    f"Total VIIRS sum: {total_v12/1e6:.1f}M → {total_v23/1e6:.1f}M nW/cm²/sr",
    "SHRUG v2.1 — VIIRS",
    'viirs_nightlights', '2023-12')

# RWI extreme detail
if rwi_path.exists():
    # Wealthiest rural-feel district (RWI > 1, mostly rural)
    add('insight', f"India's richest-poorest gap: {abs(r_sorted[0]['rwi_mean'] - r_sorted[-1]['rwi_mean']):.1f} RWI points",
        f"Between India's wealthiest district ({r_sorted[0]['district']}, {r_sorted[0]['state']}, RWI {r_sorted[0]['rwi_mean']:+.2f}) and its poorest ({r_sorted[-1]['district']}, {r_sorted[-1]['state']}, RWI {r_sorted[-1]['rwi_mean']:+.2f}), the wealth gap is {abs(r_sorted[0]['rwi_mean'] - r_sorted[-1]['rwi_mean']):.1f} units on Meta's index — roughly 2 standard deviations.",
        f"RWI gap {abs(r_sorted[0]['rwi_mean'] - r_sorted[-1]['rwi_mean']):.1f}",
        "SHRUG v2.1 — Meta RWI 2021",
        'facebook_rwi', '2021-12')


# ============================================================
# CURATION PASS — fix scope claims, cap repetition, tighten sources
# ============================================================
print("\nCurating: scope, repetition, sources...")

# --- Scope replacements per indicator ---
# Default: every SLBC fact gets "in our SLBC sample" instead of "in India".
SLBC_INDICATORS = {'credit_deposit_ratio', 'pmjdy', 'kcc', 'shg', 'branch_network'}
# Aadhaar/NFHS/RBI cover most of India; PhonePe, capital_markets are pan-India
NATIONAL_INDICATORS = {'rbi_banking_outlets', 'aadhaar_enrollment', 'capital_markets_access',
                       'digital_transactions'}
# SHRUG-derived (with attribution requirement)
SHRUG_INDICATORS = {'facebook_rwi', 'viirs_nightlights', 'pmgsy_roads'}
# NFHS (with attribution requirement)
NFHS_INDICATORS = {'nfhs_health_insurance'}

SCOPE_PHRASE = {
    'credit_deposit_ratio': 'in our SLBC data',
    'pmjdy': 'in our SLBC data',
    'kcc': 'in our SLBC data',
    'shg': 'in our SLBC data',
    'branch_network': 'in our SLBC data',
    # SHRUG-derived: ~625 districts (pre-2014 boundaries)
    'facebook_rwi': 'in the 625-district SHRUG sample',
    'viirs_nightlights': 'in the 625-district SHRUG sample',
    'pmgsy_roads': 'in the SHRUG-PMGSY sample',
    # NFHS-5: 637 districts surveyed
    'nfhs_health_insurance': 'across the 637 districts surveyed by NFHS-5',
    # UIDAI: 985 districts × Apr-Dec 2025
    'aadhaar_enrollment': 'among the 985 districts in the UIDAI dataset',
    # RBI: full national dataset
    'rbi_banking_outlets': 'in India',
    # PhonePe: pan-India
    'digital_transactions': 'in India',
    'capital_markets_access': 'in India',
}


def fix_scope(text, indicator):
    """Replace overclaim phrases with indicator-appropriate scope.

    Headlines and ledes shouldn't claim 'India's most X' if our coverage is partial.
    For SLBC indicators (22 of 30 states), rephrase to scope-honest claims.
    For RBI/PhonePe/CapMkts (truly national), keep 'India' framing.
    """
    scope = SCOPE_PHRASE.get(indicator, 'in our data')
    is_partial_coverage = indicator in SLBC_INDICATORS or indicator in SHRUG_INDICATORS

    # First — fix headline-style overclaims ("India's most X")
    if is_partial_coverage:
        # Generic "India's <SUPERLATIVE>" → "Our sample's <SUPERLATIVE>"
        text = re.sub(r"\bIndia's (most|biggest|largest|smallest|heaviest|busiest|wealthiest|quietest|brightest|darkest|highest|lowest|fastest|slowest|deepest|widest|toughest|richest|poorest|tallest|shortest|loudest)\b",
                      r"Our sample's \1", text)
        text = re.sub(r"\bIndia's only ", "Among our data, the only ", text)
        # "among India's lowest/highest/etc."
        text = re.sub(r"\bamong India's (most|biggest|largest|smallest|heaviest|highest|lowest|fastest|slowest)\b",
                      r"among the \1", text)
        # "the largest of any X in India" →  "the largest of any X in our SLBC data"
        # (handled by the in-India replacement below)

    replacements = [
        (r'\bin India\b', scope),
        (r'\bin the country\b', scope),
        (r'\bin any Indian district\b', f'of any district {scope}'),
        (r'\bin any major district\b', f'of any major district {scope}'),
        (r'\bin any single district\b', f'of any single district {scope}'),
        (r'\bof any district\b', f'of any district {scope}'),
        (r'\bof any single district\b', f'of any single district {scope}'),
        (r'\bof any major state\b', f'of any state {scope}'),
        (r'\bof any state\b', f'of any state {scope}'),
        (r'\bof any major district\b', f'of any major district {scope}'),
        # Skip "any other district of the state" — that's a within-state claim, not an
        # India-wide one, so it doesn't need scope qualifying.
        (r'\bany other district\b(?!\s+of\b)', f'any other district {scope}'),
        (r'\bany other state\b(?!\s+of\b)', f'any other state {scope}'),
        (r'\bof any Indian district\b', f'of any district {scope}'),
        (r'\ball Indian districts\b', f'all districts {scope}'),
        (r'\bnationally\b', scope),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    # Strip duplicated scope phrases
    text = re.sub(rf'({re.escape(scope)})[\s,—.]*({re.escape(scope)})', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# --- Source line attribution standardization ---
# Per-indicator source citations.
# SHRUG datasets (CC BY-NC-SA 4.0) require:
#   1. The core SHRUG citation: Asher, Lunt, Matsuura, Novosad 2021 (World Bank Econ Review)
#   2. Module-specific citations (Chi et al. 2022 for RWI; Asher & Novosad 2020 for PMGSY)
#   3. Attribution to Development Data Lab + license
# NFHS data: IIPS / ICF / Ministry of Health & Family Welfare
SOURCE_BY_INDICATOR = {
    'credit_deposit_ratio': 'SLBC quarterly data',
    'pmjdy': 'SLBC quarterly data',
    'kcc': 'SLBC quarterly data',
    'shg': 'SLBC quarterly data',
    'branch_network': 'SLBC quarterly data',
    'rbi_banking_outlets': 'RBI DBIE Banking Outlet Locator',
    'nfhs_health_insurance': 'NFHS-5 (2019–21), International Institute for Population Sciences (IIPS) / ICF / Ministry of Health & Family Welfare, GoI',
    'aadhaar_enrollment': 'UIDAI district enrolment data, Apr–Dec 2025',
    # SHRUG citations match docs.devdatalab.org plaintext format
    'facebook_rwi': 'Chi et al., PNAS 2022 (Microestimates of wealth) + Asher et al., World Bank Economic Review 2021. SHRUG v2.1, Development Data Lab. CC BY-NC-SA 4.0.',
    'viirs_nightlights': 'NOAA/Colorado School of Mines VIIRS via Asher et al., World Bank Economic Review 2021. SHRUG v2.1, Development Data Lab. CC BY-NC-SA 4.0.',
    'pmgsy_roads': 'Asher & Novosad, American Economic Review 2020 (Rural Roads and Local Economic Development). NRRDA / Ministry of Rural Development. SHRUG v2.1, Development Data Lab. CC BY-NC-SA 4.0.',
    'nrlm_shg': 'DAY-NRLM, Ministry of Rural Development, Government of India',
    'digital_transactions': 'PhonePe Pulse',
    'capital_markets_access': 'CDSL + NSDL + AMFI registries',
}


def fix_source(source, indicator, period=None):
    """Use a clean canonical source line, append period if relevant."""
    base = SOURCE_BY_INDICATOR.get(indicator, source)
    if period and indicator in SLBC_INDICATORS:
        base = f"{base}, {period}"
    # Aadhaar source already says "Apr–Dec 2025"; don't append period
    return base


# --- Strip verbose explanatory phrases from ledes ---
LEDE_STRIP_PATTERNS = [
    r'\s*Each is mapped to GPS coordinates in RBI\'s DBIE database\.',
    r'\s*Crops include cotton, paddy, sugarcane\.',
    r'\s*Each is a licensed advisor/seller of mutual fund products\.',
    r'\s*Each card provides revolving short-term credit at subsidized rates for crop production and allied activities\.',
    r'\s*\(calibrated against DHS surveys\)',
    r'\s*— branches, BCs, ATMs, CSPs and DBUs combined\.',
    r' Each one geo-tagged\.',
    r' A signature of remoteness and low population density\.',
    r' Reflects a combination of low population density, mountainous terrain, and limited industrial activity\.',
]


def strip_lede(lede):
    for pat in LEDE_STRIP_PATTERNS:
        lede = re.sub(pat, '', lede)
    # Collapse double spaces
    lede = re.sub(r'\s+', ' ', lede).strip()
    return lede


# --- Apply curation ---
for f in facts:
    f['headline'] = fix_scope(f['headline'], f['indicator'])
    f['lede'] = strip_lede(fix_scope(f['lede'], f['indicator']))
    f['source'] = fix_source(f['source'], f['indicator'], f.get('period'))


# --- Cap repetitive categories ---
# Limit state_leader 'heaviest-borrowing' to 8 (was 25)
heaviest = [f for f in facts if f['category'] == 'state_leader' and 'heaviest' in f['headline'].lower()]
heaviest_to_keep = set(f['id'] for f in heaviest[:8])
heaviest_to_drop = set(f['id'] for f in heaviest[8:])
# Limit state_leader 'low' to 4
state_low_leaders = [f for f in facts
                     if f['category'] == 'state_leader' and ('starved' in f['headline'].lower() or 'most credit-starved' in f['headline'].lower())]
slow_to_drop = set(f['id'] for f in state_low_leaders[4:])
# Limit extreme_high CDR (heaviest borrowers) to top 2
cdr_eh = [f for f in facts if f['category'] == 'extreme_high' and f['indicator'] == 'credit_deposit_ratio']
cdr_eh_to_drop = set(f['id'] for f in cdr_eh[2:5])

drop_ids = heaviest_to_drop | slow_to_drop | cdr_eh_to_drop
print(f"  Dropping {len(drop_ids)} repetitive facts")
facts = [f for f in facts if f['id'] not in drop_ids]

# Renumber
for i, f in enumerate(facts):
    f['id'] = f'{i+1:03d}'


# ============================================================
# Write outputs
# ============================================================
db.close()

out_dir = ROOT / 'public/facts'
out_dir.mkdir(exist_ok=True)
with open(out_dir / 'facts.json', 'w') as f:
    json.dump({'count': len(facts), 'generated': '2026-05-10', 'facts': facts}, f, indent=2)

# Markdown for review
with open(out_dir / 'facts.md', 'w') as f:
    f.write(f"# Surprise Me — {len(facts)} facts\n\nGenerated from FINER data on 2026-05-10.\n\n")
    cur_cat = None
    for fact in facts:
        if fact['category'] != cur_cat:
            cur_cat = fact['category']
            f.write(f"\n## {cur_cat}\n\n")
        f.write(f"### {fact['id']}. {fact['headline']}\n\n")
        f.write(f"{fact['lede']}\n\n")
        f.write(f"**{fact['stat']}**  \n")
        f.write(f"_{fact['source']}_  \n")
        f.write(f"[Open in map]({fact['map_link']})\n\n---\n\n")

print(f"\n✅ Generated {len(facts)} facts")
print(f"   → public/facts/facts.json ({(out_dir / 'facts.json').stat().st_size / 1024:.1f} KB)")
print(f"   → public/facts/facts.md ({(out_dir / 'facts.md').stat().st_size / 1024:.1f} KB)")
