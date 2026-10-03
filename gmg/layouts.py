"""Page layout plans (CMD-GMG5 S4, for the layout-variety gap G1/H4), derived from the GMG5 public reference set.

Each plan is one page structure seen in the 40 openly licensed magazine, catalogue and photo-book references
(bench/gmg5/refset/manifest_layouts.jsonl, by-eye `seen` notes and `seen_counts` first; the measured numbers there are coarse).
bench/gmg5/layout_plans.json assigns each reference to one plan; `refs` counts them, `from` says which, and `share` is the
picture share of the page those references show.

The agent only picks a plan id from a closed list. Code checks the photo count, keeps neighbouring pages from repeating
a plan, and computes every box (x, y, w, h as fractions of the page; y from the top). The references are design data
only: no reference image is stored or placed, and the reference photographs are never put in a layout.
"""
from __future__ import annotations

import math

# fmt: off
PLANS = {
    "masthead_cover": {
        "refs": 17,
        "title": "masthead band over one picture that fills most of the page, one or two words at the foot",
        "pictures": (1, 1), "share": .75, "text": ["masthead", "foot_words"],
        "from": "16 magazine covers (Harper's, Vogue 1908-1922, Collier's, Puck, Wendingen) and 1 advertisement page; picture share by eye 20-90 %, median 75 %"},
    "framed_plate": {
        "refs": 4,
        "title": "one framed picture in the upper two thirds, title and credit line centred below, folio at the foot",
        "pictures": (1, 1), "share": .55, "text": ["title", "credit", "folio"],
        "from": "2 framed fashion plates, 1 advertisement page (picture 55 %), 1 catalogue page (one product, 75 %, name + spec lines)"},
    "figure_on_blank": {
        "refs": 6,
        "title": "one figure alone on a blank page with very wide margins, a small title or signature at the foot",
        "pictures": (1, 1), "share": .3, "text": ["foot_title"],
        "from": "2 sketch pages, 3 unframed fashion plates, 1 caricature album page (picture 25-40 %)"},
    "mounted_print": {
        "refs": 2,
        "title": "one small photograph mounted slightly above centre on a plain page, an optional short caption under it",
        "pictures": (1, 1), "share": .15, "text": ["caption"],
        "from": "2 photo-album leaves (one print, about 15 % of the page; one with a hand-written caption)"},
    "loose_grid": {
        "refs": 3,
        "title": "four to six photographs in two loose columns, short captions under each or none",
        "pictures": (4, 6), "share": .35, "text": ["captions"],
        "from": "album leaf with six photographs in two columns (35 %), 2 x 2 cartes-de-visite leaf, catalogue spread of four drawings"},
    "mirror_spread": {
        "refs": 1,
        "title": "a two-page spread: one picture centred on each page, running head, two-line caption under each, mirror symmetry",
        "pictures": (2, 2), "share": .45, "text": ["running_head", "captions"],
        "from": "1 catalogue spread (one product per page, caption under each)"},
    "text_column": {
        "refs": 2,
        "title": "small head picture, centred title, one justified column of text, up to four small pictures beside it",
        "pictures": (1, 5), "share": .25, "text": ["title", "body"],
        "from": "1 magazine text page (head picture, two margin figures, about 25 %), 1 instrument-catalogue column with cuts between price lines"},
    "hero_and_two": {
        "refs": 1,
        "title": "one large picture and two small ones floating on a plain ground, a number or short line at the foot",
        "pictures": (3, 3), "share": .4, "text": ["foot_words"],
        "from": "1 catalogue page (one large and two small product pictures, item number at the foot)"},
    "contact_sheet": {
        "refs": 1,
        "title": "a dense grid of many small pictures under a header line, numbered, little white space",
        "pictures": (7, 60), "share": .5, "text": ["header", "numbers"],
        "from": "1 mail-order catalogue page (about 60 cuts in 6 columns)"},
    "type_only": {
        "refs": 3,
        "title": "a type page: title and one line (author, place or date), no picture",
        "pictures": (0, 0), "share": 0.0, "text": ["title", "line"],
        "from": "2 trade-catalogue title pages, 1 album board cover with one hand-written word"},
}
# fmt: on
ASPECT = 1.414          # page height / width (A-series portrait)
MARGIN = .08


def fits(plan_id: str, n: int) -> bool:
    lo, hi = PLANS[plan_id]["pictures"]
    return lo <= n <= hi


def _box(x, y, w, h):
    return {"x": round(x, 3), "y": round(y, 3), "w": round(w, 3), "h": round(h, 3)}


