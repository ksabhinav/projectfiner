import json
import unittest
from pathlib import Path


REGISTRY = Path(__file__).parents[1] / "public" / "data-quality" / "quarantines.json"


class QuarantineRegistryTest(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(REGISTRY.read_text())
        self.rules = self.payload["rules"]

    def test_registry_contains_every_current_critical_finding(self):
        self.assertEqual(len(self.rules), 14)

    def test_rules_are_unique_and_complete(self):
        required = {"state", "district", "quarter", "category", "field", "reason"}
        identities = set()
        for rule in self.rules:
            self.assertTrue(required.issubset(rule))
            identity = tuple(rule[key] for key in ("state", "district", "quarter", "category", "field"))
            self.assertNotIn(identity, identities)
            identities.add(identity)
            self.assertRegex(rule["quarter"], r"^\d{4}-\d{2}$")
            self.assertTrue(rule["reason"].strip())


if __name__ == "__main__":
    unittest.main()
