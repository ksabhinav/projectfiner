import hashlib
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "db"))

from build_versioned_release import render_release, verify


class VersionedReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release_id, cls.files, cls.catalog_text = render_release()
        cls.release_dir = REPO_ROOT / "public" / "releases" / cls.release_id
        cls.descriptor = json.loads(cls.files["release.json"])

    def test_committed_release_is_current_and_immutable(self):
        self.assertEqual(verify(self.release_id, self.files, self.catalog_text), [])
        for name, expected in self.files.items():
            self.assertEqual((self.release_dir / name).read_bytes(), expected)

    def test_snapshot_matches_canonical_preview_byte_for_byte(self):
        source = REPO_ROOT / "public/data-contracts/meghalaya-standardized-preview.csv"
        snapshot = self.release_dir / "observations.csv"
        self.assertEqual(snapshot.read_bytes(), source.read_bytes())
        observations = next(
            item for item in self.descriptor["distributions"]
            if item["role"] == "observations"
        )
        self.assertEqual(
            observations["sha256"], hashlib.sha256(snapshot.read_bytes()).hexdigest()
        )

    def test_release_candidate_cannot_claim_certification(self):
        self.assertEqual(self.descriptor["releaseStatus"], "immutable-preview")
        self.assertEqual(self.descriptor["certificationStatus"], "not-certified")
        self.assertFalse(self.descriptor["certification"]["eligible"])
        blockers = {
            item["code"]: item["count"]
            for item in self.descriptor["certification"]["blockers"]
        }
        self.assertEqual(blockers["non_verified_observations"], 3494)
        self.assertEqual(blockers["missing_source_pages"], 3494)
        self.assertEqual(blockers["semantic_scope_review_required"], 225)
        self.assertEqual(blockers["boundary_not_harmonised"], 494)
        self.assertEqual(blockers["partial_period_coverage"], 10)
        self.assertEqual(blockers["source_rights_not_reviewed"], 1)

    def test_catalog_points_to_versioned_landing_page_and_descriptor(self):
        catalog = json.loads(self.catalog_text)
        self.assertEqual(catalog["schemaVersion"], "release-catalog-v1")
        self.assertEqual(len(catalog["releases"]), 1)
        release = catalog["releases"][0]
        self.assertEqual(release["releaseId"], self.release_id)
        self.assertEqual(release["landingPage"], f"/releases/{self.release_id}/")
        self.assertEqual(
            release["descriptor"], f"/releases/{self.release_id}/release.json"
        )

    def test_public_discovery_surfaces_are_explicit_about_status(self):
        release_page = (REPO_ROOT / "src/pages/releases/[release].astro").read_text()
        downloads_page = (REPO_ROOT / "src/pages/downloads/index.astro").read_text()
        header = (REPO_ROOT / "src/components/Header.astro").read_text()
        sitemap = (REPO_ROOT / "public/sitemap.xml").read_text()

        self.assertIn("Not certified", release_page)
        self.assertIn("Certification blockers", release_page)
        self.assertIn("candidate.landingPage", downloads_page)
        self.assertIn("Not certified", downloads_page)
        self.assertIn('href={`${base}districts/`}', header)
        self.assertIn("Analysis <small>Experimental</small>", header)
        self.assertIn("Ask <small>Experimental</small>", header)
        self.assertIn(f"/releases/{self.release_id}/", sitemap)
        self.assertIn("/districts/", sitemap)


if __name__ == "__main__":
    unittest.main()
