"""
Rajasthan SLBC extractor v2.

Drop-in successor to extract_rajasthan.py with two practical changes:
  - Reads XLSX bundles from ./raw/ (matches the bulk-download convention
    used by sister state pipelines like madhya-pradesh and chhattisgarh).
  - Discovers any number of quarter file-sets via filename pattern, so
    future Rajasthan quarters can be dropped into raw/ and picked up
    without code edits.

The actual per-sheet extraction logic is reused unchanged from v1
(extract_rajasthan.py) — it is comprehensive and handles all 18 category
tables across both 2025 and 2026 file-set formats. Re-implementing it
here would only risk regressions.

Filename conventions recognised in raw/:
  annex_1-12_<tag>.xlsx
  annex_13-20_<tag>.xlsx
  annex_21-33_<tag>.xlsx

where <tag> is a year-ish identifier. The tag-to-quarter mapping for
the two known file sets is hard-coded in QUARTER_OVERRIDES below.
Newly-published XLSX bundles must be added to QUARTER_OVERRIDES (or
the tag itself must be a parseable YYYY-MM string).

As of the 167th SLBC meeting (Nov 2025), Rajasthan only publishes the
two quarters Sep 2025 + Dec 2025 in XLSX form. See meetings_audit.txt.
"""

import json
import os
import re
import sys
import importlib.util


# Import all extractor functions from v1 (loaded by path, not name, so
# the underscore-only module name doesn't collide with v2).
_V1_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "extract_rajasthan.py")
_spec = importlib.util.spec_from_file_location("extract_rajasthan_v1", _V1_PATH)
_v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_v1)


# Mapping from filename tag -> quarter metadata.
# Add new entries here when SLBC Rajasthan publishes new XLSX bundles.
QUARTER_OVERRIDES = {
    "2025": {  # files dated "2025" = Sep 2025 quarter (FY 2025-26 Q2)
        "quarter_key": "2025-09",
        "period": "September 2025",
        "as_on_date": "30-09-2025",
        "fy": "2025-26",
        "pmjdy_sheet": "Annex 13B",
        "jan_suraksha_sheet": "Annex 13D",
        "apy_sheet": "Annex 14A",
        "has_vishwakarma_25a": False,
    },
    "2026": {  # files dated "2026" = Dec 2025 quarter (FY 2025-26 Q3)
        "quarter_key": "2025-12",
        "period": "December 2025",
        "as_on_date": "31-12-2025",
        "fy": "2025-26",
        "pmjdy_sheet": "Annex 13A",
        "jan_suraksha_sheet": "Annex 14A",
        "apy_sheet": "Annex 14C",
        "has_vishwakarma_25a": True,
    },
}


RAW_DIR = "raw"


def discover_quarters():
    """Look in raw/ for annex_*_<tag>.xlsx triples and emit quarter records.

    A triple is complete when raw/ contains all three of
    annex_1-12_<tag>.xlsx, annex_13-20_<tag>.xlsx, annex_21-33_<tag>.xlsx.
    """
    if not os.path.isdir(RAW_DIR):
        print(f"NOTE: {RAW_DIR}/ does not exist — nothing to extract.")
        return []
    tags = set()
    for name in os.listdir(RAW_DIR):
        m = re.match(r"annex_1-12_(.+?)\.xlsx$", name, re.IGNORECASE)
        if m:
            tags.add(m.group(1))
    found = []
    for tag in sorted(tags):
        f112 = os.path.join(RAW_DIR, f"annex_1-12_{tag}.xlsx")
        f1320 = os.path.join(RAW_DIR, f"annex_13-20_{tag}.xlsx")
        f2133 = os.path.join(RAW_DIR, f"annex_21-33_{tag}.xlsx")
        if not (os.path.exists(f1320) and os.path.exists(f2133)):
            print(f"INCOMPLETE TRIPLE for tag={tag}: skipping")
            continue
        if tag not in QUARTER_OVERRIDES:
            print(f"UNKNOWN TAG {tag} — add it to QUARTER_OVERRIDES "
                  f"with quarter_key/period/sheet-name metadata.")
            continue
        meta = dict(QUARTER_OVERRIDES[tag])
        meta["files"] = {"1-12": f112, "13-20": f1320, "21-33": f2133}
        meta["tag"] = tag
        found.append(meta)
    return found


