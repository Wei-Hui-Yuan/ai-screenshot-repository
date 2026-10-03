import io
import random
import types
from pathlib import Path

import pytest
from PIL import Image, UnidentifiedImageError

from app import images
from app.images import MAX_BYTES, MAX_EDGE, RejectedImage, check_upload, compress, sha256, store

ORIENTATION = 0x0112
CAMERA_MAKE = 0x010F


def encode(image: Image.Image, fmt: str = "PNG", **options: object) -> bytes:
    out = io.BytesIO()
    image.save(out, format=fmt, **options)
    return out.getvalue()


def solid(size: tuple[int, int], fmt: str = "PNG") -> bytes:
    return encode(Image.new("RGB", size, "steelblue"), fmt)


def opened(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def test_output_is_webp() -> None:
    assert opened(compress(solid((300, 200)))).format == "WEBP"


def test_wide_image_is_scaled_to_the_default_limit() -> None:
    out = opened(compress(solid((3000, 2000))))

    assert out.size == (MAX_EDGE, 1067)


def test_tall_phone_screenshot_is_limited_by_height() -> None:
    out = opened(compress(solid((1170, 2532))))

    assert out.height == MAX_EDGE
    assert abs(out.width - 1170 * MAX_EDGE / 2532) <= 1


def test_small_image_is_not_upscaled() -> None:
    assert opened(compress(solid((400, 300)))).size == (400, 300)


def test_max_edge_can_be_lowered() -> None:
    assert max(opened(compress(solid((3000, 2000)), max_edge=1024)).size) == 1024


def test_lower_quality_gives_a_smaller_file() -> None:
    rng = random.Random(0)
    noise = Image.frombytes("RGB", (200, 200), bytes(rng.randrange(256) for _ in range(200 * 200 * 3)))
    data = encode(noise)

    assert len(compress(data, quality=30)) < len(compress(data, quality=90))


def test_exif_is_removed_and_the_rotation_is_applied() -> None:
    exif = Image.Exif()
    exif[ORIENTATION] = 6  # "rotate 90 degrees to display"
    exif[CAMERA_MAKE] = "TestPhone"
    source = encode(Image.new("RGB", (200, 100), "tomato"), "JPEG", exif=exif)
    # Precondition: the input really has EXIF, so this test can fail.
    assert opened(source).getexif().get(ORIENTATION) == 6

    out = opened(compress(source))

    assert len(out.getexif()) == 0
    assert "exif" not in out.info
    assert out.size == (100, 200)


def test_transparent_pixels_become_white_not_black() -> None:
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    image.paste((0, 0, 0, 255), (40, 40, 60, 60))  # opaque black "text"

    out = opened(compress(encode(image))).convert("RGB")

    assert min(out.getpixel((5, 5))) > 240
    assert max(out.getpixel((50, 50))) < 40


def test_palette_png_with_transparency_becomes_white() -> None:
    image = Image.new("P", (50, 50), 0)  # palette index 0 is black
    out = opened(compress(encode(image, transparency=0))).convert("RGB")

    assert min(out.getpixel((10, 10))) > 240


@pytest.mark.parametrize(("mode", "fmt"), [("L", "PNG"), ("CMYK", "JPEG"), ("RGB", "JPEG")])
def test_other_colour_modes_are_accepted(mode: str, fmt: str) -> None:
    out = opened(compress(encode(Image.new(mode, (64, 64)), fmt)))

    assert out.format == "WEBP"
    assert out.mode == "RGB"


def test_16_bit_greyscale_keeps_its_brightness_instead_of_clipping_to_white() -> None:
    mid_grey = Image.new("I;16", (8, 8), 30000)  # of 65535
    assert opened(encode(mid_grey)).mode.startswith("I")  # precondition: it really decodes as 16-bit

    out = opened(compress(encode(mid_grey))).convert("RGB")

    assert 105 <= out.getpixel((4, 4))[0] <= 130  # about 30000 / 256


def test_something_that_is_not_an_image_is_rejected() -> None:
    with pytest.raises(UnidentifiedImageError):
        compress(b"definitely not an image")


def test_a_truncated_image_is_rejected() -> None:
    whole = solid((200, 200))

    with pytest.raises(OSError):  # Pillow says "image file is truncated"
        compress(whole[: len(whole) // 2])


# --- checking an upload (AC-6, hard rule 6) ------------------------------------


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_the_three_allowed_types_are_accepted(fmt: str) -> None:
    check_upload(encode(Image.new("RGB", (40, 40), "teal"), fmt))


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_other_real_image_types_are_refused(fmt: str) -> None:
    with pytest.raises(RejectedImage, match="not PNG, JPEG or WebP"):
        check_upload(encode(Image.new("RGB", (40, 40)), fmt))


def test_the_type_comes_from_the_content_not_the_name_or_a_header() -> None:
    check_upload(encode(Image.new("RGB", (40, 40)), "PNG"))  # accepted whatever it is called
    with pytest.raises(RejectedImage, match="not PNG, JPEG or WebP"):
        check_upload(b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>")
    with pytest.raises(RejectedImage, match="not PNG, JPEG or WebP"):
        check_upload(b"")


def test_a_file_over_ten_megabytes_is_refused_before_anything_else() -> None:
    with pytest.raises(RejectedImage, match="over 10 MB"):
        check_upload(b"\0" * (MAX_BYTES + 1))


def test_a_truncated_upload_is_unreadable() -> None:
    whole = solid((200, 200))

    with pytest.raises(RejectedImage, match="unreadable image"):
        check_upload(whole[:80])


@pytest.mark.parametrize("side", [10_000, 20_000])  # about 100 and 400 million pixels
def test_a_decompression_bomb_is_unreadable(side: int) -> None:
    bomb = encode(Image.new("1", (side, side)), "PNG")  # tiny file, huge when decoded
    assert len(bomb) < MAX_BYTES

    with pytest.raises(RejectedImage, match="unreadable image"):
        check_upload(bomb)


def test_the_hash_is_a_sha256_of_the_bytes() -> None:
    assert sha256(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_a_stored_file_is_written_whole_and_a_failure_leaves_nothing_behind(tmp_path: Path) -> None:
    path = store(solid((50, 50)), "a" * 64, tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == [path.name]  # no temporary file left

    with pytest.raises(OSError):
        store(b"not an image", "b" * 64, tmp_path)

    assert [p.name for p in tmp_path.iterdir()] == [path.name]


def test_a_failed_move_into_place_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(source: object, target: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(images, "os", types.SimpleNamespace(replace=broken))

    with pytest.raises(OSError):
        store(solid((50, 50)), "c" * 64, tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_the_stored_name_is_the_hash_whatever_the_upload_was_called(tmp_path: Path) -> None:
    data = solid((300, 200))
    digest = sha256(data)

    path = store(data, digest, tmp_path)

    assert path == tmp_path / f"{digest}.webp"
    assert opened(path.read_bytes()).format == "WEBP"
    assert [p.name for p in tmp_path.iterdir()] == [f"{digest}.webp"]
