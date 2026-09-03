#!/usr/bin/env python3
"""Build the deterministic Meghalaya long-format standardized preview.

This deliberately copies only registered source fields. It preserves the raw
cell text, does not derive missing totals, and marks unresolved provenance,
boundary, and source-semantic issues instead of silently repairing them.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SOURCE_PATH = PUBLIC / "slbc-data" / "meghalaya" / "meghalaya_complete.json"
GEOGRAPHY_PATH = PUBLIC / "district_lgd_codes.json"
REGISTRY_PATH = PUBLIC / "data-contracts" / "meghalaya-indicator-registry.json"
OUTPUT_PATH = PUBLIC / "data-contracts" / "meghalaya-standardized-preview.csv"

AADHAAR_TABLE = "aadhaar_authentication"
AADHAAR_FIELDS = {
    "Number of Aadhaar seeded CASA",
    "Number of Authenticated CASA",
    "Number of operative CASA",
}
BOUNDARY_CHANGE = "2022-06-30"
BOUNDARY_DISTRICTS = {"Eastern West Khasi Hills", "West Khasi Hills"}


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def district_codes(payload: dict) -> dict[str, str]:
    result = {}
    for item in payload.get("districts", []):
        if item.get("state_lgd_code") == 17:
            result[str(item["district"])] = str(item["lgd_code"])
    if len(result) != 12:
        raise ValueError(f"Expected 12 Meghalaya LGD districts, found {len(result)}")
    return result


def parse_number(raw_value: object, value_type: str) -> tuple[str, str]:
    source_value = str(raw_value).strip()
    if not source_value:
        raise ValueError("Selected source cells must not be blank")
    cleaned = source_value.replace(",", "")
    try:
        number = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric source value {source_value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"Non-finite numeric source value {source_value!r}")
    if value_type == "integer":
        if number != number.to_integral_value():
            raise ValueError(f"Expected an integer source value, got {source_value!r}")
        value = str(number.quantize(Decimal("1")))
    elif value_type == "decimal":
        value = format(number, "f")
    else:
        raise ValueError(f"Unsupported valueType {value_type!r}")
    return source_value, value


def observation_id(release_id: str, district_code: str, period: str,
                   indicator_id: str) -> str:
    identity = "|".join((release_id, "17", district_code, period, indicator_id))
    return f"obs-{hashlib.sha256(identity.encode()).hexdigest()[:20]}"


def boundary_metadata(period: str, district: str, registry: dict) -> tuple[str, str]:
    policy = registry["boundaryPolicy"]
    if period < BOUNDARY_CHANGE:
        version = policy["preChangeVersion"]
        status = "as-reported-pre-split"
    else:
        version = policy["postChangeVersion"]
        status = "as-reported-post-split"
    if district not in BOUNDARY_DISTRICTS:
        status = "not-affected"
    return version, status


def build_rows(source: dict, geography: dict, registry: dict) -> list[dict[str, str]]:
    columns = registry["observationColumns"]
    required_columns = {
        "release_id", "state_lgd_code", "district_lgd_code", "period",
        "indicator_id", "value", "unit", "source_value", "source_id",
        "quality_status", "quality_flags",
    }
    if not required_columns.issubset(columns):
        raise ValueError("Indicator registry is missing required observation columns")

    indicators = registry.get("indicators", [])
    indicator_ids = [item["indicatorId"] for item in indicators]
    if len(indicators) != 13 or len(set(indicator_ids)) != len(indicator_ids):
        raise ValueError("Indicator registry must contain 13 unique indicators")

    by_table: dict[str, list[dict]] = {}
    for indicator in indicators:
        by_table.setdefault(indicator["sourceTable"], []).append(indicator)

    lgd_codes = district_codes(geography)
    rows = []
    quarters = source.get("quarters", {})
    for quarter_key, quarter in sorted(quarters.items()):
        period = datetime.strptime(quarter["as_on_date"], "%d-%m-%Y").date().isoformat()
        if not quarter_key.startswith(period[:7]):
            raise ValueError(f"Quarter key/date mismatch for {quarter_key}: {period}")
        tables = quarter.get("tables", {})
        for table_name, table_indicators in by_table.items():
            table = tables.get(table_name)
            if table is None:
                continue
            source_fields = set(table.get("fields", []))
            for indicator in table_indicators:
                if indicator["sourceField"] not in source_fields:
                    raise ValueError(
                        f"Missing registered field {indicator['sourceField']!r} "
                        f"in {quarter_key}/{table_name}"
                    )
            district_rows = table.get("districts", table.get("data", {}))
            if not isinstance(district_rows, dict):
                raise ValueError(f"Expected district mapping in {quarter_key}/{table_name}")

            anomaly_districts = set()
            if table_name == AADHAAR_TABLE:
                for district, values in district_rows.items():
                    seeded = Decimal(str(values["Number of Aadhaar seeded CASA"]).replace(",", ""))
                    authenticated = Decimal(str(values["Number of Authenticated CASA"]).replace(",", ""))
                    if authenticated > seeded:
                        anomaly_districts.add(district)

            expected_district_count = 11 if period < BOUNDARY_CHANGE else 12
            partial_coverage = len(district_rows) < expected_district_count
            for district, values in sorted(district_rows.items()):
                if district not in lgd_codes:
                    raise ValueError(f"Unmapped Meghalaya district {district!r}")
                boundary_version, boundary_status = boundary_metadata(
                    period, district, registry
                )
                for indicator in table_indicators:
                    source_field = indicator["sourceField"]
                    if source_field not in values:
                        raise ValueError(
                            f"Missing source cell {quarter_key}/{table_name}/"
                            f"{district}/{source_field}"
                        )
                    source_value, value = parse_number(
                        values[source_field], indicator["valueType"]
                    )
                    flags = ["source_document_unlinked"]
                    if district in BOUNDARY_DISTRICTS:
                        flags.append("boundary_not_harmonised")
                    if partial_coverage:
                        flags.append("partial_period_coverage")
                    if (
                        table_name == AADHAAR_TABLE
                        and district in anomaly_districts
                        and source_field in AADHAAR_FIELDS
                    ):
                        flags.append("semantic_scope_review_required")
                    district_code = lgd_codes[district]
                    indicator_id = indicator["indicatorId"]
                    row = {
                        "observation_id": observation_id(
                            registry["releaseId"], district_code, period, indicator_id
                        ),
                        "release_id": registry["releaseId"],
                        "schema_version": registry["schemaVersion"],
                        "state_lgd_code": "17",
                        "district_lgd_code": district_code,
                        "district": district,
                        "boundary_version": boundary_version,
                        "boundary_status": boundary_status,
                        "period": period,
                        "financial_year": str(quarter.get("fy", "")),
                        "periodicity": "quarterly",
                        "indicator_id": indicator_id,
                        "value": value,
                        "unit": indicator["unit"],
                        "source_value": source_value,
                        "source_field_label": source_field,
                        "source_id": registry["source"]["id"],
                        "source_artifact": registry["source"]["artifact"],
                        "source_table": table_name,
                        "source_page": "",
                        "missing_reason": "",
                        "quality_status": "suspect",
                        "quality_flags": "|".join(flags),
                    }
                    if set(row) != set(columns):
                        raise ValueError("Generated row does not match registered columns")
                    rows.append(row)

    identities = [row["observation_id"] for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("Generated duplicate observation identities")
    return rows


def serialise_rows(rows: list[dict[str, str]], columns: list[str]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def render() -> tuple[str, int]:
    registry = load_json(REGISTRY_PATH)
    rows = build_rows(load_json(SOURCE_PATH), load_json(GEOGRAPHY_PATH), registry)
    return serialise_rows(rows, registry["observationColumns"]), len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="Fail if the committed standardized preview is missing or stale.",
    )
    args = parser.parse_args()
    rendered, row_count = render()
    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
            print(f"{OUTPUT_PATH.relative_to(ROOT)} is stale; regenerate it")
            return 1
        print(f"{OUTPUT_PATH.relative_to(ROOT)} is current ({row_count} observations)")
        return 0
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8", newline="")
    print(f"wrote {OUTPUT_PATH.relative_to(ROOT)}: {row_count} observations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
