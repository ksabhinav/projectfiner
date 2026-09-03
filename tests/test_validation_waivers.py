import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from validate_data import (
    Issue,
    build_waiver_ledger,
    evaluate_waiver_ledger,
    issue_fingerprint,
    load_waiver_ledger,
    write_waiver_ledger,
)


def critical(district="Alpha", field="metric", period="March 2025"):
    return Issue(
        "meghalaya",
        "10x_jump",
        Issue.CRITICAL,
        district,
        field,
        period,
        "human-readable values may change",
    )


class ValidationWaiverTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 9, 2)
        self.ledger = build_waiver_ledger(
            [critical()],
            created_on=self.today,
            expires_on=date(2026, 12, 1),
        )

    def test_fingerprint_ignores_message_but_not_observation_identity(self):
        original = critical()
        changed_message = critical()
        changed_message.message = "different values"
        changed_period = critical(period="June 2025")
        self.assertEqual(issue_fingerprint(original), issue_fingerprint(changed_message))
        self.assertNotEqual(issue_fingerprint(original), issue_fingerprint(changed_period))

    def test_same_bucket_replacement_is_a_new_unwaived_finding(self):
        replacement = critical(district="Beta")
        unwaived, resolved, errors = evaluate_waiver_ledger(
            [replacement], self.ledger, today=self.today
        )
        self.assertEqual(unwaived, [replacement])
        self.assertEqual(resolved, self.ledger["fingerprints"])
        self.assertEqual(errors, [])

    def test_sharded_ledger_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "waivers"
            write_waiver_ledger(path, self.ledger)
            self.assertEqual(load_waiver_ledger(path), self.ledger | {
                "shards": [f"{prefix}.txt" for prefix in "0123456789abcdef"]
            })

    def test_resolved_findings_do_not_hide_new_findings(self):
        new_issue = critical(field="another_metric")
        unwaived, resolved, errors = evaluate_waiver_ledger(
            [new_issue], self.ledger, today=self.today
        )
        self.assertEqual(len(unwaived), 1)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(errors, [])

    def test_expired_or_tampered_ledger_fails(self):
        _, _, errors = evaluate_waiver_ledger(
            [critical()], self.ledger, today=date(2026, 12, 2)
        )
        self.assertIn("waiver ledger expired on 2026-12-01", errors)

        tampered = json.loads(json.dumps(self.ledger))
        tampered["total_waived"] = 99
        _, _, errors = evaluate_waiver_ledger(
            [critical()], tampered, today=self.today
        )
        self.assertIn("waiver ledger total_waived does not match fingerprints", errors)

        finding = critical()
        unwaived, _, errors = evaluate_waiver_ledger(
            [finding], [], today=self.today
        )
        self.assertEqual(unwaived, [finding])
        self.assertEqual(errors, ["waiver ledger root must be an object"])


if __name__ == "__main__":
    unittest.main()
