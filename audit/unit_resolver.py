"""FINER unit resolver — Phase 2, artifact 1.2 (`units.yaml`).

Resolves the unit of every column in every table by three tiers of decreasing
authority (program doc §4):

  1. CAPTION  — the source SLBC PDF almost always prints the unit in a caption
                band above the table: "(Amount in Rs. Crore)", "(Rs. in lakh)",
                "No. in actuals". Authoritative. Runs once the source harvester
                (Phase 1) has populated `sources/`. Built + unit-tested here;
                yields nothing until PDFs exist.
  2. MAGNITUDE— anchor on the canonical per-district total-deposit value and
                bucket lakh vs crore by magnitude. Medium confidence; column-
                semantics-sensitive, so it anchors on ONE fixed column and
                applies the inferred scale table-wide (a booklet declares its
                unit once). Runs now.
  3. DOCTRINE — FINER's stated canonical is Rs. lakh. Used only to flag
                CONFLICTS (data magnitude disagrees with the canonical claim),
                never as a positive unit source.

Column KIND (money / count / percent / ratio) is classified from the header
alone at high confidence — this is the half of the units problem that needs no
PDF, and it is what stops normalisation ever touching a count or a percentage.

Usage:
    python3 audit/unit_resolver.py                 # writes audit/units.yaml + audit/unit_findings.csv
    python3 audit/unit_resolver.py --sources sources   # also try caption tier
    python3 audit/test_unit_resolver.py            # tier-1 + classifier tests (no PDFs needed)
"""
import json, glob, os, re, csv, statistics, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANONICAL = "lakh"                       # FINER doctrine
TO_LAKH = {"crore": 100.0, "lakh": 1.0, "thousand": 0.01, "actual": 1e-5}

# ---------------------------------------------------------------- column kind
_PCT  = re.compile(r"(?:^|_)(pct|percent|percentage|ratio|cdr)(?:_|$)|c_?d_?ratio", re.I)
_CNT  = re.compile(r"(?:^|_)(no|nos|number|count|cnt|a_c|ac|accounts?|branch(?:es)?|"
                   r"atms?|outlets?|cards?|members?|groups?|beneficiaries|enrolled|units?)(?:_|$)", re.I)
_MONEY = re.compile(r"(?:^|_)(amt|amount|deposit|deposits|advance[sd]?|credit|disburs\w*|"
                    r"sanction\w*|outstanding|o_s|loan|limit|balance|npa|target|achiev\w*|"
                    r"disbursed|ps|agri|msme)(?:_|$)|_t$", re.I)


def classify_kind(col):
    """money | count | percent | ratio_or_other. Precedence: percent > count >
    money, so `achv_pct_amt` reads as a percentage and `target_no` as a count."""
    c = col.strip().lower()
    if _PCT.search(c):
        return "percent"
    if _CNT.search(c):
        return "count"
    if _MONEY.search(c):
        return "money"
    return "other"


# ------------------------------------------------------------- tier 1: caption
# scale keyword -> canonical scale token
_CAPTION_RES = [
    (re.compile(r"in\s*(?:rs\.?|inr|₹|rupees?)?\s*['’]?000|in\s*thousands?", re.I), "thousand"),
    (re.compile(r"\bcrores?\b|\bcr\b\.?", re.I), "crore"),
    (re.compile(r"(?:rs\.?|inr|₹|amount|amt\.?)[^\n]{0,18}?\bla(?:kh|c)s?\b|\bin\s*la(?:kh|c)s?\b", re.I), "lakh"),
    (re.compile(r"in\s*(?:actual|absolute)s?|no\.?\s*in\s*actuals?|figures?\s*in\s*(?:rs\.?|₹)\b(?!.*(?:lakh|crore|lac|thousand))", re.I), "actual"),
]


def parse_unit_caption(text):
    """Tier-1 core: pull a monetary scale out of a caption/header text band.
    Returns {'scale':..., 'evidence':...} or None. Pure + unit-tested."""
    if not text:
        return None
    flat = re.sub(r"\s+", " ", text)
    for rx, scale in _CAPTION_RES:
        m = rx.search(flat)
        if m:
            s, e = m.span()
            return {"scale": scale, "evidence": flat[max(0, s - 12):e + 12].strip()}
    return None


def _pdf_text(pdf_path, page=None):
    """Best-effort PDF text. Prefers `pdftotext -layout` (poppler); falls back to
    pdfplumber. Returns '' if neither the file nor a reader is available."""
    if not os.path.exists(pdf_path):
        return ""
    args = ["pdftotext", "-layout"]
    if page:
        args += ["-f", str(page), "-l", str(page)]
    try:
        return subprocess.run(args + [pdf_path, "-"], capture_output=True, text=True, timeout=60).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages = [pdf.pages[page - 1]] if page else pdf.pages
            return "\n".join((p.extract_text() or "") for p in pages)
    except Exception:
        return ""


