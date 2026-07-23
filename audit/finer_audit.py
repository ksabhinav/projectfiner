"""FINER project-wide auditor: integrity + usefulness + arrangement.

Usage:
    python3 finer_audit.py <files-or-dirs>...
    python3 finer_audit.py repo/data/**/*.csv --csv report.csv

Three independent scores per table (0-100). Integrity asks "are the values
right?"; Usefulness asks "can anyone actually analyse this?"; Arrangement asks
"is it machine-readable and consistent with the rest of the project?"
A table can be perfectly correct and still useless (see: empty files that pass
every integrity check).
"""
import csv, os, re, sys, glob, json
from collections import Counter, defaultdict

KEY = {"quarter", "as_on_date", "fy", "district"}
ORDER = ["March", "June", "September", "December"]
ORPHAN_TOK = {"a","pct","amt","amount","no","atm","bc_outlets","target","achv",
              "achv_no","disbursed_no","of_achievement_no","ach","achievement"}
MONTH = re.compile(r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)_\d{2}$")
TRAIL = re.compile(r"_\d{3,}$")          # 3+ digits = likely an absorbed value
ISO   = re.compile(r"^\d{2}-\d{2}-\d{4}$")
SLUG  = re.compile(r"^[a-z]+_\d{4}$")
# current-ish quarter for staleness, override with FINER_NOW
NOW = tuple(int(x) for x in os.environ.get("FINER_NOW", "2026,1").split(","))

# district counts for coverage assessment (2025 admin boundaries)
DISTRICTS = {"arunachal-pradesh":25,"goa":2,"kerala":14,"madhya-pradesh":55,
             "nagaland":16,"odisha":30,"punjab":23,"west-bengal":23,"bihar":38,
             "jharkhand":24,"assam":35,"meghalaya":12}


_MQ = {"january":0,"february":0,"march":0,"april":1,"may":1,"june":1,
       "july":2,"august":2,"september":2,"october":3,"november":3,"december":3}
def qk(q):
    # tolerant: bucket any month into its calendar quarter (real data carries a
    # few non-standard labels in HP/Kerala). Standard quarter-end months are
    # unchanged. Falls back to (0,0) for unparseable labels.
    p = q.split()
    try:
        return (int(p[1]), _MQ[p[0].lower()])
    except (IndexError, KeyError, ValueError):
        return (0, 0)


def span(qs):
    a, b = qk(qs[0]), qk(qs[-1])
    out, (y, i) = [], a
    while (y, i) <= b:
        out.append(f"{ORDER[i]} {y}")
        i += 1
        if i == 4:
            i, y = 0, y + 1
    return out


