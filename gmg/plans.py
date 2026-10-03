"""Plans: the geometry the model does not have to invent (PREP F7).

Each plan is one of the four bundled, already-checked jobs of the pinned gentleMonster (read from its
examples/, not copied). The model picks a plan and casts its roles (shape, material, label from listed options);
code scales the plan to the brief's stated size, writes the layout facts, and places the walkthrough stops.

A role keeps the obstacle class of its items: a solid slot only takes solid shapes, a walk-through slot only
walk-through shapes, so a cast cannot move an object into the route. spec.check still judges the result.
"""
from __future__ import annotations

import copy
import math

SOLID_FEATURE = ["bust", "creature", "rock", "basin", "candle_cluster", "cone_tree", "joint_column", "display", "box"]
SOLID_SMALL = ["cone_tree", "joint_column", "rock", "candle_cluster", "display", "box"]
STATION = ["display", "rock", "candle_cluster", "box"]
OVERHEAD = ["light_ceiling", "shards", "floor_patch", "zone"]
FLOOR = ["floor_patch", "zone"]
WALL = ["mirror_wall", "box"]
SHELF = ["shelf_wall", "box", "mirror_wall"]


def R(ids, shapes, desc, hero=False):
    return {"ids": ids, "shapes": shapes, "desc": desc, "hero": hero}


PLANS = {
    "orbit": {
        "example": "gm",
        "desc": "Threshold, then a central void. You pass between two objects and a screen just inside the door, then circle "
                "one hero object standing alone in a large empty void ringed by six small objects. Product stations sit at "
                "the four outer corners, outside the loop. The pay desk closes the loop at the back.",
        "roles": {
            "threshold": R(["joint_l", "joint_r"], SOLID_SMALL, "two tall objects you walk between 1-3 m inside the door"),
            "screen": R(["wire_l", "wire_r"], ["cable_curtain"], "a hanging screen with a gap you slip through"),
            "void": R(["void"], ["zone"], "the empty area around the hero (a named area, nothing built)"),
            "hero": R(["head"], SOLID_FEATURE, "the one object at the centre of the walk", hero=True),
            "ring": R(["tree%d" % i for i in range(6)], SOLID_SMALL, "six small objects ringing the void"),
            "stations": R(["st%d" % i for i in range(4)], STATION, "four product stations at the outer corners"),
            "atmosphere": R(["shards"], OVERHEAD, "something over or under the void that you walk through"),
            "pay": R(["pay"], ["box"], "the pay desk at the back"),
            "mirror": R(["mirror"], ["box"], "a fitting mirror"),
        },
        "stops": [("threshold", "standing just inside the door, between the threshold objects"),
                  ("hero", "at the edge of the void, facing the hero"),
                  ("stations", "turned away from the hero, at a product station")],
    },
    "field": {
        "example": "tb",
        "desc": "One open low field. A floor strip leads from the door to a single large hero object; four sculptural "
                "stations hold the product in a loose ring around it, and the route wanders between them to the pay at "
                "the back right. Nothing but the hero is tall.",
        "roles": {
            "field": R(["field"], ["zone"], "the open field (a named area, nothing built)"),
            "strip": R(["floor"], FLOOR, "the floor strip from the door to the hero"),
            "hero": R(["horse"], SOLID_FEATURE, "the one large object just inside", hero=True),
            "stations": R(["candle%d" % i for i in range(4)], STATION, "four product stations in a ring around the hero"),
            "pay": R(["pay"], ["box"], "the wrap and pay counter"),
        },
        "stops": [("strip", "just inside the door, looking down at the floor strip"),
                  ("hero", "in front of the hero"),
                  ("stations", "low, close to a product station")],
    },
    "chamber": {
        "example": "ac",
        "desc": "A room inside the room. A walled chamber with two side openings stands in the middle; three low "
                "monoliths inside it carry the product; two blocks break through the chamber walls. The route enters "
                "the chamber, circles the monoliths and leaves. There is no single hero: the chamber is the event.",
        "roles": {
            "chamber": R(["chamber"], OVERHEAD, "the chamber's ceiling or floor finish"),
            "walls": R(["w_front", "w_back", "w_left", "w_left2", "w_right", "w_right2"], WALL, "the chamber walls"),
            "hero": R(["mono_a", "mono_b", "mono_c"], STATION, "three low monoliths in the chamber that carry the product", hero=True),
            "piercing": R(["pierce_l", "pierce_r"], ["rock", "box"], "two blocks breaking through the chamber walls"),
            "pay": R(["pay"], ["box"], "the pay desk"),
            "fit": R(["fit"], ["box"], "the fitting room"),
        },
        "stops": [("piercing", "outside the chamber, where a block breaks through its wall"),
                  ("walls", "inside the chamber, facing its back wall"),
                  ("hero", "beside a monolith")],
    },
    "ritual": {
        "example": "ae",
        "desc": "A small ritual room. Shelf walls wrap the left, right and back; one object at the centre is where you pause "
                "first; a counter sits at the back. The route circles the centre, then follows the shelves.",
        "roles": {
            "dome": R(["dome"], ["zone"], "the area under the ceiling dome (a named area, nothing built)"),
            "shelves": R(["wl", "wb", "wr"], SHELF, "the three walls of shelves that hold the product"),
            "hero": R(["basin"], SOLID_FEATURE, "the object at the centre where you pause first", hero=True),
            "pay": R(["counter"], ["box"], "the counter at the back"),
        },
        "stops": [("hero", "a few steps in, facing the centre object"),
                  ("shelves", "beside the left shelf wall"),
                  ("dome", "at the back of the loop, looking up at the dome")],
    },
}