def pdf_caption_scale(pdf_path, page=None):
    """Tier-1 driver: scan a source PDF's text for a unit caption."""
    return parse_unit_caption(_pdf_text(pdf_path, page))


# --------------------------------------------------------- tier 2: magnitude
# canonical per-district total-deposit anchor lives in the CD-ratio category.
# Field names are normalised first, because raw-header states carry "Total
# Deposit" (spaces, title-case) rather than snake_case total_deposit.
_CD_CATS = ["credit_deposit_ratio", "cd_ratio", "credit_deposit_ratio_2"]
# exact normalised names for a single district total (tried in order, deposit
# before advance — both co-scale, deposit is the cleaner anchor)
_TOTAL_ANCHORS = ["total_deposit", "total_deposits", "deposit", "deposits",
                  "deposit_amount_d", "total_dep", "aggregate_deposit",
                  "total_advance", "total_advances", "advance", "advances",
                  "advance_amount_a"]
# area-split fallback (summed per district) when no single total exists
_AREA_SETS = [
    ("dep-area", ["dep_rural", "dep_semi_urban", "dep_urban"]),
    ("deposit-area", ["deposit_rural", "deposit_semi_urban", "deposit_urban"]),
    ("adv-area", ["adv_rural", "adv_semi_urban", "adv_urban"]),
]
# per-district branch count — the denominator for the size-invariant anchor
_BRANCH_CATS = ["branch_network", "branch_network_p2", "credit_deposit_ratio"]
_BRANCH_FIELDS = ["total_branch", "total_branches", "total", "no_of_branches",
                  "no_of_brs", "branch_total", "no_of_branch"]


def _norm(f):
    return re.sub(r"[^a-z0-9]+", "_", str(f).lower()).strip("_")


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _iter_dists(dists):
    if isinstance(dists, dict):
        for k, v in dists.items():
            if isinstance(v, dict):
                yield v
    elif isinstance(dists, list):
        for v in dists:
            if isinstance(v, dict):
                yield v


def _anchor_values(tbl):
    """Per-district anchor values from one CD table + a label, or (None,[])."""
    nmap = {_norm(f): f for f in (tbl.get("fields") or [])}
    dists = list(_iter_dists(tbl.get("districts") or {}))
    for name in _TOTAL_ANCHORS:                       # 1. a single total column
        if name in nmap:
            col = nmap[name]
            vals = [n for r in dists if (n := _num(r.get(col))) and n > 0]
            if vals:
                return name, vals
    for label, parts in _AREA_SETS:                   # 2. sum area splits
        cols = [nmap[p] for p in parts if p in nmap]
        if len(cols) >= 2:
            vals = []
            for r in dists:
                s = sum(n for c in cols if (n := _num(r.get(c))) and n > 0)
                if s > 0:
                    vals.append(s)
            if vals:
                return label, vals
    return None, []


def _branch_median(complete):
    """Median per-district branch count, for the size-invariant ratio."""
    vals = []
    for q in complete.get("quarters", {}).values():
        tabs = q.get("tables") or {}
        for cat in _BRANCH_CATS:
            if cat not in tabs:
                continue
            nmap = {_norm(f): f for f in (tabs[cat].get("fields") or [])}
            col = next((nmap[b] for b in _BRANCH_FIELDS if b in nmap), None)
            if not col:
                continue
            for r in _iter_dists(tabs[cat].get("districts") or {}):
                n = _num(r.get(col))
                if n and 0 < n < 100_000:
                    vals.append(n)
            break
    return statistics.median(vals) if vals else None


