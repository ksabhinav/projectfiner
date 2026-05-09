"""
Build VIIRS annual nightlights indicator from SHRUG v2.1.

Source: ~/Downloads/finer_data/shrug/viirs/viirs_annual_pc11dist.dta (DTA, district-aggregated)

VIIRS nightlights are a satellite-based proxy for economic activity. SHRUG provides
annual district means/sums for 2012–2023 in two flavours: 'median-masked' (robust to
fires/outliers) and 'average-masked' (smoother). We use median-masked.

Output: one indicator file per year (12 files, 2012-12.json through 2023-12.json),
treating each year as a December snapshot in the FINER timeline.

Joins via FINER (state_lgd, census_2011_code) → SHRUG (pc11_state_id, pc11_district_id).
"""
import json, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = Path.home() / 'Downloads/finer_data/shrug/viirs/viirs_annual_pc11dist.dta'
OUT_DIR = ROOT / 'public/indicators/viirs_nightlights'


def main():
    import pandas as pd

    df = pd.read_stata(SRC)
    df = df[df['category'] == 'median-masked'].copy()
    print(f"VIIRS rows (median-masked): {len(df)}")
    print(f"Years: {sorted(df['year'].unique())}")

    db = sqlite3.connect(ROOT / 'db/finer.db')
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

    OUT_DIR.mkdir(exist_ok=True)
    for year in sorted(df['year'].unique()):
        ydf = df[df['year'] == year]
        period = f"{year}-12"
        districts = []
        unmatched = 0
        for _, row in ydf.iterrows():
            key = (str(row['pc11_state_id']).strip(), str(row['pc11_district_id']).strip())
            if key not in finer:
                unmatched += 1
                continue
            lgd, dname, sname = finer[key]
            districts.append({
                'district_lgd': lgd,
                'district': dname,
                'state': sname,
                'nl_mean': round(float(row['viirs_annual_mean']), 4),
                'nl_sum': round(float(row['viirs_annual_sum']), 1),
                'nl_max': round(float(row['viirs_annual_max']), 2),
            })
        out = {
            'indicator': 'viirs_nightlights',
            'period': period,
            'period_label': f'VIIRS Nightlights {int(year)} (annual median-masked)',
            'source': 'SHRUG v2.1 (Development Data Lab) — VIIRS annual nightlights composite',
            'license': 'CC BY-NC-SA 4.0',
            'districts': districts,
        }
        out_path = OUT_DIR / f'{period}.json'
        with open(out_path, 'w') as f:
            json.dump(out, f, separators=(',', ':'))
        print(f"  {period}: {len(districts)} districts, {out_path.stat().st_size/1024:.1f} KB")


if __name__ == '__main__':
    main()
