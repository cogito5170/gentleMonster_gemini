"""Download candidate images at a moderate size (CMD-GN1 S2/S3/S4) into <workdir>/raw/, one request per image.

    python3 tools/fetch.py <workdir> photo|layout_short [thumb_px]

Flickr: the 800 px rendition (_c) of the URL Openverse gives. Wikimedia: a 960 px thumbnail from upload.wikimedia.org,
or the original when it is no wider than that (layouts use 500 px: the structure reading needs 300). Never the full-size
original of a large file. Skips SVG/TIFF/GIF. Flickr first; three refusals in a row from a host skip that host's rest.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import net  # noqa: E402

THUMB = 960


def rendition(r: dict, thumb: int = THUMB) -> "str | None":
    url = r["url"]
    host = urllib.parse.urlsplit(url).hostname
    ext = url.rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png"):
        return None
    if host == "live.staticflickr.com":
        return re.sub(r"_[a-z]\.(jpe?g)$", r"_c.\1", url) if re.search(r"_[a-z]\.jpe?g$", url) else url
    if host == "upload.wikimedia.org":
        m = re.match(r"https://upload\.wikimedia\.org/wikipedia/commons/(\w/\w\w)/(.+)$", url)
        if not m or (r.get("width") or 0) <= thumb:
            return url
        return f"https://upload.wikimedia.org/wikipedia/commons/thumb/{m[1]}/{m[2]}/{thumb}px-{m[2]}"
    return None


def main(work: str, kind: str, thumb: str = str(THUMB)):
    w = Path(work)
    raw = w / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rows, seen = json.loads((w / f"{kind}_candidates.json").read_text()), set()
    rows.sort(key=lambda r: r["source"] != "flickr")            # stable: Flickr first, then Wikimedia
    refused: dict = {}
    got = {}
    gp = w / f"{kind}_fetched.json"
    if gp.exists():
        got = json.loads(gp.read_text())
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        if r["id"] in got:
            continue
        u = rendition(r, int(thumb))
        if not u:
            got[r["id"]] = {"skip": "format"}
            continue
        host = urllib.parse.urlsplit(u).hostname
        if refused.get(host, 0) >= 3:                               # the host keeps refusing: leave it alone
            continue
        try:
            b = net.get(u, tries=2)      # a short Retry-After is honoured once
        except net.Refused as e:
            refused[host] = refused.get(host, 0) + ("HTTP 429" in str(e))
            if "HTTP 429" not in str(e):
                got[r["id"]] = {"skip": str(e)[:200]}
            print("refused:", str(e)[:160], flush=True)
            continue
        refused[host] = 0
        p = raw / f"{r['id']}.{'png' if u.lower().endswith('.png') else 'jpg'}"
        p.write_bytes(b)
        got[r["id"]] = {"fetched_url": u, "file": p.name, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        gp.write_text(json.dumps(got, indent=1))
    gp.write_text(json.dumps(got, indent=1))
    print(kind, sum("file" in v for v in got.values()), "fetched,", sum("skip" in v for v in got.values()), "skipped,",
          "hosts given up:", [h for h, n in refused.items() if n >= 3])


if __name__ == "__main__":
    main(*sys.argv[1:4])
