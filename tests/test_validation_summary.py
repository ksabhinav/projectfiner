import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate_data


class ValidationSummaryTest(unittest.TestCase):
    def test_report_emits_machine_readable_provenance(self):
        issues = [
            validate_data.Issue("assam", "period_gap", "warning", "ALL", "-", "ALL", "gap"),
            validate_data.Issue("assam", "10x_jump", "critical", "Dibrugarh", "x", "March 2026", "jump"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.md"
            summary = Path(tmp) / "summary.json"
            with patch.object(validate_data, "REPORT_PATH", report), patch.object(validate_data, "SUMMARY_PATH", summary):
                validate_data.generate_report(issues, ["assam"])
            payload = json.loads(summary.read_text())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["states_processed"], 1)
        self.assertEqual(payload["totals"], {"critical": 1, "warning": 1, "info": 0})
        self.assertEqual(payload["states"]["assam"]["critical"], 1)
        self.assertTrue(payload["generated_at"])


if __name__ == "__main__":
    unittest.main()