def audit(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return None
    hdr, body = rows[0], rows[1:]
    name = os.path.basename(path)
    state = name.split("_")[0]
    R = {"file": name, "state": state, "rows": len(body), "cols": len(hdr),
         "integrity": [], "useful": [], "arrange": []}
    idx = {h: i for i, h in enumerate(hdr)}
    di, qi = idx.get("district"), idx.get("quarter")
    datacols = [i for i, h in enumerate(hdr) if h not in KEY and h != "District"]

    # ---------------- INTEGRITY ----------------
    dups = {h: c for h, c in Counter(hdr).items() if c > 1}
    if dups:
        R["integrity"].append(("DUP_HEADER", f"{sum(dups.values())-len(dups)} cols collapse on dict-keying: {list(dups)[:3]}"))

    per_q = defaultdict(set)
    if di is not None and qi is not None:
        for r in body:
            if len(r) > max(di, qi):
                per_q[r[qi]].add(r[di])
    qs = sorted(per_q, key=qk) if per_q else []

    # transient absence = real bug; monotone = genuine district creation
    if len(qs) > 2:
        alld = set().union(*per_q.values())
        trans = []
        for d in alld:
            pres = [d in per_q[q] for q in qs]
            f, l = pres.index(True), len(pres)-1-pres[::-1].index(True)
            gaps = [qs[i] for i in range(f, l+1) if not pres[i]]
            if gaps:
                trans.append((d, gaps))
        if trans:
            R["integrity"].append(("TRANSIENT_GAP", f"district vanishes then returns (bug): {trans[:3]}"))

    ate = [h for h in hdr if h not in KEY and TRAIL.search(h)]
    if ate and any(len(per_q[q]) < max(len(v) for v in per_q.values()) for q in per_q):
        R["integrity"].append(("HEADER_ATE_ROW", f"header carries data values + row shortfall: {ate[:3]}"))

    if di is not None and qi is not None:
        k = Counter((r[qi], r[di]) for r in body if len(r) > max(qi, di))
        d2 = [x for x, c in k.items() if c > 1]
        if d2:
            R["integrity"].append(("DUP_KEY", f"{len(d2)} duplicate (quarter,district) rows"))

    negs = []
    for i in datacols:
        for r in body:
            if len(r) > i:
                try:
                    if float(r[i]) < 0:
                        negs.append(hdr[i]); break
                except: pass
    if negs:
        R["integrity"].append(("NEGATIVE", f"negative values in {negs[:3]}"))

    # ---------------- USEFULNESS ----------------
    filled = sum(1 for r in body for i in datacols if len(r) > i and r[i].strip())
    cells = len(body) * len(datacols) if body and datacols else 0
    fill = filled / cells * 100 if cells else 0
    R["fill"] = round(fill, 1)

    if filled == 0:
        R["useful"].append(("NO_DATA", "zero measurements — scaffolding only"))
    elif fill < 50:
        R["useful"].append(("SPARSE", f"fill {fill:.0f}% — concept re-columned per vintage"))

    # trendability: any single column with >=4 contiguous quarters?
    best = 0
    for i in datacols:
        have = sorted({r[qi] for r in body if len(r) > max(i, qi) and r[i].strip()}, key=qk) if qi is not None else []
        if len(have) < 2: 
            best = max(best, len(have)); continue
        full = span(have)
        run = mx = 0
        for q in full:
            run = run + 1 if q in have else 0
            mx = max(mx, run)
        best = max(best, mx)
    R["trend_run"] = best
    if best < 4:
        R["useful"].append(("NO_TREND", f"longest contiguous run on any single column = {best}q (need 4+)"))

    # district coverage vs state reality
    if qs:
        obs = max(len(v) for v in per_q.values())
        exp = DISTRICTS.get(state)
        if exp and obs < exp * 0.9:
            R["useful"].append(("PARTIAL_DISTRICTS", f"{obs}/{exp} districts covered"))

    # staleness
    if qs:
        ly, lq = qk(qs[-1])
        age = (NOW[0]-ly)*4 + (NOW[1]-lq)
        R["last"] = qs[-1]
        if age >= 8:
            R["useful"].append(("STALE", f"last data {qs[-1]} (~{age} quarters old)"))
    R["quarters"] = len(qs)

    # target/achievement pairing enables performance analysis
    low = " ".join(h.lower() for h in hdr)
    has_t = any(k in low for k in ("target", "_t"))
    has_a = any(k in low for k in ("achiev", "ach", "_a", "disburs"))
    if has_t and not has_a:
        R["useful"].append(("TARGET_ONLY", "targets without achievement — no performance measure"))

    # units are never declared anywhere
    if not any(u in low for u in ("lakh", "crore", "rs", "inr", "unit", "amount_")) and datacols:
        R["useful"].append(("NO_UNITS", "no unit declared (Rs lakh? crore? counts?) — values not interpretable"))

    # ---------------- ARRANGEMENT ----------------
    if "District" in hdr and di is not None:
        same = sum(1 for r in body if len(r) > max(di, idx["District"]) and r[di].strip() == r[idx["District"]].strip())
        R["arrange"].append(("REDUNDANT_COL", f"'District' duplicates 'district' in {same}/{len(body)} rows"))

    bad = [h for h in hdr if h != h.strip().lower().replace(" ", "_") and h not in KEY]
    if bad:
        R["arrange"].append(("HEADER_STYLE", f"{len(bad)} non-snake_case headers: {[b[:22] for b in bad[:3]]}"))
    nl = [h for h in hdr if "\n" in h or "\r" in h]
    if nl:
        R["arrange"].append(("HEADER_NEWLINE", f"{len(nl)} headers contain newlines: {[repr(x)[:26] for x in nl[:2]]}"))
    if "" in hdr:
        R["arrange"].append(("BLANK_HEADER", f"{hdr.count('')} unnamed column(s)"))

    orph = [h for h in hdr if h.strip().lower() in ORPHAN_TOK or MONTH.match(h)]
    if orph:
        R["arrange"].append(("ORPHAN_COL", f"sub-columns with no parent: {orph[:5]}"))

    ai = idx.get("as_on_date")
    if ai is not None and body:
        v = [r[ai] for r in body if len(r) > ai and r[ai].strip()]
        if v:
            fmt = "ISO-ish" if ISO.match(v[0]) else ("slug" if SLUG.match(v[0]) else "other")
            R["date_fmt"] = fmt
            if fmt != "ISO-ish":
                R["arrange"].append(("DATE_FORMAT", f"as_on_date is '{v[0]}' ({fmt}), not a parseable date"))

    fi = idx.get("fy")
    if fi is not None and body and not any(len(r) > fi and r[fi].strip() for r in body):
        R["arrange"].append(("FY_NULL", "fy column present but 100% empty"))

    nulls = [hdr[i] for i in datacols if not any(len(r) > i and r[i].strip() for r in body)]
    if nulls:
        R["arrange"].append(("NULL_COL", f"{len(nulls)} all-null column(s): {nulls[:3]}"))

    for dim in ("integrity", "useful", "arrange"):
        R[dim + "_score"] = max(0, 100 - 25 * len(R[dim]))
    R["codepath"] = ("A/raw" if "District" in hdr else
                     "B/slug" if R.get("date_fmt") == "slug" else "hybrid")
    return R


def main(paths):
    files = []
    for p in paths:
        files += glob.glob(os.path.join(p, "**", "*.csv"), recursive=True) if os.path.isdir(p) else [p]
    res = [r for r in (audit(f) for f in sorted(set(files))) if r]

    print(f"{'file':42}{'path':8}{'int':>5}{'use':>5}{'arr':>5}{'fill':>7}{'q':>4}{'run':>5}  top issue")
    print("-"*112)
    for r in res:
        top = (r["integrity"] or r["useful"] or r["arrange"] or [("OK","")])[0][0]
        print(f"{r['file'][:41]:42}{r['codepath']:8}{r['integrity_score']:>5}{r['useful_score']:>5}"
              f"{r['arrange_score']:>5}{r.get('fill',0):>6}%{r.get('quarters',0):>4}{r.get('trend_run',0):>5}  {top}")

    print("\n" + "="*112)
    agg = Counter()
    for r in res:
        for dim in ("integrity","useful","arrange"):
            for c,_ in r[dim]: agg[(dim,c)] += 1
    n = len(res)
    for dim in ("integrity","useful","arrange"):
        print(f"\n{dim.upper()}  (mean score {sum(x[dim+'_score'] for x in res)/n:.0f}/100)")
        for (d,c),k in sorted(agg.items(), key=lambda x:-x[1]):
            if d == dim: print(f"   {c:18} {k:>3}/{n} files")
    print(f"\ncodepaths: {dict(Counter(r['codepath'] for r in res))}")
    return res


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    res = main(args or ["."])
    if "--json" in sys.argv:
        json.dump(res, open("finer_audit_report.json","w"), indent=1)
        print("\nwrote finer_audit_report.json")
