"""The extension's MCP server (stdio JSON-RPC 2.0, stdlib only): six tools, one state machine (gmg.agent).

stdout is the RPC channel; everything else goes to stderr.
"""
from __future__ import annotations

import contextlib
import json
import re
import sys

from gmg import agent, photo, plans as PL, portfolio, upstream

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
        {"name": "gm_amend", "description": "Add typed constraints to a store job (language, text size, pages, rationale, generated photos, route, reference image).",
         "inputSchema": {"type": "object", "required": ["job"], "properties": {"job": JOB, "reference_image": _s("path of a reference layout image, optional"),
             "constraints": {"type": "object", "properties": {
                 "language": {"type": "string", "enum": ["en_only", "ko_and_en"]}, "text_size": {"type": "string", "enum": ["small", "normal"]},
                 "pages": {"type": "string", "enum": ["one", "multi"]}, "include_rationale": {"type": "boolean"},
                 "generated_photos": {"type": "boolean"}, "follow_route": {"type": "boolean"}}}}}},
        {"name": "gm_render", "description": "Draw a finished store job: layout PDF, moodboard PDF, blueprint PDF (minutes) or video (tens of minutes).",
         "inputSchema": {"type": "object", "required": ["job", "outputs"], "properties": {"job": JOB,
             "outputs": {"type": "array", "items": {"type": "string", "enum": agent.OUTPUTS}}}}},
        # ---- portfolio workspace
        {"name": "pf_show", "description": "Portfolio workspace: terms, page map, stored texts (ids), measured photos, proposals. Call first for portfolio work.",
         "inputSchema": {"type": "object", "properties": {}}},
        {"name": "pf_photos", "description": "Measure attached photos in code (brightness, saturation, hue, warmth, sharpness, subject, colours).",
         "inputSchema": {"type": "object", "required": ["paths"], "properties": {"paths": {"type": "array", "items": _s("image file path")}}}},
        {"name": "pf_sort", "description": "Rank measured photos by one criterion, or assign them to groups by mood; returns the measured evidence.",
         "inputSchema": {"type": "object", "properties": {
             "by": {"type": "string", "enum": photo.CRITERIA}, "photos": {"type": "array", "items": _s("photo id; empty = all")}, "k": {"type": "integer"},
             "groups": {"type": "array", "items": {"type": "object", "required": ["name", "mood"], "properties": {
                 "name": _s("group name"), "mood": {"type": "array", "items": {"type": "string", "enum": photo.MOODS}}}}}}}},
        {"name": "pf_write", "description": "Store new text candidates (answers, cover lines, captions, page text, storyline); code checks language, length and abstract words.",
         "inputSchema": {"type": "object", "required": ["kind", "items", "register", "language"], "properties": {
             "kind": {"type": "string", "enum": portfolio.KINDS}, "register": {"type": "string", "enum": portfolio.REGISTERS},
             "language": {"type": "string", "enum": portfolio.LANGS}, "max_chars": {"type": "integer"}, "about": _s("what it is about (e.g. a photo id)"),
             "keep": {"type": "array", "items": _s("a word"), "description": "words the user chose themselves (their own concepts); not counted as abstract"},
             "items": {"type": "array", "items": {"type": "object", "required": ["text"], "properties": {
                 "text": _s("the text"), "pattern": {"type": "string", "enum": portfolio.PATTERNS}, "label": _s("short label, optional")}}}}}},
        {"name": "pf_revise", "description": "Change stored text(s) with one operation; code checks the change really happened. Before and after are kept.",
         "inputSchema": {"type": "object", "required": ["op", "texts"], "properties": {
             "op": {"type": "string", "enum": portfolio.OPS}, "targets": {"type": "array", "items": _s("text id (t3), or 'last'")},
             "texts": {"type": "array", "items": _s("the new text, one per target, in order")},
             "arg": _s("refocus: the topic; widen_categories: the categories, comma-separated; translate: ko or en"),
             "source_text": _s("the user's own text, when it is not stored yet"), "register": {"type": "string", "enum": portfolio.REGISTERS},
             "keep": {"type": "array", "items": _s("a word"), "description": "words the user chose themselves; not counted as abstract"}}}},
        {"name": "pf_concept", "description": "Check a phrase against the defined terms (e.g. SPA = STYLE, PICTURE, ARCHITECTURE): one yes/no/partly verdict with a quoted reason per term.",
         "inputSchema": {"type": "object", "required": ["phrase", "verdicts"], "properties": {"phrase": _s("the phrase"),
             "terms": {"type": "array", "description": "the terms exactly as the user defined them (e.g. 'SPA is STYLIST, PHOTOGRAPHER, ARCHITECT' -> three terms); omit to use the stored terms",
                       "items": {"type": "object", "properties": {"name": _s("term"), "definition": _s("what it means")}}},
             "verdicts": {"type": "array", "items": {"type": "object", "required": ["term", "connects", "reason"], "properties": {
                 "term": _s("term"), "connects": {"type": "string", "enum": ["yes", "no", "partly"]}, "reason": _s("why, quoting the phrase or the definition")}}}}}},
        {"name": "pf_pages", "description": "Page map: set pages, propose exactly 3 options for what comes after a page, or adopt an option or a text.",
         "inputSchema": {"type": "object", "required": ["action"], "properties": {
             "action": {"type": "string", "enum": ["set", "propose", "adopt", "show"]},
             "pages": {"type": "array", "items": {"type": "object", "properties": {"n": {"type": "number"}, "title": _s("page title"), "role": _s("what the page does")}}},
             "after": {"type": "number", "description": "propose: the page number the options follow"},
             "options": {"type": "array", "items": {"type": "object", "required": ["title", "summary"], "properties": {"title": _s("title"), "summary": _s("one or two plain sentences")}}},
             "choice": _s("adopt: an option label (A, B, C) or a text id (t5)")}}},
        {"name": "pf_choose", "description": "Resolve a terse user reply ('1', 'A안', 'a ? a:b', '다시 시도') against the last numbered options, or retry the last call.",
         "inputSchema": {"type": "object", "required": ["option"], "properties": {"option": _s("the user's reply, verbatim")}}},
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
