"""Build the source catalogue — the durable "where does every state's SLBC
source live" map (Phase 1, precursor to artifact 1.5).

You cannot harvest what you cannot locate. This mines three discovery sources
already in the repo — no network — into one row-per-source-location table:

  1. src/lib/indicator-sources.ts  -> SLBC_STATE_URLS: live portal + aliasUrls
  2. public/sources/wayback.json    -> latest archived snapshot + per-host CDX
                                       snapshot counts and date span
  3. slbc-data/<state>/extract_*.py -> URLs hardcoded in the extractors

It also scores per-state source coverage and flags ORPHANS (Phase 1 step 3:
tables with no locatable source must be quarantined or deprecated).

    python3 audit/build_source_catalogue.py
    # -> audit/source_catalogue.csv  (every located source, one row each)
    # -> audit/source_coverage.csv   (per-state rollup + orphan flag)
"""
import json, os, re, csv, glob, subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS = os.path.join(REPO, "src/lib/indicator-sources.ts")
WB = os.path.join(REPO, "public/sources/wayback.json")

# state entries in SLBC_STATE_URLS: 'slug': { name: '..', url: '..', aliasUrls: [..] }
_ENTRY = re.compile(
    r"'([a-z][a-z-]+)':\s*\{\s*name:\s*'([^']*)',\s*url:\s*'([^']*)'"
    r"(?:\s*,\s*aliasUrls:\s*\[([^\]]*)\])?", re.S)
_URL = re.compile(r"https?://[A-Za-z0-9./_%*?=&:+~-]+")


def parse_state_urls():
    """slug -> {name, url, aliases[]} from the TS map."""
    if not os.path.exists(TS):
        return {}
    txt = open(TS, encoding="utf-8").read()
    out = {}
    for slug, name, url, aliases in _ENTRY.findall(txt):
        al = [u.strip().strip("'\"") for u in aliases.split(",") if u.strip()] if aliases else []
        out[slug] = {"name": name, "url": url, "aliases": al}
    return out


def load_wayback():
    if not os.path.exists(WB):
        return {}
    d = json.load(open(WB))
    return d.get("states", {})


def extractor_urls(slug):
    """Distinct http(s) URLs hardcoded in a state's extractor scripts."""
    urls = set()
    for py in glob.glob(os.path.join(REPO, "slbc-data", slug, "*.py")):
        try:
            for m in _URL.findall(open(py, encoding="utf-8", errors="ignore").read()):
                # skip obvious non-source noise
                if "web.archive.org" in m or "slbc" in m or "bank" in m or "nic.in" in m:
                    urls.add(m.rstrip(".,)'\""))
        except OSError:
            pass
    return sorted(urls)


def is_live_domain(url):
    """A real fetchable host, as opposed to a Wayback wildcard placeholder
    (some states' 'live' portal in the TS map is already a web.archive URL,
    which itself signals the live site is gone)."""
    return url.startswith("http") and "web.archive.org" not in url and "*" not in url


def main():
    states = parse_state_urls()
    wb = load_wayback()
    slugs = sorted(set(states) | set(wb))

    rows, coverage = [], []
    for slug in slugs:
        st = states.get(slug, {})
        name = st.get("name", slug)
        located = []

        if st.get("url"):
            kind = "live_portal" if is_live_domain(st["url"]) else "wayback_wildcard"
            rows.append([slug, name, kind, st["url"], "indicator-sources.ts"])
            located.append(kind)
        for a in st.get("aliases", []):
            rows.append([slug, name, "live_alias", a, "indicator-sources.ts:aliasUrls"])
            located.append("live_alias")

        w = wb.get(slug, {})
        latest = (w.get("latest") or {}).get("url")
        if latest:
            rows.append([slug, name, "wayback_latest", latest,
                         f"wayback.json:latest {(w['latest'].get('date') or '')}"])
        best_snaps, oldest = 0, ""
        for v in (w.get("variants") or []):
            n = v.get("snapshotCount") or 0
            rows.append([slug, name, "wayback_cdx_host", v.get("host", ""),
                         f"snapshots={n} span={v.get('oldestDate','?')}..{v.get('newestDate','?')}"])
            if n > best_snaps:
                best_snaps, oldest = n, v.get("oldestDate", "")

        for u in extractor_urls(slug):
            rows.append([slug, name, "extractor_url", u, "slbc-data/<state>/*.py"])

        live = is_live_domain(st.get("url", ""))
        # actionable buckets, not one vague "thin":
        #   ok               live portal + deep archive — safest
        #   archive_only     live site gone, but Wayback has history (harvest WB)
        #   live_only_fragile live works, ~no archive — ROT RISK, snapshot now
        #   ORPHAN           neither — unverifiable, quarantine/deprecate
        if live and best_snaps >= 20:
            risk = "ok"
        elif not live and best_snaps >= 20:
            risk = "archive_only"
        elif live and best_snaps < 5:
            risk = "live_only_fragile"
        elif not live and best_snaps < 5:
            risk = "ORPHAN"
        else:
            risk = "thin"
        coverage.append({
            "state": slug, "name": name,
            "live_portal": st.get("url", "") if is_live_domain(st.get("url", "")) else "",
            "n_aliases": len(st.get("aliases", [])),
            "wayback_snapshots_best": best_snaps, "wayback_oldest": oldest,
            "n_extractor_urls": len(extractor_urls(slug)),
            "coverage": risk,
        })

    with open(os.path.join(REPO, "audit", "source_catalogue.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["state", "name", "kind", "url_or_host", "evidence"])
        w.writerows(rows)
    cov_cols = ["state", "name", "live_portal", "n_aliases", "wayback_snapshots_best",
                "wayback_oldest", "n_extractor_urls", "coverage"]
    with open(os.path.join(REPO, "audit", "source_coverage.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cov_cols)
        w.writeheader()
        w.writerows(coverage)

    order = {"ORPHAN": 0, "live_only_fragile": 1, "thin": 2, "archive_only": 3, "ok": 4}
    coverage.sort(key=lambda c: (order.get(c["coverage"], 9), c["state"]))
    print(f"{'state':18}{'live?':6}{'wb_snaps':>9}{'oldest':>12}{'extr':>6}  coverage")
    for c in coverage:
        print(f"{c['state']:18}{'yes' if c['live_portal'] else 'no':6}"
              f"{c['wayback_snapshots_best']:>9}{c['wayback_oldest']:>12}"
              f"{c['n_extractor_urls']:>6}  {c['coverage']}")
    buckets = {}
    for c in coverage:
        buckets.setdefault(c["coverage"], []).append(c["state"])
    print(f"\n{len(rows)} located sources across {len(slugs)} states.")
    for b in ("ORPHAN", "live_only_fragile", "archive_only", "thin", "ok"):
        if buckets.get(b):
            print(f"  {b:18} {len(buckets[b]):>2}  {buckets[b]}")
    print("\nPriority: live_only_fragile states have a working site but ~no archive —")
    print("snapshot them FIRST (risk register: sources rot). wrote source_catalogue.csv + source_coverage.csv")


if __name__ == "__main__":
    main()
