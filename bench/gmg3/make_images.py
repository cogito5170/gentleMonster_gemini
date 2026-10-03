"""Stand-in images for the GMG3 replay (the user's real attachments were never committed).

Deterministic (fixed seed). Each image imitates only what the question log says the attachment was; the measured
values in the replay are measurements of these stand-ins, not of the applicant's photos.
    python3 bench/gmg3/make_images.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent / "images"
R = np.random.default_rng(5170)
W, H = 900, 600


def font(n):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if Path(f).is_file():
            return ImageFont.truetype(f, n)
    return ImageFont.load_default()


def noise(img, s=6):
    a = np.asarray(img).astype(np.int16) + R.integers(-s, s + 1, (img.size[1], img.size[0], 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def night_red_light():                       # dark street from inside a car, red and yellow lights, soft
    im = Image.new("RGB", (W, H), (14, 12, 16))
    d = ImageDraw.Draw(im)
    for x, y, r, c in [(300, 260, 40, (230, 30, 25)), (520, 300, 22, (250, 190, 60)), (700, 280, 18, (240, 170, 50)), (150, 320, 14, (200, 40, 30))]:
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    d.rectangle([0, 470, W, H], fill=(25, 22, 24))
    return noise(im.filter(ImageFilter.GaussianBlur(9)))


def puddle_reflection():                     # blue drums above, their reflection in a puddle below
    im = Image.new("RGB", (W, H), (120, 118, 112))
    d = ImageDraw.Draw(im)
    for i, x in enumerate((180, 330, 480, 630)):
        d.rectangle([x, 120, x + 110, 300], fill=(30, 80 + 10 * i, 170))
    d.ellipse([120, 330, 800, 560], fill=(70, 75, 80))
    top = im.crop((120, 120, 800, 300)).transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(3))
    im.paste(Image.blend(top, Image.new("RGB", top.size, (70, 75, 80)), 0.35), (120, 360))
    return noise(im)


def sprout_sand():                           # one small green sprout on beige sand, sharp
    a = np.full((H, W, 3), (205, 186, 150), np.int16) + R.integers(-18, 19, (H, W, 1))
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.line([(450, 360), (450, 290)], fill=(70, 120, 40), width=6)
    d.ellipse([410, 265, 452, 295], fill=(90, 160, 50))
    d.ellipse([448, 255, 495, 288], fill=(100, 170, 55))
    return im


def string_lights_bw():                      # black and white night terrace, a row of bright bulbs
    im = Image.new("L", (W, H), 30)
    d = ImageDraw.Draw(im)
    for i in range(12):
        x = 60 + i * 70
        y = 150 + int(30 * np.sin(i / 2))
        d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=245)
    d.rectangle([0, 420, W, H], fill=55)
    return noise(im.filter(ImageFilter.GaussianBlur(1.5)).convert("RGB"), 4)


def sunset_sea():                            # sunset sky over a dark sea, weak subject
    y = np.linspace(0, 1, H)[:, None]
    sky = np.stack([230 - 40 * y, 120 + 60 * y, 90 + 70 * y], -1) * np.ones((1, W, 1))
    sky[int(H * .62):] = (40, 52, 70)
    return noise(Image.fromarray(sky.astype(np.uint8)))


def cloudy_parking():                        # flat grey day, an empty lot, one car seen from outside
    im = Image.new("RGB", (W, H), (150, 150, 150))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 330, W, H], fill=(110, 110, 110))
    d.rounded_rectangle([360, 300, 560, 380], 18, fill=(40, 40, 40))
    return noise(im, 3)


def style_photo():                           # Q39: a person in a long dark coat in front of a warm shop window
    im = Image.new("RGB", (W, H), (60, 50, 42))
    d = ImageDraw.Draw(im)
    d.rectangle([80, 60, 820, 420], fill=(196, 178, 155))
    d.rectangle([380, 120, 520, 560], fill=(29, 27, 25))
    d.ellipse([415, 70, 485, 140], fill=(120, 95, 80))
    return noise(im.filter(ImageFilter.GaussianBlur(1)))


def page(texts, photo=None, size=(W, H)):    # a layout page: text blocks and an optional photo block
    im = Image.new("RGB", size, (246, 244, 239))
    d = ImageDraw.Draw(im)
    y = 40
    for t, n in texts:
        d.text((50, y), t, fill=(20, 20, 20), font=font(n))
        y += n + 22
    if photo is not None:
        im.paste(photo.resize((360, 240)), (size[0] - 400, size[1] - 280))
    return im


def main():
    lib = {"L1_night_red_light": night_red_light(), "L2_puddle_reflection": puddle_reflection(), "L3_sprout_sand": sprout_sand(),
           "L4_string_lights_bw": string_lights_bw(), "L5_sunset_sea": sunset_sea(), "L6_cloudy_parking": cloudy_parking()}
    for k, im in lib.items():
        im.save(OUT / "library" / f"{k}.jpg", quality=90)
    page([("SPA", 64), ("STYLE", 28), ("PICTURE", 28), ("ARCHITECTURE", 28), ("Where Did You Last Stop?", 22)], lib["L1_night_red_light"]).save(OUT / "q32_cover.jpg", quality=90)
    style_photo().save(OUT / "q39_style.jpg", quality=90)
    page([("1  STYLE", 30), ("The place I stop most often is the street.", 18), ("2  MOOD", 30), ("MY STYLE", 20)], style_photo()).save(OUT / "q41_pages_1_2.jpg", quality=90)
    page([("3", 30), ("I stop for people whose style is their own.", 20), ("4  PICTURE", 30), ("( empty )", 18)], puddle_reflection()).save(OUT / "q41_pages_3_4.jpg", quality=90)
    case = Image.new("RGB", (600, 900), (250, 250, 248))
    case.paste(sprout_sand().resize((520, 360)), (40, 40))
    ImageDraw.Draw(case).text((210, 560), "BALDE", fill=(15, 15, 15), font=font(72))
    case.save(OUT / "q42_case.jpg", quality=90)


if __name__ == "__main__":
    main()
