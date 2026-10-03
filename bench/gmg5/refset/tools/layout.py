"""Derived layout structure from a page scan (CMD-GN1 S3): numbers only, the scan itself is not kept.

measure(path) -> margins (share of page per side), columns (text/picture columns from vertical gutters),
picture_share (picture area / content area), pictures (separate picture blocks >= 2 % of the page),
text_share, line_height (median text line, share of page height) and type_scale (tallest text band / median line).
Method: a 300 px grey raster from ImageMagick; paper = the brightest common level; a 1/40-page cell is "picture" when it
is mostly ink or mid-tone (halftone, engraving, photograph), "text" when it holds some ink that is neither. It is a
coarse reading, and the manifest pairs it with a by-eye note for each page.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

W = 300


def _raster(p: Path):
    out = subprocess.run(["convert", str(p) + "[0]", "-resize", f"{W}x", "-colorspace", "Gray", "-depth", "8", "gray:-"],
                         capture_output=True, check=True).stdout
    h = len(out) // W
    return [[out[y * W + x] / 255 for x in range(W)] for y in range(h)], h


def _runs(flags):
    """[(start, end)] of True runs."""
    out, s = [], None
    for i, f in enumerate(flags + [False]):
        if f and s is None:
            s = i
        elif not f and s is not None:
            out.append((s, i))
            s = None
    return out


def measure(path) -> dict:
    g, h = _raster(Path(path))
    hist = [0] * 32
    for row in g:
        for v in row:
            hist[min(int(v * 32), 31)] += 1
    paper = (max(range(16, 32), key=lambda i: hist[i]) + .5) / 32          # brightest common level
    ink = [[v < paper - .18 for v in row] for row in g]
    mid = [[paper - .55 < v < paper - .12 for v in row] for row in g]
    rows_ink = [sum(r) / W > .01 for r in ink]
    cols_ink = [sum(ink[y][x] for y in range(h)) / h > .01 for x in range(W)]
    # ignore a dark scan border: drop ink runs touching the edge that are thinner than 3 % of the side
    def bbox(flags, n):
        rr = [r for r in _runs(flags) if not ((r[0] == 0 or r[1] == n) and r[1] - r[0] < .03 * n)]
        return (rr[0][0], rr[-1][1]) if rr else (0, n)
    y0, y1 = bbox(rows_ink, h)
    x0, x1 = bbox(cols_ink, W)
    cs = max(W // 40, 4)
    pic, txt = set(), set()
    for cy in range(y0, y1, cs):
        for cx in range(x0, x1, cs):
            cells = [(y, x) for y in range(cy, min(cy + cs, y1)) for x in range(cx, min(cx + cs, x1))]
            if not cells:
                continue
            fi = sum(ink[y][x] for y, x in cells) / len(cells)
            fm = sum(mid[y][x] for y, x in cells) / len(cells)
            if fi > .45 or fm > .35:
                pic.add((cy, cx))
            elif fi > .03:
                txt.add((cy, cx))
    # separate picture blocks (4-neighbour) of at least 2 % of the page
    seen, blocks = set(), 0
    for c in pic:
        if c in seen:
            continue
        stack, n = [c], 0
        seen.add(c)
        while stack:
            cy, cx = stack.pop()
            n += 1
            for d in ((cs, 0), (-cs, 0), (0, cs), (0, -cs)):
                nb = (cy + d[0], cx + d[1])
                if nb in pic and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        blocks += n * cs * cs >= .02 * W * h
    # columns: gutters are vertical runs inside the content box with almost no ink, at least 1.5 % of the width
    colfill = [sum(ink[y][x] or mid[y][x] for y in range(y0, y1)) / max(y1 - y0, 1) for x in range(x0, x1)]
    gutters = [r for r in _runs([f < .004 for f in colfill]) if r[1] - r[0] >= .015 * W and r[0] > 0 and r[1] < len(colfill)]
    columns = len(gutters) + 1
    # text lines: horizontal ink runs over text cells
    tx = sorted({cx for _, cx in txt})
    line_h = []
    if tx:
        prof = [any(ink[y][x] for x in range(x0, x1)) and any((y - y0) // cs * cs + y0 == cy for cy, _ in txt) for y in range(y0, y1)]
        line_h = sorted(b - a for a, b in _runs(prof) if b - a >= 2)
    content = max(len(pic) + len(txt), 1)
    med = line_h[len(line_h) // 2] if line_h else 0
    return {"margins": {"top": round(y0 / h, 3), "bottom": round(1 - y1 / h, 3), "left": round(x0 / W, 3), "right": round(1 - x1 / W, 3)},
            "columns": columns, "picture_share": round(len(pic) / content, 3), "text_share": round(len(txt) / content, 3),
            "pictures": blocks, "line_height": round(med / h, 4) if med else None,
            "type_scale": round(line_h[-1] / med, 1) if med else None, "aspect": round(h / W, 3)}
