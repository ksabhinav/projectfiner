import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from db.build_meghalaya_source_evidence import OUTPUT_PATH, render, validate_input


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
                "documentSha256": hashlib.sha256(b"retained report").hexdigest(),
                "retainedDocumentPath": "report.html",
                "sourceLocator": "retained response table",
                "capturedAt": "2026-09-07",
                "capturedBy": "test",
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(input_document), encoding="utf-8")
            (Path(directory) / "report.html").write_bytes(b"retained report")
            _, updated = render(input_path=path, archive_root=Path(directory))
        selected = next(
            unit for unit in updated["evidenceUnits"]
            if unit["evidenceUnitId"] == unit_id
        )
        self.assertEqual(selected["reviewStatus"], "captured")
        self.assertEqual(updated["summary"]["verifiedEvidenceUnitCount"], 0)


    def test_retained_document_integrity_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "report.html"
            report.write_bytes(b"original report")
            item = {
                "evidenceUnitId": "test-unit",
                "sourceDocumentUrl": "https://onlineslbcne.nic.in/report.php",
                "documentSha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                "retainedDocumentPath": "report.html",
                "sourceLocator": "district table",
                "capturedAt": "2026-09-29",
                "capturedBy": "test",
            }
            document = {
                "schemaVersion": "source-evidence-input-v1",
                "productId": "meghalaya-standardized-preview",
                "releaseId": "meghalaya-standardized-preview-v2",
                "sourceId": "slbc-meghalaya",
                "evidence": [item],
            }
            validate_input(document, {"test-unit"}, root)
            for path, message in [
                (None, "requires retainedDocumentPath"),
                ("absent.html", "is missing"),
                ("../outside.html", "within the repository"),
                (str(report), "within the repository"),
            ]:
                with self.subTest(path=path):
                    item["retainedDocumentPath"] = path
                    with self.assertRaisesRegex(ValueError, message):
                        validate_input(document, {"test-unit"}, root)
            item["retainedDocumentPath"] = "report.html"
            report.write_bytes(b"altered report")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                validate_input(document, {"test-unit"}, root)
            report.write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "is empty"):
                validate_input(document, {"test-unit"}, root)
            (root / "outside-link.html").symlink_to(root.parent)
            item["retainedDocumentPath"] = "outside-link.html/report.html"
            with self.assertRaisesRegex(ValueError, "within the repository"):
                validate_input(document, {"test-unit"}, root)


if __name__ == "__main__":
    unittest.main()
