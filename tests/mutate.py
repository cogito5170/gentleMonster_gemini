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
    ("pf: abstract gate off", "gmg/portfolio.py", '    if meas["abstract_ratio"] > lim:', "    if False:"),
    ("pf: language not checked", "gmg/portfolio.py", '    if lang == "ko" and meas["language"] == "en" or', '    if False and lang == "ko" and meas["language"] == "en" or'),
    ("pf: more_direct not checked", "gmg/portfolio.py", "        if a1 > LIMIT_DIRECT or (a1 >= a0 and a0 > 0):", "        if False:"),
    ("pf: refocus not checked", "gmg/portfolio.py", "        elif _has(new, topic) <= _has(old, topic) and not _has(new, topic):", "        elif False:"),
    ("pf: not exactly three proposals", "gmg/portfolio.py", "        if len(opts) != 3:", "        if False:"),
    ("pf: labels inside words", "gmg/portfolio.py", 'r"(?<![A-Za-z0-9])[A-Ha-h1-8](?![A-Za-z0-9])"', 'r"[A-Ha-h1-8]"'),
    ("pf: retry not recorded", "gmg/portfolio.py", '        L.log("RETRY", call=last)', "        pass"),
    ("pf: before not kept", "gmg/portfolio.py", "measures=meas, before=o[\"text\"])", "measures=meas, before=\"\")"),
    ("pf: concept reason not checked", "gmg/portfolio.py", "        if v and not any(w in r.lower() for w in pool):", "        if False:"),
    ("photo: small subjects missed", "gmg/photo.py", "regions += n >= .003 * m.size", "regions += n >= .01 * m.size"),
    ("photo: palette not distinct", "gmg/photo.py", "def distinct(pal, n: int = 5, gap: float = 30)", "def distinct(pal, n: int = 5, gap: float = 0)"),
    ("render: failure cause not kept", "gmg/agent.py", '            L.log("NOTE", step="render", why=why)', "            pass"),
    ("amend: unsupported called supported", "gmg/agent.py", '("language", "ko_and_en"): "NOT supported:', '("language", "ko_and_en"): "supported:'),
    ("pf: keep ignored", "gmg/portfolio.py", "and not any(k in x.lower() for k in kept))", ")"),
    ("H1: placeholder brand used", "gmg/agent.py", "    if b and placeholder(b):", "    if False:"),
    ("H1: placeholders reach the page", "gmg/agent.py", "    probs += [f\"{k} is placeholder text ({v!r}); write the real text\" for k, v in page if placeholder(v)]", "    pass"),
    ("H2: no served warning in results", "gmg/ext_mcp.py", "            if w:\n                r[\"served\"] = w", "            if False:\n                r[\"served\"] = w"),
    ("H2: hook records nothing", "gmg/hook.py", "    r = SV.record(models[-1], \"gemini-cli\")", "    r = {\"differs\": True}"),
    ("H2: explain hides the served model", "gmg/agent.py", "        elif k == \"SERVED\":", "        elif False:"),
    ("H3: plan in gm_new ignored", "gmg/agent.py", "    if plan in PL.PLANS:", "    if False:"),
    ("finish: vague palette error", "gmg/agent.py", "    probs += bad_hex", "    probs += [\"palette invalid\"] if bad_hex else []"),
    ("new: brand spelling not canonical", "gmg/agent.py", "    if re.sub(r\"[^a-z]\", \"\", b.lower()) in canon and", "    if False and"),
    ("new: tool name taken as a brand claim", "gmg/agent.py", "    named = bool(b) and b.lower() in request.lower()", "    named = bool(b)"),
    ("H3: tool groups ignored", "gmg/ext_mcp.py", 'return [t for t in _tools() if group == "all" or t["name"].startswith(GROUPS[group])]', "return _tools()"),
    ("P1: storyline accepted by pf_write", "gmg/portfolio.py", '    if kind == "storyline":', "    if False:"),
    ("P1: photo kinds without a photo", "gmg/portfolio.py", '    if kind in PHOTO_KINDS and not any(p["id"] == about for p in st["photos"]):', "    if False:"),
    ("P2: unmeasured images not listed", "gmg/ext_mcp.py", '                    if um and p.get("name") != "pf_photos":', "                    if False:"),
    ("P3: terse reply not routed", "gmg/ext_mcp.py", "                    g = turn.gate(p.get(\"name\") or \"\")", "                    g = None"),
    ("P2/P3: turn note never added", "gmg/loop.py", '([{"text": f"<hook_context>{note}</hook_context>"}] if note else [])', "[]"),
    ("P3: terse reply not in the note", "gmg/turn.py", "    if t[\"terse\"]:\n        out.append(", "    if False:\n        out.append("),
    ("P2: images not in the note", "gmg/turn.py", "    if t[\"images\"]:\n        out.append(", "    if False:\n        out.append("),
    ("hook: note not returned", "hooks/turn_note.py", '"additionalContext": n}} if n else {}', '"additionalContext": ""}} if False else {}'),
    ("P1: embedded questions ignored", "gmg/portfolio.py", "    if kind == \"answer\" and len(items) < len(asked):", "    if False:"),
    ("route: adoption not sent to pf_choose", "gmg/turn.py", "    pick = t[\"prompt\"].strip() if t[\"terse\"] else t.get(\"adopts\")", "    pick = t[\"prompt\"].strip() if t[\"terse\"] else None"),
    ("route: page flow not sent to pf_pages", "gmg/turn.py", " and not t.get(\"flowed\") and tool == \"pf_write\" and \"flow\" not in fired:", " and False:"),
    ("route: pf_pages never marks the flow", "gmg/ext_mcp.py", "                        turn.mark_flowed()", "                        pass"),
    ("route: English article read as a label", "gmg/turn.py", "((?-i:[A-H1-8]))", "([A-Ha-h1-8])"),
    ("refocus: list error lacks widen", "gmg/portfolio.py", "        elif re.search(r\"[,·/]\", topic):", "        elif False:"),
    ("note: widen not said", "gmg/turn.py", "    if t.get(\"widen\"):", "    if False:"),
    ("loop: daily quota waited out", "gmg/loop.py", "QUOTA_GONE = 600 ", "QUOTA_GONE = 10**9 "),
    ("route: a redirect fires forever", "gmg/turn.py", "    t[\"fired\"] = (t.get(\"fired\") or []) + [which]", "    t[\"fired\"] = []"),
    ("route: pf_pages show counts as the page map", "gmg/ext_mcp.py", ' and (p.get("arguments") or {}).get("action") != "show":', ":"),
    ("export: paths kept", "gmg/usage.py", "        s = PATHS.sub(self._path, s)", "        s = s"),
    ("export: keys kept", "gmg/usage.py", '        s = KEYS.sub("***", s)', "        s = s"),
    ("export: blobs kept", "gmg/usage.py", '        s = BLOB.sub("[bytes removed]", s)', "        s = s"),
    ("export: image not measured", "gmg/usage.py", '"measured": _measure(p)}', '"measured": None}'),
    ("export: image not named by hash", "gmg/usage.py", '                    return f"[image sha256:{sha[:16]}]"', '                    return "[path]"'),
    ("export: redirects counted as re-asks", "gmg/usage.py", 'if c.get("ok") is False and not c.get("redirected")),', 'if c.get("ok") is False),'),
    ("usage: tool calls not logged", "gmg/ext_mcp.py", '            usage.log("call",', '            (lambda *a, **k: None)("call",'),
    ("usage: hook drops the session id", "hooks/turn_note.py", 'inp.get("session_id", "")', '""'),
    ("usage: session id not hashed", "gmg/usage.py", '"session": hashlib.sha256(s.encode()).hexdigest()[:16]', '"session": s'),
    ("server: venv never used", "server.py", "    os.execv(str(PY), [str(PY)] + sys.argv)", "    pass"),
    ("P4: no aliases", "gmg/portfolio.py", "    return {w} | {b for a, b in ALIASES if a == w} | {a for a, b in ALIASES if b == w}", "    return {w}"),
    ("H3: colours not nudged", "gmg/agent.py", "        for _ in range(30):", "        for _ in range(0):"),
    ("loop: server delay ignored", "gmg/loop.py", "sleep(min(w, 60) if w is not None else 2 ** attempt)", "sleep(1)"),
]
TESTS = ["tests/test_gmg.py", "tests/test_ext.py", "tests/test_pf.py", "tests/test_usage.py"]


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
