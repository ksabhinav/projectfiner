"""Generalised header-collapse repair (state-agnostic).

Same gated, lossless procedure proven on Odisha (repair_odisha_acp.py), extended
to any state + any set of duplicate-header categories. Recovers columns the
dict-collapse dropped by re-reading the quarterly CSVs positionally and
disambiguating the repeated headers.

Per (quarter, category matching the predicate):
  1. read the quarterly CSV positionally, disambiguate duplicate headers;
  2. GATE: naive re-collapse of the raw CSV must reproduce the CURRENT
     complete.json table exactly — so the repair only ADDS columns, never alters
     a value. Tables that fail the gate are skipped, not forced;
  3. rebuild with unique names, then surgically update complete.json /
     timeseries.json / timeseries.csv, preserving every row and non-target value.

Fixed (non `__`) columns are detected from the state's timeseries.csv, because
they vary (Bihar: district,period; Jharkhand/Odisha: +as_on_date,fy). slim.json
is never touched (it carries only the 7 headline indicators, no ACP).

    python3 audit/repair_headers.py <state> [--cats acp]      # dry run
    python3 audit/repair_headers.py <state> [--cats acp] --apply
"""
import csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from disambiguate import disambiguate_headers

ROOT = os.path.join(HERE, "..", "public", "slbc-data")


def base(slug):
    return os.path.join(ROOT, slug)


def load(slug, name):
    return json.load(open(os.path.join(base(slug), name)))


def target_cats(complete, needle):
    cats = set()
    for q in complete["quarters"].values():
        cats.update(c for c in (q.get("tables") or {}) if needle in c.lower())
    return sorted(cats)


def build_recovered(slug, cats):
    complete = load(slug, f"{slug}_complete.json")
    tables, lookup, gates, recovered = {}, {}, [], 0
    for cat in cats:
        tables[cat] = {}
        for qk, q in complete["quarters"].items():
            cur = (q.get("tables") or {}).get(cat)
            csvp = os.path.join(base(slug), "quarterly", qk, f"{cat}.csv")
            if not cur or not os.path.exists(csvp):
                continue
            with open(csvp, newline="") as fh:
                rows = list(csv.reader(fh))
            if not rows:
                continue
            hdr, body = rows[0], rows[1:]
            dis = disambiguate_headers(hdr)
            cur_d = cur.get("districts") or {}
            miss = 0
            for r in body:
                collapsed = dict(zip(hdr, r))
                cj = cur_d.get(r[0])
                if cj is None:
                    miss += 1
                    continue
                for k, v in cj.items():
                    if str(collapsed.get(k, "")).strip() != str(v).strip():
                        miss += 1
            gates.append((cat, qk, len(body), miss, len(dis) - 1, len(cur_d and next(iter(cur_d.values()), {}))))
            if miss:
                continue
            fields = dis[1:]
            dists = {}
            period = q.get("period", qk)
            for r in body:
                rowd = dict(zip(dis, r))
                dists[r[0]] = {f: rowd.get(f, "") for f in fields}
                for f in fields:
                    lookup.setdefault((period, r[0]), {})[f"{cat}__{f}"] = rowd.get(f, "")
            # recovered = new fields beyond the collapsed set, x districts
            old_nf = len(cur_d and next(iter(cur_d.values()), {}))
            recovered += max(0, len(fields) - old_nf) * len(dists)
            tables[cat][qk] = {"fields": fields, "districts": dists}
    return complete, tables, lookup, gates, recovered


def apply_repair(slug, cats, complete, tables, lookup):
    cset = set(cats)
    for cat, byq in tables.items():
        for qk, tbl in byq.items():
            complete["quarters"][qk]["tables"][cat] = tbl
    json.dump(complete, open(os.path.join(base(slug), f"{slug}_complete.json"), "w"), indent=2)

    ts = load(slug, f"{slug}_fi_timeseries.json")
    for p in ts["periods"]:
        for rec in p["districts"]:
            new = lookup.get((p["period"], rec.get("district")), {})
            for k in [k for k in rec if k.split("__")[0] in cset]:
                del rec[k]
            rec.update(new)
    json.dump(ts, open(os.path.join(base(slug), f"{slug}_fi_timeseries.json"), "w"), indent=2)

    path = os.path.join(base(slug), f"{slug}_fi_timeseries.csv")
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        orig_cols = rd.fieldnames or []
        rows = list(rd)
    fixed = [c for c in orig_cols if "__" not in c]            # state-specific, detected
    for row in rows:
        for k in [k for k in row if k.split("__")[0] in cset]:
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


def main(slug, needle, apply):
    complete = load(slug, f"{slug}_complete.json")
    cats = target_cats(complete, needle)
    if not cats:
        sys.exit(f"no categories matching '{needle}' in {slug}")
    complete, tables, lookup, gates, recovered = build_recovered(slug, cats)
    bad = [g for g in gates if g[3]]
    print(f"{slug}: {len(cats)} categories matching '{needle}'")
    print(f"{'category':32}{'q_ok':>6}{'gate':>7}")
    for cat in cats:
        gs = [g for g in gates if g[0] == cat]
        okq = sum(1 for g in gs if not g[3])
        print(f"{cat:32}{okq:>6}{'  OK' if not any(g[3] for g in gs) else '  FAIL':>7}")
    if bad:
        print("\nGATE FAILURES (skipped):")
        for c, q, n, m, *_ in bad:
            print(f"  {c} {q}: {m} mismatches / {n} rows")
    print(f"\nrecovered ~{recovered} previously-collapsed cells across {len(lookup)} district-quarters")
    if not apply:
        print("(dry run — nothing written. add --apply)")
        return
    if bad:
        sys.exit("refusing to apply: gate failures present")
    nr, nc = apply_repair(slug, cats, complete, tables, lookup)
    print(f"APPLIED. {slug} timeseries.csv now {nr} rows x {nc} cols; complete.json + timeseries.json rewritten.")


if __name__ == "__main__":
    args = sys.argv[1:]
    slug = next((a for a in args if not a.startswith("--")), None)
    needle = args[args.index("--cats") + 1] if "--cats" in args else "acp"
    if not slug:
        sys.exit("usage: repair_headers.py <state> [--cats <substr>] [--apply]")
    main(slug, needle, "--apply" in args)