def items(L, ids):
    return [i for i in L["items"] if i["id"] in ids]


def scale(job: dict, sx: float, sy: float) -> dict:
    """Uniform plan-scale of a job: footprints, route, stops. Heights stay."""
    j = copy.deepcopy(job)
    L = j["layout"]
    L["W"], L["D"] = round(L["W"] * sx, 2), round(L["D"] * sy, 2)
    for it in L["items"]:
        it["x0"], it["x1"] = round(it["x0"] * sx, 3), round(it["x1"] * sx, 3)
        if it.get("type") == "door" or it.get("shape") == "door":
            continue                                    # the door stays on the street edge
        it["y0"], it["y1"] = round(it["y0"] * sy, 3), round(it["y1"] * sy, 3)
    L["columns"] = [[round(c[0] * sx, 3), round(c[1] * sy, 3)] for c in L.get("columns", [])]
    for f in L["flows"]:
        f["pts"] = [[round(p[0] * sx, 3), round(p[1] * sy, 3)] for p in f["pts"]]
    for k in ("entry", "exit"):
        if k in L:
            L[k] = [round(L[k][0] * sx, 3), round(L[k][1] * sy, 3)]
    for s in j["stops"]:
        s["at"] = [round(s["at"][0] * sx, 3), round(s["at"][1] * sy, 3)]
        s["look"] = [round(s["look"][0] * sx, 3), s["look"][1], round(s["look"][2] * sy, 3)]
    return j


def fit(spec, job: dict, W=None, D=None) -> dict:
    """Scale toward the stated size; step back toward 1.0 until spec.check has nothing to say.
    -> {'job', 'sx', 'sy', 'asked': (W, D), 'tries': [...]}"""
    W0, D0 = job["layout"]["W"], job["layout"]["D"]
    tx = min(max((W or W0) / W0, 0.5), 2.0)
    ty = min(max((D or D0) / D0, 0.5), 2.0)
    tries = []
    for k in range(6):
        sx, sy = 1 + (tx - 1) * (1 - k / 5), 1 + (ty - 1) * (1 - k / 5)
        j = scale(job, sx, sy)
        bad = spec.check(j)
        tries.append({"sx": round(sx, 3), "sy": round(sy, 3), "problems": len(bad)})
        if not bad:
            return {"job": j, "sx": round(sx, 3), "sy": round(sy, 3), "asked": (W, D), "tries": tries}
    return {"job": copy.deepcopy(job), "sx": 1.0, "sy": 1.0, "asked": (W, D), "tries": tries}


def _min_dist(spec, L, it):
    return min(spec._rect_dist(x, y, it) for x, y in spec.path_points(L))


def _lab(L, ids):
    return items(L, ids)[0].get("label", ids[0])


