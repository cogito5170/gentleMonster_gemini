"""CMD-GMG8: the Gemini CLI heap fix (telemetry kept local and discarded) and the tool-result cap. No model calls."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="gmg_heap_"))
os.environ.pop("GEMINI_CLI_SYSTEM_SETTINGS_PATH", None)

from gmg import ext_mcp, telemetry as TM  # noqa: E402

FAIL = []


def ok(c, what):
    print(("  ok  " if c else "  FAIL ") + what)
    if not c:
        FAIL.append(what)


def home(name, settings=None):
    h = TMP / name
    (h / ".gemini").mkdir(parents=True)
    if settings is not None:
        (h / ".gemini" / "settings.json").write_text(settings)
    return h


def tm(h, env=None):
    os.environ["HOME"] = str(h)
    os.environ.pop("GEMINI_CLI_HOME", None)
    for k, v in (env or {}).items():
        os.environ[k] = v
    try:
        return TM.ensure(), TM.check()
    finally:
        for k in (env or {}):
            os.environ.pop(k, None)


def private(h):
    return h / ".gentlemonster" / "cli-home" / ".gemini" / "settings.json"


print("== the telemetry setting (the private CLI's own settings)")
ok(TM.FIX == {"telemetry": {"enabled": True, "target": "local", "outfile": "/dev/null", "logPrompts": False}},
   "the same block WUG measured: enabled, local, discarded, no prompts logged")
user = '{\n  // mine\n  "security": {"auth": {"selectedType": "oauth-personal"}},\n  "telemetry": {"enabled": false},\n}\n'
h = home("plain", user)
(p, changed), _ = tm(h)
d = json.loads(p.read_text())
ok(p == private(h) and changed and d["telemetry"] == TM.FIX["telemetry"], "telemetry off -> the fix goes into ~/.gentlemonster/cli-home/.gemini/settings.json")
ok(d["security"]["auth"]["selectedType"] == "oauth-personal", "the sign-in choice is copied from the user's settings, read only")
ok((h / ".gemini" / "settings.json").read_text() == user, "the user's own ~/.gemini/settings.json is byte-identical")
(p, changed), _ = tm(h)
ok(not changed, "a rerun changes nothing")
mine = {"telemetry": {"enabled": True, "target": "gcp", "otlpEndpoint": "http://x:4317"}, "model": {"name": "y"}}
h = home("mine")
private(h).parent.mkdir(parents=True)
private(h).write_text(json.dumps(mine))
(p, changed), _ = tm(h)
ok(not changed and json.loads(private(h).read_text()) == mine, "a private config that enables telemetry is left alone")
h = home("keep")
private(h).parent.mkdir(parents=True)
private(h).write_text(json.dumps({"model": {"name": "z"}, "telemetry": {"enabled": False, "target": "gcp", "outfile": "/tmp/t.log",
                                                                      "logPrompts": True, "otlpEndpoint": "http://x:4317"}}))
tm(h)
d = json.loads(private(h).read_text())
ok(d["model"] == {"name": "z"}, "other private settings are kept")
ok(d["telemetry"] == {**TM.FIX["telemetry"], "otlpEndpoint": "http://x:4317"},
   "a disabled telemetry block is merged: the four keys are set (target, outfile, logPrompts overridden), otlpEndpoint is kept")
h = home("envhome")
alt = TMP / "althome"
tm(h, {"GEMINI_CLI_HOME": str(alt)})
ok((alt / ".gemini" / "settings.json").is_file() and not private(h).exists(), "a GEMINI_CLI_HOME you set yourself is the one used")

print("== doctor")
h = home("doc")
os.environ["HOME"] = str(h)
good, msg = TM.check()
ok(not good and "launcher predates it" in msg, "doctor flags a missing fix (no launcher with it)")
(h / ".gentlemonster" / "bin").mkdir(parents=True, exist_ok=True)
shutil.copy(ROOT / "install" / "gentlemonster", h / ".gentlemonster" / "bin" / "gentlemonster")
good, msg = TM.check()
ok(not good and "telemetry is off" in msg, "doctor flags settings without the fix")
_, (good, msg) = tm(h)
ok(good and "heap fix" in msg, "doctor: the fix is in the private CLI's settings")

h = home("docver")
os.environ["HOME"] = str(h)
fake = h / "gemini"
fake.write_text('#!/bin/sh\necho "$GEMINI_CLI_HOME"\n')
fake.chmod(0o755)
from gmg import cli as CLI  # noqa: E402
ok(CLI.cli_version(str(fake), private=True) == str(private(h).parent.parent),
   "doctor's version check runs the private CLI in its own home, so your ~/.gemini is not written")

print("== the launcher")


def launch(h, env=None, home_cli=None):
    b = h / ".gentlemonster" / "cli" / "node_modules" / ".bin"
    b.mkdir(parents=True, exist_ok=True)
    (b / "gemini").write_text('#!/bin/sh\n[ "$1" = --version ] && echo 0.62.0 && exit 0\necho "HOME_CLI=$GEMINI_CLI_HOME"\n')
    (b / "gemini").chmod(0o755)
    e = (home_cli or h / ".gentlemonster" / "cli-home") / ".gemini" / "extensions" / "gentlemonster"
    e.mkdir(parents=True, exist_ok=True)
    (e / "gemini-extension.json").write_text("{}")
    v = h / ".gentlemonster" / "venv" / "bin"
    v.mkdir(parents=True, exist_ok=True)
    (v / "gmg").write_text(f'#!/bin/sh\nPYTHONPATH={ROOT} exec {sys.executable} -m gmg.cli "$@"\n')
    (v / "gmg").chmod(0o755)
    pr = subprocess.run(["sh", str(ROOT / "install" / "gentlemonster"), "-p", "x"], capture_output=True, text=True,
                        env={"HOME": str(h), "PATH": "/usr/bin:/bin", "GMG_UPSTREAM": os.environ.get("GMG_UPSTREAM", ""), **(env or {})})
    return pr.stdout.strip()


h = home("l1", user)
ok(launch(h) == f"HOME_CLI={h}/.gentlemonster/cli-home" and json.loads(private(h).read_text())["telemetry"] == TM.FIX["telemetry"],
   "the launcher runs the CLI in its private home and writes the fix there")
ok((h / ".gemini" / "settings.json").read_text() == user, "the user's ~/.gemini/settings.json is untouched by the launcher")
h = home("l2", user)
mine = h / "my-cli-home"
ok(launch(h, {"GEMINI_CLI_HOME": str(mine)}, home_cli=mine) == f"HOME_CLI={mine}" and
   json.loads((mine / ".gemini" / "settings.json").read_text())["telemetry"] == TM.FIX["telemetry"] and not private(h).exists(),
   "a GEMINI_CLI_HOME set before launch is kept by the launcher, and the fix goes there")

print("== the tool-result cap")
small = {"ok": True, "texts": [{"id": "t1", "text": "x"}], "next": [{"tool": "pf_write"}]}
ok(ext_mcp.cap_result(small) is small, "a small result is returned as is")
os.environ["GMG_OUT"] = str(TMP / "out")
big = {"ok": True, "texts": [{"id": f"t{i}", "text": "word " * 60} for i in range(50)], "say": "s",
       "next": [{"tool": f"pf_x{i}", "args": {"a": i}} for i in range(12)]}
c = ext_mcp.cap_result(big)
cs = json.dumps(c, ensure_ascii=False, separators=(",", ":"))
rid = c.get("truncated", {}).get("result_id", "")
ok(len(cs) <= ext_mcp.CAP and c["ok"] is True and c["say"] == "s", f"a big result is cut under {ext_mcp.CAP} characters ({len(cs)})")
ok(c["next"] == big["next"], "the closed `next` list is never cut")
full = TMP / "out" / "results" / f"{rid}.json"
ok(rid and full.is_file() and json.loads(full.read_text()) == big, "the full result is kept on disk under its result id")
huge = {"ok": False, "problems": ["p"], "next": [{"tool": "gm_explain"}], "blob": "y" * 20000}
c = ext_mcp.cap_result(huge)
ok("blob" not in json.dumps(c)[:0] and len(json.dumps(c)) <= ext_mcp.CAP and c["problems"] == ["p"], "a result that is still too big keeps the essentials")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("all passed" if not FAIL else f"{len(FAIL)} failed"))
sys.exit(1 if FAIL else 0)
