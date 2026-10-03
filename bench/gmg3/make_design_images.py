"""Stand-ins for the design-set attachments (22: the cover draft, 23: the applicant's notes). Not used in the evaluation."""
from pathlib import Path

from PIL import Image, ImageDraw

import make_images as MI

OUT = Path(__file__).resolve().parent / "images" / "design"


def main():
    MI.page([("SPA", 64), ("STYLIST", 26), ("PHOTOGRAPHER", 26), ("ARCHITECT", 26), ("JEONG HYEOKJU", 18)], MI.night_red_light()).save(OUT / "q22_cover_draft.jpg", quality=90)
    im = Image.new("RGB", (900, 600), (250, 248, 240))
    d = ImageDraw.Draw(im)
    for i, t in enumerate(["space changes people", "a good space: you stop, you stay", "you come back to it", "photos: we forget, a photo takes you back",
                           "a good photo: you look for long", "life goal: give people good space"]):
        d.text((60, 60 + i * 80), "- " + t, fill=(30, 30, 30), font=MI.font(26))
    im.save(OUT / "q23_notes.jpg", quality=90)


if __name__ == "__main__":
    main()
