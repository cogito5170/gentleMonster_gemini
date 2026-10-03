#!/usr/bin/env python3
"""Gemini CLI BeforeAgent hook -> gmg.turn.record(prompt): the user's turn, terse or not, and its attached images."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from gmg import turn
    turn.record(json.loads(sys.stdin.read() or "{}").get("prompt", ""))
    print("{}")
except Exception as e:                                     # noqa: BLE001
    print(json.dumps({"systemMessage": f"[gentlemonster] the turn was NOT recorded ({type(e).__name__})"}))
