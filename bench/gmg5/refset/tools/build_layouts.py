"""Write manifest_layouts.jsonl (CMD-GN1 S3): URL + derived structure only; the fetched scans stay in the work directory.

    python3 tools/build_layouts.py <workdir>

tools/layout_notes.json holds the by-eye reading of each kept page (type, grid, masthead, photo/word pattern, and the
public-domain basis); tools/layout.py adds the measured numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import layout  # noqa: E402

HERE = Path(__file__).resolve().parent.parent


def main(work: str):
    w = Path(work)
    rows = {r["id"]: r for r in json.loads((w / "layout_short_candidates.json").read_text())}
    got = json.loads((w / "layout_short_fetched.json").read_text())
    notes = json.loads((HERE / "tools" / "layout_notes.json").read_text())
    lines = []
    for i, n in notes.items():
        r, f = rows[i], got[i]
        lines.append({
            "kind": "layout", "id": f"ov:{i}", "type": n["type"], "group": r["group"], "query": r["query"], "title": r["title"],
            "creator": r["creator"], "source": r["source"], "landing_url": r["foreign_landing_url"], "image_url": r["url"],
            "licence": r["license"], "licence_version": r.get("license_version"), "licence_url": r["license_url"],
            "date": n.get("date"), "pd_basis": n.get("pd_basis"), "fetched_sha256": f["sha256"],
            "structure": {"seen": n["seen"], "seen_counts": {"pictures": n["pictures"], "columns": n["columns"]},
                          "measured": layout.measure(w / "raw" / f["file"])}})
    (HERE / "manifest_layouts.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
    # how far the coarse measure agrees with the by-eye counts (reported, not tuned against)
    ok_p = sum(x["structure"]["measured"]["pictures"] == x["structure"]["seen_counts"]["pictures"] for x in lines)
    ok_c = sum(x["structure"]["measured"]["columns"] == x["structure"]["seen_counts"]["columns"] for x in lines)
    print(len(lines), "layout references; measured = by-eye: pictures", ok_p, "/", len(lines), ", columns", ok_c, "/", len(lines))


if __name__ == "__main__":
    main(sys.argv[1])
