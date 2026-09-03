#!/usr/bin/env python3
"""
Project FINER - Data Validation Script
Detects anomalies in SLBC financial inclusion timeseries data.

Usage:
    python3 validate_data.py                  # validate all states
    python3 validate_data.py --state assam    # validate one state
    python3 validate_data.py --verbose        # show detailed output
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
SLBC_DIR = Path(__file__).parent / "public" / "slbc-data"
REPORT_PATH = Path(__file__).parent / "DATA_VALIDATION_REPORT.md"

METADATA_FIELDS = {"district", "period", "meeting", "quarter", "date"}

# Fields whose values are ratios/percentages, not amounts or counts
RATIO_FIELD_PATTERNS = {"ratio", "pct", "percentage", "cd_ratio"}

# Threshold constants
JUMP_FACTOR = 10          # 10x jump threshold
DROP_FACTOR = 0.1         # 90% drop threshold
STDDEV_MULTIPLIER = 3     # outlier detection
DUPLICATE_THRESHOLD = 0.9 # 90% identical values => likely duplicate
MISSING_GAP_TOLERANCE = 2 # flag if district disappears for <= 2 periods


# ── Period ordering ────────────────────────────────────────────────────────────
MONTH_ORDER = {
    "march": 3, "mar": 3,
    "june": 6, "jun": 6,
    "september": 9, "sep": 9,
    "december": 12, "dec": 12,
}


def parse_period(period_str):
    """Convert 'December 2025' or 'Dec 2022' into (year, quarter_month) for sorting."""
    parts = period_str.strip().lower().split()
    if len(parts) != 2:
        return (9999, 0)
    month_str, year_str = parts
    month = MONTH_ORDER.get(month_str, 0)
    try:
        year = int(year_str)
    except ValueError:
        year = 9999
    return (year, month)


def period_sort_key(period_str):
    y, m = parse_period(period_str)
    return y * 100 + m


# ── Data loading ───────────────────────────────────────────────────────────────

def load_state_data(state_slug):
    """
    Load a state's timeseries and normalize to a common format:
    Returns list of (period_str, list_of_district_dicts) sorted chronologically.
    """
    fp = SLBC_DIR / state_slug / f"{state_slug}_fi_timeseries.json"
    if not fp.exists():
        return None

    raw = json.loads(fp.read_text())

    # Standard format: {"periods": [{"period": ..., "districts": [...]}]}
    if isinstance(raw, dict) and "periods" in raw:
        periods = []
        for p in raw["periods"]:
            period_str = p.get("period", "Unknown")
            districts = p.get("districts", [])
            periods.append((period_str, districts))
        periods.sort(key=lambda x: period_sort_key(x[0]))
        return periods

    # Haryana flat format: {district_name: [records...]}
    if isinstance(raw, dict) and "periods" not in raw:
        # Collect all unique quarters
        quarter_map = defaultdict(list)
        for dist_name, records in raw.items():
            if not isinstance(records, list):
                continue
            for rec in records:
                q = rec.get("quarter", rec.get("period", "Unknown"))
                row = dict(rec)
                row["district"] = dist_name
                row["period"] = q
                quarter_map[q].append(row)
        periods = []
        for q, districts in quarter_map.items():
            periods.append((q, districts))
        periods.sort(key=lambda x: period_sort_key(x[0]))
        return periods

    return None


def numeric_value(v):
    """Coerce a cell to float, or None if it isn't a number.

    Every state except Goa serialises its values as STRINGS ("2613.61") —
    the extractors emit formatted text, not JSON numbers. An earlier
    isinstance(v, (int, float)) guard therefore skipped 29 of 31 states
    entirely, so the validators below silently inspected almost nothing.
    Coerce instead of type-checking.
    """
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if math.isnan(v) else float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", "").replace("%", "").replace("₹", "")
        if not s or s.upper() in {"NA", "N/A", "-", "—", "NIL", "NONE"}:
            return None
        try:
            f = float(s)
        except ValueError:
            return None
        return None if math.isnan(f) else f
    return None


def get_data_fields(district_dict):
    """Return field names that are actual data (not metadata)."""
    return [k for k in district_dict.keys()
            if k not in METADATA_FIELDS and numeric_value(district_dict.get(k)) is not None]


def is_ratio_field(field_name):
    """True only if the METRIC is a ratio — not if its category merely says so.

    Fields are "<category>__<metric>". Matching the whole string meant every
    field under credit_deposit_ratio__ (total_deposit, total_advance, the
    project's most important monetary values) contained "ratio" and was
    exempted from the 10x-jump check — which is why the known Bihar and UP
    100x unit seams were never flagged. Inspect the metric half only.
    """
    metric = field_name.split("__", 1)[-1].lower()
    return any(p in metric for p in RATIO_FIELD_PATTERNS)


def get_category(field_name):
    if "__" in field_name:
        return field_name.split("__")[0]
    return "_uncategorized"


# ── Issue container ────────────────────────────────────────────────────────────

class Issue:
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

    def __init__(self, state, issue_type, severity, district, field, period, message):
        self.state = state
        self.issue_type = issue_type
        self.severity = severity
        self.district = district
        self.field = field
        self.period = period
        self.message = message

    def __repr__(self):
        return f"[{self.severity.upper()}] {self.state}/{self.district} | {self.field} @ {self.period}: {self.message}"


def issue_key(issue):
    """Stable observation-level identity, excluding changeable message text."""
    return "\x1f".join(str(value) for value in (
        issue.state,
        issue.issue_type,
        issue.district,
        issue.field,
        issue.period,
    ))


def issue_fingerprint(issue):
    """SHA-256 identity used by the reviewed waiver ledger."""
    return hashlib.sha256(issue_key(issue).encode("utf-8")).hexdigest()


def build_waiver_ledger(criticals, created_on, expires_on):
    fingerprints = sorted(issue_fingerprint(issue) for issue in criticals)
    return {
        "_comment": (
            "Exact observation-level fingerprints of legacy critical findings. "
            "A new fingerprint always fails CI, even when another finding is fixed. "
            "Remove resolved fingerprints during review; never regenerate wholesale."
        ),
        "schema_version": 1,
        "fingerprint_algorithm": "sha256-v1",
        "waiver": {
            "id": f"FINER-LEGACY-CRITICAL-{created_on.isoformat()}",
            "reason": "Legacy critical findings present when exact-identity gating was introduced.",
            "created_on": created_on.isoformat(),
            "expires_on": expires_on.isoformat(),
        },
        "total_waived": len(fingerprints),
        "fingerprints": fingerprints,
    }


def write_waiver_ledger(path, ledger):
    """Write fingerprints in 16 reviewable shards instead of one 2 MB JSON file."""
    path.mkdir(parents=True, exist_ok=True)
    shard_names = [f"{prefix}.txt" for prefix in "0123456789abcdef"]
    fingerprints = ledger["fingerprints"]
    manifest = {key: value for key, value in ledger.items() if key != "fingerprints"}
    manifest["shards"] = shard_names
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for shard_name in shard_names:
        prefix = shard_name[0]
        values = [value for value in fingerprints if value.startswith(prefix)]
        (path / shard_name).write_text("\n".join(values) + ("\n" if values else ""))


def load_waiver_ledger(path):
    """Load a sharded waiver directory (or a legacy single JSON ledger)."""
    if path.is_file():
        return json.loads(path.read_text())
    manifest = json.loads((path / "manifest.json").read_text())
    shard_names = manifest.get("shards")
    if not isinstance(shard_names, list) or not shard_names:
        raise ValueError("waiver manifest shards must be a non-empty array")
    fingerprints = []
    for shard_name in shard_names:
        if not isinstance(shard_name, str) or not re.fullmatch(r"[0-9a-f]\.txt", shard_name):
            raise ValueError(f"invalid waiver shard name: {shard_name!r}")
        fingerprints.extend((path / shard_name).read_text().splitlines())
    manifest["fingerprints"] = fingerprints
    return manifest


def evaluate_waiver_ledger(criticals, ledger, today=None):
    """Return (unwaived issues, resolved fingerprints, ledger errors)."""
    errors = []
    today = today or date.today()
    if not isinstance(ledger, dict):
        return list(criticals), [], ["waiver ledger root must be an object"]
    if ledger.get("schema_version") != 1:
        errors.append("waiver ledger schema_version must be 1")
    if ledger.get("fingerprint_algorithm") != "sha256-v1":
        errors.append("waiver ledger fingerprint_algorithm must be sha256-v1")

    fingerprints = ledger.get("fingerprints")
    if not isinstance(fingerprints, list) or not all(isinstance(item, str) for item in fingerprints):
        errors.append("waiver ledger fingerprints must be an array of strings")
        fingerprints = []
    elif fingerprints != sorted(set(fingerprints)):
        errors.append("waiver ledger fingerprints must be sorted and unique")
    elif not all(re.fullmatch(r"[0-9a-f]{64}", item) for item in fingerprints):
        errors.append("waiver ledger fingerprints must be lowercase SHA-256 hex strings")
    if ledger.get("total_waived") != len(fingerprints):
        errors.append("waiver ledger total_waived does not match fingerprints")

    waiver = ledger.get("waiver")
    if not isinstance(waiver, dict):
        errors.append("waiver ledger waiver must be an object")
        waiver = {}
    for field in ("id", "reason", "created_on"):
        if not isinstance(waiver.get(field), str) or not waiver[field].strip():
            errors.append(f"waiver ledger {field} must be a non-empty string")
    expiry_text = waiver.get("expires_on")
    try:
        expiry = date.fromisoformat(expiry_text)
    except (TypeError, ValueError):
        errors.append("waiver ledger expires_on must be an ISO date")
    else:
        if today > expiry:
            errors.append(f"waiver ledger expired on {expiry.isoformat()}")

    current = {issue_fingerprint(issue): issue for issue in criticals}
    waived = set(fingerprints)
    unwaived = [current[key] for key in sorted(current.keys() - waived)]
    resolved = sorted(waived - current.keys())
    return unwaived, resolved, errors


# ── Validators ─────────────────────────────────────────────────────────────────

def check_10x_jumps(state, periods_data, issues):
    """Check 1: Values jumping >10x or dropping >90% between consecutive periods."""
    # Build per-district per-field timeseries
    dist_field_ts = defaultdict(list)  # (district, field) -> [(period, value)]

    for period_str, districts in periods_data:
        for d in districts:
            dist = d.get("district", "Unknown")
            for field in get_data_fields(d):
                val = d[field]
                val = numeric_value(val)
                if val is not None:
                    dist_field_ts[(dist, field)].append((period_str, val))

    for (dist, field), ts in dist_field_ts.items():
        if is_ratio_field(field):
            continue
        for i in range(1, len(ts)):
            prev_period, prev_val = ts[i - 1]
            curr_period, curr_val = ts[i]
            if prev_val == 0 or curr_val == 0:
                continue
            ratio = curr_val / prev_val
            if ratio > JUMP_FACTOR:
                issues.append(Issue(
                    state, "10x_jump", Issue.CRITICAL, dist, field, curr_period,
                    f"Value jumped {ratio:.1f}x: {prev_val:,.2f} ({prev_period}) -> {curr_val:,.2f} ({curr_period})"
                ))
            elif ratio < DROP_FACTOR:
                issues.append(Issue(
                    state, "10x_jump", Issue.CRITICAL, dist, field, curr_period,
                    f"Value dropped to {ratio:.2%}: {prev_val:,.2f} ({prev_period}) -> {curr_val:,.2f} ({curr_period})"
                ))


def check_column_shifts(state, periods_data, issues):
    """Check 2: Multiple fields in same category swapping values for same district+quarter."""
    dist_cat_ts = defaultdict(lambda: defaultdict(dict))
    # dist_cat_ts[dist][category][(period_idx, field)] = value

    for p_idx, (period_str, districts) in enumerate(periods_data):
        for d in districts:
            dist = d.get("district", "Unknown")
            for field in get_data_fields(d):
                cat = get_category(field)
                val = d[field]
                val = numeric_value(val)
                if val is not None:
                    dist_cat_ts[dist][cat][(p_idx, field)] = val

    for dist, cats in dist_cat_ts.items():
        for cat, vals in cats.items():
            # Group by period
            period_fields = defaultdict(dict)
            for (p_idx, field), val in vals.items():
                period_fields[p_idx][field] = val

            period_indices = sorted(period_fields.keys())
            if len(period_indices) < 2:
                continue

            for i in range(1, len(period_indices)):
                prev_idx = period_indices[i - 1]
                curr_idx = period_indices[i]
                prev_vals = period_fields[prev_idx]
                curr_vals = period_fields[curr_idx]

                common_fields = set(prev_vals.keys()) & set(curr_vals.keys())
                if len(common_fields) < 3:
                    continue

                # Check if values appear to have shifted: field A got field B's value
                swap_count = 0
                for f1 in common_fields:
                    for f2 in common_fields:
                        if f1 >= f2:
                            continue
                        if prev_vals[f1] == 0 or prev_vals[f2] == 0:
                            continue
                        # f1 now has f2's previous value AND f2 now has f1's previous value
                        if (abs(curr_vals[f1] - prev_vals[f2]) < 0.01 and
                                abs(curr_vals[f2] - prev_vals[f1]) < 0.01 and
                                abs(curr_vals[f1] - prev_vals[f1]) > 0.01):
                            swap_count += 1

                if swap_count > 0:
                    period_str = periods_data[curr_idx][0]
                    issues.append(Issue(
                        state, "column_shift", Issue.CRITICAL, dist, cat, period_str,
                        f"{swap_count} field pair(s) in category '{cat}' appear to have swapped values"
                    ))


def check_count_amount_confusion(state, periods_data, issues):
    """Check 3: Count fields with amount-like values or amount fields with count-like values."""
    # Collect all values per field across all districts and periods
    field_values = defaultdict(list)
    for period_str, districts in periods_data:
        for d in districts:
            for field in get_data_fields(d):
                val = d[field]
                val = numeric_value(val)
                if val is not None:
                    field_values[field].append(val)

    for field, values in field_values.items():
        if not values:
            continue
        if is_ratio_field(field):
            continue

        fname = field.lower()
        median = sorted(values)[len(values) // 2]

        # Count fields (_no, _a_c, _br, _atm, _bc, _accounts, _card)
        is_count = any(fname.endswith(s) for s in ("_no", "_a_c", "_br", "_atm", "_bc", "_accounts", "_card"))
        # Amount fields (_amt, _amount, _deposit, _advance)
        is_amount = any(fname.endswith(s) for s in ("_amt", "_amount"))

        if is_count and median > 100000:
            # Count field with very large values might be amounts
            has_decimals = any(v != int(v) for v in values if isinstance(v, float))
            if has_decimals:
                issues.append(Issue(
                    state, "count_amount_confusion", Issue.WARNING, "ALL", field, "ALL",
                    f"Count field has large decimal values (median={median:,.2f}), may contain amounts"
                ))

        if is_amount and median < 100 and median > 0:
            # Amount field with small integer values might be counts
            all_int = all(v == int(v) for v in values)
            if all_int:
                issues.append(Issue(
                    state, "count_amount_confusion", Issue.WARNING, "ALL", field, "ALL",
                    f"Amount field has small integer values (median={median:,.0f}), may contain counts"
                ))


def check_missing_districts(state, periods_data, issues):
    """Check 4: Districts that appear in most periods but disappear for 1-2 and reappear."""
    dist_presence = defaultdict(set)  # district -> set of period indices
    total_periods = len(periods_data)

    for p_idx, (period_str, districts) in enumerate(periods_data):
        for d in districts:
            dist = d.get("district", "Unknown")
            dist_presence[dist].add(p_idx)

    for dist, present_indices in dist_presence.items():
        if len(present_indices) < 3:
            continue  # too few appearances to judge

        sorted_indices = sorted(present_indices)
        first, last = sorted_indices[0], sorted_indices[-1]

        for idx in range(first, last + 1):
            if idx not in present_indices:
                # Check if this is a gap (present before and after)
                before = any(i in present_indices for i in range(max(first, idx - MISSING_GAP_TOLERANCE), idx))
                after = any(i in present_indices for i in range(idx + 1, min(last + 1, idx + MISSING_GAP_TOLERANCE + 1)))
                if before and after:
                    period_str = periods_data[idx][0] if idx < len(periods_data) else f"index {idx}"
                    issues.append(Issue(
                        state, "missing_district", Issue.WARNING, dist, "-", period_str,
                        f"District missing from this period but present in adjacent periods"
                    ))


def check_duplicate_fields(state, periods_data, issues):
    """Check 5: Two fields in same category with >90% identical values."""
    # Build field value vectors keyed by (district, period_idx)
    field_vectors = defaultdict(dict)  # field -> {(dist, p_idx): value}

    for p_idx, (period_str, districts) in enumerate(periods_data):
        for d in districts:
            dist = d.get("district", "Unknown")
            for field in get_data_fields(d):
                val = d[field]
                val = numeric_value(val)
                if val is not None:
                    field_vectors[field][(dist, p_idx)] = val

    # Group fields by category
    cat_fields = defaultdict(list)
    for field in field_vectors:
        cat_fields[get_category(field)].append(field)

    flagged = set()
    for cat, fields in cat_fields.items():
        if len(fields) < 2:
            continue
        for i in range(len(fields)):
            for j in range(i + 1, len(fields)):
                f1, f2 = fields[i], fields[j]
                key_pair = tuple(sorted([f1, f2]))
                if key_pair in flagged:
                    continue

                common_keys = set(field_vectors[f1].keys()) & set(field_vectors[f2].keys())
                if len(common_keys) < 5:
                    continue

                match_count = sum(
                    1 for k in common_keys
                    if abs(field_vectors[f1][k] - field_vectors[f2][k]) < 0.01
                )
                ratio = match_count / len(common_keys)
                if ratio >= DUPLICATE_THRESHOLD:
                    flagged.add(key_pair)
                    issues.append(Issue(
                        state, "duplicate_field", Issue.WARNING, "ALL", f"{f1} vs {f2}", "ALL",
                        f"Fields are {ratio:.0%} identical across {len(common_keys)} data points in category '{cat}'"
                    ))


def check_outliers(state, periods_data, issues):
    """Check 6: Values >3 std deviations from district's own historical mean."""
    dist_field_ts = defaultdict(list)

    for period_str, districts in periods_data:
        for d in districts:
            dist = d.get("district", "Unknown")
            for field in get_data_fields(d):
                val = d[field]
                val = numeric_value(val)
                if val is not None:
                    dist_field_ts[(dist, field)].append((period_str, val))

    for (dist, field), ts in dist_field_ts.items():
        if len(ts) < 4:
            continue

        values = [v for _, v in ts]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        stddev = math.sqrt(variance)

        if stddev == 0:
            continue

        for period_str, val in ts:
            z = abs(val - mean) / stddev
            if z > STDDEV_MULTIPLIER:
                issues.append(Issue(
                    state, "outlier", Issue.INFO, dist, field, period_str,
                    f"Value {val:,.2f} is {z:.1f} std devs from mean {mean:,.2f} (stddev={stddev:,.2f})"
                ))


def check_period_coverage(state, periods_data, issues):
    """Check 7: Missing quarters in the expected sequence."""
    if len(periods_data) < 3:
        return

    parsed = []
    for period_str, _ in periods_data:
        y, m = parse_period(period_str)
        if y < 9999 and m > 0:
            parsed.append((y, m, period_str))

    parsed.sort()
    if not parsed:
        return

    # Generate expected quarterly sequence from first to last
    expected = []
    quarter_months = [3, 6, 9, 12]
    start_y, start_m, _ = parsed[0]
    end_y, end_m, _ = parsed[-1]

    y, m_idx = start_y, quarter_months.index(start_m) if start_m in quarter_months else 0
    while (y, quarter_months[m_idx]) <= (end_y, end_m):
        expected.append((y, quarter_months[m_idx]))
        m_idx += 1
        if m_idx >= 4:
            m_idx = 0
            y += 1

    actual_set = set((y, m) for y, m, _ in parsed)
    month_names = {3: "March", 6: "June", 9: "September", 12: "December"}

    gaps = []
    for y, m in expected:
        if (y, m) not in actual_set:
            gaps.append(f"{month_names[m]} {y}")

    if gaps:
        issues.append(Issue(
            state, "period_gap", Issue.WARNING, "ALL", "-", "ALL",
            f"Missing {len(gaps)} quarter(s): {', '.join(gaps[:10])}" +
            (f" ...and {len(gaps) - 10} more" if len(gaps) > 10 else "")
        ))


# ── Report generation ──────────────────────────────────────────────────────────

def generate_report(all_issues, states_processed, report_path=REPORT_PATH):
    """Print the validation summary and optionally write a Markdown report."""

    # Summary counts: state -> issue_type -> count
    summary = defaultdict(lambda: defaultdict(int))
    severity_counts = defaultdict(int)
    for issue in all_issues:
        summary[issue.state][issue.issue_type] += 1
        severity_counts[issue.severity] += 1

    issue_types = sorted(set(i.issue_type for i in all_issues))

    # ── Console summary ────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("PROJECT FINER - DATA VALIDATION SUMMARY")
    print("=" * 80)
    print(f"States processed: {len(states_processed)}")
    print(f"Total issues: {len(all_issues)}")
    print(f"  Critical: {severity_counts.get('critical', 0)}")
    print(f"  Warning:  {severity_counts.get('warning', 0)}")
    print(f"  Info:     {severity_counts.get('info', 0)}")
    print()

    if issue_types:
        # Print table header
        col_w = 14
        header = f"{'State':<22}" + "".join(f"{t[:col_w]:<{col_w}}" for t in issue_types) + "Total"
        print(header)
        print("-" * len(header))

        for state in sorted(states_processed):
            row = f"{state:<22}"
            total = 0
            for it in issue_types:
                c = summary[state].get(it, 0)
                total += c
                row += f"{c:<{col_w}}"
            row += str(total)
            print(row)

        # Totals row
        print("-" * len(header))
        row = f"{'TOTAL':<22}"
        grand = 0
        for it in issue_types:
            c = sum(summary[s].get(it, 0) for s in states_processed)
            grand += c
            row += f"{c:<{col_w}}"
        row += str(grand)
        print(row)
    else:
        print("No issues found. Data looks clean!")

    print()

    # ── Markdown report ────────────────────────────────────────────────────
    lines = []
    lines.append("# Project FINER - Data Validation Report")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"\nStates processed: {len(states_processed)}")
    lines.append(f"Total issues: **{len(all_issues)}** (Critical: {severity_counts.get('critical', 0)}, "
                 f"Warning: {severity_counts.get('warning', 0)}, Info: {severity_counts.get('info', 0)})")

    # Summary table
    if issue_types:
        lines.append("\n## Summary by State and Issue Type\n")
        lines.append("| State | " + " | ".join(issue_types) + " | Total |")
        lines.append("| --- | " + " | ".join(["---"] * len(issue_types)) + " | --- |")
        for state in sorted(states_processed):
            cells = []
            total = 0
            for it in issue_types:
                c = summary[state].get(it, 0)
                total += c
                cells.append(str(c) if c > 0 else "-")
            lines.append(f"| {state} | " + " | ".join(cells) + f" | {total} |")

    # Detailed findings by state
    lines.append("\n## Detailed Findings\n")

    for state in sorted(states_processed):
        state_issues = [i for i in all_issues if i.state == state]
        if not state_issues:
            continue

        lines.append(f"\n### {state.replace('-', ' ').title()}\n")

        # Group by type
        by_type = defaultdict(list)
        for i in state_issues:
            by_type[i.issue_type].append(i)

        for itype in sorted(by_type.keys()):
            items = by_type[itype]
            lines.append(f"\n#### {itype.replace('_', ' ').title()} ({len(items)} issues)\n")

            # Cap output to avoid massive reports
            shown = items[:50]
            for item in shown:
                sev_icon = {"critical": "**CRITICAL**", "warning": "WARNING", "info": "info"}.get(item.severity, "")
                lines.append(f"- [{sev_icon}] **{item.district}** | `{item.field}` @ {item.period}: {item.message}")

            if len(items) > 50:
                lines.append(f"\n*...and {len(items) - 50} more issues of this type (run with --verbose for full output)*\n")

    report_text = "\n".join(lines) + "\n"
    if report_path is not None:
        report_path.write_text(report_text)
        print(f"Detailed report written to: {report_path}")
    else:
        print("Detailed report not written (--no-report).")

    return severity_counts.get("critical", 0) > 0


