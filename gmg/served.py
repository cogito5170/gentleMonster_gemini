"""Which model actually served the agent (CMD-GMG4 S2).

A Gemini CLI can serve another model than the one asked (0.61+ rewrites `gemini-3.1-flash-lite` to
`gemini-3.5-flash-lite` for API-key auth; no setting turns it off -- see README). The MCP server never sees the model, so the served model is recorded from
where it is known: the AfterAgent hook reads the CLI's own chat recording (`transcript_path`, a "model" field on
every response); the API loop reads each response's `modelVersion`. Every record goes to <GMG_OUT>/served.jsonl
and, as a SERVED event, into the ledger of the job or workspace that turn worked on.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from gmg import CLI_PIN, asked_model


def _out() -> Path:
    return Path(os.environ.get("GMG_OUT") or (Path.home() / "gentleMonster_gemini_out"))


def from_transcript(path) -> "list[str]":
    """Models named on the responses of a Gemini CLI chat recording (jsonl or json), in order."""
    p = Path(path or "")
    if not p.is_file():
        return []
    found = []

    def walk(x):
        if isinstance(x, dict):
            if x.get("type") == "gemini" and isinstance(x.get("model"), str):
                found.append(x["model"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            walk(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return found


def record(model: str, source: str, same: "bool | None" = None) -> dict:
    """Append one served-model record; also a SERVED event in the most recently touched ledger.
    `same`: the caller's own comparison (agy names models by its own slugs); default: the served name starts with the asked one."""
    from gmg.ledger import Ledger
    asked = asked_model()
    rec = {"t": round(time.time(), 3), "model": model, "source": source, "asked": asked,
           "differs": not (str(model).startswith(asked) if same is None else same)}
    out = _out()
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "served.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    from gmg import usage
    usage.log("served", model=model, source=source, differs=rec["differs"])
    ledgers = sorted(out.glob("*/gmg_ledger.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if ledgers:
        Ledger(ledgers[0].parent).log("SERVED", model=model, source=source, asked=asked, differs=rec["differs"])
    return rec


def latest() -> "dict | None":
    p = _out() / "served.jsonl"
    if not p.is_file():
        return None
    lines = [l for l in p.read_text().splitlines() if l.strip()]
    return json.loads(lines[-1]) if lines else None


AGY_FRESH = 12 * 3600      # an agy session's served model counts as known for this long after a recorded check


def warning() -> "str | None":
    r = latest()
    if os.environ.get("GENTLEMONSTER_HOST") == "agy" and not (r and r.get("source") == "agy" and time.time() - r.get("t", 0) < AGY_FRESH):
        return ("served model unknown: an interactive agy session does not report it to the extension -- "
                "`gentlemonster-agy --check` runs one turn and records it")
    if r and r["differs"] and r.get("source") == "agy":
        return f"served by {r['model']}, not {r.get('asked', asked_model())} (agy chose another model than --model asked)"
    if r and r["differs"]:
        return (f"served by {r['model']}, not {r.get('asked', asked_model())} (the Gemini CLI changed the model; start it with "
                f"`gentlemonster`, which runs the pinned CLI {CLI_PIN} -- see README)")
    return None
