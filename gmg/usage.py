"""Real-use log and its export (CMD-GMG6: the preview's use becomes the next evaluation data).

Everything stays on the user's machine in <GMG_OUT>/usage.jsonl:
- the BeforeAgent hook logs each user turn, with the session id the CLI gives;
- the MCP server logs each tool call: the tool, its args, ok, problems, redirected and next;
- the AfterAgent hook logs the served model and the verdict gate.

`gmg export` writes one JSONL per session into a folder the user reviews before sharing. In the export:
- image paths become sha256 plus measured values; no image bytes;
- other file paths become `[path]`, or `[file sha256:...]` when the file exists;
- key-like strings become `***`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

SCHEMA = "gmg-usage/1"
KEYS = re.compile(r"AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}"
                  r"|(?i:(?:api[_-]?key|token|secret|password)\s*[=:]\s*)\S{8,}")
BLOB = re.compile(r"[A-Za-z0-9+/=]{200,}")
PATHS = re.compile(r"(?<![\w/.:])(?:~?/[^\s\"'<>\]\)]*/[^\s\"'<>\]\),]*|[A-Za-z]:\\[^\s\"'<>]+)|(?<=@)[^\s\"'<>\]\)]+\.\w{2,5}\b")
IMAGES = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic")
MEASURES = ("brightness", "contrast", "saturation", "warmth", "dark_share", "centre_focus", "mono", "subject_share", "layout_like", "colors")


def _out() -> Path:
    return Path(os.environ.get("GMG_OUT") or (Path.home() / "gentleMonster_gemini_out"))


def log(kind: str, **fields) -> None:
    """Append one record; a logging failure never breaks a turn or a tool call."""
    try:
        if "session" not in fields:
            from gmg import turn
            fields["session"] = (turn.current() or {}).get("session") or "unknown"
        p = _out() / "usage.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": round(time.time(), 3), "kind": kind, **fields}, ensure_ascii=False, default=str) + "\n")
    except Exception:                                       # noqa: BLE001
        pass


# ------------------------------------------------------------------ export
def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Cleaner:
    """Replaces paths, keys and blobs in any JSON value; collects the images it met (sha256 + measured values)."""

    def __init__(self, base: "Path | None" = None):
        self.images: "dict[str, dict]" = {}
        self.base = base

    def _path(self, m: "re.Match") -> str:
        raw = m.group(0)
        p = Path(os.path.expanduser(raw))
        if not p.is_absolute() and self.base:
            p = self.base / p
        try:
            if p.is_file():
                sha = _sha(p)
                if p.suffix.lower() in IMAGES:
                    if sha not in self.images:
                        self.images[sha] = {"sha256": sha, "bytes": p.stat().st_size, "measured": _measure(p)}
                    return f"[image sha256:{sha[:16]}]"
                return f"[file sha256:{sha[:16]}]"
        except OSError:
            pass
        return "[path]"

    def text(self, s: str) -> str:
        s = KEYS.sub("***", s)
        s = BLOB.sub("[bytes removed]", s)
        s = PATHS.sub(self._path, s)
        home = str(Path.home())
        return s.replace(home, "[home]") if len(home) > 1 else s

    def __call__(self, v):
        if isinstance(v, str):
            return self.text(v)
        if isinstance(v, list):
            return [self(x) for x in v]
        if isinstance(v, dict):
            return {self.text(str(k)): self(x) for k, x in v.items()}
        return v


def _measure(p: Path) -> "dict | None":
    try:
        from gmg import photo
        m = photo.measure(p)
        return {k: m[k] for k in MEASURES if k in m}
    except Exception as e:                                  # noqa: BLE001
        return {"error": type(e).__name__}


def read(path: "Path | None" = None) -> "list[dict]":
    p = path or (_out() / "usage.jsonl")
    if not p.is_file():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def sessions(recs: "list[dict]") -> "dict[str, list[dict]]":
    """Records grouped by session, then into turns: each turn opens with its user record and holds what follows."""
    by: "dict[str, list[dict]]" = {}
    for r in sorted(recs, key=lambda r: r.get("t", 0)):
        s = str(r.get("session") or "unknown")
        if r["kind"] == "turn" or not by.get(s):
            by.setdefault(s, []).append({"n": len(by.get(s, [])) + 1, "t": r.get("t"), "text": None, "calls": [], "served": [], "gates": [],
                                         "answer": None})
        cur = by[s][-1]
        if r["kind"] == "turn":
            cur["text"] = r.get("prompt")
        elif r["kind"] == "call":
            cur["calls"].append({k: r.get(k) for k in ("tool", "args", "ok", "redirected", "problems", "next")})
        elif r["kind"] == "served":
            cur["served"].append(r.get("model"))
        elif r["kind"] == "gate":
            cur["gates"].append(r.get("decision"))
            if r.get("answer") is not None:
                cur["answer"] = r.get("answer")
    return by


def export(dest: "Path | None" = None, session: str = "", src: "Path | None" = None) -> "list[Path]":
    """One JSONL per session in dest: a header line, then one line per user turn. Returns the files written."""
    from gmg import MODEL, VERSION
    dest = Path(dest or (_out() / "export"))
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for s, turns in sessions(read(src)).items():
        if session and s != session:
            continue
        clean = Cleaner()
        lines = []
        for t in turns:
            calls = clean(t["calls"])
            lines.append({"n": t["n"], "t": t["t"], "text": clean(t["text"]) if t["text"] is not None else None,
                          "path": [c["tool"] for c in calls], "calls": calls,
                          "reasks": sum(1 for c in calls if c.get("ok") is False and not c.get("redirected")),
                          "redirects": sum(1 for c in calls if c.get("redirected")),
                          "failures": [p for c in calls if c.get("ok") is False for p in (c.get("problems") or [])][:20],
                          "served": t["served"], "gates": t["gates"], "answer": clean(t["answer"]) if t["answer"] else None})
        head = {"schema": SCHEMA, "session": hashlib.sha256(s.encode()).hexdigest()[:16], "version": VERSION, "asked_model": MODEL,
                "exported": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "turns": len(lines),
                "images": list(clean.images.values())}
        f = dest / f"{head['session']}.jsonl"
        f.write_text("\n".join(json.dumps(x, ensure_ascii=False, default=str) for x in [head] + lines) + "\n", encoding="utf-8")
        written.append(f)
    return written
