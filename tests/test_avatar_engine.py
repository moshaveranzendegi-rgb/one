import unittest

from app.services.engine_selection import select_avatar_engine


class AvatarEngineSelectionTests(unittest.TestCase):
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
