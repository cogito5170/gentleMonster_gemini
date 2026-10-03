"""GMG3 conversation replay: flash-lite picks every tool across a run of real user questions.

    python3 bench/gmg3/replay.py design [--q 4,22,23]    # design set (tuning allowed)
    python3 bench/gmg3/replay.py eval                    # questions 32-42, pre-registered in eval.json

Each question's path and state are scored by code (`check_*` implement eval.json's `expected_state`, verbatim).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))


def questions_md() -> dict:
    q = subprocess.run(["git", "-C", os.environ.get("GMG_UPSTREAM", ""), "show", "35073f7:docs/portfolio/questions.md"], capture_output=True, text=True).stdout
    b = re.split(r"\n### (\d+)\. ", q)
    out = {}
    for i in range(1, len(b), 2):
        m = re.search(r"\n> (.*?)(?:\n\n→|\n\n<details>)", b[i + 1], re.S)
        if m:
            out[int(b[i])] = "\n".join(l[2:] if l.startswith("> ") else l.lstrip(">") for l in m.group(1).split("\n")).strip()
    return out


DESIGN_ATT = {4: [f"images/library/{n}.jpg" for n in ("L1_night_red_light", "L2_puddle_reflection", "L3_sprout_sand", "L4_string_lights_bw", "L5_sunset_sea")],
              22: ["images/design/q22_cover_draft.jpg"], 23: ["images/design/q23_notes.jpg"], 26: ["images/library/L6_cloudy_parking.jpg"]}


# ------------------------------------------------------------------ expected-state checks (eval.json, as registered)
CATS = [r"머리|헤어|hair", r"안경|eyewear|glasses", r"옷|clothes", r"신발|shoes", r"액세서리|악세사리|accessor", r"색|colou?r", r"향|scent"]


def _new(before, after, key):
    ids = {x["id"] for x in before[key]}
    return [x for x in after[key] if x["id"] not in ids]


def check(n, before, after) -> "tuple[bool, str]":
    nt = _new(before, after, "texts")
    npr = _new(before, after, "proposals")
    if n == 32:
        a = [t for t in nt if t["kind"] == "answer"]
        return len(a) >= 3, f"{len(a)} new answers"
    if n == 33:
        a = [t for t in nt if t.get("op") == "more_direct"]
        par = {t["id"]: t for t in after["texts"]}
        okk = all(t["measures"]["abstract_ratio"] <= par[t["parent"]].get("measures", {}).get("abstract_ratio", 1) for t in a)
        return bool(a) and okk, f"{len(a)} more_direct revisions"
    if n in (34,):
        return any(len(p["options"]) == 3 for p in npr), f"{len(npr)} new proposal sets"
    if n == 35:
        a = [t for t in nt if t.get("op") == "refocus"]
        return bool(a) and all(re.search("스타일|style", t["text"], re.I) for t in a), f"{len(a)} refocus revisions"
    if n == 36:
        retried = len([e for e in after["_events"] if e["kind"] == "RETRY"]) > len([e for e in before["_events"] if e["kind"] == "RETRY"])
        old = {t["text"] for t in before["texts"]}
        return retried and any(t["text"] not in old for t in nt), f"retry {'recorded' if retried else 'NOT recorded'}, {len(nt)} new texts"
    if n == 37:
        a = [t for t in nt if t.get("op") == "widen_categories"]
        return bool(a) and all(sum(bool(re.search(c, t["text"], re.I)) for c in CATS) >= 4 for t in a), f"{len(a)} widened"
    if n == 38:
        adopted = len(after["adopted"]) > len(before["adopted"])
        return adopted and any(len(p["options"]) == 3 for p in npr), f"adoption {'recorded' if adopted else 'NOT recorded'}, {len(npr)} new proposal sets"
    if n == 39:
        ph = [p for p in after["photos"] if p["file"] == "q39_style.jpg"]
        cols = {c.lower() for p in ph for c in p["colors"]}
        return bool(ph) and any(any(c in t["text"].lower() for c in cols) for t in nt), f"measured: {bool(ph)}, texts citing a measured colour: {sum(any(c in t['text'].lower() for c in cols) for t in nt)}"
    if n == 40:
        same = len(after["_events"]) == len(before["_events"])
        return same, "no workspace change" if same else f"{len(after['_events']) - len(before['_events'])} new events"
    if n == 41:
        return len(after["pages"]) >= 4 and any(len(p["options"]) == 3 for p in npr), f"{len(after['pages'])} pages, {len(npr)} new proposal sets"
    if n == 42:
        nr = _new(before, after, "rankings")
        return any(len(r["order"]) >= 3 for r in nr), f"{len(nr)} new rankings"
    return True, "(design question: not scored)"


def path_ok(called, req, allowed) -> bool:
    c = set(called)
    return set(req) <= c and c <= set(req) | set(allowed)


def snapshot():
    from gmg import portfolio as PF
    st = PF.state()
    st["_events"] = PF._ws().events()
    return st


def main():
    which = sys.argv[1]
    only = [int(x) for x in sys.argv[sys.argv.index("--q") + 1].split(",")] if "--q" in sys.argv else None
    out = HERE / ("results_" + which)
    out.mkdir(exist_ok=True)
    os.environ["GMG_OUT"] = str(out / "work")
    from gmg import loop, portfolio as PF, upstream
    upstream.load()
    if which == "eval":
        ev = json.loads((HERE / "eval.json").read_text())["questions"]
        PF.seed(json.loads((HERE / "seed.json").read_text()), HERE)
        qs = [{"n": q["n"], "text": q["text"], "images": [str(HERE / a) for a in q["attachments"]], "req": q["required"], "allowed": q["allowed"]} for q in ev]
    else:
        Q = questions_md()
        qs = [{"n": n, "text": Q[n], "images": [str(HERE / a) for a in DESIGN_ATT.get(n, [])]} for n in (only or [4, 22, 23, 24, 25, 26, 27, 28])]
    rows, res, t0, contents = [], [], time.time(), []
    snaps = [snapshot()]
    for q in qs:                                     # one conversation; a workspace snapshot after every question
        res.append(loop.user_turn(contents, q, log=lambda m: print("  " + m, flush=True)))
        snaps.append(snapshot())
    for q, r, b, a in zip(qs, res, snaps[:-1], snaps[1:]):
        called = [c["tool"] for c in r["calls"]]
        ok_state, why = check(q["n"], b, a) if which == "eval" else (None, "")
        usage = [t["usage"] for t in r["turns"] if "usage" in t]
        rows.append({"n": q["n"], "called": called, "path_ok": path_ok(called, q.get("req", []), q.get("allowed", [])) if which == "eval" else None,
                     "state_ok": ok_state, "state": why, "errors": sum(1 for c in r["calls"] if c["ok"] is False),
                     "offlist": sum(1 for c in r["calls"] if c["offlist"]), "model_turns": len(usage),
                     "tokens": sum(u.get("totalTokenCount", 0) for u in usage), "prompt_tokens": sum(u.get("promptTokenCount", 0) for u in usage),
                     "quota_waits": sum(1 for t in r["turns"] if t.get("http") == 429), "seconds": r["seconds"], "stop": r["stop"],
                     "reported": sorted({t.get("reported") for t in r["turns"] if t.get("reported")}), "final": r["final"][:1500],
                     "problems": [p for c in r["calls"] for p in c["problems"]][:8]})
        print(f"[{which}] q{q['n']}: {called} path_ok={rows[-1]['path_ok']} state_ok={ok_state} ({why}) errors={rows[-1]['errors']} tokens={rows[-1]['tokens']}", flush=True)
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    (out / "transcript.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    (out / "state.json").write_text(json.dumps({k: v for k, v in snaps[-1].items() if k != "_events"}, ensure_ascii=False, indent=1))
    print(f"[{which}] {round(time.time() - t0)} s")


if __name__ == "__main__":
    main()
