"""Photo-like fake phone screenshots for demos: each is a picture drawn with Pillow
(no real photos, no real people) inside a screenshot of a made-up social app.

    python -m eval.make_demo_images          # writes eval/demo/

The pictures are procedural, so they only look like photos at a glance. Each post
also carries the tags a good tagger would give it, which the demo seeding script
uses to fill the library without calling Gemini. Everything here is fictional."""

import argparse
import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H, PHOTO = 1170, 2532, 1170
Size = tuple[int, int]
Colour = tuple[int, int, int]


# --- drawing helpers -------------------------------------------------------------


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def vgrad(size: Size, top: Colour, bottom: Colour) -> Image.Image:
    mask = Image.linear_gradient("L").resize(size)  # black at the top, white at the bottom
    return Image.composite(Image.new("RGB", size, bottom), Image.new("RGB", size, top), mask)


def grain(img: Image.Image, rng: random.Random, strength: float = 0.05) -> Image.Image:
    noise = Image.frombytes("L", img.size, rng.randbytes(img.width * img.height)).convert("RGB")
    return Image.blend(img, noise, strength)


def texture(size: Size, rng: random.Random) -> Image.Image:
    """Organic, cloud-like noise: random cells at several scales, smoothed and summed."""
    total = Image.new("L", size, 0)
    for cells, weight in ((6, 0.45), (24, 0.3), (96, 0.25)):
        small = Image.frombytes("L", (cells, cells), rng.randbytes(cells * cells))
        total = ImageChops.add(total, small.resize(size, Image.Resampling.BICUBIC).point(lambda v, w=weight: int(v * w)))
    return total


def vignette(img: Image.Image, strength: float) -> Image.Image:
    mask = Image.radial_gradient("L").resize(img.size).filter(ImageFilter.GaussianBlur(30))  # dark centre, light edges
    return Image.composite(img.point(lambda v: int(v * (1 - strength))), img, mask)


def finish(img: Image.Image, rng: random.Random, blur: float = 1.2, tex: float = 0.35, vig: float = 0.4, bloom: float = 0.3, noise: float = 0.05) -> Image.Image:
    """What makes a flat drawing read as a photo: soft focus, mottled texture, lit
    highlights that bleed, darker corners and sensor grain."""
    img = img.filter(ImageFilter.GaussianBlur(blur))
    img = Image.blend(img, ImageChops.overlay(img, texture(img.size, rng).convert("RGB")), tex)
    bright = img.point(lambda v: min(255, max(0, v - 185) * 4)).filter(ImageFilter.GaussianBlur(26))
    img = ImageChops.add(img, bright.point(lambda v: int(v * bloom)))
    return grain(vignette(img, vig), rng, noise)


def glow(img: Image.Image, centre: tuple[int, int], radius: int, colour: Colour, blur: int, amount: float = 0.8) -> Image.Image:
    layer = Image.new("RGB", img.size, (0, 0, 0))
    ImageDraw.Draw(layer).ellipse((centre[0] - radius, centre[1] - radius, centre[0] + radius, centre[1] + radius), fill=colour)
    layer = layer.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * amount))
    return ImageChops.add(img, layer)


def jitter(rng: random.Random, colour: Colour, amount: int = 14) -> Colour:
    return tuple(max(0, min(255, c + rng.randint(-amount, amount))) for c in colour)  # type: ignore[return-value]


# --- the pictures ----------------------------------------------------------------


