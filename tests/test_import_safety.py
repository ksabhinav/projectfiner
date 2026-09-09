import sqlite3
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "db"))

from import_safety import upsert_slbc_data


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


if __name__ == "__main__":
    unittest.main()
