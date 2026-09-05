import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_built_site import validate_site


PAGE = """<!doctype html>
<html lang="en"><head>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-src 'none'; upgrade-insecure-requests">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta name="description" content="Fixture">
<title>Fixture</title>
<link rel="canonical" href="https://projectfiner.com{route}">
<script type="application/ld+json">{{"@type":"WebPage"}}</script>
</head><body><main><h1 id="top">Fixture</h1>{body}</main></body></html>
"""


def write_fixture(root: Path, *, index_body: str = '<a href="/about/#top">About</a>'):
    (root / "about").mkdir(parents=True)
    (root / "index.html").write_text(PAGE.format(route="/", body=index_body))
    (root / "about" / "index.html").write_text(PAGE.format(route="/about/", body=""))
    (root / "sitemap.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://projectfiner.com/</loc></url>
  <url><loc>https://projectfiner.com/about/</loc></url>
  <url><loc>https://projectfiner.com/changelog/</loc></url>
  <url><loc>https://projectfiner.com/corrections/</loc></url>
  <url><loc>https://projectfiner.com/data-dictionary/</loc></url>
  <url><loc>https://projectfiner.com/data-rights/</loc></url>
  <url><loc>https://projectfiner.com/downloads/</loc></url>
  <url><loc>https://projectfiner.com/districts/</loc></url>
  <url><loc>https://projectfiner.com/methodology/</loc></url>
  <url><loc>https://projectfiner.com/privacy/</loc></url>
  <url><loc>https://projectfiner.com/releases/meghalaya-standardized-preview-v1/</loc></url>
</urlset>""")
    for route in (
        "changelog", "corrections", "data-dictionary", "data-rights",
        "downloads", "districts", "methodology", "privacy",
        "releases/meghalaya-standardized-preview-v1",
    ):
        directory = root / route
        directory.mkdir(parents=True)
        (directory / "index.html").write_text(PAGE.format(route=f"/{route}/", body=""))


class BuiltSiteValidatorTests(unittest.TestCase):
    def test_valid_fixture_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root)
            errors, stats = validate_site(root)
            self.assertEqual(errors, [])
            self.assertEqual(stats["pages"], 11)
            self.assertEqual(stats["sitemap_urls"], 11)

    def test_missing_internal_link_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root, index_body='<a href="/missing/">Missing</a>')
            errors, _ = validate_site(root)
            self.assertTrue(any("points to missing" in error for error in errors))

    def test_invalid_metadata_and_accessibility_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(
                root,
                index_body=(
                    '<img src="/about/">'
                    '<input id="query">'
                    '<div id="top"></div>'
                    '<script type="application/ld+json">{bad}</script>'
                ),
            )
            errors, _ = validate_site(root)
            combined = "\n".join(errors)
            self.assertIn("no alt attribute", combined)
            self.assertIn("has no accessible label", combined)
            self.assertIn("duplicate id", combined)
            self.assertIn("invalid JSON-LD", combined)

    def test_missing_browser_security_metadata_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root)
            index = root / "index.html"
            index.write_text(
                index.read_text()
                .replace(
                    '<meta http-equiv="Content-Security-Policy" '
                    'content="default-src \'self\'; object-src \'none\'; '
                    'base-uri \'self\'; form-action \'self\'; '
                    'frame-src \'none\'; upgrade-insecure-requests">\n',
                    "",
                )
                .replace(
                    '<meta name="referrer" '
                    'content="strict-origin-when-cross-origin">\n',
                    "",
                )
            )
            errors, _ = validate_site(root)
            combined = "\n".join(errors)
            self.assertIn("expected one Content Security Policy", combined)
            self.assertIn("expected referrer policy", combined)


if __name__ == "__main__":
    unittest.main()
