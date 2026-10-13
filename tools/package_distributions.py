from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT.parent / "RS-ai-Installers"
MAX_DOWNLOAD_BYTES = 200_000_000
PART_BYTES = 180_000_000
EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "source-bundle", "release-assets", "dist", "build", "dist-packages", "outputs", "data", "models", "pretrained_models",
    ".gradle", "node_modules",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".sqlite", ".sqlite3", ".db"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_files(relative_roots: Iterable[str]) -> list[Path]:
    result: list[Path] = []
    for rel in relative_roots:
        source = ROOT / rel
        if not source.exists():
            raise FileNotFoundError(f"Missing package source: {rel}")
        candidates = [source] if source.is_file() else source.rglob("*")
        for path in candidates:
            if not path.is_file():
                continue
            rel_parts = path.relative_to(ROOT).parts
            if any(part in EXCLUDED_DIRS for part in rel_parts):
                continue
            if path.suffix.lower() in EXCLUDED_SUFFIXES or path.name in {".DS_Store", "Thumbs.db"}:
                continue
            result.append(path)
    return sorted(set(result), key=lambda p: p.relative_to(ROOT).as_posix().lower())


def write_zip(zip_path: Path, files: list[Path]) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as archive:
        for path in files:
            rel = Path("RS-ai") / path.relative_to(ROOT)
            archive.write(path, rel.as_posix())
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Archive validation failed ({zip_path.name}): {bad}")


def remove_old_outputs(out: Path, base: str) -> None:
    for path in out.glob(base + ".part*"):
        if path.is_file() and re.fullmatch(re.escape(base) + r"\.part\d{3,}", path.name):
            path.unlink()
    (out / f"{base}.sha256.txt").unlink(missing_ok=True)
    (out / f"{base}.zip.sha256.txt").unlink(missing_ok=True)
    (out / f"{base}.zip").unlink(missing_ok=True)


def package(out: Path, base: str, roots: list[str]) -> list[Path]:
    remove_old_outputs(out, base)
    zip_path = out / f"{base}.zip"
    files = iter_files(roots)
    write_zip(zip_path, files)
    digest = sha256(zip_path)
    checksum = out / f"{base}.sha256.txt"
    checksum.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii")
    outputs: list[Path]
    if zip_path.stat().st_size >= PART_BYTES:
        outputs = []
        with zip_path.open("rb") as src:
            index = 1
            while True:
                data = src.read(PART_BYTES)
                if not data:
                    break
                part = out / f"{base}.part{index:03d}"
                part.write_bytes(data)
                if part.stat().st_size >= MAX_DOWNLOAD_BYTES:
                    raise RuntimeError(f"Part exceeded size requirement: {part.name}")
                outputs.append(part)
                index += 1
        zip_path.unlink()
    else:
        outputs = [zip_path]
    for p in outputs:
        if p.stat().st_size >= MAX_DOWNLOAD_BYTES:
            raise RuntimeError(f"Download exceeds 200,000,000 bytes: {p.name}")
    print(f"{base}: {len(files)} files; " + ", ".join(f"{p.name}={p.stat().st_size:,} bytes" for p in outputs))
    print(f"  SHA-256 {digest}")
    return outputs + [checksum]


def main() -> None:
    parser = argparse.ArgumentParser(description="Package RS ai installers/source archives below 200 MB per download.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.output.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    windows_roots = [
        "app", "web", "tools", "tests", "requirements.txt", "requirements-vision.txt", "requirements-captions.txt",
        "INSTALL_RS-ai.bat", "BUILD_EXE_WINDOWS.bat", "PACKAGE_EXE_WINDOWS.bat", "RUN_RS-ai.bat", "RUN_RS-ai_LAN.bat", "RUN_RS-ai_Portable.bat",
        "JOIN_PARTS.bat", "JOINER_README_FA.txt", "install_windows.bat", "install_tts.bat", "install_vision.bat",
        "install_captions.bat", "README.md", "START_HERE_FA.md", "INSTALLER_NOTES_FA.md", "CPU_ENGINE_GUIDE_FA.md", "STATUS.md", "CHANGELOG.md",
        "run.py", ".gitignore",
    ]
    android_roots = ["android", "INSTALLER_NOTES_FA.md", "README.md"]
    joiner_roots = ["JOIN_PARTS.bat", "JOINER_README_FA.txt", "tools/JOIN_PARTS.ps1", "tools/split_package.py", "tools/join_parts.py", "tests/test_join_parts.py", "tests/test_split_package.py"]
    all_roots = [p.name for p in ROOT.iterdir() if p.name not in EXCLUDED_DIRS and p.name not in {"RS-ai-Installers"}]

    created: list[Path] = []
    created += package(out, "RS-ai-Windows-Setup", windows_roots)
    created += package(out, "RS-ai-Android-Studio-Source", android_roots)
    created += package(out, "RS-ai-Part-Joiner", joiner_roots)
    created += package(out, "RS-ai-Complete-Source", all_roots)
    created += package(out, "RS-ai-source", all_roots)

    print(f"\nOutput: {out}")
    print("All downloadable archives/parts were size-checked and ZIP files were integrity-tested.")


if __name__ == "__main__":
    main()