def facts(spec, plan_id: str, job: dict) -> "list[str]":
    """Four true sentences about this layout, measured from it. The model only says what they mean.
    The model's labels go in brackets after a noun code chose, so the sentence stays grammatical whatever the label is."""
    L, P = job["layout"], PLANS[plan_id]["roles"]
    g = lambda r: items(L, P[r]["ids"])          # noqa: E731
    lab = lambda r: _lab(L, P[r]["ids"])         # noqa: E731
    if plan_id == "orbit":
        a, b = g("screen")
        th = g("threshold")
        v = g("void")[0]
        c = _min_dist(spec, L, g("hero")[0])
        return [f"A pair of threshold objects ({lab('threshold')}) stands {min(i['y0'] for i in th):.1f}-{max(i['y1'] for i in th):.1f} m inside the door, "
                f"with a hanging screen ({lab('screen')}) between them; the route slips through a {b['x0'] - a['x1']:.1f} m gap.",
                f"The hero ({lab('hero')}) stands alone in an empty {v['x1'] - v['x0']:.0f} x {v['y1'] - v['y0']:.0f} m area ({lab('void')}); "
                f"the route circles it and never comes closer than {c:.1f} m.",
                f"Four product stations ({lab('stations')}) sit at the outer corners, outside the loop, so you turn away from the hero to reach them.",
                f"The pay desk ({lab('pay')}) closes the loop at the back wall."]
    if plan_id == "field":
        s, h = g("strip")[0], g("hero")[0]
        st = g("stations")
        c = min(_min_dist(spec, L, i) for i in st)
        return [f"A floor strip ({lab('strip')}) runs {s['y1'] - s['y0']:.1f} m from the door toward the hero ({lab('hero')}).",
                f"The hero stands alone {h['y0']:.1f} m inside the door, {h['h']:.1f} m tall; nothing else rises above {max(i['h'] for i in st):.1f} m.",
                f"Four product stations ({lab('stations')}) ring it loosely, {c:.1f} m from the route at the closest.",
                f"The pay counter ({lab('pay')}) sits at the back right, where the route ends."]
    if plan_id == "chamber":
        ws = g("walls")
        x0, x1 = min(i["x0"] for i in ws), max(i["x1"] for i in ws)
        y0, y1 = min(i["y0"] for i in ws), max(i["y1"] for i in ws)
        hs = [i["h"] for i in g("hero")]
        left = sorted([i for i in ws if i["id"].startswith("w_left")], key=lambda i: i["y0"])
        gap = left[1]["y0"] - left[0]["y1"] if len(left) == 2 else 0
        return [f"A walled chamber ({lab('walls')}), {x1 - x0:.0f} x {y1 - y0:.0f} m, stands inside the room; you enter it through a {gap:.1f} m opening in its side.",
                f"Three low monoliths ({lab('hero')}) inside it carry the product at {min(hs):.1f}-{max(hs):.1f} m high.",
                f"Two blocks ({lab('piercing')}) break through the chamber walls on opposite sides.",
                f"The pay desk ({lab('pay')}) and the fitting room ({lab('fit')}) stay outside the chamber."]
    if plan_id == "ritual":
        h = g("hero")[0]
        return [f"Shelf walls ({lab('shelves')}) wrap the left, right and back of the {L['W']:.0f} x {L['D']:.0f} m room.",
                f"The centre object ({lab('hero')}) is the first stop, {h['y0']:.1f} m in from the door.",
                "The route circles it first, then follows the shelves.",
                f"The counter ({lab('pay')}) sits at the back, off the loop."]
    raise KeyError(plan_id)


def size_note(spec, ex: dict, W, D) -> str:
    if not (W or D):
        return f"default {ex['layout']['W']:g} x {ex['layout']['D']:g} m"
    f = fit(spec, ex, W, D)
    w, d = f["job"]["layout"]["W"], f["job"]["layout"]["D"]
    exact = abs(w - (W or w)) < .05 and abs(d - (D or d)) < .05
    return f"built at {w:g} x {d:g} m" + ("" if exact else f" (stated {W or '-'} x {D or '-'} m does not fit this plan)")


def cast(job: dict, plan_id: str, choice: dict) -> dict:
    j = copy.deepcopy(job)
    for role, c in choice.items():
        for it in items(j["layout"], PLANS[plan_id]["roles"][role]["ids"]):
            it["shape"] = c["shape"]
            it["label"] = c["label"]
            if c["shape"] not in ("zone", "door"):
                it["material"] = c["material"]
            if c["shape"] != "rock":
                it.pop("cloth", None)
    return j


def stop_points(job: dict) -> "list[dict]":
    return [{"at": s["at"], "look": s["look"], "h": s["h"], "d": s["d"]} for s in job["stops"]]


def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
