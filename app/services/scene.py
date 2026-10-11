from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageOps


def _fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = size
    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _remove_background(image: Image.Image) -> Image.Image:
    try:
        from rembg import remove
    except ImportError as exc:
        raise RuntimeError("برای قرار دادن آواتار روی عکس محیط، حذف پس‌زمینه لازم است. فایل install_vision.bat را اجرا کن؛ برنامه پس‌زمینه را به‌صورت اشتباه حدس نمی‌زند.") from exc
    result = remove(image.convert("RGBA"))
    if not isinstance(result, Image.Image):
        raise RuntimeError("حذف پس‌زمینه خروجی تصویر معتبری نداد.")
    return result.convert("RGBA")


def composite_scene(avatar_path: Path, environment_path: Path | None, output_path: Path, aspect: str) -> Path:
    if not environment_path:
        # Keep the original picture as reference; do not silently synthesize a background.
        ImageOps.exif_transpose(Image.open(avatar_path)).convert("RGB").save(output_path, quality=95)
        return output_path
    ratios = {
        "9:16": (400, 720),
        "4:5": (576, 720),
        "1:1": (720, 720),
        "16:9": (720, 400),
        "4:3": (720, 540),
        "3:4": (540, 720),
    }
    size = ratios[aspect]
    with Image.open(environment_path) as env:
        background = _fit_cover(env, size)
    with Image.open(avatar_path) as source:
        foreground = _remove_background(ImageOps.exif_transpose(source))
    if foreground.getbbox() is None:
        raise RuntimeError("از عکس آواتار نتوانستم شخص را جدا کنم؛ یک عکس روشن با بدن واضح انتخاب کن.")
    max_h = int(size[1] * 0.92)
    scale = min(max_h / max(1, foreground.height), (size[0] * 0.72) / max(1, foreground.width))
    new_size = (max(1, round(foreground.width * scale)), max(1, round(foreground.height * scale)))
    foreground = foreground.resize(new_size, Image.Resampling.LANCZOS)
    x = (size[0] - foreground.width) // 2
    y = max(0, size[1] - foreground.height - int(size[1] * 0.015))
    background_rgba = background.convert("RGBA")
    background_rgba.alpha_composite(foreground, (x, y))
    background_rgba.convert("RGB").save(output_path, quality=95)
    return output_path
