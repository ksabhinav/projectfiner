#!/usr/bin/env python3
"""Record every North-East syntax hazard without guessing corrected values."""

import argparse
import hashlib
import json
from collections import Counter

from build_north_east_indicator_inventory import (
    ROOT, STATES, classify_value, json_pointer_token, profile_state,
    reporting_period, serialise, source_path,
)
from validate_release_data import strict_json_loads


OUTPUT = ROOT / "public/data-contracts/north-east-value-dispositions.json"
ASSAM_OUTPUT = ROOT / "db/assam_split_number_quarantine.json"
POLICIES = {
    "split-numeric-tokens": (
        "quarantined", "split_numeric_tokens",
        "Multiple numbers occupy one cell. Re-extract the source table before analytical use.",
    ),
    "spreadsheet-error": (
        "quarantined", "source_formula_error",
        "The source contains a spreadsheet error, not a numeric observation. Do not substitute zero.",
    ),
    "invalid-numeric-grouping": (
        "quarantined", "invalid_numeric_grouping",
        "Comma grouping is malformed. Check the source before removing separators.",
    ),
    "non-finite": (
        "quarantined", "non_finite_value",
        "A non-finite value is not a usable numeric observation.",
    ),
    "percentage-text": (
        "suspect", "percentage_definition_unreviewed",
        "Verify the indicator definition, scale and reporting base before interpreting the percentage suffix.",
    ),
    "missing-marker": (
        "suspect", "missing_reason_unresolved",
        "The source's missing marker has no confirmed meaning. Do not infer zero, suppression or not-applicable.",
    ),
}


def build_dispositions():
    states, records = [], []
    seen = set()
    for slug, blob_sha in STATES:
        raw = source_path(slug).read_bytes()
        profile = profile_state(slug, blob_sha, raw)
        source = strict_json_loads(raw.decode("utf-8"))
        counts = Counter()
        for pi, period in enumerate(source["periods"]):
            month = reporting_period(period["period"])
            for ri, row in enumerate(period["districts"]):
                for field, value in sorted(row.items()):
                    if "__" not in field:
                        continue
                    value_class = classify_value(value)
                    if value_class not in POLICIES:
                        continue
                    identity = (slug, month, row["district"], field)
                    if identity in seen:
                        raise ValueError(f"Duplicate disposition identity: {identity}")
                    seen.add(identity)
                    status, flag, reason = POLICIES[value_class]
                    record_id = hashlib.sha256(
                        json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()
                    ).hexdigest()
                    records.append({
                        "observationId": record_id,
                        "stateSlug": slug,
                        "period": month,
                        "sourcePeriodLabel": period["period"],
                        "districtLabel": row["district"],
                        "sourceField": field,
                        "sourceValue": value,
                        "sourceArtifact": profile["sourceArtifact"],
                        "sourceArtifactSha256": profile["sourceArtifactSha256"],
                        "sourceJsonPointer": (
                            f"/periods/{pi}/districts/{ri}/{json_pointer_token(field)}"
                        ),
                        "valueClass": value_class,
                        "qualityStatus": status,
                        "qualityFlag": flag,
                        "numericValue": None,
                        "analyticalUse": "excluded_pending_source_review",
                        "reason": reason,
                    })
                    counts[value_class] += 1
        for value_class in POLICIES:
            if counts[value_class] != profile["valueClassCounts"][value_class]:
                raise ValueError(f"{slug}: incomplete {value_class} dispositions")
        states.append({
            "stateSlug": slug,
            "sourceArtifact": profile["sourceArtifact"],
            "sourceGitBlobSha": blob_sha,
            "sourceArtifactSha256": profile["sourceArtifactSha256"],
            "recordCount": sum(counts.values()),
            "valueClassCounts": dict(sorted(counts.items())),
        })
    records.sort(key=lambda r: (r["stateSlug"], r["period"], r["districtLabel"], r["sourceField"]))
    return {
        "schemaVersion": "north-east-value-dispositions-v1",
        "qualityTier": "raw-experimental",
        "generatedBy": "db/build_north_east_value_dispositions.py",
        "policy": {
            "scope": "Syntax hazards, percentage text and explicit missing markers in all eight pinned North-East time-series artifacts. Free text, blank cells and absent keys remain covered by the field inventory.",
            "rawValues": "Source artifacts remain unchanged. Null numericValue means excluded from numeric analysis, never zero or a guessed correction.",
            "enforcement": "The shared browser parser and unified SLBC importer accept only complete finite numbers with valid comma grouping. These syntax dispositions apply without downloading this ledger.",
            "provenance": "Hashes and JSON Pointers identify committed artifacts. They do not assert original document/page verification or certification.",
        },
        "summary": {
            "stateCount": len(states),
            "recordCount": len(records),
            "quarantinedCount": sum(r["qualityStatus"] == "quarantined" for r in records),
            "reviewRequiredCount": sum(r["qualityStatus"] == "suspect" for r in records),
            "valueClassCounts": dict(sorted(Counter(r["valueClass"] for r in records).items())),
        },
        "states": states,
        "records": records,
    }


def assam_quarantine(dispositions):
    state = next(s for s in dispositions["states"] if s["stateSlug"] == "assam")
    return {
        "schema_version": "assam-split-number-quarantine-v2",
        "issue_id": "FINER-003",
        "state": "assam",
        "source_artifact": "public" + state["sourceArtifact"],
        "source_sha": state["sourceGitBlobSha"],
        "source_artifact_sha256": state["sourceArtifactSha256"],
        "disposition": "excluded_from_clean_analytical_views",
        "generated_by": "db/build_north_east_value_dispositions.py",
        "records": [{
            "period": r["sourcePeriodLabel"], "district": r["districtLabel"],
            "field": r["sourceField"], "raw_value": r["sourceValue"],
            "quality_status": r["qualityStatus"], "quality_flag": r["qualityFlag"],
            "reason": r["reason"], "source_json_pointer": r["sourceJsonPointer"],
        } for r in dispositions["records"]
            if r["stateSlug"] == "assam" and r["valueClass"] == "split-numeric-tokens"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build_dispositions()
    outputs = {OUTPUT: data, ASSAM_OUTPUT: assam_quarantine(data)}
    for path, payload in outputs.items():
        rendered = serialise(payload)
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != rendered:
                raise SystemExit(f"North-East value dispositions are stale: {path.name}")
        else:
            path.write_text(rendered, encoding="utf-8")
    print(f"North-East value dispositions: {data['summary']}")


if __name__ == "__main__":
    main()
