import unittest

from app.services.engine_selection import select_avatar_engine
from app.pipeline import cpu_render_guard


class AvatarEngineSelectionTests(unittest.TestCase):
    def test_long_cpu_render_requires_explicit_opt_in(self):
        message = cpu_render_guard("sadtalker_cpu", 30.0, False, 5.0)
        self.assertIsNotNone(message)
        self.assertIn("۳۸ دقیقه", message)

    def test_short_cpu_preview_is_allowed(self):
        self.assertIsNone(cpu_render_guard("sadtalker_cpu", 5.0, False, 5.0))

    def test_long_cpu_render_can_be_explicitly_allowed(self):
        self.assertIsNone(cpu_render_guard("sadtalker_cpu", 30.0, True, 5.0))

    def test_gpu_engine_is_not_subject_to_cpu_preview_guard(self):
        self.assertIsNone(cpu_render_guard("omniavatar", 180.0, False, 5.0))

    def test_prefers_omniavatar_when_compatible_gpu_is_ready(self):
        self.assertEqual(select_avatar_engine(True, True), "omniavatar")

    def test_uses_sadtalker_cpu_without_nvidia_gpu(self):
        self.assertEqual(select_avatar_engine(False, True), "sadtalker_cpu")

    def test_returns_none_when_no_engine_is_installed(self):
        self.assertIsNone(select_avatar_engine(False, False))

    def test_does_not_choose_omniavatar_when_gpu_is_unavailable(self):
        self.assertEqual(select_avatar_engine(False, False), None)


if __name__ == "__main__":
    unittest.main()
