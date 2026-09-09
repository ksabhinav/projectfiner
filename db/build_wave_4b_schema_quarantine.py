#!/usr/bin/env python3
"""Build the Wave 4B schema-quarantine registry from public state CSVs."""

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "db" / "wave_4b_schema_quarantine.json"
METADATA_FIELDS = {"quarter", "district", "as_on_date", "fy"}
CONFIG = {
    "bihar": {
        "issue_id": "FINER-011",
        "path": "public/slbc-data/bihar/bihar_fi_timeseries.csv",
        "git_blob_sha": "4e9815d7299c4fa33fa07449d836deba33b42701",
    },
    "jharkhand": {
        "issue_id": "FINER-012",
        "path": "public/slbc-data/jharkhand/jharkhand_fi_timeseries.csv",
        "git_blob_sha": "9d1a0558191a4249fe686f1b3b46744b2ed46787",
    },
    "odisha": {
        "issue_id": "FINER-013",
        "path": "public/slbc-data/odisha/odisha_fi_timeseries.csv",
        "git_blob_sha": "0bb6efcdd8466d20bea113b822ba3f058e966939",
    },
    "uttarakhand": {
        "issue_id": "FINER-014",
        "path": "public/slbc-data/uttarakhand/uttarakhand_fi_timeseries.csv",
        "git_blob_sha": "349666ec666bedc3f9bd938c57b0953203070703",
    },
}


def build_registry() -> dict:
    states = {}
    fields = []
    for state, config in CONFIG.items():
        path = ROOT / config["path"]
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            headers = next(reader)
            rows = [row for row in reader if any(cell for cell in row)]

        date_count = blank_count = overlap_count = 0
        for index, field in enumerate(headers):
            if field in METADATA_FIELDS:
                continue
            flags = []
            if re.search(r"20\d{2}", field):
                flags.append("date_in_field_name")
                date_count += 1
            values = [
                row[index].strip()
                for row in rows
                if index < len(row) and row[index].strip()
            ]
            if not values:
                flags.append("entirely_blank")
                blank_count += 1
            if len(flags) == 2:
                overlap_count += 1
            if flags:
                fields.append({
                    "state": state,
                    "issue_id": config["issue_id"],
                    "field": field,
                    "quality_status": "quarantined",
                    "quality_flags": flags,
                    "non_empty_observation_count": len(values),
                    "example_raw_values": values[:3],
                    "disposition": "exclude_field_from_clean_analytical_views_pending_schema_normalisation",
                })

        states[state] = {
            "issue_id": config["issue_id"],
            "source_artifact": config["path"],
            "source_git_blob_sha": config["git_blob_sha"],
            "date_specific_fields": date_count,
            "blank_fields": blank_count,
            "overlap_fields": overlap_count,
            "unique_quarantined_fields": date_count + blank_count - overlap_count,
        }

    fields.sort(key=lambda item: (item["state"], item["field"]))
    return {
        "schema_version": "wave-4b-schema-quarantine-v1",
        "wave": "4B",
        "states": states,
        "detection_rules": {
            "date_in_field_name": "Field name contains a four-digit year beginning with 20; period has leaked into schema.",
            "entirely_blank": "Field has no non-empty value in the full state timeseries CSV.",
        },
        "raw_preservation": "Source field names and values remain unchanged in Raw / Experimental artifacts.",
        "summary": {
            "state_count": len(states),
            "date_specific_fields": sum(item["date_specific_fields"] for item in states.values()),
            "blank_fields": sum(item["blank_fields"] for item in states.values()),
            "overlap_fields": sum(item["overlap_fields"] for item in states.values()),
            "unique_quarantined_fields": len(fields),
        },
        "fields": fields,
    }


def serialise(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = serialise(build_registry())
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Wave 4B schema-quarantine registry is stale")
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
