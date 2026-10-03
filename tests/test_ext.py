"""Extension tests -- fake agent only, no network, no key. Run: python3 tests/test_ext.py
Needs the pinned gentleMonster (GMG_UPSTREAM=<checkout at the lock commit>, or `gmg setup` done before)."""
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
TMP = Path(tempfile.mkdtemp(prefix="gmg_ext_"))
os.environ["GMG_OUT"] = str(TMP / "out")
os.environ["GEMINI_API_KEY"] = "AIza" + "TESTKEY0123456789abcdefghijklmnop"

from gmg import agent, ext_mcp, hook, loop, upstream  # noqa: E402
from gmg.fake_agent import FakeAgent  # noqa: E402
from gmg.ledger import Ledger  # noqa: E402

FAIL = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL ") + what)
    if not cond:
        FAIL.append(what)


def sec(t):
    print(f"\n== {t} ==")


spec, paths = upstream.load()
REQ = "Design a store with gentleMonster.\nBrief: 비 오는 밤의 문턱, 폭 14 m 깊이 12 m\nBrand: Gentle Monster"

sec("manifest, hook config, GEMINI.md")
man = json.loads((ROOT / "gemini-extension.json").read_text())
ok(man["contextFileName"] == "GEMINI.md" and "server.py" in "".join(man["mcpServers"]["gentlemonster"]["args"]), "manifest names GEMINI.md and server.py")
hk = json.loads((ROOT / "hooks" / "hooks.json").read_text())
ok("verdict_gate.py" in hk["hooks"]["AfterAgent"][0]["hooks"][0]["command"] and "turn_note.py" in hk["hooks"]["BeforeAgent"][0]["hooks"][0]["command"],
   "AfterAgent and BeforeAgent hooks configured")
g = (ROOT / "GEMINI.md").read_text()
ok(len(g) < 1600 and "next" in g and "gm_new" in g and "pf_show" in g, f"GEMINI.md is short ({len(g)} chars), says: follow next, and routes")

sec("tools: few, Gemini-declarable")
T = ext_mcp.tools()
ok([t["name"] for t in T][:6] == ["gm_new", "gm_plan", "gm_cast", "gm_story", "gm_finish", "gm_explain"] and len(T) == 16, f"{len(T)} tools, the store chain first")
D = loop.declarations()
ok(all(d["parameters"]["type"] == "OBJECT" for d in D) and "maxLength" not in json.dumps(D), "declarations use only keys Gemini takes")

sec("the state machine, one call at a time")
r = agent.call("gm_plan", {"job": "gm-00000000", "plan": "orbit"})
ok(r["ok"] is False and r["next"][0]["tool"] == "gm_new", "a call out of order says what to call instead")
r = agent.call("gm_new", {"request": REQ, "brand": "Gentle Monster", "theme": "A quiet threshold.", "mood": "quiet", "hero_idea": "pool", "product": "eyewear"})
ok(r["ok"] is False and "mood" in r["problems"][0], "one mood word -> ok:false with the fact, gm_new again")
new = dict(request=REQ, brand="Gentle Monster", theme="A threshold where the rain is switched off.", mood=["quiet", "wet", "dark"],
           hero_idea="a black pool", product="fragrance")
r = agent.call("gm_new", new)
job = r["job"]
ok(r["ok"] and r["size_m"] == [14.0, 12.0] and r["product"] == "eyewear" and any("sells eyewear" in n for n in r["notes"]),
   "size read by code; a named known brand's product set by code, said in notes")
rx = agent.call("gm_new", dict(new, request="겨울 사우나 니트웨어 매장", brand="", product="fashion"))
ok(rx["brand"] == "Gentle Monster" and rx["product"] == "fashion" and not rx["notes"], "no brand named: default brand, and the brief's product is kept")
rx = agent.call("gm_new", dict(new, request="제주 매장, 책 대신 향", brand="Aesop", product="fragrance"))
ok(rx["brand"] == "Aesop" and rx["product"] == "fragrance" and any("not in the request text" in n for n in rx["notes"]),
   "a named brand is kept even if the request text the agent passed lacks it (said in notes); Aesop may sell fragrance")
ok([n["tool"] for n in r["next"]] == ["gm_plan"] and r["next"][0]["args"]["plan"] == ["orbit", "field", "chamber", "ritual"], "next = gm_plan with its 4 options")
r2 = agent.call("gm_new", new)
ok(r2 == r and sum(1 for e in Ledger(paths.job_dir(job)).events() if e["kind"] == "START") == 1, "the same gm_new again: same result, no new run")

