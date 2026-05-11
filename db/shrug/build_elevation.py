"""
Build Elevation & Terrain Ruggedness indicator from SHRUG v2.1.

Source: NASA SRTM (Shuttle Radar Topography Mission, Farr & Kobrick 2000)
        — district-aggregated by SHRUG v2.1.
        ~/Downloads/finer_data/shrug-elevation/elevation_pc11dist.csv

SRTM is a 30m-resolution global DEM captured in Feb 2000. SHRUG aggregates
elevation cells to district level and reports mean, median, std, min, max,
plus 5th/25th percentiles. We expose:

  - elevation_mean   — mean elevation in metres (proxy for hill/plain)
  - elevation_max    — peak within district
  - elevation_range  — max − min (a Riley-style ruggedness proxy)
  - elevation_std    — within-district elevation std (also a TRI proxy;
                        higher = more rugged)

Joins via FINER (state_lgd, census_2011_code) → SHRUG (pc11_state_id,
pc11_district_id). Output: public/indicators/elevation_terrain/static.json.

License: SHRUG v2.1 CC BY-NC-SA 4.0. Underlying SRTM data is public-domain
(NASA/NGA).

Citations:
  Farr, T. G., & Kobrick, M. (2000). Shuttle Radar Topography Mission
    produces a wealth of data. Eos, Transactions American Geophysical
    Union, 81(48), 583-585.
  Asher, S., Lunt, T., Matsuura, R., & Novosad, P. (2021). Development
    research at high geographic resolution: an analysis of night-lights,
    firms, and poverty in India using the SHRUG open data platform.
    The World Bank Economic Review, 35(4), 845-871.
"""
import csv, json, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = Path.home() / 'Downloads/finer_data/shrug-elevation/elevation_pc11dist.csv'
OUT = ROOT / 'public/indicators/elevation_terrain/static.json'


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
        for row in csv.DictReader(f):
            key = (row['pc11_state_id'].strip(), row['pc11_district_id'].strip())
            if key not in finer:
                unmatched += 1
                continue
            lgd, dname, sname = finer[key]
            try:
                emean = float(row['elevation_mean'])
                emedian = float(row['elevation_median'])
                emin = float(row['elevation_min'])
                emax = float(row['elevation_max'])
                estd = float(row['elevation_std'])
            except (ValueError, KeyError, TypeError):
                continue
            districts.append({
                'district_lgd': lgd,
                'district': dname,
                'state': sname,
                'elevation_mean':   round(emean, 1),
                'elevation_median': round(emedian, 1),
                'elevation_min':    round(emin, 1),
                'elevation_max':    round(emax, 1),
                'elevation_range':  round(emax - emin, 1),
                'elevation_std':    round(estd, 1),
            })

    # Stable sort for diff-friendly output
    districts.sort(key=lambda d: (d['state'], d['district']))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'indicator': 'elevation_terrain',
        'quarter': 'static',
        'label': 'Elevation & Terrain Ruggedness (SRTM, ~2000)',
        'source': 'SRTM (NASA, Feb 2000), district-aggregated via SHRUG v2.1',
        'scraped_date': '2000-02-22',
        'districts': districts,
    }
    with open(OUT, 'w') as f:
        json.dump(payload, f, separators=(',', ':'))
    print(f"  {OUT.relative_to(ROOT)}: {len(districts)} districts ({unmatched} unmatched)")


if __name__ == '__main__':
    main()
