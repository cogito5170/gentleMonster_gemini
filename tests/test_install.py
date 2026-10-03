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
ok("npm install --prefix \"$HOME/.gentlemonster/cli\"" in block and "@google/gemini-cli@0.62.0" in block and "npm install -g" not in block,
   "a private Gemini CLI 0.62.0 under ~/.gentlemonster; the user's own gemini is not touched")
ok("grep -qs 'gentlemonster/bin' \"$HOME/.zshrc\" ||" in block, "the PATH line is added to ~/.zshrc once")
sha = re.search(r"--ref (\S+)", block)
ok(sha and (re.fullmatch(r"[0-9a-f]{40}", sha.group(1)) or sha.group(1) == "PREVIEW_SHA"), "the extension is installed at one commit")
ok("--consent" in block, "no interactive confirmation in the middle of the paste")
ok('-n "$GEMINI_API_KEY"' in block and "echo $GEMINI_API_KEY" not in block and "${GEMINI_API_KEY" not in block, "the key is checked, never printed")
ok(lines[-1].endswith("gmg\" doctor"), "it ends with gmg doctor")

import os, subprocess, tempfile  # noqa: E401,E402
launcher = ROOT / "install" / "gentlemonster"


def run_launcher(version, extension, *args, model=""):
    home = Path(tempfile.mkdtemp(prefix="gm_launch_"))
    if version:
        b = home / ".gentlemonster" / "cli" / "node_modules" / ".bin"
        b.mkdir(parents=True)
        (b / "gemini").write_text("#!/bin/sh\n[ \"$1\" = --version ] && echo " + version + " && exit 0\necho ARGS \"$@\" MODEL=$GENTLEMONSTER_MODEL\n")
        (b / "gemini").chmod(0o755)
    if extension:
        e = home / ".gemini" / "extensions" / "gentlemonster"
        e.mkdir(parents=True)
        (e / "gemini-extension.json").write_text("{}")
    p = subprocess.run(["sh", str(launcher), *args], capture_output=True, text=True, env={"HOME": str(home), "PATH": "/usr/bin:/bin", **({"GENTLEMONSTER_MODEL": model} if model else {})})
    return p.returncode, p.stdout.strip().splitlines()


rc, out = run_launcher("0.62.0", True, "-p", "hello")
ok(rc == 0 and out == ["ARGS -m gemini-3-flash-preview -p hello MODEL=gemini-3-flash-preview"],
   f"the launcher runs the private CLI with gemini-3-flash-preview, passes arguments and tells the extension the model ({out})")
rc, out = run_launcher("0.62.0", True, "-p", "hi", model="gemini-3.1-flash-lite")
ok(rc == 0 and out == ["ARGS -m gemini-3.1-flash-lite -p hi MODEL=gemini-3.1-flash-lite"], "GENTLEMONSTER_MODEL overrides the model for experiments")
rc, out = run_launcher("0.62.0", True, "mcp", "list")
ok(rc == 0 and out == ["ARGS mcp list MODEL="], f"a management command passes through without a model ({out})")
rc, out = run_launcher("0.60.0", True)
ok(rc == 1 and len(out) == 1 and "0.60.0, not 0.62.0" in out[0] and "@google/gemini-cli@0.62.0" in out[0] and "npm install --prefix" in out[0], "a wrong CLI version stops with one line saying what to run")
rc, out = run_launcher("", True)
ok(rc == 1 and len(out) == 1 and "missing" in out[0], "no private CLI -> one line")
rc, out = run_launcher("0.62.0", False)
ok(rc == 1 and len(out) == 1 and "extension is not installed" in out[0], "no extension -> one line")
ok("cp \"$HOME/.gemini/extensions/gentlemonster/install/gentlemonster\"" in block, "the block installs this launcher from the pinned extension")
usage = (ROOT / "USAGE.md").read_text()
ok(block.strip() in usage or "INSTALL_BLOCK" in usage, "USAGE.md shows the same block")
ok("preview" in usage.lower() and "not a release" in usage.lower(), "USAGE.md says preview, not a release")
print("\n" + ("all passed" if not FAIL else f"{len(FAIL)} failed"))
sys.exit(1 if FAIL else 0)
