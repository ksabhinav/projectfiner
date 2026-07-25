"""Pre-publish integrity gate (Phase 6).

None of the repairs stay fixed without a gate — a future extractor run could
silently re-introduce the header collapse or a value regression. This is the
check that fails loudly. It compares the live data against a committed baseline
(`gate_baseline.json`) and exits non-zero on any regression:

  1. no NEW collapse — a state's count of duplicate-field tables in complete.json
     must not EXCEED its baseline. The three repaired states are pinned at 0, so
     any recurrence fails. States with a known, source-dependent residual
     (west-bengal, tamil-nadu, kerala, karnataka) are pinned at their current
     count — they may only go down.
  2. reconciliation ceiling — internal-consistency failures must not exceed the
     baseline (129).
  3. no duplicate (quarter, district) rows in any timeseries.json.
  4. canonical fields present — every (state, CD-ratio) deposit/cd_ratio anchor
     recorded in the baseline must still exist (guards the keep-last repair).

Usage:
    python3 audit/gate.py                    # check; exit 1 on regression
    python3 audit/gate.py --update-baseline  # re-pin baseline to current (after an intended change)
"""
import json, glob, os, sys, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify as V
import unit_resolver as UR

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO, "audit", "gate_baseline.json")
CD_ANCHORS = ("total_deposit", "deposits", "deposit", "cd_ratio", "overall_cd_ratio")


def measure():
    """Current integrity metrics across all states."""
    dup_tables = collections.Counter()
    dup_keys = collections.Counter()
    canon = {}
    recon_fail = 0
    for cj in sorted(glob.glob(os.path.join(REPO, "public/slbc-data/*/*_complete.json"))):
        slug = os.path.basename(cj).replace("_complete.json", "")
        try:
            d = json.load(open(cj))
        except Exception:
            continue
        for q in d.get("quarters", {}).values():
            for tbl in (q.get("tables") or {}).values():
                f = tbl.get("fields") or []
                if len(f) != len(set(f)):
                    dup_tables[slug] += 1
                for a in CD_ANCHORS:
                    if a in f:
                        canon.setdefault(slug, set()).add(a)
        recon_fail += sum(fail for (_, fail, _) in V.reconcile_state(d, slug).values())
    # duplicate (quarter, district) keys in timeseries
    for tj in sorted(glob.glob(os.path.join(REPO, "public/slbc-data/*/*_fi_timeseries.json"))):
        slug = os.path.basename(tj).replace("_fi_timeseries.json", "")
        try:
            d = json.load(open(tj))
        except Exception:
            continue
        seen = collections.Counter()
        for p in d.get("periods", []):
            for rec in p.get("districts", []):
                seen[(p.get("period"), rec.get("district"))] += 1
        dk = sum(1 for c in seen.values() if c > 1)
        if dk:
            dup_keys[slug] = dk
    return {
        "dup_field_tables": dict(dup_tables),
        "dup_district_keys": dict(dup_keys),
        "reconciliation_failures": recon_fail,
        "canonical_anchors": {k: sorted(v) for k, v in canon.items()},
    }


def load_baseline():
    return json.load(open(BASELINE)) if os.path.exists(BASELINE) else None


def check():
    cur = measure()
    base = load_baseline()
    if base is None:
        sys.exit("no baseline — run: python3 audit/gate.py --update-baseline")
    fails = []

    for slug, n in cur["dup_field_tables"].items():
        b = base["dup_field_tables"].get(slug, 0)
        if n > b:
            fails.append(f"COLLAPSE REGRESSION: {slug} has {n} duplicate-field tables (baseline {b})")
    if cur["reconciliation_failures"] > base["reconciliation_failures"]:
        fails.append(f"RECONCILIATION REGRESSION: {cur['reconciliation_failures']} failures "
                     f"(baseline {base['reconciliation_failures']})")
    for slug, n in cur["dup_district_keys"].items():
        if n > base["dup_district_keys"].get(slug, 0):
            fails.append(f"DUPLICATE KEYS: {slug} has {n} duplicate (quarter,district) rows")
    for slug, anchors in base["canonical_anchors"].items():
        have = set(cur["canonical_anchors"].get(slug, []))
        lost = set(anchors) - have
        if lost:
            fails.append(f"CANONICAL FIELD LOST: {slug} no longer has {sorted(lost)}")

    print(f"reconciliation failures: {cur['reconciliation_failures']} (baseline {base['reconciliation_failures']})")
    print(f"states with duplicate-field tables: {len(cur['dup_field_tables'])} "
          f"(pinned residual: {sorted(base['dup_field_tables'])})")
    improved = []
    for slug, b in base["dup_field_tables"].items():
        n = cur["dup_field_tables"].get(slug, 0)
        if n < b:
            improved.append(f"{slug} {b}->{n}")
    if improved:
        print(f"improvements since baseline: {improved} (run --update-baseline to lock in)")
    if fails:
        print("\nGATE FAILED:")
        for f in fails:
            print(f"  ✗ {f}")
        sys.exit(1)
    print("\nGATE PASSED — no integrity regression.")


def update():
    cur = measure()
    json.dump(cur, open(BASELINE, "w"), indent=2, sort_keys=True)
    print(f"baseline pinned: recon={cur['reconciliation_failures']}, "
          f"residual-collapse states={sorted(cur['dup_field_tables'])}")
    print(f"wrote {os.path.relpath(BASELINE, REPO)}")


if __name__ == "__main__":
    update() if "--update-baseline" in sys.argv else check()
