import unittest

from app.validation import RESOLUTIONS, validate_form


class ValidationTests(unittest.TestCase):
    def _valid(self):
        return {
            "scenario": "سلام",
            "language": "fa",
            "voice": "fa-IR-DilaraNeural",
            "audio_source": "tts",
            "body_mode": "keep",
            "clothing_mode": "current",
            "garments": {},
            "video_ratio": "9:16",
            "video_format": "mp4",
            "output_directory": "",
            "daily_limit": "20",
        }

    def test_presets_have_valid_dimensions(self):
        self.assertEqual(RESOLUTIONS["9:16"], (1080, 1920))
        self.assertEqual(RESOLUTIONS["16:9"], (1920, 1080))
        self.assertEqual(set(RESOLUTIONS), {"9:16", "4:5", "1:1", "16:9", "4:3", "3:4"})

    def test_valid_form(self):
        self.assertEqual(validate_form(self._valid()), [])

    def test_current_clothing_disallows_garment_upload(self):
        form = self._valid()
        form["garments"] = {"upper": {"path": "shirt.png"}}
        self.assertTrue(any("لباس فعلی" in x for x in validate_form(form)))

    def test_one_piece_cannot_combine_with_separate_layers(self):
        form = self._valid()
        form["clothing_mode"] = "custom"
        form["garments"] = {"upper": {"path": "shirt.png"}, "onepiece": {"path": "dress.png"}}
        self.assertTrue(any("یک‌تکه" in x for x in validate_form(form)))

    def test_language_and_voice_pairing(self):
        form = self._valid()
        form["language"] = "ru"
        self.assertTrue(any("زبان" in x for x in validate_form(form)))
        form["voice"] = "ru-RU-SvetlanaNeural"
        self.assertEqual(validate_form(form), [])

    def test_bad_format_rejected(self):
        form = self._valid()
        form["video_format"] = "wmv"
        self.assertTrue(any("فرمت" in x for x in validate_form(form)))

    def test_cloud_engine_mode_is_valid_and_unknown_mode_rejected(self):
        form = self._valid()
        form["engine_mode"] = "cloud"
        self.assertEqual(validate_form(form), [])
        form["engine_mode"] = "magic"
        self.assertTrue(any("مسیر تولید آواتار" in x for x in validate_form(form)))


if __name__ == "__main__":
    unittest.main()
