import csv
import json
import unittest
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
PILOT_PATH = REPO_ROOT / "db/meghalaya_source_evidence_pilot.json"
OBSERVATIONS_PATH = REPO_ROOT / "public/data-contracts/meghalaya-standardized-preview.csv"


class MeghalayaSourceEvidencePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pilot = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
        with OBSERVATIONS_PATH.open(encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_pilot_covers_the_latest_period_and_all_registered_tables(self):
        scope = self.pilot["pilot"]
        latest_period = max(row["period"] for row in self.rows)
        scoped = [row for row in self.rows if row["period"] == scope["period"]]
        self.assertEqual(scope["period"], latest_period)
        self.assertEqual(scope["observationCount"], len(scoped))
        self.assertEqual(scope["observationCount"], 156)
        self.assertEqual(
            set(scope["sourceTables"]),
            {row["source_table"] for row in scoped},
        )
        self.assertEqual(
            set(scope["expectedEvidenceUnitIds"]),
            {
                f"meghalaya-{scope['period']}-{table.replace('_', '-')}"
                for table in scope["sourceTables"]
            },
        )

    def test_report_families_pin_official_portal_entrypoints(self):
        families = self.pilot["reportFamilies"]
        self.assertEqual(
            {item["sourceTable"] for item in families},
            set(self.pilot["pilot"]["sourceTables"]),
        )
        self.assertEqual(
            sum(len(item["indicatorIds"]) for item in families),
            13,
        )
        for item in families:
            parsed = urlparse(item["formUrl"])
            self.assertEqual(parsed.scheme, "https")
            self.assertEqual(parsed.netloc, "onlineslbcne.nic.in")
            self.assertTrue(parsed.path.endswith(".php"))
            self.assertTrue(item["locatorRequirement"])

    def test_capture_state_does_not_claim_source_evidence(self):
        capture = self.pilot["capture"]
        self.assertEqual(capture["status"], "blocked")
        self.assertFalse(self.pilot["pilot"]["expectedEvidenceStatus"] == "captured")
        self.assertFalse(self.pilot["pilot"].get("capturedEvidenceUnitIds"))
        self.assertIn("No evidence unit is marked captured", capture["notes"])
        self.assertEqual(
            capture["observedFailureUrl"],
            "https://onlineslbcne.nic.in/error.php",
        )


if __name__ == "__main__":
    unittest.main()