def extract_all_for_quarter(qinfo):
    """Run all per-sheet extractors for one quarter using v1 logic."""
    f112 = qinfo["files"]["1-12"]
    f1320 = qinfo["files"]["13-20"]
    f2133 = qinfo["files"]["21-33"]

    print(f"\n{'='*60}")
    print(f"Quarter: {qinfo['period']} ({qinfo['quarter_key']})")
    print(f"  Files: {os.path.basename(f112)}, "
          f"{os.path.basename(f1320)}, {os.path.basename(f2133)}")
    print(f"{'='*60}")

    data = {}
    data["credit_deposit_ratio"] = _v1.extract_annex3(f112)
    data["acp_summary"] = _v1.extract_annex12(f112)
    data["acp_accounts"] = _v1.extract_annex12a(f112)
    data["acp_agriculture"] = _v1.extract_annex12b(f112)
    data["acp_msme"] = _v1.extract_annex12c(f112)
    data["acp_other_priority"] = _v1.extract_annex12d(f112)
    data["non_priority_sector"] = _v1.extract_annex12e(f112)

    data["pmjdy"] = _v1.extract_pmjdy_district(f1320, qinfo["pmjdy_sheet"])
    data["jan_suraksha"] = _v1.extract_jan_suraksha_district(f1320, qinfo["jan_suraksha_sheet"])
    data["apy"] = _v1.extract_apy_district(f1320, qinfo["apy_sheet"])
    data["nwr_pledge"] = _v1.extract_annex15a(f1320)
    data["nrlm"] = _v1.extract_annex17a(f1320)
    data["pmegp"] = _v1.extract_annex18a(f1320)
    data["ambedkar_scheme"] = _v1.extract_annex19a(f1320)
    data["pmajay"] = _v1.extract_annex20a(f1320)

    data["mnsupy"] = _v1.extract_annex23a(f2133)
    if qinfo["has_vishwakarma_25a"]:
        data["vishwakarma"] = _v1.extract_annex25a(f2133)
    else:
        data["vishwakarma"] = {}
    data["rseti"] = _v1.extract_annex28(f2133)
    return data


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    quarters = discover_quarters()
    if not quarters:
        print("No complete XLSX triples found in raw/. Nothing to do.")
        return 1

    all_quarters = []
    for qinfo in quarters:
        data = extract_all_for_quarter(qinfo)
        all_quarters.append({
            "quarter_key": qinfo["quarter_key"],
            "period": qinfo["period"],
            "as_on_date": qinfo["as_on_date"],
            "fy": qinfo["fy"],
            "data": data,
        })
    all_quarters.sort(key=lambda q: q["quarter_key"])

    complete = _v1.build_complete_json(all_quarters)
    timeseries = _v1.build_timeseries_json(all_quarters)

    with open("rajasthan_complete.json", "w") as f:
        json.dump(complete, f, indent=2, ensure_ascii=False)
    print("\nWrote rajasthan_complete.json")

    with open("rajasthan_fi_timeseries.json", "w") as f:
        json.dump(timeseries, f, indent=2, ensure_ascii=False)
    print("Wrote rajasthan_fi_timeseries.json")

    print(f"\n{'='*60}\nSUMMARY\n{'='*60}")
    for q in all_quarters:
        dists = set()
        for cat in q["data"].values():
            dists.update(cat.keys())
        print(f"\n{q['period']} ({q['quarter_key']}): {len(dists)} unique districts")
        for cat_key in _v1.CATEGORY_DEFS:
            cat_data = q["data"].get(cat_key, {})
            if cat_data:
                n_fields = sum(len(v) for v in cat_data.values()) // max(len(cat_data), 1)
                print(f"  {cat_key}: {len(cat_data)} districts, ~{n_fields} fields each")
    return 0


if __name__ == "__main__":
    sys.exit(main())
