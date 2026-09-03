import hashlib
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "db"))

from build_release_manifest import build_manifest, serialise_manifest


class ReleaseManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = build_manifest()
        cls.manifest_path = REPO_ROOT / "public" / "release-manifest.json"

    def test_committed_manifest_is_current_and_content_addressed(self):
        self.assertEqual(
            self.manifest_path.read_text(encoding="utf-8"),
            serialise_manifest(self.manifest),
        )
        payload = dict(self.manifest)
        release_id = payload.pop("releaseId")
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        expected = hashlib.sha256(canonical.encode()).hexdigest()[:12]
        self.assertEqual(release_id, f"finer-{expected}")

    def test_every_download_has_file_integrity_and_explicit_rights_status(self):
        sources = {source["id"]: source for source in self.manifest["sources"]}
        self.assertEqual(self.manifest["projectDataLicense"], None)
        self.assertEqual(self.manifest["rightsReviewStatus"], "not-legally-reviewed")

        datasets = [*self.manifest["states"], *self.manifest["capitalMarkets"]]
        for dataset in datasets:
            self.assertEqual(dataset["qualityTier"], "raw-experimental")
            self.assertEqual(dataset["rightsStatus"], "not-reviewed")
            self.assertIsNone(dataset["license"])
            for source_id in dataset["sourceIds"]:
                self.assertIn(source_id, sources)
                self.assertIsNone(sources[source_id]["license"])
                self.assertEqual(sources[source_id]["rightsStatus"], "not-reviewed")
            for distribution in dataset["distributions"]:
                path = REPO_ROOT / "public" / distribution["path"]
                self.assertTrue(path.exists(), path)
                self.assertEqual(distribution["bytes"], path.stat().st_size)
                self.assertEqual(
                    distribution["sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
                )
                self.assertIsNone(distribution["license"])
                self.assertEqual(distribution["rightsStatus"], "not-reviewed")

    def test_state_and_capital_market_inventory_is_complete(self):
        states = self.manifest["states"]
        self.assertEqual(len(states), 31)
        self.assertEqual(len({state["slug"] for state in states}), 31)
        group_counts = {
            group: sum(state["group"] == group for state in states)
            for group in ("north-east", "other", "ut")
        }
        self.assertEqual(group_counts, {"north-east": 8, "other": 19, "ut": 4})
        self.assertEqual(len(self.manifest["capitalMarkets"]), 4)
        for registry in self.manifest["capitalMarkets"]:
            self.assertFalse(registry["districtMapped"])
            self.assertEqual(registry["geographyLevel"], "location")
            self.assertIsNone(registry["snapshotDate"])

        meghalaya = next(state for state in states if state["slug"] == "meghalaya")
        preview = next(
            item for item in meghalaya["distributions"]
            if item.get("role") == "observations"
        )
        dictionary = next(
            item for item in meghalaya["distributions"]
            if item.get("role") == "indicator-registry"
        )
        self.assertEqual(self.manifest["summary"]["distributionCount"], 68)
        self.assertEqual(preview["rowCount"], 3494)
        self.assertEqual(preview["indicatorCount"], 13)
        self.assertEqual(preview["qualityTier"], "standardized-preview")
        self.assertEqual(preview["certificationStatus"], "not-certified")
        self.assertEqual(dictionary["schemaVersion"], "indicator-registry-v1")

    def test_download_ui_consumes_manifest_and_emits_bom_free_csv(self):
        page = (REPO_ROOT / "src/pages/downloads/index.astro").read_text()
        state_component = (REPO_ROOT / "src/components/StateDownload.svelte").read_text()
        meghalaya_page = (
            REPO_ROOT / "src/pages/slbc-data/meghalaya/download.astro"
        ).read_text()
        download_helper = (REPO_ROOT / "src/lib/download.ts").read_text()
        sitemap = (REPO_ROOT / "public/sitemap.xml").read_text()

        self.assertIn("release-manifest.json", page)
        self.assertNotIn("const neStates = [", page)
        self.assertNotIn("districts × providers", page)
        self.assertIn("data-rights/", page)
        self.assertIn("release-manifest.json", state_component)
        self.assertIn("Standardized preview", state_component)
        self.assertIn("Not certified", state_component)
        self.assertIn("release-manifest.json", meghalaya_page)
        self.assertIn("preview.rowCount", meghalaya_page)
        self.assertNotIn("\\ufeff", state_component)
        self.assertNotIn("\\ufeff", download_helper)
        self.assertIn("https://projectfiner.com/data-rights/", sitemap)


if __name__ == "__main__":
    unittest.main()
