"""Triage the reconciliation failures into root causes + fixes.

Reconciliation (verify.py) flags cells that fail an internal-consistency check.
Triage asks *why* each failed, so the 513 flags collapse into a handful of
actionable root causes rather than 513 separate mysteries. Classification is
evidence-based, from the value pattern of each failing row:

  header_collapse     achievement `a`/`pct` reconcile with a DIFFERENT `_t`
                      column than their label implies — the duplicate-header
                      collapse kept the grand-total pair and dropped the per-
                      subcategory ones. Recoverable from the quarterly CSVs
                      (disambiguate.py); no re-extraction needed.
  garbage_ratio_field reported CD ratio is 0 / 1.0 / absurd (>250) while the
                      amounts are plausible — the ratio column wasn't parsed.
  unit_mismatch       computed vs reported differ by ~100x — a per-row crore/
                      lakh mix (Phase-2 units).
  parse_misalign      amounts and ratio disagree by a middling factor — a real
                      column misalignment; needs re-extract + source check.
  marginal_definitional  small, consistent gap — likely a definitional CD-ratio
                      difference (different advance base); adjudicate, likely accept.

    python3 audit/triage.py     # -> audit/triage.csv (per cause) + audit/triage_rows.csv (per cell)
"""
import csv, glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify as V
import unit_resolver as UR

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIX = {
    "header_collapse":       ("recoverable", "disambiguate headers -> re-derive complete.json/timeseries", "HIGH"),
    "garbage_ratio_field":   ("partial",     "derive CD ratio from adv/dep (sanity-bounded) or re-extract quarter", "MEDIUM"),
    "unit_mismatch":         ("recoverable", "apply per-row crore->lakh normalisation (Phase 2 units)", "MEDIUM"),
    "parse_misalign":        ("needs_reextract", "re-extract table + verify against source PDF (dual extract)", "HIGH"),
    "marginal_definitional": ("accept?",     "adjudicate vs source; likely a definitional CD-ratio difference", "LOW"),
}


def _t_cols(fields):
    return [f for f in fields if f.endswith("_t")]


def classify_achievement(row, fields):
    """Does a/pct reconcile with SOME _t column (=> collapse), or nothing?"""
    a, pct = UR._num(row.get("a")), UR._num(row.get("pct"))
    if a is None or pct is None:
        return "parse_misalign"
    for tc in _t_cols(fields):
        tv = UR._num(row.get(tc))
        if tv and tv > 0 and V._close(a / tv * 100, pct, 0.05, 2.0):
            return "header_collapse"
    return "parse_misalign"


def classify_ratio(dep, adv, cdr):
    comp = adv / dep * 100
    r = comp / cdr if cdr else 0
    if cdr <= 1.5 or cdr > 250:
        return "garbage_ratio_field"
    if 0.008 <= r <= 0.012 or 80 <= r <= 120:
        return "unit_mismatch"
    if 0.75 <= r <= 1.33:
        return "marginal_definitional"
    return "parse_misalign"


def main():
    per_cell, per_cause = [], {}   # per_cause: (table,cause) -> count
    for cj in sorted(glob.glob(os.path.join(REPO, "public/slbc-data/*/*_complete.json"))):
        slug = os.path.basename(cj).replace("_complete.json", "")
        if slug == "tamilnadu":
            continue
        complete = json.load(open(cj))
        for period, cat, dname, row, fields in V._iter_rows(complete):
            roles = V.find_roles(fields)
            for check, ok, detail in V.reconcile_row(row, roles):
                if ok:
                    continue
                if check == "achievement_pct":
                    cause = classify_achievement(row, fields)
                elif check == "ratio":
                    dep, adv, cdr = (UR._num(row.get(roles["deposit"])),
                                     UR._num(row.get(roles["advance"])),
                                     UR._num(row.get(roles["cd_ratio"])))
                    cause = classify_ratio(dep, adv, cdr)
                else:
                    cause = "parse_misalign"
                tid = f"{slug}__{cat}"
                per_cause[(tid, check, cause)] = per_cause.get((tid, check, cause), 0) + 1
                per_cell.append({"table_id": tid, "check": check, "quarter": period,
                                 "district": dname, "cause": cause, "detail": detail})

    # per-cell worklist
    with open(os.path.join(REPO, "audit", "triage_rows.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["table_id", "check", "quarter", "district", "cause", "detail"])
        w.writeheader()
        w.writerows(per_cell)

    # per (table, cause) rollup
    rollup = []
    for (tid, check, cause), n in sorted(per_cause.items(), key=lambda x: -x[1]):
        rec, fix, prio = FIX[cause]
        rollup.append({"table_id": tid, "check": check, "cause": cause, "n_cells": n,
                       "recoverable": rec, "priority": prio, "fix": fix})
    with open(os.path.join(REPO, "audit", "triage.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["table_id", "check", "cause", "n_cells",
                                           "recoverable", "priority", "fix"])
        w.writeheader()
        w.writerows(rollup)

    # console summary by cause
    by_cause = {}
    for r in rollup:
        c = by_cause.setdefault(r["cause"], [0, set(), FIX[r["cause"]]])
        c[0] += r["n_cells"]
        c[1].add(r["table_id"])
    total = sum(c[0] for c in by_cause.values())
    order = ["header_collapse", "parse_misalign", "garbage_ratio_field", "unit_mismatch", "marginal_definitional"]
    print(f"{'root cause':22}{'cells':>7}{'tables':>8}  {'prio':6} fix")
    print("-" * 96)
    for cause in order:
        if cause not in by_cause:
            continue
        n, tids, (rec, fix, prio) = by_cause[cause]
        print(f"{cause:22}{n:>7}{len(tids):>8}  {prio:6} {fix[:52]}")
        print(f"{'':22}{'':>7}{'':>8}  [{rec}] {sorted(tids)}")
    print("-" * 96)
    print(f"{'TOTAL':22}{total:>7}")
    recov = sum(c[0] for cause, c in by_cause.items()
                if FIX[cause][0] in ("recoverable",))
    print(f"\n{recov}/{total} cells ({recov/total*100:.0f}%) are recoverable without re-extraction "
          f"(header collapse + unit normalisation).")
    print("wrote audit/triage.csv, audit/triage_rows.csv")


if __name__ == "__main__":
    main()
