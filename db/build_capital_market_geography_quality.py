#!/usr/bin/env python3
"""Build the Wave 4C capital-market geography quality registry."""

import argparse
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "db" / "capital_market_geography_quality.json"
DISTRICTS = ROOT / "public" / "district_lgd_codes.json"
STATES = ROOT / "public" / "state-bounds.json"
CONFIG = {
    "cdsl": {
        "issue_id": "FINER-015", "path": "public/DPSCs/cdsl_dp_centres.json",
        "git_blob_sha": "4b9bbe12eb9080b7eef74d35c8e22fd64bbba2ad",
        "location_fields": ["loc"], "publisher": "Central Depository Services (India) Limited",
        "source_url": "https://www.cdslindia.com/",
    },
    "nsdl": {
        "issue_id": "FINER-016", "path": "public/DPSCs/nsdl_dp_centres.json",
        "git_blob_sha": "a90ee9a8ca361e1520007ededa2643771a7e847b",
        "location_fields": ["loc"], "publisher": "National Securities Depository Limited",
        "source_url": "https://www.nsdl.co.in/",
    },
    "amfi_corporate": {
        "issue_id": "FINER-017", "path": "public/MFDs/mfd_corporate.json",
        "git_blob_sha": "f5e61fcbfdf85d9a3905b93e87ee45bffebe9e28",
        "location_fields": ["c", "loc"], "publisher": "Association of Mutual Funds in India",
        "source_url": "https://www.amfiindia.com/",
    },
    "amfi_individual": {
        "issue_id": "FINER-018", "path": "public/MFDs/mfd_individual.json",
        "git_blob_sha": "77b14016db8f2369e8aaae5bddc396d85befc01e",
        "location_fields": ["c", "loc"], "publisher": "Association of Mutual Funds in India",
        "source_url": "https://www.amfiindia.com/",
    },
}


