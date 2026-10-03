"""Drive the extension the way Gemini CLI does: flash-lite picks the tools (Gemini API function calling).

Same tool schemas as the MCP server (tools/list), GEMINI.md as the system instruction, the user's request as
the first turn. Every tool call goes through ext_mcp.handle (the server's own code path). Stops when the model
answers without a call, or at the turn cap.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from gmg import MODEL, agent, ext_mcp, hook
from gmg.gemini import API, _retry_delay, http, key

ROOT = Path(__file__).resolve().parent.parent
PROMPT = "Design a store with gentleMonster.\nBrief: {brief}"
PROMPT_BRAND = "\nBrand: {brand}"
_KEEP = {"type", "enum", "properties", "required", "items", "description"}


QUOTA_GONE = 600      # a server delay longer than this is a used-up daily quota: stop at once, do not wait it out

def _served(turns):
    """The API names the model that served each response (modelVersion); record the last one of this turn."""
    ms = [t["reported"] for t in turns if t.get("reported") and t["reported"] != "미보고"]
    if ms:
        from gmg import served
        served.record(ms[-1], "api")


def to_decl(s: dict) -> dict:
    out = {}
    for k, v in s.items():
        if k not in _KEEP:
            continue
        out[k] = v.upper() if k == "type" else {p: to_decl(q) for p, q in v.items()} if k == "properties" else to_decl(v) if k == "items" else v
    return out


def declarations(group: str = "") -> list:
    return [{"name": t["name"], "description": t["description"], "parameters": to_decl(t["inputSchema"])} for t in ext_mcp.tools(group)]


def run(brief: str, brand: str = "", transport=None, model: str = "", max_turns: int = 24, sleep=time.sleep, log=None) -> dict:
    model = model or MODEL
    transport = transport or http
    system = (ROOT / "GEMINI.md").read_text(encoding="utf-8")
    decls = declarations()
    contents = [{"role": "user", "parts": [{"text": PROMPT.format(brief=brief) + (PROMPT_BRAND.format(brand=brand) if brand else "")}]}]
    turns, calls, t0, prev_next, final, stop = [], [], time.time(), ["gm_new"], "", "answered"
    for turn in range(max_turns):
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "tools": [{"functionDeclarations": decls}]}
        d = None
        for attempt in range(1, 6):
            ts = time.time()
            code, text, rh = transport(f"{API}/models/{model}:generateContent", body,
                                       {"Content-Type": "application/json", "x-goog-api-key": key()}, {"step": "agent", "turn": turn})
            if code == 200:
                d = json.loads(text)
                break
            w = _retry_delay(text, rh)
            turns.append({"turn": turn, "attempt": attempt, "http": code, "wait": w})
            if code not in (429, 500, 502, 503, 504) or attempt == 5 or (w or 0) > QUOTA_GONE:
                break
            sleep(min(w, 60) if w is not None else 2 ** attempt)
        if d is None:
            stop = "quota_exhausted" if (turns[-1].get("wait") or 0) > QUOTA_GONE else "http_error"
            break
        cand = (d.get("candidates") or [{}])[0]
        usage = d.get("usageMetadata") or {}
        turns.append({"turn": turn, "ms": int((time.time() - ts) * 1000), "finish": cand.get("finishReason"), "usage": usage,
                      "reported": d.get("modelVersion", "미보고")})
        parts = (cand.get("content") or {}).get("parts") or []
        fcs = [p["functionCall"] for p in parts if "functionCall" in p]
        if not fcs:
            final = "".join(p.get("text", "") for p in parts if not p.get("thought"))
            stop = "answered" if cand.get("finishReason") == "STOP" else f"finish_{cand.get('finishReason')}"
            break
        contents.append({"role": "model", "parts": parts})        # as returned (thought signatures included)
        resp = []
        for fc in fcs:
            r = ext_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": fc.get("name"), "arguments": fc.get("args") or {}}})
            res = json.loads(r["result"]["content"][0]["text"]) if "result" in r else {"ok": False, "problems": [str(r.get("error"))]}
            calls.append({"turn": turn, "tool": fc.get("name"), "args": fc.get("args"), "ok": res.get("ok"), "offlist": fc.get("name") not in prev_next,
                          "problems": res.get("problems", []), "notes": res.get("notes", []), "job": res.get("job")})
            prev_next = [n.get("tool") for n in res.get("next", [])]
            fr = {"name": fc.get("name"), "response": {"result": res}}
            if fc.get("id"):
                fr["id"] = fc["id"]
            resp.append({"functionResponse": fr})
            if log:
                log(f"[loop] {fc.get('name')} -> ok={res.get('ok')}")
        contents.append({"role": "user", "parts": resp})
    else:
        stop = "turn_cap"
    _served(turns)
    jobs = [c["job"] for c in calls if c.get("job")]
    job = jobs[-1] if jobs else None
    state = None
    if job:
        try:
            state = agent.verdict(job)["verdict"]
        except Exception:                                   # noqa: BLE001
            state = None
    spec_out = __import__("os").environ.get("GMG_OUT") or (Path.home() / "gentleMonster_gemini_out")
    return {"job": job, "state": state, "stop": stop, "final": final, "seconds": round(time.time() - t0, 1),
            "turns": turns, "calls": calls, "claimed": hook.claimed(final),
            "hook": hook.decide({"prompt_response": final}, spec_out) if final else {}}


def _mime(p: Path) -> str:
    b = p.read_bytes()[:12]
    return "image/png" if b.startswith(b"\x89PNG") else "image/webp" if b[8:12] == b"WEBP" else "image/jpeg"


def user_turn(contents: list, q: dict, transport=None, model: str = "", max_turns: int = 12, sleep=time.sleep, log=None) -> dict:
    """One user turn of a conversation (contents is the shared history and grows). q: {"text", "images": [paths], "n"}."""
    import base64
    model = model or MODEL
    transport = transport or http
    system = (ROOT / "GEMINI.md").read_text(encoding="utf-8")
    decls = declarations()
    imgs = [Path(p) for p in q.get("images", [])]
    from gmg import turn
    note = turn.note(turn.record(q["text"] + "".join(f"\n[attached: {p}]" for p in imgs)))   # what the BeforeAgent hook does in the CLI
    contents.append({"role": "user", "parts": [{"text": q["text"] + "".join(f"\n[attached: {p}]" for p in imgs)}] +
                     [{"inline_data": {"mime_type": _mime(p), "data": base64.b64encode(p.read_bytes()).decode()}} for p in imgs] +
                     ([{"text": f"<hook_context>{note}</hook_context>"}] if note else [])})
    rec = {"calls": [], "turns": [], "final": "", "stop": "answered"}
    t0, prev_next = time.time(), None
    for turn in range(max_turns):
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "tools": [{"functionDeclarations": decls}]}
        d = None
        for attempt in range(1, 6):
            ts = time.time()
            code, txt, rh = transport(f"{API}/models/{model}:generateContent", body,
                                      {"Content-Type": "application/json", "x-goog-api-key": key()}, {"step": "agent", "turn": turn, "q": q.get("n")})
            if code == 200:
                d = json.loads(txt)
                break
            w = _retry_delay(txt, rh)
            rec["turns"].append({"turn": turn, "attempt": attempt, "http": code, "wait": w})
            if code not in (429, 500, 502, 503, 504) or attempt == 5 or (w or 0) > QUOTA_GONE:
                break
            sleep(min(w, 60) if w is not None else 2 ** attempt)
        if d is None:
            rec["stop"] = "quota_exhausted" if (rec["turns"][-1].get("wait") or 0) > QUOTA_GONE else "http_error"
            break
        cand = (d.get("candidates") or [{}])[0]
        rec["turns"].append({"turn": turn, "ms": int((time.time() - ts) * 1000), "finish": cand.get("finishReason"),
                             "usage": d.get("usageMetadata") or {}, "reported": d.get("modelVersion", "미보고")})
        parts = (cand.get("content") or {}).get("parts") or []
        if not parts:
            rec["stop"] = f"empty_{cand.get('finishReason')}"
            break
        contents.append({"role": "model", "parts": parts})
        fcs = [p["functionCall"] for p in parts if "functionCall" in p]
        if not fcs:
            rec["final"] = "".join(p.get("text", "") for p in parts if not p.get("thought"))
            rec["stop"] = "answered" if cand.get("finishReason") == "STOP" else f"finish_{cand.get('finishReason')}"
            break
        resp = []
        for fc in fcs:
            r = ext_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": fc.get("name"), "arguments": fc.get("args") or {}}})
            res = json.loads(r["result"]["content"][0]["text"]) if "result" in r else {"ok": False, "problems": [str(r.get("error"))]}
            rec["calls"].append({"tool": fc.get("name"), "args": fc.get("args"), "ok": res.get("ok"), "problems": res.get("problems", []),
                                 "offlist": prev_next is not None and fc.get("name") not in prev_next})
            prev_next = [n.get("tool") for n in res.get("next", [])] + [o["call"]["tool"] for o in res.get("options", []) if "call" in o] + ["pf_choose", "pf_show"]
            fr = {"name": fc.get("name"), "response": {"result": res}}
            if fc.get("id"):
                fr["id"] = fc["id"]
            resp.append({"functionResponse": fr})
            if log:
                log(f"[q{q.get('n')}] {fc.get('name')} -> ok={res.get('ok')}")
        contents.append({"role": "user", "parts": resp})
    else:
        rec["stop"] = "turn_cap"
    _served(rec["turns"])
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def converse(turns, transport=None, model: str = "", max_turns: int = 12, sleep=time.sleep, log=None) -> list:
    """One conversation, many user turns (a replay); state carries over. -> one record per user turn."""
    contents = []
    return [user_turn(contents, q, transport, model, max_turns, sleep, log) for q in turns]
