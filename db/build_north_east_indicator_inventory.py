#!/usr/bin/env python3
"""Build the state-scoped North-East SLBC indicator inventory."""

import argparse
import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

from build_release_manifest import normalise_period
from validate_release_data import strict_json_loads


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "data-contracts" / "north-east-indicator-inventory.json"
REVIEW_OUTPUT = ROOT / "public" / "data-contracts" / "north-east-field-review.csv"
STATES = [
    ("arunachal-pradesh", "8d0db11a048e079472028f42ad765f4d7ca7f407"),
    ("assam", "84dafd2a948a0096cb105520c36ba14ac95f21aa"),
    ("manipur", "094cc9f5e8de3204581170224f21dc20af4ddfac"),
    ("meghalaya", "b9859c03b67724e3e38074c2e530ad0cbe1def6d"),
    ("mizoram", "2b04bcd7a5acf457ebf7e881ca86a8e00cd038cd"),
    ("nagaland", "92eef9130cd140fe5b60f6889baeee6e24722f87"),
    ("sikkim", "c543b5a4d8d09b2051d941c4e9a197495b25ed34"),
    ("tripura", "8d40f215cbfff0b8fc67db4709b5cbf0c3a04e52"),
]
# Accept plain decimals and correctly grouped Western or Indian thousands.
# Blind comma removal would turn malformed values such as '1,2,3' into 123.
NUMERIC_LIKE = re.compile(
    r"^[+-]?(?:(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+|"
    r"[0-9]{1,2}(?:,[0-9]{2})+,[0-9]{3})(?:\.[0-9]*)?|\.[0-9]+)$"
)
MISSING_MARKERS = {"_", "-", "NA", "N/A"}
FORMULA_ERRORS = {
    "#DIV/0!", "#N/A", "#VALUE!", "#REF!", "#NAME?", "#NUM!",
    "#NULL!", "#SPILL!", "#CALC!",
}
VALUE_CLASSES = (
    "numeric", "blank", "null", "missing-marker", "percentage-text",
    "spreadsheet-error", "split-numeric-tokens", "invalid-numeric-grouping",
    "non-finite", "text", "unsupported-type",
)
EXAMPLE_CLASSES = set(VALUE_CLASSES) - {"numeric", "blank", "null"}
EXAMPLES_PER_CLASS = 2


def classify_value(value):
    """Describe cell syntax without assigning units or interpreting missingness."""
    if value is None:
        return "null"
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return "unsupported-type"
    if isinstance(value, (int, float)):
        return "numeric" if isinstance(value, int) or math.isfinite(value) else "non-finite"
    raw = value.strip()
    if not raw:
        return "blank"
    if raw.upper() in MISSING_MARKERS:
        return "missing-marker"
    if raw.upper() in FORMULA_ERRORS:
        return "spreadsheet-error"
    if raw.lower() in {"nan", "+nan", "-nan", "inf", "+inf", "-inf",
                        "infinity", "+infinity", "-infinity"}:
        return "non-finite"
    if NUMERIC_LIKE.fullmatch(raw):
        return "numeric"
    if raw.endswith("%") and NUMERIC_LIKE.fullmatch(raw[:-1].strip()):
        return "percentage-text"
    tokens = raw.split()
    if len(tokens) > 1 and all(NUMERIC_LIKE.fullmatch(token) for token in tokens):
        return "split-numeric-tokens"
    if "," in raw and NUMERIC_LIKE.fullmatch(raw.replace(",", "")):
        return "invalid-numeric-grouping"
    return "text"


def reporting_period(label):
    period = normalise_period(str(label), {"period": str(label)})
    if not period or period[-2:] not in {"03", "06", "09", "12"}:
        raise ValueError(f"Invalid quarterly period label: {label!r}")
    return period


def json_pointer_token(value):
    return value.replace("~", "~0").replace("/", "~1")


