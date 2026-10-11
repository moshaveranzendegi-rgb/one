from __future__ import annotations
import hashlib
import tempfile
import unittest
from pathlib import Path
from tools import split_package

class SplitPackageTests(unittest.TestCase):
    def test_split_parts_are_sequential_and_reassemble_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = bytes(range(256)) * 51
            original = root / 'demo.zip'
            original.write_bytes(payload)
            parts = split_package.split(original, part_size=1024)
            self.assertGreater(len(parts), 1)
            self.assertEqual([p.name for p in parts], [f'demo.part{i:03d}' for i in range(1, len(parts) + 1)])
            self.assertTrue(all(p.stat().st_size < 200_000_000 for p in parts))
            recovered = b''.join(p.read_bytes() for p in parts)
            self.assertEqual(recovered, payload)
            sidecar = root / 'demo.sha256.txt'
            self.assertIn(hashlib.sha256(payload).hexdigest(), sidecar.read_text())

    def test_reject_part_limit_of_200mb_or_more(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / 'demo.zip'
            original.write_bytes(b'a')
            with self.assertRaises(ValueError):
                split_package.split(original, part_size=200_000_000)

if __name__ == '__main__':
    unittest.main()
