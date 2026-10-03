"""CMD-GMG5 S4/S6: measure the reference photos with the real tool (gmg.photo.measure), not the ImageMagick quick_measures.
Writes bench/gmg5/refset_measured.jsonl: one line per photo with its group (from gmg-net's query, not a measurement) and the
measured values. Design data only (S5). Run: GMG_UPSTREAM=... python3 bench/gmg5/measure_refset.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gmg import photo, upstream  # noqa: E402

REF = ROOT / "bench" / "gmg5" / "refset"
OUT = ROOT / "bench" / "gmg5" / "refset_measured.jsonl"


def main() -> int:
    upstream.load()
    rows = []
    for line in (REF / "manifest_photos.jsonl").read_text().splitlines():
        e = json.loads(line)
        m = photo.measure(REF / e["file"])
        m.pop("file")
        rows.append({"id": e["id"], "file": e["file"], "group": e["group"], "sha256": e["sha256"], "measured": m})
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{len(rows)} photos measured -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
