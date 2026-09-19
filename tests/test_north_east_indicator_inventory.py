import copy
import csv
import hashlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "db"))
import build_north_east_indicator_inventory as builder
INVENTORY = (
    ROOT / "public" / "data-contracts" / "north-east-indicator-inventory.json"
)
BUILDER = ROOT / "db" / "build_north_east_indicator_inventory.py"
EXPECTED = {
    "arunachal-pradesh": (26, 611, 465),
    "assam": (35, 1095, 1025),
    "manipur": (40, 619, 1017),
    "meghalaya": (23, 268, 1248),
    "mizoram": (29, 301, 553),
    "nagaland": (26, 352, 367),
    "sikkim": (4, 24, 8),
    "tripura": (35, 280, 185),
}


def git_blob_sha(path):
    content = path.read_bytes()
    payload = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    return hashlib.sha1(payload).hexdigest()


class NorthEastIndicatorInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def test_missingness_and_numeric_syntax_are_not_guessed(self):
        cases = [
            (None, "null"), ("", "blank"), (" \n\t", "blank"),
            ("NA", "missing-marker"), ("n/a", "missing-marker"),
            ("_", "missing-marker"), ("-", "missing-marker"),
            ("0", "numeric"), (0, "numeric"), (12.5, "numeric"),
            ("-0.00", "numeric"), ("1,234,567.89", "numeric"),
            ("1,23,456.78", "numeric"), ("+1,234", "numeric"),
            ("-.5", "numeric"), ("1234", "numeric"),
            ("1,2,3", "invalid-numeric-grouping"),
            ("12,34", "invalid-numeric-grouping"),
            ("1,,234", "invalid-numeric-grouping"),
            ("6 5.84", "split-numeric-tokens"),
            ("1,234\n5,678", "split-numeric-tokens"),
            ("81.00%", "percentage-text"), ("0 %", "percentage-text"),
            ("#DIV/0!", "spreadsheet-error"), ("#N/A", "spreadsheet-error"),
            ("NaN", "non-finite"), (float("inf"), "non-finite"),
            ("-Infinity", "non-finite"), (True, "unsupported-type"),
            ([1], "unsupported-type"), ({"value": 1}, "unsupported-type"),
            ("Not available", "text"), ("NIL", "text"),
            ("26.03.2025", "text"), ("1e3", "text"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(builder.classify_value(raw), expected)

    def test_numeric_coverage_excludes_missing_cells_and_keeps_zero(self):
        source = self.fixture()
        state = self.profile(source)
        field = next(f for f in state["fields"] if f["sourceField"] == "test__value")
        self.assertEqual(state["recordCount"], 4)
        self.assertEqual((field["presentCount"], field["absentCount"]), (3, 1))
        self.assertEqual((field["numericCount"], field["zeroCount"]), (1, 1))
        self.assertEqual((field["periodCount"], field["numericPeriodCount"]), (2, 1))
        self.assertEqual(field["numericPeriods"], ["2024-06"])
        self.assertEqual((field["districtLabelCount"], field["numericDistrictLabelCount"]), (2, 1))
        self.assertEqual(field["valueClassCounts"]["missing-marker"], 1)
        self.assertEqual(field["valueClassCounts"]["blank"], 1)
        self.assertEqual(field["nonblankCount"], 2)

    def test_untrusted_source_structure_and_stale_pins_fail_closed(self):
        source = self.fixture()
        raw = json.dumps(source).encode()
        with self.assertRaisesRegex(ValueError, "source Git blob hash changed"):
            builder.profile_state("assam", "0" * 40, raw)
        variants = []
        wrong_state = copy.deepcopy(source)
        wrong_state["state"] = "meghalaya"
        variants.append(wrong_state)
        wrong_period = copy.deepcopy(source)
        wrong_period["periods"][0]["districts"][0]["period"] = "March 2024"
        variants.append(wrong_period)
        duplicate_district = copy.deepcopy(source)
        duplicate_district["periods"][0]["districts"].append(
            duplicate_district["periods"][0]["districts"][0]
        )
        variants.append(duplicate_district)
        duplicate_period = copy.deepcopy(source)
        duplicate_period["periods"].append(duplicate_period["periods"][0])
        variants.append(duplicate_period)
        bad_container = copy.deepcopy(source)
        bad_container["periods"][0]["districts"] = {}
        variants.append(bad_container)
        for variant in variants:
            with self.subTest(source=variant), self.assertRaises(ValueError):
                self.profile(variant)
        for raw in (b'{"state":"assam","state":"meghalaya"}',
                    b'{"state":"assam","value":NaN}'):
            with self.assertRaises(ValueError):
                self.profile_bytes(raw)

    def test_shared_labels_require_numeric_periods_in_every_named_state(self):
        assam = self.profile(self.fixture())
        meghalaya = copy.deepcopy(assam)
        meghalaya["stateSlug"] = "meghalaya"
        field = next(f for f in meghalaya["fields"] if f["sourceField"] == "test__value")
        field["numericPeriods"] = []
        with patch.object(builder, "STATES", [("assam", "a"), ("meghalaya", "b")]), \
                patch.object(builder, "source_path") as source_path, \
                patch.object(builder, "profile_state", side_effect=[assam, meghalaya]):
            source_path.return_value.read_bytes.return_value = b""
            inventory = builder.build_inventory()
        shared = next(f for f in inventory["sharedExactFieldLabels"] if f["sourceField"] == "test__value")
        self.assertEqual(shared["states"], ["assam", "meghalaya"])
        self.assertEqual(shared["numericStates"], ["assam"])
        self.assertEqual(shared["commonNumericPeriods"], [])
        self.assertEqual(shared["commonNumericPeriodCount"], 0)

    def test_examples_are_bounded_and_locate_original_cells(self):
        field_name = "test__path~/name"
        source = {"state": "assam", "periods": [{"period": "June 2024", "districts": [
            {"district": str(i), field_name: "private@example.test"} for i in range(4)
        ]}]}
        state = self.profile(source)
        examples = state["fields"][0]["reviewExamples"]
        self.assertEqual(len(examples), 2)
        for example in examples:
            self.assertNotIn("sourceValue", example)
            self.assertIn("path~0~1name", example["sourceJsonPointer"])
            self.assertEqual(self.resolve_pointer(source, example["sourceJsonPointer"]), "private@example.test")

    def test_committed_counts_reconcile_and_examples_match_hashed_sources(self):
        for state in self.inventory["states"]:
            raw = (ROOT / "public" / state["sourceArtifact"].lstrip("/")).read_bytes()
            source = json.loads(raw)
            self.assertEqual(state["sourceArtifactSha256"], hashlib.sha256(raw).hexdigest())
            for field in state["fields"]:
                counts = field["valueClassCounts"]
                self.assertEqual(sum(counts.values()), field["presentCount"])
                self.assertEqual(field["presentCount"] + field["absentCount"], state["recordCount"])
                self.assertEqual(field["numericCount"], counts["numeric"])
                self.assertEqual(field["numericPeriodCount"], len(field["numericPeriods"]))
                self.assertLessEqual(field["zeroCount"], field["numericCount"])
                for example in field["reviewExamples"]:
                    value = self.resolve_pointer(source, example["sourceJsonPointer"])
                    self.assertEqual(builder.classify_value(value), example["valueClass"])
                    if "sourceValue" in example:
                        self.assertEqual(example["sourceValue"], value)
            for key in builder.VALUE_CLASSES:
                self.assertEqual(state["valueClassCounts"][key], sum(f["valueClassCounts"][key] for f in state["fields"]))
        states = {s["stateSlug"]: s for s in self.inventory["states"]}
        self.assertEqual(states["assam"]["valueClassCounts"]["split-numeric-tokens"], 268)
        self.assertEqual(states["sikkim"]["valueClassCounts"]["percentage-text"], 45)
        self.assertEqual(states["meghalaya"]["valueClassCounts"]["spreadsheet-error"], 4)
        quarantine = json.loads((ROOT / "db/assam_split_number_quarantine.json").read_text())
        for record in quarantine["records"]:
            self.assertEqual(builder.classify_value(record["raw_value"]), "split-numeric-tokens")

    def test_review_csv_is_complete_and_reproducible(self):
        text = builder.REVIEW_OUTPUT.read_text(encoding="utf-8")
        self.assertEqual(text, builder.serialise_review(self.inventory))
        rows = list(csv.DictReader(io.StringIO(text)))
        ids = {f["indicatorId"] for s in self.inventory["states"] for f in s["fields"]}
        self.assertEqual({r["indicator_id"] for r in rows}, ids)
        self.assertEqual(len(rows), len(ids))
        self.assertTrue(all(r["cross_state_comparable"] == "false" for r in rows))

    @staticmethod
    def fixture():
        return {"state": "assam", "periods": [
            {"period": "June 2024", "districts": [
                {"district": "A", "test__value": "0"},
                {"district": "B", "test__value": "NA"},
            ]},
            {"period": "September 2024", "districts": [
                {"district": "A", "test__value": ""}, {"district": "B"},
            ]},
        ]}

    @classmethod
    def profile(cls, source):
        return cls.profile_bytes(json.dumps(source).encode())

    @staticmethod
    def profile_bytes(raw):
        sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        return builder.profile_state("assam", sha, raw)

    @staticmethod
    def resolve_pointer(source, pointer):
        value = source
        for token in pointer.split("/")[1:]:
            token = token.replace("~1", "/").replace("~0", "~")
            value = value[int(token)] if isinstance(value, list) else value[token]
        return value

    def test_committed_inventory_is_reproducible(self):
        subprocess.run(
            [sys.executable, str(BUILDER), "--check"],
            cwd=ROOT,
            check=True,
        )

    def test_all_eight_states_and_source_versions_are_exact(self):
        states = {
            state["stateSlug"]: state for state in self.inventory["states"]
        }
        self.assertEqual(set(states), set(EXPECTED))
        for slug, (periods, records, fields) in EXPECTED.items():
            state = states[slug]
            self.assertEqual(
                (state["periodCount"], state["recordCount"], state["fieldCount"]),
                (periods, records, fields),
            )
            source = ROOT / "public" / state["sourceArtifact"].lstrip("/")
            self.assertEqual(state["sourceGitBlobSha"], git_blob_sha(source))

    def test_inventory_does_not_guess_semantic_equivalence(self):
        self.assertEqual(self.inventory["qualityTier"], "raw-experimental")
        self.assertEqual(
            self.inventory["scope"]["fieldEntryCount"],
            sum(value[2] for value in EXPECTED.values()),
        )
        indicator_ids = []
        for state in self.inventory["states"]:
            for field in state["fields"]:
                indicator_ids.append(field["indicatorId"])
                self.assertIsNone(field["unit"])
                self.assertEqual(field["unitStatus"], "not-reviewed")
                self.assertIsNone(field["measureType"])
                self.assertEqual(field["measureTypeStatus"], "not-reviewed")
                self.assertFalse(field["crossStateComparable"])
        self.assertEqual(len(indicator_ids), len(set(indicator_ids)))

        shared = self.inventory["sharedExactFieldLabels"]
        self.assertTrue(shared)
        self.assertLess(max(item["stateCount"] for item in shared), 8)
        self.assertTrue(
            all(item["semanticEquivalence"] == "not-reviewed" for item in shared)
        )


if __name__ == "__main__":
    unittest.main()