job = agent.call("gm_new", new)["job"]
r = agent.call("gm_plan", {"job": job, "plan": "maze"})
ok(r["ok"] is False and r["next"][0]["tool"] == "gm_plan", "a plan off the list -> ok:false, the options again")
r = agent.call("gm_story", {"job": job, "title": "x"})
ok(r["ok"] is False and r["next"][0]["tool"] == "gm_plan" and r["next"][0]["args"]["plan"], "a step too early -> the first undecided step, with its full options")
r = agent.call("gm_plan", {"job": job, "plan": "orbit"})
ok(r["ok"] and r["next"][0]["tool"] == "gm_cast" and "hero" in r["next"][0]["roles"], "plan -> cast with its roles and options")
cast_next = r["next"][0]
roles = [{"role": k, "shape": v["shape"][0], "material": "steel", "label": f"{k} thing"} for k, v in cast_next["roles"].items()]
roles = [x for x in roles if x["role"] != "ring"] + [{"role": "hero", "shape": "door", "material": "steel", "label": "black pool"}]
roles = [x for x in roles if not (x["role"] == "hero" and x["shape"] != "door")]
r = agent.call("gm_cast", {"job": job, "roles": roles, "room": {"floor": "black_stone", "wall": "concrete", "ceiling": "black_stone", "light": "dark_gallery", "fog": "light"}})
ok(r["ok"] and any(n.startswith("hero: used the plan's own shape") for n in r["notes"]) and any("ring" in n and "not given" in n for n in r["notes"]),
   "a shape off the list and a missing role are filled from the plan and said in notes")
facts = r["next"][0]["facts"]
ok(len(facts) == 4 and "black pool" in facts[1], "the facts are measured and use the agent's labels")
bad = agent.call("gm_story", {"job": job, "title": "비", "subtitle": "s", "line": "One. Two.", "synopsis": "It rains.", "keywords": ["a", "a", "b"], "quote": "q", "why": ["x"]})
ok(bad["ok"] is False and len(bad["problems"]) >= 5 and bad["next"][0]["tool"] == "gm_story", f"bad story -> {len(bad['problems'])} facts, gm_story again")
long_title = "The Dry Threshold Where Rain Forgets To Fall Tonight"
r = agent.call("gm_story", {"job": job, "title": long_title, "subtitle": "Where the rain is switched off", "line": "The rain stops at the door.",
                            "synopsis": "You come in out of the rain. A black pool waits in the dark. You circle it.", "keywords": ["Threshold", "Held rain", "Silence"],
                            "quote": "Inside, only the light is wet.", "why": [{"t": "A dry gap", "d": "You slow down."}, {"t": "Only the pool moves", "d": "It is the only motion."},
                                                                           {"t": "Turn to choose", "d": "You turn to choose."}, {"t": "The desk ends it", "d": "It ends the walk."}]})
ok(r["ok"] and any("title" in n for n in r["notes"]), "an over-long title is cut by code (NORMALIZE), not sent back")
jw = json.loads(json.dumps(Ledger(paths.job_dir(job)).run()))
ok(next(e for e in reversed(jw) if e["kind"] == "DECISION" and e["step"] == "story")["output"]["why"][1]["t"] == "Only the pool moves", "why headlines are the agent's, not cut from the sentence")
fin = {"job": job, "palette": [{"hex": h, "name": n} for h, n in (("#121417", "Night"), ("#3a4148", "Wet"), ("#8d989f", "Steel"), ("#d8dde0", "Glow"), ("#c4422d", "Tail"))],
       "accent": "5", "material_names": ["A", "B", "C", "D"], "stops": [{"cap": "I step in.", "sub": "Quiet."}, {"cap": "I see it.", "sub": "Still."}, {"cap": "The end.", "sub": "Done."}]}
r = agent.call("gm_finish", fin)
ok(r["ok"] is False and any("stop 3 cap is not first person" in p for p in r["problems"]), "a caption not in the first person -> ok:false")
fin["stops"][2]["cap"] = "I choose my frames."
r = agent.call("gm_finish", fin)
ok(r["ok"] and r["verdict"] == "DONE" and r["say"].startswith(f"{job}: DONE"), "finish -> DONE, a `say` line from the ledger")
j = json.loads((paths.job_dir(job) / "job.json").read_text())
ok(spec.check(j) == [] and j["title"] != long_title and len(j["title"]) <= 40, "job.json passes the pinned spec.check; the title was cut")
n_end = sum(1 for e in Ledger(paths.job_dir(job)).run() if e["kind"] == "END")
r = agent.call("gm_finish", fin)
ok(r["verdict"] == "DONE" and sum(1 for e in Ledger(paths.job_dir(job)).run() if e["kind"] == "END") == n_end, "the same gm_finish again changes nothing")
agent.call("gm_plan", {"job": job, "plan": "field"})
st = agent.verdict(job)["verdict"]
full_story = {"job": job, "title": "T", "subtitle": "S", "line": "One line.", "synopsis": "You come in. You see the pool. You leave.",
              "keywords": ["a", "b", "c"], "quote": "Q", "why": [{"t": "One", "d": "One."}, {"t": "Two", "d": "Two."}, {"t": "Three", "d": "Three."}, {"t": "Four", "d": "Four."}]}
