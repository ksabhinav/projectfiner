import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MapToolbarAccessibilityContractTests(unittest.TestCase):
    def test_live_map_toolbar_uses_native_controls_and_valid_popups(self):
        strip = (REPO_ROOT / "src/components/map/IndicatorStrip.svelte").read_text(
            encoding="utf-8"
        )
        picker = (REPO_ROOT / "src/components/map/IndicatorPicker.svelte").read_text(
            encoding="utf-8"
        )

        self.assertIn('<button class="search" type="button"', strip)
        self.assertNotIn('<span class="search" role="button"', strip)
        self.assertIn('id="scope-picker"', strip)
        self.assertIn('role="listbox"', strip)
        self.assertIn('role="option"', strip)
        self.assertIn("handleScopeKeydown", strip)
        self.assertIn("closeCell", strip)

        self.assertIn('role="dialog"', picker)
        self.assertIn('class="list" role="listbox"', picker)
        self.assertIn('aria-pressed=', picker)
        self.assertIn("handleListKeydown", picker)
        self.assertIn("ArrowDown", picker)
        self.assertIn("Home", picker)
        self.assertIn("End", picker)


if __name__ == "__main__":
    unittest.main()
