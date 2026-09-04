import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


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


if __name__ == "__main__":
    unittest.main()
