import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
            source = ROOT / state["sourceArtifact"].lstrip("/")
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
