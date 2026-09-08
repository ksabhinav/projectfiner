import json
from collections import Counter
from pathlib import Path

REGISTRY = Path(__file__).parents[1] / "db" / "west_bengal_garbled_field_quarantine.json"


def test_west_bengal_garbled_field_registry_is_explicit_and_complete():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    fields = data["fields"]
    assert data["schema_version"] == "west-bengal-garbled-field-quarantine-v1"
    assert data["issue_id"] == "FINER-010"
    assert data["detection_summary"] == {
        "ocr_split_cumulative_token": 141,
        "character_by_character_header": 5,
        "total": 146,
    }
    assert len(fields) == 146
    assert len({entry["field"] for entry in fields}) == len(fields)
    assert Counter(entry["detection_reason"] for entry in fields) == {
        "ocr_split_cumulative_token": 141,
        "character_by_character_header": 5,
    }
    assert all(entry["issue_id"] == "FINER-010" for entry in fields)
    assert all(entry["quality_status"] == "quarantined" for entry in fields)
    assert all(entry["quality_flag"] == "garbled_field_name" for entry in fields)
    assert all(entry["non_empty_observation_count"] > 0 for entry in fields)
    assert all(entry["period_count"] > 0 for entry in fields)
    assert all(entry["district_count"] > 0 for entry in fields)
    assert all(entry["example_raw_values"] for entry in fields)
