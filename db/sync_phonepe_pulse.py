#!/usr/bin/env python3
"""Replace FINER's PhonePe series from a pinned upstream Pulse checkout.

PhonePe's August/September 2026 release restated every historical period and
explicitly warns against joining the new figures to older downloads. This
sync therefore rebuilds the complete local series; it never appends a quarter.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
TIMESERIES = PUBLIC / "digital-payments" / "phonepe_district_timeseries.json"
INDICATOR_DIR = PUBLIC / "indicators" / "digital_transactions"
MANIFEST = PUBLIC / "indicators" / "manifest.json"
LGD_CODES = PUBLIC / "district_lgd_codes.json"
MONTHS = {1: "March", 2: "June", 3: "September", 4: "December"}
def district_name(value: str) -> str:
    cleaned = re.sub(r"\s+district$", "", value.strip(), flags=re.IGNORECASE)
    return cleaned.title()


def state_slug(value: str) -> str:
    """Match the frontend's normStateSlug convention exactly."""
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", value.lower().replace("&", "and")))


def identity_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z\s]", "", value.upper())).strip()


def canonical_districts() -> dict[tuple[str, str], str]:
    registry = json.loads(LGD_CODES.read_text(encoding="utf-8"))
    result = {}
    for item in registry["districts"]:
        canonical = item["district"]
        state = state_slug(item["state"])
        for name in [canonical, *(item.get("aliases") or [])]:
            result[(state, identity_name(name))] = canonical
    return result


def metric(payload: dict) -> tuple[int, float]:
    metrics = payload.get("metric") or []
    totals = [item for item in metrics if item.get("type") == "TOTAL"]
    if len(totals) != 1:
        raise ValueError(f"Expected one TOTAL transaction metric, got {metrics!r}")
    total = totals[0]
    return int(total["count"]), round(float(total["amount"]) / 100_000, 2)


