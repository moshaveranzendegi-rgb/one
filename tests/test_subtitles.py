import tempfile
import unittest
from pathlib import Path

from app.services.audio import _word_boundary_from_event, write_srt


class SubtitleTests(unittest.TestCase):
    def test_srt_preserves_persian_text_and_order(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "captions.srt"
            write_srt([(0, 1.2, "سلام دنیا"), (1.3, 2.4, "روز خوبی است")], path)
            content = path.read_text(encoding="utf-8-sig")
            self.assertIn("سلام دنیا", content)
            self.assertIn("00:00:00,000 --> 00:00:01,200", content)
            self.assertIn("2\n00:00:01,300 --> 00:00:02,400", content)

    def test_edge_tts_word_boundary_uses_top_level_fields_and_100ns_ticks(self):
        event = {
            "type": "WordBoundary",
            "offset": 12_000_000,
            "duration": 5_000_000,
            "text": "سلام",
        }
        self.assertEqual(_word_boundary_from_event(event), (1.2, 1.7, "سلام"))

    def test_non_word_event_is_ignored(self):
        self.assertIsNone(_word_boundary_from_event({"type": "audio", "data": b"x"}))

    def test_empty_subtitles_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                write_srt([], Path(d) / "empty.srt")


if __name__ == "__main__":
    unittest.main()
