#!/usr/bin/env python3
"""Audit district name mappings between SLBC data and GeoJSON for Project FINER."""

import json
import os

GEOJSON_PATH = "public/data/district_boundaries.geojson"
SLBC_BASE = "public/slbc-data"

# Mapping from directory slug to GeoJSON STATE_UT value
STATE_SLUG_TO_GEOJSON = {
    "assam": "ASSAM",
    "meghalaya": "MEGHALAYA",
    "manipur": "MANIPUR",
    "arunachal-pradesh": "ARUNACHAL PRADESH",
    "mizoram": "MIZORAM",
    "tripura": "TRIPURA",
    "nagaland": "NAGALAND",
    "sikkim": "SIKKIM",
    "bihar": "BIHAR",
    "west-bengal": "WEST BENGAL",
}

# Existing DISTRICT_ALIASES from src/pages/index.astro
# Direction: GeoJSON name -> SLBC name (used to look up SLBC data for a GeoJSON district)
DISTRICT_ALIASES = {
    "PAPUMPARE": "PAPUM PARE",
    "KEYI PANYOR": "CAPITAL COMPLEX",
    "DARANG": "DARRANG",
    "MARIGAON": "MORIGAON",
    "SIBSAGAR": "SIVASAGAR",
    "SRIBHUMI": "KARIMGANJ",
    "WEST KARBI ANAGLONG": "WEST KARBI ANGLONG",
    "KAMJANG": "KAMJONG",
    "RIBHOI": "RI BHOI",
    "GOMTI": "GOMATI",
    "PURBA CHAMPARAN": "PURBI CHAMPARAN",
    "KAIMUR (BHABUA)": "KAIMUR",
    "PASHCHIM CHAMPARAN": "PASHCHIMI CHAMPARAN",
    "SARAIKELA-KHARSAWAN": "SERAIKELA-KHARSAWAN",
    "ANUGUL": "ANGUL",
    "DAKSHIN BASTAR DANTEWARA": "DANTEWADA",
    "UTTAR BASTAR KANKER": "KANKER",
    "KAWARDHA (KABIRDHAM)": "KABIRDHAM",
    "GARIYABAND": "GARIABAND",
    "JANJGIR - CHAMPA": "JANJGIR-CHAMPA",
    "KHAIRGARH-CHHUIKHADAN-GANDAI": "KHAIRAGARH-CHHUIKHADAN-GANDAI",
    "JAJAPUR": "JAJPUR",
    "KEONJHAR (KENDUJHAR)": "KEONJHAR",
    "NABARANGAPUR": "NABARANGPUR",
    "NUAPARHA": "NUAPADA",
    "RAYAGARHA": "RAYAGADA",
    "ALIPUR DUAR": "ALIPURDUAR",
    "BIRBHAM": "BIRBHUM",
    "DARJILING": "DARJEELING",
    "HAORA": "HOWRAH",
    "HUGLI": "HOOGHLY",
    "KOCH BIHAR": "COOCH BEHAR",
    "MALDAH": "MALDA",
    "NORTH TWENTY-FOUR PARGANAS": "NORTH 24 PARGANAS",
    "PASCHIM BARDDHAMAN": "PASCHIM BARDHAMAN",
    "PURBA BARDDHAMAN": "PURBA BARDHAMAN",
    "PURULIYA": "PURULIA",
    "SOUTH 24PARGANAS": "SOUTH 24 PARGANAS",
}

# Reverse alias map: GeoJSON name -> SLBC name(s)
ALIAS_REVERSE = {}
for slbc_name, geo_name in DISTRICT_ALIASES.items():
    ALIAS_REVERSE.setdefault(geo_name, []).append(slbc_name)


def load_geojson_districts(geojson_path):
    """Return dict: STATE_UT -> set of uppercase district names."""
    with open(geojson_path) as f:
        gj = json.load(f)
    state_districts = {}
    for feat in gj["features"]:
        props = feat["properties"]
        state = (props.get("STATE_UT") or "").strip().upper()
        district = (props.get("DISTRICT") or "").strip().upper()
        if state and district:
            state_districts.setdefault(state, set()).add(district)
    return state_districts


