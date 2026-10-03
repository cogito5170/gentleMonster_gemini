"""Gemini over REST, for one narrow slot at a time.

Every call: fixed model (gemini-3.1-flash-lite, no fallback), JSON out under a responseSchema, and a ledger line
(MODEL_CALL) with the model the response *says* it is, finishReason and token counts. The key is read from
GEMINI_API_KEY (or GOOGLE_API_KEY) and never written anywhere.

What is retried and what is not (PREP F2/F3):
  429 / 5xx / network  -> retried, at most 3 attempts, Retry-After honoured, no sleep after the last
  blocked prompt, finishReason other than STOP (MAX_TOKENS, SAFETY, ...)  -> recorded and raised, never resent
  other 4xx            -> raised at once
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from gmg import MODEL, schema as S

API = os.environ.get("GMG_GEMINI_API", "https://generativelanguage.googleapis.com/v1beta")
RETRY = {429, 500, 502, 503, 504}


class ModelError(RuntimeError):
    def __init__(self, outcome: str, msg: str):
        super().__init__(f"{outcome}: {msg}")
        self.outcome = outcome


def key() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def http(url, body, headers, hint=None, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers or {})


class Gemini:
    def __init__(self, ledger=None, model: str = "", transport=None, sleep=time.sleep, attempts: int = 3):
        self.model = model or os.environ.get("GMG_MODEL") or MODEL
        if transport is None and os.environ.get("GMG_FAKE"):
            from gmg import fake
            transport = fake.Fake(os.environ.get("GMG_FAKE", "1"))
        self.transport = transport or http
        self.ledger, self.sleep, self.attempts = ledger, sleep, attempts

    def _log(self, **kw):
        if self.ledger:
            self.ledger.log("MODEL_CALL", asked=self.model, **kw)

    def ask(self, step: str, prompt: str, sch: dict, images=(), system: str = "", temperature: float = 0.7) -> dict:
        """-> {'value': parsed JSON or None, 'problems': [facts], 'reported': model name, 'usage': {...}}"""
        k = key()
        if not k and self.transport is http:
            raise ModelError("no_key", "GEMINI_API_KEY is not set")
        parts = [{"text": prompt}] + [{"inline_data": {"mime_type": m, "data": __import__("base64").b64encode(b).decode()}} for m, b in images]
        body = {"contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": 8192,
                                     "responseMimeType": "application/json", "responseSchema": S.to_gemini(sch)}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"{API}/models/{self.model}:generateContent"
        hdr = {"Content-Type": "application/json", "x-goog-api-key": k}
        last = None
        for a in range(1, self.attempts + 1):
            t0 = time.time()
            try:
                code, text, rh = self.transport(url, body, hdr, {"step": step, "schema": sch})
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                self._log(step=step, attempt=a, outcome="network", error=type(e).__name__, ms=int((time.time() - t0) * 1000))
                last = ModelError("network", type(e).__name__)
                if a < self.attempts:
                    self.sleep(2 ** (a - 1))
                continue
            ms = int((time.time() - t0) * 1000)
            if code != 200:
                msg = _err(text)
                self._log(step=step, attempt=a, outcome=f"http_{code}", error=msg[:300], ms=ms)
                last = ModelError(f"http_{code}", msg)
                if code in RETRY and a < self.attempts:
                    ra = rh.get("Retry-After") or rh.get("retry-after")
                    self.sleep(min(float(ra), 30) if ra and str(ra).replace(".", "", 1).isdigit() else 2 ** (a - 1))
                    continue
                raise last
            try:
                d = json.loads(text)
            except json.JSONDecodeError:
                self._log(step=step, attempt=a, outcome="bad_body", ms=ms)
                last = ModelError("bad_body", "the HTTP body was not JSON")
                if a < self.attempts:
                    self.sleep(2 ** (a - 1))
                continue
            usage, reported = d.get("usageMetadata") or {}, d.get("modelVersion") or "미보고"
            mismatch = reported != "미보고" and not reported.startswith(self.model)
            cands = d.get("candidates") or []
            block = (d.get("promptFeedback") or {}).get("blockReason")
            finish = cands[0].get("finishReason") if cands else None
            base = dict(step=step, attempt=a, reported=reported, model_mismatch=mismatch, finish=finish, usage=usage, ms=ms)
            if block or not cands:
                self._log(outcome="blocked", block=block or "no candidates", **base)
                raise ModelError("blocked", f"the prompt was blocked ({block or 'no candidates'})")
            if finish != "STOP":
                out = "truncated" if finish == "MAX_TOKENS" else "blocked"
                self._log(outcome=out, **base)
                raise ModelError(out, f"finishReason {finish}")
            txt = "".join(p.get("text", "") for p in (cands[0].get("content") or {}).get("parts", []) if not p.get("thought"))
            try:
                v = json.loads(txt)
                probs = S.check(v, sch)
            except json.JSONDecodeError as e:
                v, probs = None, [f"the reply was not a JSON object ({e.msg})"]
            self._log(outcome="ok" if not probs else "schema_violation", problems=probs[:20], reply=v if v is not None else txt[:2000], **base)
            return {"value": v, "problems": probs, "reported": reported, "usage": usage, "mismatch": mismatch}
        raise last


def _err(text: str) -> str:
    try:
        return json.loads(text)["error"]["message"]
    except Exception:                                       # noqa: BLE001
        return text[:300]
