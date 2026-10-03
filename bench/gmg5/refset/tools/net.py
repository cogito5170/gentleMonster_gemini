"""Polite HTTP for the GMG5 reference set (CMD-GN1 S4).

One User-Agent that says who we are, at most one request per second per host (Openverse: one per 3.5 s, its anonymous
burst limit is 20/min; upload.wikimedia.org: one per 15 s, it answered 429 at 1/s and 1/5 s), Retry-After honoured in full for the
whole host (up to 15 min, longer = give up), exponential back-off on 429/503, and no redirect to a host outside ALLOWED
(a refused host is reported, never routed around). Every attempt is appended to request_log.jsonl.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "gmg-net-refset/0.1 (+https://github.com/cogito5170/gentlemonster_gemini; GMG5 design reference set; polite, 1 req/s)"
ALLOWED = {"api.openverse.org", "live.staticflickr.com", "upload.wikimedia.org", "commons.wikimedia.org", "archive.org"}
INTERVAL = {"api.openverse.org": 3.5, "upload.wikimedia.org": 15.0}   # Wikimedia answered 429 at 1/s and at 1/5 s
LOG = Path(__file__).resolve().parent.parent / "request_log.jsonl"
_last: dict = {}
_cool: dict = {}      # host -> monotonic time before which we send nothing (Retry-After)
MAX_WAIT = 900


class Refused(Exception):
    """A host outside ALLOWED, or a status we do not retry."""


class _NoForeignRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = urllib.parse.urlsplit(newurl).hostname
        if host not in ALLOWED:
            raise Refused(f"redirect to {host} (outside the allowed list) from {req.full_url}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_NoForeignRedirect)


def _log(**rec):
    with LOG.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def get(url: str, tries: int = 4, timeout: int = 60) -> bytes:
    u = urllib.parse.urlsplit(url)
    if u.hostname not in ALLOWED:
        raise Refused(f"{u.hostname} is outside the allowed list")
    wait = 5.0
    for n in range(tries):
        gap = max(INTERVAL.get(u.hostname, 1.0) - (time.monotonic() - _last.get(u.hostname, -1e9)),
                  _cool.get(u.hostname, 0) - time.monotonic())
        if gap > 0:
            time.sleep(gap)
        _last[u.hostname] = time.monotonic()
        t0 = time.time()
        try:
            with _opener.open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
                body = r.read()
            _log(ts=round(t0, 1), host=u.hostname, path=(u.path + ("?" + u.query if u.query else ""))[:200], status=200, bytes=len(body), attempt=n + 1)
            return body
        except urllib.error.HTTPError as e:
            ra = e.headers.get("Retry-After")
            _log(ts=round(t0, 1), host=u.hostname, path=(u.path + ("?" + u.query if u.query else ""))[:200], status=e.code, bytes=0, attempt=n + 1,
                 retry_after=ra)
            if e.code not in (429, 503):
                raise Refused(f"HTTP {e.code} for {url}") from e
            delay = float(ra) if ra and ra.isdigit() else wait
            _cool[u.hostname] = time.monotonic() + delay          # the whole host waits, not just this URL
            if n == tries - 1 or delay > MAX_WAIT:
                raise Refused(f"HTTP {e.code} for {url} (Retry-After {ra})") from e
            time.sleep(delay)
            wait *= 2
        except Refused as e:
            _log(ts=round(t0, 1), host=u.hostname, path=u.path[:200], status="refused_redirect", bytes=0, attempt=n + 1, note=str(e)[:200])
            raise
    raise Refused(f"gave up on {url}")


def get_json(url: str):
    return json.loads(get(url))
