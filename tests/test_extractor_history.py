import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "db"))

from extractor_history import merge_complete_history


class ExtractorHistoryTests(unittest.TestCase):
    def test_partial_rerun_retains_older_quarters(self):
        existing = {
            "source": "old metadata",
            "legacy_note": "Wayback recovery",
            "quarters": {
                "2020-03": {"period": "March 2020", "tables": {"old": {}}},
                "2025-12": {"period": "December 2025", "tables": {"stale": {}}},
            },
        }
        candidate = {
            "source": "current metadata",
            "quarters": {
                "2025-12": {"period": "December 2025", "tables": {"fresh": {}}},
                "2026-03": {"period": "March 2026", "tables": {"new": {}}},
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "state_complete.json"
            output.write_text(json.dumps(existing), encoding="utf-8")
            merged, summary = merge_complete_history(candidate, output)

        self.assertEqual(list(merged["quarters"]), ["2020-03", "2025-12", "2026-03"])
        self.assertEqual(
            merged["quarters"]["2020-03"], existing["quarters"]["2020-03"]
        )
        self.assertEqual(
            merged["quarters"]["2025-12"], candidate["quarters"]["2025-12"]
        )
        self.assertEqual(merged["source"], "current metadata")
        self.assertEqual(merged["legacy_note"], "Wayback recovery")
        self.assertEqual(
            summary,
            {
                "preexisting": 2,
                "extracted": 2,
                "added": 1,
                "retained": 1,
                "total": 3,
            },
        )

    def test_first_run_uses_only_extracted_quarters(self):
        candidate = {
            "source": "SLBC",
            "quarters": {"2026-03": {"period": "March 2026", "tables": {}}},
        }
        with tempfile.TemporaryDirectory() as directory:
            merged, summary = merge_complete_history(
                candidate, Path(directory) / "missing.json"
            )

        self.assertEqual(merged, candidate)
        self.assertEqual(summary["preexisting"], 0)
        self.assertEqual(summary["added"], 1)
        self.assertEqual(summary["retained"], 0)

    def test_every_remaining_risky_writer_uses_history_guard(self):
        guarded = [
            "slbc-data/chhattisgarh/extract_chhattisgarh.py",
            "slbc-data/jharkhand/extract_jharkhand.py",
            "slbc-data/odisha/extract_odisha.py",
            "public/slbc-data/extract_karnataka.py",
        ]
        for relative in guarded:
            source = (REPO_ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("merge_complete_history", source, relative)

        v2 = (
            REPO_ROOT
            / "slbc-data/chhattisgarh/extract_chhattisgarh_v2.py"
        ).read_text(encoding="utf-8")
        self.assertIn("build_complete_json", v2)
        self.assertIn("from extract_chhattisgarh import", v2)


if __name__ == "__main__":
    unittest.main()
