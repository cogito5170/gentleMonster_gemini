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
            "colors": distinct(GP.palette(p, 8)), "layout_like": layout_like(p)}


LAYOUT_FLAT, LAYOUT_EDGE = .17, .52    # the middle of the region the design data allows, chosen blind (CMD-GMG10 S4;
                                       # bench/gmg5/CALIBRATION.md). Before: .08, .6


def layout_signals(p) -> "tuple[float, float]":
    """(flat, edge) for telling a page, board or screenshot from a photograph.
    flat: share of 8x8 blocks that are perfectly flat and not black. Crushed shadows and black studio backgrounds are flat
    in photographs too; the upstream flat-block score counted them, and flagged 16 of 87 reference photographs.
    edge: the longest straight edge (the share of one pixel row or column with a strong step), as frames, columns,
    rules and text lines make."""
    import numpy as np
    from gentle_monster import photos as GP
    L = np.asarray(GP._load(p, 800).convert("L")).astype(float)
    h, w = (L.shape[0] // 8) * 8, (L.shape[1] // 8) * 8
    B = L[:h, :w].reshape(h // 8, 8, w // 8, 8).transpose(0, 2, 1, 3).reshape(-1, 64)
    flat = float((((B.max(1) - B.min(1)) == 0) & (B.mean(1) >= 24)).mean())
    edge = float(max((np.abs(np.diff(L, axis=1)) > 40).mean(0).max(), (np.abs(np.diff(L, axis=0)) > 40).mean(1).max()))
    return round(flat, 3), round(edge, 3)


def layout_like(p) -> bool:
    flat, edge = layout_signals(p)
    return flat >= LAYOUT_FLAT and edge >= LAYOUT_EDGE


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


# Each mood is 0 at the 10th percentile of the GMG5 public reference set (87 photographs) and 1 at its 90th
# (bench/gmg5/CALIBRATION.md). Before, sharpness/400 put 74 of the 87 at 1, so "sharpest" and "softest" could not rank them,
# and warmth (.5 + warmth) moved every photo by less than .2.
SCALE = {"brightness": (.20, .53), "saturation": (0.0, .60), "warmth": (0.0, .20), "sharpness": (280.0, 2500.0)}


def level(m: dict, k: str) -> float:
    lo, hi = SCALE[k]
    v = m[k]
    if k == "sharpness":
        v, lo, hi = math.log(max(v, 1.0)), math.log(lo), math.log(hi)
    return min(max((v - lo) / (hi - lo), 0.0), 1.0)


def score(m: dict, by: str) -> float:
    sh = level(m, "sharpness")
    return {"brightest": m["brightness"], "darkest": 1 - m["brightness"], "most_saturated": m["saturation"], "most_muted": 1 - m["saturation"],
            "warmest": m["warmth"], "coolest": -m["warmth"], "sharpest": sh, "softest": 1 - sh,
            "single_subject": (1.0 if m["subject_regions"] == 1 and m["subject_share"] <= .4 else .4 if m["subject_regions"] == 2 else 0)
                              - .1 * min(abs(m["subject_share"] - .1), 1),          # one clear subject first; its size only breaks ties
            "night": m["dark_share"] * .7 + (1 - m["brightness"]) * .3}[by]


def mood_fit(m: dict, moods) -> float:
    b, s, w, sh = (level(m, k) for k in ("brightness", "saturation", "warmth", "sharpness"))
    f = {"bright": b, "dark": 1 - b, "saturated": s, "muted": 1 - s, "warm": w, "cool": 1 - w, "sharp": sh, "soft": 1 - sh,
         "monochrome": 1.0 if m["mono"] else 0.0}
    return sum(f[x] for x in moods) / max(len(moods), 1)