def sunset_skyline(rng: random.Random) -> Image.Image:
    img = glow(vgrad((PHOTO, PHOTO), (58, 44, 112), (255, 150, 72)), (585, 650), 240, (255, 190, 110), 90)
    d = ImageDraw.Draw(img)
    d.ellipse((475, 540, 695, 760), fill=(255, 238, 190))
    for colour, base, lo, hi, windows in (((120, 78, 120), 760, 80, 240, False), ((58, 40, 78), 830, 120, 340, False), ((22, 18, 36), 900, 160, 420, True)):
        x = -20
        while x < PHOTO:
            w, h = rng.randint(50, 130), rng.randint(lo, hi)
            d.rectangle((x, base - h, x + w, 990), fill=colour)
            if windows:
                for wy in range(base - h + 24, 980, 36):
                    for wx in range(x + 10, x + w - 14, 26):
                        if rng.random() < 0.28:
                            d.rectangle((wx, wy, wx + 10, wy + 14), fill=(255, 210, 120))
            x += w - 6
    water = vgrad((PHOTO, 190), (46, 40, 86), (14, 14, 34))
    img.paste(water, (0, 980))
    for _ in range(16):  # the sun on the water
        y = rng.randint(1000, 1160)
        ImageDraw.Draw(img).line((585 - rng.randint(20, 140), y, 585 + rng.randint(20, 140), y), fill=(255, 190, 120), width=4)
    return finish(img, rng, blur=1.3)


