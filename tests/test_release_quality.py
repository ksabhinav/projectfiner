import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "db"))

from validate_release_data import validate_release


class ReleaseQualityTests(unittest.TestCase):
    def make_release(self, content, *, file_format="CSV", overrides=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        public = Path(temporary.name)
        suffix = file_format.lower()
        path = public / f"sample.{suffix}"
        raw = content.encode("utf-8")
        path.write_bytes(raw)
        distribution = {
            "path": path.name,
            "format": file_format,
            "mediaType": "text/csv" if file_format == "CSV" else "application/json",
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "encoding": "utf-8",
        }
        if file_format == "CSV":
            rows = list(csv.reader(content.splitlines()))
            distribution.update({
                "rowCount": max(0, len(rows) - 1),
                "columnCount": len(rows[0]) if rows else 0,
                "irregularRowCount": 0,
            })
        distribution.update(overrides or {})
        manifest = {"states": [{"slug": "sample", "distributions": [distribution]}]}
        manifest_path = public / "release-manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest_path, public

    def test_committed_release_passes_structural_gate(self):
        self.assertEqual(validate_release(), [])

    def test_rejects_irregular_csv_rows(self):
        manifest, public = self.make_release("district,period\nAlpha,March 2025,extra\n")
        errors = validate_release(manifest, public)
        self.assertTrue(any("has 3 columns; expected 2" in error for error in errors), errors)

    def test_rejects_blank_and_duplicate_headers(self):
        manifest, public = self.make_release("district,,district\nAlpha,x,y\n")
        errors = validate_release(manifest, public)
        self.assertTrue(any("blank CSV header" in error for error in errors), errors)

    def test_rejects_duplicate_json_keys_and_non_finite_numbers(self):
        for content, expected in [('{"a": 1, "a": 2}', "duplicate JSON key"),
                                  ('{"value": NaN}', "non-finite JSON number")]:
            with self.subTest(content=content):
                manifest, public = self.make_release(content, file_format="JSON")
                errors = validate_release(manifest, public)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_rejects_bom_and_integrity_drift(self):
        manifest, public = self.make_release("\ufeffdistrict,period\nAlpha,March 2025\n")
        errors = validate_release(manifest, public)
        self.assertTrue(any("BOM is not allowed" in error for error in errors), errors)

        manifest, public = self.make_release(
            "district,period\nAlpha,March 2025\n", overrides={"sha256": "0" * 64}
        )
        errors = validate_release(manifest, public)
        self.assertTrue(any("SHA-256 does not match" in error for error in errors), errors)

    def test_rejects_path_traversal(self):
        manifest, public = self.make_release(
            "district,period\nAlpha,March 2025\n", overrides={"path": "../sample.csv"}
        )
        errors = validate_release(manifest, public)
        self.assertTrue(any("safe POSIX path" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
