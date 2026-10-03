"""CMD-GMG5 D3: what the reference-set changes do on the design questions only (split 'design' in
gentleMonster@4eb4ffa questions.semantic.json; the eval_seen questions 32-42 and anything held out are not used).
No model calls: the tools' own outputs on those questions' images, before (the formulas as they were) and after.
Images: the private gm-photos top level (values only are written). Run: GMG_UPSTREAM=... python3 bench/gmg5/design_check.py GM_PHOTOS_DIR"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gmg import layouts as LY, photo, upstream  # noqa: E402


def old_sharp(m):
    return min(m["sharpness"] / 400, 1)


def main(gm: Path) -> int:
    upstream.load()
    from gentle_monster import photos as GP
    out = {"what": __doc__.split("\n")[0], "questions": {}}
    M = {f: photo.measure(gm / f) for f in ["1.webp", "2.webp", "3.webp", "4.webp", "5.webp"]}
    rank = lambda key: [f for f, _ in sorted(M.items(), key=lambda x: -key(x[1]))]  # noqa: E731
    out["questions"]["4"] = {
        "asks": "classify photos 1-5 by colour, brightness, saturation, blur, focus, objects, subject",
        "blur_before": {f: round(old_sharp(m), 3) for f, m in M.items()},
        "blur_after": {f: round(photo.level(m, "sharpness"), 3) for f, m in M.items()},
        "sharpest_order_before": rank(old_sharp), "sharpest_order_after": rank(lambda m: photo.level(m, "sharpness")),
        "warm_fit_before": {f: round(.5 + m["warmth"], 3) for f, m in M.items()},
        "warm_fit_after": {f: round(photo.mood_fit(m, ["warm"]), 3) for f, m in M.items()},
    }
    imgs = {"11": ["6.webp"], "23": ["8.jpg"], "26": ["9.jpg", "7.jpg"]}
    for q, fs in imgs.items():
        out["questions"][q] = {f: {"layout_like_before": GP.reference_score(gm / f) >= GP.REF_THRESHOLD, "layout_like_after": photo.layout_like(gm / f)} for f in fs}
    out["questions"]["4"]["layout_like_before"] = {f: GP.reference_score(gm / f) >= GP.REF_THRESHOLD for f in M}
    out["questions"]["4"]["layout_like_after"] = {f: photo.layout_like(gm / f) for f in M}
    for q, asks in (("13", "a moodboard as a one-page magazine layout"), ("21", "a reference layout given; place the photos; a magazine-form moodboard")):
        out["questions"][q] = {"asks": asks, "plans_before": 0,
                               "plans_after_by_photo_count": {n: LY.options(n) for n in (0, 1, 2, 3, 4, 5, 6, 12)}}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "gm-photos")))