def ramen_bowl(rng: random.Random) -> Image.Image:
    img = vgrad((PHOTO, PHOTO), (132, 92, 58), (96, 62, 38))
    d = ImageDraw.Draw(img)
    for y in range(0, PHOTO, 9):  # wood grain
        d.line((0, y, PHOTO, y + rng.randint(-5, 5)), fill=jitter(rng, (112, 76, 48), 10), width=rng.randint(1, 3))
    shadow = Image.new("RGB", img.size, (0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((115, 135, 1075, 1095), fill=(120, 120, 120))
    img = ImageChops.subtract(img, shadow.filter(ImageFilter.GaussianBlur(30)).point(lambda v: int(v * 0.5)))
    d = ImageDraw.Draw(img)
    cx = cy = 585
    d.ellipse((cx - 470, cy - 470, cx + 470, cy + 470), fill=(238, 236, 230))
    d.ellipse((cx - 430, cy - 430, cx + 430, cy + 430), fill=(205, 60, 50))
    d.ellipse((cx - 405, cy - 405, cx + 405, cy + 405), fill=(196, 128, 62))
    for _ in range(46):  # noodles
        a, r, pts = rng.uniform(0, math.tau), rng.randint(40, 330), []
        for t in range(0, 90, 6):
            ang = a + t / 40
            pts.append((cx + (r + 12 * math.sin(t / 5)) * math.cos(ang) * 0.9, cy + (r + 12 * math.sin(t / 5)) * math.sin(ang) * 0.9))
        d.line(pts, fill=jitter(rng, (240, 214, 140), 12), width=13, joint="curve")
    for ex, ey in ((455, 450), (640, 410)):  # soft-boiled egg halves
        d.ellipse((ex - 85, ey - 70, ex + 85, ey + 70), fill=(250, 246, 238))
        d.ellipse((ex - 42, ey - 36, ex + 42, ey + 36), fill=(244, 160, 40))
    img = glow(img, (470, 420), 150, (255, 205, 130), 80, 0.45)  # light on the broth
    d = ImageDraw.Draw(img)
    for px, py in ((690, 640), (560, 690), (760, 520)):  # chashu slices
        d.ellipse((px - 78, py - 58, px + 78, py + 58), fill=(214, 152, 124))
        d.ellipse((px - 50, py - 36, px + 50, py + 36), outline=(176, 108, 84), width=7)
    d.rectangle((785, 330, 900, 560), fill=(24, 54, 36))  # nori
    for _ in range(70):
        sx, sy = rng.randint(330, 860), rng.randint(330, 860)
        if (sx - cx) ** 2 + (sy - cy) ** 2 < 330**2:
            d.ellipse((sx - 9, sy - 9, sx + 9, sy + 9), fill=(110, 170, 60))
    for off in (0, 38):  # chopsticks
        d.polygon([(700 + off, 90), (722 + off, 90), (950 + off, 700), (930 + off, 706)], fill=(80, 46, 28))
    return finish(img, rng, blur=1.4)


def mountain_lake(rng: random.Random) -> Image.Image:
    img = vgrad((PHOTO, PHOTO), (118, 170, 226), (226, 238, 246))
    d = ImageDraw.Draw(img)
    for colour, base, peak in (((132, 150, 178), 640, 330), ((84, 104, 128), 690, 440), ((40, 74, 62), 760, 560)):
        pts, x = [(0, 760)], 0
        while x <= PHOTO:
            pts.append((x, base - rng.randint(0, peak - 250) - (peak - 250) * math.sin(x / 260 + base) ** 2 // 2))
            x += rng.randint(60, 120)
        d.polygon(pts + [(PHOTO, 760)], fill=colour)
    for px in range(60, PHOTO, 70):  # pines along the shore
        h = rng.randint(70, 150)
        d.polygon([(px, 760 - h), (px - 26, 770), (px + 26, 770)], fill=(18, 52, 40))
    top = img.crop((0, 380, PHOTO, 770))
    lake = vgrad((PHOTO, 400), (74, 128, 158), (30, 76, 108))
    reflection = top.transpose(Image.Transpose.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(4))
    lake.paste(Image.blend(lake.crop((0, 0, PHOTO, 390)), reflection, 0.55), (0, 0))
    img.paste(lake, (0, 770))
    for _ in range(40):  # ripples
        y = rng.randint(790, 1150)
        ImageDraw.Draw(img).line((rng.randint(0, 900), y, rng.randint(100, 1170), y), fill=(190, 220, 235), width=2)
    return finish(img, rng, blur=1.1)


def beach_day(rng: random.Random) -> Image.Image:
    img = vgrad((PHOTO, PHOTO), (96, 176, 236), (206, 232, 250))
    clouds = Image.new("RGB", img.size, (0, 0, 0))
    cd = ImageDraw.Draw(clouds)
    for _ in range(14):
        x, y = rng.randint(0, 1000), rng.randint(60, 360)
        cd.ellipse((x, y, x + rng.randint(160, 340), y + rng.randint(40, 90)), fill=(255, 255, 255))
    img = ImageChops.add(img, clouds.filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * 0.8)))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 560, PHOTO, 740), fill=(38, 150, 192))
    d.rectangle((0, 560, PHOTO, 600), fill=(92, 190, 212))
    for i in range(7):  # wave lines
        y = 640 + i * 16
        d.line([(x, y + 6 * math.sin(x / 40 + i)) for x in range(0, PHOTO, 20)], fill=(236, 250, 252), width=3)
    sand = vgrad((PHOTO, 430), (238, 222, 178), (214, 188, 138))
    img.paste(sand, (0, 740))
    d.polygon([(260, 1170), (330, 760), (352, 760), (300, 1170)], fill=(120, 84, 52))  # palm
    for ang in (-150, -110, -70, -30, 10, 40):
        ex, ey = 342 + 230 * math.cos(math.radians(ang)), 760 + 150 * math.sin(math.radians(ang))
        d.polygon([(342, 756), (ex, ey - 40), (ex + 10, ey + 10)], fill=(40, 130, 64))
    d.polygon([(820, 880), (1060, 880), (940, 760)], fill=(222, 70, 60))  # parasol
    d.rectangle((936, 760, 944, 1100), fill=(230, 230, 230))
    return finish(img, rng, blur=1.1)