def profile_state(slug, git_blob_sha, raw_bytes):
    actual_sha = hashlib.sha1(
        b"blob " + str(len(raw_bytes)).encode("ascii") + b"\0" + raw_bytes
    ).hexdigest()
    if actual_sha != git_blob_sha:
        raise ValueError(f"{slug}: source Git blob hash changed; review the source pin")
    data = strict_json_loads(raw_bytes.decode("utf-8"))
    if not isinstance(data, dict) or data.get("state") != slug:
        raise ValueError(f"{slug}: source state does not match inventory state")
    periods = data.get("periods")
    if not isinstance(periods, list):
        raise ValueError(f"{slug}: periods must be an array")
    fields = {}
    district_labels = set()
    record_count = 0
    seen_periods = set()
    for period_index, period in enumerate(periods):
        if not isinstance(period, dict) or not isinstance(period.get("districts"), list):
            raise ValueError(f"{slug}: invalid period or districts container")
        period_label = reporting_period(period.get("period", ""))
        if period_label in seen_periods:
            raise ValueError(f"{slug}: duplicate period {period_label}")
        seen_periods.add(period_label)
        seen_districts = set()
        for record_index, record in enumerate(period["districts"]):
            if not isinstance(record, dict):
                raise ValueError(f"{slug}: district record must be an object")
            district = record.get("district")
            if not isinstance(district, str) or not district.strip():
                raise ValueError(f"{slug}: missing district label in {period_label}")
            if district in seen_districts:
                raise ValueError(f"{slug}: duplicate district label {district!r} in {period_label}")
            seen_districts.add(district)
            effective_period = reporting_period(record.get("period") or period["period"])
            if effective_period != period_label:
                raise ValueError(f"{slug}: record period disagrees with its container")
            record_count += 1
            district_labels.add(district)
            for source_field, value in record.items():
                if "__" not in source_field:
                    continue
                entry = fields.setdefault(source_field, {
                    "districts": set(), "periods": set(), "classes": Counter(),
                    "numeric_districts": set(), "numeric_periods": set(),
                    "nonblank": 0, "zeros": 0, "examples": {},
                })
                entry["districts"].add(district)
                entry["periods"].add(effective_period)
                value_class = classify_value(value)
                entry["classes"][value_class] += 1
                if value_class not in {"blank", "null"}:
                    entry["nonblank"] += 1
                if value_class == "numeric":
                    entry["numeric_districts"].add(district)
                    entry["numeric_periods"].add(effective_period)
                    if Decimal(str(value).strip().replace(",", "")) == 0:
                        entry["zeros"] += 1
                if value_class in EXAMPLE_CLASSES:
                    examples = entry["examples"].setdefault(value_class, [])
                    if len(examples) < EXAMPLES_PER_CLASS:
                        example = {
                            "valueClass": value_class,
                            "period": effective_period,
                            "districtLabel": district,
                            "sourceJsonPointer": (
                                f"/periods/{period_index}/districts/{record_index}/"
                                f"{json_pointer_token(source_field)}"
                            ),
                        }
                        # Free text can contain contacts or meeting notes. A
                        # locator is sufficient; do not republish it in the index.
                        if value_class not in {"text", "unsupported-type"}:
                            example["sourceValue"] = value
                        examples.append(example)

    field_entries = []
    totals = Counter()
    for source_field, stats in sorted(fields.items()):
        category, field_name = source_field.split("__", 1)
        counts = {key: stats["classes"][key] for key in VALUE_CLASSES}
        totals.update(counts)
        present = sum(counts.values())
        numeric_count = counts["numeric"]
        other_count = stats["nonblank"] - numeric_count
        if numeric_count and other_count:
            value_profile = "mixed"
        elif other_count:
            value_profile = "text"
        elif numeric_count:
            value_profile = "numeric-like"
        else:
            value_profile = "blank-only"
        field_entries.append({
            "indicatorId": f"slbc.{slug}.{source_field}",
            "sourceField": source_field,
            "category": category,
            "fieldName": field_name,
            "presentCount": present,
            "absentCount": record_count - present,
            "nonblankCount": stats["nonblank"],
            "periodCount": len(stats["periods"]),
            "districtLabelCount": len(stats["districts"]),
            "numericCount": numeric_count,
            "zeroCount": stats["zeros"],
            "numericPeriodCount": len(stats["numeric_periods"]),
            "numericPeriods": sorted(stats["numeric_periods"]),
            "numericDistrictLabelCount": len(stats["numeric_districts"]),
            "valueProfile": value_profile,
            "valueClassCounts": counts,
            "reviewExamples": [
                example for key in VALUE_CLASSES
                for example in stats["examples"].get(key, [])
            ],
            "unit": None,
            "unitStatus": "not-reviewed",
            "measureType": None,
            "measureTypeStatus": "not-reviewed",
            "crossStateComparable": False,
        })
    return {
        "stateSlug": slug,
        "sourceArtifact": f"/slbc-data/{slug}/{slug}_fi_timeseries.json",
        "sourceGitBlobSha": git_blob_sha,
        "sourceArtifactSha256": hashlib.sha256(raw_bytes).hexdigest(),
        "periodCount": len(periods),
        "recordCount": record_count,
        "districtLabelCount": len(district_labels),
        "fieldCount": len(field_entries),
        "numericFieldCount": sum(field["numericCount"] > 0 for field in field_entries),
        "valueClassCounts": {key: totals[key] for key in VALUE_CLASSES},
        "fields": field_entries,
    }


def source_path(slug):
    return (
        ROOT
        / "public"
        / "slbc-data"
        / slug
        / f"{slug}_fi_timeseries.json"
    )


