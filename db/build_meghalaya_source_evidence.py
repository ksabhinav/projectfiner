#!/usr/bin/env python3
"""Build the Meghalaya primary-source evidence acquisition ledger."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS_PATH = ROOT / "public/data-contracts/meghalaya-standardized-preview.csv"
INPUT_PATH = ROOT / "db/meghalaya_source_evidence_input.json"
OUTPUT_PATH = ROOT / "db/meghalaya_source_evidence.json"

PRODUCT_ID = "meghalaya-standardized-preview"
RELEASE_ID = "meghalaya-standardized-preview-v2"
SOURCE_ID = "slbc-meghalaya"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_unit_id(period: str, source_table: str) -> str:
    return f"meghalaya-{period}-{source_table.replace('_', '-')}"


def require_https(value: str, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute HTTPS URL")


def require_iso_date(value: str, field: str) -> None:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an ISO date") from exc


def validate_input(document: dict, expected_ids: set[str]) -> dict[str, dict]:
    expected_header = {
        "schemaVersion": "source-evidence-input-v1",
        "productId": PRODUCT_ID,
        "releaseId": RELEASE_ID,
        "sourceId": SOURCE_ID,
    }
    for field, expected in expected_header.items():
        if document.get(field) != expected:
            raise ValueError(f"Evidence input {field} must equal {expected!r}")

    indexed: dict[str, dict] = {}
    for item in document.get("evidence", []):
        unit_id = str(item.get("evidenceUnitId", "")).strip()
        if unit_id not in expected_ids:
            raise ValueError(f"Unknown evidence unit: {unit_id!r}")
        if unit_id in indexed:
            raise ValueError(f"Duplicate evidence unit: {unit_id}")
        required = (
            "sourceDocumentUrl", "documentSha256", "sourceLocator",
            "capturedAt", "capturedBy",
        )
        missing = [field for field in required if not str(item.get(field, "")).strip()]
        if missing:
            raise ValueError(
                f"Evidence unit {unit_id} is incomplete: {', '.join(missing)}"
            )
        require_https(item["sourceDocumentUrl"], "sourceDocumentUrl")
        archive_url = item.get("archivedDocumentUrl")
        if archive_url:
            require_https(archive_url, "archivedDocumentUrl")
        if not SHA256_RE.fullmatch(item["documentSha256"]):
            raise ValueError(f"Evidence unit {unit_id} has an invalid SHA-256")
        require_iso_date(item["capturedAt"], "capturedAt")
        reviewed_at = str(item.get("reviewedAt", "")).strip()
        reviewed_by = str(item.get("reviewedBy", "")).strip()
        if bool(reviewed_at) != bool(reviewed_by):
            raise ValueError(
                f"Evidence unit {unit_id} must provide reviewedAt and reviewedBy together"
            )
        if reviewed_at:
            require_iso_date(reviewed_at, "reviewedAt")
        indexed[unit_id] = item
    return indexed


def render(
    input_path: Path = INPUT_PATH,
    observations_path: Path = OBSERVATIONS_PATH,
) -> tuple[str, dict]:
    with observations_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        grouped[(row["period"], row["source_table"])] += 1
    expected_ids = {
        evidence_unit_id(period, source_table)
        for period, source_table in grouped
    }
    evidence = validate_input(load_json(input_path), expected_ids)
    units = []
    for (period, source_table), observation_count in sorted(grouped.items()):
        unit_id = evidence_unit_id(period, source_table)
        captured = evidence.get(unit_id)
        if captured:
            reviewed = bool(str(captured.get("reviewedAt", "")).strip())
            unit = {
                "evidenceUnitId": unit_id,
                "period": period,
                "sourceTable": source_table,
                "observationCount": observation_count,
                "sourceKind": "primary-portal-response",
                "sourceDocumentUrl": captured["sourceDocumentUrl"],
                "archivedDocumentUrl": captured.get("archivedDocumentUrl"),
                "documentSha256": captured["documentSha256"],
                "sourceLocator": captured["sourceLocator"],
                "capturedAt": captured["capturedAt"],
                "capturedBy": captured["capturedBy"],
                "reviewedAt": captured.get("reviewedAt"),
                "reviewedBy": captured.get("reviewedBy"),
                "reviewStatus": "verified" if reviewed else "captured",
                "notes": captured.get("notes", ""),
            }
        else:
            unit = {
                "evidenceUnitId": unit_id,
                "period": period,
                "sourceTable": source_table,
                "observationCount": observation_count,
                "sourceKind": "primary-portal-response",
                "sourceDocumentUrl": None,
                "archivedDocumentUrl": None,
                "documentSha256": None,
                "sourceLocator": None,
                "capturedAt": None,
                "capturedBy": None,
                "reviewedAt": None,
                "reviewedBy": None,
                "reviewStatus": "pending",
                "notes": (
                    "No exact retained primary-portal response or document locator "
                    "is linked yet."
                ),
            }
        units.append(unit)
    verified = [unit for unit in units if unit["reviewStatus"] == "verified"]
    captured = [unit for unit in units if unit["reviewStatus"] == "captured"]
    pending = [unit for unit in units if unit["reviewStatus"] == "pending"]
    verified_observations = sum(unit["observationCount"] for unit in verified)
    document = {
        "schemaVersion": "source-evidence-ledger-v1",
        "productId": PRODUCT_ID,
        "releaseId": RELEASE_ID,
        "sourceId": SOURCE_ID,
        "generatedBy": "db/build_meghalaya_source_evidence.py",
        "evidencePolicy": {
            "certificationRequirement": (
                "Each observation must link to an exact primary-source document or "
                "retained portal response, its SHA-256, and a page/table or stable "
                "response locator."
            ),
            "sourceHierarchy": (
                "The online SLBC NE portal is primary. A quarterly PDF booklet may "
                "corroborate a value or fill a documented gap, but must not be "
                "represented as provenance for a portal-derived value without an "
                "explicit equivalence review."
            ),
            "statusValues": ["pending", "captured", "verified"],
        },
        "summary": {
            "observationCount": len(rows),
            "evidenceUnitCount": len(units),
            "verifiedEvidenceUnitCount": len(verified),
            "capturedEvidenceUnitCount": len(captured),
            "pendingEvidenceUnitCount": len(pending),
            "observationsCoveredByVerifiedEvidence": verified_observations,
            "observationsPendingEvidence": len(rows) - verified_observations,
        },
        "evidenceUnits": units,
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n", document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered, _ = render()
    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                "Meghalaya source-evidence ledger is stale; run "
                "python3 db/build_meghalaya_source_evidence.py"
            )
        print("Meghalaya source-evidence ledger is current")
        return 0
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
