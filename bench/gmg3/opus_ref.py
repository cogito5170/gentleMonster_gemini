"""Arm A: the original session's texts for questions 32-42 (gentleMonster@35073f7 docs/portfolio), measured by the same gates.
    GMG_UPSTREAM=<checkout> python3 bench/gmg3/opus_ref.py   -> bench/gmg3/opus_ref.json"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from gmg import portfolio as PF  # noqa: E402


def doc(name):
    return subprocess.run(["git", "-C", os.environ["GMG_UPSTREAM"], "show", f"35073f7:docs/portfolio/{name}"], capture_output=True, text=True).stdout


def section(text, start, end=None):
    a = text.index(start)
    b = text.index(end, a + len(start)) if end else len(text)
    return text[a:b]


def quotes(block):
    """Korean blockquote paragraphs (the page text), without markdown emphasis."""
    out, cur = [], []
    for ln in block.splitlines():
        if ln.startswith("> "):
            cur.append(ln[2:].replace("**", ""))
        elif cur:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def main():
    st, sl, pi = doc("01_style.md"), doc("storyline.md"), doc("02_picture.md")
    q13 = quotes(section(st, "## ④ Q1–Q3", "## 풀쿼트"))
    texts = {
        "32/33/35/36 Q1-Q3": q13,
        "34 storyline": [section(sl, "```", "## 섹션마다").strip("`\n ")],
        "37 opening (A)": quotes(section(st, "## ① 여는 글", "## ② 전환")),
        "38 STYLE flow": [section(sl, "## 01 STYLE 안의 흐름").strip()],
        "39 SECTOR A": [section(st, "## ③ SECTOR A", "## ④ Q1–Q3").strip()],
        "41 4 PICTURE opening": quotes(section(pi, "### 여는 글", "### Why is a picture")),
        "42 One To One table": [section(pi, "| 순위 |", "- 단어는").strip()],
    }
    out = {}
    for k, ts in texts.items():
        rows = []
        for t in ts:
            bad, meas = PF.gates(t, "direct", "ko", 0)
            rows.append({"text": t[:400], "measures": meas, "direct_gate_passed": not bad, "problems": bad})
        out[k] = rows
    (HERE / "opus_ref.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    n = sum(len(v) for v in out.values())
    p = sum(r["direct_gate_passed"] for v in out.values() for r in v)
    print(f"A texts: {n}, passing the direct gates: {p}")
    for k, v in out.items():
        print(k, [(r["measures"]["abstract_ratio"], r["direct_gate_passed"]) for r in v])


if __name__ == "__main__":
    main()
