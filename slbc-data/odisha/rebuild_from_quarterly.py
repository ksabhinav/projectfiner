#!/usr/bin/env python3
"""
Recover Odisha data cells lost to the duplicate-header collapse — WITHOUT
re-running the PDF extractor.

The quarterly CSVs under public/slbc-data/odisha/quarterly/ are positionally
complete (values are a plain list). odisha_complete.json keyed each district
row as a {field: value} dict, so repeated sub-column names (a/pct, semi_urban/
urban) overwrote each other, keeping only the last (grand-total) value and
dropping ~20k per-subcategory cells. That collapse propagated into the
timeseries and slim files, the Downloads page, and the analysis pages.

This reads each quarterly CSV, disambiguates its header with the SAME rule now
baked into extract_odisha.py, and rebuilds:
  odisha_complete.json          (recovers the dropped cells)
  odisha_fi_timeseries.json/csv (re-derived from the fixed complete.json)
  odisha_fi_slim.json           (7 homepage categories, re-derived)

It ONLY replaces the tables that actually have duplicate headers; every other
table is rebuilt from its CSV too but comes out identical, so the diff is
exactly the recovered data. Aborts if any table's district set or any surviving
value would change (a safety net against reading the wrong CSV).

    python3 slbc-data/odisha/rebuild_from_quarterly.py [--dry-run]
"""
import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_odisha import disambiguate_headers   # noqa: E402

HERE = Path(__file__).resolve().parent
PUB = Path(__file__).resolve().parents[2] / "public/slbc-data/odisha"
QUARTERLY = PUB / "quarterly"
COMPLETE = PUB / "odisha_complete.json"
TS = PUB / "odisha_fi_timeseries.json"
TS_CSV = PUB / "odisha_fi_timeseries.csv"
SLIM = PUB / "odisha_fi_slim.json"

SLIM_CATEGORIES = {"credit_deposit_ratio", "pmjdy", "branch_network", "kcc",
                   "shg", "digital_transactions", "aadhaar_authentication"}


def slim_base(category):
    """branch_network_p2 -> branch_network, so numbered variants stay in slim."""
    return re.sub(r"_(?:p?\d+)$", "", category)