def boxes(plan_id: str, n: int) -> dict:
    """Picture boxes (largest first) and text boxes for `n` pictures. Areas are fractions of one page
    (a spread is two pages side by side; its x runs 0-2)."""
    if plan_id not in PLANS:
        raise ValueError(f"{plan_id!r} is not a plan")
    if not fits(plan_id, n):
        lo, hi = PLANS[plan_id]["pictures"]
        raise ValueError(f"{plan_id} takes {lo}-{hi} pictures, not {n}")
    m, share = MARGIN, PLANS[plan_id]["share"]
    pics, text = [], {}
    if plan_id == "masthead_cover":
        text["masthead"] = _box(m, .04, 1 - 2 * m, .12)
        pics.append(_box(0, .17, 1, share))            # the picture runs to the edges, as most of the covers do
        text["foot_words"] = _box(m, .17 + share + .01, 1 - 2 * m, 1 - (.17 + share + .01) - .02)
    elif plan_id == "framed_plate":
        h = share / (1 - 2 * .14)
        pics.append(_box(.14, .08, 1 - 2 * .14, h))
        text["title"] = _box(.14, .08 + h + .03, 1 - 2 * .14, .05)
        text["credit"] = _box(.14, .08 + h + .08, 1 - 2 * .14, .03)
        text["folio"] = _box(.45, .94, .1, .03)
    elif plan_id in ("figure_on_blank", "mounted_print"):
        w = math.sqrt(share / 1.3)                     # a portrait picture, height 1.3 x width (in page units)
        h = share / w
        y = .5 - h / 2 - (.05 if plan_id == "mounted_print" else 0)
        pics.append(_box(.5 - w / 2, y, w, h))
        key = "caption" if plan_id == "mounted_print" else "foot_title"
        text[key] = _box(.5 - w / 2, y + h + .02, w, .04) if plan_id == "mounted_print" else _box(.3, .9, .4, .04)
    elif plan_id == "loose_grid":
        rows = math.ceil(n / 2)
        cw = .3
        ch = share / n / cw
        gy = (1 - 2 * m - rows * (ch + .03)) / max(rows - 1, 1)
        for i in range(n):
            r, c = divmod(i, 2)
            pics.append(_box(.15 + c * (cw + .1), m + r * (ch + .03 + gy), cw, ch))
        text["captions"] = [_box(p["x"], round(p["y"] + p["h"] + .005, 3), p["w"], .025) for p in pics]
    elif plan_id == "mirror_spread":
        text["running_head"] = _box(m, .04, 2 - 2 * m, .03)
        for pg in (0, 1):
            w = .6
            pics.append(_box(pg + .2, .18, w, share / w))
        text["captions"] = [_box(p["x"], round(p["y"] + p["h"] + .02, 3), p["w"], .05) for p in pics]
    elif plan_id == "text_column":
        pics.append(_box(.2, m, .6, .25))
        text["title"] = _box(.2, m + .27, .6, .05)
        text["body"] = _box(.2, m + .34, .6, 1 - 2 * m - .34)
        for i in range(n - 1):                         # alternate margins, top to bottom
            pics.append(_box(.03 if i % 2 == 0 else .83, .45 + (i // 2) * .22, .14, .12))
    elif plan_id == "hero_and_two":
        pics.append(_box(m, m, .62, .5))
        pics.append(_box(.74, m + .05, .2, .18))
        pics.append(_box(.74, m + .3, .2, .18))
        text["foot_words"] = _box(.3, .9, .4, .04)
    elif plan_id == "contact_sheet":
        cols = 6 if n > 24 else 4 if n > 9 else 3
        rows = math.ceil(n / cols)
        text["header"] = _box(m, .03, 1 - 2 * m, .04)
        cw, ch = (1 - 2 * m) / cols, (1 - .1 - m) / rows
        h = ch - .025                                  # room for the number under each picture
        w = min(cw - .01, share / n / h)              # the sheet keeps the references' picture share whatever the count
        for i in range(n):
            r, c = divmod(i, cols)
            pics.append(_box(m + c * cw + (cw - w) / 2, .1 + r * ch + .005, w, h))
        text["numbers"] = "under each picture"
    else:                                              # type_only
        text["title"] = _box(m, .38, 1 - 2 * m, .12)
        text["line"] = _box(m, .52, 1 - 2 * m, .04)
    return {"pictures": pics, "text": text, "picture_share": round(sum(p["w"] * p["h"] for p in pics) / (2 if plan_id == "mirror_spread" else 1), 3)}


def options(n: "int | None", avoid=()) -> "list[str]":
    """Plans that take `n` pictures (any count when n is None), minus the plans of the neighbouring pages."""
    return [k for k in PLANS if (n is None or fits(k, n)) and k not in avoid]