def build_inventory():
    state_entries = []
    lexical_coverage = {}

    for slug, git_blob_sha in STATES:
        state = profile_state(slug, git_blob_sha, source_path(slug).read_bytes())
        state_entries.append(state)
        for field in state["fields"]:
            lexical_coverage.setdefault(field["sourceField"], {})[slug] = set(
                field["numericPeriods"]
            )

    shared = [
        {
            "sourceField": field,
            "stateCount": len(states),
            "states": sorted(states),
            "numericStates": sorted(slug for slug, periods in states.items() if periods),
            "commonNumericPeriods": sorted(set.intersection(*states.values())),
            "commonNumericPeriodCount": len(set.intersection(*states.values())),
            "semanticEquivalence": "not-reviewed",
        }
        for field, states in sorted(lexical_coverage.items())
        if len(states) > 1
    ]
    field_count = sum(state["fieldCount"] for state in state_entries)
    return {
        "registrySchemaVersion": "north-east-field-inventory-v2",
        "qualityTier": "raw-experimental",
        "scope": {
            "region": "North East India",
            "stateCount": len(state_entries),
            "fieldEntryCount": field_count,
            "description": (
                "State-scoped inventory of raw SLBC field labels. It is a "
                "standardization-readiness artifact, not a comparable dataset."
            ),
        },
        "policy": {
            "indicatorIdentity": (
                "State slug plus exact raw source field; no cross-state "
                "semantic equivalence is asserted."
            ),
            "units": "Not inferred from field names; review is required.",
            "measureTypes": "Not inferred from field names; review is required.",
            "lexicalMatches": (
                "Exact shared labels are discovery candidates only and do not "
                "establish comparable definitions, units, or periods."
            ),
            "numericCoverage": (
                "Counts syntactically numeric cells, including zero. It does not "
                "establish analytical validity, complete geography, or comparability."
            ),
            "missingValues": (
                "Absent keys, blank strings, JSON nulls, and explicit _, -, NA, N/A "
                "markers are counted separately. Their source meaning is unresolved; "
                "none is converted to zero, suppression, or not-applicable."
            ),
            "numericSyntax": (
                "Plain decimals and valid Indian/Western comma grouping are numeric. "
                "Percentage suffixes, spreadsheet errors, multiple numeric tokens, "
                "malformed grouping, and non-finite values remain separate classes. "
                "No number is selected or unit inferred from an ambiguous cell."
            ),
            "coverageDenominator": (
                "Absent counts use the state's existing raw district-period records. "
                "They do not imply the field should exist for every record. Legacy "
                "period/district counts describe key presence, including blank cells."
            ),
            "sharedPeriodCoverage": (
                "Intersection of numeric reporting months across every state holding "
                "the exact label; a state with no numeric values makes it empty. "
                "Period overlap alone does not establish comparable measures."
            ),
            "reviewExamples": (
                "At most two source-order examples per non-numeric class per field. "
                "JSON Pointers locate cells in the hashed local artifact, not upstream "
                "source pages. Free text is not copied into this inventory."
            ),
            "nextGate": (
                "Review definitions, units, measure types, geography vintage, "
                "and provenance before promoting any field to standardized preview."
            ),
        },
        "states": state_entries,
        "sharedExactFieldLabels": shared,
    }


def serialise(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def serialise_review(data):
    output = io.StringIO(newline="")
    columns = [
        "state_slug", "indicator_id", "source_field", "source_artifact",
        "source_artifact_sha256", "state_record_count", "present_count",
        "absent_count", "nonblank_count", "numeric_count", "zero_count",
        "presence_period_count", "numeric_period_count", "numeric_district_label_count",
        "numeric_periods", *[f"{key.replace('-', '_')}_count" for key in VALUE_CLASSES if key != "numeric"],
        "unit_status", "measure_type_status", "cross_state_comparable",
    ]
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for state in data["states"]:
        for field in state["fields"]:
            row = {
                "state_slug": state["stateSlug"],
                "indicator_id": field["indicatorId"],
                "source_field": field["sourceField"],
                "source_artifact": state["sourceArtifact"],
                "source_artifact_sha256": state["sourceArtifactSha256"],
                "state_record_count": state["recordCount"],
                "present_count": field["presentCount"],
                "absent_count": field["absentCount"],
                "nonblank_count": field["nonblankCount"],
                "numeric_count": field["numericCount"],
                "zero_count": field["zeroCount"],
                "presence_period_count": field["periodCount"],
                "numeric_period_count": field["numericPeriodCount"],
                "numeric_district_label_count": field["numericDistrictLabelCount"],
                "numeric_periods": "|".join(field["numericPeriods"]),
                "unit_status": field["unitStatus"],
                "measure_type_status": field["measureTypeStatus"],
                "cross_state_comparable": "false",
            }
            row.update({
                f"{key.replace('-', '_')}_count": count
                for key, count in field["valueClassCounts"].items() if key != "numeric"
            })
            writer.writerow(row)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    inventory = build_inventory()
    outputs = {OUTPUT: serialise(inventory), REVIEW_OUTPUT: serialise_review(inventory)}
    if args.check:
        for path, rendered in outputs.items():
            if not path.exists() or path.read_text(encoding="utf-8") != rendered:
                raise SystemExit(f"North-East review artifact is stale: {path.name}")
        return 0
    for path, rendered in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
