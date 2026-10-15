from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import audio


async def _raise_edge_403(*args, **kwargs):
    raise RuntimeError("403 Invalid response status")


class AudioFallbackTests(unittest.TestCase):
    def test_persian_tts_uses_piper_after_edge_failure_without_gtts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "spoken.mp3"
            with patch("app.services.audio._edge_tts_stream", new=_raise_edge_403):
                with patch("app.services.audio._gtts_fallback") as google_fallback:
                    with patch("app.services.audio._piper_fallback", return_value="fa_IR-mana-medium") as piper_fallback:
                        provider = audio.make_tts("سلام، تست صدا.", "fa", "", target, None, "ffmpeg")
            self.assertIn("piper-fa_IR-mana-medium", provider)
            piper_fallback.assert_called_once()
            google_fallback.assert_not_called()

    def test_persian_tts_uses_piper_even_if_gtts_would_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "spoken.mp3"
            with patch("app.services.audio._edge_tts_stream", new=_raise_edge_403):
                with patch("app.services.audio._gtts_fallback", side_effect=AssertionError("gTTS must not be used for Persian")):
                    with patch("app.services.audio._piper_fallback", return_value="fa_IR-mana-medium") as piper_fallback:
                        provider = audio.make_tts("سلام، تست صدا.", "fa", "", target, None, "ffmpeg")
            self.assertIn("piper-fa_IR-mana-medium", provider)
            piper_fallback.assert_called_once()

    def test_english_tts_falls_back_to_gtts_after_edge_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "spoken.mp3"
            with patch("app.services.audio._edge_tts_stream", new=_raise_edge_403):
                with patch("app.services.audio._gtts_fallback") as fallback:
                    provider = audio.make_tts("Hello, fallback test.", "en", "", target, None, "ffmpeg")
            self.assertIn("gTTS-en", provider)
            self.assertIn("RuntimeError", provider)
            fallback.assert_called_once()

    def test_fallback_subtitles_are_utf8_srt_and_use_media_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            media = folder / "speech.mp3"
            subs = folder / "captions.srt"
            media.write_bytes(b"placeholder")
            with patch("app.services.audio.media_duration", return_value=4.2):
                audio._write_fallback_subtitles(
                    "سلام، این یک آزمایش زیرنویس است. این جمله دوم است.",
                    media,
                    subs,
                    "ffmpeg",
                )
            content = subs.read_text(encoding="utf-8-sig")
            self.assertIn("سلام", content)
            self.assertIn("-->", content)
            self.assertIn("این جمله دوم است.", content)


if __name__ == "__main__":
    unittest.main()
