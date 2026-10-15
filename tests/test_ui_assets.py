from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestUiAssets(unittest.TestCase):
    def test_mobile_vertical_scroll_is_explicit(self):
        css = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("overflow-y:auto", css)
        self.assertIn("touch-action:pan-y", css)

    def test_local_engine_is_default_and_cloud_handoff_is_explicit(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('option value="auto" selected', html)
        self.assertIn('option value="cloud"', html)
        self.assertNotIn('option value="cloud" selected', html)
        self.assertIn('id="cloudActionPanel"', html)
        self.assertIn("limitedBodyMode", js)
        self.assertIn("awaiting_cloud", js)


if __name__ == "__main__":
    unittest.main()
