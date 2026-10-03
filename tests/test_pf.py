"""Portfolio workspace + production options tests -- no network, no key. Run: python3 tests/test_pf.py
Images are drawn here (not the bench stand-ins). Needs Pillow + numpy and the pinned gentleMonster."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="gmg_pf_"))
os.environ["GMG_OUT"] = str(TMP / "out")
os.environ["GEMINI_API_KEY"] = "AIza" + "TESTKEY0123456789abcdefghijklmnop"

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from gmg import agent, ext_mcp, loop, photo, portfolio as PF, upstream  # noqa: E402


def ext_mcp_handle(name, args):
    r = ext_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})
    return json.loads(r["result"]["content"][0]["text"])
from gmg.fake_agent import FakeAgent  # noqa: E402

FAIL = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL ") + what)
    if not cond:
        FAIL.append(what)


def sec(t):
    print(f"\n== {t} ==")


spec, paths = upstream.load()
D = TMP / "img"
D.mkdir()


def img(name, bg, blobs=(), size=(300, 200), mode="RGB"):
    im = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(im)
    for (x, y, r, c) in blobs:
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    if mode == "L":
        im = im.convert("L").convert("RGB")
    p = D / f"{name}.png"
    im.save(p)
    return str(p)


one = img("one", (200, 190, 170), [(150, 100, 12, (30, 120, 40))])
two = img("two", (200, 190, 170), [(80, 100, 14, (30, 30, 160)), (220, 100, 14, (160, 30, 30))])
dark = img("dark", (12, 10, 14), [(150, 90, 10, (240, 60, 40))])
bright = img("bright", (245, 244, 240))
grey = img("grey", (120, 120, 120), [(150, 100, 30, (40, 40, 40))], mode="L")
notimg = D / "x.png"
notimg.write_text("not an image")

sec("photo measuring is code (S1)")
m1, m2, md, mg = (photo.measure(p) for p in (one, two, dark, grey))
ok(m1["subject_regions"] == 1 and m2["subject_regions"] == 2, f"one small subject -> 1 region, two -> 2 ({m1['subject_regions']}, {m2['subject_regions']})")
ok(md["brightness"] < .15 and photo.score(md, "night") > photo.score(m1, "night"), "the dark one is the night one")
ok(mg["mono"] and mg["hue"] == "none", "a grey image is monochrome, no hue")
rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]  # noqa: E731
cols = photo.measure(dark)["colors"] + m2["colors"]
ok(all(sum((a - b) ** 2 for a, b in zip(rgb(x), rgb(y))) ** .5 >= 30 for c in (photo.measure(dark)["colors"], m2["colors"]) for i, x in enumerate(c) for y in c[i + 1:]),
   "palette colours are at least 30 apart (no near-duplicates)")
try:
    photo.measure(notimg)
    ok(False, "a non-image is refused")
except ValueError:
    ok(True, "a non-image is refused")

sec("pf_photos / pf_sort")
r = PF.call("pf_photos", {"paths": [one, two, dark, bright, grey]})
ok(r["ok"] and len(r["photos"]) == 5 and r["options"][0]["label"] == "1", "five measured, numbered options")
n_ev = len(PF._ws().events())
PF.call("pf_photos", {"paths": [one]})
ok(sum(1 for e in PF._ws().events() if e["kind"] == "PHOTO") == 5, "measuring the same file again adds no photo")
ids = {p["file"]: p["id"] for p in r["photos"]}
r = PF.call("pf_sort", {"by": "single_subject"})
order = r["ranking"]["order"]
ok(r["ok"] and max(order.index(ids[f]) for f in ("one.png", "dark.png", "grey.png")) < min(order.index(ids[f]) for f in ("two.png", "bright.png")),
   "single_subject ranks every one-subject image above the two-subject and the empty one")
ok(all("evidence" in t for t in r["ranking"]["table"]), "every rank carries its measured evidence")
r = PF.call("pf_sort", {"groups": [{"name": "night", "mood": ["dark"]}, {"name": "day", "mood": ["bright", "muted"]}]})
asg = {a["file"]: a["group"] for a in r["ranking"]["assign"]}
ok(asg["dark.png"] == "night" and asg["bright.png"] == "day", "groups by mood: dark -> night, bright -> day")
r = PF.call("pf_sort", {"by": "prettiest"})
ok(r["ok"] is False and "single_subject" in str(r["next"]), "a criterion off the list -> the list")

sec("pf_write: the agent writes, code checks (S2)")
r = PF.call("pf_write", {"kind": "answer", "register": "direct", "language": "ko",
                         "items": [{"text": "스타일은 본질과 존재의 철학이며 내면의 영혼이다."}]})
ok(r["ok"] is False and "abstract" in r["problems"][0] and "본질" in r["problems"][0], "abstract words over the direct limit -> named")
r = PF.call("pf_write", {"kind": "answer", "register": "direct", "language": "ko", "items": [{"text": "Style is what you wear."}]})
ok(r["ok"] is False and "language" in r["problems"][0], "English text where Korean was asked -> refused")
r = PF.call("pf_write", {"kind": "question", "register": "direct", "language": "en", "items": [{"text": "Where did you stop", "pattern": "question"}]})
ok(r["ok"] is False and "question mark" in r["problems"][0], "a question pattern needs a question mark")
r = PF.call("pf_write", {"kind": "answer", "register": "direct", "language": "ko", "items": [
    {"text": "같은 흰 셔츠도 누가 입느냐에 따라 다르게 보인다.", "label": "Q1"}, {"text": "나는 길에서 코트 길이가 맞는 사람을 보면 멈춘다.", "label": "Q2"}]})
ok(r["ok"] and [t["label"] for t in r["texts"]] == ["A", "B"] and r["options"][0]["call"]["args"]["choice"] == r["texts"][0]["id"], "stored, lettered A/B, options adopt them")
t_a = r["texts"][0]["id"]

r = PF.call("pf_write", {"kind": "statement", "register": "direct", "language": "ko", "keep": ["무의식"],
                         "items": [{"text": "무의식은 내가 길에서 멈추는 이유다."}]})
ok(r["ok"] and r["texts"][0]["measures"]["abstract_ratio"] == 0, "a word the user chose (keep) is not counted as abstract")

sec("pf_revise: closed operations, before and after kept (S3)")
abstract = PF.call("pf_write", {"kind": "answer", "register": "poetic", "language": "ko", "items": [{"text": "스타일은 아침마다 고르는 옷과 신발에서 드러나는 나의 철학이다."}]})
tid = abstract["texts"][0]["id"]
r = PF.call("pf_revise", {"op": "more_direct", "targets": [tid], "texts": ["스타일은 나의 철학과 정체성의 울림이다."]})
ok(r["ok"] is False and "more_direct must lower" in r["problems"][0], "more_direct that stays abstract -> refused")
r = PF.call("pf_revise", {"op": "more_direct", "targets": [tid], "texts": ["스타일은 내가 아침에 고르는 코트와 신발이다."]})
ok(r["ok"] and r["texts"][0]["parent"] == tid and r["texts"][0]["measures"]["abstract_ratio"] < r["texts"][0]["before_abstract"], "more_direct accepted: lower abstract ratio, parent kept")
ok(PF.state()["texts"][-1]["before"].startswith("스타일은 아침마다"), "the before text is in the ledger")
r = PF.call("pf_revise", {"op": "refocus", "arg": "스타일", "targets": [t_a], "texts": ["같은 흰 셔츠도 누가 입느냐에 따라 다르다."]})
ok(r["ok"] is False and "centre on" in r["problems"][0], "refocus without the topic -> refused")
r = PF.call("pf_revise", {"op": "widen_categories", "arg": "머리, 안경, 옷, 신발", "source_text": "어떤 머리를 했는지, 무슨 옷을 입었는지.",
                          "texts": ["어떤 머리를 했는지, 어떤 안경을 썼는지, 무슨 옷과 신발을 신었는지."]})
ok(r["ok"] and PF.state()["texts"][-2].get("source") == "user", "the user's own text is stored first, then widened")
r = PF.call("pf_revise", {"op": "shorten", "targets": ["last"], "texts": ["어떤 머리를 했는지, 어떤 안경을 썼는지, 무슨 옷과 신발을 신었는지, 그리고 향까지."]})
ok(r["ok"] is False and "shorten must cut" in r["problems"][0], "shorten that grows -> refused")

sec("pf_concept: a phrase against the terms (S4)")
r = PF.call("pf_concept", {"phrase": "Where did you last stop?", "terms": [{"name": "STYLE", "definition": "a person with style"},
                                                                        {"name": "PICTURE", "definition": "a scene like a photograph"}],
                           "verdicts": [{"term": "STYLE", "connects": "partly", "reason": "you can stop for a person with style"}]})
ok(r["ok"] is False and any("no verdict for PICTURE" in p for p in r["problems"]), "every term needs a verdict")
r = PF.call("pf_concept", {"phrase": "Where did you last stop?", "verdicts": [
    {"term": "STYLE", "connects": "partly", "reason": "seems fine to me"},
    {"term": "PICTURE", "connects": "yes", "reason": "a scene like a photograph is where you stop"}]})
ok(r["ok"] is False and any("must quote" in p for p in r["problems"]), "a reason that quotes nothing from the phrase or the definition -> refused")
r = PF.call("pf_concept", {"phrase": "Where did you last stop?", "verdicts": [
    {"term": "STYLE", "connects": "partly", "reason": "you can stop for a person with style"},
    {"term": "PICTURE", "connects": "yes", "reason": "a scene like a photograph is where you stop"}]})
ok(r["ok"] and r["concept"]["of"] == 2 and "1 of 2" in r["say"], "a yes/no/partly table with reasons")

sec("pf_pages: page map, three proposals, adopt (S5)")
PF.call("pf_pages", {"action": "set", "pages": [{"n": 0, "title": "COVER", "role": "SPA"}, {"n": 1, "title": "STYLE", "role": "opening"}]})
r = PF.call("pf_pages", {"action": "propose", "after": 1, "options": [{"title": "Street", "summary": "길에서 멈춘 사람."}, {"title": "Mirror", "summary": "거울 앞의 나."}]})
ok(r["ok"] is False and "exactly 3" in r["problems"][0], "two proposals -> refused (exactly 3)")
r = PF.call("pf_pages", {"action": "propose", "after": 1, "options": [{"title": "Street", "summary": "길에서 멈춘 사람."}, {"title": "Mirror", "summary": "거울 앞의 나."},
                                                                   {"title": "Closet", "summary": "옷장을 연 아침."}]})
ok(r["ok"] and [o["label"] for o in r["options"]] == ["A", "B", "C"], "three proposals, A/B/C")

sec("pf_choose: terse replies resolve to one exact call (S7)")
r = PF.call("pf_choose", {"option": "B안을 채택한다"})
ok(r["ok"] and r["adopted"]["option"] == "B" and PF.state()["proposals"][-1]["adopted"] == "B", "'B안을 채택한다' -> adopt B")
PF.call("pf_pages", {"action": "propose", "after": 2, "options": [{"title": "One", "summary": "하나."}, {"title": "Two", "summary": "둘."}, {"title": "Three", "summary": "셋."}]})
r = PF.call("pf_choose", {"option": "a ? a:b"})
ok(r["ok"] and r["adopted"]["option"] == "A", "'a ? a:b' -> the first that resolves (A)")
r = PF.call("pf_choose", {"option": "다시 시도"})
ok(r["ok"] and r["retry"]["tool"] == "pf_pages" and any(e["kind"] == "RETRY" for e in PF._ws().events()), "'다시 시도' -> the last call offered again, recorded")
r = PF.call("pf_choose", {"option": "zebra"})
ok(r["ok"] is False and "last options were" in r["problems"][0], "an unresolvable reply lists the options")

sec("pf_show")
r = PF.call("pf_show", {})
ok(r["ok"] and r["terms"] and len(r["pages"]) == 2 and r["texts"] and r["photos"], "shows terms, pages, texts, photos")

sec("gm_amend / gm_render (S6, S8)")
lr = loop.run("비 오는 밤", "Gentle Monster", transport=FakeAgent("ok"), sleep=lambda s: None)
job = lr["job"]
r = agent.call("gm_amend", {"job": job, "constraints": {"language": "ko_and_en", "pages": "one", "bogus": 1}})
ok(r["ok"] is False and any("bogus" in p for p in r["problems"]), "an unknown constraint -> refused with the allowed list")
r = agent.call("gm_amend", {"job": job, "constraints": {"language": "ko_and_en", "pages": "one"}})
ok(r["ok"] and "NOT supported" in r["effect"]["language"] and "NOT one page" in r["effect"]["pages"], "constraints the pinned code cannot honour are said, not faked")
from gentle_monster import pipeline  # noqa: E402
real_video = pipeline.video
pipeline.video = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ffmpeg missing"))
r = agent.call("gm_render", {"job": job, "outputs": ["layout_pdf", "video"]})
pipeline.video = real_video
ok(r["drawn"].get("layout_pdf") == "layout.pdf" and r["ok"] is False and any("video failed: RuntimeError: ffmpeg missing" in n for n in r["notes"]),
   "layout drawn; a failed video says its cause")
ex = agent.call("gm_explain", {"job": job})
ok(any("video failed" in l for l in ex["explain"]), "gm_explain shows the failure cause from the ledger (S8 / q21)")
r = agent.call("gm_render", {"job": job, "outputs": ["hologram"]})
ok(r["ok"] is False, "an output off the list -> refused")


class Script:
    """A scripted model: per user turn, a list of ('call', name, args) / ('text', s)."""
    def __init__(self, turns):
        self.q, self.i = turns, 0

    def __call__(self, url, body, headers, hint):
        last = body["contents"][-1]
        if last["role"] == "user" and "text" in last["parts"][0]:
            self.cur = list(self.q[self.i])
            self.i += 1
        a = self.cur.pop(0)
        parts = [{"text": a[1]}] if a[0] == "text" else [{"functionCall": {"name": a[1], "args": a[2]}}]
        return 200, json.dumps({"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": parts}}],
                                "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 10, "totalTokenCount": 110},
                                "modelVersion": "gemini-3.1-flash-lite"}), {}


sec("converse: one conversation, state carried across user turns")
import hashlib  # noqa: E402
pid = "p" + hashlib.sha256(Path(one).read_bytes()).hexdigest()[:6]
cap = lambda w: ("call", "pf_write", {"kind": "caption", "register": "direct", "language": "ko", "about": pid, "items": [{"text": w}]})  # noqa: E731
sc = Script([[("call", "pf_show", {}), ("call", "pf_photos", {"paths": [one]}), cap("웅덩이"), ("text", "A안: 웅덩이")],
             [("call", "pf_choose", {"option": "다시 시도"}), cap("새싹"), ("text", "B: 새싹")],
             [("text", "커밋은 호스트가 할 일입니다.")]])
recs = loop.converse([{"n": 1, "text": "사진에 붙일 단어 하나", "images": [one]}, {"n": 2, "text": "다시 시도"}, {"n": 3, "text": "커밋해줘"}], transport=sc, sleep=lambda s: None)
ok([[c["tool"] for c in r_["calls"]] for r_ in recs] == [["pf_show", "pf_photos", "pf_write"], ["pf_choose", "pf_write"], []], "per-turn calls recorded; the repo request calls no tool")
ok(all(r_["stop"] == "answered" for r_ in recs) and not any(c["offlist"] for r_ in recs for c in r_["calls"]), "each turn ends in an answer; no off-list call")
texts = [t["text"] for t in PF.state()["texts"]]
ok("웅덩이" in texts and "새싹" in texts, "state carried: both captions are in the workspace")

sec("proposals 1-4 (design-set fixes) and the H3 colour nudge")
from gmg import turn  # noqa: E402
r = PF.call("pf_write", {"kind": "storyline", "register": "direct", "language": "ko", "items": [{"text": "다음 쪽은 스타일."}]})
ok(r["ok"] is False and r["next"][0]["tool"] == "pf_pages", "P1: a storyline is page flow -> pf_pages, not pf_write")
r = PF.call("pf_write", {"kind": "sector", "register": "direct", "language": "ko", "items": [{"text": "검정과 베이지."}]})
ok(r["ok"] is False and r["next"][0]["tool"] == "pf_photos", "P1: a photo-based kind without a measured photo -> measure it first")
r = PF.call("pf_write", {"kind": "sector", "register": "direct", "language": "ko", "about": pid, "items": [{"text": "검정과 베이지."}]})
ok(r["ok"], "P1: with a measured photo id it is accepted")
turn.record("다시 시도")
o = ext_mcp_handle("pf_write", {"kind": "answer", "register": "direct", "language": "ko", "items": [{"text": "다시 쓴 답."}]})
ok(o["ok"] is False and o["next"][0]["tool"] == "pf_choose", "P3: after a terse reply, any other pf tool is redirected to pf_choose")
ext_mcp_handle("pf_choose", {"option": "다시 시도"})
o = ext_mcp_handle("pf_write", {"kind": "answer", "register": "direct", "language": "ko", "items": [{"text": "다시 쓴 답."}]})
ok(o["ok"], "P3: once pf_choose resolved it, the turn goes on")
turn.record("이 사진으로 SECTOR A를 써라\n[attached: " + two + "]")
o = ext_mcp_handle("pf_show", {})
ok(o.get("unmeasured_images") == [] or o.get("unmeasured_images") is None or o["next"][0]["tool"] == "pf_photos", "P2: attached images are checked against the measured ones")
fresh = img("fresh", (90, 40, 40), [(150, 100, 20, (240, 240, 200))])
turn.record("이 사진은? [attached: " + fresh + "]")
o = ext_mcp_handle("pf_show", {})
ok(o.get("unmeasured_images") == [fresh] and o["next"][0]["tool"] == "pf_photos", "P2: an attached, unmeasured image is listed and pf_photos comes first")
turn.record("다음")
st0 = PF.call("pf_write", {"kind": "answer", "register": "direct", "language": "ko", "items": [{"text": "좋은 패션은 몸에 맞는 옷이다."}]})["texts"][0]["id"]
r = PF.call("pf_revise", {"op": "refocus", "arg": "style", "targets": [st0], "texts": ["좋은 스타일은 몸에 맞게 고른 옷과 신발이다."]})
ok(r["ok"], "P4: refocus on 'style' accepts a Korean text about 스타일")
r = PF.call("pf_revise", {"op": "widen_categories", "arg": "hair, eyewear, shoes", "targets": ["last"], "texts": ["머리, 안경, 신발까지 본다."]})
ok(r["ok"], "P4: widen with English category names accepts the Korean words")
pal = [{"hex": "#e0e0e0", "name": "a"}, {"hex": "#e5e5e5", "name": "b"}, {"hex": "#202020", "name": "c"}, {"hex": "#252525", "name": "d"}, {"hex": "#c0392b", "name": "e"}]
ch = agent._nudge(pal)
rgbs = [[int(x["hex"][i:i + 2], 16) for i in (1, 3, 5)] for x in pal]
ok(len(ch) == 2 and all(sum((a - b) ** 2 for a, b in zip(rgbs[i], rgbs[j])) ** .5 >= 30 for i in range(5) for j in range(i + 1, 5)),
   f"H3: near-identical colours are pushed apart by code ({ch})")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("all passed" if not FAIL else f"{len(FAIL)} failed"))
sys.exit(1 if FAIL else 0)
