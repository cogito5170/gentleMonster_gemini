"""AfterAgent hook: the answer may only state the verdict the job's ledger holds.

Gemini CLI sends {prompt_response, stop_hook_active, ...} on stdin. If the answer claims a result
(DONE / NEEDS_REVIEW / FAILED, or "passed" / "did not pass") that differs from the latest job's ledger:
first time -> deny (the CLI rewrites the answer), with the ledger's verdict line to use instead;
again -> no block, a systemMessage warning (no endless rewrites). No claim, or no job -> pass.
A check that could not run says so in a systemMessage; it is never counted as a pass.
Limit: a text check -- a paraphrase it does not know is not caught.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

POS = re.compile(r"\b(DONE|passed|passes|all checks)\b|통과했|통과함|통과\s*\(", re.I)
NEG = re.compile(r"\b(NEEDS_REVIEW|FAILED|did not pass|does not pass|not passed)\b|통과하지 못|실패", re.I)


def claimed(text: str) -> "str | None":
    if NEG.search(text or ""):
        return "not DONE"
    if POS.search(text or ""):
        return "DONE"
    return None


def latest(out_dir) -> "tuple[str, dict] | None":
    from gmg.ledger import Ledger
    fs = sorted(Path(out_dir).glob("gm-*/gmg_ledger.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not fs:
        return None
    return fs[0].parent.name, Ledger(fs[0].parent).status()


def decide(inp: dict, out_dir) -> dict:
    c = claimed(inp.get("prompt_response") or "")
    if c is None:
        return {}
    j = latest(out_dir)
    if j is None:
        return {}
    job, st = j
    real = "DONE" if st["state"] == "DONE" else "not DONE"
    if c == real:
        return {}
    line = f"{job}: {st['state']}"
    if inp.get("stop_hook_active"):
        return {"systemMessage": f"[gentlemonster] the answer states a result the ledger does not hold; the ledger says: {line}"}
    return {"decision": "deny", "reason": f"Rewrite the answer. The job's ledger says: {line}. State the result only as that line "
                                          "(or call gm_explain); do not state checks or results yourself."}


def served(inp: dict) -> "str | None":
    """Record which model served this turn (from the CLI's chat recording); a warning when it is not the asked model."""
    from gmg import served as SV
    models = SV.from_transcript(inp.get("transcript_path"))
    if not models:
        return "[gentlemonster] the served model could not be read from the CLI transcript (not recorded)"
    r = SV.record(models[-1], "gemini-cli")
    return f"[gentlemonster] {SV.warning()}" if r["differs"] else None


def main() -> int:
    try:
        inp = json.loads(sys.stdin.read() or "{}")
        out = decide(inp, os.environ.get("GMG_OUT") or (Path.home() / "gentleMonster_gemini_out"))
        w = served(inp)
        if w:
            out["systemMessage"] = (out.get("systemMessage", "") + " " + w).strip()
    except Exception as e:                                  # noqa: BLE001
        out = {"systemMessage": f"[gentlemonster] the answer was NOT checked against the ledger ({type(e).__name__})"}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
