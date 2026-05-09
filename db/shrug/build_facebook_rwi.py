"""
Build Facebook Relative Wealth Index (RWI) indicator from SHRUG v2.1.

Source: Meta/Facebook RWI 2021, district-aggregated by SHRUG.
        ~/Downloads/finer_data/shrug/facebook-rwi/facebook_rwi_pc11dist.csv

RWI is a relative wealth proxy derived from FB connectivity + satellite imagery + survey calibration
(Chi et al. 2022). Scale roughly -2 to +2; higher = wealthier than India average.

Joins via FINER (state_lgd, census_2011_code) → SHRUG (pc11_state_id, pc11_district_id).
Output: public/indicators/facebook_rwi/2021-12.json

License: SHRUG is CC BY-NC-SA 4.0. RWI itself is from Meta Data for Good — see citation.
"""
import csv, json, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = Path.home() / 'Downloads/finer_data/shrug/facebook-rwi/facebook_rwi_pc11dist.csv'
OUT = ROOT / 'public/indicators/facebook_rwi/2021-12.json'


def main():
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

    districts = []
    unmatched = 0
    with open(SRC) as f:
        for row in csv.DictReader(f):
            key = (row['pc11_state_id'].strip(), row['pc11_district_id'].strip())
            if key not in finer:
                unmatched += 1
                continue
            lgd, dname, sname = finer[key]
            try:
                mean = float(row['facebook_mean_rwi'])
                rmin = float(row['facebook_min_rwi'])
                rmax = float(row['facebook_max_rwi'])
                cells = int(float(row['facebook_num_cells_rwi']))
                error_mean = float(row['facebook_mean_error'])
            except (ValueError, KeyError, TypeError):
                continue
            districts.append({
                'district_lgd': lgd,
                'district': dname,
                'state': sname,
                'rwi_mean': round(mean, 3),
                'rwi_min': round(rmin, 3),
                'rwi_max': round(rmax, 3),
                'rwi_spread': round(rmax - rmin, 3),
                'rwi_cells': cells,
                'rwi_error_mean': round(error_mean, 3),
            })

    print(f"FB RWI districts mapped: {len(districts)} (unmatched: {unmatched})")

    out = {
        'indicator': 'facebook_rwi',
        'period': '2021-12',
        'period_label': 'Facebook RWI 2021',
        'source': 'SHRUG v2.1 (Development Data Lab) — Meta/Facebook Relative Wealth Index 2021 (Chi et al.)',
        'license': 'CC BY-NC-SA 4.0',
        'districts': districts,
    }
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"  wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size/1024:.1f} KB)")


if __name__ == '__main__':
    main()
