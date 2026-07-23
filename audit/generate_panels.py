"""Reproduce the site's *download surface* for repo-wide auditing.

The website's per-indicator download (StateDownload.svelte -> downloadIndicator)
builds a multi-quarter panel on the fly from each state's `_complete.json`:
headers = [quarter, as_on_date, fy, district, <union of category fields>], one
row per (quarter, district). This script regenerates those exact panels for
EVERY state x category, so `finer_audit.py` can be run over what users actually
get -- collapse and all.

Important: panels are the POST-collapse artifact. Duplicate `a`/`pct`/`amt`
columns have already been eaten by the dict-keyed `_complete.json`, so they
surface here as ORPHAN_COL, not DUP_HEADER. The duplicate-header *cause* lives
in the raw quarterly CSVs (public/slbc-data/<state>/quarterly/**) -- audit those
separately.

Usage:
    python3 audit/generate_panels.py [out_dir]      # default: audit/panels
    FINER_NOW=2026,2 python3 audit/finer_audit.py audit/panels --json
"""
import json, csv, glob, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iter_dists(dists):
    """Yield (district_name, values_dict) from either dict- or list-shaped
    district containers found across states' `_complete.json`."""
    if isinstance(dists, dict):
        for k, v in dists.items():
            if isinstance(v, dict):
                yield k, v
    elif isinstance(dists, list):
        for v in dists:
            if isinstance(v, dict):
                yield (v.get("district") or v.get("DISTRICT") or v.get("name") or ""), v


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    n_states = n_tables = 0
    for cj in sorted(glob.glob(os.path.join(REPO, "public/slbc-data/*/*_complete.json"))):
        slug = os.path.basename(cj).replace("_complete.json", "")
        try:
            d = json.load(open(cj))
        except Exception as e:
            print("SKIP", cj, e)
            continue
        quarters = d.get("quarters", {})
        if not quarters:
            continue
        qkeys = sorted(quarters.keys())
        cats = set()
        for q in quarters.values():
            cats.update((q.get("tables") or {}).keys())
        n_states += 1
        for cat in sorted(cats):
            fields, seen = [], set()          # dedup, insertion order == the JS Set
            for qk in qkeys:
                tbl = (quarters[qk].get("tables") or {}).get(cat)
                if not tbl:
                    continue
                for f in (tbl.get("fields") or []):
                    if f not in seen:
                        seen.add(f)
                        fields.append(f)
            headers = ["quarter", "as_on_date", "fy", "district"] + fields
            rows = []
            for qk in qkeys:
                q = quarters[qk]
                tbl = (q.get("tables") or {}).get(cat)
                if not tbl:
                    continue
                dists = tbl.get("districts")
                if dists is None:
                    dists = tbl.get("data")
                for dist, vals in iter_dists(dists):
                    row = [q.get("period") or qk, q.get("as_on_date") or qk, q.get("fy") or "", dist]
                    for f in fields:
                        row.append(str(vals.get(f, "")))
                    rows.append(row)
            if not rows:
                continue
            with open(os.path.join(outdir, f"{slug}_{cat}.csv"), "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(headers)
                w.writerows(rows)
            n_tables += 1
    print(f"Generated {n_tables} download panels across {n_states} states -> {outdir}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "audit", "panels"))
