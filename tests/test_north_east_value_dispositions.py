import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "db"))
from import_slbc import parse_numeric


class NorthEastValueDispositionTests(unittest.TestCase):
    def test_importer_preserves_source_text_without_guessing_numbers(self):
        fixtures = json.loads((ROOT / "tests/fixtures/numeric-values.json").read_text())
        for fixture in fixtures:
            with self.subTest(value=fixture["value"]):
                text, numeric = parse_numeric(fixture["value"])
                self.assertEqual(numeric, fixture["expected"])
                expected_text = None if fixture["value"] is None else str(fixture["value"]).strip()
                self.assertEqual(text, expected_text)
        for value in [float("inf"), float("nan"), "9" * 400]:
            self.assertIsNone(parse_numeric(value)[1])

    def test_ledger_links_every_disposition_to_unchanged_source_bytes(self):
        ledger = json.loads((ROOT / "public/data-contracts/north-east-value-dispositions.json").read_text())
        self.assertEqual(ledger["summary"]["valueClassCounts"], {
            "split-numeric-tokens": 268, "spreadsheet-error": 4,
            "percentage-text": 69, "missing-marker": 39,
        })
        self.assertEqual(ledger["summary"]["stateCount"], 8)
        self.assertEqual(ledger["summary"]["quarantinedCount"], 272)
        self.assertEqual(ledger["summary"]["reviewRequiredCount"], 108)
        sources = {}
        for state in ledger["states"]:
            raw = (ROOT / "public" / state["sourceArtifact"].lstrip("/")).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), state["sourceArtifactSha256"])
            sources[state["stateSlug"]] = json.loads(raw)
        ids = set()
        for row in ledger["records"]:
            value = sources[row["stateSlug"]]
            for token in row["sourceJsonPointer"].split("/")[1:]:
                token = token.replace("~1", "/").replace("~0", "~")
                value = value[int(token)] if isinstance(value, list) else value[token]
            self.assertEqual(value, row["sourceValue"])
            self.assertIsNone(row["numericValue"])
            self.assertIsNone(parse_numeric(value)[1])
            ids.add(row["observationId"])
        self.assertEqual(len(ids), 380)

    def test_dispositions_and_extended_quarantine_are_reproducible(self):
        subprocess.run([sys.executable, "db/build_north_east_value_dispositions.py", "--check"], cwd=ROOT, check=True)
