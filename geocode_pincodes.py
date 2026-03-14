"""
geocode_pincodes.py
-------------------
Reads unique_pincodes.json, geocodes each via Nominatim (OSM),
and writes pincode_coords.json.

Run once locally:
    pip install requests
    python geocode_pincodes.py

Then upload pincode_coords.json to your projectfiner GitHub repo.

Rate: ~1 req/sec (Nominatim ToS). ~5006 pins ≈ 90 minutes.
Progress is saved incrementally — safe to interrupt and resume.
"""

import json, time, os, requests

INPUT_FILE  = "unique_pincodes.json"
OUTPUT_FILE = "pincode_coords.json"
USER_AGENT  = "ProjectFINER/1.0 (abhinav@projectfiner.com)"  # update your email

# Load pincodes
with open(INPUT_FILE) as f:
    pincodes = json.load(f)

# Load existing progress if resuming
if os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE) as f:
        coords = json.load(f)
    print(f"Resuming — {len(coords)} already geocoded, {len(pincodes)-len(coords)} remaining.")
else:
    coords = {}

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

todo = [p for p in pincodes if p not in coords]
total = len(pincodes)

for i, pin in enumerate(todo, start=len(coords) + 1):
    try:
        resp = session.get(
            "https://nominatim.openstreetmap.org/search",
            params={"postalcode": pin, "country": "IN", "format": "json", "limit": 1},
            timeout=10
        )
        results = resp.json()
        if results:
            coords[pin] = [round(float(results[0]["lat"]), 5),
                           round(float(results[0]["lon"]), 5)]
        else:
            coords[pin] = None  # not found
    except Exception as ex:
        print(f"  Error on {pin}: {ex}")
        coords[pin] = None

    # Save every 50 pins
    if i % 50 == 0:
        with open(OUTPUT_FILE, "w") as f:
            json.dump(coords, f, separators=(",", ":"))
        pct = i / total * 100
        found = sum(1 for v in coords.values() if v)
        print(f"  [{i}/{total}] {pct:.1f}% — {found} resolved, {i-found} not found")

    time.sleep(1.1)  # Nominatim ToS: max 1 req/sec

# Final save
with open(OUTPUT_FILE, "w") as f:
    json.dump(coords, f, separators=(",", ":"))

found = sum(1 for v in coords.values() if v)
print(f"\nDone. {found}/{total} pincodes geocoded → {OUTPUT_FILE}")
print("Upload pincode_coords.json to your projectfiner GitHub repo.")
