"""The job ledger: <job dir>/gmg_ledger.jsonl, one event per line, append only.

Status is read from here and nowhere else. A file on disk that the ledger did not record (or whose bytes no
longer match the recorded sha256) is not done. Model text is data inside events; nothing in it is ever read
back as a status.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

NAME = "gmg_ledger.jsonl"


def sha256(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Ledger:
    def __init__(self, job_dir):
        self.dir = Path(job_dir)
        self.path = self.dir / NAME

    def log(self, kind: str, **data) -> dict:
        self.dir.mkdir(parents=True, exist_ok=True)
        ev = {"t": round(time.time(), 3), "kind": kind, **data}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev

    def artifact(self, p, what: str) -> dict:
        p = Path(p)
        return self.log("ARTIFACT", what=what, path=str(p.resolve().relative_to(self.dir.resolve())) if self.dir.resolve() in p.resolve().parents else str(p),
                        sha256=sha256(p), bytes=p.stat().st_size)

    def events(self) -> "list[dict]":
        if not self.path.is_file():
            return []
        out = []
        for ln in self.path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                out.append({"kind": "UNREADABLE"})
        return out

    def run(self) -> "list[dict]":
        """Events of the latest run (after the last START)."""
        ev = self.events()
        starts = [i for i, e in enumerate(ev) if e.get("kind") == "START"]
        return ev[starts[-1]:] if starts else ev

    def decision(self, step: str) -> "dict | None":
        """The accepted output of a step in the latest run."""
        for e in reversed(self.run()):
            if e.get("kind") == "DECISION" and e.get("step") == step:
                return e
        return None

    def status(self) -> dict:
        run = self.run()
        end = next((e for e in reversed(run) if e.get("kind") == "END"), None)
        arts = {}
        for e in run:
            if e.get("kind") == "ARTIFACT":
                p = Path(e["path"]) if Path(e["path"]).is_absolute() else self.dir / e["path"]
                arts[e["what"]] = "done" if p.is_file() and sha256(p) == e["sha256"] else "changed since recorded"
        calls = [e for e in run if e.get("kind") == "MODEL_CALL"]
        return {"state": end["state"] if end else ("(no end record)" if run else "(no ledger)"),
                "artifacts": arts,
                "steps": [e["step"] for e in run if e.get("kind") == "DECISION"],
                "model_calls": len(calls),
                "tokens": totals(calls)}


def totals(calls) -> dict:
    t = {"prompt": 0, "output": 0, "thoughts": 0, "total": 0}
    for c in calls:
        u = c.get("usage") or {}
        t["prompt"] += u.get("promptTokenCount", 0)
        t["output"] += u.get("candidatesTokenCount", 0)
        t["thoughts"] += u.get("thoughtsTokenCount", 0)
        t["total"] += u.get("totalTokenCount", 0)
    return t
