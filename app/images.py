"""Image handling. Only compress() exists so far: validation, hashing and storage
come in phase 2."""

import io

from PIL import Image, ImageOps

# Starting values from the plan. The phase 1 spike checks them against Gemini's
# tagging quality and locks the final numbers here.
MAX_EDGE = 1600
WEBP_QUALITY = 80


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
