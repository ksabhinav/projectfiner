import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = (
    "SearchPalette.svelte",
    "FactCard.svelte",
    "FocusOverlay.svelte",
)


class DialogAccessibilityContractTests(unittest.TestCase):
    def test_map_dialogs_manage_focus_without_suppressed_warnings(self):
        sources = {
            name: (REPO_ROOT / "src/components/map" / name).read_text(encoding="utf-8")
            for name in COMPONENTS
        }

        for name, source in sources.items():
            with self.subTest(component=name):
                self.assertNotIn("svelte-ignore", source)
                self.assertIn('role="dialog"', source)
                self.assertIn('aria-modal="true"', source)
                self.assertIn("previouslyFocused", source)
                self.assertRegex(source, r"e\.key\s*!==?\s*['\"]Tab|e\.key\s*===\s*['\"]Tab")

        self.assertRegex(sources["SearchPalette.svelte"], r"<button[^>]+sp-backdrop")
        self.assertRegex(sources["FactCard.svelte"], r"<button[^>]+backdrop")
        self.assertIn('role="combobox"', sources["SearchPalette.svelte"])
        self.assertIn('role="listbox"', sources["SearchPalette.svelte"])
        self.assertIn("aria-activedescendant=", sources["SearchPalette.svelte"])
        self.assertIn("bind:this={closeButton}", sources["FactCard.svelte"])
        self.assertIn("bind:this={closeButton}", sources["FocusOverlay.svelte"])


if __name__ == "__main__":
    unittest.main()
