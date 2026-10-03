"""The current user turn, as code sees it (CMD-GMG3 proposals 2 and 3).

The MCP server never sees the user's words or attachments. A BeforeAgent hook (Gemini CLI passes `prompt`) or the
API loop records them here, and adds `note()` to the turn: <GMG_OUT>/turn.json = {prompt, terse, images, chose}. Tool results then
- point a terse reply ("다시 시도", "1", "A안", "a ? a:b") to pf_choose before anything else, and
- list attached images that have not been measured yet (pf_photos), so photos are measured, not only looked at.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

IMG = r"[^\s\]'\"]+\.(?:jpe?g|png|webp)"
TERSE = re.compile(r"^\s*(?:[1-8]\.?|[A-Ha-h]\s*안?\.?|[A-Ha-h1-8]\s*\?\s*[A-Ha-h1-8]\s*:\s*[A-Ha-h1-8]|다시(?:\s*시도)?|재시도|again|retry|try again)\s*[.!]?\s*$", re.I)


def _path() -> Path:
    return Path(os.environ.get("GMG_OUT") or (Path.home() / "gentleMonster_gemini_out")) / "turn.json"


def images_in(prompt: str) -> "list[str]":
    """@path (Gemini CLI) and [attached: path] (the API loop) image references, in order."""
    found = re.findall(r"@(" + IMG + ")", prompt or "", re.I) + re.findall(r"\[attached:\s*(" + IMG + r")\s*\]", prompt or "", re.I)
    return list(dict.fromkeys(found))


def record(prompt: str) -> dict:
    t = {"prompt": (prompt or "")[:2000], "terse": bool(TERSE.match(prompt or "")), "images": images_in(prompt), "chose": False}
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(t, ensure_ascii=False))
    return t


def note(t: "dict | None") -> "str | None":
    """What the BeforeAgent hook adds to the turn (as <hook_context>), so the routing holds even when no tool is
    called: attached images are measured with pf_photos, and a terse reply goes to pf_choose."""
    if not t:
        return None
    out = []
    if t["terse"]:
        out.append(f"The user's reply {t['prompt'].strip()!r} picks or retries an earlier option: call pf_choose with it "
                   "first, then continue from what it returns.")
    if t["images"]:
        out.append(f"{len(t['images'])} image(s) attached ({', '.join(Path(i).name for i in t['images'])}): measure them "
                   "with pf_photos before describing, sorting or ranking them; cite the measured values, not your impression.")
    return " ".join(out) or None


def current() -> "dict | None":
    try:
        return json.loads(_path().read_text())
    except (OSError, ValueError):
        return None


def mark_chose() -> None:
    t = current()
    if t:
        t["chose"] = True
        _path().write_text(json.dumps(t, ensure_ascii=False))


def gate(tool: str) -> "dict | None":
    """A result that redirects the call, or None. Only a terse reply is redirected (to pf_choose, once)."""
    t = current()
    if t and t["terse"] and not t["chose"] and tool.startswith("pf_") and tool not in ("pf_choose", "pf_show"):
        return {"ok": False, "problems": [f"the user's reply was {t['prompt'].strip()!r}: resolve it with pf_choose first"],
                "next": [{"tool": "pf_choose", "args": {"option": t["prompt"].strip()}}]}
    return None


def unmeasured() -> "list[str]":
    t = current()
    if not t or not t["images"]:
        return []
    try:
        from gmg import portfolio as PF
        have = {Path(p.get("path", "")).name for p in PF.state()["photos"]}
    except Exception:                                       # noqa: BLE001
        have = set()
    return [i for i in t["images"] if Path(i).name not in have]