def load_slbc_districts(slbc_path):
    """Return set of unique district names (original case) from a _complete.json file."""
    with open(slbc_path) as f:
        data = json.load(f)
    districts = set()
    quarters = data.get("quarters", {})
    for qtr_key, qtr_val in quarters.items():
        tables = qtr_val.get("tables", {})
        for cat_key, cat_val in tables.items():
            dist_data = cat_val.get("districts", {})
            for dist_name in dist_data.keys():
                districts.add(dist_name)
    return districts


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    geojson_path = os.path.join(base, GEOJSON_PATH)
    slbc_base = os.path.join(base, SLBC_BASE)

    geo_districts = load_geojson_districts(geojson_path)

    print("=" * 80)
    print("DISTRICT AUDIT: SLBC vs GeoJSON")
    print("=" * 80)

    total_in_slbc_not_geo = 0
    total_in_geo_not_slbc = 0
    total_uncovered = 0

    for slug, geo_state in sorted(STATE_SLUG_TO_GEOJSON.items()):
        slbc_file = os.path.join(slbc_base, slug, f"{slug}_complete.json")
        if not os.path.exists(slbc_file):
            print(f"\n--- {slug} ---")
            print(f"  WARNING: {slbc_file} not found, skipping.")
            continue

        geo_set = geo_districts.get(geo_state, set())
        slbc_raw = load_slbc_districts(slbc_file)
        slbc_upper = {d.strip().upper() for d in slbc_raw}

        # DISTRICT_ALIASES direction: GeoJSON name -> SLBC name
        # Build reverse: SLBC name -> GeoJSON name for this analysis
        slbc_to_geo = {v: k for k, v in DISTRICT_ALIASES.items()}

        # For each GeoJSON district, it can be matched if:
        #   - its name is in slbc_upper directly, OR
        #   - it has an alias and that alias target is in slbc_upper
        geo_matched = set()
        for gname in geo_set:
            if gname in slbc_upper:
                geo_matched.add(gname)
            elif gname in DISTRICT_ALIASES and DISTRICT_ALIASES[gname] in slbc_upper:
                geo_matched.add(gname)

        # SLBC districts matched: direct match or via reverse alias
        slbc_matched = set()
        for sname in slbc_upper:
            if sname in geo_set:
                slbc_matched.add(sname)
            elif sname in slbc_to_geo and slbc_to_geo[sname] in geo_set:
                slbc_matched.add(sname)

        in_slbc_not_geo = slbc_upper - geo_set  # raw name not in GeoJSON
        in_geo_not_slbc = geo_set - slbc_upper   # raw name not in SLBC

        # Check which SLBC mismatches are covered by existing aliases
        covered_by_alias = set()
        not_covered = set()
        for name in in_slbc_not_geo:
            if name in slbc_to_geo and slbc_to_geo[name] in geo_set:
                covered_by_alias.add(name)
            else:
                not_covered.add(name)

        # GeoJSON districts with no SLBC data even after alias resolution
        geo_missing_data = geo_set - geo_matched

        total_in_slbc_not_geo += len(in_slbc_not_geo)
        total_in_geo_not_slbc += len(geo_missing_data)
        total_uncovered += len(not_covered)

        print(f"\n{'=' * 80}")
        print(f"  {geo_state} (slug: {slug})")
        print(f"  GeoJSON districts: {len(geo_set)}  |  SLBC districts: {len(slbc_upper)}")
        print(f"{'=' * 80}")

        if in_slbc_not_geo:
            print(f"\n  [A] In SLBC but NOT in GeoJSON ({len(in_slbc_not_geo)}):")
            for name in sorted(in_slbc_not_geo):
                geo_alias = slbc_to_geo.get(name)
                if geo_alias and geo_alias in geo_set:
                    print(f"      {name}  -> ALIAS '{geo_alias}': '{name}' (COVERED)")
                else:
                    print(f"      {name}  ** NEEDS ALIAS **")
        else:
            print(f"\n  [A] In SLBC but NOT in GeoJSON: NONE")

        if geo_missing_data:
            print(f"\n  [B] In GeoJSON but NOT in SLBC (after aliases) ({len(geo_missing_data)}):")
            for name in sorted(geo_missing_data):
                print(f"      {name}")
        else:
            print(f"\n  [B] In GeoJSON but NOT in SLBC: NONE")

        if not_covered:
            print(f"\n  [C] UNCOVERED mismatches (need new aliases): {len(not_covered)}")
            for name in sorted(not_covered):
                print(f"      {name}")
        else:
            print(f"\n  [C] All SLBC->GeoJSON mismatches are covered by existing aliases.")

    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"  Total SLBC names not in GeoJSON:          {total_in_slbc_not_geo}")
    print(f"  Total GeoJSON districts missing SLBC data: {total_in_geo_not_slbc}")
    print(f"  Total UNCOVERED mismatches (need aliases): {total_uncovered}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
