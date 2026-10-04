"""CMD-GMG5 S4 (committed for CMD-GMG10 S2): do learned mood lists sort the reference photos into their groups, before
and after the calibrated scales? Run: python3 bench/gmg5/mood_halves.py   (reads bench/gmg5/refset_measured.jsonl)

- The 87 reference photos are split in two halves by the parity of their sha256's first byte.
- On one half, a mood list is learned per group: one or two of the nine moods, by greedy coordinate ascent, three passes.
- Each photo of the other half goes to the group whose list fits it best (mean mood value). Accuracy is the share
  assigned to their own group. Chance is 1/5.
- "before": the formulas as they were (sharpness/400, .5 +/- warmth, raw brightness and saturation).
- "after": the calibrated form of gmg/photo.py (0 at the 10th percentile, 1 at the 90th, sharpness on a log scale).
  The percentiles are taken from the training half only, so the test half stays unseen. (The shipped SCALE uses all 87.)

Reported in CMD-GMG5 rev 2: before .41/.58, after .50/.58 (test half 1 / test half 0).
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

ROWS = [json.loads(x) for x in (Path(__file__).resolve().parent / "refset_measured.jsonl").read_text().splitlines()]
GROUPS = sorted({r["group"] for r in ROWS})
MOODS = ["bright", "dark", "saturated", "muted", "warm", "cool", "sharp", "soft", "monochrome"]
CANDIDATES = [c for k in (1, 2) for c in itertools.combinations(MOODS, k)]


def half(r) -> int:
    return int(r["sha256"][:2], 16) % 2


def quantile(vals, p):
    v = sorted(vals)
    i = p * (len(v) - 1)
    lo = int(i)
    return v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * (i - lo)


def fit_before(m, moods):
    sh = min(m["sharpness"] / 400, 1)
    f = {"bright": m["brightness"], "dark": 1 - m["brightness"], "saturated": m["saturation"], "muted": 1 - m["saturation"],
         "warm": .5 + m["warmth"], "cool": .5 - m["warmth"], "sharp": sh, "soft": 1 - sh, "monochrome": 1.0 if m["mono"] else 0.0}
    return sum(f[x] for x in moods) / len(moods)


def fit_after(train):
    sc = {}
    for k, fn in (("brightness", lambda m: m["brightness"]), ("saturation", lambda m: m["saturation"]),
                  ("warmth", lambda m: m["warmth"]), ("sharp", lambda m: math.log(max(m["sharpness"], 1)))):
        vs = [fn(r["measured"]) for r in train]
        sc[k] = (quantile(vs, .1), quantile(vs, .9))

    def n(k, v):
        lo, hi = sc[k]
        return max(0.0, min(1.0, (v - lo) / (hi - lo)))

    def f(m, moods):
        b, s, w = n("brightness", m["brightness"]), n("saturation", m["saturation"]), n("warmth", m["warmth"])
        sh = n("sharp", math.log(max(m["sharpness"], 1)))
        d = {"bright": b, "dark": 1 - b, "saturated": s, "muted": 1 - s, "warm": w, "cool": 1 - w, "sharp": sh, "soft": 1 - sh,
             "monochrome": 1.0 if m["mono"] else 0.0}
        return sum(d[x] for x in moods) / len(moods)
    return f


def accuracy(rows, lists, fit) -> float:
    return sum(max(GROUPS, key=lambda g: fit(r["measured"], lists[g])) == r["group"] for r in rows) / len(rows)


def learn(rows, fit) -> dict:
    lists = {g: ("dark",) for g in GROUPS}
    for _ in range(3):
        for g in GROUPS:
            lists[g] = max(CANDIDATES, key=lambda c: accuracy(rows, {**lists, g: c}, fit))
    return lists


def run() -> dict:
    out = {}
    for name in ("before", "after"):
        for tr in (0, 1):
            train = [r for r in ROWS if half(r) == tr]
            test = [r for r in ROWS if half(r) != tr]
            fit = fit_before if name == "before" else fit_after(train)
            lists = learn(train, fit)
            out[(name, tr)] = (round(accuracy(train, lists, fit), 2), round(accuracy(test, lists, fit), 2), lists)
    return out


if __name__ == "__main__":
    res = run()
    for (name, tr), (a_tr, a_te, lists) in res.items():
        print(f"{name}: learn on half {tr} (train {a_tr:.2f}) -> test on half {1 - tr}: {a_te:.2f}   {lists}")
    print(f"\nbefore {res[('before', 0)][1]:.2f}/{res[('before', 1)][1]:.2f} -> after {res[('after', 0)][1]:.2f}/{res[('after', 1)][1]:.2f}")
