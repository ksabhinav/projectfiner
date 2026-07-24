"""Repair the Odisha ACP header-collapse (triage cause: header_collapse, 411 cells).

The 5 acp_district_* tables were built by dict-keying rows whose achievement (`a`)
and percent (`pct`) columns share names across every sub-category, so only the
last (grand-total) pair survived and the per-subcategory achievements were lost.
The quarterly CSVs kept every value positionally — this recovers them.

Method, per (quarter, category):
  1. read the quarterly CSV positionally, disambiguate the duplicate headers
     (audit/disambiguate.py) so each a/pct attaches to its sub-category;
  2. GATE: naive-collapse the raw CSV (dict(zip(header,row))) must reproduce the
     CURRENT complete.json table exactly — proof the CSV is a faithful superset
     and the repair only ADDS columns, never alters an existing value;
  3. rebuild the table with unique names.

Then surgically update all three artifacts, preserving every row and every
non-ACP value: complete.json (table replace), timeseries.json (per-record key
swap), timeseries.csv (column swap + re-sort). slim.json has no ACP fields.

    python3 audit/repair_odisha_acp.py            # dry run: gates + planned change
    python3 audit/repair_odisha_acp.py --apply    # write the three artifacts
"""
import csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from disambiguate import disambiguate_headers

OD = os.path.join(HERE, "..", "public", "slbc-data", "odisha")
ACP_CATS = ["acp_district_agri", "acp_district_agri_allied", "acp_district_ancillary",
            "acp_district_msme", "acp_district_total"]


def _load(name):
    return json.load(open(os.path.join(OD, name)))


def build_recovered():
    """Return {cat: {qkey: {fields, districts}}} and a lookup
    {(period_label, district): {f'{cat}__{field}': value}} — plus gate results."""
    complete = _load("odisha_complete.json")
    tables, lookup, gates = {}, {}, []
    for cat in ACP_CATS:
        tables[cat] = {}
        for qk, q in complete["quarters"].items():
            cur = (q.get("tables") or {}).get(cat)
            csvp = os.path.join(OD, "quarterly", qk, f"{cat}.csv")
            if not os.path.exists(csvp) or not cur:
                continue
            with open(csvp, newline="") as fh:
                rows = list(csv.reader(fh))
            hdr, body = rows[0], rows[1:]
            dis = disambiguate_headers(hdr)
            # GATE: naive collapse of raw CSV == current complete.json table
            cur_d = cur.get("districts") or {}
            miss = 0
            for r in body:
                collapsed = dict(zip(hdr, r))         # last-wins, == old dict-keying
                cj = cur_d.get(r[0])
                if cj is None:
                    miss += 1
                    continue
                for k, v in cj.items():
                    if str(collapsed.get(k, "")).strip() != str(v).strip():
                        miss += 1
            gates.append((cat, qk, len(body), miss))
            if miss:
                continue                              # unsafe — skip this table
            # rebuild with unique names
            fields = [d for d in dis[1:]]             # drop 'district'
            dists = {}
            period = q.get("period", qk)
            for r in body:
                rowd = dict(zip(dis, r))
                dname = r[0]
                dists[dname] = {f: rowd.get(f, "") for f in fields}
                for f in fields:
                    lookup.setdefault((period, dname), {})[f"{cat}__{f}"] = rowd.get(f, "")
            tables[cat][qk] = {"fields": fields, "districts": dists}
    return complete, tables, lookup, gates


def apply_repair(complete, tables, lookup):
    # 1. complete.json — replace ACP tables
    for cat, byq in tables.items():
        for qk, tbl in byq.items():
            complete["quarters"][qk]["tables"][cat] = tbl
    json.dump(complete, open(os.path.join(OD, "odisha_complete.json"), "w"),
              indent=2)

    # 2. timeseries.json — per record, drop old ACP keys, add disambiguated ones
    ts = _load("odisha_fi_timeseries.json")
    for p in ts["periods"]:
        period = p["period"]
        for rec in p["districts"]:
            dname = rec.get("district")
            new = lookup.get((period, dname), {})
            for k in [k for k in rec if k.split("__")[0] in ACP_CATS]:
                del rec[k]
            rec.update(new)
    json.dump(ts, open(os.path.join(OD, "odisha_fi_timeseries.json"), "w"),
              indent=2)

    # 3. timeseries.csv — swap ACP columns, preserve every row; re-sort columns
    path = os.path.join(OD, "odisha_fi_timeseries.csv")
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        rows = list(rd)
    fixed = ["district", "period", "as_on_date", "fy"]
    for row in rows:
        for k in [k for k in row if k.split("__")[0] in ACP_CATS]:
            del row[k]
        row.update(lookup.get((row.get("period"), row.get("district")), {}))
    keys = set()
    for row in rows:
        keys.update(row)
    cols = [c for c in fixed if c in keys] + sorted(k for k in keys if k not in fixed)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in cols})
    return len(rows), len(cols)


def main(apply):
    complete, tables, lookup, gates = build_recovered()
    bad = [g for g in gates if g[3]]
    print(f"{'category':28}{'quarters':>9}{'gate':>8}")
    for cat in ACP_CATS:
        gs = [g for g in gates if g[0] == cat]
        ok = sum(1 for g in gs if not g[3])
        nf = len([f for f in tables[cat]])
        print(f"{cat:28}{ok:>9}/{len(gs):<3}  {'OK' if not any(g[3] for g in gs) else 'FAIL'}")
    if bad:
        print("\nGATE FAILURES (skipped, would need investigation):")
        for c, q, n, m in bad:
            print(f"  {c} {q}: {m} mismatches / {n} rows")
    n_new = sum(len(v) for v in lookup.values())
    sample = next(iter(tables["acp_district_msme"].values()))
    print(f"\nrecovered per-subcategory a/pct across {len(lookup)} district-quarters")
    print(f"msme fields after repair ({len(sample['fields'])}): "
          f"{[f for f in sample['fields'] if f.endswith(('_a','_pct'))][:6]} ...")
    if not apply:
        print("\n(dry run — nothing written. re-run with --apply)")
        return
    if bad:
        sys.exit("\nrefusing to apply: gate failures present")
    nrows, ncols = apply_repair(complete, tables, lookup)
    print(f"\nAPPLIED. timeseries.csv now {nrows} rows x {ncols} cols. "
          f"complete.json + timeseries.json rewritten. slim.json untouched (no ACP).")


if __name__ == "__main__":
    main("--apply" in sys.argv)
