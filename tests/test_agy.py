"""CMD-GMG7: gentleMonster inside Antigravity CLI (agy), tested without agy (a fake agy on PATH).

The agy output shapes here are assumptions from agy's CHANGELOG until the run on the user's Mac.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="gmg_agy_"))
os.environ["GMG_OUT"] = str(TMP / "out")
os.environ.setdefault("GMG_UPSTREAM", str(Path.home() / "gentleMonster"))
for k in ("GENTLEMONSTER_HOST", "GENTLEMONSTER_MODEL", "GMG_MODEL"):
    os.environ.pop(k, None)

from gmg import agy as AG, served as SV  # noqa: E402

FAIL = []


def ok(c, what):
    print(("  ok  " if c else "  FAIL ") + what)
    if not c:
        FAIL.append(what)


print("== workspace files")
home = TMP / "home"
ext = home / ".gentlemonster" / "ext"
shutil.copytree(ROOT, ext, ignore=shutil.ignore_patterns(".git", "bench", "__pycache__", "out"))
py = str(home / ".gentlemonster" / "venv" / "bin" / "python3")
ws = home / "gentlemonster"
fs = AG.files(ws, py, ext)
cfg = json.loads(fs[".agents/mcp_config.json"])["mcpServers"]
ok(set(cfg) == {"gentlemonster", "gentlemonster-portfolio"}, "two MCP servers, the same split as the Gemini CLI extension")
ok(all(c["command"] == py and c["args"][0] == str(ext / "server.py") and (ext / "server.py").is_file() for c in cfg.values()),
   "each runs the extension's own server.py under the install venv's Python (no fork)")
ok([c["args"][1:] for c in cfg.values()] == [["--tools", "store"], ["--tools", "portfolio"]], "store and portfolio tool groups")
ok(all(c["env"] == {"GENTLEMONSTER_HOST": "agy"} for c in cfg.values()), "the servers know they run under agy")
rules = fs[f".agents/rules/{AG.RULE}"]
ok((ROOT / "GEMINI.md").read_text() in rules and "Antigravity" in rules, "the rules are GEMINI.md's instructions, plus one agy line")
blob = "\n".join(fs.values())
paths = re.findall(r'"(/[^"]+)"', blob)
ok(paths and all(p.startswith(str(home)) for p in paths), "every absolute path is under $HOME")
ok(not re.search(r"AIza|sk-|ghp_|token|secret|password", blob, re.I), "no key or token in the generated files")
ok(AG.setup(ws, py, ext) == [".agents/mcp_config.json", f".agents/rules/{AG.RULE}"] and AG.setup(ws, py, ext) == [], "setup writes once; a rerun changes nothing")
(ws / ".agents" / "mcp_config.json").write_text("{}")
ok(AG.setup(ws, py, ext) == [".agents/mcp_config.json"], "a changed file is restored")
os.environ["GENTLEMONSTER_EXT"] = str(ext)
ok(AG.ext_dir() == ext, "GENTLEMONSTER_EXT names the checkout")
del os.environ["GENTLEMONSTER_EXT"]

print("== model choice (agy's own names)")
lst = json.dumps([{"slug": "gemini-3.5-flash", "displayName": "Gemini 3.5 Flash"}, {"slug": "gemini-3-flash", "displayName": "Gemini 3 Flash"},
                  {"slug": "gemini-3.1-pro", "displayName": "Gemini 3.1 Pro"}])
ok(AG.pick_model(lst)[0] == "gemini-3-flash", "the slug for Gemini 3 Flash is picked, not 3.5")
ok(AG.pick_model(json.dumps({"models": [{"id": "gemini-3-flash-preview"}]}))[0] == "gemini-3-flash-preview", "an id field works too")
ok(AG.pick_model("gemini-3.8-flash\tGemini 3.8 Flash\ngemini-3-flash\tGemini 3 Flash\n")[0] == "gemini-3-flash", "tab-separated text works too")
slug, names = AG.pick_model(json.dumps([{"slug": "gemini-3.5-flash"}, {"slug": "gemini-3.1-flash-lite"}, {"slug": "gemini-3-flash-lite"}]))
ok(slug is None and "gemini-3.5-flash" in names, "no Gemini 3 Flash -> no pick (the user chooses), and the offered names are listed")
ok(not any(AG.is_flash_3(x) for x in ("gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash-lite", "Gemini 3.8 Flash")) and
   all(AG.is_flash_3(x) for x in ("gemini-3-flash-preview", "Gemini 3 Flash", "models/gemini-3-flash")), "Gemini 3 Flash is told apart from 3.x and lite")

print("== served model from agy output (shape assumed)")
ok(AG.served_models(json.dumps({"result": "2", "model": "gemini-3-flash"})) == ["gemini-3-flash"], "json: a model string")
sj = "\n".join(json.dumps(x) for x in ({"type": "init", "model": {"id": "gemini-3-flash", "display_name": "Gemini 3 Flash"}},
                                       {"type": "tool_use", "name": "mcp_gentlemonster-portfolio_pf_show"}, {"type": "result", "text": "2"}))
ok(AG.served_models(sj)[:1] == ["gemini-3-flash"] and AG.tools_called(sj) == ["pf_show"], "stream-json: a model object, and the tool called")
ok(AG.served_models("plain text") == [], "no JSON -> nothing claimed")
ok(AG.same_model("gemini-3-flash", "Gemini 3 Flash") and not AG.same_model("gemini-3-flash", "gemini-3.5-flash"), "agy slug and display name compare")


def gmg(*args, stdin="", env=None):
    e = dict(os.environ, PYTHONPATH=str(ROOT), **(env or {}))
    p = subprocess.run([sys.executable, "-m", "gmg.cli", *args], input=stdin, capture_output=True, text=True, env=e, cwd=str(ROOT))
    return p.returncode, p.stdout.strip(), p.stderr.strip()


rc, out, _ = gmg("agy-served", stdin=sj, env={"GENTLEMONSTER_MODEL": "gemini-3-flash"})
ok(rc == 0 and "gemini-3-flash (as asked)" in out and "pf_show" in out and SV.latest()["source"] == "agy" and not SV.latest()["differs"],
   f"agy-served records the served model as asked ({out})")
rc, out, _ = gmg("agy-served", stdin=json.dumps({"model": "gemini-3.5-flash", "text": "pf_show"}), env={"GENTLEMONSTER_MODEL": "gemini-3-flash"})
ok(rc == 1 and "NOT gemini-3-flash" in out and SV.latest()["differs"], "a different served model is marked")
rc, out, _ = gmg("agy-served", stdin=json.dumps({"text": "2"}), env={"GENTLEMONSTER_MODEL": "gemini-3-flash"})
ok(rc == 1 and "unknown" in out, "no model in the output -> unknown, exit 1")
rc, out, _ = gmg("agy-served", stdin=json.dumps({"model": "gemini-3-flash", "denied_actions": ["pf_show"]}), env={"GENTLEMONSTER_MODEL": "gemini-3-flash"})
ok(rc == 1 and "permission" in out, "a refused tool call is named, with what to do")
rc, out, err = gmg("agy-model", stdin=json.dumps([{"slug": "gemini-3.5-flash"}]))
ok(rc == 2 and not out and "gemini-3.5-flash" in err and "your decision" in err and len(err.splitlines()) == 1, "agy-model stops with one line and the choice")

print("== the served-model warning under agy")
os.environ["GENTLEMONSTER_HOST"] = "agy"
(TMP / "out" / "served.jsonl").unlink()
ok("unknown" in (SV.warning() or ""), "no agy record -> every tool result says the served model is unknown")
os.environ["GENTLEMONSTER_MODEL"] = "gemini-3-flash"
SV.record("Gemini 3 Flash", "agy", same=True)
ok(SV.warning() is None, "after a recorded agy check that matched, no warning")
SV.record("gemini-3.5-flash", "agy", same=False)
ok("agy chose another model" in (SV.warning() or ""), "a different agy model is warned")
del os.environ["GENTLEMONSTER_HOST"], os.environ["GENTLEMONSTER_MODEL"]

print("== the launcher, with a fake agy")
bin_ = TMP / "fakebin"
bin_.mkdir()
log = TMP / "agy.log"
models_json = TMP / "models.json"
(bin_ / "agy").write_text(f"""#!/bin/sh
echo "ARGS $@ | CWD $(pwd) | MODEL=$GENTLEMONSTER_MODEL HOST=$GENTLEMONSTER_HOST" >> {log}
[ "$1" = "--version" ] && echo 1.2.16 && exit 0
[ "$1" = "models" ] && cat {models_json} && exit 0
case " $* " in *" -p "*) echo '{{"model": "gemini-3-flash", "steps": [{{"tool": "mcp_gentlemonster-portfolio_pf_show"}}], "result": "0"}}' ;; esac
exit 0
""")
(bin_ / "agy").chmod(0o755)
vbin = home / ".gentlemonster" / "venv" / "bin"
vbin.mkdir(parents=True)
(vbin / "gmg").write_text(f"#!/bin/sh\nPYTHONPATH={ROOT} GENTLEMONSTER_EXT={ext} exec {sys.executable} -m gmg.cli \"$@\"\n")
(vbin / "gmg").chmod(0o755)
launcher = ROOT / "install" / "gentlemonster-agy"


def launch(*args, path=True, model=""):
    log.write_text("")
    env = {"HOME": str(home), "PATH": (str(bin_) + ":" if path else "") + "/usr/bin:/bin", "GMG_OUT": str(TMP / "out"),
           "GMG_UPSTREAM": os.environ["GMG_UPSTREAM"], **({"GENTLEMONSTER_AGY_MODEL": model} if model else {})}
    p = subprocess.run(["sh", str(launcher), *args], capture_output=True, text=True, env=env)
    return p.returncode, (p.stdout + p.stderr).strip().splitlines(), log.read_text().strip().splitlines()


shutil.rmtree(ws)
models_json.write_text(lst)
rc, out, calls = launch("-x", "hello")
ok(rc == 0 and calls[-1].startswith("ARGS --model gemini-3-flash -x hello") and f"CWD {ws}" in calls[-1] and "MODEL=gemini-3-flash HOST=agy" in calls[-1],
   f"agy starts in the workspace with agy's slug for Gemini 3 Flash, arguments passed, model told to the extension ({calls[-1:]})")
ok((ws / ".agents" / "mcp_config.json").is_file() and (ws / ".agents" / "rules" / AG.RULE).is_file(), "the launcher writes the workspace files")
rc, out, calls = launch("-x", model="gemini-3.5-flash")
ok(rc == 0 and calls[-1].startswith("ARGS --model gemini-3.5-flash -x") and not any(c.startswith("ARGS models") for c in calls),
   "GENTLEMONSTER_AGY_MODEL is the user's choice and is used as is")
models_json.write_text(json.dumps([{"slug": "gemini-3.5-flash"}, {"slug": "gemini-3.1-pro"}]))
rc, out, calls = launch()
ok(rc == 2 and len(out) == 1 and "gemini-3.1-pro" in out[0] and not any("--model" in c for c in calls), "no Gemini 3 Flash in agy -> stop, list, agy not started")
rc, out, calls = launch("--version")
ok(rc == 0 and out == ["1.2.16"] and calls == ["ARGS --version | CWD " + str(Path.cwd()) + " | MODEL= HOST="] or (rc == 0 and out == ["1.2.16"]),
   "--version passes through to agy")
models_json.write_text(lst)
rc, out, calls = launch("--check")
ok(rc == 0 and any("served model: gemini-3-flash (as asked)" in o and "pf_show" in o for o in out) and "-p" in calls[-1] and "--output-format json" in calls[-1],
   f"--check runs one headless turn and prints the served model ({out})")
rc, out, calls = launch(path=False)
ok(rc == 1 and len(out) == 1 and "agy is not on PATH" in out[0], "no agy -> one line with the install command")

p = subprocess.run([str(vbin / "gmg"), "doctor", "--host", "agy"], capture_output=True, text=True,
                   env={"HOME": str(home), "PATH": str(bin_) + ":/usr/bin:/bin", "GMG_UPSTREAM": os.environ["GMG_UPSTREAM"], "GMG_OUT": str(TMP / "out")})
d = p.stdout
ok("no API key needed" in d and "GEMINI_API_KEY" not in d and "ok   Antigravity CLI 1.2.16" in d and "Gemini CLI" not in d.replace("Antigravity CLI", ""),
   "doctor --host agy: no key asked, agy found, no Gemini CLI check")
ok(re.search(r"ok   agy workspace .* has this extension's MCP servers and rules", d), "doctor --host agy: the workspace files are checked")

print("== the install block")
block = (ROOT / "install" / "macos-agy.zsh").read_text()
lines = [ln for ln in block.splitlines() if ln.strip()]
ok(not any(ln.lstrip().startswith("#") for ln in lines) and "<" not in block and ">" not in block, "no comment lines, no angle brackets")
sha = re.findall(r"origin (\S+)\n.*checkout -q (\S+)", block)
ok(sha and sha[0][0] == sha[0][1] and (re.fullmatch(r"[0-9a-f]{40}", sha[0][0]) or sha[0][0] == "PREVIEW_SHA"), "the extension is checked out at one commit")
ok("pip install --quiet -e" in block and "gmg\" doctor --host agy" in block and lines[-1] == "gentlemonster-agy --check", "editable install, agy doctor, ends with the check turn")
ok("GEMINI_API_KEY" not in block and "npm" not in block, "no API key and no Gemini CLI needed")
ok("grep -qs 'gentlemonster/bin' \"$HOME/.zshrc\" ||" in block, "PATH line added once")
usage = (ROOT / "USAGE.md").read_text()
ok(block.strip() in usage or "INSTALL_BLOCK_AGY" in usage, "USAGE.md shows the same block")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("all passed" if not FAIL else f"{len(FAIL)} failed"))
sys.exit(1 if FAIL else 0)
