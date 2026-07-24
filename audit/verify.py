"""Phase-3 verification harness.

The program's core method is *dual independent extraction*: read each table a
second time with a structurally different parser and diff cell by cell. That
needs the source PDF corpus (Phase 1), which an ephemeral session can't fetch —
so `diff_tables()` is built and tested as the pluggable core, ready for the
second reading, but the headline work here is the slice that runs TODAY:

  1. RECONCILIATION — internal-consistency checks that need no second source and
     catch a large share of extraction errors:
       * ratio:        advance / deposit * 100  ==  reported CD ratio
       * area_sum:     rural + semi_urban + urban  ==  reported total
       * achievement%: achievement / target * 100  ==  reported pct   (the check
                        that started this: Odisha's collapsed a/pct)
     A row that fails these was almost certainly mis-extracted. This is not a
     substitute for source verification — both a wrong parse and a wrong source
     can still reconcile — but it is a cheap, high-yield first pass.

  2. STRATIFIED SAMPLER — the worklist a human (or the second extractor) checks
     against the page image. Over-samples where parsers fail: quarter boundaries,
     total rows, highest-magnitude cells, merged-header-adjacent orphans.

  3. ERROR-RATE STATS — Wilson / rule-of-three upper bound, so "0 errors in 60
     cells" becomes a defensible "<5%" rather than a bare "looks fine".

    python3 audit/verify.py                          # reconcile all tables -> reconciliation.csv
    python3 audit/verify.py --sample odisha:acp_district_msme --tier A
    python3 audit/test_verify.py                     # pure-logic tests
"""
import csv, glob, json, math, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unit_resolver as UR

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIER_N = {"A": 60, "B": 30, "C": 10}

# ------------------------------------------------------------- error-rate math
def wilson_upper(errors, n, z=1.96):
    """Upper bound of the 95% Wilson score interval for a proportion."""
    if n == 0:
        return 1.0
    p = errors / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, (centre + half) / d)


def rule_of_three_upper(n):
    """95% upper bound when zero errors are observed in n trials (3/n)."""
    return 3.0 / n if n else 1.0


# ------------------------------------------------------------- reconciliation
def _n(v):
    return UR._num(v)


def find_roles(fields):
    """Locate the columns each reconciliation check needs, by normalised name."""
    nm = {UR._norm(f): f for f in fields}
    pick = lambda cands: next((nm[c] for c in cands if c in nm), None)
    return {
        "deposit": pick(["total_deposit", "deposits", "deposit", "deposit_amount_d"]),
        "advance": pick(["total_advance", "total_advances", "advance", "advances", "advance_amount_a"]),
        "cd_ratio": pick(["overall_cd_ratio", "cd_ratio", "c_d_ratio", "cdr", "current_c_d_ratio"]),
        "dep_areas": [nm[a] for a in ("dep_rural", "dep_semi_urban", "dep_urban",
                                      "deposit_rural", "deposit_semi_urban", "deposit_urban") if a in nm],
        "adv_areas": [nm[a] for a in ("adv_rural", "adv_semi_urban", "adv_urban") if a in nm],
        "target": pick(["total_target", "target"]) or next((nm[k] for k in nm if k.endswith("_t") and k.startswith("total")), None),
        "achievement": nm.get("a"),
        "pct": nm.get("pct"),
    }


def _close(got, want, rel=0.05, floor=2.0):
    return abs(got - want) <= max(floor, abs(want) * rel)


def reconcile_row(row, roles):
    """Yield (check, ok, detail) for each applicable relationship in one row."""
    r = roles
    if r["deposit"] and r["advance"] and r["cd_ratio"]:
        dep, adv, cdr = _n(row.get(r["deposit"])), _n(row.get(r["advance"])), _n(row.get(r["cd_ratio"]))
        if dep and adv is not None and cdr is not None and dep > 0:
            got = adv / dep * 100
            yield ("ratio", _close(got, cdr, 0.05, 2.0), f"adv/dep={got:.1f} vs cdr={cdr:.1f}")
    for label, cols in (("dep_area_sum", r["dep_areas"]), ("adv_area_sum", r["adv_areas"])):
        tot_col = r["deposit"] if label.startswith("dep") else r["advance"]
        if len(cols) >= 2 and tot_col:
            parts = [_n(row.get(c)) for c in cols]
            tot = _n(row.get(tot_col))
            if tot and all(p is not None for p in parts) and tot > 0:
                s = sum(parts)
                yield (label, _close(s, tot, 0.02, 1.0), f"sum={s:.0f} vs total={tot:.0f}")
    if r["achievement"] and r["pct"] and r["target"]:
        a, pct, t = _n(row.get(r["achievement"])), _n(row.get(r["pct"])), _n(row.get(r["target"]))
        if a is not None and pct is not None and t and t > 0:
            got = a / t * 100
            yield ("achievement_pct", _close(got, pct, 0.05, 2.0), f"a/t={got:.1f} vs pct={pct:.1f}")


