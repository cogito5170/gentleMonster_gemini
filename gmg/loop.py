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
PROMPT = "Design a store with gentleMonster.\nBrief: {brief}\nBrand: {brand}"
_KEEP = {"type", "enum", "properties", "required", "items", "description"}


def to_decl(s: dict) -> dict:
    out = {}
    for k, v in s.items():
        if k not in _KEEP:
            continue
        out[k] = v.upper() if k == "type" else {p: to_decl(q) for p, q in v.items()} if k == "properties" else to_decl(v) if k == "items" else v
    return out


def declarations() -> list:
    return [{"name": t["name"], "description": t["description"], "parameters": to_decl(t["inputSchema"])} for t in ext_mcp.tools()]


def run(brief: str, brand: str = "", transport=None, model: str = "", max_turns: int = 24, sleep=time.sleep, log=None) -> dict:
    model = model or MODEL
    transport = transport or http
    system = (ROOT / "GEMINI.md").read_text(encoding="utf-8")
    decls = declarations()
    contents = [{"role": "user", "parts": [{"text": PROMPT.format(brief=brief, brand=brand or "(none named)")}]}]
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
            if code not in (429, 500, 502, 503, 504) or attempt == 5:
                break
            sleep(min(w, 60) if w is not None else 2 ** attempt)
        if d is None:
            stop = "http_error"
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
