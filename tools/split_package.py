from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

PART_SIZE = 180_000_000  # safely below a 200 MB download limit


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def split(path: Path, part_size: int = PART_SIZE) -> list[Path]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if part_size <= 0 or part_size >= 200_000_000:
        raise ValueError("Part size must be positive and below 200,000,000 bytes.")
    part_prefix = f"{path.stem}.part"
    for stale in path.parent.glob(part_prefix + "*"):
        if stale.is_file() and stale.name[len(part_prefix):].isdigit():
            stale.unlink()
    hash_path = path.with_name(f"{path.stem}.sha256.txt")
    outputs: list[Path] = []
    with path.open("rb") as source:
        number = 1
        while True:
            data = source.read(part_size)
            if not data:
                break
            output = path.with_name(f"{path.stem}.part{number:03d}")
            output.write_bytes(data)
            outputs.append(output)
            number += 1
    hash_path.write_text(f"{sha256(path)}  {path.name}\n", encoding="ascii")
    print(f"{path.name}: {len(outputs)} part(s), SHA-256={sha256(path)}")
    for output in outputs:
        if output.stat().st_size >= 200_000_000:
            raise RuntimeError(f"Part exceeds 200 MB: {output}")
        print(f"  {output.name}: {output.stat().st_size:,} bytes")
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split an installer archive into linked parts under 200 MB each.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--part-size", type=int, default=PART_SIZE)
    args = parser.parse_args()
    split(args.archive, args.part_size)