def magnitude_scale(complete):
    """Infer a state's money scale, preferring the size-invariant deposit/branch
    ratio (crore states cluster ~30-65, lakh states ~2.7k-27k -- a ~40x gap that
    cancels out state economy size). Falls back to bare deposit magnitude, which
    cannot separate a small state in lakh from a large one in crore, so that path
    is capped at low/medium confidence and flagged for caption confirmation."""
    vals, anchor = [], None
    for q in complete.get("quarters", {}).values():
        tabs = q.get("tables") or {}
        cat = next((c for c in _CD_CATS if c in tabs), None)
        if not cat:
            continue
        label, v = _anchor_values(tabs[cat])
        if v:
            anchor = f"{cat}.{label}"
            vals.extend(v)
    if not vals:
        return {"scale": None, "confidence": "none", "method": None, "anchor": None,
                "median": None, "ratio": None,
                "note": "no CD-ratio deposit/advance anchor — needs caption tier"}
    med = statistics.median(vals)
    br = _branch_median(complete)

    if br:                                            # size-invariant ratio path
        ratio = med / br
        scale = "crore" if ratio < 1_000 else "lakh"
        conf = "high" if (ratio < 300 or ratio > 1_800) else "medium"
        return {"scale": scale, "confidence": conf, "method": "deposit_per_branch",
                "anchor": anchor, "median": round(med, 1), "ratio": round(ratio, 1),
                "note": f"deposit/branch={ratio:,.0f} (branch median {br:,.0f})"}

    # magnitude-only fallback — size-confounded, so never high confidence
    scale = "crore" if med < 30_000 else "lakh"
    conf = "medium" if (med > 200_000 or med < 3_000) else "low"
    return {"scale": scale, "confidence": conf, "method": "deposit_magnitude",
            "anchor": anchor, "median": round(med, 1), "ratio": None,
            "note": "no branch anchor; magnitude cannot separate small-lakh from big-crore — confirm via caption"}


# ------------------------------------------------------------------- resolve
def resolve_state(complete, sources_dir=None, slug=None):
    mag = magnitude_scale(complete)

    caption = None
    if sources_dir and slug:
        for pdf in sorted(glob.glob(os.path.join(sources_dir, slug, "*.pdf"))):
            hit = pdf_caption_scale(pdf)
            if hit:
                caption = {**hit, "source_doc": os.path.relpath(pdf, REPO)}
                break

    # authority: caption > magnitude
    if caption:
        scale, source, conf, evidence = caption["scale"], "caption", "high", caption["evidence"]
    elif mag["scale"]:
        scale, source, conf = mag["scale"], mag["method"], mag["confidence"]
        evidence = f"{mag['anchor']}: {mag['note']}"
    else:
        scale, source, conf, evidence = None, "unknown", "none", mag["note"]

    # per-column kinds across every category
    cols = {}
    for q in complete.get("quarters", {}).values():
        for cat, tbl in (q.get("tables") or {}).items():
            for f in (tbl.get("fields") or []):
                cols.setdefault((cat, f), classify_kind(f))

    conflict = bool(scale and scale != CANONICAL and source != "unknown")
    return {
        "scale": scale, "unit_source": source, "confidence": conf, "evidence": evidence,
        "magnitude": mag, "caption": caption,
        "conflict_vs_canonical": conflict,     # data unit != doctrine (lakh)
        "columns": cols,
    }


def _yaml_dump(data):
    try:
        import yaml
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    except ImportError:
        return _yaml_manual(data)


def _q(s):
    s = str(s)
    return f'"{s}"' if re.search(r'[:#\'"{}\[\],&*?|<>=!%@`]|^\s|\s$', s) else s


def _yaml_manual(data, ind=0):
    out, pad = [], "  " * ind
    for k, v in data.items():
        if isinstance(v, dict):
            out.append(f"{pad}{_q(k)}:")
            out.append(_yaml_manual(v, ind + 1))
        else:
            out.append(f"{pad}{_q(k)}: {'' if v is None else _q(v)}")
    return "\n".join(x for x in out if x)


def _backfill_registry(units_yaml):
    """Fill registry.csv's unit_declared/unit_source from the resolved units.
    A table gets a money scale only if it actually contains a money column;
    count/percent-only tables (branch counts, PMJDY accounts) get 'n/a'."""
    reg = os.path.join(REPO, "audit", "registry.csv")
    if not os.path.exists(reg):
        return
    # per (state, category) -> has a money column?
    money_cats = {}
    for slug, s in units_yaml.items():
        for key, meta in s["columns"].items():
            cat = key.rsplit(".", 1)[0]
            money_cats[(slug, cat)] = money_cats.get((slug, cat), False) or meta["kind"] == "money"
    with open(reg, newline="") as fh:
        rows = list(csv.DictReader(fh))
        cols = rows[0].keys() if rows else []
    for r in rows:
        s = units_yaml.get(r["state"])
        if not s:
            continue
        has_money = money_cats.get((r["state"], r["indicator"]), False)
        if has_money and s["default_money_scale"] != "unknown":
            r["unit_declared"] = f'{s["default_money_scale"]} ({s["confidence"]})'
            r["unit_source"] = s["unit_source"]
        elif not has_money:
            r["unit_declared"] = "n/a"
            r["unit_source"] = "no-money-cols"
        else:
            r["unit_declared"] = "unknown"
            r["unit_source"] = "needs-caption"
    if "unit_source" not in cols:                     # add column if registry predates it
        cols = list(cols) + ["unit_source"]
    with open(reg, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cols))
        w.writeheader()
        w.writerows(rows)
    print(f"backfilled unit columns into {os.path.relpath(reg, REPO)}")


