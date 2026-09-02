import json
import sqlite3
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "db"))

from build_district_pages import GeographyRegistry
from init_schema import SCHEMA


class GeographyRegistryTests(unittest.TestCase):
    def setUp(self):
        self.districts = [
            {
                "lgd_code": 101,
                "state_lgd_code": 18,
                "state": "Assam",
                "district": "Canonical One",
                "aliases": ["Old One"],
            },
            {
                "lgd_code": 201,
                "state_lgd_code": 22,
                "state": "Chhattisgarh",
                "district": "Canonical One",
                "aliases": [],
            },
        ]

    def test_resolution_is_state_scoped_and_returns_canonical_identity(self):
        registry = GeographyRegistry(self.districts)
        district, reason = registry.resolve("assam", "Old One")
        self.assertIsNone(reason)
        self.assertEqual(district["lgdCode"], 101)
        self.assertEqual(district["districtSlug"], "canonical-one")

        district, reason = registry.resolve("chhattisgarh", "Old One")
        self.assertIsNone(district)
        self.assertEqual(reason, "unmatched_district")

    def test_reviewed_alias_cannot_cross_a_state_boundary(self):
        with self.assertRaisesRegex(ValueError, "crosses state boundary"):
            GeographyRegistry(self.districts, [{
                "state": "chhattisgarh",
                "alias": "Wrong-state alias",
                "district_lgd": 101,
            }])

    def test_ambiguous_state_scoped_alias_is_rejected(self):
        districts = [dict(row) for row in self.districts]
        districts[0]["aliases"] = ["Shared alias"]
        districts[1] = {
            **districts[1],
            "state": "Assam",
            "state_lgd_code": 18,
            "aliases": ["Shared alias"],
        }
        registry = GeographyRegistry(districts)
        district, reason = registry.resolve("assam", "Shared alias")
        self.assertIsNone(district)
        self.assertEqual(reason, "ambiguous_district")


class SlbcSchemaIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        self.db.executemany(
            "INSERT INTO states (lgd_code, name, slug) VALUES (?, ?, ?)",
            [(18, "Assam", "assam"), (22, "Chhattisgarh", "chhattisgarh")],
        )
        self.db.execute(
            "INSERT INTO districts (lgd_code, name, state_lgd_code) VALUES (101, 'Example', 18)"
        )
        self.db.execute(
            "INSERT INTO periods (id, label, code) VALUES (1, 'June 2026', '2026-06')"
        )
        self.db.execute(
            "INSERT INTO slbc_fields (id, field_key, category, field_name) "
            "VALUES (1, 'example_value', 'example', 'value')"
        )

    def tearDown(self):
        self.db.close()

    def test_matching_state_and_district_is_accepted(self):
        self.db.execute(
            "INSERT INTO slbc_data "
            "(state_lgd_code, district_lgd, period_id, field_id, value_numeric) "
            "VALUES (18, 101, 1, 1, 1)"
        )

    def test_cross_state_district_is_blocked_on_insert(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, "does not belong to state"):
            self.db.execute(
                "INSERT INTO slbc_data "
                "(state_lgd_code, district_lgd, period_id, field_id, value_numeric) "
                "VALUES (22, 101, 1, 1, 1)"
            )

    def test_cross_state_district_is_blocked_on_update(self):
        self.db.execute(
            "INSERT INTO slbc_data "
            "(state_lgd_code, district_lgd, period_id, field_id, value_numeric) "
            "VALUES (18, 101, 1, 1, 1)"
        )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "does not belong to state"):
            self.db.execute("UPDATE slbc_data SET state_lgd_code=22")


class GeneratedDistrictIndexTests(unittest.TestCase):
    def test_index_has_one_canonical_route_per_lgd(self):
        payload = json.loads((REPO_ROOT / "public/districts/index.json").read_text())
        districts = payload["districts"]
        redirects = payload["redirects"]

        lgd_codes = [row["lgdCode"] for row in districts]
        canonical_routes = {
            (row["state"], row["districtSlug"]) for row in districts
        }
        redirect_routes = {
            (row["state"], row["districtSlug"]) for row in redirects
        }
        self.assertEqual(payload["count"], len(districts))
        self.assertEqual(len(lgd_codes), len(set(lgd_codes)))
        self.assertEqual(len(canonical_routes), len(districts))
        self.assertTrue(canonical_routes.isdisjoint(redirect_routes))

    def test_sitemap_excludes_alias_redirects(self):
        payload = json.loads((REPO_ROOT / "public/districts/index.json").read_text())
        sitemap = (REPO_ROOT / "public/sitemap.xml").read_text()
        for redirect in payload["redirects"]:
            alias_url = (
                f'/district/{redirect["state"]}/{redirect["districtSlug"]}/'
            )
            self.assertNotIn(alias_url, sitemap)

    def test_every_canonical_route_has_a_matching_json_download(self):
        payload = json.loads((REPO_ROOT / "public/districts/index.json").read_text())
        for district in payload["districts"]:
            json_path = (
                REPO_ROOT
                / "public/districts"
                / district["state"]
                / f'{district["districtSlug"]}.json'
            )
            self.assertTrue(json_path.exists(), json_path)
            self.assertEqual(district["dataFiles"], [district["districtSlug"]])


if __name__ == "__main__":
    unittest.main()
