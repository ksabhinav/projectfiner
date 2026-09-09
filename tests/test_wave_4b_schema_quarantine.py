import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parents[1]
REGISTRY = ROOT / "db" / "wave_4b_schema_quarantine.json"
BUILDER = ROOT / "db" / "build_wave_4b_schema_quarantine.py"
EXPECTED = {
    "bihar": {"date_specific_fields": 40, "blank_fields": 0, "overlap_fields": 0, "unique_quarantined_fields": 40},
    "jharkhand": {"date_specific_fields": 332, "blank_fields": 63, "overlap_fields": 5, "unique_quarantined_fields": 390},
    "odisha": {"date_specific_fields": 107, "blank_fields": 11, "overlap_fields": 2, "unique_quarantined_fields": 116},
    "uttarakhand": {"date_specific_fields": 10, "blank_fields": 0, "overlap_fields": 0, "unique_quarantined_fields": 10},
}


def test_wave_4b_registry_is_current():
    subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=ROOT, check=True)


def test_wave_4b_registry_has_state_specific_issue_ids_and_counts():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert data["schema_version"] == "wave-4b-schema-quarantine-v1"
    assert data["summary"] == {
        "state_count": 4,
        "date_specific_fields": 489,
        "blank_fields": 74,
        "overlap_fields": 7,
        "unique_quarantined_fields": 556,
    }
    for state, expected in EXPECTED.items():
        actual = data["states"][state]
        assert {key: actual[key] for key in expected} == expected

    fields = data["fields"]
    assert len(fields) == 556
    assert len({(entry["state"], entry["field"]) for entry in fields}) == len(fields)
    assert Counter(entry["issue_id"] for entry in fields) == {
        "FINER-011": 40,
        "FINER-012": 390,
        "FINER-013": 116,
        "FINER-014": 10,
    }
    assert all(entry["quality_status"] == "quarantined" for entry in fields)
    assert all(entry["quality_flags"] for entry in fields)
    assert all(
        entry["non_empty_observation_count"] == 0
        for entry in fields
        if "entirely_blank" in entry["quality_flags"]
    )
