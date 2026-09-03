import csv
import io
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "db"))

from build_meghalaya_standardized import render


class MeghalayaStandardizedPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output_path = (
            REPO_ROOT / "public/data-contracts/meghalaya-standardized-preview.csv"
        )
        cls.registry = json.loads(
            (REPO_ROOT / "public/data-contracts/meghalaya-indicator-registry.json")
            .read_text(encoding="utf-8")
        )
        cls.rows = list(csv.DictReader(io.StringIO(cls.output_path.read_text())))

    def test_committed_preview_is_current(self):
        rendered, row_count = render()
        self.assertEqual(row_count, 3494)
        self.assertEqual(self.output_path.read_text(encoding="utf-8"), rendered)

    def test_contract_has_unique_canonical_observation_identities(self):
        self.assertEqual(len(self.rows), 3494)
        self.assertEqual(
            list(self.rows[0]), self.registry["observationColumns"]
        )
        self.assertEqual(len({row["observation_id"] for row in self.rows}), 3494)
        self.assertEqual({row["state_lgd_code"] for row in self.rows}, {"17"})
        self.assertEqual(
            len({row["district_lgd_code"] for row in self.rows}), 12
        )
        self.assertEqual(
            {row["indicator_id"] for row in self.rows},
            {item["indicatorId"] for item in self.registry["indicators"]},
        )
        self.assertEqual(len(self.registry["indicators"]), 13)

    def test_aadhaar_scope_conflicts_are_flagged_without_correction(self):
        flagged = [
            row for row in self.rows
            if "semantic_scope_review_required" in row["quality_flags"].split("|")
        ]
        groups = {(row["district_lgd_code"], row["period"]) for row in flagged}
        self.assertEqual(len(flagged), 225)
        self.assertEqual(len(groups), 75)
        self.assertEqual(
            {row["indicator_id"] for row in flagged},
            {"aadhaar_seeded_casa", "aadhaar_authenticated_casa", "operative_casa"},
        )
        sample = next(
            row for row in self.rows
            if row["district"] == "East Garo Hills"
            and row["period"] == "2020-06-30"
            and row["indicator_id"] == "aadhaar_authenticated_casa"
        )
        self.assertEqual(sample["source_value"], "1962")
        self.assertEqual(sample["value"], "1962")

    def test_boundary_and_partial_coverage_are_explicit(self):
        eastern_west = [
            row for row in self.rows if row["district"] == "Eastern West Khasi Hills"
        ]
        self.assertTrue(eastern_west)
        self.assertTrue(all(row["period"] >= "2022-06-30" for row in eastern_west))
        self.assertTrue(all(
            "boundary_not_harmonised" in row["quality_flags"].split("|")
            for row in eastern_west
        ))

        partial = [
            row for row in self.rows
            if "partial_period_coverage" in row["quality_flags"].split("|")
        ]
        self.assertEqual(len(partial), 10)
        self.assertEqual({row["period"] for row in partial}, {"2019-06-30", "2019-09-30"})
        self.assertEqual({row["source_table"] for row in partial}, {"pmjdy"})

    def test_preview_is_truthfully_non_certified(self):
        self.assertEqual(self.registry["qualityTier"], "standardized-preview")
        self.assertEqual(self.registry["certificationStatus"], "not-certified")
        self.assertFalse(self.registry["source"]["pageReferencesAvailable"])
        self.assertEqual({row["quality_status"] for row in self.rows}, {"suspect"})
        self.assertTrue(all(
            "source_document_unlinked" in row["quality_flags"].split("|")
            for row in self.rows
        ))

    def test_source_value_and_unit_are_preserved_and_declared(self):
        sample = next(
            row for row in self.rows
            if row["district"] == "East Garo Hills"
            and row["period"] == "2020-06-30"
            and row["indicator_id"] == "total_deposits_lakh"
        )
        self.assertEqual(sample["source_value"], "41301.84")
        self.assertEqual(sample["value"], "41301.84")
        self.assertEqual(sample["unit"], "INR lakh")


if __name__ == "__main__":
    unittest.main()
