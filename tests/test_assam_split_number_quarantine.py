import json
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parents[1]


class AssamQuarantineTests(unittest.TestCase):
    def test_all_affected_fields_and_original_cells_are_preserved(self):
        data = json.loads((ROOT / "db/assam_split_number_quarantine.json").read_text())
        source = json.loads((ROOT / data["source_artifact"]).read_text())
        records = data["records"]
        self.assertEqual(data["schema_version"], "assam-split-number-quarantine-v2")
        self.assertEqual(data["issue_id"], "FINER-003")
        self.assertEqual(len(records), 268)
        self.assertEqual(Counter(r["field"] for r in records), {
            "non_ps_outstanding__nps_npa_pct": 60,
            "nrlm__nrlm_npa_pct": 30,
            "pmegp__pmegp_npa_pct": 22,
            "pmmy_mudra_os_npa__mudra_npa_pct": 31,
            "shg__shg_npa_pct": 125,
        })
        identities = set()
        for record in records:
            self.assertEqual(record["quality_status"], "quarantined")
            value = source
            for token in record["source_json_pointer"].split("/")[1:]:
                token = token.replace("~1", "/").replace("~0", "~")
                value = value[int(token)] if isinstance(value, list) else value[token]
            self.assertEqual(value, record["raw_value"])
            identities.add((record["period"], record["district"], record["field"]))
        self.assertEqual(len(identities), len(records))