def normalise(value) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def build_registry() -> dict:
    state_data = json.loads(STATES.read_text(encoding="utf-8"))
    state_by_code = {code.upper(): item["name"] for code, item in state_data.items()}
    district_data = json.loads(DISTRICTS.read_text(encoding="utf-8"))["districts"]
    district_index = {}
    for district in district_data:
        for label in [district["district"], *district.get("aliases", [])]:
            key = (normalise(district["state"]), normalise(label))
            district_index.setdefault(key, []).append(district)

    datasets = {}
    resolutions = {}
    unresolved = {}
    duplicate_groups = []

    for dataset, config in CONFIG.items():
        records = json.loads((ROOT / config["path"]).read_text(encoding="utf-8"))
        counts = {
            "records": len(records), "mapped_records": 0, "unresolved_records": 0,
            "missing_pincode": 0, "invalid_nonblank_pincode": 0,
            "missing_state": 0, "invalid_nonblank_state": 0,
            "missing_location": 0, "exact_duplicate_rows": 0,
            "unique_mapped_districts": 0,
        }
        reason_counts = {}
        mapped_districts = set()
        seen = {}
        duplicates = {}

        for index, record in enumerate(records):
            canonical = json.dumps(
                record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            if canonical in seen:
                counts["exact_duplicate_rows"] += 1
                duplicates.setdefault(seen[canonical], []).append(index)
            else:
                seen[canonical] = index

            state_code = str(record.get("st") or "").strip().upper()
            pincode = str(record.get("p") or "").strip()
            if not pincode:
                counts["missing_pincode"] += 1
            elif not re.fullmatch(r"\d{6}", pincode):
                counts["invalid_nonblank_pincode"] += 1
            if not state_code:
                counts["missing_state"] += 1
            elif state_code not in state_by_code:
                counts["invalid_nonblank_state"] += 1

            candidates = []
            for field in config["location_fields"]:
                raw = str(record.get(field) or "").strip()
                value = normalise(raw)
                if value:
                    candidates.append({"field": field, "raw": raw, "normalised": value})
            if not candidates:
                counts["missing_location"] += 1

            reason = None
            found = []
            if not state_code:
                reason = "missing_state"
            elif state_code not in state_by_code:
                reason = "invalid_state"
            elif not candidates:
                reason = "missing_location"
            else:
                state_name = normalise(state_by_code[state_code])
                for candidate in candidates:
                    for district in district_index.get(
                        (state_name, candidate["normalised"]), []
                    ):
                        found.append((district, candidate))
                unique = {item[0]["lgd_code"]: item[0] for item in found}
                if len(unique) == 1:
                    district = next(iter(unique.values()))
                    counts["mapped_records"] += 1
                    mapped_districts.add(district["lgd_code"])
                    for matched, candidate in found:
                        key = (
                            dataset, state_code, candidate["field"],
                            candidate["normalised"], matched["lgd_code"],
                        )
                        entry = resolutions.setdefault(key, {
                            "dataset": dataset, "state_code": state_code,
                            "source_field": candidate["field"],
                            "source_value_normalized": candidate["normalised"],
                            "source_value_examples": [],
                            "district_lgd_code": matched["lgd_code"],
                            "district": matched["district"],
                            "state_lgd_code": matched["state_lgd_code"],
                            "mapping_method": "exact_state_" + (
                                "city" if candidate["field"] == "c" else "location"
                            ),
                            "mapping_confidence": 1.0,
                        })
                        if (
                            candidate["raw"] not in entry["source_value_examples"]
                            and len(entry["source_value_examples"]) < 3
                        ):
                            entry["source_value_examples"].append(candidate["raw"])
                else:
                    reason = (
                        "ambiguous_exact_state_match"
                        if len(unique) > 1 else "no_exact_state_match"
                    )

            if reason:
                counts["unresolved_records"] += 1
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
                raw_city = str(record.get("c") or "").strip()
                raw_location = str(record.get("loc") or "").strip()
                key = (
                    dataset, reason, state_code,
                    normalise(raw_city), normalise(raw_location),
                )
                entry = unresolved.setdefault(key, {
                    "dataset": dataset, "issue_id": config["issue_id"],
                    "state_code": state_code or None,
                    "city_normalized": normalise(raw_city) or None,
                    "location_normalized": normalise(raw_location) or None,
                    "reason": reason, "record_count": 0, "examples": [],
                    "disposition": "retain_raw_and_exclude_from_district_level_product",
                })
                entry["record_count"] += 1
                example = {}
                if raw_city:
                    example["city"] = raw_city
                if raw_location:
                    example["location"] = raw_location
                if example not in entry["examples"] and len(entry["examples"]) < 3:
                    entry["examples"].append(example)

        counts["unique_mapped_districts"] = len(mapped_districts)
        for first_index, duplicate_indices in duplicates.items():
            duplicate_groups.append({
                "dataset": dataset, "issue_id": config["issue_id"],
                "first_index": first_index, "duplicate_indices": duplicate_indices,
                "disposition": "retain_raw; exclude duplicate occurrences from derived counts",
            })
        datasets[dataset] = {
            "issue_id": config["issue_id"], "source_artifact": config["path"],
            "source_git_blob_sha": config["git_blob_sha"],
            "publisher": config["publisher"], "source_url": config["source_url"],
            "as_of": None, "as_of_status": "missing_from_source_artifact",
            "quality_tier": "raw-experimental", "counts": counts,
            "unresolved_reason_counts": reason_counts,
        }

    resolution_list = sorted(
        resolutions.values(),
        key=lambda x: (
            x["dataset"], x["state_code"], x["source_field"],
            x["source_value_normalized"], x["district_lgd_code"],
        ),
    )
    unresolved_list = sorted(
        unresolved.values(),
        key=lambda x: (
            x["dataset"], x["reason"], x["state_code"] or "",
            x["city_normalized"] or "", x["location_normalized"] or "",
        ),
    )
    duplicate_groups.sort(key=lambda x: (x["dataset"], x["first_index"]))
    totals = {}
    for dataset in datasets.values():
        for key, value in dataset["counts"].items():
            if key != "unique_mapped_districts":
                totals[key] = totals.get(key, 0) + value
    totals.update({
        "dataset_count": len(datasets),
        "resolution_dictionary_entries": len(resolution_list),
        "unresolved_location_groups": len(unresolved_list),
        "duplicate_groups": len(duplicate_groups),
    })
    return {
        "schema_version": "capital-market-geography-quality-v1", "wave": "4C",
        "district_registry": {
            "path": "public/district_lgd_codes.json",
            "git_blob_sha": "cb0a0679dd511db5abd89fa585dc4e5ea502b4eb",
            "geography_vintage": "current registry; source artifact does not embed observation-date boundary vintage",
        },
        "state_registry": {
            "path": "public/state-bounds.json",
            "git_blob_sha": "6a1f988835269f4afd5d42d4330961700d02dd83",
        },
        "mapping_policy": {
            "method": "casefolded alphanumeric exact match of city/location to district name or reviewed alias, constrained to stated state",
            "confidence": 1.0, "cross_state_fallback": False,
            "fuzzy_matching": False,
            "unresolved_disposition": "retain raw; exclude from district-level product",
        },
        "datasets": datasets, "summary": totals,
        "resolution_dictionary": resolution_list,
        "unresolved_location_groups": unresolved_list,
        "duplicate_groups": duplicate_groups,
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
            raise SystemExit("Capital-market geography quality registry is stale")
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