rs = agent.call("gm_story", full_story)
ok(st == "(reopened)" and rs["ok"] is False and rs["next"][0]["tool"] == "gm_cast", "re-deciding the plan reopens the job; a full story is refused until the new plan is cast")
ex = agent.call("gm_explain", {"job": job})
ok(ex["ok"] and any(l.startswith("fact 1 (measured by code)") for l in ex["explain"]) and any(l.startswith("fallback") for l in ex["explain"]),
   "gm_explain renders decisions, facts and fallbacks from the ledger")

sec("code repairs geometry a shape swap broke (b6, rev-2 run 2)")
narrow = dict(new, request="겨울 사우나 니트웨어, 폭 8 m 깊이 10 m", brand="", product="fashion")
jn = agent.call("gm_new", narrow)["job"]
cn = agent.call("gm_plan", {"job": jn, "plan": "ritual"})["next"][0]
rl = [{"role": k, "shape": ("box" if k == "hero" else v["shape"][0]), "material": "wood", "label": "stone stove" if k == "hero" else f"{k} wall"} for k, v in cn["roles"].items()]
agent.call("gm_cast", {"job": jn, "roles": rl, "room": {"floor": "wood", "wall": "wood", "ceiling": "wood", "light": "warm_spot", "fog": "light"}})
agent.call("gm_story", {"job": jn, "title": "Steam Alley", "subtitle": "A sauna", "line": "Warm wood.", "synopsis": "You come in from the cold. A stone stove waits. You circle it.",
                        "keywords": ["Warmth", "Steam", "Knit"], "quote": "Stay a while.", "why": [{"t": "Warm walls", "d": "One."}, {"t": "The stove", "d": "Two."}, {"t": "The loop", "d": "Three."}, {"t": "The counter", "d": "Four."}]})
fin2 = dict(fin, job=jn)
rv = agent.call("gm_finish", fin2)
evs = Ledger(paths.job_dir(jn)).run()
ok(rv["verdict"] == "DONE" and any(e["kind"] == "REPAIR" and "hero -> basin" in e["reverted"] for e in evs),
   "a box where the plan has a round basin breaks the 0.3 m clearance on the 8 m plan; code puts the basin back and says so")

sec("GMG4: plan in gm_new (H3), placeholders never reach a page (H1), the served model (H2)")
from gmg import served as SV  # noqa: E402
r = agent.call("gm_new", dict(new, request="H1 시험: 비 오는 밤", brand="(none named)", plan="orbit"))
ok(r["ok"] and r["brand"] == "Gentle Monster" and r.get("options") and any("placeholder" in n for n in r["notes"]), "a placeholder brand is not a brand: default, said, with closed options")
ok(r["next"][0]["tool"] == "gm_cast" and "built_m" in r, "plan given in gm_new: the next call is gm_cast (one turn fewer)")
jh = r["job"]
cn = r["next"][0]
agent.call("gm_cast", {"job": jh, "roles": [{"role": k, "shape": v["shape"][0], "material": "steel", "label": "TBD" if k == "hero" else f"{k} thing"} for k, v in cn["roles"].items()],
                       "room": {"floor": "concrete", "wall": "concrete", "ceiling": "concrete", "light": "dark_gallery", "fog": "none"}})
agent.call("gm_story", {"job": jh, "title": "T", "subtitle": "S", "line": "One line.", "synopsis": "You come in. You see the hero. You leave.",
                        "keywords": ["a", "b", "c"], "quote": "Q", "why": [{"t": "A", "d": "One."}, {"t": "B", "d": "Two."}, {"t": "C", "d": "Three."}, {"t": "D", "d": "Four."}]})
