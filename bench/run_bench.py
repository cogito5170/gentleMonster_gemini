"""Run the pre-registered comparison (bench/PROTOCOL.md). Real Gemini calls for B and C; A is read from bench/opus.

    GMG_UPSTREAM=<pinned checkout> python3 bench/run_bench.py [--only b1,b2] [--out DIR]

Writes bench/results/<arm>_<id>/ (job.json, synopsis.md, layout_preview.png, ledger or drafts) and
bench/results/metrics.json. Every run is kept; nothing is re-run to pick a better one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from gmg import MODEL, run, upstream  # noqa: E402
from gmg.gemini import API, key  # noqa: E402
from gmg.ledger import Ledger, totals  # noqa: E402


# ------------------------------------------------------------------ metrics (PROTOCOL 2)
def completeness(spec, job) -> "tuple[int, list[str]]":
    """12 items; each is 1 only if that part is present and well formed."""
    if not isinstance(job, dict):
        return 0, ["no job"]
    hexok = lambda h: isinstance(h, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", h) is not None  # noqa: E731
    try:
        probs = spec.check(job)
    except Exception as e:                                  # noqa: BLE001 -- a check that crashes is not a pass
        probs = [f"spec.check raised {type(e).__name__}"]
    lay = [p for p in probs if any(w in p for w in ("door", "item", "envelope", "overlap", "circulation", "flows", "share the id"))]
    stp = [p for p in probs if p.startswith("stop ") or "walkthrough stops" in p or "stops hold" in p]
    items = {
        "brand": lambda: bool(str(job["brand"]).strip()),
        "title": lambda: bool(str(job["title"]).strip()),
        "line": lambda: bool(str(job["line"]).strip()),
        "synopsis 60-900": lambda: 60 <= len(job["synopsis"]) <= 900,
        "keywords 3": lambda: len(job["keywords"]) == 3,
        "why 3-4": lambda: 3 <= len(job["why"]) <= 4,
        "palette 5 hex": lambda: len(job["palette"]) == 5 and all(hexok(p.get("hex")) for p in job["palette"]),
        "accent hex": lambda: hexok(job["accent"]),
        "materials 4 presets": lambda: len(job["materials"]) == 4 and all(m.get("preset") in spec.MATERIALS for m in job["materials"]),
        "room": lambda: all(job["room"].get(k) in spec.MATERIALS for k in ("floor", "wall", "ceiling")) and job["room"].get("light") in spec.LIGHTS,
        "layout": lambda: "layout" in job and not lay and not any("missing" in p for p in probs),
        "stops": lambda: len(job["stops"]) == 3 and not stp,
    }
    got, miss = 0, []
    for k, f in items.items():
        try:
            g = bool(f())
        except Exception:                                   # noqa: BLE001
            g = False
        got += g
        if not g:
            miss.append(k)
    return got, miss


# ------------------------------------------------------------------ B: gentleMonster's own synopsis loop on flash-lite
class Plain:
    """The request gentle_monster.llm.ask sends (temperature 0.9, maxOutputTokens 8192, no schema), with usage kept.
    Same retry rule as upstream: 429/5xx and network retried up to 3 attempts; empty candidates also retried (upstream KeyError)."""
    def __init__(self, model=MODEL):
        self.model, self.calls = model, []

    def __call__(self, prompt: str) -> str:
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.9, "maxOutputTokens": 8192}}
        last = None
        for i in range(3):
            t0 = time.time()
            req = urllib.request.Request(f"{API}/models/{self.model}:generateContent", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "x-goog-api-key": key()})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    d = json.loads(r.read().decode())
                c = d["candidates"][0]
                self.calls.append({"ms": int((time.time() - t0) * 1000), "finish": c.get("finishReason"), "usage": d.get("usageMetadata", {}),
                                   "reported": d.get("modelVersion", "미보고")})
                return "".join(p.get("text", "") for p in c["content"]["parts"] if not p.get("thought"))
            except urllib.error.HTTPError as e:
                self.calls.append({"ms": int((time.time() - t0) * 1000), "outcome": f"http_{e.code}"})
                last = e
                if e.code not in (429, 500, 502, 503, 504):
                    break
            except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as e:
                self.calls.append({"ms": int((time.time() - t0) * 1000), "outcome": type(e).__name__})
                last = e
            if i < 2:
                time.sleep(2 * (i + 1))
        raise RuntimeError(f"Gemini call failed: {type(last).__name__}")


def draw(pipeline, name):
    with open(os.devnull, "w") as dn:
        import contextlib
        with contextlib.redirect_stdout(dn):
            return pipeline.layout(name, moodboard=False, use_llm=False, log=lambda m: None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=str(HERE / "results"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    spec, paths = upstream.load(str(out / "_work"))
    from gentle_monster import pipeline, synopsis as SY
    briefs = json.loads((HERE / "briefs.json").read_text())["briefs"]
    if a.only:
        briefs = [b for b in briefs if b["id"] in a.only.split(",")]
    rows = json.loads((out / "metrics.json").read_text()) if (out / "metrics.json").is_file() else []
    for b in briefs:
        # A -- pinned before any run
        job = json.loads((HERE / "opus" / f"{b['id']}.r1.json").read_text())
        pipeline.save_job(f"A_{b['id']}", job)
        draw(pipeline, f"A_{b['id']}")
        g, miss = completeness(spec, job)
        rows.append({"brief": b["id"], "arm": "A", "gate": not spec.check(job), "complete": g, "missing": miss, "reasks": 0,
                     "seconds": None, "calls": 0, "tokens": None, "reported": "-"})

        # B -- gentleMonster as is, model = flash-lite
        plain = Plain()
        t0 = time.time()
        try:
            r = SY.generate(b["brief"], brand=b["brand"], ask=plain, log=lambda m: None)
            err = None
        except Exception as e:                              # noqa: BLE001 -- e.g. spec.check raising on a mistyped draft (PREP F4)
            r, err = {"job": None, "rounds": None, "problems": [f"{type(e).__name__}: {e}"], "drafts": []}, f"{type(e).__name__}: {e}"
        secs = round(time.time() - t0, 1)
        d = paths.job_dir(f"B_{b['id']}")
        (d / "drafts.json").write_text(json.dumps({"rounds": r["rounds"], "problems": r["problems"], "drafts": r["drafts"], "error": err,
                                                   "calls": plain.calls}, ensure_ascii=False, indent=1))
        if r["job"]:
            pipeline.save_job(f"B_{b['id']}", r["job"])
        g, miss = completeness(spec, r["job"])
        rounds = r["rounds"] or len(r["drafts"])
        rows.append({"brief": b["id"], "arm": "B", "gate": bool(r["job"]), "complete": g, "missing": miss,
                     "reasks": max(rounds - 1, 0) + (0 if r["job"] else 1), "seconds": secs, "calls": len(plain.calls),
                     "tokens": totals(plain.calls), "reported": ",".join(sorted({c.get("reported", "-") for c in plain.calls})), "error": err})

        # C -- gmg
        t0 = time.time()
        res = run.make(f"C_{b['id']}", b["brief"], b["brand"], draw=True, log=lambda m: None)
        L = Ledger(Path(res["dir"]))
        ev = L.run()
        t_start = ev[0]["t"]
        t_job = next((e["t"] for e in ev if e["kind"] == "GATE"), ev[-1]["t"])
        cj = json.loads((Path(res["dir"]) / "job.json").read_text()) if (Path(res["dir"]) / "job.json").is_file() and res["state"] == "DONE" else None
        g, miss = completeness(spec, cj)
        calls = [e for e in ev if e["kind"] == "MODEL_CALL"]
        reask = sum(max(e.get("asks", 1) - 1, 0) for e in ev if e["kind"] == "DECISION") + (0 if res["state"] == "DONE" else 1)
        rows.append({"brief": b["id"], "arm": "C", "gate": res["state"] == "DONE", "complete": g, "missing": miss, "reasks": reask,
                     "seconds": round(t_job - t_start, 1), "calls": len(calls), "tokens": totals(calls),
                     "reported": ",".join(sorted({c.get("reported", "-") for c in calls})),
                     "fallbacks": [e.get("roles") or e.get("step") for e in ev if e["kind"] == "FALLBACK"], "state": res["state"],
                     "plan": (L.decision("plan") or {}).get("output", {}).get("plan")})
        for arm in "ABC":
            src = paths.job_dir(f"{arm}_{b['id']}")
            dst = out / f"{arm}_{b['id']}"
            if dst.exists():
                shutil.rmtree(dst)
            dst.mkdir(parents=True)
            for f in ("job.json", "synopsis.md", "layout_preview.png", "drafts.json", "gmg_ledger.jsonl", "layout.pdf"):
                if (src / f).is_file():
                    shutil.copy2(src / f, dst / f)
        (out / "metrics.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        print(f"[bench] {b['id']}: " + " · ".join(f"{r_['arm']} gate={r_['gate']} complete={r_['complete']}/12 reasks={r_['reasks']} calls={r_['calls']}"
                                             for r_ in rows if r_["brief"] == b["id"]), flush=True)
    return 0


def blind(out: Path) -> None:
    """X/Y = A/C by the first bit of sha256(brief id): reproducible, not chosen after seeing results."""
    bd = HERE / "blind"
    if bd.exists():
        shutil.rmtree(bd)
    key_ = {}
    for b in json.loads((HERE / "briefs.json").read_text())["briefs"]:
        bit = hashlib.sha256(b["id"].encode()).digest()[0] >> 7
        xy = {"X": "A", "Y": "C"} if bit == 0 else {"X": "C", "Y": "A"}
        key_[b["id"]] = xy
        for side, arm in xy.items():
            d = bd / b["id"] / side
            d.mkdir(parents=True)
            for f in ("synopsis.md", "layout_preview.png"):
                if (out / f"{arm}_{b['id']}" / f).is_file():
                    shutil.copy2(out / f"{arm}_{b['id']}" / f, d / f)
        (bd / b["id"] / "brief.txt").write_text(f"{b['brief']}\nbrand: {b['brand'] or '(none given)'}\n")
    (bd / "key.json").write_text(json.dumps(key_, indent=1))


if __name__ == "__main__":
    if sys.argv[1:2] == ["blind"]:
        blind(HERE / "results")
        sys.exit(0)
    sys.exit(main())
