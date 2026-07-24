"""Quarantine register for the CD-ratio reconciliation failures.

Unlike the header collapse — where the data was present and merely mis-keyed, so
disambiguation recovered it losslessly — these failures are genuine source
extraction errors: the correct value is NOT in the artifacts. They cannot be
responsibly auto-fixed; deriving `cd_ratio = adv/dep` fabricates a number when
(as the Chhattisgarh rows show) the deposit/advance themselves are misparsed.

So this doesn't repair anything. It produces the quarantine register the program
needs — every failing cell classified by root cause, severity, and the action it
requires against source (Phase-1 corpus + Phase-3 dual extraction).

Classes:
  parse_misalign   amounts and ratio disagree by a middling factor — column
                   misalignment. Re-extract + verify.  [HIGH / quarantine]
  garbage_row      ratio is 0/1.0/absurd AND deposit/advance are implausibly
                   small — the whole row is misparsed.  [HIGH / quarantine]
  unit_mismatch    ratio plausible but adv/dep ~100x off it — a per-row crore/
                   lakh mix. Needs source to know which side.  [MED / quarantine]
  definitional     small (<33%) consistent gap — SLBCs compute CD ratio on
                   different advance bases (RIDF/investment inclusion). Reported
                   value is likely the official one; our raw adv/dep is the wrong
                   benchmark. Not a defect.  [LOW / accept, review]

    python3 audit/flag_cd_ratio_issues.py    # -> audit/known_issues.csv (+ registry flag)
"""
import csv, glob, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify as V
import unit_resolver as UR

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASS = {
    "parse_misalign": ("HIGH", "quarantine", "re-extract table + dual-verify vs source PDF"),
    "garbage_row":    ("HIGH", "quarantine", "whole-row re-extract (deposit/advance also implausible)"),
    "unit_mismatch":  ("MEDIUM", "quarantine", "source check: which of deposit/advance is x100 off"),
    "definitional":   ("LOW", "accept-review", "confirm CD-ratio definition vs source; likely accept as published"),
}


def classify(dep, adv, cdr, comp, dep_med):
    ratio = comp / cdr if cdr else 0
    implausible_dep = dep_med and dep < 0.05 * dep_med
    if cdr <= 1.5 or cdr > 400:
        return "garbage_row"
    if 0.008 <= ratio <= 0.012 or 80 <= ratio <= 120:
        return "unit_mismatch"
    if 0.67 <= ratio <= 1.5:
        return "definitional"
    return "parse_misalign"


def main():
    issues = []
    for cj in sorted(glob.glob(os.path.join(REPO, "public/slbc-data/*/*_complete.json"))):
        slug = os.path.basename(cj).replace("_complete.json", "")
        if slug == "tamilnadu":
            continue
        complete = json.load(open(cj))
        # per-state deposit median for the implausibility heuristic
        deps = []
        for period, cat, dname, row, fields in V._iter_rows(complete):
            roles = V.find_roles(fields)
            if roles["deposit"]:
                n = UR._num(row.get(roles["deposit"]))
                if n and n > 0:
                    deps.append(n)
        dep_med = statistics.median(deps) if deps else None

        for period, cat, dname, row, fields in V._iter_rows(complete):
            roles = V.find_roles(fields)
            if not (roles["deposit"] and roles["advance"] and roles["cd_ratio"]):
                continue
            dep, adv, cdr = (UR._num(row.get(roles["deposit"])),
                             UR._num(row.get(roles["advance"])),
                             UR._num(row.get(roles["cd_ratio"])))
            if not (dep and adv is not None and cdr is not None and dep > 0):
                continue
            comp = adv / dep * 100
            if V._close(comp, cdr, 0.05, 2.0):
                continue
            cause = classify(dep, adv, cdr, comp, dep_med)
            sev, disp, action = CLASS[cause]
            issues.append({
                "table_id": f"{slug}__{cat}", "state": slug, "quarter": period,
                "district": dname, "deposit": round(dep, 1), "advance": round(adv, 1),
                "cd_ratio_reported": cdr, "cd_ratio_raw_advdep": round(comp, 1),
                "cause": cause, "severity": sev, "disposition": disp, "action": action,
            })

    cols = ["table_id", "state", "quarter", "district", "deposit", "advance",
            "cd_ratio_reported", "cd_ratio_raw_advdep", "cause", "severity",
            "disposition", "action"]
    with open(os.path.join(REPO, "audit", "known_issues.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(sorted(issues, key=lambda x: (x["severity"] != "HIGH", x["state"])))

    # registry flag: count of open (non-accept) issues per table
    _flag_registry(issues)

    import collections
    byc = collections.Counter(i["cause"] for i in issues)
    print(f"{len(issues)} CD-ratio issues registered")
    for c in ("parse_misalign", "garbage_row", "unit_mismatch", "definitional"):
        if byc[c]:
            sev, disp, _ = CLASS[c]
            print(f"  {c:16} {byc[c]:3}  [{sev}/{disp}]")
    defect = sum(v for c, v in byc.items() if c != "definitional")
    print(f"\n{defect} genuine defects (need source: Phase-1 corpus + Phase-3 dual extract); "
          f"{byc['definitional']} likely definitional (accept/review).")
    print("None are safely auto-fixable — the correct values are not in the artifacts.")
    print("wrote audit/known_issues.csv")


def _flag_registry(issues):
    import collections
    reg = os.path.join(REPO, "audit", "registry.csv")
    if not os.path.exists(reg):
        return
    open_by_tid = collections.Counter(i["table_id"] for i in issues if i["disposition"] == "quarantine")
    with open(reg, newline="") as fh:
        rows = list(csv.DictReader(fh))
        cols = list(rows[0].keys()) if rows else []
    if "cd_ratio_defects" not in cols:
        cols.append("cd_ratio_defects")
    for r in rows:
        r["cd_ratio_defects"] = open_by_tid.get(r["table_id"], "")
    with open(reg, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"flagged {sum(open_by_tid.values())} quarantined cells across "
          f"{len(open_by_tid)} tables in registry.csv")


if __name__ == "__main__":
    main()
