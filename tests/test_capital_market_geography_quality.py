import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
REGISTRY = ROOT / "db" / "capital_market_geography_quality.json"
BUILDER = ROOT / "db" / "build_capital_market_geography_quality.py"
EXPECTED = {
    "cdsl": {"records": 20612, "mapped_records": 8844, "unresolved_records": 11768, "missing_pincode": 38, "invalid_nonblank_pincode": 0, "missing_state": 158, "missing_location": 53, "exact_duplicate_rows": 2},
    "nsdl": {"records": 57005, "mapped_records": 38356, "unresolved_records": 18649, "missing_pincode": 2166, "invalid_nonblank_pincode": 0, "missing_state": 2209, "missing_location": 5, "exact_duplicate_rows": 0},
    "amfi_corporate": {"records": 10760, "mapped_records": 8062, "unresolved_records": 2698, "missing_pincode": 83, "invalid_nonblank_pincode": 26, "missing_state": 103, "missing_location": 10, "exact_duplicate_rows": 0},
    "amfi_individual": {"records": 187254, "mapped_records": 135307, "unresolved_records": 51947, "missing_pincode": 18, "invalid_nonblank_pincode": 5, "missing_state": 53, "missing_location": 78, "exact_duplicate_rows": 0},
}


def test_capital_market_registry_is_reproducible():
    subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=ROOT, check=True)


def test_capital_market_registry_counts_and_policy():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert data["schema_version"] == "capital-market-geography-quality-v1"
    assert data["mapping_policy"]["cross_state_fallback"] is False
    assert data["mapping_policy"]["fuzzy_matching"] is False
    assert data["summary"]["records"] == 275631
    assert data["summary"]["mapped_records"] == 190569
    assert data["summary"]["unresolved_records"] == 85062
    assert data["summary"]["missing_pincode"] == 2305
    assert data["summary"]["invalid_nonblank_pincode"] == 31
    assert data["summary"]["missing_state"] == 2523
    assert data["summary"]["exact_duplicate_rows"] == 2
    assert data["summary"]["resolution_dictionary_entries"] == 3014
    assert data["summary"]["unresolved_location_groups"] == 14061
    for dataset, expected in EXPECTED.items():
        counts = data["datasets"][dataset]["counts"]
        for key, value in expected.items():
            assert counts[key] == value
        assert data["datasets"][dataset]["as_of"] is None
        assert data["datasets"][dataset]["as_of_status"] == "missing_from_source_artifact"


def test_every_resolution_is_state_constrained_and_every_reject_is_retained():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert all(item["mapping_confidence"] == 1.0 for item in data["resolution_dictionary"])
    assert all(item["mapping_method"].startswith("exact_state_") for item in data["resolution_dictionary"])
    assert all(item["district_lgd_code"] for item in data["resolution_dictionary"])
    assert sum(item["record_count"] for item in data["unresolved_location_groups"]) == 85062
    assert all(
        item["disposition"] == "retain_raw_and_exclude_from_district_level_product"
        for item in data["unresolved_location_groups"]
    )
