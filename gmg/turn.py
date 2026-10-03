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


def questions_in(prompt: str) -> "list[str]":
    """Questions written inside the turn ("..?, ..?, ..?"), in order; fewer than two -> []."""
    qs = [q.strip(" ,\"'“”‘’\n") for q in re.findall(r"[^?？\"“”\n,]+[?？]", re.sub(r"\[attached:[^\]]*\]", "", prompt or ""))]
    qs = [q for q in qs if len(q) >= 4]
    return qs if len(qs) >= 2 else []


ADOPT = re.compile(r"(?<![A-Za-z0-9])([A-Ha-h1-8])\s*(?:안|案|번|option)?\s*(?:을|를|으로|로)?\s*(?:채택|선택|고른다|고르겠|adopt|choose|go with|pick)"
                   r"|(?:adopt|choose|go with|pick)\s+(?:option\s+([A-Ha-h1-8])|((?-i:[A-H1-8])))(?![A-Za-z0-9])", re.I)


def adopted_in(prompt: str) -> "str | None":
    """The option label a turn adopts ("A안을 채택한다", "adopt B"), or None."""
    m = ADOPT.search(prompt or "")
    return next(g for g in m.groups() if g).upper() if m else None


FLOW = re.compile(r"스토리\s*라인|story\s*-?line|이어지는\s*(?:스토리|이야기|페이지|흐름)|다음\s*(?:페이지|지면|장)|페이지\s*(?:구성|흐름|순서|방향)|page\s*(?:flow|order|map)|next\s*page", re.I)


WIDEN = re.compile(r"(?:범주|카테고리|categor\w*)[^.?!\n]{0,20}(?:확장|넓|늘리|추가)|(?:widen|expand|broaden|add)[^.?!\n]{0,20}categor", re.I)


def record(prompt: str, session: str = "") -> dict:
    t = {"prompt": (prompt or "")[:2000], "session": session or "unknown", "terse": bool(TERSE.match(prompt or "")), "images": images_in(prompt), "chose": False,
         "questions": [] if TERSE.match(prompt or "") else questions_in(prompt), "adopts": adopted_in(prompt),
         "flow": bool(FLOW.search(prompt or "")) and not TERSE.match(prompt or ""), "flowed": False,
         "widen": bool(WIDEN.search(prompt or ""))}
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(t, ensure_ascii=False))
    from gmg import usage
    usage.log("turn", session=t["session"], prompt=(prompt or "")[:4000], images=t["images"], terse=t["terse"])
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
    if t.get("adopts") and not t["terse"]:
        out.append(f"The user adopts option {t['adopts']}: record it with pf_choose ({t['adopts']!r}) before doing what comes next.")
    if t.get("flow"):
        out.append("The user asks about the story line / page flow: keep it in the page map with pf_pages (set the pages the user "
                   "describes, then propose exactly 3 options for what follows); write page text only after that.")
    if t.get("widen"):
        out.append("The user asks to widen the categories: use pf_revise op=widen_categories, arg = the category words, comma-separated.")
    if t.get("questions"):
        out.append(f"The request asks {len(t['questions'])} questions: answer them with pf_write kind=answer, one item per question, in order.")
    if t["images"]:
        out.append(f"{len(t['images'])} image(s) attached ({', '.join(Path(i).name for i in t['images'])}): measure them "
                   "with pf_photos before describing, sorting or ranking them; cite the measured values, not your impression.")
    return " ".join(out) or None


def current() -> "dict | None":
    try:
        return json.loads(_path().read_text())
    except (OSError, ValueError):
        return None


def _mark(key: str) -> None:
    t = current()
    if t:
        t[key] = True
        _path().write_text(json.dumps(t, ensure_ascii=False))


def mark_chose() -> None:
    _mark("chose")


def mark_flowed() -> None:
    _mark("flowed")


def _fire(t: dict, which: str) -> None:
    """A redirect fires once per turn: if the agent cannot follow it (no option A to adopt, say), the turn is not stuck."""
    t["fired"] = (t.get("fired") or []) + [which]
    _path().write_text(json.dumps(t, ensure_ascii=False))


def gate(tool: str) -> "dict | None":
    """A result that redirects the call, or None.
    - a terse reply or an adoption ("A안을 채택") goes to pf_choose first;
    - a turn about the story line / page flow goes to pf_pages before pf_write.
    Each fires at most once per turn."""
    t = current()
    if not t or not tool.startswith("pf_") or tool == "pf_show":
        return None
    fired = t.get("fired") or []
    pick = t["prompt"].strip() if t["terse"] else t.get("adopts")
    if pick and not t["chose"] and tool != "pf_choose" and "pick" not in fired:
        _fire(t, "pick")
        why = f"the user's reply was {pick!r}" if t["terse"] else f"the user adopts option {pick}"
        return {"ok": False, "problems": [f"{why}: resolve it with pf_choose first"], "next": [{"tool": "pf_choose", "args": {"option": pick}}]}
    if t.get("flow") and not t.get("flowed") and tool == "pf_write" and "flow" not in fired:
        _fire(t, "flow")
        return {"ok": False, "problems": ["this turn is about the story line / page flow: put it in the page map with pf_pages first "
                                          "(action set for the pages the user describes, action propose for exactly 3 options of what follows)"],
                "next": [{"tool": "pf_pages", "args": {"action": "set", "pages": "[{n, title, role}]"}},
                         {"tool": "pf_pages", "args": {"action": "propose", "after": "page number", "options": "3 x {title, summary}"}}]}
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
