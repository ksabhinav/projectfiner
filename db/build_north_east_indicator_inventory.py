#!/usr/bin/env python3
"""Build the state-scoped North-East SLBC indicator inventory."""

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "data-contracts" / "north-east-indicator-inventory.json"
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
NUMERIC_LIKE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


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
        path = source_path(slug)
        data = json.loads(path.read_text(encoding="utf-8"))
        periods = data.get("periods", [])
        fields = {}
        district_labels = set()
        record_count = 0

        for period in periods:
            period_label = str(period.get("period") or "")
            for record in period.get("districts", []):
                record_count += 1
                district = str(record.get("district") or "")
                if district:
                    district_labels.add(district)
                effective_period = str(record.get("period") or period_label)
                for source_field, value in record.items():
                    if "__" not in source_field:
                        continue
                    entry = fields.setdefault(
                        source_field,
                        {
                            "districts": set(),
                            "periods": set(),
                            "present": 0,
                            "nonblank": 0,
                            "numeric_like": 0,
                            "text": 0,
                        },
                    )
                    entry["present"] += 1
                    if district:
                        entry["districts"].add(district)
                    if effective_period:
                        entry["periods"].add(effective_period)
                    raw = "" if value is None else str(value).strip()
                    if not raw:
                        continue
                    entry["nonblank"] += 1
                    if NUMERIC_LIKE.fullmatch(raw.replace(",", "")):
                        entry["numeric_like"] += 1
                    else:
                        entry["text"] += 1

        field_entries = []
        for source_field in sorted(fields):
            stats = fields[source_field]
            category, field_name = source_field.split("__", 1)
            if stats["text"] and stats["numeric_like"]:
                value_profile = "mixed"
            elif stats["text"]:
                value_profile = "text"
            elif stats["numeric_like"]:
                value_profile = "numeric-like"
            else:
                value_profile = "blank-only"
            field_entries.append(
                {
                    "indicatorId": f"slbc.{slug}.{source_field}",
                    "sourceField": source_field,
                    "category": category,
                    "fieldName": field_name,
                    "presentCount": stats["present"],
                    "nonblankCount": stats["nonblank"],
                    "periodCount": len(stats["periods"]),
                    "districtLabelCount": len(stats["districts"]),
                    "valueProfile": value_profile,
                    "unit": None,
                    "unitStatus": "not-reviewed",
                    "measureType": None,
                    "measureTypeStatus": "not-reviewed",
                    "crossStateComparable": False,
                }
            )
            lexical_coverage.setdefault(source_field, []).append(slug)

        state_entries.append(
            {
                "stateSlug": slug,
                "sourceArtifact": (
                    f"/slbc-data/{slug}/{slug}_fi_timeseries.json"
                ),
                "sourceGitBlobSha": git_blob_sha,
                "periodCount": len(periods),
                "recordCount": record_count,
                "districtLabelCount": len(district_labels),
                "fieldCount": len(field_entries),
                "fields": field_entries,
            }
        )

    shared = [
        {
            "sourceField": field,
            "stateCount": len(states),
            "states": sorted(states),
            "semanticEquivalence": "not-reviewed",
        }
        for field, states in sorted(lexical_coverage.items())
        if len(states) > 1
    ]
    field_count = sum(state["fieldCount"] for state in state_entries)
    return {
        "registrySchemaVersion": "north-east-field-inventory-v1",
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = serialise(build_inventory())
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("North-East indicator inventory is stale")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
