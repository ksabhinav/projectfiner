#!/usr/bin/env python3
"""
Shrink public/data/district_boundaries.geojson for the homepage first load.

The homepage fetches this file unconditionally before the map paints, so its
size is the dominant first-load cost. The source ships 3D coordinates
([lng, lat, 0.0] — Leaflet ignores the z) at 6-decimal precision (~11 cm),
absurd for a national/state-zoom choropleth. This:

  1. drops the z coordinate (3D -> 2D)
  2. Douglas-Peucker simplifies each feature (preserve_topology=True)
  3. rounds coordinates to 5 decimals (~1.1 m)

All properties are preserved (the cap_* counts feed capital-markets
regeneration and cost almost nothing) and all features are kept — including
the 28 null-STATE_UT stubs, which still carry real geometry and would leave
holes in the map if dropped.

Idempotent: re-running on an already-simplified file barely changes it.

    python3 scripts/simplify_district_boundaries.py [--tolerance 0.001]
"""
import argparse
import json
import os
from pathlib import Path

from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parent.parent
GEOJSON = ROOT / "public/data/district_boundaries.geojson"
DECIMALS = 4


def count_points(coords):
    n = 0
    def walk(x):
        nonlocal n
        if isinstance(x, (list, tuple)) and x and isinstance(x[0], (int, float)):
            n += 1
        elif isinstance(x, (list, tuple)):
            for y in x:
                walk(y)
    walk(coords)
    return n


def round_coords(x):
    if isinstance(x, (list, tuple)) and x and isinstance(x[0], (int, float)):
        # a coordinate pair (drop any z already handled upstream)
        return [round(x[0], DECIMALS), round(x[1], DECIMALS)]
    return [round_coords(y) for y in x]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolerance", type=float, default=0.001,
                    help="Douglas-Peucker tolerance in degrees (default 0.001 ~ 111 m)")
    args = ap.parse_args()

    before_bytes = GEOJSON.stat().st_size
    g = json.loads(GEOJSON.read_text())

    pts_before = pts_after = 0
    simplified = failed = repaired = 0
    for f in g["features"]:
        geom = f.get("geometry")
        if not geom or not geom.get("coordinates"):
            continue
        pts_before += count_points(geom["coordinates"])
        try:
            s = shape(geom)
            s2 = s.simplify(args.tolerance, preserve_topology=True)
            if s2.is_empty:
                s2 = s              # keep the original rather than lose a district
                failed += 1
            else:
                simplified += 1
            # Round FIRST, then validate: snapping vertices to 4 decimals can
            # re-introduce self-intersections on intricate coastlines (Andaman,
            # coastal Gujarat/Karnataka), so the validity check must see the
            # rounded geometry, not the pre-rounded one.
            rounded = shape({"type": s2.geom_type,
                             "coordinates": round_coords(mapping(s2)["coordinates"])})
            if not rounded.is_valid:
                rounded = make_valid(rounded)
                repaired += 1
            # make_valid can emit GeometryCollections; keep only (Multi)Polygon parts.
            if rounded.geom_type == "GeometryCollection":
                polys = [g2 for g2 in rounded.geoms
                         if g2.geom_type in ("Polygon", "MultiPolygon")]
                rounded = unary_union(polys) if polys else s2
            m = mapping(rounded)
            f["geometry"] = {"type": m["type"], "coordinates": m["coordinates"]}
        except Exception as e:
            print(f"  WARN: {f['properties'].get('DISTRICT')}: {e}")
            f["geometry"] = {"type": geom["type"],
                             "coordinates": round_coords(geom["coordinates"])}
            failed += 1
        pts_after += count_points(f["geometry"]["coordinates"])

    # Compact separators — every byte counts on the first-load path.
    GEOJSON.write_text(json.dumps(g, separators=(",", ":")))
    after_bytes = GEOJSON.stat().st_size

    print(f"features: {len(g['features'])} ({simplified} simplified, "
          f"{repaired} repaired, {failed} kept as-is)")
    print(f"points:   {pts_before:,} -> {pts_after:,} ({pts_after/pts_before:.0%})")
    print(f"size:     {before_bytes/1e6:.1f} MB -> {after_bytes/1e6:.2f} MB "
          f"({after_bytes/before_bytes:.0%})")


if __name__ == "__main__":
    main()
