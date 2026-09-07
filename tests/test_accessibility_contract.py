import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class AccessibilityContractTests(unittest.TestCase):
    def test_rankings_controls_and_sorting_are_keyboard_accessible(self):
        component = (
            REPO_ROOT / "src/components/analysis/DistrictRankings.svelte"
        ).read_text(encoding="utf-8")

        for control in ("state", "category", "quarter", "metric"):
            with self.subTest(control=control):
                self.assertIn(f'for="ranking-{control}"', component)
                self.assertIn(f'id="ranking-{control}"', component)

        self.assertNotRegex(component, r"<th[^>]+onclick=")
        self.assertEqual(component.count('class="sort-button"'), 3)
        self.assertIn("aria-sort=", component)
        self.assertIn('role="status"', component)
        self.assertIn('role="alert"', component)
        self.assertIn('aria-live="polite"', component)
        self.assertIn("<caption>", component)


if __name__ == "__main__":
    unittest.main()
