"""The Gemini CLI heap fix, ported from well_used_gemini (CMD-GMG8, WUG HEAP.md, BD-259).

**The bug.** Gemini CLI 0.62.0 with telemetry off, which is the default, buffers every model request in `telemetryBuffer`.
- Each entry is a closure holding the whole history as JSON.
- The buffer is never drained, because telemetry is never initialized.
- So the heap grows as turns², and long sessions die with "JavaScript heap out of memory".

**The fix.** Enable telemetry so that it sends and keeps nothing: target local, outfile /dev/null, logPrompts false.
- WUG measured 1174 -> 30 KB/turn and no OOM over 41.7 minutes.
- Measured here with gentleMonster's own MCP server: see bench/preview/HEAP.md.

**Where it goes: the private CLI's own settings.**
- `gentlemonster` runs its private Gemini CLI with `GEMINI_CLI_HOME=~/.gentlemonster/cli-home`. That CLI keeps its settings, extensions and sign-in in `~/.gentlemonster/cli-home/.gemini/`.
- The block goes into that settings file only when it does not already enable telemetry. A config there that enables telemetry is left alone.
- The user's own `~/.gemini` is never written.
- Why not a system settings file? Gemini CLI reads system settings only when the file and every parent directory are owned by root, which needs sudo. This was measured, see HEAP.md.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

FIX = {"telemetry": {"enabled": True, "target": "local", "outfile": "/dev/null", "logPrompts": False}}


def _home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def cli_home() -> Path:
    """The private CLI's home: GEMINI_CLI_HOME when set (the launcher sets it), else ~/.gentlemonster/cli-home."""
    return Path(os.environ.get("GEMINI_CLI_HOME") or (_home() / ".gentlemonster" / "cli-home"))


def settings_path() -> Path:
    return cli_home() / ".gemini" / "settings.json"


def _read_json(p: Path) -> dict:
    """settings.json may hold // and /* */ comments and trailing commas; anything unreadable counts as empty."""
    try:
        t = p.read_text(encoding="utf-8")
    except OSError:
        return {}
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    t = re.sub(r'(^|[^:"\\])//[^\n]*', r"\1", t)
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    try:
        d = json.loads(t)
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        return {}


def _enabled(d: dict) -> bool:
    tel = d.get("telemetry")
    return isinstance(tel, dict) and tel.get("enabled") is True


def ensure() -> "tuple[Path, bool]":
    """Put the fix into the private CLI's settings when telemetry is not enabled there. Returns (path, changed).
    The first time, the sign-in choice (security.auth.selectedType) is copied from the user's ~/.gemini/settings.json,
    read only, so the private CLI does not ask again."""
    p = settings_path()
    d = _read_json(p)
    changed = False
    if not _enabled(d):
        d["telemetry"] = dict(FIX["telemetry"])
        changed = True
    if not p.is_file():
        auth = ((_read_json(_home() / ".gemini" / "settings.json").get("security") or {}).get("auth") or {}).get("selectedType")
        if auth:
            d.setdefault("security", {}).setdefault("auth", {})["selectedType"] = auth
        changed = True
    if changed:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    return p, changed


def check() -> "tuple[bool, str]":
    """For gmg doctor: is the heap fix in effect for `gentlemonster`?"""
    launcher = _home() / ".gentlemonster" / "bin" / "gentlemonster"
    if not (launcher.is_file() and "GEMINI_CLI_HOME" in launcher.read_text(encoding="utf-8", errors="replace")):
        return False, ("heap fix missing: the installed `gentlemonster` launcher predates it -- paste the B install block "
                       "from USAGE.md again")
    d = _read_json(settings_path())
    if not _enabled(d):
        return False, (f"heap fix missing: telemetry is off in {settings_path()} -- run `gentlemonster --version` once "
                       "(it writes the fix) or paste the B install block again")
    t = d["telemetry"]
    mine = all(t.get(k) == v for k, v in FIX["telemetry"].items())
    return True, ("heap fix: the private Gemini CLI keeps telemetry local and discarded, with no prompts logged" if mine else
                  f"telemetry is enabled in {settings_path()} by your own config (left alone; the heap fix needs only enabled)")
