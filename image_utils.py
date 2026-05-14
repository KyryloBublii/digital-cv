"""WebP conversion utility — requires Pillow."""
import os
from pathlib import Path


def convert_to_webp(src: str | os.PathLike, quality: int = 85) -> Path:
    """Convert an image file to WebP and return the output path.

    The output is written alongside the source with a .webp extension.
    Skips conversion if the WebP file already exists and is newer than the source.
    """
    from PIL import Image

    src = Path(src)
    dst = src.with_suffix(".webp")

    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst

    with Image.open(src) as img:
        img.save(dst, "WEBP", quality=quality, method=6)

    return dst


def convert_static_images(static_dir: str | os.PathLike, exts: tuple[str, ...] = (".jpg", ".jpeg", ".png")) -> list[Path]:
    """Walk a static directory and convert all matching images to WebP."""
    converted = []
    for path in Path(static_dir).rglob("*"):
        if path.suffix.lower() in exts:
            converted.append(convert_to_webp(path))
    return converted
