#!/usr/bin/env python3
"""
Delhi SLBC extractor.

Source: slbcdelhi.pnb.bank.in (Punjab National Bank, SLBC convenor for NCT of Delhi
since April 2020 — replaced Punjab & Sind Bank).

Each quarterly SLBC agenda booklet contains a clean district-wise summary
table on the first agenda page (after the Delhi profile). Schema:

    S.No.  Name of District  No. of Branches  No. of ATMs  Deposits  Advances  CD Ratio

(Column order varies slightly across meetings — Branches column sometimes
moves; the 122nd (Dec 2025) places the same table in Annexure-5 with
**actual-rupee** amounts instead of crores.)

11 revenue districts: Central, East, New Delhi, North, North East, North West,
Shahdara, South, South East, South West, West.

Meetings covered: 110th (Dec 2022) → 122nd (Dec 2025) = 13 quarters.

Output (in this directory):
  meetings_audit.txt
  delhi_complete.json
  delhi_fi_timeseries.json
  delhi_fi_timeseries.csv

The output JSON/CSV is also copied to public/slbc-data/delhi/ by the calling
script (or do it manually after running this extractor).

State LGD code: 7. Source amounts (page-1 table) are in **Rs. Crores**;
the 122nd Annexure-5 prints amounts in rupees (×10^-7 → Crores). Everything
is converted to ₹ Lakhs (canonical FINER unit, ×100 from Crores).
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent           # slbc-data/delhi/
PROJECT = ROOT.parent.parent                     # projectfiner/
PUBLIC_OUT = PROJECT / "public" / "slbc-data" / "delhi"
PUBLIC_OUT.mkdir(parents=True, exist_ok=True)

CANONICAL_DISTRICTS = [
    "Central", "East", "New Delhi", "North", "North East", "North West",
    "Shahdara", "South", "South East", "South West", "West",
]
DISTRICT_KEYS_UPPER = {d.upper(): d for d in CANONICAL_DISTRICTS}

# Meeting → quarter (verified against each PDF's title block).
MEETING_TO_QUARTER = {
    110: "December 2022",
    111: "March 2023",
    112: "June 2023",
    113: "September 2023",
    114: "December 2023",
    115: "March 2024",
    116: "June 2024",
    117: "September 2024",
    118: "December 2024",
    119: "March 2025",
    120: "June 2025",
    121: "September 2025",
    122: "December 2025",
}

# Each meeting's main agenda PDF. Some are .rar bundles; we extract those.
SOURCES = [
    # (meeting_no, kind, relative_path inside slbc-data/delhi/)
    (110, "rar", "110th_agenda.rar"),
    (111, "rar", "111th_agenda.rar"),
    (112, "rar", "112th_agenda.rar"),
    (113, "rar", "113th_agenda.rar"),
    (114, "rar", "114th_agenda.rar"),
    (115, "rar", "115th_agenda.rar"),
    (116, "rar", "116th_agenda.rar"),
    (117, "rar", "117th_agenda.rar"),
    (118, "rar", "118th_agenda.rar"),
    (119, "rar", "119th_agenda.rar"),
    (120, "rar", "120th_agenda.rar"),
    (121, "pdf", "121st_agenda.pdf"),
    (122, "pdf", "122nd_agenda.pdf"),
]


def _run(cmd: list[str], cwd: str | None = None) -> str:
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return res.stdout


def _pdftotext(pdf_path: Path) -> str:
    out = pdf_path.with_suffix(".txt")
    subprocess.run(["pdftotext", "-layout", str(pdf_path), str(out)], check=True)
    txt = out.read_text(errors="replace")
    out.unlink(missing_ok=True)
    return txt


def _extract_rar_to_text(rar_path: Path) -> str:
    """Extract the booklet's main agenda PDF and return its plain text.

    Each bundle contains 2–3 PDFs:
      - "Agenda Book / Agenda Booklet ..."   ← the one we want
      - "Consolidated Annex / All Annex ..."  ← skip
      - "Agenda Items Indexing ..."           ← short TOC, skip

    Preference order:
      1. file names matching 'agenda book/booklet' AND not containing 'annex'
      2. file names containing 'agenda' AND not containing 'annex'/'indexing'
      3. fallback: largest remaining PDF
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["unar", "-o", tmpdir, str(rar_path)], check=True, capture_output=True)
        all_pdfs = list(Path(tmpdir).rglob("*.pdf"))
        if not all_pdfs:
            return ""

        def is_annex(name: str) -> bool:
            n = name.lower()
            return "annex" in n or "annexure" in n

        def is_indexing(name: str) -> bool:
            n = name.lower()
            # "Indexing" / "Items Indexing" — short TOC PDFs.  Note this is
            # narrower than 'index' (the main booklet sometimes has "with Index"
            # in its name and we still want it).
            return "indexing" in n or "items index" in n

        # Tier 1: agenda book/booklet, not annex, not pure indexing
        tier1 = [p for p in all_pdfs
                 if ("agenda book" in p.name.lower() or "agenda booklet" in p.name.lower())
                 and not is_annex(p.name) and not is_indexing(p.name)]
        # Tier 2: any "agenda" PDF that's not annex/indexing
        tier2 = [p for p in all_pdfs
                 if "agenda" in p.name.lower()
                 and not is_annex(p.name) and not is_indexing(p.name)]
        # Tier 3: anything that's not annex/indexing
        tier3 = [p for p in all_pdfs
                 if not is_annex(p.name) and not is_indexing(p.name)]

        pool = tier1 or tier2 or tier3 or all_pdfs
        pool.sort(key=lambda p: p.stat().st_size, reverse=True)
        return _pdftotext(pool[0])


