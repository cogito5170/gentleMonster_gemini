"""Licence check for the GMG5 reference set (CMD-GN1 S2, D1). Exit 1 on any problem.

    python3 tools/licence_check.py            # check bench/gmg5/refset
    python3 tools/licence_check.py --selftest # break a copy five ways; every break must fail the check

Rules: every file under photos/ is listed in manifest_photos.jsonl with a reuse licence (CC0, Public Domain Mark,
CC BY, CC BY-SA), a licence URL, a landing URL and a matching sha256; CC BY and BY-SA also need the creator and an
attribution line. Layout references store no page files: URL + derived structure only, with a licence or
public-domain basis recorded.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REUSE = {"cc0", "pdm", "by", "by-sa"}
NEEDS_CREDIT = {"by", "by-sa"}


def _jsonl(p: Path) -> list:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def check(root: Path) -> list:
    bad = []
    photos = _jsonl(root / "manifest_photos.jsonl")
    listed = {}
    for e in photos:
        tag = e.get("id", "?")
        if e.get("licence") not in REUSE:
            bad.append(f"{tag}: licence {e.get('licence')!r} is not a reuse licence")
        for k in ("licence_url", "landing_url", "file", "sha256"):
            if not e.get(k):
                bad.append(f"{tag}: missing {k}")
        if e.get("licence") in NEEDS_CREDIT and not (e.get("creator") and e.get("attribution")):
            bad.append(f"{tag}: {e.get('licence')} needs creator and attribution")
        if not e.get("redistributable"):
            bad.append(f"{tag}: stored file without redistributable=true")
        if e.get("file"):
            listed[e["file"]] = e
            f = root / e["file"]
            if not f.is_file():
                bad.append(f"{tag}: file {e['file']} is missing")
            elif hashlib.sha256(f.read_bytes()).hexdigest() != e.get("sha256"):
                bad.append(f"{tag}: sha256 of {e['file']} does not match")
    for f in sorted((root / "photos").glob("*")) if (root / "photos").is_dir() else []:
        if f"photos/{f.name}" not in listed:
            bad.append(f"photos/{f.name}: stored file not in the manifest (no licence on record)")
    for e in _jsonl(root / "manifest_layouts.jsonl"):
        tag = e.get("id", "?")
        if e.get("file"):
            bad.append(f"{tag}: layout references store no page file")
        if not e.get("landing_url") or not e.get("structure"):
            bad.append(f"{tag}: layout reference needs landing_url and structure")
        if e.get("licence") not in REUSE:
            bad.append(f"{tag}: licence {e.get('licence')!r} is not open")
    return bad


def selftest() -> int:
    breaks = {
        "unlisted file": lambda r: (r / "photos" / "stray.jpg").write_bytes(b"\xff\xd8\xff stray"),
        "all-rights-reserved licence": lambda r: _edit(r, lambda e: e.update(licence="arr")),
        "sha mismatch": lambda r: _edit(r, lambda e: e.update(sha256="0" * 64)),
        "BY without creator": lambda r: _edit(r, lambda e: e.update(licence="by", creator="")),
        "layout page stored": lambda r: _edit(r, lambda e: e.update(file="pages/x.jpg"), "manifest_layouts.jsonl"),
    }
    fails = 0
    for name, brk in breaks.items():
        with tempfile.TemporaryDirectory() as t:
            r = Path(t) / "refset"
            shutil.copytree(HERE, r, ignore=shutil.ignore_patterns("tools", "*.md", "request_log.jsonl"))
            assert not check(r), "the clean copy must pass"
            brk(r)
            caught = bool(check(r))
            fails += not caught
            print(f"{'caught' if caught else 'MISSED'}: {name}")
    return 1 if fails else 0


def _edit(r: Path, fn, name: str = "manifest_photos.jsonl"):
    rows = _jsonl(r / name)
    fn(rows[0])
    (r / name).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    bad = check(HERE)
    n_p, n_l = len(_jsonl(HERE / "manifest_photos.jsonl")), len(_jsonl(HERE / "manifest_layouts.jsonl"))
    for b in bad:
        print("FAIL", b)
    print(f"{'FAILED' if bad else 'ok'}: {n_p} photos, {n_l} layout references, {len(bad)} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
