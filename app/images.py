"""Image handling: check an upload, hash it, compress it, store it."""

import hashlib
import io
import os
import uuid
from pathlib import Path

from PIL import Image, ImageOps

# Locked by the phase 1 spike: tagging at 1600 px WebP q80 matched the original
# files on the synthetic screenshots (see planning/spike-results.md).
MAX_EDGE = 1600
WEBP_QUALITY = 80

MAX_BYTES = 10 * 1024 * 1024
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


class RejectedImage(Exception):
    """An upload we won't store. str() is the fixed message from design.md §6, safe
    to show as-is."""


def check_upload(data: bytes) -> None:
    """Raise RejectedImage unless this is a real PNG, JPEG or WebP of a sane size.

    The type comes from decoding the bytes, never from the file name (rule 6). The
    whole image is decoded, which catches truncated files. Pillow's decompression-bomb
    guard stays on, and its pixel limit is also checked here directly, because
    Pillow only warns between one and two times the limit."""
    if len(data) > MAX_BYTES:
        raise RejectedImage("over 10 MB")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ALLOWED_FORMATS:
                raise RejectedImage("not PNG, JPEG or WebP")
            if Image.MAX_IMAGE_PIXELS and image.width * image.height > Image.MAX_IMAGE_PIXELS:
                raise RejectedImage("unreadable image")
            image.load()
    except RejectedImage:
        raise
    except Image.UnidentifiedImageError as exc:
        raise RejectedImage("not PNG, JPEG or WebP") from exc
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise RejectedImage("unreadable image") from exc


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store(data: bytes, digest: str, folder: Path) -> Path:
    """Write the compressed copy as <sha256>.webp. The uploaded name is never used
    (rule 3). It is written to a temporary file and moved into place, so a reader
    never sees a half-written image."""
    path = folder / f"{digest}.webp"
    temp = folder / f"{digest}.{uuid.uuid4().hex}.tmp"
    try:
        temp.write_bytes(compress(data))
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def compress(data: bytes, max_edge: int = MAX_EDGE, quality: int = WEBP_QUALITY) -> bytes:
    """Re-encode an image as WebP with its longest edge at most max_edge.

    Never upscales. Re-encoding drops EXIF and other metadata, and decoding with
    Pillow raises for anything that isn't a real image. The decompression-bomb
    guard stays at Pillow's default (hard rule 6).
    """
    with Image.open(io.BytesIO(data)) as source:
        image = _flatten(ImageOps.exif_transpose(source))  # rotate first: the tag is dropped
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="WEBP", quality=quality)
    return out.getvalue()


def _flatten(image: Image.Image) -> Image.Image:
    """An RGB copy. Transparent pixels go white: converting directly makes them
    black, which would hide dark text in a transparent PNG. 16-bit greyscale is
    scaled to 8-bit first: converting directly clips it to pure white."""
    if image.mode.startswith("I"):  # "I" and the "I;16" family
        image = image.point(lambda v: v / 256).convert("L")
    has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
    if not has_alpha:
        return image.convert("RGB")
    rgba = image.convert("RGBA")
    page = Image.new("RGB", rgba.size, "white")
    page.paste(rgba, mask=rgba.getchannel("A"))
    return page
