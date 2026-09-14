import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "db"))

from import_safety import ImportAudit, upsert_slbc_data
import import_slbc


class SlbcUpsertSafetyTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(
            """
            CREATE TABLE slbc_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state_lgd_code INTEGER NOT NULL,
                district_lgd INTEGER NOT NULL,
                period_id INTEGER NOT NULL,
                field_id INTEGER NOT NULL,
                value_text TEXT,
                value_numeric REAL,
                source_file TEXT
            );
            CREATE UNIQUE INDEX idx_slbc_unique
            ON slbc_data(district_lgd, period_id, field_id);
            """
        )

    def tearDown(self):
        self.db.close()

    def test_conflict_update_preserves_row_identity(self):
        original = (7, 101, 1, 22, "10", 10.0, "first.json")
        changed = (7, 101, 1, 22, "12", 12.0, "second.json")

        self.assertEqual(upsert_slbc_data(self.db, [original]), 1)
        original_id = self.db.execute(
            "SELECT id FROM slbc_data"
        ).fetchone()[0]

        self.assertEqual(upsert_slbc_data(self.db, [changed]), 1)
        row = self.db.execute(
            "SELECT id, value_text, value_numeric, source_file FROM slbc_data"
        ).fetchone()

        self.assertEqual(row, (original_id, "12", 12.0, "second.json"))
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM slbc_data").fetchone()[0],
            1,
        )

    def test_replaying_batch_converges_without_duplicates(self):
        rows = [
            (7, 101, 1, 22, "10", 10.0, "delhi"),
            (7, 101, 1, 23, "20", 20.0, "delhi"),
        ]
        upsert_slbc_data(self.db, rows)
        first = self.db.execute(
            "SELECT id, district_lgd, period_id, field_id, value_numeric "
            "FROM slbc_data ORDER BY field_id"
        ).fetchall()

        upsert_slbc_data(self.db, rows)
        second = self.db.execute(
            "SELECT id, district_lgd, period_id, field_id, value_numeric "
            "FROM slbc_data ORDER BY field_id"
        ).fetchall()

        self.assertEqual(second, first)
        self.assertEqual(upsert_slbc_data(self.db, []), 0)

    def test_no_slbc_importer_uses_replace_semantics(self):
        offenders = []
        for path in (REPO_ROOT / "db").glob("import*.py"):
            if "INSERT OR REPLACE INTO slbc_data" in path.read_text(encoding="utf-8"):
                offenders.append(path.name)
        self.assertEqual(offenders, [])



    def test_unified_importer_accounts_for_silent_skip_cases(self):
        self.db.executescript(
            """
            CREATE TABLE periods (
                id INTEGER PRIMARY KEY,
                label TEXT UNIQUE,
                code TEXT UNIQUE
            );
            CREATE TABLE slbc_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_key TEXT UNIQUE,
                category TEXT,
                field_name TEXT,
                unit TEXT
            );
            INSERT INTO periods(id, label, code)
            VALUES (1, 'March 2025', '2025-03');
            """
        )

        class Matcher:
            @staticmethod
            def state_lgd_from_slug(slug):
                return 7

            @staticmethod
            def resolve(name, **kwargs):
                return 101 if name == "Known" else None

        source = {
            "periods": [{
                "period": "March 2025",
                "districts": [
                    {
                        "district": "Known",
                        "branch_network__total_branch": "4",
                    },
                    {
                        "district": "Unknown",
                        "branch_network__total_branch": "5",
                    },
                    {
                        "district": "Known",
                        "period": "",
                        "branch_network__total_branch": "6",
                    },
                ],
            }]
        }
        audit = ImportAudit("slbc")
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "delhi"
            state_dir.mkdir()
            (state_dir / "delhi_fi_timeseries.json").write_text(
                json.dumps(source), encoding="utf-8"
            )
            original_dir = import_slbc.SLBC_DIR
            import_slbc.SLBC_DIR = directory
            try:
                rows = import_slbc.import_state_timeseries(
                    self.db, Matcher(), "delhi", {}, {}, audit=audit
                )
            finally:
                import_slbc.SLBC_DIR = original_dir

        self.assertEqual(rows, 1)
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM slbc_data").fetchone()[0],
            1,
        )
        self.assertEqual(audit.summary()["records_observed"], 3)
        self.assertEqual(audit.summary()["records_accepted"], 1)
        self.assertEqual(audit.summary()["records_rejected"], 2)

    def test_reject_ledger_is_deterministic_and_reconciles(self):
        audit = ImportAudit("slbc")
        audit.accept()
        for _ in range(2):
            audit.reject(
                "unresolved_district",
                state_slug="assam",
                period_label="March 2025",
                district_raw="Unknown",
            )

        self.assertEqual(
            audit.summary(),
            {
                "source": "slbc",
                "records_observed": 3,
                "records_accepted": 1,
                "records_rejected": 2,
                "unique_rejects": 1,
            },
        )

        with tempfile.TemporaryDirectory() as directory:
            ledger_path, summary_path = audit.write(directory)
            entries = [
                json.loads(line)
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
            ]
            persisted_summary = json.loads(
                summary_path.read_text(encoding="utf-8")
            )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["occurrence_count"], 2)
        self.assertEqual(
            entries[0]["reason"], "unresolved_district"
        )
        self.assertEqual(persisted_summary, audit.summary())


if __name__ == "__main__":
    unittest.main()
