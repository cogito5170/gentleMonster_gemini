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
    ("sleep after the last attempt", "gmg/gemini.py", "if code in RETRY and a < self.attempts:", "if code in RETRY:"),
    ("model mismatch not flagged", "gmg/gemini.py", 'mismatch = reported != "미보고" and not reported.startswith(self.model)', "mismatch = False"),
    ("key written to the ledger", "gmg/gemini.py", "base = dict(step=step,", "base = dict(hdr=hdr, step=step,"),
    ("status ignores the hash", "gmg/ledger.py", 'sha256(p) == e["sha256"]', "True"),
    ("Korean not caught", "gmg/schema.py", 'if s.get("english") and HANGUL.search(v):', "if False:"),
    ("no re-ask", "gmg/steps.py", "def _ask(ctx, step, prompt, sch, extra=None, retries=1,", "def _ask(ctx, step, prompt, sch, extra=None, retries=0,"),
    ("size not read", "gmg/steps.py", "            return float(m.group(1)), float(m.group(2))", "            return None, None"),
    ("cast fallback off", "gmg/steps.py", "        if bad:                                     # keep", "        if False:                                   # keep"),
    ("why without the measured fact", "gmg/steps.py", 'out["why"] = [{"t": w["t"], "d": f"{F[i]} {w[\'meaning\']}"}', 'out["why"] = [{"t": w["t"], "d": w["meaning"]}'),
    ("pin not checked", "gmg/upstream.py", 'if head(r) != LOCK["commit"]:\n        raise NotReady(f"gentleMonster is not', 'if False:\n        raise NotReady(f"gentleMonster is not'),
    ("notification answered", "gmg/mcp.py", "    if mid is None:\n        return None", "    if False:\n        return None"),
    ("render without a recorded job", "gmg/run.py", 'if st["artifacts"].get("job") != "done":', "if False:"),
]


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
        r = subprocess.run([sys.executable, str(d / "r" / "tests" / "test_gmg.py")], capture_output=True, text=True, timeout=600)
        red = r.returncode != 0
        caught += red
        print(("  red  " if red else "  MISSED ") + name)
        shutil.rmtree(d, ignore_errors=True)
    print(f"\n{caught}/{len(M)} mutations caught")
    return 0 if caught == len(M) else 1


if __name__ == "__main__":
    sys.exit(main())
