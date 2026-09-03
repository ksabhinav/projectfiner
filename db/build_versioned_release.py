#!/usr/bin/env python3
"""Publish and verify immutable snapshots of FINER standardized products.

The first snapshot is a release candidate, not a certified release. Its
machine-readable descriptor derives certification blockers from the actual
observation rows and rights metadata. Existing version directories are never
silently overwritten: changed content requires a new release ID.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
REGISTRY_PATH = PUBLIC / "data-contracts" / "meghalaya-indicator-registry.json"
OBSERVATIONS_PATH = PUBLIC / "data-contracts" / "meghalaya-standardized-preview.csv"
RELEASES_ROOT = PUBLIC / "releases"
CATALOG_PATH = RELEASES_ROOT / "index.json"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_rows(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def distribution(path: str, content: bytes, media_type: str, role: str) -> dict:
    return {
        "role": role,
        "path": path,
        "url": f"/{path}",
        "mediaType": media_type,
        "bytes": len(content),
        "sha256": sha256_bytes(content),
    }


def certification_blockers(
    rows: list[dict[str, str]], *, source_rights_reviewed: bool = False
) -> list[dict]:
    statuses = Counter(row["quality_status"] for row in rows)
    flags = Counter(
        flag
        for row in rows
        for flag in row["quality_flags"].split("|")
        if flag
    )
    missing_pages = sum(not row["source_page"].strip() for row in rows)
    blockers = []
    non_verified = len(rows) - statuses.get("verified", 0)
    if non_verified:
        blockers.append({
            "code": "non_verified_observations",
            "count": non_verified,
            "message": "Every certified observation must have quality_status=verified.",
        })
    if missing_pages:
        blockers.append({
            "code": "missing_source_pages",
            "count": missing_pages,
            "message": "Every observation must link to its source document and page.",
        })
    for flag in (
        "semantic_scope_review_required",
        "boundary_not_harmonised",
        "partial_period_coverage",
    ):
        if flags[flag]:
            blockers.append({
                "code": flag,
                "count": flags[flag],
                "message": "This unresolved quality flag blocks certification.",
            })
    if not source_rights_reviewed:
        blockers.append({
            "code": "source_rights_not_reviewed",
            "count": 1,
            "message": "Upstream reuse rights require review before certification.",
        })
    return blockers


def render_release() -> tuple[str, dict[str, bytes], str]:
    registry_bytes = REGISTRY_PATH.read_bytes()
    observations_bytes = OBSERVATIONS_PATH.read_bytes()
    registry = json.loads(registry_bytes)
    rows = read_rows(observations_bytes)
    release_id = registry["releaseId"]
    release_dir = f"releases/{release_id}"
    blockers = certification_blockers(
        rows,
        source_rights_reviewed=bool(
            registry.get("certificationPolicy", {}).get("sourceRightsReviewed")
        ),
    )
    status_counts = dict(sorted(Counter(
        row["quality_status"] for row in rows
    ).items()))
    flag_counts = dict(sorted(Counter(
        flag
        for row in rows
        for flag in row["quality_flags"].split("|")
        if flag
    ).items()))
    distributions = [
        distribution(
            f"{release_dir}/observations.csv", observations_bytes,
            "text/csv", "observations",
        ),
        distribution(
            f"{release_dir}/indicator-registry.json", registry_bytes,
            "application/json", "indicator-registry",
        ),
    ]
    descriptor = {
        "schemaVersion": "release-candidate-v1",
        "productId": registry["productId"],
        "releaseId": release_id,
        "releaseStatus": "immutable-preview",
        "qualityTier": registry["qualityTier"],
        "certificationStatus": "not-certified" if blockers else "certified",
        "generatedBy": "db/build_versioned_release.py",
        "landingPage": f"/releases/{release_id}/",
        "summary": {
            "observationCount": len(rows),
            "indicatorCount": len(registry["indicators"]),
            "districtCount": len({row["district_lgd_code"] for row in rows}),
            "earliestPeriod": min(row["period"] for row in rows),
            "latestPeriod": max(row["period"] for row in rows),
            "qualityStatusCounts": status_counts,
            "qualityFlagCounts": flag_counts,
        },
        "certification": {
            "eligible": not blockers,
            "criteria": [
                "All observations are verified.",
                "Every observation links to a source document and page.",
                "Semantic, boundary and partial-coverage flags are resolved.",
                "Upstream reuse rights are reviewed.",
            ],
            "blockers": blockers,
        },
        "distributions": distributions,
    }
    descriptor_bytes = (
        json.dumps(descriptor, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    files = {
        "observations.csv": observations_bytes,
        "indicator-registry.json": registry_bytes,
        "release.json": descriptor_bytes,
    }
    catalog = {
        "schemaVersion": "release-catalog-v1",
        "releases": [{
            "productId": descriptor["productId"],
            "releaseId": release_id,
            "releaseStatus": descriptor["releaseStatus"],
            "qualityTier": descriptor["qualityTier"],
            "certificationStatus": descriptor["certificationStatus"],
            "landingPage": descriptor["landingPage"],
            "descriptor": f"/{release_dir}/release.json",
            "observationCount": descriptor["summary"]["observationCount"],
            "latestPeriod": descriptor["summary"]["latestPeriod"],
        }],
    }
    catalog_text = json.dumps(
        catalog, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    return release_id, files, catalog_text


def verify(release_id: str, files: dict[str, bytes], catalog_text: str) -> list[str]:
    errors = []
    target = RELEASES_ROOT / release_id
    for name, expected in files.items():
        path = target / name
        if not path.exists():
            errors.append(f"missing {path.relative_to(ROOT)}")
        elif path.read_bytes() != expected:
            errors.append(
                f"immutable release drift at {path.relative_to(ROOT)}; "
                "bump the source registry releaseId"
            )
    if not CATALOG_PATH.exists():
        errors.append(f"missing {CATALOG_PATH.relative_to(ROOT)}")
    elif CATALOG_PATH.read_text(encoding="utf-8") != catalog_text:
        errors.append(f"stale {CATALOG_PATH.relative_to(ROOT)}")
    return errors


def publish(release_id: str, files: dict[str, bytes], catalog_text: str) -> None:
    target = RELEASES_ROOT / release_id
    target.mkdir(parents=True, exist_ok=True)
    for name, expected in files.items():
        path = target / name
        if path.exists() and path.read_bytes() != expected:
            raise ValueError(
                f"refusing to overwrite immutable {path.relative_to(ROOT)}; "
                "bump the source registry releaseId"
            )
        path.write_bytes(expected)
    CATALOG_PATH.write_text(catalog_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    release_id, files, catalog_text = render_release()
    if args.check:
        errors = verify(release_id, files, catalog_text)
        if errors:
            for error in errors:
                print(error)
            return 1
        print(f"versioned release {release_id} is current and immutable")
        return 0
    publish(release_id, files, catalog_text)
    print(f"published immutable release candidate {release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
