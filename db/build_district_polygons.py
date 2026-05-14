#!/usr/bin/env python3
"""
Inject a simplified SVG path for every district's polygon into its
public/districts/<state>/<district>.json file.

Reads public/data/district_boundaries.geojson, matches each feature to a
(state, district) pair from public/districts/index.json, simplifies the
polygon (Douglas-Peucker, ~0.005°), projects to a fixed viewBox, and
embeds the path inline as `polygon.path` + `polygon.viewBox`.

The DistrictPage.svelte component renders this as a static SVG sticker
in the page hero — no client-side mapping library, no runtime fetch,
zero JS cost. Path strings are <3 KB typical.

Run AFTER db/build_district_pages.py (the index needs to exist):
  python3 db/build_district_pages.py
  python3 db/build_district_polygons.py
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

ROOT = Path(__file__).resolve().parent.parent
GEOJSON = ROOT / 'public/data/district_boundaries.geojson'
DISTRICTS_DIR = ROOT / 'public/districts'

VIEW_W = 1000
VIEW_H = 620
PAD = 24                # px of padding inside the viewBox
SIMPLIFY_TOLERANCE = 0.004   # degrees ≈ 400m at India latitudes

# Source GeoJSON uses uppercase human state names. Map to our slugs so
# (state_slug, district_slug) matches both sides cleanly.
STATE_UT_TO_SLUG = {
    'ANDHRA PRADESH':     'andhra-pradesh',
    'ARUNACHAL PRADESH':  'arunachal-pradesh',
    'ASSAM':              'assam',
    'BIHAR':              'bihar',
    'CHHATTISGARH':       'chhattisgarh',
    'DELHI':              'delhi',
    'GOA':                'goa',
    'GUJARAT':            'gujarat',
    'HARYANA':            'haryana',
    'HIMACHAL PRADESH':   'himachal-pradesh',
    'JAMMU AND KASHMIR':  'jammu-kashmir',
    'JHARKHAND':          'jharkhand',
    'KARNATAKA':          'karnataka',
    'KERALA':             'kerala',
    'LADAKH':             'ladakh',
    'MADHYA PRADESH':     'madhya-pradesh',
    'MAHARASHTRA':        'maharashtra',
    'MANIPUR':            'manipur',
    'MEGHALAYA':          'meghalaya',
    'MIZORAM':            'mizoram',
    'NAGALAND':           'nagaland',
    'ODISHA':             'odisha',
    'PUNJAB':             'punjab',
    'RAJASTHAN':          'rajasthan',
    'SIKKIM':             'sikkim',
    'TAMIL NADU':         'tamil-nadu',
    'TELANGANA':          'telangana',
    'TRIPURA':            'tripura',
    'UTTAR PRADESH':      'uttar-pradesh',
    'UTTARAKHAND':        'uttarakhand',
    'WEST BENGAL':        'west-bengal',
    'ANDAMAN AND NICOBAR ISLANDS':         'andaman-nicobar',
    'CHANDIGARH':                          'chandigarh',
    'DADRA & NAGAR HAVELI & DAMAN & DIU':  'dadra-nagar-haveli',
    'LAKSHADWEEP':                         'lakshadweep',
    'PUDUCHERRY':                          'puducherry',
}


def slugify(s: str) -> str:
    s = (s or '').lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s


# Manual aliases for SLBC-side names that don't slugify-match the GeoJSON.
# Key = (state_slug, our_district_slug); value = GeoJSON DISTRICT slugified.
# Only the misses found by the run-and-log pass are added here.
DISTRICT_ALIASES: dict[tuple[str, str], str] = {
    # West Bengal — GeoJSON spelling differs from SLBC
    ('west-bengal', 'paraganas-south'): 'south-twenty-four-parganas',
    ('west-bengal', 'north-24-parganas'): 'north-twenty-four-parganas',
    ('west-bengal', 'south-24-parganas'): 'south-twenty-four-parganas',
    ('west-bengal', 'cooch-behar'): 'koch-bihar',
    ('west-bengal', 'coochbehar'): 'koch-bihar',
    ('west-bengal', 'hooghly'): 'hugli',
    ('west-bengal', 'howrah'): 'haora',
    ('west-bengal', 'malda'): 'maldah',
    ('west-bengal', 'birbhum'): 'birbham',
    ('west-bengal', 'darjeeling'): 'darjiling',
    ('west-bengal', 'purulia'): 'puruliya',
    ('west-bengal', 'paschim-bardhaman'): 'paschim-barddhaman',
    ('west-bengal', 'purba-bardhaman'): 'purba-barddhaman',
    ('west-bengal', 'alipurduar'): 'alipur-duar',
    # Chhattisgarh
    ('chhattisgarh', 'dantewada'): 'dakshin-bastar-dantewara',
    ('chhattisgarh', 'kanker'): 'uttar-bastar-kanker',
    ('chhattisgarh', 'kabirdham'): 'kawardha-kabirdham',
    ('chhattisgarh', 'gariaband'): 'gariyaband',
    ('chhattisgarh', 'janjgirchampa'): 'janjgir-champa',
    ('chhattisgarh', 'sarangarh-bilaigarh'): 'sarangarhbilaigarh',
    ('chhattisgarh', 'khairagarh-chhuikhadan-gandai'): 'khairgarh-chhuikhadan-gandai',
    # Odisha
    ('odisha', 'angul'): 'anugul',
    ('odisha', 'baleshwar'): 'balasore',
    ('odisha', 'sonepur'): 'subarnapur',
    ('odisha', 'jagatsinghapur'): 'jagatsinghpur',
    ('odisha', 'jajpur'): 'jajapur',
    ('odisha', 'keonjhar'): 'kendujhar',
    ('odisha', 'nabarangpur'): 'nabarangapur',
    ('odisha', 'nuapada'): 'nuaparha',
    ('odisha', 'rayagada'): 'rayagarha',
    # Bihar
    ('bihar', 'purbi-champaran'): 'purba-champaran',
    ('bihar', 'kaimur'): 'kaimur-bhabua',
    ('bihar', 'pashchimi-champaran'): 'pashchim-champaran',
    # Karnataka
    ('karnataka', 'bagalkote'): 'bagalkot',
    ('karnataka', 'belgaum'): 'belagavi',
    # Assam
    ('assam', 'morigaon'): 'marigaon',
    ('assam', 'sivasagar'): 'sibsagar',
    ('assam', 'karimganj'): 'sribhumi',
    ('assam', 'kamrup'): 'kamrup-rural',
    ('assam', 'darrang'): 'darang',
    ('assam', 'west-karbi-anglong'): 'west-karbi-anaglong',
    # Manipur
    ('manipur', 'kamjong'): 'kamjang',
    # Gujarat
    ('gujarat', 'ahmedabad'): 'ahmadabad',
    ('gujarat', 'aravalli'): 'arvalli',
    ('gujarat', 'banaskantha'): 'banas-kantha',
    ('gujarat', 'chhota-udepur'): 'chhotaudepur',
    ('gujarat', 'dang'): 'dangs',
    ('gujarat', 'dohad'): 'dahod',
    ('gujarat', 'kutch'): 'kachchh',
    ('gujarat', 'mehsana'): 'mahesana',
    ('gujarat', 'panchmahal'): 'panch-mahals',
    ('gujarat', 'panchmahals'): 'panch-mahals',
    ('gujarat', 'sabarkantha'): 'sabar-kantha',
    # Andhra Pradesh — naming differs significantly
    ('andhra-pradesh', 'alluri-sitharama-raju'): 'alluri-sitarama-raju',
    ('andhra-pradesh', 'anantapur'): 'ananthapuramu',
    ('andhra-pradesh', 'konaseema'): 'dr-b-r-ambedkar-konaseema',
    ('andhra-pradesh', 'spsr-nellore'): 'sri-potti-sriramulu-nellore',
    ('andhra-pradesh', 'visakhapatanam'): 'visakhapatnam',
    ('andhra-pradesh', 'ysr'): 'y-s-r',
    # Arunachal Pradesh
    ('arunachal-pradesh', 'leparada'): 'lepa-rada',
    ('arunachal-pradesh', 'papum-pare'): 'papumpare',
    ('arunachal-pradesh', 'capital-complex'): 'keyi-panyor',
    # Meghalaya
    ('meghalaya', 'ri-bhoi'): 'ribhoi',
    # Tripura
    ('tripura', 'gomati'): 'gomti',
    # Jharkhand
    ('jharkhand', 'seraikela-kharsawan'): 'saraikela-kharsawan',
    ('jharkhand', 'east-singhbum'): 'east-singhbhum',
    ('jharkhand', 'sahebganj'): 'sahibganj',
    # Jammu & Kashmir — GeoJSON uses older transliterations
    ('jammu-kashmir', 'bandipora'): 'bandipura',
    ('jammu-kashmir', 'bandipore'): 'bandipura',
    ('jammu-kashmir', 'baramulla'): 'baramula',
    ('jammu-kashmir', 'budgam'): 'badgam',
    ('jammu-kashmir', 'poonch'): 'punch',
    ('jammu-kashmir', 'rajouri'): 'rajauri',
    ('jammu-kashmir', 'reasi'): 'riasi',
    ('jammu-kashmir', 'shopian'): 'shupiyan',
    # Haryana
    ('haryana', 'charkhi-dadri'): 'charki-dadri',
    ('haryana', 'mewat'): 'nuh',
    # Himachal Pradesh
    ('himachal-pradesh', 'lahaul-and-spiti'): 'lahul-spiti',
    ('himachal-pradesh', 'lahul-and-spiti'): 'lahul-spiti',
    # Karnataka — GeoJSON uses post-2014 Kannada transliterations
    ('karnataka', 'chamarajanagar'): 'chamarajanagara',
    ('karnataka', 'davangere'): 'davanagere',
    ('karnataka', 'bangalore-rural'): 'bengaluru-rural',
    ('karnataka', 'bangalore-urban'): 'bengaluru-urban',
    ('karnataka', 'bengaluru-rural'): 'bengaluru-rural',
    ('karnataka', 'bengaluru-urban'): 'bengaluru-urban',
    ('karnataka', 'bellary'): 'ballari',
    ('karnataka', 'bijapur'): 'vijayapura',
    ('karnataka', 'chickballapur'): 'chikkaballapura',
    ('karnataka', 'chikkamagalur'): 'chikkamagaluru',
    ('karnataka', 'gulbarga'): 'kalaburagi',
    ('karnataka', 'kolar'): 'kolara',
    ('karnataka', 'mysore'): 'mysuru',
    ('karnataka', 'shimoga'): 'shivamogga',
    ('karnataka', 'tumkur'): 'tumakuru',
    # Kerala
    ('kerala', 'kasargod'): 'kasaragod',
    ('kerala', 'trivandrum'): 'thiruvananthapuram',
    # Madhya Pradesh
    ('madhya-pradesh', 'east-nimar'): 'khandwa',
    ('madhya-pradesh', 'hoshangabad'): 'narmadapuram',
    ('madhya-pradesh', 'narsinghpur'): 'narsimhapur',
    # Maharashtra (post-2023 renames; SLBC uses old names still)
    ('maharashtra', 'ahmednagar'): 'ahilyanagar',
    ('maharashtra', 'aurangabad'): 'chhatrapati-sambhaji-nagar',
    ('maharashtra', 'chhatrapati-sambhajinagar'): 'chhatrapati-sambhaji-nagar',
    ('maharashtra', 'osmanabad'): 'dharashiv',
    ('bihar', 'chhatrapati-sambhajinagar'): 'chhatrapati-sambhaji-nagar',
    # Meghalaya (already aliased above, but slug variations seen in data)
    ('meghalaya', 'ribhoi'): 'ri-bhoi',
    # Odisha
    ('odisha', 'kendujhar'): 'keonjhar-kendujhar',
    ('odisha', 'keonjhar'): 'keonjhar-kendujhar',
    # Puducherry
    ('puducherry', 'pondicherry'): 'puducherry',
    # Punjab — GeoJSON has FIROZPUR + SAS NAGAR (SAHIBZADA AJIT SINGH NAGAR)
    ('punjab', 'ferozepur'): 'firozpur',
    ('punjab', 'firozepur'): 'firozpur',
    ('punjab', 's-a-s-nagar'): 'sas-nagar-sahibzada-ajit-singh-nagar',
    ('punjab', 'sas-nagar'): 'sas-nagar-sahibzada-ajit-singh-nagar',
    ('punjab', 'malerkotla'): 'maler-kotla',
    # Rajasthan
    ('rajasthan', 'chittorgarh'): 'chittaurgarh',
    ('rajasthan', 'dholpur'): 'dhaulpur',
    ('rajasthan', 'jalore'): 'jalor',
    ('rajasthan', 'jhunjhunu'): 'jhunjhunun',
    # Sikkim (post-2021 rename: East→Pakyong, North→Mangan, South→Namchi, West→Gyalshing)
    ('sikkim', 'east-sikkim'): 'pakyong',
    ('sikkim', 'north-sikkim'): 'mangan',
    ('sikkim', 'south-sikkim'): 'namchi',
    ('sikkim', 'west-sikkim'): 'gyalshing',
    # Tamil Nadu
    ('tamil-nadu', 'kallakkurichi'): 'kallakurichi',
    ('tamil-nadu', 'kanchipuram'): 'kancheepuram',
    ('tamil-nadu', 'thiruvallur'): 'tiruvallur',
    ('tamil-nadu', 'tirupattur'): 'tirupathur',
    ('tamil-nadu', 'tuticorin'): 'thoothukudi',
    ('tamil-nadu', 'villupuram'): 'viluppuram',
    # Telangana
    ('telangana', 'jagitial'): 'jagtial',
    ('telangana', 'jangoan'): 'jangaon',
    ('telangana', 'jayashankar-bhupalapally'): 'jayashankar-bhupalpalli',
    ('telangana', 'kumuram-bheem-asifabad'): 'kumuram-bheem',
    ('telangana', 'mahabubnagar'): 'mahbubnagar',
    ('telangana', 'rangareddy'): 'ranga-reddy',
    # Uttar Pradesh
    ('uttar-pradesh', 'barabanki'): 'bara-banki',
    ('uttar-pradesh', 'kushi-nagar'): 'kushinagar',
    ('uttar-pradesh', 'maharajganj'): 'mahrajganj',
    ('uttar-pradesh', 'sant-kabeer-nagar'): 'sant-kabir-nagar',
    ('uttar-pradesh', 'shravasti'): 'shrawasti',
    ('uttar-pradesh', 'siddharth-nagar'): 'siddharthnagar',
    # Uttarakhand
    ('uttarakhand', 'dehradun'): 'dehradan',
    ('uttarakhand', 'hardwar'): 'haridwar',
    ('uttarakhand', 'pauri'): 'pauri-garhwal',
    ('uttarakhand', 'rudra-prayag'): 'rudraprayag',
    ('uttarakhand', 'tehri'): 'tehri-garhwal',
    ('uttarakhand', 'udam-singh-nagar'): 'udham-singh-nagar',
    ('uttarakhand', 'usnagar'): 'udham-singh-nagar',
    ('uttarakhand', 'uttar-kashi'): 'uttarkashi',
    # West Bengal — additional slug variants
    ('west-bengal', '24-paraganas-north'): 'north-twenty-four-parganas',
    ('west-bengal', '24-paraganas-south'): 'south-24parganas',
    ('west-bengal', 'south-24-parganas'): 'south-24parganas',
    ('west-bengal', 'dinajpur-dakshin'): 'dakshin-dinajpur',
    ('west-bengal', 'dinajpur-uttar'): 'uttar-dinajpur',
    ('west-bengal', 'medinipur-east'): 'purba-medinipur',
    ('west-bengal', 'medinipur-west'): 'paschim-medinipur',
    # Andaman & Nicobar
    ('andaman-nicobar', 'south-andaman'): 'south-andamans',
    ('andaman-nicobar', 'nicobar'): 'nicobars',
    # Ladakh
    ('ladakh', 'leh-ladakh'): 'leh',
}


def build_geojson_lookup() -> dict[tuple[str, str], BaseGeometry]:
    """(state_slug, district_slug) -> shapely geometry."""
    d = json.loads(GEOJSON.read_text())
    out: dict[tuple[str, str], BaseGeometry] = {}
    skipped_states = 0
    for f in d['features']:
        props = f.get('properties') or {}
        state_raw = props.get('STATE_UT')
        if not state_raw:
            skipped_states += 1
            continue
        state_slug = STATE_UT_TO_SLUG.get(state_raw)
        if not state_slug:
            continue
        dist_raw = props.get('DISTRICT')
        if not dist_raw:
            continue
        dist_slug = slugify(dist_raw)
        out[(state_slug, dist_slug)] = shape(f['geometry'])
    if skipped_states:
        print(f'  (skipped {skipped_states} features with null STATE_UT)')
    return out


def project_path(geom: BaseGeometry, view_w: int = VIEW_W,
                 view_h: int = VIEW_H, pad: int = PAD) -> str:
    """Project lon/lat → SVG path string filling a viewBox.

    Per-district projection: each polygon is centered + scaled to fit its own
    viewBox. Aspect ratio of the polygon's bounding box is preserved by
    fitting the larger dimension to (view - 2*pad) and centring on the other
    axis.
    """
    minx, miny, maxx, maxy = geom.bounds
    bw = max(1e-9, maxx - minx)
    bh = max(1e-9, maxy - miny)
    avail_w = view_w - 2 * pad
    avail_h = view_h - 2 * pad
    scale = min(avail_w / bw, avail_h / bh)
    used_w = bw * scale
    used_h = bh * scale
    off_x = pad + (avail_w - used_w) / 2
    off_y = pad + (avail_h - used_h) / 2

    def xform(x: float, y: float) -> tuple[float, float]:
        # SVG y is inverted relative to geographic y (north is up = lower y in SVG).
        sx = off_x + (x - minx) * scale
        sy = off_y + (maxy - y) * scale
        return sx, sy

    polys = list(geom.geoms) if hasattr(geom, 'geoms') else [geom]
    chunks: list[str] = []
    for p in polys:
        if not hasattr(p, 'exterior'):
            continue
        # Exterior ring
        coords = list(p.exterior.coords)
        if not coords:
            continue
        first = xform(coords[0][0], coords[0][1])
        parts = [f'M{first[0]:.1f},{first[1]:.1f}']
        for c in coords[1:]:
            x, y = xform(c[0], c[1])
            parts.append(f'L{x:.1f},{y:.1f}')
        parts.append('Z')
        chunks.append(''.join(parts))
        # Interior rings (holes)
        for hole in p.interiors:
            hc = list(hole.coords)
            if not hc:
                continue
            first = xform(hc[0][0], hc[0][1])
            hparts = [f'M{first[0]:.1f},{first[1]:.1f}']
            for c in hc[1:]:
                x, y = xform(c[0], c[1])
                hparts.append(f'L{x:.1f},{y:.1f}')
            hparts.append('Z')
            chunks.append(''.join(hparts))
    return ''.join(chunks)


def main():
    if not GEOJSON.exists():
        print(f'ERROR: {GEOJSON} missing', file=sys.stderr)
        sys.exit(1)
    index_path = DISTRICTS_DIR / 'index.json'
    if not index_path.exists():
        print(f'ERROR: {index_path} missing — run db/build_district_pages.py first', file=sys.stderr)
        sys.exit(1)

    print(f'loading {GEOJSON.relative_to(ROOT)}…')
    lookup = build_geojson_lookup()
    print(f'  {len(lookup)} (state, district) features indexed')

    index = json.loads(index_path.read_text())
    rows = index['districts']

    matched = 0
    missed: list[tuple[str, str]] = []
    for row in rows:
        state = row['state']
        dslug = row['districtSlug']
        geom = lookup.get((state, dslug))
        if geom is None:
            alias = DISTRICT_ALIASES.get((state, dslug))
            if alias:
                geom = lookup.get((state, alias))
        if geom is None:
            # Try a loose fallback: ignore any -1/-2 numeric suffix from
            # post-2020 carved districts that haven't reached our boundary
            # GeoJSON yet.
            base = re.sub(r'-\d+$', '', dslug)
            if base != dslug:
                geom = lookup.get((state, base))
        if geom is None:
            missed.append((state, dslug))
            continue

        simp = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        path = project_path(simp)
        if not path:
            missed.append((state, dslug))
            continue

        json_path = DISTRICTS_DIR / state / f'{dslug}.json'
        if not json_path.exists():
            continue
        payload = json.loads(json_path.read_text())
        payload['polygon'] = {
            'path': path,
            'viewBox': f'0 0 {VIEW_W} {VIEW_H}',
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
        matched += 1

    print(f'matched {matched}/{len(rows)}; missed {len(missed)}')
    if missed:
        print(f'all {len(missed)} misses (state, district):')
        for s, d in missed:
            print(f'  {s:20} {d}')


if __name__ == '__main__':
    main()
