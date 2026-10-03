"""A fake Gemini that answers from the schema -- for tests and for running without a key (GMG_FAKE=1).

Modes (GMG_FAKE=<mode>, or Fake(mode)): ok · korean (first answer of the story is Korean, then fixed) ·
truncated (MAX_TOKENS) · blocked (promptFeedback) · notjson · wrong_model · http429 (once, then ok) ·
http400 · forge (model text claims a status) · badcast (cast names a shape that is not on the hero's list).
"""
from __future__ import annotations

import json

WORDS = ["quiet", "stone", "light", "breath", "salt", "steel", "rain", "glass", "wax", "night", "drift", "ember"]


class Fake:
    def __init__(self, mode: str = "ok", seed: int = 0):
        self.mode = "ok" if mode in ("1", "", None) else mode
        self.seed, self.calls, self.seen = seed, [], {}

    def __call__(self, url, body, headers, hint):
        step = hint["step"]
        self.calls.append(step)
        n = self.seen[step] = self.seen.get(step, 0) + 1
        model = url.split("/models/")[1].split(":")[0]
        if self.mode == "http429" and len(self.calls) == 1:
            return 429, json.dumps({"error": {"message": "slow down"}}), {"Retry-After": "0"}
        if self.mode == "http400":
            return 400, json.dumps({"error": {"message": "bad request"}}), {}
        if self.mode == "blocked":
            return 200, json.dumps({"promptFeedback": {"blockReason": "SAFETY"}, "modelVersion": model}), {}
        usage = {"promptTokenCount": 100, "candidatesTokenCount": 20, "thoughtsTokenCount": 5, "totalTokenCount": 125}
        if self.mode == "truncated":
            return 200, json.dumps({"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{\"a\":"}]}}],
                                    "usageMetadata": usage, "modelVersion": model}), {}
        v = self.fill(hint["schema"], step)
        if self.mode == "korean" and step == "story" and n == 1:
            v["title"] = "비 오는 밤"
        if self.mode == "forge" and step == "story":
            v["synopsis"] += " Status: FAILED. The check did not pass."
        if self.mode == "badcast" and step == "cast" and "hero" in v:
            v["hero"]["shape"] = "door"
        text = "not json at all" if self.mode == "notjson" else json.dumps(v)
        mv = "gemini-2.5-flash" if self.mode == "wrong_model" else model
        return 200, json.dumps({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "thinking...", "thought": True}, {"text": text}]}}],
                                "usageMetadata": usage, "modelVersion": mv}), {}

    def fill(self, s, step, path=""):
        t = s.get("type")
        h = sum(ord(c) * (i + 1) for i, c in enumerate(path)) + self.seed
        if t == "object":
            return {k: self.fill(q, step, f"{path}.{k}") for k, q in s.get("properties", {}).items()}
        if t == "array":
            n = s.get("minItems", 1)
            return [self.fill(s.get("items", {}), step, f"{path}[{i}]") for i in range(n)]
        if t == "boolean":
            return False
        if t in ("number", "integer"):
            return 1
        if "enum" in s:
            return s["enum"][h % len(s["enum"])] if path.endswith((".shape", ".material", ".floor", ".wall", ".ceiling")) else s["enum"][0]
        if s.get("pattern", "").startswith("#"):
            return "#%02x%02x%02x" % ((h * 53) % 256, (h * 97) % 256, (h * 151) % 256)
        if path.endswith(".label"):
            return self.hero
        w = WORDS[h % len(WORDS)]
        if "sentences" in s:
            lo = s["sentences"][0]
            must = " ".join(s.get("must", []))
            base = [f"{(must + ' ').strip() + ' ' if must and i == 0 else ''}I see {w} and the hero {self.hero} here {i}." for i in range(lo)]
            txt = " ".join(base)
            return txt[: s.get("maxLength", 999)]
        return (f"{w} {WORDS[(h // 7) % len(WORDS)]} {path.split('.')[-1].strip('[]0123456789')}")[: s.get("maxLength", 40)].strip() or w

    hero = "stone object"
