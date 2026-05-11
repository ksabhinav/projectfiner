"""
Build Agricultural Land Use & Irrigation indicator from SHRUG v2.1.

Source: India Population Census 2011 Village Directory (VD11) — district-aggregated
        by SHRUG v2.1 (pc11_vd_clean_pc11dist).
        ~/Downloads/finer_data/shrug-vd11/pc11_vd_clean_pc11dist.tab

The Census Village Directory enumerates land-use accounts for every revenue village.
SHRUG aggregates the 16 land-use columns to district level. We expose the most
financially-relevant ones (irrigated area is the strongest predictor of KCC
penetration, agri-credit demand, MSP procurement, and rural-credit profitability):

  - cropland_ha        — Net Sown Area (ha) — district's cultivated footprint
  - irrigated_ha       — Total Irrigated Area (ha) — assured-water cropland
  - unirrigated_ha     — Unirrigated Area (ha) — rain-fed cropland
  - canal_irr_ha       — Canal-irrigated Area (ha) — major-irrigation projects
  - tubewell_irr_ha    — Well/Tubewell-irrigated Area (ha) — groundwater
  - irrigation_pct     — irrigated_ha / (irrigated_ha + unirrigated_ha) × 100
  - forest_ha          — Forest Area (ha) — context for hilly/tribal districts

SHRUG does not publish district-level crop output (rice/wheat tonnes) in v2.1 —
the closest agricultural production proxy is the Village Directory land-use
table. Net Sown Area is the canonical "how much of this district is under
cultivation" measure; Irrigated Area is the canonical "how much of that
cropland is climate-resilient" measure.

Joins via FINER (state_lgd, census_2011_code) → SHRUG (pc11_state_id,
pc11_district_id). Output: public/indicators/crop_production/static.json.

License: SHRUG v2.1 CC BY-NC-SA 4.0. Underlying Census 2011 is © Office of the
Registrar General & Census Commissioner, India.

Citations:
  Office of the Registrar General & Census Commissioner, India. (2011).
    Population Census 2011 — Village Directory.
  Asher, S., Lunt, T., Matsuura, R., & Novosad, P. (2021). Development
    research at high geographic resolution: an analysis of night-lights,
    firms, and poverty in India using the SHRUG open data platform.
    The World Bank Economic Review, 35(4), 845-871.
"""
import csv, json, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = Path.home() / 'Downloads/finer_data/shrug-vd11/pc11_vd_clean_pc11dist.tab'
OUT = ROOT / 'public/indicators/crop_production/static.json'


def main():
    db = sqlite3.connect(ROOT / 'db/finer.db')
    # Build (pc11_state, pc11_district) → (lgd, district_name, state_name) map
    finer = {}
    for r in db.execute("""SELECT d.lgd_code, d.name, d.state_lgd_code, d.census_2011_code, s.name
                           FROM districts d JOIN states s ON s.lgd_code=d.state_lgd_code
                           WHERE d.census_2011_code IS NOT NULL AND d.census_2011_code != ''"""):
        lgd, dname, st_lgd, c11, sname = r
        try:
            key = (f"{st_lgd:02d}", f"{int(c11):03d}")
        except ValueError:
            continue
        finer[key] = (lgd, dname, sname)
    db.close()

    if not SRC.exists():
        raise SystemExit(f"Source file not found: {SRC}")

    districts = []
    unmatched = 0
    with open(SRC) as f:
        for row in csv.DictReader(f, delimiter='\t'):
            key = (row['pc11_state_id'].strip(), row['pc11_district_id'].strip())
            if key not in finer:
                unmatched += 1
                continue
            lgd, dname, sname = finer[key]

            def num(col):
                v = row.get(col, '')
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return 0.0

            cropland_ha     = num('pc11_vd_land_nt_swn')
            irrigated_ha    = num('pc11_vd_land_src_irr')
            unirrigated_ha  = num('pc11_vd_land_un_irr')
            canal_ha        = num('pc11_vd_land_canal_irr')
            tubewell_ha     = num('pc11_vd_land_wl_tw_irr')
            forest_ha       = num('pc11_vd_land_fores')

            # Skip rows where every land-use column is 0 (data simply absent)
            if (cropland_ha + irrigated_ha + unirrigated_ha + canal_ha + tubewell_ha + forest_ha) == 0:
                continue

            denom = irrigated_ha + unirrigated_ha
            irrigation_pct = (irrigated_ha / denom * 100.0) if denom > 0 else 0.0

            districts.append({
                'district_lgd': lgd,
                'district': dname,
                'state': sname,
                'cropland_ha':     round(cropland_ha, 1),
                'irrigated_ha':    round(irrigated_ha, 1),
                'unirrigated_ha':  round(unirrigated_ha, 1),
                'canal_irr_ha':    round(canal_ha, 1),
                'tubewell_irr_ha': round(tubewell_ha, 1),
                'irrigation_pct':  round(irrigation_pct, 1),
                'forest_ha':       round(forest_ha, 1),
            })

    # Stable sort for diff-friendly output
    districts.sort(key=lambda d: (d['state'], d['district']))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'indicator': 'crop_production',
        'quarter': 'static',
        'label': 'Agricultural Land Use & Irrigation (Census 2011 VD, via SHRUG v2.1)',
        'source': 'Census 2011 Village Directory, district-aggregated via SHRUG v2.1',
        'scraped_date': '2011-03-01',
        'districts': districts,
    }
    with open(OUT, 'w') as f:
        json.dump(payload, f, separators=(',', ':'))
    print(f"  {OUT.relative_to(ROOT)}: {len(districts)} districts ({unmatched} unmatched)")


if __name__ == '__main__':
    main()