_NUM = r"([0-9][0-9,]*\.?[0-9]*)"


def _to_float(s: str) -> float | None:
    s = s.replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _detect_district_table(text: str) -> list[dict] | None:
    """Find the first district-wise summary table.

    The summary has 5 numeric columns: Branches, ATMs, Deposits, Advances, CD Ratio.
    """
    lines = text.splitlines()
    rows = []
    # Match either with leading "<sno>" or without; require district name + 5 numbers.
    pat = re.compile(
        r"^\s*(?:\d+\s+)?(" + "|".join(sorted(DISTRICT_KEYS_UPPER.keys(),
                                              key=len, reverse=True)) +
        r")\s+" + r"\s+".join([_NUM] * 5) + r"\s*$",
        re.IGNORECASE,
    )
    for line in lines:
        m = pat.match(line)
        if m:
            name = DISTRICT_KEYS_UPPER[m.group(1).upper()]
            branches = _to_float(m.group(2))
            atms = _to_float(m.group(3))
            deposits = _to_float(m.group(4))
            advances = _to_float(m.group(5))
            cdr = _to_float(m.group(6))
            rows.append({
                "district": name,
                "branches": branches,
                "atms": atms,
                "deposits": deposits,
                "advances": advances,
                "cd_ratio": cdr,
            })
            if len(rows) >= 11:
                # First complete table reached — collected all 11 unique
                # districts (rows may be duplicated by header echo lines;
                # dedupe by first-seen district).
                break

    # Dedupe by first occurrence (some PDFs repeat the Central row right after
    # the header).
    seen = set()
    uniq = []
    for r in rows:
        if r["district"] not in seen:
            uniq.append(r)
            seen.add(r["district"])
    if len(uniq) >= 11:
        return uniq[:11]
    return None


