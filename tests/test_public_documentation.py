import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PublicDocumentationTests(unittest.TestCase):
    REQUIRED_DOCUMENTS = {
        "README.md",
        "LICENSE",
        "CITATION.cff",
        "METHODOLOGY.md",
        "DATA_DICTIONARY.md",
        "CORRECTIONS.md",
        "PRIVACY.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
    }

    def test_required_release_documents_are_present(self):
        for relative in self.REQUIRED_DOCUMENTS:
            path = REPO_ROOT / relative
            self.assertTrue(path.is_file(), relative)
            self.assertGreater(len(path.read_text(encoding="utf-8").strip()), 100)

    def test_local_markdown_links_resolve(self):
        documents = [
            REPO_ROOT / name
            for name in self.REQUIRED_DOCUMENTS
            if name.endswith(".md")
        ]
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                relative = target.split("#", 1)[0]
                self.assertTrue(
                    (document.parent / relative).exists(),
                    f"broken link {target!r} in {document.name}",
                )

    def test_no_unsupported_project_or_data_licence_is_claimed(self):
        package = json.loads((REPO_ROOT / "package.json").read_text())
        manifest = json.loads(
            (REPO_ROOT / "public/release-manifest.json").read_text()
        )
        licence = (REPO_ROOT / "LICENSE").read_text()
        about = (REPO_ROOT / "src/pages/about/index.astro").read_text()

        self.assertEqual(package["license"], "UNLICENSED")
        self.assertIsNone(manifest["projectDataLicense"])
        self.assertIn("No licence is currently granted", licence)
        self.assertNotIn("Project FINER is open source", about)
        self.assertNotIn("All data is freely downloadable", about)
        self.assertNotIn("clean, structured datasets", about)
        self.assertNotIn("License: Public information", about)

    def test_about_coverage_and_footer_use_release_metadata(self):
        about = (REPO_ROOT / "src/pages/about/index.astro").read_text()
        footer = (REPO_ROOT / "src/components/Footer.astro").read_text()
        downloads = (REPO_ROOT / "src/pages/downloads/index.astro").read_text()

        self.assertIn("release-manifest.json", about)
        self.assertIn("releaseManifest.summary.stateCount", about)
        self.assertIn("releaseManifest.summary.distributionCount", about)
        self.assertIn("releaseManifest.releaseId", footer)
        self.assertIn("<Footer />", downloads)

    def test_public_document_routes_and_download_links_resolve(self):
        route_names = {
            "methodology",
            "data-dictionary",
            "corrections",
            "privacy",
            "changelog",
        }
        footer = (REPO_ROOT / "src/components/Footer.astro").read_text()
        state_download = (
            REPO_ROOT / "src/components/StateDownload.svelte"
        ).read_text()
        sitemap = (REPO_ROOT / "public/sitemap.xml").read_text()

        for route in route_names:
            self.assertTrue((REPO_ROOT / f"src/pages/{route}/index.astro").is_file())
            self.assertIn(f"{route}/", footer)
            self.assertIn(f"https://projectfiner.com/{route}/", sitemap)
        for route in ("methodology", "data-dictionary", "corrections"):
            self.assertIn(f"{route}/", state_download)

    def test_correction_intake_and_tier_language_are_explicit(self):
        issue_template = (
            REPO_ROOT / ".github/ISSUE_TEMPLATE/data-correction.yml"
        ).read_text()
        methodology = (REPO_ROOT / "METHODOLOGY.md").read_text()
        rights = (REPO_ROOT / "src/pages/data-rights/index.astro").read_text()

        self.assertIn("Source evidence", issue_template)
        self.assertIn("No current FINER distribution is Gold or certified", methodology)
        self.assertIn("standardized preview", rights)
        self.assertIn("not certified analysis-ready data", rights)


if __name__ == "__main__":
    unittest.main()