def _iter_rows(complete):
    """Yield (quarter, category, district, row_dict, fields) across a state."""
    for qk, q in complete.get("quarters", {}).items():
        for cat, tbl in (q.get("tables") or {}).items():
            fields = tbl.get("fields") or []
            dists = tbl.get("districts") or {}
            it = dists.items() if isinstance(dists, dict) else (
                (v.get("district", ""), v) for v in dists if isinstance(v, dict))
            for dname, row in it:
                if isinstance(row, dict):
                    yield q.get("period", qk), cat, dname, row, fields


def reconcile_state(complete, slug):
    """Per (category, check) reconciliation tallies + a few example failures."""
    agg = {}   # (cat, check) -> [n, fail, examples]
    roles_cache = {}
    for period, cat, dname, row, fields in _iter_rows(complete):
        # key on the field set, not the category: a category's columns vary
        # across quarters, so caching by name alone misses/adds checks.
        fkey = tuple(fields)
        roles = roles_cache.get(fkey)
        if roles is None:
            roles = roles_cache[fkey] = find_roles(fields)
        for check, ok, detail in reconcile_row(row, roles):
            k = (cat, check)
            a = agg.setdefault(k, [0, 0, []])
            a[0] += 1
            if not ok:
                a[1] += 1
                if len(a[2]) < 3:
                    a[2].append(f"{dname} {period}: {detail}")
    return agg


# --------------------------------------------------------------- stratified sample
def sample_table(complete, category, tier="B", seed=None):
    """Stratified cell sample for one (state, category) table -> list of dicts.
    Over-samples exactly where extraction breaks."""
    rows, fields = [], []
    for period, cat, dname, row, fs in _iter_rows(complete):
        if cat != category:
            continue
        rows.append((period, dname, row))
        if not fields:
            fields = fs
    if not rows:
        return []
    datacols = [f for f in fields if f not in ("district",)]
    rnd = random.Random(seed if seed is not None else hash(category) & 0xFFFF)
    picks = {}   # (period, district, column) -> stratum

    def add(period, dist, col, stratum):
        if col and (period, dist, col) not in picks:
            picks[(period, dist, col)] = stratum

    quarters = sorted({p for p, _, _ in rows})
    by_q = {q: [(d, rw) for p, d, rw in rows if p == q] for q in quarters}
    key_col = datacols[0] if datacols else None
    for q in quarters:                                   # 1. one per quarter (drift)
        d, rw = rnd.choice(by_q[q])
        add(q, d, rnd.choice(datacols) if datacols else None, "per_quarter")
    q0 = quarters[-1]                                    # boundary + totals on latest q
    ds = sorted({d for d, _ in by_q[q0]})
    if ds:                                               # 2. first & last district
        for d in (ds[0], ds[-1]):
            add(q0, d, key_col, "boundary_row")
    for d, _ in by_q[q0]:                                # 3. total rows
        if any(t in d.lower() for t in ("total", "grand")):
            add(q0, d, key_col, "total_row")
    orphans = [c for c in datacols if UR._norm(c) in ("a", "pct", "amt", "no", "amount")]
    mags = []                                            # 4. highest-magnitude cells
    for p, d, rw in rows:
        for c in datacols:
            v = _n(rw.get(c))
            if v is not None:
                mags.append((v, p, d, c))
    for _, p, d, c in sorted(mags, reverse=True)[:5]:
        add(p, d, c, "high_magnitude")
    for p, d, rw in rows[:8]:                            # 5. merged-header-adjacent
        for c in orphans[:2]:
            add(p, d, c, "merged_header_adj")
    all_cells = [(p, d, c) for p, d, rw in rows for c in datacols]  # 6. random remainder
    rnd.shuffle(all_cells)
    for p, d, c in all_cells:
        if len(picks) >= TIER_N[tier]:
            break
        add(p, d, c, "random")

    out = []
    val = {(p, d): rw for p, d, rw in rows}
    for (p, d, c), stratum in list(picks.items())[: TIER_N[tier]]:
        out.append({"quarter": p, "district": d, "column": c,
                    "published_value": val.get((p, d), {}).get(c, ""), "stratum": stratum})
    return out


# ---------------------------------------------- dual-extraction diff (pluggable core)
def diff_tables(published, second, rel=0.01, floor=0.5):
    """Align two readings of a table by (quarter, district, column) and diff.
    Each is a list of {quarter, district, column, value}. Returns
    {agree, disagree, only_published, only_second, mismatches:[...]}.
    This is the core of dual-extraction verification; `second` is supplied by an
    independent parser/VLM once the source corpus exists."""
    def index(t):
        return {(r["quarter"], r["district"], r["column"]): r["value"] for r in t}
    a, b = index(published), index(second)
    agree = dis = 0
    mism = []
    for k in a.keys() & b.keys():
        va, vb = UR._num(a[k]), UR._num(b[k])
        if va is not None and vb is not None:
            ok = abs(va - vb) <= max(floor, abs(va) * rel)
        else:
            ok = str(a[k]).strip() == str(b[k]).strip()
        if ok:
            agree += 1
        else:
            dis += 1
            if len(mism) < 50:
                mism.append({"key": k, "published": a[k], "second": b[k]})
    return {"agree": agree, "disagree": dis,
            "only_published": len(a.keys() - b.keys()),
            "only_second": len(b.keys() - a.keys()), "mismatches": mism}


