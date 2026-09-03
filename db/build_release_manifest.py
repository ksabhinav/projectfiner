#!/usr/bin/env python3
"""Build the machine-readable contract for every public download card.

The manifest is deliberately content-addressed and deterministic. It describes
what is actually committed under ``public/``; it does not certify the data or
invent rights that the upstream publisher has not stated and FINER has not
reviewed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
REGISTRY_PATH = ROOT / "db" / "release_sources.json"
OUTPUT_PATH = PUBLIC / "release-manifest.json"
MEGHALAYA_PREVIEW_PATH = PUBLIC / "data-contracts" / "meghalaya-standardized-preview.csv"
MEGHALAYA_REGISTRY_PATH = PUBLIC / "data-contracts" / "meghalaya-indicator-registry.json"

MONTHS = {
    "jan": "01", "january": "01", "feb": "02", "february": "02",
    "mar": "03", "march": "03", "apr": "04", "april": "04",
    "may": "05", "jun": "06", "june": "06", "jul": "07",
    "july": "07", "aug": "08", "august": "08", "sep": "09",
    "sept": "09", "september": "09", "oct": "10", "october": "10",
    "nov": "11", "november": "11", "dec": "12", "december": "12",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalise_period(key: str, payload: dict) -> str | None:
    if re.fullmatch(r"\d{4}-\d{2}", key):
        return key
    match = re.fullmatch(r"([A-Za-z]+)[_ -](\d{4})", key)
    if match and match.group(1).lower() in MONTHS:
        return f"{match.group(2)}-{MONTHS[match.group(1).lower()]}"
    label = str(payload.get("period", ""))
    match = re.search(r"([A-Za-z]+)\s+(\d{4})", label)
    if match and match.group(1).lower() in MONTHS:
        return f"{match.group(2)}-{MONTHS[match.group(1).lower()]}"
    return None


def base_file_metadata(path: Path, media_type: str, file_format: str) -> dict:
    relative = path.relative_to(PUBLIC).as_posix()
    with path.open("rb") as handle:
        raw_prefix = handle.read(3)
    return {
        "path": relative,
        "url": f"/{relative}",
        "format": file_format,
        "mediaType": media_type,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "encoding": "utf-8-with-bom" if raw_prefix == b"\xef\xbb\xbf" else "utf-8",
    }


def inspect_csv(path: Path) -> dict:
    metadata = base_file_metadata(path, "text/csv", "CSV")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        row_count = 0
        irregular_rows = 0
        for row in reader:
            row_count += 1
            if len(row) != len(header):
                irregular_rows += 1
    metadata.update({
        "rowCount": row_count,
        "columnCount": len(header),
        "irregularRowCount": irregular_rows,
    })
    return metadata


def inspect_complete_json(path: Path) -> tuple[dict, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    quarters = payload.get("quarters")
    if not isinstance(quarters, dict):
        raise ValueError(f"Missing quarters object: {path}")

    periods: set[str] = set()
    unparsed_periods: list[str] = []
    districts: set[str] = set()
    categories: set[str] = set()
    nested_records = 0

    for key, quarter in quarters.items():
        if not isinstance(quarter, dict):
            raise ValueError(f"Quarter {key!r} is not an object: {path}")
        period = normalise_period(key, quarter)
        if period:
            periods.add(period)
        else:
            unparsed_periods.append(key)
        tables = quarter.get("tables", {})
        if not isinstance(tables, dict):
            raise ValueError(f"Quarter {key!r} has no tables object: {path}")
        for category, table in tables.items():
            categories.add(category)
            if not isinstance(table, dict):
                continue
            rows = table.get("districts", table.get("data", {}))
            if isinstance(rows, dict):
                districts.update(str(name) for name in rows)
                nested_records += len(rows)
            elif isinstance(rows, list):
                nested_records += len(rows)
                for row in rows:
                    if isinstance(row, dict) and row.get("district"):
                        districts.add(str(row["district"]))

    sorted_periods = sorted(periods)
    coverage = {
        "periodCount": len(quarters),
        "earliestPeriod": sorted_periods[0] if sorted_periods else None,
        "latestPeriod": sorted_periods[-1] if sorted_periods else None,
        "unparsedPeriods": sorted(unparsed_periods),
        "districtCount": len(districts),
        "categoryCount": len(categories),
        "nestedRecordCount": nested_records,
    }
    metadata = base_file_metadata(path, "application/json", "JSON")
    metadata.update({"nestedRecordCount": nested_records})
    return coverage, metadata


def rights_source(source_id: str, publisher: str, url: str, notice: str,
                  scope: str, alias_urls: list[str] | None = None) -> dict:
    return {
        "id": source_id,
        "scope": scope,
        "publisher": publisher,
        "url": url,
        "aliasUrls": alias_urls or [],
        "license": None,
        "termsUrl": None,
        "rightsStatus": "not-reviewed",
        "permittedUse": "Unknown; consult the publisher's current terms before reuse.",
        "attribution": f"Source: {publisher} ({url}).",
        "notice": notice,
    }


def attach_distribution_rights(file_metadata: dict, source_id: str) -> dict:
    return {
        **file_metadata,
        "schemaVersion": "raw-v1",
        "qualityTier": "raw-experimental",
        "sourceIds": [source_id],
        "license": None,
        "rightsStatus": "not-reviewed",
    }


def attach_preview_rights(file_metadata: dict, source_id: str, registry: dict,
                          role: str, schema_version: str) -> dict:
    return {
        **file_metadata,
        "productId": registry["productId"],
        "productReleaseId": registry["releaseId"],
        "role": role,
        "schemaVersion": schema_version,
        "qualityTier": registry["qualityTier"],
        "certificationStatus": registry["certificationStatus"],
        "indicatorCount": len(registry["indicators"]),
        "sourceIds": [source_id],
        "license": None,
        "rightsStatus": "not-reviewed",
    }


def build_manifest(registry_path: Path = REGISTRY_PATH) -> dict:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    notice = registry["rightsNotice"]
    sources = []
    states = []

    for slug, config in sorted(registry["states"].items()):
        source_id = f"slbc-{slug}"
        complete_path = PUBLIC / "slbc-data" / slug / f"{slug}_complete.json"
        csv_path = PUBLIC / "slbc-data" / slug / f"{slug}_fi_timeseries.csv"
        if not complete_path.exists() or not csv_path.exists():
            raise FileNotFoundError(f"Incomplete state download pair for {slug}")

        coverage, complete_file = inspect_complete_json(complete_path)
        csv_file = inspect_csv(csv_path)
        sources.append(rights_source(
            source_id, config["publisher"], config["url"], notice,
            f"SLBC/UTLBC source material for {config['name']}",
            config.get("aliasUrls"),
        ))
        state_distributions = [
            attach_distribution_rights(complete_file, source_id),
            attach_distribution_rights(csv_file, source_id),
        ]
        if slug == "meghalaya":
            indicator_registry = json.loads(
                MEGHALAYA_REGISTRY_PATH.read_text(encoding="utf-8")
            )
            if indicator_registry["source"]["id"] != source_id:
                raise ValueError("Meghalaya preview source does not match release source")
            preview_file = inspect_csv(MEGHALAYA_PREVIEW_PATH)
            state_distributions.extend([
                attach_preview_rights(
                    preview_file, source_id, indicator_registry,
                    "observations", indicator_registry["schemaVersion"],
                ),
                attach_preview_rights(
                    base_file_metadata(
                        MEGHALAYA_REGISTRY_PATH, "application/json", "JSON"
                    ),
                    source_id,
                    indicator_registry,
                    "indicator-registry",
                    indicator_registry["registrySchemaVersion"],
                ),
            ])
        states.append({
            "slug": slug,
            "name": config["name"],
            "group": config["group"],
            "qualityTier": "raw-experimental",
            "sourceIds": [source_id],
            "rightsStatus": "not-reviewed",
            "license": None,
            "coverage": coverage,
            "distributions": state_distributions,
        })

    capital_markets = []
    for item_id, config in sorted(registry["capitalMarkets"].items()):
        source_id = f"capital-{item_id}"
        path = PUBLIC / config["path"]
        records = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError(f"Capital-market registry is not an array: {path}")
        sources.append(rights_source(
            source_id, config["publisher"], config["url"], notice,
            config["title"],
        ))
        capital_markets.append({
            "id": item_id,
            "label": config["label"],
            "title": config["title"],
            "filename": config["filename"],
            "recordLabel": config["recordLabel"],
            "recordCount": len(records),
            "fields": config["fields"],
            "geographyLevel": "location",
            "districtMapped": False,
            "snapshotDate": None,
            "qualityTier": "raw-experimental",
            "sourceIds": [source_id],
            "rightsStatus": "not-reviewed",
            "license": None,
            "distributions": [attach_distribution_rights(
                base_file_metadata(path, "application/json", "JSON"), source_id
            )],
        })

    manifest = {
        "schemaVersion": 1,
        "releaseStatus": "research-preview",
        "qualityTier": "raw-experimental",
        "generatedBy": "db/build_release_manifest.py",
        "rightsReviewStatus": registry["rightsReviewStatus"],
        "rightsNotice": notice,
        "projectDataLicense": None,
        "summary": {
            "stateCount": len(states),
            "capitalMarketRegistryCount": len(capital_markets),
            "distributionCount": sum(len(state["distributions"]) for state in states)
            + sum(len(item["distributions"]) for item in capital_markets),
        },
        "sources": sorted(sources, key=lambda source: source["id"]),
        "states": states,
        "capitalMarkets": capital_markets,
    }
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    manifest["releaseId"] = f"finer-{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"
    return manifest


def serialise_manifest(manifest: dict) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="Fail if public/release-manifest.json is missing or stale.",
    )
    args = parser.parse_args()
    rendered = serialise_manifest(build_manifest())
    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
            print("public/release-manifest.json is stale; regenerate it")
            return 1
        print("public/release-manifest.json is current")
        return 0
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    manifest = json.loads(rendered)
    print(
        f"wrote {OUTPUT_PATH.relative_to(ROOT)}: {manifest['releaseId']}, "
        f"{manifest['summary']['stateCount']} states, "
        f"{manifest['summary']['distributionCount']} distributions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