def coffee_flatlay(rng: random.Random) -> Image.Image:
    img = vgrad((PHOTO, PHOTO), (238, 236, 232), (222, 218, 212))
    d = ImageDraw.Draw(img)
    for _ in range(30):  # marble veins
        x, y = rng.randint(0, PHOTO), rng.randint(0, PHOTO)
        d.line([(x, y), (x + rng.randint(-200, 200), y + rng.randint(-200, 200))], fill=(190, 188, 184), width=rng.randint(1, 3))
    img = img.filter(ImageFilter.GaussianBlur(2))
    shadow = Image.new("RGB", img.size, (0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((180, 250, 800, 870), fill=(150, 150, 150))
    sd.ellipse((630, 600, 1010, 880), fill=(150, 150, 150))
    img = ImageChops.subtract(img, shadow.filter(ImageFilter.GaussianBlur(24)).point(lambda v: int(v * 0.4)))
    d = ImageDraw.Draw(img)
    d.rectangle((960, 40, 1170, 380), fill=(34, 36, 40))  # a laptop corner
    d.ellipse((150, 240, 770, 860), fill=(250, 250, 248))  # saucer
    d.ellipse((220, 300, 700, 780), fill=(244, 244, 242), outline=(220, 220, 216), width=5)
    d.ellipse((260, 340, 660, 740), fill=(112, 72, 46))
    d.ellipse((290, 370, 630, 710), fill=(226, 198, 164))  # milk
    for i in range(5):  # latte art
        d.ellipse((450 - 28 * (i + 1), 480 - 12 * (i + 1) + 40, 450 + 28 * (i + 1), 560 + 12 * (i + 1)), outline=(112, 72, 46), width=6)
    d.arc((730, 450, 880, 600), 200, 340, fill=(220, 220, 216), width=14)  # handle
    d.ellipse((680, 640, 1010, 900), fill=(214, 152, 72))  # croissant
    for k in range(6):
        d.arc((690 + k * 40, 650, 790 + k * 40, 890), 100, 260, fill=(166, 108, 44), width=7)
    return finish(img, rng, blur=1.2, noise=0.04)


def neon_bokeh(rng: random.Random) -> Image.Image:
    img = vgrad((PHOTO, PHOTO), (12, 10, 30), (40, 14, 48))
    layer = Image.new("RGB", img.size, (0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(90):
        x, y, r = rng.randint(0, PHOTO), rng.randint(100, PHOTO), rng.randint(24, 130)
        colour = rng.choice(((255, 40, 150), (40, 200, 255), (255, 170, 40), (150, 80, 255), (60, 255, 170)))
        ld.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(c * rng.uniform(0.35, 0.8)) for c in colour))
    layer = layer.filter(ImageFilter.GaussianBlur(7))
    img = ImageChops.add(img, layer)
    d = ImageDraw.Draw(img)
    d.rectangle((760, 0, 790, PHOTO), fill=(255, 90, 200))  # a neon tube
    img = ImageChops.add(img, img.crop((0, 0, PHOTO, PHOTO)).filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * 0.4)))
    return finish(img, rng, blur=0.6, noise=0.07, bloom=0.5)