def build(upstream: Path, revision: str) -> tuple[dict, dict[str, dict]]:
    tx_root = upstream / "data/map/transaction/hover/country/india/state"
    merchant_root = upstream / "data/map/merchant/hover/country/india/state"
    if not tx_root.is_dir() or not merchant_root.is_dir():
        raise FileNotFoundError("Upstream checkout does not contain PhonePe map transaction and merchant data")

    periods: dict[str, list[dict]] = {}
    indicator_files: dict[str, dict] = {}
    canonical = canonical_districts()
    for source in sorted(tx_root.glob("*/*/*.json")):
        state_source, year, quarter_text = source.parts[-3], source.parts[-2], source.stem
        quarter = int(quarter_text)
        period_code = f"{year}-{quarter * 3:02d}"
        period_label = f"{MONTHS[quarter]} {year}"
        state = state_slug(state_source)
        transaction_payload = json.loads(source.read_text(encoding="utf-8"))
        merchant_file = merchant_root / state_source / year / f"{quarter}.json"
        merchant_payload = json.loads(merchant_file.read_text(encoding="utf-8")) if merchant_file.exists() else {}
        merchants = merchant_payload.get("data", {}).get("hoverData") or {}
        merchant_by_name = {identity_name(name): int(value["registeredCount"]) for name, value in merchants.items()}

        for row in transaction_payload.get("data", {}).get("hoverDataList") or []:
            district = district_name(row["name"])
            district = canonical.get((state, identity_name(district)), district)
            count, amount_lakhs = metric(row)
            record = {
                "district": district,
                "period": period_label,
                "phonepe_upi__transaction_count": count,
                "phonepe_upi__transaction_amount": amount_lakhs,
                "phonepe_upi__registered_merchants": merchant_by_name.get(identity_name(row["name"])),
                "phonepe_upi__state": state,
            }
            periods.setdefault(period_code, []).append(record)

    serialised_periods = []
    for period_code in sorted(periods):
        records = sorted(periods[period_code], key=lambda row: (row["phonepe_upi__state"], row["district"]))
        identities = {(row["phonepe_upi__state"], row["district"].casefold()) for row in records}
        if len(identities) != len(records):
            raise ValueError(f"Duplicate state/district identity in {period_code}")
        label = f"{MONTHS[int(period_code[-2:]) // 3]} {period_code[:4]}"
        serialised_periods.append({
            "period": label,
            "period_code": period_code,
            "num_districts": len(records),
            "path": f"../indicators/digital_transactions/{period_code}.json",
        })
        phonepe_rows = [
            {
                "district": row["district"],
                "state": row["phonepe_upi__state"],
                "transaction_count": str(row["phonepe_upi__transaction_count"]),
                "transaction_amount": str(row["phonepe_upi__transaction_amount"]),
                **({"registered_merchants": str(row["phonepe_upi__registered_merchants"])} if row["phonepe_upi__registered_merchants"] is not None else {}),
            }
            for row in records
        ]
        existing_path = INDICATOR_DIR / f"{period_code}.json"
        if existing_path.exists():
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
            old_rows = {(row.get("state"), str(row.get("district", "")).casefold()): row for row in existing.get("districts", [])}
            for row in phonepe_rows:
                old = old_rows.get((row["state"], row["district"].casefold()), {})
                for key, value in old.items():
                    if key not in {"district", "state", "transaction_count", "transaction_amount", "registered_merchants"}:
                        row[key] = value

        indicator_files[period_code] = {
            "indicator": "digital_transactions",
            "quarter": period_code,
            "label": label,
            "source_revision": revision,
            "methodology_version": "phonepe-pulse-restated-amj-2026",
            "districts": phonepe_rows,
        }

    output = {
        "schema_version": 3,
        "storage": "quarterly-partitions",
        "source": "PhonePe Pulse",
        "source_url": "https://github.com/PhonePe/pulse",
        "source_revision": revision,
        "license": "CDLA-Permissive-2.0",
        "amount_unit": "Rs. Lakhs",
        "methodology_version": "phonepe-pulse-restated-amj-2026",
        "comparability_warning": "PhonePe restated all periods from January-March 2018. Do not join these figures to previously downloaded Pulse series or interpret the restatement boundary as growth.",
        "num_periods": len(serialised_periods),
        "num_district_periods": sum(item["num_districts"] for item in serialised_periods),
        "latest_period": serialised_periods[-1]["period_code"],
        "periods": serialised_periods,
    }
    return output, indicator_files


def dump(value: dict) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n"


def update_manifest(period_codes: list[str], *, check: bool) -> bool:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    desired = sorted(period_codes, reverse=True)
    manifest["quarters_by_indicator"]["digital_transactions"] = desired
    manifest["quarters"] = sorted(set(manifest["quarters"]) | set(desired), reverse=True)
    manifest["latest_quarter"] = manifest["quarters"][0]
    expected = dump(manifest)
    if check:
        return MANIFEST.read_text(encoding="utf-8") == expected
    MANIFEST.write_text(expected, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output, indicator_files = build(args.upstream, args.revision)

    expected_timeseries = dump(output)
    ok = TIMESERIES.exists() and TIMESERIES.read_text(encoding="utf-8") == expected_timeseries
    for period, payload in indicator_files.items():
        path = INDICATOR_DIR / f"{period}.json"
        ok = ok and path.exists() and path.read_text(encoding="utf-8") == dump(payload)
    if args.check:
        ok = ok and update_manifest(list(indicator_files), check=True)
        if not ok:
            print("Committed PhonePe outputs do not match the pinned upstream revision")
            return 1
        print(f"PhonePe sync verified: {output['num_periods']} periods through {output['latest_period']}")
        return 0

    TIMESERIES.write_text(expected_timeseries, encoding="utf-8")
    INDICATOR_DIR.mkdir(parents=True, exist_ok=True)
    for period, payload in indicator_files.items():
        (INDICATOR_DIR / f"{period}.json").write_text(dump(payload), encoding="utf-8")
    update_manifest(list(indicator_files), check=False)
    print(f"Wrote {sum(len(p['districts']) for p in indicator_files.values()):,} district-period rows across {output['num_periods']} periods through {output['latest_period']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
