"""CMD-GMG5 S4: what the public reference set changed -- calibrated mood scales, the layout_like rule, page layout plans.
Design data only (bench/gmg5/refset, the GMG5 public set). No network, no key. Run: python3 tests/test_gmg5.py"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="gmg_g5_"))
os.environ["GMG_OUT"] = str(TMP / "out")

from PIL import Image, ImageDraw  # noqa: E402

from gmg import layouts as LY, photo, portfolio as PF, upstream  # noqa: E402

FAIL = []
B5 = ROOT / "bench" / "gmg5"


def ok(c, what):
    print(("  ok  " if c else "  FAIL ") + what)
    if not c:
        FAIL.append(what)


def q(v, p):
    v = sorted(v)
    i = p * (len(v) - 1)
    lo = int(i)
    return v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * (i - lo)


upstream.load()
rows = [json.loads(x) for x in (B5 / "refset_measured.jsonl").read_text().splitlines()]
M = [r["measured"] for r in rows]

print("== the reference set, measured with gmg.photo.measure")
ok(len(rows) == 87 and {r["group"] for r in rows} == {"night_rain_street", "beach_dusk", "still_object", "street_light_portrait", "black_and_white"},
   "87 photographs in the five mood groups of gmg-net's set")
again = photo.measure(B5 / "refset" / rows[0]["file"])
ok(all(again[k] == rows[0]["measured"][k] for k in ("brightness", "saturation", "warmth", "sharpness")), "the stored measures are what the tool measures now")

print("== mood scales calibrated on the set (0 at its 10th percentile, 1 at its 90th)")
for k, (lo, hi) in photo.SCALE.items():
    v = [m[k] for m in M]
    if k == "sharpness":
        good = abs(math.log(q(v, .1)) - math.log(lo)) < .1 and abs(math.log(q(v, .9)) - math.log(hi)) < .1
    else:
        good = abs(q(v, .1) - lo) < .02 and abs(q(v, .9) - hi) < .02
    ok(good, f"{k}: scale {lo}-{hi} is the set's 10th-90th percentile")
lv = [photo.level(m, "sharpness") for m in M]
ok(sum(x >= 1 for x in lv) <= 10 and sum(x <= 0 for x in lv) <= 10, f"sharpness: {sum(x >= 1 for x in lv)} at the top, {sum(x <= 0 for x in lv)} at the bottom (sharpness/400 put 74 of 87 at the top)")
ok(len({round(photo.score(m, 'sharpest'), 3) for m in M}) >= 60, "'sharpest' ranks the set instead of tying it")
for mood in ("bright", "dark", "saturated", "muted", "warm", "cool", "sharp", "soft"):
    f = [photo.mood_fit(m, [mood]) for m in M]
    ok(q(f, .9) - q(f, .1) >= .8, f"mood {mood}: spreads over the set ({q(f, .1):.2f}-{q(f, .9):.2f})")
bw = [photo.mood_fit(r["measured"], ["monochrome"]) for r in rows if r["group"] == "black_and_white"]
ok(min(bw) == 1.0, "monochrome: all 13 black-and-white photographs")
night = [photo.mood_fit(r["measured"], ["dark"]) for r in rows if r["group"] == "night_rain_street"]
day = [photo.mood_fit(r["measured"], ["dark"]) for r in rows if r["group"] == "beach_dusk"]
ok(sorted(night)[len(night) // 2] > sorted(day)[len(day) // 2] + .3, "dark: night streets sit well above beach dusk (medians)")

print("== layout_like: a page, board or screenshot, not a photograph")
sig = json.loads((B5 / "layout_like_signals.json").read_text())
rule = lambda r: r["flat"] >= photo.LAYOUT_FLAT and r["edge"] >= photo.LAYOUT_EDGE  # noqa: E731
ok(not any(rule(r) for r in sig["refset"]), "0 of 87 reference photographs (the upstream flat-block score flagged 16)")
hard = [r for r in sig["refset"] if r["flat"] >= photo.LAYOUT_FLAT]
ok(len(hard) >= 3 and not any(photo.layout_like(B5 / "refset" / r["file"]) for r in hard),
   f"the {len(hard)} photographs with large flat areas (a white sky, a studio ground) are still photographs: no long straight edges")
gm = sig["gm_photos"]
ok(not any(rule(r) for r in gm if r["role"] == "photo"), "0 of the user's 5 photographs")
ok(len(gm) == 9 and sum(rule(r) for r in gm if r["role"] != "photo") == 3, "design questions 11, 22, 26: the reference layout and both draft pages (the notes page of q23 is the miss)")
D = TMP / "img"
D.mkdir()
bd = Image.new("RGB", (600, 400), "white")
d = ImageDraw.Draw(bd)
for i in range(3):
    d.rectangle([30 + i * 190, 40, 200 + i * 190, 220], outline="black", width=3, fill=(200, 190 - 30 * i, 170))
for y in range(250, 380, 18):
    d.line([30, y, 570, y], fill=(40, 40, 40), width=2)
bd.save(D / "board.png")
ph = Image.new("RGB", (600, 400), "black")
d = ImageDraw.Draw(ph)
for i in range(40):
    d.ellipse([200 + i, 100 + i % 7, 400 - i, 300 - i % 5], fill=(120 + i * 3, 90 + i, 40 + i * 2))
ph.save(D / "studio.png")
ok(photo.layout_like(D / "board.png"), "a drawn board (flat paper, boxes, rules) is layout_like")
ok(not photo.layout_like(D / "studio.png"), "an object on a black studio ground is not")

print("== page layout plans from the 40 layout references")
lp = json.loads((B5 / "layout_plans.json").read_text())["refs"]
manifest = [json.loads(x) for x in (B5 / "refset" / "manifest_layouts.jsonl").read_text().splitlines()]
ok([r["id"] for r in lp] == [m["id"] for m in manifest], "every reference is assigned to one plan")
ok(all(r["plan"] in LY.PLANS for r in lp), "only plans that exist")
ok(set(LY.PLANS) == {r["plan"] for r in lp}, "every plan comes from at least one reference")
ok(all(LY.fits(r["plan"], r["seen_counts"]["pictures"]) for r in lp), "each reference's picture count (by eye) fits its plan")
ok(all(v["refs"] == sum(r["plan"] == k for r in lp) for k, v in LY.PLANS.items()), "each plan's reference count matches the map")
bad = []
for k, v in LY.PLANS.items():
    lo, hi = v["pictures"]
    for n in range(lo, hi + 1):
        b = LY.boxes(k, n)
        boxes = b["pictures"] + [x for t in b["text"].values() for x in (t if isinstance(t, list) else [t] if isinstance(t, dict) else [])]
        w = 2 if k == "mirror_spread" else 1
        if len(b["pictures"]) != n or any(x["x"] < 0 or x["y"] < 0 or x["x"] + x["w"] > w + 1e-6 or x["y"] + x["h"] > 1 + 1e-6 for x in boxes) \
                or abs(b["picture_share"] - v["share"]) > .1:
            bad.append((k, n))
ok(not bad, f"every plan, every allowed count: one box per photo, all on the page, picture share within .1 of the references' ({bad[:3]})")

print("== pf_pages layout: closed choice, count and neighbour checks")
for i, c in enumerate([(200, 60, 40), (40, 60, 200), (90, 90, 90)]):
    Image.new("RGB", (300, 200), c).save(D / f"p{i}.png")
PF.call("pf_pages", {"action": "set", "pages": [{"n": 1, "title": "COVER"}, {"n": 2, "title": "STREET"}, {"n": 3, "title": "NIGHT"}]})
ids = [p["id"] for p in PF.call("pf_photos", {"paths": [str(D / f"p{i}.png") for i in range(3)]})["photos"]]
r = PF.call("pf_pages", {"action": "layout", "page": 1, "photos": ids[:1]})
ok(r["ok"] and {p["id"] for p in r["plans"]} == {k for k in LY.PLANS if LY.fits(k, 1)} and len(r["options"]) == len(r["plans"]),
   "the plans that take one photo, numbered")
r = PF.call("pf_choose", {"option": str(1 + [p["id"] for p in r["plans"]].index("masthead_cover"))})
ok(r["ok"] and r["layout"]["plan"] == "masthead_cover" and r["layout"]["boxes"]["pictures"][0]["photo"] == ids[0], "a terse '1' lays the page out; the photo is in its box")
r = PF.call("pf_pages", {"action": "layout", "page": 2, "photos": ids[1:2]})
ok("masthead_cover" not in [p["id"] for p in r["plans"]] and r["avoided"] == ["masthead_cover"], "page 2 is not offered page 1's plan")
r = PF.call("pf_pages", {"action": "layout", "page": 2, "photos": ids[1:2], "choice": "masthead_cover"})
ok(not r["ok"] and "neighbouring" in r["problems"][0] and "masthead_cover" not in r["next"][0]["args"]["choice"], "choosing it anyway is refused, with the plans that may follow")
r = PF.call("pf_pages", {"action": "layout", "page": 2, "photos": ids, "choice": "framed_plate"})
ok(not r["ok"] and "takes 1-1 photos" in r["problems"][0], "a plan that does not take three photos is refused")
r = PF.call("pf_pages", {"action": "layout", "page": 2, "photos": ids, "choice": "hero_and_two"})
ok(r["ok"] and [b["photo"] for b in r["layout"]["boxes"]["pictures"]] == ids, "three photos: the first is the large one")
r = PF.call("pf_pages", {"action": "layout", "page": 3, "photos": ["pzzzzzz"], "choice": "mounted_print"})
ok(not r["ok"] and r["next"][0]["tool"] == "pf_photos", "an unmeasured photo id is refused")
r = PF.call("pf_pages", {"action": "layout", "page": 3, "photos": [], "choice": "nonsense"})
ok(not r["ok"] and "not one of" in r["problems"][0], "a plan outside the list is refused")
ok({x["page"]: x["plan"] for x in PF.call("pf_show", {})["layouts"]} == {"1": "masthead_cover", "2": "hero_and_two"}, "pf_show lists the layouts")
from gmg import ext_mcp  # noqa: E402
tl = ext_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})["result"]["tools"]
pp = next(t for t in tl if t["name"] == "pf_pages")["inputSchema"]["properties"]
ok("layout" in pp["action"]["enum"] and "page" in pp and "photos" in pp, "the MCP schema offers layout with page and photos")
r = json.loads(ext_mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "pf_pages", "arguments": {"action": "layout", "page": 3, "photos": ids[2:3]}}})["result"]["content"][0]["text"])
ok(r["ok"] and "hero_and_two" in r["avoided"], "through the MCP server: page 3 avoids page 2's plan")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("all passed" if not FAIL else f"{len(FAIL)} failed"))
sys.exit(1 if FAIL else 0)
