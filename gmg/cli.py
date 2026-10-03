"""gmg -- gentleMonster on gemini-3.1-flash-lite.

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

from gmg import MODEL, run, upstream
from gmg.gemini import API, key


def _name(brief: str, name: str) -> str:
    if name:
        return name
    import hashlib
    return "gmg_" + hashlib.sha256(brief.encode()).hexdigest()[:10]


def doctor() -> int:
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
    say(bool(k), "GEMINI_API_KEY is set" + ("" if k else " (value never shown)"))
    model = os.environ.get("GMG_MODEL") or MODEL
    if k:
        try:
            req = urllib.request.Request(f"{API}/models/{model}", headers={"x-goog-api-key": k})
            with urllib.request.urlopen(req, timeout=30) as r:
                m = json.loads(r.read().decode())
            say("generateContent" in m.get("supportedGenerationMethods", []), f"{model} is listed and takes generateContent")
        except Exception as e:                              # noqa: BLE001
            say(False, f"{model} could not be read: {type(e).__name__}")
    else:
        say(False, f"{model} not checked (no key) -- an unchecked model is not counted as ok")
    import shutil
    import subprocess
    g = shutil.which("gemini")
    if g:
        try:
            v = subprocess.run([g, "--version"], capture_output=True, text=True, timeout=60).stdout.strip()
            parts = tuple(int(x) for x in re.findall(r"\d+", v)[:3])
            say(parts < (0, 61, 0), f"Gemini CLI {v}" + ("" if parts < (0, 61, 0) else
                " maps gemini-3.1-flash-lite to gemini-3.5-flash-lite; install @google/gemini-cli@0.60.0 to keep 3.1"))
        except Exception as e:                              # noqa: BLE001
            say(False, f"Gemini CLI version could not be read: {type(e).__name__}")
    else:
        print("  --   Gemini CLI not on PATH (the extension needs it; the API harness does not)")
    for mod in ("PIL", "numpy", "matplotlib", "playwright"):
        try:
            __import__(mod)
            say(True, f"{mod} (for the PDFs)")
        except ImportError:
            say(False, f"{mod} missing -- pip install 'gentlemonster-gemini[render]' (decisions still run with --no-draw)")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gmg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    sub.add_parser("doctor")
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
            return doctor()
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