# ------------------------------------------------------------------------- drivers
def run_reconciliation():
    findings, backfill = [], {}
    for cj in sorted(glob.glob(os.path.join(REPO, "public/slbc-data/*/*_complete.json"))):
        slug = os.path.basename(cj).replace("_complete.json", "")
        if slug == "tamilnadu":
            continue
        try:
            complete = json.load(open(cj))
        except Exception as e:
            print("SKIP", slug, e)
            continue
        agg = reconcile_state(complete, slug)
        st_checks = st_fail = 0
        cat_tot = {}
        for (cat, check), (n, fail, ex) in sorted(agg.items()):
            findings.append({
                "table_id": f"{slug}__{cat}", "state": slug, "category": cat, "check": check,
                "n_checked": n, "n_fail": fail,
                "fail_rate": round(fail / n * 100, 1) if n else 0,
                "err_ub95": round(wilson_upper(fail, n) * 100, 1),
                "examples": " | ".join(ex),
            })
            st_checks += n
            st_fail += fail
            c = cat_tot.setdefault(cat, [0, 0])
            c[0] += n
            c[1] += fail
        for cat, (n, fail) in cat_tot.items():
            backfill[(slug, cat)] = (n, fail)
        if st_checks:
            print(f"{slug:18} checks={st_checks:6}  fails={st_fail:5}  "
                  f"fail_rate={st_fail/st_checks*100:5.1f}%")

    fcols = ["table_id", "state", "category", "check", "n_checked", "n_fail",
             "fail_rate", "err_ub95", "examples"]
    with open(os.path.join(REPO, "audit", "reconciliation.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fcols)
        w.writeheader()
        w.writerows(findings)
    _backfill_registry(backfill)
    tot_n = sum(f["n_checked"] for f in findings)
    tot_f = sum(f["n_fail"] for f in findings)
    worst = sorted(findings, key=lambda f: -f["fail_rate"])[:8]
    print(f"\n{len(findings)} (table,check) rows. {tot_n:,} cells reconciled, "
          f"{tot_f:,} fail ({tot_f/tot_n*100:.1f}%).")
    print("Worst (likely extraction errors):")
    for f in worst:
        if f["n_checked"] >= 10 and f["fail_rate"] > 0:
            print(f"  {f['table_id']:36} {f['check']:15} {f['n_fail']}/{f['n_checked']} "
                  f"({f['fail_rate']}%)  e.g. {f['examples'][:70]}")
    print("wrote audit/reconciliation.csv")


def _backfill_registry(backfill):
    reg = os.path.join(REPO, "audit", "registry.csv")
    if not os.path.exists(reg):
        return
    with open(reg, newline="") as fh:
        rows = list(csv.DictReader(fh))
        cols = list(rows[0].keys()) if rows else []
    for c in ("recon_checks", "recon_fails", "recon_fail_rate"):
        if c not in cols:
            cols.append(c)
    for r in rows:
        n, fail = backfill.get((r["state"], r["indicator"]), (0, 0))
        r["recon_checks"], r["recon_fails"] = n, fail
        r["recon_fail_rate"] = round(fail / n * 100, 1) if n else ""
    with open(reg, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"backfilled reconciliation columns into {os.path.relpath(reg, REPO)}")


def run_sample(spec, tier):
    slug, _, cat = spec.partition(":")
    cj = os.path.join(REPO, "public/slbc-data", slug, f"{slug}_complete.json")
    if not os.path.exists(cj):
        sys.exit(f"no complete.json for {slug}")
    complete = json.load(open(cj))
    if not cat:
        cats = sorted({c for q in complete["quarters"].values() for c in (q.get("tables") or {})})
        sys.exit(f"specify a category, e.g. {slug}:{cats[0]}  (available: {cats[:6]}...)")
    sample = sample_table(complete, cat, tier)
    out = os.path.join(REPO, "audit", f"sample_{slug}_{cat}.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["quarter", "district", "column", "published_value", "stratum"])
        w.writeheader()
        w.writerows(sample)
    print(f"Tier {tier}: {len(sample)} cells to verify against the source PDF for {slug}:{cat}")
    for s in sample:
        print(f"  [{s['stratum']:17}] {s['quarter']:15} {s['district']:20} {s['column']:24} = {s['published_value']}")
    print(f"\nwrote {os.path.relpath(out, REPO)} — check each against the page image; "
          f"0 errors here => <{rule_of_three_upper(len(sample))*100:.0f}% error rate (95% UB)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--sample" in a:
        spec = a[a.index("--sample") + 1]
        tier = a[a.index("--tier") + 1] if "--tier" in a else "B"
        run_sample(spec, tier)
    else:
        run_reconciliation()
