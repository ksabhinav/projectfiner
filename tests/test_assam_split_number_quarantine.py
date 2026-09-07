import json
import re
from pathlib import Path

REGISTRY = Path(__file__).parents[1] / "db" / "assam_split_number_quarantine.json"
SPLIT_NUMBER = re.compile(r"^\s*\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s*$")


def test_assam_split_number_registry_is_explicit_and_complete():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = data["records"]
    assert data["schema_version"] == "assam-split-number-quarantine-v1"
    assert data["disposition"] == "excluded_from_clean_analytical_views"
    assert len(records) == 36
    assert {record["field"] for record in records} == {
        "pmegp__pmegp_npa_pct",
        "pmmy_mudra_os_npa__mudra_npa_pct",
    }
    assert all(record["quality_status"] == "quarantined" for record in records)
    assert all(record["quality_flag"] == "split_numeric_tokens" for record in records)
    assert all(SPLIT_NUMBER.fullmatch(record["raw_value"]) for record in records)
    assert len({(r["period"], r["district"], r["field"]) for r in records}) == len(records)
