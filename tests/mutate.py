"""Mutation check: break one guarantee at a time in a copy of gmg; the test suite must fail every time.
Run: python3 tests/mutate.py   (same environment as tests/test_gmg.py)"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = [
    ("finishReason gate off", "gmg/gemini.py", 'if finish != "STOP":', "if False:"),
    ("blocked prompt not caught", "gmg/gemini.py", "if block or not cands:", "if False:"),
    ("sleep after the last attempt", "gmg/gemini.py", "if code in RETRY and a < self.attempts + (QUOTA_EXTRA if code == 429 else 0):", "if code in RETRY:"),
    ("server retry delay ignored", "gmg/gemini.py", "                wait = _retry_delay(text, rh)", "                wait = None"),
    ("no extra attempts for a quota", "gmg/gemini.py", "QUOTA_EXTRA = 2 ", "QUOTA_EXTRA = 0 "),
    ("model mismatch not flagged", "gmg/gemini.py", 'mismatch = reported != "미보고" and not reported.startswith(self.model)', "mismatch = False"),
    ("key written to the ledger", "gmg/gemini.py", "base = dict(step=step,", "base = dict(hdr=hdr, step=step,"),
    ("status ignores the hash", "gmg/ledger.py", 'sha256(p) == e["sha256"]', "True"),
    ("Korean not caught", "gmg/schema.py", 'if s.get("english") and HANGUL.search(v):', "if False:"),
    ("no re-ask", "gmg/steps.py", "def _ask(ctx, step, prompt, sch, extra=None, retries=1,", "def _ask(ctx, step, prompt, sch, extra=None, retries=0,"),
    ("size not read", "gmg/steps.py", "            return float(m.group(1)), float(m.group(2))", "            return None, None"),
    ("brand invented", "gmg/steps.py", "    out = dict(v, brand=brand or (named if seen else \"\") or \"Gentle Monster\"", "    out = dict(v, brand=brand or named or \"Gentle Monster\""),
    ("cast fallback off", "gmg/steps.py", "        if bad:                                     # keep", "        if False:                                   # keep"),
    ("why without the measured fact", "gmg/steps.py", 'out["why"] = [{"t": w["t"], "d": f"{F[i]} {w[\'meaning\']}"}', 'out["why"] = [{"t": w["t"], "d": w["meaning"]}'),
    ("pin not checked", "gmg/upstream.py", 'if head(r) != LOCK["commit"]:\n        raise NotReady(f"gentleMonster is not', 'if False:\n        raise NotReady(f"gentleMonster is not'),
    ("notification answered", "gmg/mcp.py", "    if mid is None:\n        return None", "    if False:\n        return None"),
    ("render without a recorded job", "gmg/run.py", 'if st["artifacts"].get("job") != "done":', "if False:"),
    # the extension's state machine, hook and loop
    ("ext: no next list", "gmg/agent.py", '"notes": notes, "next": [offer_plan(spec, job, W, D)]}', '"notes": notes, "next": []}'),
    ("ext: long text not cut", "gmg/agent.py", "    if len(t) <= n:\n        return t, False", "    if True:\n        return t, False"),
    ("ext: brand note missing", "gmg/agent.py", "    if b and not any(w.lower() in request.lower()", "    if False and not any(w.lower() in request.lower()"),
    ("ext: known brand product ignored", "gmg/agent.py", "    if known and product not in known:", "    if False:"),
    ("ext: default brand overrides product", "gmg/agent.py", "KNOWN.get(b.lower()) if named else None", "KNOWN.get(b.lower())"),
    ("ext: not idempotent", "gmg/agent.py", '    if not _same(L, "new", args):', "    if True:"),
    ("ext: stale steps used", "gmg/agent.py", "    if any(last.get(s, -1) > last[step] for s in ORDER[:k]):", "    if False:"),
    ("ext: order after arguments", "gmg/agent.py", "        if name in PREREQ and", "        if False and name in PREREQ and"),
    ("ext: caption person not checked", "gmg/agent.py", '            if s.get("cap") and not re.search(r"\\b(I|my|me)\\b", s["cap"]):', "            if False:"),
    ("ext: fallback not said", "gmg/agent.py", "        if fb:\n            notes.append", "        if False:\n            notes.append"),
    ("ext: no geometry repair", "gmg/agent.py", "                if c[\"cast\"][r][\"shape\"] != own:", "                if False:"),
    ("hook: never denies", "gmg/hook.py", '    return {"decision": "deny",', '    return {"decision": "allow",'),
    ("loop: off-list not counted", "gmg/loop.py", '"offlist": fc.get("name") not in prev_next', '"offlist": False'),
    ("loop: server delay ignored", "gmg/loop.py", "sleep(min(w, 60) if w is not None else 2 ** attempt)", "sleep(1)"),
]
TESTS = ["tests/test_gmg.py", "tests/test_ext.py"]


def main() -> int:
    caught = 0
    for name, f, old, new in M:
        d = Path(tempfile.mkdtemp(prefix="gmg_mut_"))
        shutil.copytree(ROOT, d / "r", ignore=shutil.ignore_patterns(".git", "__pycache__", "out", "bench"))
        p = d / "r" / f
        s = p.read_text()
        if old not in s:
            print(f"  ??  {name}: the code to mutate is not there any more")
            shutil.rmtree(d)
            return 2
        p.write_text(s.replace(old, new, 1))
        red = any(subprocess.run([sys.executable, str(d / "r" / t)], capture_output=True, text=True, timeout=600).returncode != 0 for t in TESTS)
        caught += red
        print(("  red  " if red else "  MISSED ") + name)
        shutil.rmtree(d, ignore_errors=True)
    print(f"\n{caught}/{len(M)} mutations caught")
    return 0 if caught == len(M) else 1


if __name__ == "__main__":
    sys.exit(main())