def _detect_unit_scale(rows: list[dict]) -> float:
    """Return multiplier to convert source amounts → ₹ Lakhs.

    Pre-122 meetings carry amounts in Crores (typical totals ~1.5–1.9M Cr
    = ~150–190 lakh Lakhs).  The 122nd Annexure-5 carries amounts as
    *actual rupees* (~10^13 for total) — multiplier 1e-5 to Lakhs.

    Detection: if the median Deposits value across the 11 districts is
    > 1e10 we treat amounts as rupees-actual.
    """
    deps = sorted(r["deposits"] for r in rows if r["deposits"] is not None)
    if not deps:
        return 100.0  # default: Crores → Lakhs
    median = deps[len(deps) // 2]
    if median > 1e10:        # rupees as actual
        return 1e-5          # rupees → Lakhs
    return 100.0             # Crores → Lakhs


def _extract_meeting(meeting_no: int, kind: str, src: Path) -> dict | None:
    if not src.exists():
        print(f"  [WARN] missing source: {src}")
        return None
    if kind == "pdf":
        text = _pdftotext(src)
    elif kind == "rar":
        text = _extract_rar_to_text(src)
    else:
        return None

    # Try Annexure-5 layout first (used by the 122nd and any later PDFs that
    # follow that template).  If it matches, prefer it because the actual-rupee
    # amounts are far more precise than the rounded-Crore page-1 numbers.
    rows = _detect_annexure_5_table(text)
    if rows is None:
        rows = _detect_district_table(text)
    if rows is None:
        return None
    multiplier = _detect_unit_scale(rows)
    return {
        "meeting": meeting_no,
        "quarter": MEETING_TO_QUARTER[meeting_no],
        "multiplier": multiplier,
        "rows": rows,
    }


def _detect_annexure_5_table(text: str) -> list[dict] | None:
    """122nd-style table: DISTRICT WISE CD RATIO AT QUARTER ENDED ... with
    deposits/advances stored as actual rupees (e.g. 2747786934815).

    Anchored to the 'DISTRICT WISE CD RATIO AT QUARTER ENDED' or 'Number
    and Amount as actual' marker to avoid false positives on unrelated
    Annexure tables.
    """
    if not re.search(
        r"DISTRICT WISE CD RATIO AT QUARTER ENDED|Number and Amount as actual",
        text, re.IGNORECASE,
    ):
        return None
    lines = text.splitlines()
    pat = re.compile(
        r"^\s*\d+\s+(" + "|".join(sorted(DISTRICT_KEYS_UPPER.keys(),
                                          key=len, reverse=True)) +
        r")\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9.]+)\s*$",
        re.IGNORECASE,
    )
    rows = []
    for line in lines:
        m = pat.match(line)
        if m:
            name = DISTRICT_KEYS_UPPER[m.group(1).upper()]
            rows.append({
                "district": name,
                "branches": _to_float(m.group(2)),
                "atms": _to_float(m.group(3)),
                "deposits": _to_float(m.group(4)),
                "advances": _to_float(m.group(5)),
                "cd_ratio": _to_float(m.group(6)),
            })
    seen = set()
    uniq = []
    for r in rows:
        if r["district"] not in seen:
            uniq.append(r)
            seen.add(r["district"])
    if len(uniq) >= 11:
        return uniq[:11]
    return None


def build_outputs(extracted: list[dict]) -> None:
    # Sort meetings chronologically
    extracted.sort(key=lambda x: x["meeting"])

    # ── Timeseries JSON (FINER canonical shape) ─────────────────────────
    periods_payload = []
    for entry in extracted:
        period_label = entry["quarter"]
        mult = entry["multiplier"]
        districts = []
        for r in entry["rows"]:
            rec = {"district": r["district"], "period": period_label}
            if r["branches"] is not None:
                rec["branch_network__total_branch"] = r["branches"]
            if r["deposits"] is not None:
                rec["credit_deposit_ratio__total_deposit"] = round(r["deposits"] * mult, 2)
            if r["advances"] is not None:
                rec["credit_deposit_ratio__total_advance"] = round(r["advances"] * mult, 2)
            if r["cd_ratio"] is not None:
                rec["credit_deposit_ratio__cd_ratio"] = r["cd_ratio"]
            districts.append(rec)
        periods_payload.append({"period": period_label, "districts": districts})

    ts = {"state": "Delhi", "state_lgd_code": 7, "periods": periods_payload}
    (ROOT / "delhi_fi_timeseries.json").write_text(json.dumps(ts, indent=2))
    (PUBLIC_OUT / "delhi_fi_timeseries.json").write_text(json.dumps(ts, indent=2))

    # ── Complete JSON (mirrors NE state shape) ──────────────────────────
    complete = {"state": "Delhi", "state_lgd_code": 7, "quarters": {}}
    for entry in extracted:
        q = entry["quarter"]
        key = q.lower().replace(" ", "_")
        mult = entry["multiplier"]
        cdr_fields = {}
        bn_fields = {}
        for r in entry["rows"]:
            d = r["district"]
            cdr_fields.setdefault("districts", {})[d] = {
                "total_deposit": str(round(r["deposits"] * mult, 2)) if r["deposits"] is not None else "",
                "total_advance": str(round(r["advances"] * mult, 2)) if r["advances"] is not None else "",
                "cd_ratio":      str(r["cd_ratio"]) if r["cd_ratio"] is not None else "",
            }
            bn_fields.setdefault("districts", {})[d] = {
                "total_branch": str(int(r["branches"])) if r["branches"] is not None else "",
                "total_atm":    str(int(r["atms"]))     if r["atms"] is not None else "",
            }
        complete["quarters"][key] = {
            "period": q,
            "tables": {
                "credit_deposit_ratio": {
                    "fields": ["total_deposit", "total_advance", "cd_ratio"],
                    "districts": cdr_fields["districts"],
                },
                "branch_network": {
                    "fields": ["total_branch", "total_atm"],
                    "districts": bn_fields["districts"],
                },
            },
        }
    (ROOT / "delhi_complete.json").write_text(json.dumps(complete, indent=2))
    (PUBLIC_OUT / "delhi_complete.json").write_text(json.dumps(complete, indent=2))

    # ── Timeseries CSV (wide format) ────────────────────────────────────
    fields = [
        "district", "period",
        "credit_deposit_ratio__total_deposit",
        "credit_deposit_ratio__total_advance",
        "credit_deposit_ratio__cd_ratio",
        "branch_network__total_branch",
    ]
    csv_path = ROOT / "delhi_fi_timeseries.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for p in periods_payload:
            for d in p["districts"]:
                row = {k: d.get(k, "") for k in fields}
                w.writerow(row)
    shutil.copy(csv_path, PUBLIC_OUT / "delhi_fi_timeseries.csv")

    # ── Slim timeseries (subset that the homepage map loads) ────────────
    # The slim shape mirrors _fi_timeseries.json but trimmed to the 7
    # indicator categories.  For Delhi this is identical (we only carry
    # branch_network + credit_deposit_ratio fields), but we still emit a
    # _fi_slim.json so the build pipeline can serve it.
    (PUBLIC_OUT / "delhi_fi_slim.json").write_text(json.dumps(ts, indent=2))


def write_audit(extracted: list[dict]) -> None:
    """Write meetings_audit.txt detailing each meeting + granularity finding."""
    lines = []
    lines.append("Delhi SLBC — meetings audit")
    lines.append("=" * 60)
    lines.append("")
    lines.append("Source: https://slbcdelhi.pnb.bank.in/")
    lines.append("Convenor: Punjab National Bank (since April 2020; previously")
    lines.append("          Punjab & Sind Bank was the convenor).")
    lines.append("State LGD code: 7")
    lines.append("11 revenue districts: Central, East, New Delhi, North, North")
    lines.append("  East, North West, Shahdara, South, South East, South West, West.")
    lines.append("")
    lines.append("Granularity: district-wise (all 11 revenue districts), NOT")
    lines.append("NCT-aggregate only.  Each quarterly agenda booklet's first")
    lines.append("agenda page carries a 'District wise analysis of NCT of Delhi'")
    lines.append("table with five numeric columns:")
    lines.append("    Branches | ATMs | Deposits | Advances | CD Ratio")
    lines.append("")
    lines.append("Unit conventions:")
    lines.append("  - Meetings 110th–121st: amounts in Crores (page-1 summary).")
    lines.append("  - Meeting 122nd: Annexure-5 reports same five columns")
    lines.append("    but with deposits/advances in actual rupees (×10^7 of crores).")
    lines.append("  Extractor auto-detects via median-deposit threshold and")
    lines.append("  converts everything to ₹ Lakhs (FINER canonical).")
    lines.append("")
    lines.append("Meetings ingested:")
    lines.append("")
    lines.append(f"  {'Meeting':<8}  {'Quarter':<18}  {'Rows':<5}  {'Unit at source'}")
    lines.append(f"  {'-'*8}  {'-'*18}  {'-'*5}  {'-'*15}")
    for entry in extracted:
        unit = "Rupees (actual)" if entry["multiplier"] < 1 else "Crores"
        lines.append(f"  {entry['meeting']:<8}  {entry['quarter']:<18}  {len(entry['rows']):<5}  {unit}")
    lines.append("")
    lines.append("")
    lines.append("Indicator coverage:")
    lines.append("  - credit_deposit_ratio: 13 quarters × 11 districts")
    lines.append("    (total_deposit, total_advance, cd_ratio)")
    lines.append("  - branch_network: 13 quarters × 11 districts")
    lines.append("    (total_branch, total_atm)")
    lines.append("")
    lines.append("Not extracted (annexures with bank-wise rather than district-wise")
    lines.append("granularity, parked for future expansion):")
    lines.append("  - PMJDY accounts (Annexure-7+)  — public/private bank rows,")
    lines.append("    not district rows")
    lines.append("  - KCC (Annexure-3, 14)          — bank-wise only")
    lines.append("  - MUDRA (Annexure-12)           — bank-wise only")
    lines.append("  - SHG (under 'NULM/DAY-NRLM')   — bank-wise")
    lines.append("  - PMEGP / Stand Up India / APY  — bank-wise targets")
    lines.append("")
    lines.append("(Delhi SLBC publishes district-wise rural-branch counts in a")
    lines.append("separate table, and district-wise APY targets — they're noted")
    lines.append("here but not yet imported.  CD-ratio + branch counts are the")
    lines.append("two indicators with comprehensive 11-district coverage.)")
    lines.append("")
    lines.append("Known source-side anomalies (preserved as-is, NOT corrected):")
    lines.append("  - 113th meeting (Sep 2023): per-district advances column")
    lines.append("    appears truncated relative to the reported overall CDR")
    lines.append("    (per-district advances sum to ~₹964,846 Cr, implying")
    lines.append("     65.49% CDR; but the booklet footer reports 103.77%).")
    lines.append("    Per-district CD-ratio % values are independently printed")
    lines.append("    in the same row and used as-is for that quarter.")
    lines.append("    Faithful to source per FINER data-integrity rules.")

    (ROOT / "meetings_audit.txt").write_text("\n".join(lines))


def main() -> None:
    extracted = []
    print("Extracting Delhi SLBC PDFs …")
    for meeting_no, kind, name in SOURCES:
        src = ROOT / name
        print(f"  · meeting {meeting_no} ({kind}): {name}")
        rec = _extract_meeting(meeting_no, kind, src)
        if rec is None:
            print(f"    └─ no district table detected (skipping)")
            continue
        unit = "rupees" if rec["multiplier"] < 1 else "crores"
        print(f"    └─ {len(rec['rows'])} districts, unit={unit}, "
              f"quarter={rec['quarter']}")
        extracted.append(rec)

    if not extracted:
        print("ERROR: no data extracted.")
        sys.exit(1)

    build_outputs(extracted)
    write_audit(extracted)
    print(f"\nWrote {len(extracted)} quarters × 11 districts to:")
    print(f"  {ROOT}/delhi_fi_timeseries.json")
    print(f"  {PUBLIC_OUT}/delhi_fi_timeseries.json")
    print(f"  {PUBLIC_OUT}/delhi_fi_slim.json")
    print(f"  {ROOT}/meetings_audit.txt")


if __name__ == "__main__":
    main()
