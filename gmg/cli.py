"""gmg -- gentleMonster on Gemini (default gemini-3-flash-preview).

    gmg setup                               fetch / check the pinned gentleMonster
    gmg doctor                              key present? model listed with generateContent? pinned code? deps?
    gmg make "<brief>" [--brand B] [--name N] [--no-draw] [--moodboard] [--ref img]
    gmg step <name> <brief|plan|cast|room|story|palette|stops|assemble> [--brief ...]   one decision
    gmg render <name> [--moodboard]         PDFs from a job the ledger recorded
    gmg status <name> · gmg explain <name> [--step S] · gmg runs · gmg check <job.json> · gmg plans

Exit codes: 0 done · 3 needs review (a gate did not pass) · 1 failed · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from gmg import CLI_PIN, asked_model, run, upstream
from gmg.gemini import API, key


def _name(brief: str, name: str) -> str:
    if name:
        return name
    import hashlib
    return "gmg_" + hashlib.sha256(brief.encode()).hexdigest()[:10]


def cli_version(g: str, private: bool) -> str:
    """`gemini --version`. The private CLI runs in its own home, as the launcher runs it, so your ~/.gemini is not written."""
    import subprocess
    env = dict(os.environ)
    if private:
        from gmg import telemetry as TM
        env["GEMINI_CLI_HOME"] = str(TM.cli_home())
    return subprocess.run([g, "--version"], capture_output=True, text=True, timeout=60, env=env).stdout.strip()


def doctor(host: str = "") -> int:
    """host "" = Gemini CLI with an API key; "agy" = Antigravity CLI (Google sign-in); "google" = Gemini CLI with Login with Google."""
    ok = True

    def say(good, what):
        nonlocal ok
        ok &= bool(good)
        print(("  ok   " if good else "  FAIL ") + what)
    try:
        upstream.ready()
        say(True, f"gentleMonster at the pinned commit {upstream.LOCK['commit'][:12]}")
    except upstream.NotReady as e:
        say(False, str(e))
    k = key()
    model = asked_model()
    if host:
        print(f"  --   no API key needed ({'Antigravity CLI' if host == 'agy' else 'Gemini CLI'} signs in with your Google account)")
    else:
        say(bool(k), "GEMINI_API_KEY is set" + ("" if k else " (value never shown)"))
        if k:
            try:
                req = urllib.request.Request(f"{API}/models/{model}", headers={"x-goog-api-key": k})
                with urllib.request.urlopen(req, timeout=30) as r:
                    m = json.loads(r.read().decode())
                say("generateContent" in m.get("supportedGenerationMethods", []), f"{model} is listed and takes generateContent")
            except Exception as e:                          # noqa: BLE001
                say(False, f"{model} could not be read: {type(e).__name__}")
        else:
            say(False, f"{model} not checked (no key) -- an unchecked model is not counted as ok")
    import shutil
    import subprocess
    if host == "agy":
        a = shutil.which("agy")
        try:
            v = subprocess.run([a, "--version"], capture_output=True, text=True, timeout=60).stdout.strip() if a else ""
        except Exception:                                   # noqa: BLE001
            v = ""
        say(bool(v), f"Antigravity CLI {v}" if v else "agy not found on PATH -- install it (USAGE.md, Antigravity)")
        from gmg import agy as AG
        w = Path.home() / "gentlemonster"
        good = all((w / rel).is_file() and (w / rel).read_text(encoding="utf-8") == text
                   for rel, text in AG.files(w, str(Path(sys.executable))).items())
        say(good, f"agy workspace {w} has this extension's MCP servers and rules" + ("" if good else " -- run: gentlemonster-agy --version"))
    private = Path.home() / ".gentlemonster" / "cli" / "node_modules" / ".bin" / "gemini"     # the `gentlemonster` launcher's CLI
    g = None if host == "agy" else str(private) if private.is_file() else shutil.which("gemini")
    if g:
        try:
            v = cli_version(g, private=g == str(private))
            say(v == CLI_PIN, f"Gemini CLI {v}" + (" (private, used by `gentlemonster`)" if g == str(private) else "") + ("" if v == CLI_PIN else
                f" -- the pinned CLI is {CLI_PIN}; paste the install block from USAGE.md again"))
        except Exception as e:                              # noqa: BLE001
            say(False, f"Gemini CLI version could not be read: {type(e).__name__}")
    elif host != "agy":
        print("  --   Gemini CLI not on PATH (the extension needs it; the API harness does not)")
    if host != "agy":
        from gmg import telemetry as TM
        say(*TM.check())
    for mod in ("PIL", "numpy", "matplotlib", "playwright"):
        try:
            __import__(mod)
            say(True, f"{mod} (for the PDFs)")
        except ImportError:
            say(False, f"{mod} missing -- pip install 'gentlemonster-gemini[render]' (decisions still run with --no-draw)")
    try:
        from playwright.sync_api import sync_playwright
        upstream.load()
        from gentle_monster import paths as GP              # the pinned code's own launcher (it prefers a preinstalled Chromium)
        with sync_playwright() as pw:
            GP.launch(pw, gl=False).close()
        say(True, "Chromium starts (the PDFs are drawn in it)")
    except ImportError:
        pass
    except Exception as e:                                  # noqa: BLE001 -- also upstream.NotReady: said above
        say(False, f"Chromium does not start ({type(e).__name__}) -- run: {sys.executable} -m playwright install chromium")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gmg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    dr = sub.add_parser("doctor")
    dr.add_argument("--host", choices=["", "agy", "google"], default="")
    ag = sub.add_parser("agy-setup", help="write the agy workspace files (MCP servers, rules); rerun-safe")
    ag.add_argument("--workspace", default=str(Path.home() / "gentlemonster"))
    sub.add_parser("cli-settings", help="for the gentlemonster launcher: put the heap fix into the private CLI's settings when telemetry is off")
    sub.add_parser("agy-model", help="stdin: agy models --output-format json; prints agy's slug for gemini-3-flash-preview")
    sub.add_parser("agy-served", help="stdin: an agy -p --output-format json run; records and prints the served model")
    sub.add_parser("plans")
    m = sub.add_parser("make")
    m.add_argument("brief")
    m.add_argument("--brand", default="")
    m.add_argument("--name", default="")
    m.add_argument("--no-draw", action="store_true")
    m.add_argument("--moodboard", action="store_true")
    m.add_argument("--ref", action="append", default=[])
    s = sub.add_parser("step")
    s.add_argument("name")
    s.add_argument("step", choices=run.ORDER + ["assemble", "start"])
    s.add_argument("--brief", default="")
    s.add_argument("--brand", default="")
    r = sub.add_parser("render")
    r.add_argument("name")
    r.add_argument("--moodboard", action="store_true")
    for c in ("status", "explain"):
        x = sub.add_parser(c)
        x.add_argument("name")
        if c == "explain":
            x.add_argument("--step", default="")
    sub.add_parser("runs")
    ex = sub.add_parser("export", help="one JSONL per session of real use, paths/keys/image bytes removed; review before sharing")
    ex.add_argument("--out", default="")
    ex.add_argument("--session", default="")
    ck = sub.add_parser("check")
    ck.add_argument("job")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "setup":
            upstream.setup()
            return 0
        if a.cmd == "doctor":
            return doctor(a.host)
        if a.cmd == "agy-setup":
            from gmg import agy as AG
            changed = AG.setup(a.workspace, str(Path(sys.executable)))
            print(f"agy workspace {a.workspace}: " + (", ".join(changed) + " written" if changed else "up to date"))
            return 0
        if a.cmd == "cli-settings":
            from gmg import telemetry as TM
            p, changed = TM.ensure()
            print(f"{p}: " + ("heap fix written" if changed else "up to date"))
            return 0
        if a.cmd == "agy-model":
            from gmg import agy as AG
            return AG.main_model()
        if a.cmd == "agy-served":
            from gmg import agy as AG
            return AG.main_served()
        if a.cmd == "export":
            from gmg import usage
            files = usage.export(Path(a.out) if a.out else None, a.session)
            for f in files:
                print(f)
            print(f"{len(files)} session file(s). Read them before sharing; share only into the private repo cogito5170/gm-photos under usage/."
                  if files else "nothing logged yet (usage.jsonl is empty)")
            return 0
        if a.cmd == "plans":
            from gmg import plans as PL
            for k, p in PL.PLANS.items():
                print(f"{k}: {p['desc']}\n  roles: " + ", ".join(f"{r} ({'/'.join(x['shapes'])})" for r, x in p["roles"].items()))
            return 0
        if a.cmd == "make":
            res = run.make(_name(a.brief, a.name), a.brief, a.brand, draw=not a.no_draw, moodboard=a.moodboard, refs=a.ref)
            print(json.dumps(res, ensure_ascii=False, indent=1))
            return res["rc"]
        if a.cmd == "step":
            ctx = run.context(a.name)
            if a.step == "start":
                print(run.start(ctx, a.brief, a.brand))
                return 0
            if a.step == "assemble":
                res = run.assemble(ctx)
                print(json.dumps({"problems": res["problems"], "reverted": res["reverted"]}, ensure_ascii=False, indent=1))
                return 0 if not res["problems"] else 3
            print(json.dumps(run.step(ctx, a.step, brief=a.brief, brand=a.brand), ensure_ascii=False, indent=1))
            return 0
        if a.cmd == "render":
            res = run.render(run.context(a.name), moodboard=a.moodboard)
            print(json.dumps({k: str(v) for k, v in res.items() if k in ("pdf", "preview", "moodboard")}, indent=1))
            return 0
        if a.cmd == "status":
            print(json.dumps(run.status(a.name), ensure_ascii=False, indent=1))
            return 0
        if a.cmd == "explain":
            print(run.explain(a.name, step_name=a.step))
            return 0
        if a.cmd == "runs":
            print(json.dumps(run.runs(), ensure_ascii=False, indent=1))
            return 0
        if a.cmd == "check":
            spec, _ = upstream.load()
            bad = spec.check(spec.load(a.job))
            print("ok" if not bad else "\n".join("- " + b for b in bad))
            return 0 if not bad else 3
    except upstream.NotReady as e:
        print(f"[gmg] not ready: {e}", file=sys.stderr)
        return 1
    except Exception as e:                                  # noqa: BLE001
        msg = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "***", str(e))
        print(f"[gmg {a.cmd} failed] {type(e).__name__}: {msg}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
