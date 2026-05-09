"""
Precompute per-state bounds, centroid, slug, LGD from public/data/india_states.geojson
joined to FINER's states table.

Output: public/state-bounds.json — keyed by 2-letter state_code (matches the
geojson feature property), with each entry containing:
  - name, state_code (2-letter)
  - bounds: leaflet [[south,west],[north,east]]
  - centroid: [lat, lng]
  - lgd: FINER state lgd_code (integer)
  - slug: FINER state slug (kebab-case)
  - finer_name: FINER's canonical state name

Run:
  python3 scripts/build_state_bounds.py
"""
import json, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALIASES = {
    'jammu & kashmir': 'jammu and kashmir',
    'orissa': 'odisha',
    'pondicherry': 'puducherry',
    'uttaranchal': 'uttarakhand',
    'andaman & nicobar': 'andaman and nicobar',
    'andaman and nicobar islands': 'andaman and nicobar',
    'dadra & nagar haveli & daman & diu': 'dadra and nagar haveli and daman and diu',
}


def bbox_from_geom(geom):
    minx, miny, maxx, maxy = 1e9, 1e9, -1e9, -1e9

    def walk(c):
        nonlocal minx, miny, maxx, maxy
        if (isinstance(c, (list, tuple)) and len(c) >= 2
                and isinstance(c[0], (int, float))):
            x, y = c[0], c[1]
            if x < minx: minx = x
            if y < miny: miny = y
            if x > maxx: maxx = x
            if y > maxy: maxy = y
        elif isinstance(c, list):
            for sub in c:
                walk(sub)
    walk(geom['coordinates'])
    return [minx, miny, maxx, maxy]


def main():
    db = sqlite3.connect(ROOT / 'db/finer.db')
    finer = {}
    for lgd, name, slug in db.execute("SELECT lgd_code, name, slug FROM states"):
        norm = name.lower().replace('&', 'and').strip()
        finer[norm] = (lgd, slug, name)
    db.close()

    with open(ROOT / 'public/data/india_states.geojson') as f:
        g = json.load(f)

    bounds, unmatched = {}, []
    for ft in g['features']:
        name = ft['properties']['state_name']
        code = ft['properties']['state_code']
        norm = name.lower().replace('&', 'and').strip()
        norm = ALIASES.get(norm, norm)

        match = finer.get(norm)
        if not match:
            for k, v in finer.items():
                if norm in k or k in norm:
                    match = v
                    break

        bb = bbox_from_geom(ft['geometry'])
        entry = {
            'name': name,
            'state_code': code,
            'bounds': [[bb[1], bb[0]], [bb[3], bb[2]]],
            'centroid': [(bb[1] + bb[3]) / 2, (bb[0] + bb[2]) / 2],
        }
        if match:
            lgd, slug, finer_name = match
            entry['lgd'] = lgd
            entry['slug'] = slug
            entry['finer_name'] = finer_name
        else:
            unmatched.append(name)
        bounds[code] = entry

    print(f"States: {len(g['features'])}, matched: {sum(1 for v in bounds.values() if 'lgd' in v)}")
    if unmatched:
        print(f"Unmatched: {unmatched}")

    out = ROOT / 'public/state-bounds.json'
    with open(out, 'w') as f:
        json.dump(bounds, f, indent=2)
    print(f"Wrote {out.relative_to(ROOT)} ({out.stat().st_size/1024:.1f} KB)")


if __name__ == '__main__':
    main()
