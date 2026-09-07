import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "db/public_formula_error_corrections.json"
FORMULA_ERROR = "#DIV/0!"


class PublicFormulaErrorTests(unittest.TestCase):
    def test_corrections_are_explicit_and_complete(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(registry["schemaVersion"], "public-formula-error-corrections-v1")
        self.assertEqual(len(registry["corrections"]), 16)
        self.assertEqual(
            {item["sourceToken"] for item in registry["corrections"]},
            {FORMULA_ERROR},
        )
        self.assertEqual(
            {item["replacement"] for item in registry["corrections"]},
            {None},
        )
        self.assertTrue(
            all(item["path"].startswith("public/slbc-data/") for item in registry["corrections"])
        )

    def test_public_data_contains_no_literal_division_errors(self):
        offenders = []
        for path in (REPO_ROOT / "public/slbc-data").rglob("*"):
            if path.is_file() and FORMULA_ERROR in path.read_text(
                encoding="utf-8", errors="replace"
            ):
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
