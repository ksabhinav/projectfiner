import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "db"))

from match_districts import DistrictMatcher


class DistrictMatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "districts.db"
        db = sqlite3.connect(self.db_path)
        db.executescript(
            """
            CREATE TABLE states (
                lgd_code INTEGER PRIMARY KEY,
                slug TEXT NOT NULL
            );
            CREATE TABLE districts (
                lgd_code INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                state_lgd_code INTEGER NOT NULL
            );
            CREATE TABLE district_aliases (
                district_lgd INTEGER NOT NULL,
                alias TEXT NOT NULL,
                source TEXT
            );
            """
        )
        db.executemany(
            "INSERT INTO states (lgd_code, slug) VALUES (?, ?)",
            [(2, "himachal-pradesh"), (18, "assam"), (22, "chhattisgarh")],
        )
        db.executemany(
            "INSERT INTO districts (lgd_code, name, state_lgd_code) VALUES (?, ?, ?)",
            [
                (101, "Bilaspur", 2),
                (201, "Bilaspur", 22),
                (301, "Tamulpur", 18),
                (302, "Bastar", 22),
            ],
        )
        db.executemany(
            "INSERT INTO district_aliases (district_lgd, alias, source) VALUES (?, ?, ?)",
            [
                (101, "Old Bilaspur", "test"),
                (201, "Old Bilaspur", "test"),
                (301, "Tamulpur District HQ", "test"),
            ],
        )
        db.commit()
        db.close()
        self.matcher = DistrictMatcher(self.db_path)

    def tearDown(self):
        self.matcher.close()
        self.temp_dir.cleanup()

    def test_shared_name_resolves_inside_supplied_state(self):
        self.assertEqual(self.matcher.resolve("Bilaspur", state_lgd=2), 101)
        self.assertEqual(self.matcher.resolve("Bilaspur", state_slug="chhattisgarh"), 201)

    def test_wrong_state_never_falls_back_to_another_state(self):
        self.assertIsNone(self.matcher.resolve("Tamulpur", state_lgd=22))

    def test_unknown_state_slug_never_falls_back_globally(self):
        self.assertIsNone(self.matcher.resolve("Tamulpur", state_slug="not-a-state"))

    def test_unique_name_can_resolve_when_state_is_absent(self):
        self.assertEqual(self.matcher.resolve("Tamulpur"), 301)

    def test_ambiguous_name_is_rejected_when_state_is_absent(self):
        self.assertIsNone(self.matcher.resolve("Bilaspur"))

    def test_ambiguous_alias_is_rejected_when_state_is_absent(self):
        self.assertIsNone(self.matcher.resolve("Old Bilaspur"))

    def test_suffix_is_removed_exactly_not_with_rstrip_character_semantics(self):
        self.assertEqual(self.matcher.resolve("Bastar District", state_lgd=22), 302)

    def test_alias_remains_state_scoped(self):
        self.assertEqual(self.matcher.resolve("Tamulpur District HQ", state_lgd=18), 301)
        self.assertIsNone(self.matcher.resolve("Tamulpur District HQ", state_lgd=22))


if __name__ == "__main__":
    unittest.main()
