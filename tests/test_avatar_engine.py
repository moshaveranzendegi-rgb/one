import unittest

from app.services.engine_selection import select_avatar_engine, resolve_engine_mode


class AvatarEngineSelectionTests(unittest.TestCase):
    def test_prefers_omniavatar_when_compatible_gpu_is_ready(self):
        self.assertEqual(select_avatar_engine(True, True), "omniavatar")

    def test_uses_sadtalker_cpu_without_nvidia_gpu(self):
        self.assertEqual(select_avatar_engine(False, True), "sadtalker_cpu")

    def test_returns_none_when_no_engine_is_installed(self):
        self.assertIsNone(select_avatar_engine(False, False))

    def test_does_not_choose_omniavatar_when_gpu_is_unavailable(self):
        self.assertEqual(select_avatar_engine(False, False), None)

    def test_auto_uses_the_available_local_cpu_engine(self):
        self.assertEqual(resolve_engine_mode("auto", "sadtalker_cpu"), "sadtalker_cpu")

    def test_auto_does_not_fall_back_to_cloud_when_local_engine_is_missing(self):
        with self.assertRaises(RuntimeError):
            resolve_engine_mode("auto", None)

    def test_cloud_mode_is_used_only_when_explicitly_requested(self):
        self.assertEqual(resolve_engine_mode("cloud", "sadtalker_cpu"), "cloud")

    def test_cpu_mode_rejects_a_missing_cpu_engine(self):
        with self.assertRaises(RuntimeError):
            resolve_engine_mode("cpu", "none")


if __name__ == "__main__":
    unittest.main()
