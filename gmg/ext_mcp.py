"""The extension's MCP server (stdio JSON-RPC 2.0, stdlib only): six tools, one state machine (gmg.agent).

stdout is the RPC channel; everything else goes to stderr.
"""
from __future__ import annotations

import contextlib
import json
import re
import sys

from gmg import agent, plans as PL, upstream

PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]
JOB = {"type": "string", "description": "the job id gm_new returned (gm-xxxxxxxx)"}


def _s(desc):
    return {"type": "string", "description": desc}


def tools() -> list:
    spec, _ = upstream.load()
    mats = sorted(spec.MATERIALS)
    roles = sorted({r for p in PL.PLANS.values() for r in p["roles"]})
    shapes = sorted({s for p in PL.PLANS.values() for r in p["roles"].values() for s in r["shapes"]})
    S = agent.SURFACE
    return [
        {"name": "gm_new", "description": "Start a store design job from the user's brief. Always the first call.",
         "inputSchema": {"type": "object", "required": ["request", "theme", "mood", "hero_idea", "product"], "properties": {
             "request": _s("the user's request, verbatim (any language)"),
             "brand": _s("the brand the user named, exactly as written; empty if none"),
             "theme": _s("the brief's idea in one English sentence"),
             "mood": {"type": "array", "items": _s("one English word"), "description": "exactly 3 words"},
             "hero_idea": _s("the one object or image the space is built around, in English"),
             "product": {"type": "string", "enum": agent.PRODUCTS}}}},
        {"name": "gm_plan", "description": "Choose the floor plan (one of the listed options).",
         "inputSchema": {"type": "object", "required": ["job", "plan"], "properties": {"job": JOB, "plan": {"type": "string", "enum": list(PL.PLANS)}}}},
        {"name": "gm_cast", "description": "Give every role of the plan a shape, a material and a label; choose the room.",
         "inputSchema": {"type": "object", "required": ["job", "roles", "room"], "properties": {
             "job": JOB,
             "roles": {"type": "array", "description": "one item per role listed by gm_plan", "items": {"type": "object", "required": ["role", "shape", "material", "label"], "properties": {
                 "role": {"type": "string", "enum": roles}, "shape": {"type": "string", "enum": shapes},
                 "material": {"type": "string", "enum": mats}, "label": _s("1-5 English words")}}},
             "room": {"type": "object", "required": list(S), "properties": {k: {"type": "string", "enum": v} for k, v in S.items()}}}}},
        {"name": "gm_story", "description": "Write the story of the space, in English, from the facts gm_cast returned.",
         "inputSchema": {"type": "object", "required": ["job", "title", "subtitle", "line", "synopsis", "keywords", "quote", "why"], "properties": {
             "job": JOB, "title": _s("short title"), "subtitle": _s("one short line"), "line": _s("one sentence"),
             "synopsis": _s("3-5 sentences, second person (you)"), "keywords": {"type": "array", "items": _s("keyword"), "description": "3 different"},
             "quote": _s("the philosophy in one line"), "why": {"type": "array", "description": "one per fact, in order", "items": {"type": "object", "required": ["t", "d"], "properties": {
                 "t": _s("2-6 word headline"), "d": _s("one sentence: what the fact does for the visitor")}}}}}},
        {"name": "gm_finish", "description": "Colours, material names and the 3 walkthrough captions; then code checks and draws the job.",
         "inputSchema": {"type": "object", "required": ["job", "palette", "accent", "material_names", "stops"], "properties": {
             "job": JOB,
             "palette": {"type": "array", "description": "exactly 5", "items": {"type": "object", "required": ["hex", "name"], "properties": {"hex": _s("#rrggbb"), "name": _s("short colour name")}}},
             "accent": {"type": "string", "enum": ["1", "2", "3", "4", "5"], "description": "which palette colour is the accent"},
             "material_names": {"type": "array", "items": _s("material name"), "description": "4, in the order gm_story listed"},
             "stops": {"type": "array", "description": "exactly 3", "items": {"type": "object", "required": ["cap", "sub"], "properties": {
                 "cap": _s("first person, one sentence"), "sub": _s("one line under it")}}}}}},
        {"name": "gm_explain", "description": "The job's verdict and why it came out this way (from the job's ledger).",
         "inputSchema": {"type": "object", "required": ["job"], "properties": {"job": JOB}}},
    ]


def handle(msg: dict):
    mid, method, p = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None
    try:
        if method == "initialize":
            v = p.get("protocolVersion")
            res = {"protocolVersion": v if v in PROTOCOLS else PROTOCOLS[0], "capabilities": {"tools": {}},
                   "serverInfo": {"name": "gentlemonster-gemini", "version": "0.2.0"}}
        elif method == "tools/list":
            res = {"tools": tools()}
        elif method == "tools/call":
            with contextlib.redirect_stdout(sys.stderr):
                try:
                    r = agent.call(p.get("name"), p.get("arguments") or {})
                except Exception as e:                      # noqa: BLE001
                    r = {"ok": False, "problems": [f"{type(e).__name__}: " + re.sub(r"AIza[0-9A-Za-z_-]{20,}", "***", str(e))],
                         "next": [{"tool": "gm_explain", "why": "see where the job stands"}]}
            res = {"content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False)}], "isError": not r.get("ok", False)}
        elif method == "ping":
            res = {}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": res}
    except Exception as e:                                  # noqa: BLE001
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}


def main() -> int:
    try:
        upstream.ready()
    except upstream.NotReady:
        upstream.setup(log=lambda m: print(m, file=sys.stderr))      # first run: fetch the pinned gentleMonster
    for ln in sys.stdin:
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = handle(json.loads(ln))
        except json.JSONDecodeError:
            r = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if r is not None:
            sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
