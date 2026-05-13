#!/usr/bin/env python3
"""
Extract Goa SLBC district-wise data from agenda PDFs (slbcgoa.com).

GRANULARITY FINDING
-------------------
Goa SLBC publishes most data state-aggregate (bank-wise) — Deposits, Advances,
CD Ratio, PMJDY, KCC, SHG, MUDRA are all reported per-bank, not per-district.

The ONLY consistently district-wise table across every quarter is the
"Banking network" table under Agenda No. 3 / "Review of Financial Inclusion
Initiatives", which breaks branch counts down into North Goa vs South Goa
(rural / semi-urban split in post-2021 agendas).

This extractor pulls the per-quarter "Total" row for each district from the
banking network table and emits `branch_network__total_branch` per district.
ACP target tables (Agenda No. 9) are also district-wise but appear only in
December-quarter agendas — recorded in meetings_audit.txt, not ingested
(annual cadence rather than quarterly, and only one quarter of data per year).

Output files (modelled after Madhya Pradesh's CD-ratio-only output pattern):
- goa_complete.json
- goa_fi_timeseries.json
- goa_fi_timeseries.csv
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDF_DIR = HERE / "pdfs"

# Map meeting number → quarter (YYYY-MM). Quarter = the "as on" date in the
# Banking-network section header. Verified by inspection of every agenda PDF.
MEETING_QUARTERS = {
    110: "2020-06",
    111: "2020-09",
    112: "2020-12",
    113: "2021-03",
    114: "2021-06",
    115: "2021-09",
    116: "2021-12",
    117: "2022-03",
    118: "2022-06",
    119: "2022-09",
    120: "2022-12",
    121: "2023-03",
    122: "2023-06",
    123: "2023-09",
    124: "2023-12",
    125: "2024-03",
    126: "2024-06",
    127: "2024-09",
    128: "2024-12",
    129: "2025-03",
    130: "2025-06",
    131: "2025-09",
    132: "2025-12",
}

MONTH_NAMES = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def period_label(q: str) -> str:
    y, m = q.split("-")
    return f"{MONTH_NAMES[m]} {y}"


def pdf_to_text(pdf_path: Path) -> str:
    """Convert PDF to text using poppler's pdftotext -layout."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=60,
    )
    return result.stdout


# Match the "Grand Total" row of the banking network table.
# Two layouts:
#   pre-2021 (single column per district, no SU split):
#     Grand Total   47   382   407   789
#   post-2021 (Rural+SU split):
#     Grand Total   48   539   492   1031
# Both end with: banks  north_total  south_total  grand_total
GRAND_TOTAL_RE = re.compile(
    r"^\s*Grand\s+Total\s+(\d+)\s+(\d{1,4})\s+(\d{1,4})\s+(\d{1,5})\s*$"
)
# Pre-2021 agendas (110-113) close the table with "Total" (no Grand Total row).
# Same four-number shape: banks  north_total  south_total  grand_total.
TOTAL_RE = re.compile(
    r"^\s*Total\s+(\d+)\s+(\d{1,4})\s+(\d{1,4})\s+(\d{1,5})\s*$"
)


def extract_branch_network(text: str) -> tuple[int | None, int | None, int | None]:
    """
    Parse the banking-network table from the agenda text.
    Returns (north_total, south_total, grand_total) or (None, None, None).
    """
    lines = text.splitlines()
    in_section = False
    for i, line in enumerate(lines):
        # Locate section start
        if re.search(r"Banking\s+network\s+as\s+on", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            # Section ends at next agenda item or BC/CSP heading
            if re.search(r"Business\s+Correspondent|Agenda\s+No|^\s*b\)", line):
                in_section = False
                continue
            m = GRAND_TOTAL_RE.match(line) or TOTAL_RE.match(line)
            if m:
                _banks, north, south, total = m.groups()
                return int(north), int(south), int(total)
    return None, None, None


def extract_all() -> dict:
    """Walk every PDF, return {period: {district: total_branch}}."""
    per_quarter: dict[str, dict[str, int]] = {}

    for meeting, quarter in sorted(MEETING_QUARTERS.items()):
        pdf = PDF_DIR / f"{meeting}_agenda.pdf"
        if not pdf.exists():
            print(f"  [skip] {pdf.name} missing", file=sys.stderr)
            continue
        text = pdf_to_text(pdf)
        north, south, total = extract_branch_network(text)
        if north is None:
            print(f"  [warn] no Grand-Total row found in meeting {meeting}", file=sys.stderr)
            continue
        if north + south != total:
            print(
                f"  [warn] meeting {meeting} {quarter}: north+south={north+south} != total={total}",
                file=sys.stderr,
            )
        per_quarter[quarter] = {
            "North Goa": north,
            "South Goa": south,
        }
        print(f"  [ok]  meeting {meeting:>3}  {quarter}  N={north:>4}  S={south:>4}  T={total:>4}")
    return per_quarter


def write_outputs(data: dict[str, dict[str, int]]) -> None:
    """Emit goa_complete.json, goa_fi_timeseries.json, goa_fi_timeseries.csv."""
    quarters = sorted(data.keys())

    # 1) goa_complete.json — same shape as Madhya Pradesh / other CD-only states
    complete: dict = {"quarters": {}}
    for q in quarters:
        label = period_label(q)
        snake = label.lower().replace(" ", "_")
        complete["quarters"][snake] = {
            "period": label,
            "tables": {
                "branch_network": {
                    "fields": ["total_branch"],
                    "districts": {
                        d: {"total_branch": str(v)} for d, v in data[q].items()
                    },
                }
            },
        }

    # 2) goa_fi_timeseries.json — nested periods/districts shape used by frontend
    timeseries: dict = {"periods": []}
    for q in quarters:
        label = period_label(q)
        timeseries["periods"].append({
            "period": label,
            "districts": [
                {
                    "district": d,
                    "period": label,
                    "branch_network__total_branch": v,
                }
                for d, v in data[q].items()
            ],
        })

    # 3) flat CSV (wide)
    rows = []
    districts = ["North Goa", "South Goa"]
    for q in quarters:
        label = period_label(q)
        for d in districts:
            rows.append({
                "district": d,
                "period": label,
                "branch_network__total_branch": data[q].get(d, ""),
            })

    out_complete = HERE / "goa_complete.json"
    out_ts = HERE / "goa_fi_timeseries.json"
    out_csv = HERE / "goa_fi_timeseries.csv"

    out_complete.write_text(json.dumps(complete, indent=2))
    out_ts.write_text(json.dumps(timeseries, indent=2))
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["district", "period", "branch_network__total_branch"])
        w.writeheader()
        w.writerows(rows)

    # 4) slim copy
    slim = json.dumps(timeseries)
    (HERE / "goa_fi_slim.json").write_text(slim)

    print(f"\nWrote:")
    print(f"  {out_complete}")
    print(f"  {out_ts}")
    print(f"  {out_csv}")
    print(f"  {HERE / 'goa_fi_slim.json'}")


def main() -> int:
    print(f"Extracting Goa SLBC data from {PDF_DIR} ...")
    data = extract_all()
    if not data:
        print("No data extracted.", file=sys.stderr)
        return 1
    write_outputs(data)
    print(f"\nDone. {len(data)} quarters extracted (Jun 2020 -> Dec 2025).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
