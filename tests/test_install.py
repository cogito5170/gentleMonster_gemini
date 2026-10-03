"""CMD-GMG6 S1: the macOS install block pastes into zsh as is, and USAGE.md carries the same block."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAIL = []


def ok(c, what):
    print(("  ok  " if c else "  FAIL ") + what)
    if not c:
        FAIL.append(what)


block = (ROOT / "install" / "macos.zsh").read_text()
lines = [ln for ln in block.splitlines() if ln.strip()]
ok(not any(ln.lstrip().startswith("#") for ln in lines), "no comment lines (interactive zsh runs '#' as a command)")
ok("<" not in block and ">" not in block, "no angle brackets (no placeholders, no redirection to mistype)")
ok("@google/gemini-cli@0.60.0" in block, "Gemini CLI pinned to 0.60.0")
sha = re.search(r"--ref (\S+)", block)
ok(sha and (re.fullmatch(r"[0-9a-f]{40}", sha.group(1)) or sha.group(1) == "PREVIEW_SHA"), "the extension is installed at one commit")
ok("--consent" in block, "no interactive confirmation in the middle of the paste")
ok('-n "$GEMINI_API_KEY"' in block and "echo $GEMINI_API_KEY" not in block and "${GEMINI_API_KEY" not in block, "the key is checked, never printed")
ok(lines[-1].endswith("gmg\" doctor"), "it ends with gmg doctor")
usage = (ROOT / "USAGE.md").read_text()
ok(block.strip() in usage or "INSTALL_BLOCK" in usage, "USAGE.md shows the same block")
ok("preview" in usage.lower() and "not a release" in usage.lower(), "USAGE.md says preview, not a release")
print("\n" + ("all passed" if not FAIL else f"{len(FAIL)} failed"))
sys.exit(1 if FAIL else 0)
