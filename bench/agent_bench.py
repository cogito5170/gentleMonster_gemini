"""Rev-2 measurement: arm D (flash-lite walks the extension's tools via Gemini API function calling).

    GMG_UPSTREAM=<pinned checkout> python3 bench/agent_bench.py [--only b1,b2]
    python3 bench/agent_bench.py blind
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "results_rev2"
os.environ.setdefault("GMG_OUT", str(OUT / "_work"))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from gmg import loop, upstream  # noqa: E402
from gmg.ledger import totals  # noqa: E402
from run_bench import completeness  # noqa: E402

KEEP = ("job.json", "synopsis.md", "layout_preview.png", "gmg_ledger.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    spec, paths = upstream.load()
    OUT.mkdir(parents=True, exist_ok=True)
    mp = OUT / "metrics.json"
    rows = json.loads(mp.read_text()) if mp.is_file() else []
    for b in json.loads((HERE / "briefs.json").read_text())["briefs"]:
        if a.only and b["id"] not in a.only.split(","):
            continue
        n = 1 + sum(1 for r in rows if r["brief"] == b["id"])
        r = loop.run(b["brief"], b["brand"], log=lambda m: print(f"  {b['id']} {m}", flush=True))
        job = None
        if r["job"] and r["state"] == "DONE":
            job = json.loads((paths.job_dir(r["job"]) / "job.json").read_text())
        g, miss = completeness(spec, job)
        ok_turns = [t for t in r["turns"] if "usage" in t]
        row = {"brief": b["id"], "arm": "D", "run": n, "job": r["job"], "state": r["state"], "stop": r["stop"],
               "gate": r["state"] == "DONE", "complete": g, "missing": miss,
               "reasks": sum(1 for c in r["calls"] if c["ok"] is False) + (0 if r["state"] == "DONE" else 1),
               "offlist": sum(1 for c in r["calls"] if c["offlist"]), "tool_calls": len(r["calls"]),
               "turns": len(ok_turns), "model_calls": len(r["turns"]), "quota_waits": sum(1 for t in r["turns"] if t.get("http") == 429),
               "tokens": totals(ok_turns), "seconds": r["seconds"],
               "reported": sorted({t.get("reported") for t in ok_turns}),
               "claimed": r["claimed"], "honest": (r["claimed"] is None) or ((r["claimed"] == "DONE") == (r["state"] == "DONE")),
               "hook_would_deny": r["hook"].get("decision") == "deny",
               "fallback_notes": sum(len(c["notes"]) for c in r["calls"])}
        rows.append(row)
        d = OUT / f"D_{b['id']}"
        if d.exists():
            d.rename(OUT / f"D_{b['id']}.run{n - 1}")
        d.mkdir(parents=True)
        (d / "transcript.json").write_text(json.dumps({k: r[k] for k in ("calls", "turns", "final", "stop", "state", "job")}, ensure_ascii=False, indent=1))
        if r["job"]:
            for f in KEEP:
                if (paths.job_dir(r["job"]) / f).is_file():
                    shutil.copy2(paths.job_dir(r["job"]) / f, d / f)
        mp.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        print(f"[rev2] {b['id']} run {n}: {r['state']} stop={r['stop']} complete={g}/12 reasks={row['reasks']} offlist={row['offlist']} "
              f"tool_calls={row['tool_calls']} turns={row['turns']} tokens={row['tokens']['total']} {r['seconds']} s honest={row['honest']}", flush=True)
    return 0


def blind() -> None:
    bd = HERE / "blind_rev2"
    if bd.exists():
        shutil.rmtree(bd)
    key = {}
    for b in json.loads((HERE / "briefs.json").read_text())["briefs"]:
        x_is_a = hashlib.sha256(f"{b['id']}:rev2".encode()).digest()[0] % 2 == 0
        xy = {"X": "A", "Y": "D"} if x_is_a else {"X": "D", "Y": "A"}
        key[b["id"]] = dict(xy)
        for side, arm in xy.items():
            src = HERE / "results" / f"A_{b['id']}" if arm == "A" else OUT / f"D_{b['id']}"
            key[b["id"]][side + "_from"] = str(src.relative_to(HERE)) if (src / "synopsis.md").is_file() else "(no job)"
            dst = bd / b["id"] / side
            dst.mkdir(parents=True)
            for f in ("synopsis.md", "layout_preview.png"):
                if (src / f).is_file():
                    shutil.copy2(src / f, dst / f)
        (bd / b["id"] / "brief.txt").write_text(f"{b['brief']}\nbrand: {b['brand'] or '(none given)'}\n")
    (bd / "key.json").write_text(json.dumps(key, indent=1))


if __name__ == "__main__":
    if sys.argv[1:2] == ["blind"]:
        blind()
        sys.exit(0)
    sys.exit(main())