r = agent.call("gm_finish", dict(fin, job=jh))
ok(r["ok"] is False and any("hero label is placeholder text" in p for p in r["problems"]), "a placeholder label ('TBD') is refused at gm_finish, not printed")
fin3 = dict(fin, job=jh)
fin3["stops"] = [dict(x) for x in fin["stops"]]
fin3["stops"][1]["sub"] = "N/A"
r = agent.call("gm_finish", fin3)
ok(r["ok"] is False and any("stop 2 sub is placeholder" in p for p in r["problems"]), "a placeholder caption line is refused")
ok(agent.placeholder("(none named)") and agent.placeholder("") and agent.placeholder("없음") and not agent.placeholder("Gentle Monster"), "placeholder() knows filler from names")
fin4 = dict(fin, job=jh)
fin4["palette"] = [dict(x) for x in fin["palette"]]
fin4["palette"][4]["hex"] = "#E0E0E0,name:"
fin4["palette"][3]["hex"] = "grey"
r = agent.call("gm_finish", fin4)
ok(r["ok"] is False and any("colour 4 hex 'grey' is not #rrggbb" in p for p in r["problems"]) and not any("colour 5" in p for p in r["problems"]),
   "a garbled hex holding '#E0E0E0' is repaired by code; a hopeless one is named with its value (fresh-set f2 looped on a vague message)")
SV.record("gemini-3.5-flash-lite", "api")
r = agent.call("gm_explain", {"job": jh})
ok(any("served by gemini-3.5-flash-lite" in l and "NOT" in l for l in r["explain"]), "gm_explain shows the served model when it is not 3.1")
o = ext_mcp.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "pf_show", "arguments": {}}})
ok("served by gemini-3.5-flash-lite" in o["result"]["content"][0]["text"], "every tool result carries the served-model warning")
SV.record("gemini-3.1-flash-lite", "api")
o = ext_mcp.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "pf_show", "arguments": {}}})
ok('"served"' not in o["result"]["content"][0]["text"], "no warning when 3.1 served")
tp = TMP / "chat.jsonl"
tp.write_text(json.dumps({"sessionId": "x"}) + "\n" + json.dumps({"$set": {"messages": [{"type": "user"}, {"type": "gemini", "model": "gemini-3.5-flash-lite"}]}}) + "\n")
ok(SV.from_transcript(tp) == ["gemini-3.5-flash-lite"], "the served model is read from the CLI's chat recording")
w = hook.served({"transcript_path": str(tp)})
ok(w and "not gemini-3.1-flash-lite" in w and SV.latest()["source"] == "gemini-cli", "the hook records it and warns")
ok("could not be read" in hook.served({"transcript_path": str(TMP / "none.jsonl")}), "no transcript -> said, not counted as recorded")
SV.record("gemini-3.1-flash-lite", "api")
r = agent.call("gm_new", dict(new, request="H1 시험 2", brand="gentleMonster"))
ok(r["brand"] == "Gentle Monster" and any("read as" in n for n in r["notes"]), "'gentleMonster' is read as the known brand 'Gentle Monster'")

r = agent.call("gm_new", dict(new, request="Design a store with gentleMonster.\nBrief: 안개 낀 항구의 가방 팝업", brand="gentleMonster", product="objects"))
ok(r["brand"] == "Gentle Monster" and r["product"] == "objects", "the extension's name in the prompt is not a brand claim: the brief's product is kept")
ok(len(ext_mcp.tools("store")) == 8 and len(ext_mcp.tools("portfolio")) == 8 and all(t["name"].startswith("gm_") for t in ext_mcp.tools("store")),
   "two servers: store (gm_*) and portfolio (pf_*), 8 tools each")
ok(set(man["mcpServers"]) == {"gentlemonster", "gentlemonster-portfolio"} and "store" in man["mcpServers"]["gentlemonster"]["args"], "the manifest starts both servers")

sec("hook: the answer may only state the ledger's verdict")
out = TMP / "hk"
os.environ["GMG_OUT"] = str(out)
d = paths.OUT
ok(hook.decide({"prompt_response": "All checks passed."}, out) == {}, "no job -> pass")
L = Ledger(Path(out) / "gm-11111111")
L.log("START", job="gm-11111111")
L.log("END", state="NEEDS_REVIEW", rc=3)
ok(hook.decide({"prompt_response": "Here it is. All checks passed: DONE."}, out).get("decision") == "deny", "claims DONE, ledger NEEDS_REVIEW -> deny")
ok("systemMessage" in hook.decide({"prompt_response": "DONE", "stop_hook_active": True}, out), "again -> warning, no endless rewrite")
ok(hook.decide({"prompt_response": "gm-11111111: NEEDS_REVIEW -- spec.check: ..."}, out) == {}, "the ledger's own line -> pass")
ok(hook.decide({"prompt_response": "Here is your store."}, out) == {}, "no claim -> pass")
pr = subprocess.run([sys.executable, str(ROOT / "hooks" / "verdict_gate.py")], input=json.dumps({"prompt_response": "passed"}), capture_output=True, text=True,
                    env=dict(os.environ, GMG_OUT=str(out)), cwd=str(ROOT))
