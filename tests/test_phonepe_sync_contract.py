import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public/digital-payments/phonepe_district_timeseries.json"


class PhonePeSyncContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(DATA.read_text(encoding="utf-8"))

    def test_series_is_a_pinned_full_restatement(self):
        self.assertEqual(self.data["schema_version"], 3)
        self.assertEqual(self.data["storage"], "quarterly-partitions")
        self.assertEqual(self.data["source_revision"], "943e6e52a71513d683f804add12d0b61145e8007")
        self.assertEqual(self.data["license"], "CDLA-Permissive-2.0")
        self.assertEqual(self.data["methodology_version"], "phonepe-pulse-restated-amj-2026")
        self.assertEqual(self.data["num_periods"], 34)
        self.assertEqual(self.data["latest_period"], "2026-06")
        self.assertIn("Do not join", self.data["comparability_warning"])

    def test_latest_period_has_amount_and_merchant_data(self):
        latest_meta = self.data["periods"][-1]
        latest = json.loads((ROOT / "public/indicators/digital_transactions/2026-06.json").read_text(encoding="utf-8"))
        self.assertEqual(latest_meta["period_code"], "2026-06")
        self.assertGreaterEqual(latest_meta["num_districts"], 780)
        self.assertTrue(all(int(row["transaction_count"]) >= 0 for row in latest["districts"]))
        self.assertTrue(all(float(row["transaction_amount"]) >= 0 for row in latest["districts"]))
        merchant_rows = sum("registered_merchants" in row for row in latest["districts"])
        self.assertGreaterEqual(merchant_rows, 700)

    def test_manifest_and_ui_use_the_new_horizon(self):
        manifest = json.loads((ROOT / "public/indicators/manifest.json").read_text(encoding="utf-8"))
        page = (ROOT / "src/pages/index.astro").read_text(encoding="utf-8")
        citation = (ROOT / "src/lib/indicator-sources.ts").read_text(encoding="utf-8")
        self.assertEqual(manifest["quarters_by_indicator"]["digital_transactions"][0], "2026-06")
        self.assertIn("registered_merchants", page)
        self.assertNotIn("timePoints: ['2024-03'", page)
        self.assertIn("CDLA-Permissive-2.0", citation)


if __name__ == "__main__":
    unittest.main()
