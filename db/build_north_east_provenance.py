#!/usr/bin/env python3
"""Build artifact-level provenance for the North-East indicator inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
INVENTORY_PATH = PUBLIC / "data-contracts" / "north-east-indicator-inventory.json"
SOURCE_REGISTRY_PATH = ROOT / "db" / "release_sources.json"
OUTPUT_PATH = PUBLIC / "data-contracts" / "north-east-provenance.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    payload = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    return hashlib.sha1(payload).hexdigest()


def build_provenance() -> dict:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    registry = json.loads(SOURCE_REGISTRY_PATH.read_text(encoding="utf-8"))
    artifacts = []

    for state in inventory["states"]:
        slug = state["stateSlug"]
        config = registry["states"].get(slug)
        if not config or config.get("group") != "north-east":
            raise ValueError(f"Missing North-East release source for {slug}")

        artifact_path = state["sourceArtifact"]
        artifact = PUBLIC / artifact_path.lstrip("/")
        actual_git_blob_sha = git_blob_sha(artifact)
        if actual_git_blob_sha != state["sourceGitBlobSha"]:
            raise ValueError(f"Inventory source Git blob is stale for {slug}")
        artifact_sha256 = sha256_file(artifact)
        source_id = f"slbc-{slug}"
        artifacts.append({
            "artifactBytes": artifact.stat().st_size,
            "artifactGitBlobSha": actual_git_blob_sha,
            "artifactId": (
                f"{source_id}-timeseries-{artifact_sha256[:12]}"
            ),
            "artifactPath": artifact_path,
            "artifactRole": "consolidated-raw-timeseries",
            "artifactSha256": artifact_sha256,
            "publisher": config["publisher"],
            "publisherAliasUrls": config.get("aliasUrls", []),
            "publisherLandingUrl": config["url"],
            "rightsReviewStatus": registry["rightsReviewStatus"],
            "sourceDocumentStatus": "not-linked",
            "sourceId": source_id,
            "sourcePageStatus": "not-linked",
            "stateSlug": slug,
            "upstreamExtractionRunStatus": "not-recorded",
        })

    inventory_sha256 = sha256_file(INVENTORY_PATH)
    return {
        "artifactInputs": artifacts,
        "build": {
            "builder": "db/build_north_east_indicator_inventory.py",
            "inputArtifactCount": len(artifacts),
            "inventoryBuildId": (
                f"north-east-indicator-inventory-{inventory_sha256[:12]}"
            ),
            "method": (
                "Profile exact raw field labels and lexical value characteristics "
                "from the eight committed state time-series artifacts; do not infer "
                "units, measure types, or semantic equivalence."
            ),
            "provenanceBuilder": "db/build_north_east_provenance.py",
            "reproducibleFromCommittedArtifacts": True,
            "sourceArtifactExtractionReproducible": False,
        },
        "knownGaps": [
            (
                "The committed time-series artifacts are not yet linked to exact "
                "upstream documents and pages."
            ),
            (
                "The upstream extraction runs that created the committed time-series "
                "artifacts are not recorded."
            ),
            "Source reuse rights have not been legally reviewed.",
            (
                "Artifact-level provenance does not make raw fields semantically "
                "comparable across states."
            ),
        ],
        "product": {
            "artifactBytes": INVENTORY_PATH.stat().st_size,
            "artifactPath": "/data-contracts/north-east-indicator-inventory.json",
            "artifactSha256": inventory_sha256,
            "id": "north-east-indicator-inventory",
            "schemaVersion": inventory["registrySchemaVersion"],
        },
        "qualityTier": "raw-experimental",
        "schemaVersion": "north-east-provenance-registry-v1",
    }


def serialise(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="Fail if the committed North-East provenance registry is stale.",
    )
    args = parser.parse_args()
    rendered = serialise(build_provenance())
    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
            print("public/data-contracts/north-east-provenance.json is stale")
            return 1
        print("public/data-contracts/north-east-provenance.json is current")
        return 0
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
