"""Render the site-wide Open Graph card → public/og-image.png (1200×630).

The card is scripts/og_card_template.html with a district choropleth filled in
from real data: the homepage's default view (PhonePe UPI transaction count,
latest quarter), using the map's own vermillion ramp and quantile breaks
(computeBreaks / getColor in src/pages/index.astro). Districts that don't join
render in the map's no-data grey rather than being guessed.

Rendered with headless Chrome (Playwright) so the Google Fonts actually load —
cairosvg silently fell back to Helvetica.

    python3 scripts/build_og_image.py
"""
import json
import math
import re
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / 'scripts/og_card_template.html'
PNG = ROOT / 'public/og-image.png'
GEO = ROOT / 'public/data/district_boundaries.geojson'
OUTLINE = ROOT / 'public/Maps/india-outline.geojson'
LGD = ROOT / 'public/district_lgd_codes.json'
IND_DIR = ROOT / 'public/indicators/digital_transactions'
FIELD = 'transaction_count'

RAMP = ['#F4E1D6', '#EDC9B2', '#E0A88E', '#CC7A56', '#B84A2E', '#8E331E']
NO_DATA = '#E8E4DC'
BOX_W, BOX_H = 480, 480
LON0, LON1, LAT0, LAT1 = 67.5, 98.0, 6.5, 37.5
KX = math.cos(math.radians(22))


def norm(s):
    return re.sub(r'[^a-z]', '', (s or '').lower())


def project():
    w = (LON1 - LON0) * KX
    h = LAT1 - LAT0
    s = min(BOX_W / w, BOX_H / h)
    ox = (BOX_W - w * s) / 2
    oy = (BOX_H - h * s) / 2
    return lambda lon, lat: (ox + (lon - LON0) * KX * s, oy + (LAT1 - lat) * s)


def ring_path(ring, proj, min_step=0.6):
    pts, last = [], None
    for lon, lat in ring:
        x, y = proj(lon, lat)
        if last and abs(x - last[0]) < min_step and abs(y - last[1]) < min_step:
            continue
        pts.append((x, y))
        last = (x, y)
    if len(pts) < 3:
        return ''
    return 'M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in pts) + 'Z'


def geom_path(geom, proj):
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    return ''.join(ring_path(r, proj) for poly in polys for r in poly)


def compute_breaks(values):
    v = sorted(values)
    return [v[min(int(p * len(v)), len(v) - 1)] for p in (0.2, 0.4, 0.6, 0.8, 0.95)]


def get_color(val, breaks):
    if val is None:
        return NO_DATA
    for i in range(len(breaks) - 1, -1, -1):
        if val >= breaks[i]:
            return RAMP[min(i + 1, len(RAMP) - 1)]
    return RAMP[0]


def load_values():
    quarter_file = sorted(IND_DIR.glob('[0-9][0-9][0-9][0-9]-[0-9][0-9].json'))[-1]
    data = json.loads(quarter_file.read_text())

    # (state slug, district name/alias) → LGD code, via the site's own lookup.
    lgd = json.loads(LGD.read_text())['districts']
    state_lgd = {norm(d['state']): d['state_lgd_code'] for d in lgd}
    by_name = {}
    for d in lgd:
        for name in [d['district'], *d.get('aliases', [])]:
            by_name[(d['state_lgd_code'], norm(name))] = d['lgd_code']

    values, misses = {}, 0
    for rec in data['districts']:
        st = state_lgd.get(norm(rec['state']))
        code = by_name.get((st, norm(rec['district'])))
        try:
            val = float(rec.get(FIELD))
        except (TypeError, ValueError):
            continue
        if code is None:
            misses += 1
            continue
        values[code] = values.get(code, 0) + val
    return data, values, misses


def build_map():
    data, values, misses = load_values()
    breaks = compute_breaks(list(values.values()))
    proj = project()
    geo = json.loads(GEO.read_text())

    painted, paths = 0, []
    for f in geo['features']:
        if not f.get('geometry'):
            continue
        try:
            val = values.get(int(f['properties'].get('DIST_LGD')))
        except (TypeError, ValueError):
            val = None
        painted += val is not None
        d = geom_path(f['geometry'], proj)
        if d:
            paths.append(f'<path d="{d}" fill="{get_color(val, breaks)}"/>')

    outline = json.loads(OUTLINE.read_text())
    outline_d = ''.join(geom_path(f['geometry'], proj) for f in outline['features'] if f.get('geometry'))

    svg = (
        f'<svg viewBox="0 0 {BOX_W} {BOX_H}" xmlns="http://www.w3.org/2000/svg">'
        f'<g stroke="#F4EFE6" stroke-width="0.35" stroke-linejoin="round">{"".join(paths)}</g>'
        f'<path d="{outline_d}" fill="none" stroke="#1B140E" stroke-opacity="0.35" stroke-width="0.6" stroke-linejoin="round"/>'
        '</svg>'
    )
    caption = f'UPI transactions by district · {data["label"]} · PhonePe Pulse'
    print(f'  {len(values)} districts joined ({misses} unmatched records), '
          f'{painted}/{len(geo["features"])} polygons painted')
    return svg, caption


def main():
    svg, caption = build_map()
    html = TEMPLATE.read_text().replace('{{MAP}}', svg).replace('{{CAPTION}}', caption)
    with tempfile.TemporaryDirectory() as tmp:
        page_path = Path(tmp) / 'og.html'
        page_path.write_text(html)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome')
            page = browser.new_page(viewport={'width': 1200, 'height': 630})
            page.goto(page_path.as_uri(), wait_until='networkidle')
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(PNG), type='png')
            browser.close()
    print(f'  wrote {PNG.relative_to(ROOT)} ({PNG.stat().st_size // 1024} KB)')


if __name__ == '__main__':
    main()
