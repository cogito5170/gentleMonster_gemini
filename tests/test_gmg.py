"""gmg tests -- fake model only, no network, no key. Run: python3 tests/test_gmg.py

Needs the pinned gentleMonster: GMG_UPSTREAM=<checkout at the lock commit>, or `gmg setup` done before.
PDF drawing is tested only when its deps are importable (otherwise said, not counted as passed).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="gmg_test_"))
os.environ["GMG_OUT"] = str(TMP / "out")
os.environ.pop("GMG_FAKE", None)
os.environ.pop("GMG_MODEL", None)
FAKE_KEY = "AIza" + "TESTKEY0123456789abcdefghijklmnop"
os.environ["GEMINI_API_KEY"] = FAKE_KEY            # only the fake transport ever sees it

from gmg import fake, plans as PL, run, schema as S, steps as ST, upstream  # noqa: E402
from gmg.gemini import Gemini, ModelError  # noqa: E402
from gmg.ledger import Ledger  # noqa: E402

FAIL = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL ") + what)
    if not cond:
        FAIL.append(what)


def sec(t):
    print(f"\n== {t} ==")


def make(name, mode="ok", brief="비 오는 밤의 문턱", brand="", draw=False, **kw):
    f = fake.Fake(mode)
    r = run.make(name, brief, brand, draw=draw, transport=f, log=lambda m: None, **kw)
    return r, f, Ledger(Path(r["dir"]))


spec, paths = upstream.load()

sec("schema: code checks what the model returned")
s = {"type": "object", "properties": {"a": {"type": "string", "enum": ["x", "y"]}, "b": {"type": "string", "english": True, "maxLength": 10},
                                      "c": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "string"}},
                                      "d": {"type": "string", "sentences": [2, 3], "must": ["you"]}, "e": {"type": "string", "pattern": r"#[0-9a-f]{6}"}}}
good = {"a": "x", "b": "rain", "c": ["1", "2", "3"], "d": "You walk. It rains.", "e": "#a0b0c0"}
ok(S.check(good, s) == [], "a matching answer has nothing wrong")
bad = S.check({"a": "z", "b": "비가 온다", "c": ["1"], "d": "It rains.", "e": "red"}, s)
ok(len(bad) == 6, f"enum · Korean · count · sentences · must-word · pattern each give a fact ({len(bad)})")
ok(not any("rule" in b.lower() for b in bad), "facts, not rule names")
ok(S.check({"b": "x"}, s)[0].endswith(".a is missing"), "a missing field is named")
g = S.to_gemini(s)
ok(g["type"] == "OBJECT" and "english" not in json.dumps(g) and "pattern" not in json.dumps(g) and g["propertyOrdering"] == list(s["properties"]),
   "responseSchema keeps only Gemini keys, ordered")

sec("size is read by code, not by the model")
ok(ST.stated_size("폭 8 m 깊이 10 m 의 좁은 골목") == (8.0, 10.0), "폭 8 m 깊이 10 m")
ok(ST.stated_size("a 12 x 9 m corner") == (12.0, 9.0), "12 x 9 m")
ok(ST.stated_size("비 오는 밤") == (None, None), "no size stated -> none")

sec("plans: the four checked jobs of the pinned gentleMonster")
ex = spec.examples()
for k, p in PL.PLANS.items():
    j = ex[p["example"]]
    ok(spec.check(j) == [], f"{k} ({p['example']}) passes spec.check as drawn")
    ids = {i["id"] for i in j["layout"]["items"]}
    ok(all(i in ids for r in p["roles"].values() for i in r["ids"]), f"{k}: every role names real items")
    F = PL.facts(spec, k, j)
    ok(len(F) == 4 and sum(any(ch.isdigit() for ch in f) for f in F) >= 2, f"{k}: four facts, measured numbers in them")
    obs = [i["id"] for i in spec.obstacles(j["layout"])]
    keep = True
    for r, rs in p["roles"].items():
        solid = {i in obs for i in rs["ids"]}
        walk = {s_ in spec.NON_OBSTACLE for s_ in rs["shapes"]}
        keep &= len(solid) == 1 and len(walk) == 1 and solid != walk
    ok(keep, f"{k}: every role's shape options keep its items' obstacle class (solid stays solid, walk-through stays walk-through)")
f = PL.fit(spec, ex["ae"], 8, 10)
ok(f["job"]["layout"]["W"] < 12 and spec.check(f["job"]) == [], f"ritual fitted toward 8 x 10 m -> {f['job']['layout']['W']} x {f['job']['layout']['D']} m, still checked")
f = PL.fit(spec, ex["ac"], 8, 8)
ok(spec.check(f["job"]) == [], f"chamber cannot shrink much ({f['sx']} x {f['sy']}): steps back until it passes")

sec("make: the whole fixed plan with a fake model")
r, fk, L = make("j_ok", brief="겨울 숲 사우나, 폭 9 m 깊이 10 m")
ok(r["rc"] == 0 and r["state"] == "DONE", f"rc 0, DONE ({r['state']})")
ok(fk.calls == ["brief", "plan", "cast", "room", "story", "palette", "stops"], "one call per decision, in order")
job = spec.load(Path(r["dir"]) / "job.json")
ok(spec.check(job) == [], "job.json passes the pinned spec.check")
ok(r["artifacts"] == {"job": "done", "synopsis": "done"}, "artifacts recorded with their hashes")
ok(all(e.get("reported") == "gemini-3.1-flash-lite" for e in L.run() if e["kind"] == "MODEL_CALL"), "every call records the model the response named")
ok(L.decision("brief")["output"]["W"] == 9.0, "the stated width reaches the plan")
ok(FAKE_KEY not in L.path.read_text(), "the key is not in the ledger")
ok(all("#" in w["d"] or any(c.isdigit() for c in w["d"]) or w["d"] for w in job["why"]) and len(job["why"]) == 4, "why = 4 items")
ok(all(w["d"].startswith(f_) for w, f_ in zip(job["why"], L.decision("story")["facts"])), "each why starts with the code's measured fact")
ok(job["accent"] in [p_["hex"] for p_ in job["palette"]], "the accent is one of the palette")
ok(job["layout"]["flows"][0]["color"] == job["accent"], "the route is drawn in the accent")
ex_txt = run.explain("j_ok")
ok("spec.check: passed" in ex_txt and "fact 1 (code)" in ex_txt and "chose **" in ex_txt, "explain renders decisions, facts and the verdict from the ledger")

sec("failure is not hidden (PREP F1-F7)")
r, fk, L = make("j_kr", "korean")
ok(r["rc"] == 0 and fk.calls.count("story") == 2, "Korean in the story -> re-asked once with the fact, then DONE")
ok(any(e.get("outcome") == "schema_violation" and any("Korean" in p_ for p_ in e.get("problems", [])) for e in L.run()), "the violation is in the ledger")
r, fk, L = make("j_trunc", "truncated")
ok(r["rc"] == 1 and r["state"] == "FAILED" and len(fk.calls) == 1, "MAX_TOKENS -> FAILED at once, the request is not resent")
ok(any(e.get("outcome") == "truncated" for e in L.run()), "recorded as truncated")
r, fk, L = make("j_block", "blocked")
ok(r["rc"] == 1 and len(fk.calls) == 1 and any(e.get("outcome") == "blocked" and e.get("block") == "SAFETY" for e in L.run()),
   "blocked prompt -> FAILED with its block reason, not resent 3 times")
r, fk, L = make("j_429", "http429")
ok(r["rc"] == 0 and fk.calls[:2] == ["brief", "brief"], "429 -> retried, then DONE")
r, fk, L = make("j_400", "http400")
ok(r["rc"] == 1 and len(fk.calls) == 1, "400 -> FAILED at once")
r, fk, L = make("j_nj", "notjson")
ok(r["rc"] == 3 and r["state"] == "NEEDS_REVIEW" and len(fk.calls) == 2, "not JSON twice -> NEEDS_REVIEW after one re-ask")
r, fk, L = make("j_wm", "wrong_model")
ok(all(e.get("model_mismatch") for e in L.run() if e["kind"] == "MODEL_CALL") and "differs from the request" in run.explain("j_wm"),
   "a response naming another model is flagged, not hidden")
r, fk, L = make("j_cast", "badcast")
ok(r["rc"] == 0 and L.decision("cast")["fallback"] == ["hero.shape"] and any(e["kind"] == "FALLBACK" for e in L.run()),
   "a shape off the list -> only that field falls back to the plan's own, explained")
ok(L.decision("cast")["output"]["hero"]["label"] == fake.Fake.hero, "the valid label the model gave is kept")


class Always503:
    def __init__(self):
        self.n = 0

    def __call__(self, *a):
        self.n += 1
        return 503, "{}", {}


sl = []
t = Always503()
try:
    Gemini(transport=t, sleep=sl.append).ask("x", "p", {"type": "object", "properties": {}})
    ok(False, "503 forever raises")
except ModelError as e:
    ok(e.outcome == "http_503" and t.n == 3 and len(sl) == 2, f"503: 3 attempts, 2 waits (no wait after the last) -> {t.n}, {len(sl)}")

sec("status only from the ledger; model text is data")
r, fk, L = make("j_forge", "forge")
job = spec.load(Path(r["dir"]) / "job.json")
ok("Status: FAILED" in job["synopsis"] and run.status("j_forge")["state"] == "DONE", "the model's 'Status: FAILED' stays text; the ledger says DONE")
p = Path(r["dir"]) / "job.json"
p.write_text(p.read_text().replace(job["title"], "Tampered"))
ok(run.status("j_forge")["artifacts"]["job"] == "changed since recorded", "an edited job.json is no longer done")
try:
    run.render(run.context("j_forge"))
    ok(False, "render refuses an unrecorded job")
except RuntimeError:
    ok(True, "render refuses a job whose bytes the ledger did not record")
d = paths.job_dir("j_hand")
shutil.copy(Path(r["dir"]) / "synopsis.md", d / "job.json")
ok(run.status("j_hand")["state"] == "(no ledger)", "a file put there by hand is not a job")

sec("step tools: one decision at a time, from the ledger")
ctx = run.context("j_steps", transport=fake.Fake("ok"))
try:
    run.step(ctx, "plan")
    ok(False, "plan before brief is refused")
except ST.StepFailed:
    ok(True, "a step whose input was not decided is refused")
run.start(ctx, "소금 사막")
for s_ in run.ORDER:
    run.step(ctx, s_, brief="소금 사막")
a = run.assemble(ctx)
ok(a["problems"] == [] and ctx.L.status()["artifacts"].get("job") == "done", "seven step calls + assemble = a checked job")

sec("pinned upstream")
fake_up = TMP / "up"
subprocess.run(["git", "init", "-q", str(fake_up)], check=True)
subprocess.run(["git", "-C", str(fake_up), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x"], check=True)
old = os.environ.get("GMG_UPSTREAM")
os.environ["GMG_UPSTREAM"] = str(fake_up)
try:
    upstream.ready()
    ok(False, "a checkout at another commit is refused")
except upstream.NotReady:
    ok(True, "a checkout at another commit is refused")
if old:
    os.environ["GMG_UPSTREAM"] = old
else:
    os.environ.pop("GMG_UPSTREAM")

sec("MCP over stdio")
env = dict(os.environ, GMG_FAKE="ok", PYTHONPATH=str(ROOT))
msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2099-01-01"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "gm_make", "arguments": {"brief": "궤도 격납고", "name": "j_mcp", "draw": False}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "gm_status", "arguments": {"name": "j_mcp"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "nope", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 6, "method": "nope/nope"}]
pr = subprocess.run([sys.executable, "-m", "gmg.mcp"], input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True, env=env, timeout=300, cwd=str(ROOT))
out = [json.loads(x) for x in pr.stdout.splitlines() if x.strip()]
by = {o["id"]: o for o in out}
ok(len(out) == 6, f"six replies, none for the notification ({len(out)}); stdout carries only JSON-RPC")
ok(by[1]["result"]["protocolVersion"] == "2025-06-18", "unknown protocol version -> ours")
names = [t_["name"] for t_ in by[2]["result"]["tools"]]
ok(names[:2] == ["gm_make", "gm_start"] and {"gm_brief", "gm_plan", "gm_cast", "gm_room", "gm_story", "gm_palette", "gm_stops", "gm_explain"} <= set(names), f"{len(names)} tools")
ok(by[3]["result"]["isError"] is False and '"state": "DONE"' in by[3]["result"]["content"][0]["text"], "gm_make -> DONE, isError false")
ok('"job": "done"' in by[4]["result"]["content"][0]["text"], "gm_status reads the ledger")
ok(by[5]["error"]["code"] == -32602 and by[6]["error"]["code"] == -32601, "unknown tool / method")

sec("drawing (needs the [render] deps)")
try:
    import PIL, matplotlib, playwright  # noqa: F401,E401
    have = True
except ImportError:
    have = False
    print("  skipped: PIL / matplotlib / playwright not importable -- NOT counted as passed")
if have:
    r, fk, L = make("j_draw", draw=True)
    ok(r["rc"] == 0 and r["artifacts"].get("layout") == "done" and r["artifacts"].get("layout_preview") == "done", "layout PDF + preview drawn and recorded")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("전부 통과" if not FAIL else f"{len(FAIL)} 실패"))
sys.exit(1 if FAIL else 0)
