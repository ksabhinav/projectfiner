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
from disambiguate import disambiguate_headers_keep_last as disambiguate_headers

ROOT = os.path.join(HERE, "..", "public", "slbc-data")


def base(slug):
    return os.path.join(ROOT, slug)


def load(slug, name):
    return json.load(open(os.path.join(base(slug), name)))


def target_cats(complete, needle):
    if needle == "*ALLDUPS*":
        # unrepaired collapse: complete.json fields list carries duplicates
        cats = set()
        for q in complete["quarters"].values():
            for c, tbl in (q.get("tables") or {}).items():
                f = tbl.get("fields") or []
                if len(f) != len(set(f)):
                    cats.add(c)
        return sorted(cats)
    cats = set()
    for q in complete["quarters"].values():
        cats.update(c for c in (q.get("tables") or {}) if needle in c.lower())
    return sorted(cats)


def build_recovered(slug, cats):
    """Include a category only if EVERY quarter with data passes the gate, so a
    category is never left half-repaired. Returns tables, lookup, per-cat report."""
    complete = load(slug, f"{slug}_complete.json")
    tables, lookup, report, recovered = {}, {}, [], 0
    for cat in cats:
        staged, ok_all, nq, bad_q = {}, True, 0, []
        for qk, q in complete["quarters"].items():
            cur = (q.get("tables") or {}).get(cat)
            csvp = os.path.join(base(slug), "quarterly", qk, f"{cat}.csv")
            if not cur or not os.path.exists(csvp):
                continue
            cf = cur.get("fields") or []
            if len(cf) == len(set(cf)):          # this quarter isn't collapsed — leave it
                continue
            with open(csvp, newline="") as fh:
                rows = list(csv.reader(fh))
            if not rows:
                continue
            nq += 1
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
            if miss:
                ok_all = False
                bad_q.append((qk, miss))
                continue
            old_nf = len(cur_d and next(iter(cur_d.values()), {}))
            staged[qk] = (dis, body, q.get("period", qk), len(dis) - 1 - old_nf)
        if nq == 0:
            continue
        if not ok_all:
            report.append((cat, "SKIP", nq, bad_q))
            continue
        tables[cat] = {}
        for qk, (dis, body, period, dnew) in staged.items():
            fields = dis[1:]
            dists = {}
            for r in body:
                rowd = dict(zip(dis, r))
                dists[r[0]] = {f: rowd.get(f, "") for f in fields}
                for f in fields:
                    lookup.setdefault((period, r[0]), {})[f"{cat}__{f}"] = rowd.get(f, "")
            recovered += max(0, dnew) * len(dists)
            tables[cat][qk] = {"fields": fields, "districts": dists}
        report.append((cat, "ok", nq, len(tables[cat])))
    return complete, tables, lookup, report, recovered


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
    label = "all collapsed" if needle == "*ALLDUPS*" else f"matching '{needle}'"
    if not cats:
        print(f"{slug}: no categories {label} — nothing to do (already repaired?)")
        return
    complete, tables, lookup, report, recovered = build_recovered(slug, cats)
    repaired = [c for c, s, *_ in report if s == "ok"]
    skipped = [(c, extra) for c, s, n, extra in report if s == "SKIP"]
    print(f"{slug}: {len(cats)} categories {label}  ->  {len(repaired)} repairable, {len(skipped)} gate-skipped")
    for c, s, n, extra in report:
        if s == "ok":
            print(f"  ok    {c:34} {extra}/{n} quarters")
    for c, extra in skipped:
        print(f"  SKIP  {c:34} gate mismatch in {[q for q, _ in extra]}")
    print(f"\nrecovered ~{recovered} previously-collapsed cells across {len(lookup)} district-quarters")
    if not apply:
        print("(dry run — nothing written. add --apply)")
        return
    if not tables:
        print("nothing repairable to apply.")
        return
    nr, nc = apply_repair(slug, repaired, complete, tables, lookup)
    print(f"APPLIED. {slug} timeseries.csv now {nr} rows x {nc} cols; complete.json + timeseries.json rewritten.")


if __name__ == "__main__":
    args = sys.argv[1:]
    slug = next((a for a in args if not a.startswith("--")), None)
    needle = args[args.index("--cats") + 1] if "--cats" in args else "acp"
    if not slug:
        sys.exit("usage: repair_headers.py <state> [--cats <substr>] [--apply]")
    main(slug, needle, "--apply" in args)
