#!/usr/bin/env python3
"""Fail closed when a public release distribution is structurally unsafe.

This gate validates the files named by ``public/release-manifest.json``. It is
deliberately separate from ``validate_data.py``: that validator detects
domain anomalies against an accepted baseline, while this one rejects broken
delivery artifacts unconditionally.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
MANIFEST_PATH = PUBLIC / "release-manifest.json"
REQUIRED_FIELDS = {
    "path", "format", "mediaType", "bytes", "sha256", "encoding",
}


class ValidationError(ValueError):
    """Raised for a single invalid release artifact."""


def strict_json_loads(text: str):
    def reject_constant(value):
        raise ValidationError(f"non-finite JSON number {value}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValidationError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    return json.loads(
        text,
        parse_constant=reject_constant,
        object_pairs_hook=unique_object,
    )


def distributions(manifest: dict):
    for dataset in [*manifest.get("states", []), *manifest.get("capitalMarkets", [])]:
        for distribution in dataset.get("distributions", []):
            yield dataset, distribution


def resolve_distribution(public_root: Path, relative: str) -> Path:
    posix_path = PurePosixPath(relative)
    if posix_path.is_absolute() or ".." in posix_path.parts or "\\" in relative:
        raise ValidationError("path must be a safe POSIX path below public/")
    path = public_root.joinpath(*posix_path.parts)
    if path.resolve().parent != public_root.resolve() and public_root.resolve() not in path.resolve().parents:
        raise ValidationError("path resolves outside public/")
    return path


def validate_csv(text: str, distribution: dict, state_dataset: bool) -> None:
    try:
        rows = csv.reader(text.splitlines(keepends=True), strict=True)
        header = next(rows, [])
        parsed_rows = list(rows)
    except csv.Error as exc:
        raise ValidationError(f"invalid CSV: {exc}") from exc

    if not header:
        raise ValidationError("CSV has no header")
    blank_headers = [index + 1 for index, value in enumerate(header) if not value.strip()]
    if blank_headers:
        raise ValidationError(f"blank CSV header(s) at column(s) {blank_headers}")
    duplicates = sorted({value for value in header if header.count(value) > 1})
    if duplicates:
        raise ValidationError(f"duplicate CSV header(s): {duplicates}")
    if state_dataset and not {"district", "period"}.issubset(header):
        raise ValidationError("state CSV must contain district and period columns")

    for line_number, row in enumerate(parsed_rows, 2):
        if len(row) != len(header):
            raise ValidationError(
                f"CSV row {line_number} has {len(row)} columns; expected {len(header)}"
            )
        if not row or all(not value.strip() for value in row):
            raise ValidationError(f"CSV row {line_number} is blank")

    declared = {
        "rowCount": len(parsed_rows),
        "columnCount": len(header),
        "irregularRowCount": 0,
    }
    for field, actual in declared.items():
        if field in distribution and distribution[field] != actual:
            raise ValidationError(
                f"manifest {field} is {distribution[field]!r}; actual value is {actual}"
            )


def validate_distribution(public_root: Path, distribution: dict, state_dataset: bool) -> None:
    missing = sorted(REQUIRED_FIELDS - distribution.keys())
    if missing:
        raise ValidationError(f"manifest entry is missing {missing}")

    path = resolve_distribution(public_root, distribution["path"])
    if not path.is_file():
        raise ValidationError("file does not exist")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValidationError("UTF-8 BOM is not allowed")
    if b"\x00" in raw:
        raise ValidationError("NUL byte is not allowed")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"file is not valid UTF-8: {exc}") from exc

    if distribution["encoding"] != "utf-8":
        raise ValidationError("manifest encoding must be utf-8")
    if distribution["bytes"] != len(raw):
        raise ValidationError(
            f"manifest bytes is {distribution['bytes']}; actual value is {len(raw)}"
        )
    digest = hashlib.sha256(raw).hexdigest()
    if distribution["sha256"] != digest:
        raise ValidationError("manifest SHA-256 does not match file")

    file_format = distribution["format"]
    if file_format == "CSV":
        if distribution["mediaType"] != "text/csv":
            raise ValidationError("CSV mediaType must be text/csv")
        validate_csv(text, distribution, state_dataset)
    elif file_format == "JSON":
        if distribution["mediaType"] != "application/json":
            raise ValidationError("JSON mediaType must be application/json")
        payload = strict_json_loads(text)
        if not isinstance(payload, (dict, list)):
            raise ValidationError("JSON root must be an object or array")
    else:
        raise ValidationError(f"unsupported format {file_format!r}")


def validate_release(manifest_path: Path = MANIFEST_PATH, public_root: Path = PUBLIC) -> list[str]:
    try:
        manifest = strict_json_loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        return [f"release-manifest.json: {exc}"]

    errors = []
    seen = set()
    entries = list(distributions(manifest))
    if not entries:
        return ["release-manifest.json: no distributions declared"]

    for dataset, distribution in entries:
        relative = distribution.get("path", "<missing path>")
        if relative in seen:
            errors.append(f"{relative}: distribution path is declared more than once")
            continue
        seen.add(relative)
        try:
            validate_distribution(
                public_root,
                distribution,
                state_dataset="slug" in dataset,
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            errors.append(f"{relative}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--public-root", type=Path, default=PUBLIC)
    args = parser.parse_args()

    errors = validate_release(args.manifest, args.public_root)
    if errors:
        print(f"release data validation failed ({len(errors)} error(s)):")
        for error in errors:
            print(f"  - {error}")
        return 1

    manifest = strict_json_loads(args.manifest.read_text(encoding="utf-8"))
    count = sum(1 for _ in distributions(manifest))
    print(f"release data validation passed: {count} distributions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