# ── Main ───────────────────────────────────────────────────────────────────────

def validate_state(state_slug, verbose=False):
    """Run all validations for a single state. Returns list of Issues."""
    data = load_state_data(state_slug)
    if data is None:
        if verbose:
            print(f"  Skipping {state_slug}: no timeseries file found")
        return []

    if verbose:
        n_periods = len(data)
        n_districts = sum(len(dists) for _, dists in data)
        print(f"  {state_slug}: {n_periods} periods, {n_districts} total district-records")

    issues = []

    check_10x_jumps(state_slug, data, issues)
    check_column_shifts(state_slug, data, issues)
    check_count_amount_confusion(state_slug, data, issues)
    check_missing_districts(state_slug, data, issues)
    check_duplicate_fields(state_slug, data, issues)
    check_outliers(state_slug, data, issues)
    check_period_coverage(state_slug, data, issues)

    if verbose:
        print(f"    -> {len(issues)} issues found")

    return issues


def main():
    parser = argparse.ArgumentParser(description="Project FINER Data Validation")
    parser.add_argument("--state", type=str, default=None,
                        help="Validate a single state (slug, e.g. 'assam' or 'west-bengal')")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed progress output")
    parser.add_argument("--waivers", type=str, default=None,
                        help="Path to the reviewed observation-level critical waiver ledger. "
                             "Every new fingerprint fails independently.")
    parser.add_argument("--write-waivers", type=str, default=None,
                        help="Bootstrap an exact waiver ledger from current critical issues. "
                             "Use once; do not overwrite a reviewed ledger wholesale.")
    parser.add_argument("--waiver-days", type=int, default=90,
                        help="Validity period used only with --write-waivers (default: 90).")
    parser.add_argument("--report", type=Path, default=REPORT_PATH,
                        help="Markdown report path (default: DATA_VALIDATION_REPORT.md)")
    parser.add_argument("--no-report", action="store_true",
                        help="Do not write the Markdown report (useful for clean CI checks)")
    args = parser.parse_args()

    if not SLBC_DIR.exists():
        print(f"ERROR: SLBC data directory not found: {SLBC_DIR}", file=sys.stderr)
        sys.exit(1)

    # Discover states
    if args.state:
        states = [args.state]
        if not (SLBC_DIR / args.state).is_dir():
            print(f"ERROR: State directory not found: {SLBC_DIR / args.state}", file=sys.stderr)
            sys.exit(1)
    else:
        states = sorted([
            d.name for d in SLBC_DIR.iterdir()
            if d.is_dir() and (d / f"{d.name}_fi_timeseries.json").exists()
        ])

    print(f"Validating {len(states)} state(s)...")
    if args.verbose:
        print()

    all_issues = []
    for state in states:
        issues = validate_state(state, verbose=args.verbose)
        all_issues.extend(issues)

    report_path = None if args.no_report else args.report
    has_critical = generate_report(all_issues, states, report_path=report_path)

    criticals = [i for i in all_issues if i.severity == Issue.CRITICAL]

    if args.write_waivers:
        if args.waiver_days < 1:
            print("ERROR: --waiver-days must be positive", file=sys.stderr)
            sys.exit(2)
        created_on = date.today()
        ledger = build_waiver_ledger(
            criticals,
            created_on=created_on,
            expires_on=created_on + timedelta(days=args.waiver_days),
        )
        write_waiver_ledger(Path(args.write_waivers), ledger)
        print(f"\nWrote waiver ledger: {args.write_waivers} "
              f"({len(criticals)} exact fingerprints; expires "
              f"{ledger['waiver']['expires_on']})\n")
        sys.exit(0)

    if args.waivers:
        waiver_path = Path(args.waivers)
        if not waiver_path.exists():
            print(f"ERROR: waiver ledger not found: {waiver_path}", file=sys.stderr)
            sys.exit(2)
        try:
            ledger = load_waiver_ledger(waiver_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: invalid waiver ledger: {exc}", file=sys.stderr)
            sys.exit(2)
        unwaived, resolved, ledger_errors = evaluate_waiver_ledger(criticals, ledger)
        print(f"\nWaivers: {ledger.get('total_waived', 0)} exact fingerprints; "
              f"{len(criticals)} critical now.")
        if resolved:
            print(f"  {len(resolved)} waived finding(s) are resolved; remove their fingerprints in review.")
        if ledger_errors:
            print("\nResult: invalid waiver ledger. Exit code 1.")
            for error in ledger_errors:
                print(f"  - {error}")
            sys.exit(1)
        if unwaived:
            print(f"\nResult: {len(unwaived)} NEW unwaived critical finding(s). Exit code 1.\n")
            for issue in unwaived[:20]:
                print(f"  {issue_fingerprint(issue)}  {issue}")
            if len(unwaived) > 20:
                print(f"  ...and {len(unwaived) - 20} more")
            print("\n  Fix the findings or add individually reviewed fingerprints with an expiry.\n")
            sys.exit(1)
        print("\nResult: No new critical fingerprints. Exit code 0.\n")
        sys.exit(0)

    if has_critical:
        print("\nResult: CRITICAL issues found. Exit code 1.\n")
        sys.exit(1)
    else:
        print("\nResult: No critical issues. Exit code 0.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
