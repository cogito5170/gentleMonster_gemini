"""Photo measurement (S1): code measures mood; the agent only names content.

Reuses the pinned gentleMonster's photos.measure / palette (brightness, contrast, dark share, saturation, warmth,
focus, palette) and adds what curation needs: hue, sharpness (Laplacian variance) and a subject estimate
(how many separate regions stand out from the image's median colour). Needs Pillow + numpy.
"""
from __future__ import annotations

import math
from pathlib import Path

IMG_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")
HUES = [(15, "red"), (45, "orange"), (70, "yellow"), (160, "green"), (200, "cyan"), (260, "blue"), (300, "purple"), (345, "magenta"), (361, "red")]


def is_image(p: Path) -> bool:
    b = p.read_bytes()[:12]
    return any(b.startswith(m) for m in IMG_MAGIC) and (not b.startswith(b"RIFF") or b[8:12] == b"WEBP")


def _hue(im):
    import numpy as np
    hsv = np.asarray(im.convert("HSV")).astype(float)
    h, s = hsv[..., 0] / 255 * 2 * math.pi, hsv[..., 1] / 255
    if s.sum() < 1e-6 or s.mean() < .03:
        return None, "none"
    deg = (math.degrees(math.atan2((np.sin(h) * s).sum(), (np.cos(h) * s).sum())) + 360) % 360
    return round(deg), next(n for lim, n in HUES if deg < lim)


def _subject(im):
    """Regions that stand out from the median colour: (share of the frame, number of separate regions >= 0.3 %)."""
    import numpy as np
    a = np.asarray(im.resize((120, 80))).astype(float) / 255
    med = np.median(a.reshape(-1, 3), 0)
    m = np.sqrt(((a - med) ** 2).sum(-1)) > .25
    seen, regions = np.zeros_like(m), 0
    for y, x in zip(*np.nonzero(m)):
        if seen[y, x]:
            continue
        stack, n = [(y, x)], 0
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            n += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < m.shape[0] and 0 <= nx < m.shape[1] and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        regions += n >= .003 * m.size          # a small subject (a sprout) is a subject too
    return round(float(m.mean()), 3), regions


def measure(path) -> dict:
    """Everything in numbers; nothing guessed. Raises ValueError for a file that is not an image."""
    import numpy as np
    from PIL import ImageFilter
    from gentle_monster import photos as GP
    p = Path(path)
    if not p.is_file() or not is_image(p):
        raise ValueError(f"{p} is not a JPEG, PNG or WEBP image")
    if p.stat().st_size > 25e6:
        raise ValueError(f"{p} is larger than 25 MB")
    m = GP.measure(p)
    im = GP._load(p, 600)
    lap = np.asarray(im.convert("L").filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], 1, 128))).astype(float)
    deg, name = _hue(im)
    share, regions = _subject(im)
    return {"file": p.name, "brightness": m["brightness"], "dark_share": m["dark"], "contrast": m["contrast"], "saturation": m["saturation"],
            "warmth": m["warmth"], "hue_deg": deg, "hue": name, "mono": bool(m["mono"]), "sharpness": round(float(lap.var()), 1),
            "centre_focus": m["focus"], "subject_share": share, "subject_regions": regions,
            "colors": distinct(GP.palette(p, 8)), "layout_like": GP.reference_score(p) >= GP.REF_THRESHOLD}


def distinct(pal, n: int = 5, gap: float = 30) -> "list[str]":
    """Palette colours, most frequent first, skipping any within `gap` (RGB distance) of one already kept."""
    out = []
    for h, _ in pal:
        c = [int(h[i:i + 2], 16) for i in (1, 3, 5)]
        if all(sum((a - b) ** 2 for a, b in zip(c, [int(k[i:i + 2], 16) for i in (1, 3, 5)])) ** .5 >= gap for k in out):
            out.append(h)
    return out[:n]


# ------------------------------------------------------------------ closed criteria and moods, scored by code
CRITERIA = ["brightest", "darkest", "most_saturated", "most_muted", "warmest", "coolest", "sharpest", "softest", "single_subject", "night"]
MOODS = ["bright", "dark", "saturated", "muted", "warm", "cool", "sharp", "soft", "monochrome"]


def score(m: dict, by: str) -> float:
    sh = min(m["sharpness"] / 400, 1)
    return {"brightest": m["brightness"], "darkest": 1 - m["brightness"], "most_saturated": m["saturation"], "most_muted": 1 - m["saturation"],
            "warmest": m["warmth"], "coolest": -m["warmth"], "sharpest": sh, "softest": 1 - sh,
            "single_subject": (1.0 if m["subject_regions"] == 1 and m["subject_share"] <= .4 else .4 if m["subject_regions"] == 2 else 0)
                              - .1 * min(abs(m["subject_share"] - .1), 1),          # one clear subject first; its size only breaks ties
            "night": m["dark_share"] * .7 + (1 - m["brightness"]) * .3}[by]


def mood_fit(m: dict, moods) -> float:
    sh = min(m["sharpness"] / 400, 1)
    f = {"bright": m["brightness"], "dark": 1 - m["brightness"], "saturated": m["saturation"], "muted": 1 - m["saturation"],
         "warm": .5 + m["warmth"], "cool": .5 - m["warmth"], "sharp": sh, "soft": 1 - sh, "monochrome": 1.0 if m["mono"] else 0.0}
    return sum(f[x] for x in moods) / max(len(moods), 1)