ok(json.loads(pr.stdout).get("decision") == "deny", "the hook script, as Gemini CLI runs it")
pr = subprocess.run([sys.executable, str(ROOT / "hooks" / "verdict_gate.py")], input="not json", capture_output=True, text=True, env=dict(os.environ, GMG_OUT=str(out)), cwd=str(ROOT))
ok("NOT checked" in json.loads(pr.stdout).get("systemMessage", ""), "a hook that cannot check says so; not counted as a pass")
os.environ["GMG_OUT"] = str(TMP / "out")

sec("the loop: a fake flash-lite picks every tool itself")
r = loop.run("비 오는 밤의 문턱", "Gentle Monster", transport=FakeAgent("ok"), sleep=lambda s: None)
ok(r["state"] == "DONE" and r["stop"] == "answered" and [c["tool"] for c in r["calls"]] == ["gm_new", "gm_plan", "gm_cast", "gm_story", "gm_finish"],
   "five calls in order, DONE, then an answer")
ok(not any(c["offlist"] for c in r["calls"]) and r["claimed"] == "DONE" and r["hook"] == {}, "no off-list call; the answer's claim matches the ledger")
r = loop.run("소금 사막", "Tamburins", transport=FakeAgent("korean"), sleep=lambda s: None)
ok(r["state"] == "DONE" and sum(1 for c in r["calls"] if c["ok"] is False) == 1, "Korean story -> one ok:false, fixed, DONE")
r = loop.run("궤도 격납고", "", transport=FakeAgent("offlist"), sleep=lambda s: None)
ok(r["state"] == "DONE" and sum(c["offlist"] for c in r["calls"]) == 1, "an off-list call is counted, refused, and the loop recovers")
r = loop.run("수영장", "", transport=FakeAgent("badcast"), sleep=lambda s: None)
ok(r["state"] == "DONE" and any("hero: used the plan's own shape" in n for c in r["calls"] for n in c["notes"]), "a bad shape is filled from the plan")
r = loop.run("겨울 사우나", "", transport=FakeAgent("samecall"), sleep=lambda s: None)
ok(r["state"] == "DONE", "a repeated call is harmless")
r = loop.run("도서관", "Aesop", transport=FakeAgent("nocall"), sleep=lambda s: None)
ok(r["job"] is None and r["state"] is None and r["calls"] == [], "no tool call -> no job, and nothing is counted as done")


class Quota:
    def __init__(self):
        self.n, self.f = 0, FakeAgent("ok")

    def __call__(self, *a):
        self.n += 1
        if self.n <= 2:
            return 429, json.dumps({"error": {"message": "quota", "details": [{"retryDelay": "3s"}]}}), {}
        return self.f(*a)


sl = []
r = loop.run("비", "", transport=Quota(), sleep=sl.append)
ok(r["state"] == "DONE" and sl == [3.0, 3.0], f"429 in the loop waits the server's delay ({sl})")

sec("MCP over stdio (the server Gemini CLI starts)")
msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "gm_plan", "arguments": {"job": "nope", "plan": "orbit"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "gm_bogus", "arguments": {}}}]
pr = subprocess.run([sys.executable, str(ROOT / "server.py")], input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True,
                    env=dict(os.environ), timeout=300, cwd=str(TMP))
o = {x["id"]: x for x in map(json.loads, pr.stdout.splitlines())}
ok(len(o) == 4 and o[1]["result"]["protocolVersion"] == "2025-03-26", "four replies, protocol echoed, stdout only JSON-RPC")
ok(len(o[2]["result"]["tools"]) == 16, "tools/list: 16")
r3 = json.loads(o[3]["result"]["content"][0]["text"])
ok(o[3]["result"]["isError"] and r3["next"][0]["tool"] == "gm_new", "a bad job id -> isError, and the call that fixes it")
ok(json.loads(o[4]["result"]["content"][0]["text"])["next"][0]["tool"] == "gm_new", "an unknown tool -> told where to start")
ok("AIza" not in "".join(p.read_text() for p in Path(os.environ["GMG_OUT"]).rglob("*.jsonl")), "no key in any ledger")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("all passed" if not FAIL else f"{len(FAIL)} failed"))
sys.exit(1 if FAIL else 0)