def main(sources_dir=None):
    units_yaml, findings = {}, []
    for cj in sorted(glob.glob(os.path.join(REPO, "public/slbc-data/*/*_complete.json"))):
        slug = os.path.basename(cj).replace("_complete.json", "")
        if slug == "tamilnadu":                      # stray duplicate master
            continue
        try:
            complete = json.load(open(cj))
        except Exception as e:
            print("SKIP", slug, e)
            continue
        r = resolve_state(complete, sources_dir, slug)
        kinds = [k for k in r["columns"].values()]
        nmoney = kinds.count("money")

        cols_yaml = {}
        for (cat, f), kind in sorted(r["columns"].items()):
            unit = {"money": r["scale"] or "unknown", "count": "count",
                    "percent": "percent"}.get(kind, "unknown")
            cols_yaml[f"{cat}.{f}"] = {"kind": kind, "unit": unit}
        units_yaml[slug] = {
            "default_money_scale": r["scale"] or "unknown",
            "unit_source": r["unit_source"],
            "confidence": r["confidence"],
            "evidence": r["evidence"],
            "canonical_unit": CANONICAL,
            "to_canonical_factor": TO_LAKH.get(r["scale"], None),
            "conflict_vs_canonical": r["conflict_vs_canonical"],
            "columns": cols_yaml,
        }
        findings.append({
            "state": slug, "money_scale": r["scale"] or "UNKNOWN",
            "unit_source": r["unit_source"], "confidence": r["confidence"],
            "anchor": r["magnitude"]["anchor"] or "", "anchor_median": r["magnitude"]["median"] or "",
            "dep_per_branch": r["magnitude"].get("ratio") or "",
            "conflict_vs_lakh": "YES" if r["conflict_vs_canonical"] else "",
            "n_money_cols": nmoney, "n_count_cols": kinds.count("count"),
            "n_percent_cols": kinds.count("percent"), "n_other_cols": kinds.count("other"),
            "note": r["magnitude"]["note"],
        })

    with open(os.path.join(REPO, "audit", "units.yaml"), "w") as fh:
        fh.write("# FINER unit manifest (artifact 1.2). Generated by audit/unit_resolver.py.\n")
        fh.write("# default_money_scale is the DATA's unit; canonical target is Rs. lakh.\n")
        fh.write("# unit_source: caption > magnitude > unknown. Caption tier needs sources/.\n\n")
        fh.write(_yaml_dump(units_yaml) + "\n")

    fcols = ["state", "money_scale", "unit_source", "confidence", "anchor", "anchor_median",
             "dep_per_branch", "conflict_vs_lakh", "n_money_cols", "n_count_cols",
             "n_percent_cols", "n_other_cols", "note"]
    with open(os.path.join(REPO, "audit", "unit_findings.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fcols)
        w.writeheader()
        w.writerows(findings)

    # backfill unit columns into registry.csv (artifact 1.1), if present
    _backfill_registry(units_yaml)

    # console summary
    findings.sort(key=lambda x: (x["money_scale"], str(x["anchor_median"])))
    print(f"{'state':18}{'scale':8}{'method':20}{'conf':8}{'anchor_med':>13}{'dep/br':>9}  conflict")
    for f in findings:
        am = f"{f['anchor_median']:,.0f}" if isinstance(f["anchor_median"], (int, float)) else "-"
        db = f"{f['dep_per_branch']:,.0f}" if isinstance(f["dep_per_branch"], (int, float)) else "-"
        print(f"{f['state']:18}{f['money_scale']:8}{f['unit_source']:20}{f['confidence']:8}{am:>13}{db:>9}  {f['conflict_vs_lakh']}")
    crore = [f["state"] for f in findings if f["money_scale"] == "crore"]
    unk = [f["state"] for f in findings if f["money_scale"] == "UNKNOWN"]
    print(f"\n{len(findings)} states. crore-scale (100x off vs lakh): {len(crore)} -> {crore}")
    print(f"unknown (need caption tier): {len(unk)} -> {unk}")
    print("wrote audit/units.yaml, audit/unit_findings.csv")


if __name__ == "__main__":
    src = None
    if "--sources" in sys.argv:
        src = sys.argv[sys.argv.index("--sources") + 1]
    main(src)