def read_csv_table(path):
    """(disambiguated_fields, {district: {field: value}}) from a quarterly CSV."""
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], {}
    raw_header = rows[0]
    # header[0] is the district column; disambiguate only the value columns.
    fields = disambiguate_headers(raw_header[1:])
    districts = {}
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        name = r[0].strip()
        vals = r[1:]
        districts[name] = {fields[i]: (vals[i] if i < len(vals) else "")
                           for i in range(len(fields))}
    return fields, districts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    complete = json.loads(COMPLETE.read_text())

    recovered_cells = 0
    changed_tables = 0
    value_conflicts = []
    coverage_conflicts = []

    for qk, qobj in complete["quarters"].items():
        for cat, tbl in qobj.get("tables", {}).items():
            csv_path = QUARTERLY / qk / f"{cat}.csv"
            if not csv_path.exists():
                coverage_conflicts.append(f"{qk}/{cat}: no quarterly CSV")
                continue
            new_fields, new_districts = read_csv_table(csv_path)

            old_districts = tbl.get("districts", {})
            # Safety net 1: district set must be identical.
            if set(new_districts) != set(old_districts):
                coverage_conflicts.append(
                    f"{qk}/{cat}: district set differs "
                    f"(csv {len(new_districts)} vs json {len(old_districts)})")
                continue

            # Safety net 2: every field the OLD json still had must keep its
            # value in the rebuilt row (we only ADD recovered fields; we never
            # change a value that survived the collapse). The collapsed field
            # (e.g. `a`) is allowed to disappear — its value re-appears under a
            # disambiguated name (e.g. `total_msme_a`).
            added = 0
            for d, old_row in old_districts.items():
                new_row = new_districts[d]
                for fk, fv in old_row.items():
                    if fk in new_row and new_row[fk] != fv:
                        value_conflicts.append(f"{qk}/{cat}/{d}/{fk}: "
                                               f"{fv!r} -> {new_row[fk]!r}")
                added += max(0, len(new_row) - len(old_row))

            if new_fields != tbl.get("fields") or added:
                changed_tables += 1
                recovered_cells += added

            tbl["fields"] = new_fields
            tbl["num_districts"] = len(new_districts)
            tbl["districts"] = new_districts

    print(f"tables changed: {changed_tables}")
    print(f"recovered cells: {recovered_cells:,}")
    if coverage_conflicts:
        print(f"\nCOVERAGE CONFLICTS ({len(coverage_conflicts)}):")
        for c in coverage_conflicts[:10]:
            print("  " + c)
    if value_conflicts:
        print(f"\nVALUE CONFLICTS ({len(value_conflicts)}) — ABORTING, no files written:")
        for c in value_conflicts[:15]:
            print("  " + c)
        sys.exit(1)

    if args.dry_run:
        print("\n(dry run — no files written)")
        return

    # ---- write complete.json ------------------------------------------------
    COMPLETE.write_text(json.dumps(complete, indent=2, ensure_ascii=False))
    print(f"\nwrote {COMPLETE.name}")

    # ---- inject recovered fields into the committed timeseries IN PLACE ------
    # NOT via build_timeseries: on this complete.json it yields 239 records vs
    # the committed 216 (the committed file is stale, and the extra records are
    # duplicate spellings like Baleshwar/Balasore). Both are separate
    # pre-existing bugs; a collapse fix must change only FIELDS, not the record
    # set. So keep every existing (period, district) record and refresh each
    # district's category fields from the fixed complete.json.
    ts = json.loads(TS.read_text())
    pname_to_qk = {q["period"]: qk for qk, q in complete["quarters"].items()}
    for p in ts["periods"]:
        qk = pname_to_qk.get(p["period"])
        if qk is None:
            continue
        tables = complete["quarters"][qk].get("tables", {})
        for rec in p["districts"]:
            d = rec["district"]
            for cat, tbl in tables.items():
                if d not in tbl["districts"]:
                    continue
                # drop this category's old (possibly collapsed) keys, re-add all
                for k in [k for k in rec if k.startswith(cat + "__")]:
                    del rec[k]
                for fk, fv in tbl["districts"][d].items():
                    rec[f"{cat}__{fk}"] = fv
    TS.write_text(json.dumps(ts, indent=2, ensure_ascii=False))
    print(f"wrote {TS.name} ({sum(len(p['districts']) for p in ts['periods'])} records)")

    # ---- timeseries CSV (wide) from the updated timeseries -------------------
    all_fields = set()
    for p in ts["periods"]:
        for rec in p["districts"]:
            all_fields.update(k for k in rec if k not in ("district", "period"))
    sorted_fields = sorted(all_fields)
    with open(TS_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["district", "period", "as_on_date", "fy"] + sorted_fields)
        for p in ts["periods"]:
            for rec in p["districts"]:
                w.writerow([rec.get("district", ""), rec.get("period", ""),
                            p.get("as_on_date", ""), p.get("fy", "")]
                           + [rec.get(fld, "") for fld in sorted_fields])
    print(f"wrote {TS_CSV.name}")

    # ---- slim (7 homepage categories), re-derived from the updated timeseries -
    slim = json.loads(SLIM.read_text())
    slim_periods = []
    for p in ts["periods"]:
        rows = []
        for rec in p["districts"]:
            keep = {"district": rec["district"], "period": rec["period"]}
            for k, v in rec.items():
                if "__" in k and slim_base(k.split("__")[0]) in SLIM_CATEGORIES:
                    keep[k] = v
            rows.append(keep)
        slim_periods.append({"period": p["period"], "districts": rows})
    slim["periods"] = slim_periods
    SLIM.write_text(json.dumps(slim, indent=2, ensure_ascii=False))
    print(f"wrote {SLIM.name}")


if __name__ == "__main__":
    main()
