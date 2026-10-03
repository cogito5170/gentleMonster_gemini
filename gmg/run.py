"""The fixed plan of a job: steps in order, judged by code, recorded in the ledger.

    brief -> plan -> cast -> room -> story -> palette -> stops -> assemble (spec.check) -> render (PDFs)

Exit codes: 0 DONE (spec.check passed) · 3 NEEDS_REVIEW (a gate did not pass) · 1 FAILED (the model or the run failed).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

from gmg import MODEL, steps as ST, upstream
from gmg.gemini import Gemini, ModelError
from gmg.ledger import Ledger, totals

ORDER = ["brief", "plan", "cast", "room", "story", "palette", "stops"]
FN = {"plan": ST.pick_plan, "cast": ST.cast_roles, "room": ST.pick_room, "story": ST.write_story,
      "palette": ST.pick_palette, "stops": ST.write_stops}
RC = {"DONE": 0, "NEEDS_REVIEW": 3, "FAILED": 1}


def context(name: str, transport=None, out_dir=None) -> ST.Ctx:
    spec, paths = upstream.load(out_dir)
    from gentle_monster import pipeline
    d = paths.job_dir(name)
    L = Ledger(d)
    return ST.Ctx(name, L, Gemini(L, transport=transport), spec, pipeline)


def start(ctx, brief: str, brand: str = "") -> str:
    rid = uuid.uuid4().hex[:12]
    ctx.L.log("START", run=rid, job=ctx.name, brief=brief, brand=brand, model=ctx.g.model,
              upstream=upstream.LOCK["commit"], brief_sha=hashlib.sha256(brief.encode()).hexdigest()[:16])
    return rid


def step(ctx, name: str, **kw):
    if name == "brief":
        return ST.read_brief(ctx, kw["brief"], kw.get("brand", ""))
    return FN[name](ctx)


def finish(ctx, rc_state: str, **kw) -> int:
    ctx.L.log("END", state=rc_state, rc=RC[rc_state], **kw)
    return RC[rc_state]


def assemble(ctx) -> dict:
    r = ST.assemble(ctx)
    if not r["problems"]:
        p = ctx.pipeline.save_job(ctx.name, r["job"])
        ctx.L.artifact(p, "job")
        ctx.L.artifact(p.parent / "synopsis.md", "synopsis")
    return r


def render(ctx, moodboard: bool = False, refs=(), log=None) -> dict:
    """Layout PDF (+ moodboard) from job.json with the pinned gentleMonster. Only a job the ledger recorded is drawn."""
    st = ctx.L.status()
    if st["artifacts"].get("job") != "done":
        raise RuntimeError("job.json is not recorded as done in the ledger -- run make (or assemble) first")
    log = log or (lambda m: print(m, file=sys.stderr))
    with contextlib.redirect_stdout(sys.stderr):
        r = ctx.pipeline.layout(ctx.name, moodboard=False, use_llm=False, log=log)
        ctx.L.artifact(r["pdf"], "layout")
        ctx.L.artifact(r["preview"], "layout_preview")
        if moodboard:
            from gentle_monster import moodboard as MB, render as RD
            d = ctx.L.dir
            refs = ctx.pipeline._keep(ctx.name, refs, "refs", log) or ctx.pipeline._kept(ctx.name, "refs")
            photos = ctx.pipeline._kept(ctx.name, "photos")
            renders = []
            if len(photos) < 3:
                have = {v: d / f"render_{v}.png" for v in ctx.pipeline.MOOD_VIEWS}
                if not all(p.is_file() for p in have.values()):
                    RD.stills(ctx.pipeline.load_job(ctx.name), d, views=[v for v, p in have.items() if not p.is_file()], w=1400, h=900)
                renders = [str(p) for p in have.values()]
            m = MB.build(ctx.pipeline.load_job(ctx.name), d, photos, refs, renders=renders, plan=r["plan"],
                         ask_vision=ST.vision(ctx, MB.CATALOG), use_llm=bool(refs))
            ctx.L.artifact(m["pdf"], "moodboard")
            r["moodboard"] = m["pdf"]
    return r


def make(name: str, brief: str, brand: str = "", draw: bool = True, moodboard: bool = False, refs=(), transport=None,
         out_dir=None, log=None) -> dict:
    log = log or (lambda m: print(m, file=sys.stderr))
    ctx = context(name, transport, out_dir)
    t0 = time.time()
    start(ctx, brief, brand)
    try:
        for s in ORDER:
            step(ctx, s, brief=brief, brand=brand)
            log(f"[gmg] {s} decided")
        r = assemble(ctx)
        if r["problems"]:
            rc = finish(ctx, "NEEDS_REVIEW", seconds=round(time.time() - t0, 1), why="spec.check: " + "; ".join(r["problems"][:6]))
        else:
            if draw:
                render(ctx, moodboard=moodboard, refs=refs, log=log)
            rc = finish(ctx, "DONE", seconds=round(time.time() - t0, 1))
    except ST.StepFailed as e:
        rc = finish(ctx, "NEEDS_REVIEW", seconds=round(time.time() - t0, 1), why=f"step {e.step} did not pass: " + "; ".join(e.problems[:6]))
    except ModelError as e:
        rc = finish(ctx, "FAILED", seconds=round(time.time() - t0, 1), why=f"model call {e.outcome}")
    return {"rc": rc, "dir": str(ctx.L.dir), **ctx.L.status()}


# ------------------------------------------------------------------ read-only views (ledger only)
def status(name: str, out_dir=None) -> dict:
    _, paths = upstream.load(out_dir)
    return Ledger(paths.job_dir(name)).status()


def runs(out_dir=None, limit: int = 20) -> "list[dict]":
    _, paths = upstream.load(out_dir)
    out = []
    for f in sorted(Path(paths.OUT).glob("*/gmg_ledger.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        s = Ledger(f.parent).status()
        out.append({"job": f.parent.name, "state": s["state"], "model_calls": s["model_calls"]})
    return out


def explain(name: str, out_dir=None, step_name: str = "") -> str:
    """Why the job came out the way it did -- rendered from the ledger, nothing else."""
    _, paths = upstream.load(out_dir)
    run = Ledger(paths.job_dir(name)).run()
    if not run:
        return f"(no ledger for {name})"
    st = run[0]
    lines = [f"# {name}", f"brief: {st.get('brief')}", f"model asked: {st.get('model')} · gentleMonster @ {str(st.get('upstream'))[:12]}", ""]
    calls = [e for e in run if e["kind"] == "MODEL_CALL"]
    for e in run:
        k = e["kind"]
        if step_name and e.get("step") not in (step_name, None):
            continue
        if k == "DECISION":
            o = e["output"]
            lines.append(f"## {e['step']}  (asked {e.get('asks', 0)} time(s))")
            if e["step"] == "brief":
                lines.append(f"- brand: {o['brand']} ({e.get('why', {}).get('brand')}) · size: {o['W'] or '-'} x {o['D'] or '-'} m ({e.get('why', {}).get('size')})")
                lines.append(f"- theme: {o['theme']} · hero idea: {o['hero_idea']} · product: {o['product']}")
            elif e["step"] == "plan":
                lines.append(f"- chose **{o['plan']}** of {len(e.get('options', {}))} listed plans: {o['reason']}")
                lines.append(f"- built {o['W']:g} x {o['D']:g} x {o['H']:g} m (scale {o['sx']} x {o['sy']}; tries {e.get('scale_tries')})")
            elif e["step"] == "cast":
                lines += [f"- {r}: {x['label']} = {x['shape']} in {x['material']}" for r, x in o.items()]
            elif e["step"] == "story":
                lines += [f"- **{o['title']}** — {o['line']}"] + [f"- fact {i + 1} (code): {f}" for i, f in enumerate(e.get("facts", []))]
            elif e["step"] == "assemble":
                lines.append("- spec.check: " + ("passed" if not o["problems"] else "; ".join(o["problems"])))
            else:
                lines.append("- " + json.dumps(o, ensure_ascii=False)[:400])
        elif k in ("FALLBACK", "REPAIR"):
            lines.append(f"- **{k.lower()}** in {e['step']}: {e.get('used') or e.get('why')} ({'; '.join(map(str, e.get('problems') or e.get('reverted') or []))[:300]})")
        elif k == "MODEL_CALL" and e.get("outcome") != "ok":
            lines.append(f"- model call {e['step']} #{e['attempt']}: {e['outcome']} {'; '.join(e.get('problems') or [])[:300]}")
        elif k == "END":
            lines += ["", f"**end: {e['state']}** (rc {e['rc']}) {e.get('why', '')}"]
    rep = sorted({c.get("reported") for c in calls if c.get("reported")})
    lines += ["", f"model calls: {len(calls)} · reported model: {', '.join(rep) or '-'}"
              + (" · **differs from the request**" if any(c.get("model_mismatch") for c in calls) else "")
              + f" · tokens: {totals(calls)}"]
    return "\n".join(lines)
