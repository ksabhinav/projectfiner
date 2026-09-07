import json
import tempfile
import unittest
from pathlib import Path

from db.build_meghalaya_source_evidence import OUTPUT_PATH, render


class MeghalayaSourceEvidenceTests(unittest.TestCase):
    def test_committed_ledger_is_current(self):
        rendered, _ = render()
        self.assertEqual(OUTPUT_PATH.read_text(encoding="utf-8"), rendered)

    def test_ledger_exposes_the_complete_pending_backlog(self):
        _, document = render()
        summary = document["summary"]
        self.assertEqual(summary["observationCount"], 3494)
        self.assertEqual(summary["evidenceUnitCount"], 94)
        self.assertEqual(summary["verifiedEvidenceUnitCount"], 0)
        self.assertEqual(summary["capturedEvidenceUnitCount"], 0)
        self.assertEqual(summary["pendingEvidenceUnitCount"], 94)
        self.assertEqual(summary["observationsPendingEvidence"], 3494)
        self.assertEqual(
            {unit["reviewStatus"] for unit in document["evidenceUnits"]},
            {"pending"},
        )
        self.assertTrue(
            all(unit["sourceDocumentUrl"] is None for unit in document["evidenceUnits"])
        )

    def test_incomplete_evidence_claim_is_rejected(self):
        _, document = render()
        unit_id = document["evidenceUnits"][0]["evidenceUnitId"]
        input_document = {
            "schemaVersion": "source-evidence-input-v1",
            "productId": "meghalaya-standardized-preview",
            "releaseId": "meghalaya-standardized-preview-v2",
            "sourceId": "slbc-meghalaya",
            "evidence": [{
                "evidenceUnitId": unit_id,
                "sourceDocumentUrl": "https://onlineslbcne.nic.in/evidence",
                "sourceLocator": "table response",
                "capturedAt": "2026-09-07",
                "capturedBy": "test",
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(input_document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "documentSha256"):
                render(input_path=path)

    def test_complete_capture_is_not_verified_without_review(self):
        _, document = render()
        unit_id = document["evidenceUnits"][0]["evidenceUnitId"]
        input_document = {
            "schemaVersion": "source-evidence-input-v1",
            "productId": "meghalaya-standardized-preview",
            "releaseId": "meghalaya-standardized-preview-v2",
            "sourceId": "slbc-meghalaya",
            "evidence": [{
                "evidenceUnitId": unit_id,
                "sourceDocumentUrl": "https://onlineslbcne.nic.in/evidence",
                "archivedDocumentUrl": None,
                "documentSha256": "a" * 64,
                "sourceLocator": "retained response table",
                "capturedAt": "2026-09-07",
                "capturedBy": "test",
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(input_document), encoding="utf-8")
            _, updated = render(input_path=path)
        selected = next(
            unit for unit in updated["evidenceUnits"]
            if unit["evidenceUnitId"] == unit_id
        )
        self.assertEqual(selected["reviewStatus"], "captured")
        self.assertEqual(updated["summary"]["verifiedEvidenceUnitCount"], 0)


if __name__ == "__main__":
    unittest.main()