def autumn_temple(rng: random.Random) -> Image.Image:
    img = vgrad((PHOTO, PHOTO), (206, 224, 236), (232, 236, 230))
    d = ImageDraw.Draw(img)
    d.polygon([(0, 700), (250, 560), (520, 650), (800, 520), (1170, 640), (1170, 800), (0, 800)], fill=(150, 170, 160))
    d.polygon([(250, 820), (585, 640), (920, 820)], fill=(46, 38, 38))  # temple roof
    d.rectangle((300, 820, 870, 1000), fill=(156, 112, 84))
    for px in range(330, 870, 110):
        d.rectangle((px, 820, px + 22, 1000), fill=(176, 40, 36))
    d.rectangle((0, 1000, PHOTO, PHOTO), fill=(188, 172, 150))  # stone path
    img = img.filter(ImageFilter.GaussianBlur(5))  # the temple is far away, so soft
    reds = ((196, 40, 28), (222, 90, 30), (170, 30, 40), (232, 150, 40), (150, 24, 32))
    canopy = img.convert("RGBA")
    # Foliage in three depth layers: big and very blurred at the back, small and sharp in front.
    for count, rmin, rmax, blur, shade in ((900, 34, 78, 9, 0.62), (1500, 14, 36, 4, 0.8), (2200, 5, 16, 1.2, 1.0)):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for _ in range(count):
            x, y = rng.randint(-40, PHOTO + 40), int(abs(rng.gauss(110, 190)))
            r = rng.randint(rmin, rmax)
            base = tuple(int(c * shade) for c in jitter(rng, rng.choice(reds), 24))
            ld.ellipse((x - r, y - r // 2, x + r, y + r // 2), fill=base + (rng.randint(150, 235),))  # leaves are flat ovals
        canopy = Image.alpha_composite(canopy, layer.filter(ImageFilter.GaussianBlur(blur)))
    ground = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(ground)
    for _ in range(420):  # fallen leaves on the path
        x, y, r = rng.randint(0, PHOTO), rng.randint(1000, 1180), rng.randint(5, 16)
        gd.ellipse((x - r, y - r // 2, x + r, y + r // 2), fill=jitter(rng, rng.choice(reds), 20) + (225,))
    img = Image.alpha_composite(canopy, ground.filter(ImageFilter.GaussianBlur(1.6))).convert("RGB")
    return finish(img, rng, blur=0.7, tex=0.45)


def pasta_plate(rng: random.Random) -> Image.Image:
    img = vgrad((PHOTO, PHOTO), (100, 68, 44), (74, 48, 32))
    d = ImageDraw.Draw(img)
    for y in range(0, PHOTO, 11):
        d.line((0, y, PHOTO, y + rng.randint(-4, 4)), fill=jitter(rng, (88, 58, 38), 8), width=2)
    shadow = Image.new("RGB", img.size, (0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((110, 140, 1070, 1100), fill=(110, 110, 110))
    img = ImageChops.subtract(img, shadow.filter(ImageFilter.GaussianBlur(28)).point(lambda v: int(v * 0.5)))
    d = ImageDraw.Draw(img)
    cx = cy = 585
    d.ellipse((cx - 460, cy - 460, cx + 460, cy + 460), fill=(246, 246, 244))
    d.ellipse((cx - 330, cy - 330, cx + 330, cy + 330), fill=(238, 238, 236), outline=(222, 222, 220), width=6)
    d.ellipse((cx - 250, cy - 230, cx + 250, cy + 230), fill=(204, 58, 38))  # sauce
    for _ in range(34):
        a, r, pts = rng.uniform(0, math.tau), rng.randint(20, 220), []
        for t in range(0, 70, 5):
            ang = a + t / 22
            pts.append((cx + r * math.cos(ang) * 1.05, cy + r * math.sin(ang)))
        d.line(pts, fill=jitter(rng, (236, 200, 110), 10), width=15, joint="curve")
    for bx, by in ((520, 470), (640, 560), (580, 640)):  # basil
        d.polygon([(bx, by - 52), (bx + 36, by), (bx, by + 52), (bx - 36, by)], fill=(46, 140, 62))
    for _ in range(90):  # parmesan
        sx, sy = rng.randint(380, 800), rng.randint(400, 780)
        if (sx - cx) ** 2 + (sy - cy) ** 2 < 220**2:
            d.ellipse((sx - 5, sy - 5, sx + 5, sy + 5), fill=(250, 244, 220))
    d.polygon([(900, 220), (930, 214), (1040, 640), (1010, 650)], fill=(200, 200, 204))  # fork
    return finish(img, rng, blur=1.3)


def alpine_meadow(rng: random.Random) -> Image.Image:
    img = vgrad((PHOTO, PHOTO), (96, 160, 230), (214, 232, 246))
    d = ImageDraw.Draw(img)
    d.polygon([(0, 640), (200, 380), (360, 520), (610, 260), (860, 540), (1010, 420), (1170, 600), (1170, 700), (0, 700)], fill=(120, 138, 164))
    d.polygon([(610, 260), (560, 360), (610, 330), (660, 380)], fill=(250, 250, 252))  # snow
    d.polygon([(200, 380), (160, 450), (210, 430), (250, 460)], fill=(250, 250, 252))
    meadow = vgrad((PHOTO, 560), (96, 150, 62), (60, 108, 44))
    img.paste(meadow, (0, 610))
    d.polygon([(500, 1170), (590, 700), (620, 700), (760, 1170)], fill=(206, 184, 140))  # trail
    for _ in range(260):
        x, y = rng.randint(0, PHOTO), rng.randint(720, 1160)
        r = 3 + (y - 700) // 70
        d.ellipse((x - r, y - r, x + r, y + r), fill=rng.choice(((255, 255, 255), (250, 220, 60), (240, 120, 170), (150, 110, 230))))
    return finish(img, rng, blur=1.2)


def market_stall(rng: random.Random) -> Image.Image:
    img = vgrad((PHOTO, PHOTO), (212, 188, 150), (150, 110, 74))
    d = ImageDraw.Draw(img)
    for i, x in enumerate(range(0, PHOTO, 130)):  # striped awning
        d.polygon([(x, 0), (x + 130, 0), (x + 150, 250), (x + 20, 250)], fill=(214, 52, 44) if i % 2 == 0 else (248, 244, 236))
    img = img.filter(ImageFilter.GaussianBlur(3))
    d = ImageDraw.Draw(img)
    fruit = ((240, 140, 30), (200, 40, 40), (250, 214, 60), (112, 170, 60), (150, 40, 90))
    for row, y in enumerate(range(420, 1100, 220)):
        d.rectangle((60, y + 70, 1110, y + 210), fill=(138, 96, 60))  # crate
        colour = fruit[row % len(fruit)]
        for x in range(90, 1100, 76):
            r = 38
            d.ellipse((x - r, y - r + 40, x + r, y + r + 40), fill=jitter(rng, colour, 16))
            d.ellipse((x - 14, y - 22, x + 4, y - 4), fill=jitter(rng, (255, 255, 255), 0))
    return finish(img, rng, blur=1.1)


# --- the screenshot around a picture ----------------------------------------------


@dataclass(frozen=True)
class Post:
    name: str
    scene: Callable[[random.Random], Image.Image]
    user: str
    caption: str  # words starting with # are drawn in blue
    place: str | None  # shown under the user name, like a location tag
    likes: str
    ago: str
    colour: Colour  # the avatar
    dark: bool
    # What a good tagger would say about it, for seeding the demo library:
    title: str
    summary: str
    category: str
    city: str | None
    country: str | None
    tags: list[str] = field(default_factory=list)


POSTS = [
    Post("post-lisbon", sunset_skyline, "marta.walks", "Golden hour from the Alfama rooftops. Worth the climb. #lisbon #sunset #travel", "Lisbon, Portugal",
         "2,184", "3 HOURS AGO", (232, 98, 60), False, "Sunset over the Lisbon rooftops", "A skyline at golden hour, posted from the Alfama district in Lisbon.",
         "travel", "Lisbon", "Portugal", ["lisbon", "portugal", "sunset", "skyline", "alfama", "golden hour"]),
    Post("post-osaka-ramen", ramen_bowl, "noodle.notes", "Best bowl of the trip, shop near Dotonbori. Extra chashu, always. #ramen #osaka #foodie", "Osaka, Japan",
         "5,310", "1 DAY AGO", (200, 60, 50), True, "Ramen bowl in Osaka", "A top-down photo of a ramen bowl with egg, chashu and nori, tagged in Osaka.",
         "food", "Osaka", "Japan", ["ramen", "osaka", "japan", "noodles", "chashu", "dotonbori"]),
    Post("post-bled", mountain_lake, "ana.outdoors", "Lake Bled at 6am, not a soul around. #lakebled #slovenia #mountains", "Lake Bled, Slovenia",
         "9,042", "5 DAYS AGO", (60, 140, 120), False, "Lake Bled at sunrise", "Still water reflecting mountains and pine forest, tagged Lake Bled in Slovenia.",
         "travel", "Bled", "Slovenia", ["lake bled", "slovenia", "mountains", "lake", "reflection", "sunrise"]),
    Post("post-beach", beach_day, "sam.sunday", "Finally some sun. Weekend reset. #beach #weekend #summer", None,
         "812", "2 DAYS AGO", (236, 170, 40), False, "Beach day with a red parasol", "A sunny beach with a palm tree, a red parasol and calm blue water.",
         "travel", None, None, ["beach", "palm tree", "parasol", "summer", "sea"]),
    Post("post-coffee", coffee_flatlay, "slowmornings", "Saturday ritual at the corner cafe. Flat white and a croissant. #coffee #brunch", None,
         "1,479", "6 HOURS AGO", (150, 100, 70), False, "Flat white and croissant", "A flat lay of a latte with heart art next to a croissant on a marble table.",
         "food", None, None, ["coffee", "flat white", "croissant", "cafe", "brunch"]),
    Post("post-neon", neon_bokeh, "late.shift", "Walking home after the concert. City lights doing their thing. #nightlife #bokeh", None,
         "403", "4 DAYS AGO", (150, 80, 255), True, "Neon city lights at night", "Blurred pink, blue and amber lights from a night street.",
         "other", None, None, ["night", "neon", "city lights", "bokeh", "concert"]),
    Post("post-kyoto", autumn_temple, "kenji.trips", "Eikando at peak colour. Go early, the queue is real. #kyoto #autumn #temple", "Kyoto, Japan",
         "6,727", "1 WEEK AGO", (190, 50, 40), False, "Autumn leaves at a Kyoto temple", "Red maple leaves framing a temple roof and stone path in Kyoto.",
         "travel", "Kyoto", "Japan", ["kyoto", "japan", "autumn", "maple", "temple", "eikando"]),
    Post("post-pasta", pasta_plate, "sunday.table", "Sunday dinner, recipe in the comments. Fresh basil makes it. #pasta #homecooking", None,
         "2,950", "3 DAYS AGO", (210, 70, 50), True, "Homemade tomato pasta", "A plate of spaghetti in tomato sauce with basil and parmesan.",
         "food", None, None, ["pasta", "tomato sauce", "basil", "parmesan", "homecooking", "recipe"]),
    Post("post-hike", alpine_meadow, "trail.log", "Alpine meadow on day two. Flowers everywhere. #hiking #alps", None,
         "1,102", "8 DAYS AGO", (90, 150, 70), False, "Alpine meadow hike", "A flower meadow and a trail leading to snow-capped peaks.",
         "travel", None, None, ["hiking", "alps", "meadow", "mountains", "trail", "flowers"]),
    Post("post-market", market_stall, "weekend.finds", "Saturday market haul. Oranges were unreal. #market #fruit", None,
         "366", "9 DAYS AGO", (240, 140, 30), False, "Fruit stall at a market", "Crates of oranges, apples and lemons under a red and white awning.",
         "food", None, None, ["market", "fruit", "oranges", "stall"]),
]


def post_screenshot(post: Post, rng: random.Random) -> Image.Image:
    bg, ink, grey, line = ((18, 18, 20), (244, 244, 246), (150, 150, 158), (46, 46, 52)) if post.dark else ((255, 255, 255), (24, 24, 28), (128, 128, 136), (226, 226, 230))
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    d.text((70, 30), "9:41", fill=ink, font=font(42, True))  # status bar
    for i in range(4):
        d.rectangle((W - 330 + i * 18, 62 - i * 8, W - 318 + i * 18, 70), fill=ink)
    d.rounded_rectangle((W - 220, 36, W - 130, 72), radius=9, outline=ink, width=4)
    d.rounded_rectangle((W - 214, 42, W - 150, 66), radius=5, fill=ink)
    d.rectangle((W - 126, 48, W - 120, 60), fill=ink)
    d.ellipse((60, 120, 156, 216), fill=post.colour)  # app bar
    d.text((108, 168), post.user[0].upper(), fill=(255, 255, 255), font=font(46, True), anchor="mm")
    d.text((180, 124 if post.place else 150), post.user, fill=ink, font=font(42, True))
    if post.place:
        d.ellipse((182, 184, 200, 202), outline=grey, width=3)
        d.text((212, 174), post.place, fill=grey, font=font(32))
    for dx in (0, 24, 48):
        d.ellipse((W - 140 + dx, 160, W - 128 + dx, 172), fill=ink)
    img.paste(post.scene(rng), (0, 250))
    y = 1460  # action row
    heart = [(16 * math.sin(t / 20) ** 3, -(13 * math.cos(t / 20) - 5 * math.cos(2 * t / 20) - 2 * math.cos(3 * t / 20) - math.cos(4 * t / 20))) for t in range(1, 126)]
    d.line([(90 + px * 2.6, y + 40 + py * 2.6) for px, py in heart], fill=ink, width=6, joint="curve")
    d.ellipse((190, y + 8, 270, y + 78), outline=ink, width=6)
    d.polygon([(204, y + 66), (196, y + 96), (232, y + 76)], fill=bg, outline=ink)
    d.polygon([(330, y + 18), (410, y + 52), (330, y + 86), (346, y + 52)], outline=ink, width=6)
    d.polygon([(W - 130, y + 10), (W - 70, y + 10), (W - 70, y + 90), (W - 100, y + 66), (W - 130, y + 90)], outline=ink, width=6)
    d.text((60, y + 124), f"{post.likes} likes", fill=ink, font=font(42, True))
    x, cy, f, fb = 60, y + 196, font(42), font(42, True)  # caption, wrapped word by word
    for word in [post.user] + post.caption.split():
        face = fb if word == post.user else f
        width = d.textlength(word + " ", font=face)
        if x + width > W - 60:
            x, cy = 60, cy + 62
        d.text((x, cy), word, fill=(56, 120, 230) if word.startswith("#") else ink, font=face)
        x += width
    d.text((60, cy + 100), "View all comments", fill=grey, font=font(38))
    d.text((60, cy + 160), post.ago, fill=grey, font=font(30))
    d.line((0, 2380, W, 2380), fill=line, width=3)  # bottom bar
    for i, cx in enumerate((120, 345, 585, 825, 1050)):
        if i == 0:
            d.polygon([(cx - 36, 2462), (cx, 2424), (cx + 36, 2462), (cx + 36, 2492), (cx - 36, 2492)], outline=ink, width=5)
        elif i == 1:
            d.ellipse((cx - 30, 2424, cx + 14, 2468), outline=ink, width=5)
            d.line((cx + 10, 2464, cx + 34, 2490), fill=ink, width=5)
        elif i == 2:
            d.rounded_rectangle((cx - 36, 2424, cx + 36, 2492), radius=14, outline=ink, width=5)
            d.line((cx, 2444, cx, 2472), fill=ink, width=5)
            d.line((cx - 14, 2458, cx + 14, 2458), fill=ink, width=5)
        elif i == 3:
            d.ellipse((cx - 32, 2426, cx + 32, 2480), outline=ink, width=5)
        else:
            d.ellipse((cx - 32, 2424, cx + 32, 2488), fill=post.colour)
    return img


def generate(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, post in enumerate(POSTS):
        path = out / f"{post.name}.png"
        post_screenshot(post, random.Random(1000 + index)).save(path, format="PNG")
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write photo-like fake phone screenshots for demos.")
    parser.add_argument("--out", type=Path, default=Path("eval/demo"))
    args = parser.parse_args(argv)
    print(f"Wrote {len(generate(args.out))} images to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
