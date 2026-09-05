import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def version_tuple(version):
    return tuple(int(part) for part in version.split("-")[0].split("."))


class DependencyContractTests(unittest.TestCase):
    def test_unmaintained_xlsx_package_is_not_shipped(self):
        package = json.loads((REPO_ROOT / "package.json").read_text())
        lock = json.loads((REPO_ROOT / "package-lock.json").read_text())

        self.assertNotIn("xlsx", package.get("dependencies", {}))
        self.assertNotIn("node_modules/xlsx", lock["packages"])

        runtime_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (REPO_ROOT / "src").rglob("*")
            if path.suffix in {".astro", ".js", ".svelte", ".ts"}
        )
        self.assertNotIn("import('xlsx')", runtime_source)
        self.assertNotIn('import("xlsx")', runtime_source)

    def test_framework_packages_stay_beyond_known_vulnerable_releases(self):
        package = json.loads((REPO_ROOT / "package.json").read_text())
        lock = json.loads((REPO_ROOT / "package-lock.json").read_text())

        expected_floors = {
            "astro": "7.3.1",
            "@astrojs/svelte": "9.0.1",
            "svelte": "5.57.0",
            "vite": "8.2.2",
        }
        declared_dependencies = package["dependencies"]

        for dependency in ("astro", "@astrojs/svelte", "svelte"):
            with self.subTest(dependency=dependency):
                declared = declared_dependencies[dependency].lstrip("^~>=< ")
                self.assertGreaterEqual(
                    version_tuple(declared), version_tuple(expected_floors[dependency])
                )

        for dependency, minimum in expected_floors.items():
            with self.subTest(locked_dependency=dependency):
                locked = lock["packages"][f"node_modules/{dependency}"]["version"]
                self.assertGreaterEqual(version_tuple(locked), version_tuple(minimum))

    def test_browser_libraries_are_self_hosted_or_integrity_pinned(self):
        browser_pages = "\n".join(
            path.read_text(encoding="utf-8")
            for root in (REPO_ROOT / "src", REPO_ROOT / "public")
            for path in root.rglob("*")
            if path.suffix in {".astro", ".html", ".svelte"}
        )

        self.assertNotIn("https://cdn.plot.ly/", browser_pages)
        self.assertIn('src="/vendor/plotly.min.js"', browser_pages)

        homepage = (REPO_ROOT / "src/pages/index.astro").read_text(encoding="utf-8")
        self.assertIn(
            'integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="',
            homepage,
        )
        self.assertIn(
            'integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="',
            homepage,
        )


if __name__ == "__main__":
    unittest.main()
