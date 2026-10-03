"""Store the chosen photographs and write manifest.jsonl (CMD-GN1 S2).

    python3 tools/build_photos.py <workdir>

Reads <workdir>/photo_candidates.json, photo_fetched.json and tools/photo_selection.json (chosen by eye from contact
sheets: on-topic, a photograph, no selfies, no close-ups of children, at most 3 per creator per group). Each stored file
is the fetched rendition shrunk to 800 px on the long edge (ImageMagick; metadata kept). Pillow is not installable here
(pypi is outside this environment's network list), so the quick measures below come from ImageMagick + plain Python;
GMG's pf_photos measures (gmg.photo.measure) are for S4 and are not computed here.
"""
from __future__ import annotations

import colorsys
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LICENCE_NAMES = {"cc0": "CC0 1.0", "pdm": "Public Domain Mark 1.0", "by": "CC BY", "by-sa": "CC BY-SA"}


def quick_measures(p: Path) -> dict:
    raw = subprocess.run(["convert", str(p) + "[0]", "-resize", "160x160", "-colorspace", "sRGB", "-depth", "8", "rgb:-"],
                         capture_output=True, check=True).stdout
    px = [tuple(raw[i:i + 3]) for i in range(0, len(raw) - 2, 3)]
    luma = [(.2126 * r + .7152 * g + .0722 * b) / 255 for r, g, b in px]
    sat = [colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[1] for r, g, b in px]
    n = len(px)
    mean = sum(luma) / n
    s_sorted = sorted(sat)
    return {"brightness": round(mean, 3), "dark_share": round(sum(v < .25 for v in luma) / n, 3),
            "contrast": round((sum((v - mean) ** 2 for v in luma) / n) ** .5, 3), "saturation": round(sum(sat) / n, 3),
            "warmth": round(sum(r - b for r, _, b in px) / n / 255, 3), "mono": s_sorted[int(.95 * (n - 1))] < .12}


def main(work: str):
    w = Path(work)
    rows = {}
    for r in json.loads((w / "photo_candidates.json").read_text()):
        rows.setdefault(r["id"], r)
    got = json.loads((w / "photo_fetched.json").read_text())
    sel = json.loads((HERE / "tools" / "photo_selection.json").read_text())
    out = HERE / "photos"
    out.mkdir(exist_ok=True)
    lines = []
    for group, ids in sel.items():
        for i in ids:
            r, f = rows[i], got[i]
            dst = out / f"{group}__{i[:8]}.jpg"
            subprocess.run(["convert", str(w / "raw" / f["file"]) + "[0]", "-resize", "800x800>", "-quality", "82", str(dst)], check=True)
            b = dst.read_bytes()
            wh = subprocess.run(["identify", "-format", "%w %h", str(dst)], capture_output=True, text=True, check=True).stdout.split()
            lines.append({
                "kind": "photo", "id": f"ov:{i}", "group": group, "query": r["query"], "title": r["title"],
                "creator": r["creator"], "creator_url": r.get("creator_url"), "source": r["source"],
                "landing_url": r["foreign_landing_url"], "image_url": r["url"], "fetched_url": f["fetched_url"],
                "licence": r["license"], "licence_version": r.get("license_version"), "licence_url": r["license_url"],
                "licence_name": f"{LICENCE_NAMES[r['license']]} {r.get('license_version') or ''}".strip(),
                "attribution": r.get("attribution"), "redistributable": True,
                "file": f"photos/{dst.name}", "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b),
                "width": int(wh[0]), "height": int(wh[1]), "fetched_sha256": f["sha256"], "fetched_bytes": f["bytes"],
                "quick_measures": quick_measures(dst)})
    (HERE / "manifest_photos.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
    print(len(lines), "photos;", sum(x["bytes"] for x in lines) // 1024, "KiB")


if __name__ == "__main__":
    main(sys.argv[1])
