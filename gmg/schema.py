"""A small schema dialect: what the model must return, checked by code.

The same schema is sent as Gemini `responseSchema` (to_gemini keeps only the keys Gemini takes) and then
enforced here (check), because a response schema narrows the model but does not prove the answer.
Extra keys we enforce ourselves: maxLength, minLength, pattern, english (no Hangul), sentences [lo, hi], must (words).
"""
from __future__ import annotations

import re

HANGUL = re.compile("[가-힣]")
_GEMINI_KEYS = {"type", "enum", "properties", "required", "items", "minItems", "maxItems", "description", "nullable", "propertyOrdering"}


def _hint(s: dict) -> str:
    """Limits Gemini's schema has no key for, said in words in the description (code still enforces them)."""
    h = []
    if "maxLength" in s:
        h.append(f"at most {s['maxLength']} characters")
    if "sentences" in s:
        lo, hi = s["sentences"]
        h.append(f"{lo} sentence" if lo == hi == 1 else f"{lo}-{hi} sentences")
    if s.get("english"):
        h.append("English")
    return " ".join(filter(None, [s.get("description", ""), f"({', '.join(h)})" if h else ""]))


def to_gemini(s: dict) -> dict:
    out = {}
    if s.get("type") == "string" and _hint(s):
        out["description"] = _hint(s)
    for k, v in s.items():
        if k not in _GEMINI_KEYS:
            continue
        if k == "type":
            out[k] = v.upper()
        elif k == "properties":
            out[k] = {p: to_gemini(q) for p, q in v.items()}
            out["propertyOrdering"] = list(v)
        elif k == "items":
            out[k] = to_gemini(v)
        elif k != "description" or "description" not in out:
            out[k] = v
    return out


def sentences(t: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s])


def check(v, s: dict, where: str = "answer") -> "list[str]":
    """Facts about what is wrong with v. Empty = matches the schema."""
    t = s.get("type")
    bad = []
    if t == "object":
        if not isinstance(v, dict):
            return [f"{where} should be an object"]
        for k in s.get("required", list(s.get("properties", {}))):
            if k not in v:
                bad.append(f"{where}.{k} is missing")
        for k, q in s.get("properties", {}).items():
            if k in v:
                bad += check(v[k], q, f"{where}.{k}")
        return bad
    if t == "array":
        if not isinstance(v, list):
            return [f"{where} should be a list"]
        lo, hi = s.get("minItems"), s.get("maxItems")
        if lo is not None and len(v) < lo or hi is not None and len(v) > hi:
            want = f"exactly {lo}" if lo == hi else f"{lo}-{hi}"
            bad.append(f"{where} has {len(v)} items; give {want}")
        for i, x in enumerate(v):
            bad += check(x, s.get("items", {}), f"{where}[{i}]")
        return bad
    if t == "string":
        if not isinstance(v, str):
            return [f"{where} should be text"]
        if "enum" in s and v not in s["enum"]:
            return [f"{where} is {v!r}; it must be one of the listed options"]
        if len(v.strip()) < s.get("minLength", 1 if "enum" not in s else 0):
            bad.append(f"{where} is empty")
        if "maxLength" in s and len(v) > s["maxLength"]:
            bad.append(f"{where} is {len(v)} characters; keep it under {s['maxLength']}")
        if "pattern" in s and not re.fullmatch(s["pattern"], v):
            bad.append(f"{where} {v!r} is not in the form {s['pattern']}")
        if s.get("english") and HANGUL.search(v):
            bad.append(f"{where} contains Korean; write it in English")
        if "sentences" in s:
            n, (lo, hi) = sentences(v), s["sentences"]
            if not lo <= n <= hi:
                bad.append(f"{where} has {n} sentences; write {lo}-{hi}")
        for w in s.get("must", []):
            if not re.search(r"\b%s\b" % re.escape(w), v, re.I):
                bad.append(f"{where} does not use the word {w!r}")
        return bad
    if t in ("number", "integer"):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or (t == "integer" and not float(v).is_integer()):
            return [f"{where} should be a {t}"]
        if "enum" in s and v not in s["enum"]:
            return [f"{where} is {v}; it must be one of {s['enum']}"]
        return []
    if t == "boolean":
        return [] if isinstance(v, bool) else [f"{where} should be true or false"]
    return []
