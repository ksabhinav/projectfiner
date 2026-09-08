import json
import re
from collections import Counter
from pathlib import Path

REGISTRY = Path(__file__).parents[1] / "db" / "tamil_nadu_split_number_quarantine.json"
SPLIT_NUMBER = re.compile(r"^\s*[+-]?\d+(?:\.\d+)?\s+[+-]?\d+(?:\.\d+)?\s*$")
EXPECTED_FIELDS = {
    "cd_ratio__o_deposit": 36,
    "kcc_fisheries__f_outstanding_amount_as_n_on_end_of_current_quarter": 35,
    "pmjdy__total": 36,
    "uncategorized__no_of_amo_appli_unt_of_catio_loan_ns_sanct_rejec_ioned_ted": 6,
    "aabcs__sdy_no": 8,
    "uncategorized__10": 12,
    "pmmy_mudra__10": 48,
    "tahdco__sub": 7,
    "tahdco__1_84_01": 1,
    "tahdco__2_64_04": 1,
    "tahdco__4_48_05": 1,
    "uncategorized__amnt": 1,
    "uncategorized__no": 1
}


def test_tamil_nadu_split_number_registry_is_explicit_and_complete():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = data["records"]
    assert data["schema_version"] == "tamil-nadu-split-number-quarantine-v1"
    assert data["issue_id"] == "FINER-003"
    assert data["disposition"] == "excluded_from_clean_analytical_views"
    assert len(records) == 193
    assert Counter(record["field"] for record in records) == EXPECTED_FIELDS
    assert all(record["issue_id"] == "FINER-003" for record in records)
    assert all(record["quality_status"] == "quarantined" for record in records)
    assert all(record["quality_flag"] == "split_numeric_tokens" for record in records)
    assert all(SPLIT_NUMBER.fullmatch(record["raw_value"]) for record in records)
    assert len({(r["period"], r["district"], r["field"]) for r in records}) == len(records)
