from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VisionPackagingTests(unittest.TestCase):
    def test_windows_bundle_copies_pymatting_metadata(self):
        build_script = (ROOT / "tools" / "build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("'--copy-metadata', 'pymatting'", build_script)

    def test_windows_build_installs_vision_cpu_dependencies(self):
        workflow = (ROOT / ".github" / "workflows" / "build-installers.yml").read_text(encoding="utf-8")
        self.assertIn("-r requirements-vision.txt", workflow)

    def test_background_removal_defaults_to_lightweight_cpu_model(self):
        scene = (ROOT / "app" / "services" / "scene.py").read_text(encoding="utf-8")
        self.assertIn('or "u2netp"', scene)
        self.assertIn('session=_background_session(model_name)', scene)

    def test_runtime_checks_pymatting_distribution_metadata(self):
        runtime = (ROOT / "app" / "services" / "runtime.py").read_text(encoding="utf-8")
        self.assertIn('distribution("pymatting")', runtime)


if __name__ == "__main__":
    unittest.main()
