"""The declarative state checks (replay.check_spec) agree with the registered GMG3 checks (replay.check) on 32-42."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench" / "gmg3"))
import replay  # noqa: E402

CATS = replay.CATS
SPEC = {32: [{"texts": {"kind": "answer"}, "min": 3}],
        34: [{"proposals": 3}],
        35: [{"texts": {"op": "refocus"}, "contains_any": ["스타일|style"]}],
        36: [{"retry": True}, {"texts": {}}],
        37: [{"texts": {"op": "widen_categories"}, "names_min": {"words": CATS, "k": 4}}],
        38: [{"adopted": True}, {"proposals": 3}],
        39: [{"photo": "q39_style.jpg", "cites_colour": True}, {"texts": {}}],
        41: [{"pages_min": 4}, {"proposals": 3}],
        42: [{"ranking_min": 3}]}
FAIL = []


def ok(c, what):
    print(("  ok  " if c else "  FAIL ") + what)
    if not c:
        FAIL.append(what)


B = {"texts": [{"id": "t1", "kind": "answer", "text": "옷", "measures": {"abstract_ratio": 0.1}}], "proposals": [], "adopted": [], "pages": {"1": {}},
     "rankings": [], "photos": [], "_events": [{"kind": "TEXT"}]}


def after(**kw):
    a = copy.deepcopy(B)
    for k, v in kw.items():
        a[k] = a[k] + v if isinstance(a[k], list) else v
    return a


cases = {
    32: [after(texts=[{"id": f"t{i}", "kind": "answer", "text": "x"} for i in (2, 3, 4)]), after(texts=[{"id": "t2", "kind": "answer", "text": "x"}])],
    34: [after(proposals=[{"id": "q1", "options": [1, 2, 3]}]), after(proposals=[{"id": "q1", "options": [1, 2]}])],
    35: [after(texts=[{"id": "t2", "op": "refocus", "text": "스타일은"}]), after(texts=[{"id": "t2", "op": "refocus", "text": "패션은"}])],
    36: [after(_events=[{"kind": "RETRY"}], texts=[{"id": "t2", "text": "새 글"}]), after(texts=[{"id": "t2", "text": "새 글"}])],
    37: [after(texts=[{"id": "t2", "op": "widen_categories", "text": "머리, 안경, 옷, 신발"}]), after(texts=[{"id": "t2", "op": "widen_categories", "text": "머리, 옷"}])],
    38: [after(adopted=[{"x": 1}], proposals=[{"id": "q1", "options": [1, 2, 3]}]), after(proposals=[{"id": "q1", "options": [1, 2, 3]}])],
    39: [after(photos=[{"file": "q39_style.jpg", "colors": ["#112233"]}], texts=[{"id": "t2", "text": "검정 #112233"}]),
         after(photos=[{"file": "q39_style.jpg", "colors": ["#112233"]}], texts=[{"id": "t2", "text": "검정"}])],
    41: [after(pages={"1": {}, "2": {}, "3": {}, "4": {}}, proposals=[{"id": "q1", "options": [1, 2, 3]}]), after(proposals=[{"id": "q1", "options": [1, 2, 3]}])],
    42: [after(rankings=[{"id": "r1", "order": [1, 2, 3]}]), after(rankings=[{"id": "r1", "order": [1, 2]}])],
}
for n, (good, bad) in cases.items():
    for a, want in ((good, True), (bad, False)):
        c, s = replay.check(n, B, a)[0], replay.check_spec(SPEC[n], B, a)[0]
        ok(c == s == want, f"q{n}: registered check {c}, declarative {s}, expected {want}")
ok(replay.check_spec([{"unchanged": True}], B, after(_events=[{"kind": "SERVED"}]))[0], "unchanged: a SERVED record is not a workspace change")
ok(not replay.check_spec([{"unchanged": True}], B, after(_events=[{"kind": "TEXT"}]))[0], "unchanged: any other event is")
ok(not replay.check_spec([{"nonsense": 1}], B, B)[0], "an unknown condition fails, it is never skipped")
print("\n" + ("all passed" if not FAIL else f"{len(FAIL)} failed"))
sys.exit(1 if FAIL else 0)
