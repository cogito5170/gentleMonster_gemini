#!/usr/bin/env python3
"""Gemini CLI BeforeAgent hook -> gmg.turn.record(prompt): the user's turn, terse or not, and its attached images;
turn.note() goes back as additionalContext (the CLI appends it to the turn as <hook_context>)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from gmg import turn
    inp = json.loads(sys.stdin.read() or "{}")
    n = turn.note(turn.record(inp.get("prompt", ""), inp.get("session_id", "")))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "BeforeAgent", "additionalContext": n}} if n else {}))
except Exception as e:                                     # noqa: BLE001
    print(json.dumps({"systemMessage": f"[gentlemonster] the turn was NOT recorded ({type(e).__name__})"}))
