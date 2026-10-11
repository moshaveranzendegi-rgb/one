from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

PART_RE = re.compile(r"^(?P<base>.+)\.part(?P<number>\d{3,})$")
MAX_PART_BYTES = 200_000_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def join_parts(base: str, directory: Path = Path.cwd()) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", base):
        raise ValueError("Base name may contain only letters, digits, dot, underscore and hyphen.")
    found: list[tuple[int, Path]] = []
    for path in directory.iterdir():
        match = PART_RE.fullmatch(path.name)
        if match and match.group("base") == base and path.is_file():
            found.append((int(match.group("number")), path))
    found.sort()
    if not found:
        raise FileNotFoundError(f"No parts found: {base}.part001")
    for index, (number, path) in enumerate(found, start=1):
        if number != index:
            raise ValueError(f"Missing part {index:03d}; all parts must be in one folder.")
        if path.stat().st_size <= 0 or path.stat().st_size >= MAX_PART_BYTES:
            raise ValueError(f"Part size invalid: {path.name}")

    checksum_file = directory / f"{base}.sha256.txt"
    if not checksum_file.is_file():
        raise FileNotFoundError(f"Required checksum file is missing: {checksum_file.name}")
    match = re.search(r"\b([a-fA-F0-9]{64})\b", checksum_file.read_text(encoding="ascii", errors="strict"))
    if not match:
        raise ValueError("Checksum file does not contain a valid SHA-256 value.")
    expected = match.group(1).lower()
    output = directory / f"{base}.zip"
    temporary = directory / f"{base}.zip.partial"
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("wb") as out:
            for _, part in found:
                with part.open("rb") as stream:
                    while block := stream.read(1024 * 1024):
                        out.write(block)
        actual = sha256(temporary)
        if actual != expected:
            raise ValueError(f"SHA-256 mismatch: expected {expected}, got {actual}.")
        temporary.replace(output)
        return output
    except Exception:
        temporary.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely reassemble RS ai installer parts and verify SHA-256.")
    parser.add_argument("base", help="Base filename without .part001 or .zip")
    parser.add_argument("--directory", type=Path, default=Path.cwd())
    args = parser.parse_args()
    output = join_parts(args.base, args.directory.resolve())
    print(f"Reassembled and verified: {output}")
    print(f"SHA-256: {sha256(output)}")


if __name__ == "__main__":
    main()
