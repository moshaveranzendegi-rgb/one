from __future__ import annotations
import hashlib
import tempfile
import unittest
from pathlib import Path
from tools.join_parts import join_parts
from tools.split_package import split

class JoinPartsTests(unittest.TestCase):
    def test_split_join_round_trip_and_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sample.zip"
            original = (b"RS-ai" * 30_000) + bytes(range(256))
            source.write_bytes(original)
            split(source, part_size=4096)
            source.unlink()
            joined = join_parts("sample", root)
            self.assertEqual(joined.read_bytes(), original)
            self.assertEqual(hashlib.sha256(joined.read_bytes()).hexdigest(), hashlib.sha256(original).hexdigest())

    def test_missing_part_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sample.zip"
            source.write_bytes(b"x" * 9000)
            parts = split(source, part_size=3000)
            source.unlink()
            parts[1].unlink()
            with self.assertRaisesRegex(ValueError, "Missing part"):
                join_parts("sample", root)

    def test_checksum_mismatch_is_rejected_and_partial_output_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sample.zip"
            source.write_bytes(b"x" * 9000)
            parts = split(source, part_size=3000)
            source.unlink()
            parts[0].write_bytes(b"y" * 3000)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                join_parts("sample", root)
            self.assertFalse((root / "sample.zip.partial").exists())
            self.assertFalse((root / "sample.zip").exists())

if __name__ == "__main__":
    unittest.main()
