"""The decisions. One function = one decision = one MCP tool.

Each step reads what earlier steps decided from the ledger, asks the model for one narrow slot (options listed,
answer under a schema), checks the answer in code, re-asks once with the facts that are wrong, and writes a
DECISION event. Choice steps that still fail fall back to the plan's own value (FALLBACK, explained); text steps
that still fail stop the run.
"""
from __future__ import annotations

import json
import re

from gmg import plans as PL
from gmg import schema as S

SYSTEM = ("You fill one narrow slot of a spatial design job for an experimental flagship store. "
          "Answer only with JSON that matches the schema. Write English. "
          "Never write about checks, status, results, versions or which model you are -- code reports those.")
PRODUCTS = ["eyewear", "fragrance", "skincare", "fashion", "objects"]
FOG = {"none": 0.0, "light": 0.02, "dense": 0.045}
# what each room surface may be made of -- a narrower list than every preset (no light-textile floor)
SURFACE = {"floor": ["concrete", "polished_concrete", "granite", "black_stone", "wood", "mineral_white", "white_gloss",
                     "graphite_wax", "strata_clay", "red_wax"],
           "wall": ["concrete", "mineral_white", "lime_plaster", "strata_clay", "wood", "aluminium", "mirror_aluminium",
                    "black_stone", "granite", "white_gloss"],
           "ceiling": ["concrete", "black_stone", "mineral_white", "lime_plaster", "wood", "aluminium", "mirror_aluminium",
                       "textile_light"]}


class StepFailed(RuntimeError):
    def __init__(self, step, problems):
        super().__init__(f"{step}: " + "; ".join(problems[:6]))
        self.step, self.problems = step, problems


class Ctx:
    """What a step needs: the ledger, the model client, the pinned spec, the job name."""
    def __init__(self, name, ledger, gemini, spec, pipeline=None):
        self.name, self.L, self.g, self.spec, self.pipeline = name, ledger, gemini, spec, pipeline

    def got(self, step):
        d = self.L.decision(step)
        if not d:
            raise StepFailed(step, [f"step {step!r} has not been decided in this run yet"])
        return d["output"]


def _ask(ctx, step, prompt, sch, extra=None, retries=1, images=()):
    """-> (value, asks, problems). extra(value) -> more facts that code checks beyond the schema."""
    p, probs, v = prompt, [], None
    for r in range(retries + 1):
        res = ctx.g.ask(step, p, sch, images=images, system=SYSTEM)
        v, probs = res["value"], list(res["problems"])
        if not probs and extra:
            probs = extra(v)
        if not probs:
            return v, r + 1, []
        prev = json.dumps(v, ensure_ascii=False)[:4000] if v is not None else "(not JSON)"
        p = (prompt + "\n\nYour previous answer:\n" + prev + "\n\nThese things are true about that answer and must change:\n- "
             + "\n- ".join(probs) + "\n\nReturn the corrected JSON only.")
    return v, retries + 1, probs


def _decide(ctx, step, output, asks, **why):
    ctx.L.log("DECISION", step=step, output=output, asks=asks, **why)
    return output


def _str(n, **kw):
    return {"type": "string", "maxLength": n, "english": True, **kw}


# ------------------------------------------------------------------ 1. read the brief
DIMS = [re.compile(r"(\d+(?:\.\d+)?)\s*(?:m|미터)?\s*[x×X*]\s*(\d+(?:\.\d+)?)\s*(?:m|미터)"),
        re.compile(r"(?:폭|너비|가로|width)\s*(\d+(?:\.\d+)?)\s*(?:m|미터)?.{0,12}?(?:깊이|세로|depth)\s*(\d+(?:\.\d+)?)", re.I)]


def stated_size(brief: str):
    """Width and depth if the brief states them -- read by code, not by the model."""
    for rx in DIMS:
        m = rx.search(brief)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None


def read_brief(ctx, brief: str, brand: str = "") -> dict:
    sch = {"type": "object", "properties": {
        "brand_named": _str(40, minLength=0, description="the brand the brief names, in Latin letters; empty if none"),
        "place": _str(40, minLength=0, description="city or district, in English; empty if none"),
        "theme": _str(160, sentences=[1, 1], description="the brief's idea in one English sentence"),
        "mood": {"type": "array", "minItems": 3, "maxItems": 3, "items": _str(20)},
        "hero_idea": _str(60, description="the one object or image the space should be built around"),
        "product": {"type": "string", "enum": PRODUCTS}}}
    prompt = (f"Brief (may be Korean): {brief}\n\nRead the brief. Fill: brand_named, place, theme (one sentence), "
              f"mood (three single words), hero_idea (a short noun phrase), product (what the store sells).")
    v, asks, probs = _ask(ctx, "brief", prompt, sch)
    if probs:
        raise StepFailed("brief", probs)
    W, D = stated_size(brief)
    out = dict(v, brand=brand or v["brand_named"] or "Gentle Monster", W=W, D=D, text=brief)
    src = "given" if brand else ("named in the brief" if v["brand_named"] else "none named -> Gentle Monster (the gentleMonster default)")
    return _decide(ctx, "brief", out, asks, brief=brief, why={"brand": src, "size": "read from the brief by code" if W else "not stated"})


# ------------------------------------------------------------------ 2. pick a plan
def pick_plan(ctx) -> dict:
    b = ctx.got("brief")
    ex = ctx.spec.examples()
    opts = {k: f"{p['desc']} Size: {PL.size_note(ctx.spec, ex[p['example']], b['W'], b['D'])}." for k, p in PL.PLANS.items()}
    sch = {"type": "object", "properties": {"plan": {"type": "string", "enum": list(opts)}, "reason": _str(200, sentences=[1, 2])}}
    prompt = (f"Theme: {b['theme']}\nHero idea: {b['hero_idea']}\nMood: {', '.join(b['mood'])}\nProduct: {b['product']}\n\n"
              "Choose the floor plan that best stages this theme. Options:\n" + "\n".join(f"- {k}: {d}" for k, d in opts.items())
              + "\n\nAnswer with the plan id and one or two sentences of reason.")
    v, asks, probs = _ask(ctx, "plan", prompt, sch)
    fell = bool(probs)
    if fell:
        v = {"plan": "orbit", "reason": "fallback: the answer did not name a listed plan"}
        ctx.L.log("FALLBACK", step="plan", problems=probs, used="orbit")
    f = PL.fit(ctx.spec, ex[PL.PLANS[v["plan"]]["example"]], b["W"], b["D"])
    out = {"plan": v["plan"], "reason": v["reason"], "sx": f["sx"], "sy": f["sy"],
           "W": f["job"]["layout"]["W"], "D": f["job"]["layout"]["D"], "H": f["job"]["layout"]["H"]}
    return _decide(ctx, "plan", out, asks, options=opts, fallback=fell, scale_tries=f["tries"])


def _geometry(ctx):
    p = ctx.got("plan")
    ex = ctx.spec.examples()[PL.PLANS[p["plan"]]["example"]]
    return p, PL.scale(ex, p["sx"], p["sy"])


# ------------------------------------------------------------------ 3. cast the roles
def cast_roles(ctx) -> dict:
    b, (p, job) = ctx.got("brief"), _geometry(ctx)
    roles = PL.PLANS[p["plan"]]["roles"]
    mats = sorted(ctx.spec.MATERIALS)
    props = {r: {"type": "object", "properties": {
        "shape": {"type": "string", "enum": spec_["shapes"]},
        "material": {"type": "string", "enum": mats},
        "label": _str(40, description="what the visitor would call it, 1-5 words")}} for r, spec_ in roles.items()}
    sch = {"type": "object", "properties": props}
    lines = []
    for r, rs in roles.items():
        it = PL.items(job["layout"], rs["ids"])[0]
        lines.append(f"- {r}: {rs['desc']} ({len(rs['ids'])} x, about {it['x1'] - it['x0']:.1f} x {it['y1'] - it['y0']:.1f} m). "
                     f"shapes: " + "; ".join(f"{s} = {ctx.spec.SHAPES[s]}" for s in rs["shapes"]))
    prompt = (f"Theme: {b['theme']}\nHero idea: {b['hero_idea']}\nMood: {', '.join(b['mood'])}\nProduct: {b['product']}\n"
              f"Plan: {p['plan']}\n\nFor each role choose a shape (from that role's list), a material and a short label. "
              f"Materials: {', '.join(mats)}.\nRoles:\n" + "\n".join(lines))
    v, asks, probs = _ask(ctx, "cast", prompt, sch)
    out, fell = {}, []
    for r, rs in roles.items():
        c = (v or {}).get(r) if isinstance(v, dict) else None
        c = c if isinstance(c, dict) else {}
        it = PL.items(job["layout"], rs["ids"])[0]
        own = {"shape": it.get("shape", "box"), "material": it.get("material", "concrete"), "label": it.get("label", r)}
        bad = [k for k, q in props[r]["properties"].items() if k not in c or S.check(c[k], q, k)]
        if bad:                                     # keep what was valid, take the plan's own value for the rest
            c = {k: (own[k] if k in bad else c[k]) for k in own}
            fell.append(f"{r}.{'/'.join(bad)}")
        out[r] = c
    if fell:
        ctx.L.log("FALLBACK", step="cast", roles=fell, problems=probs, used="the plan's own shape, material and label")
    return _decide(ctx, "cast", out, asks, fallback=fell)


# ------------------------------------------------------------------ 4. room
def pick_room(ctx) -> dict:
    b, c = ctx.got("brief"), ctx.got("cast")
    _, job = _geometry(ctx)
    mats, lights = sorted(ctx.spec.MATERIALS), sorted(ctx.spec.LIGHTS)
    sch = {"type": "object", "properties": {
        **{k: {"type": "string", "enum": [m for m in v if m in mats]} for k, v in SURFACE.items()},
        "light": {"type": "string", "enum": lights},
        "fog": {"type": "string", "enum": list(FOG)}, "beams": {"type": "boolean"}}}
    prompt = (f"Theme: {b['theme']}\nMood: {', '.join(b['mood'])}\nThe hero is a {c['hero']['label']} ({c['hero']['material']}).\n\n"
              f"Choose the room's floor, wall and ceiling materials, the light (dark_gallery = dark room, spot-lit objects; "
              f"white_gallery = bright white; daylight = soft day; warm_spot = warm pools of light), fog and whether light beams show.")
    v, asks, probs = _ask(ctx, "room", prompt, sch)
    if probs:
        ctx.L.log("FALLBACK", step="room", problems=probs, used="the plan's own room")
        v = dict(job["room"])
        v.setdefault("fog", 0.0)
        out = v
    else:
        out = {k: v[k] for k in ("floor", "wall", "ceiling", "light")}
        out["fog"], out["beams"] = FOG[v["fog"]], v["beams"]
        if job["room"].get("dome"):
            out["dome"] = True
    return _decide(ctx, "room", out, asks, fallback=bool(probs))


# ------------------------------------------------------------------ 5. story
def _cast_job(ctx):
    p, job = _geometry(ctx)
    return p, PL.cast(job, p["plan"], ctx.got("cast"))


def _words(label):
    return [w for w in re.findall(r"[A-Za-z]{4,}", label)]


def write_story(ctx) -> dict:
    b, c = ctx.got("brief"), ctx.got("cast")
    p, job = _cast_job(ctx)
    F = PL.facts(ctx.spec, p["plan"], job)
    hero = c["hero"]["label"]
    sch = {"type": "object", "properties": {
        "title": _str(40), "subtitle": _str(70), "line": _str(180, sentences=[1, 1]),
        "synopsis": _str(900, minLength=60, sentences=[3, 5], must=["you"]),
        "keywords": {"type": "array", "minItems": 3, "maxItems": 3, "items": _str(24)},
        "quote": _str(110),
        "why": {"type": "array", "minItems": len(F), "maxItems": len(F), "items": {"type": "object", "properties": {
            "t": _str(60, description="a short headline for this layout fact"),
            "meaning": _str(180, sentences=[1, 1], description="one sentence: what this fact does for the visitor")}}}}}

    def extra(v):
        bad = []
        if len({k.strip().lower() for k in v["keywords"]}) < 3:
            bad.append("two keywords are the same; give three different keywords")
        ws = _words(hero)
        if ws and not any(re.search(r"\b%s" % re.escape(w), v["synopsis"], re.I) for w in ws):
            bad.append(f"the synopsis never mentions the {hero}, the object at the centre of the walk")
        return bad

    prompt = (f"Brand: {b['brand']}\nBrief: {b['text']}\nTheme: {b['theme']}\nMood: {', '.join(b['mood'])}\n"
              f"Product: {b['product']}\nThe room ({job['layout']['W']:g} x {job['layout']['D']:g} m): "
              + "; ".join(f"{r} = {x['label']} ({x['shape']}, {x['material']})" for r, x in c.items()) +
              "\n\nLayout facts (true, measured):\n" + "\n".join(f"{i + 1}. {f}" for i, f in enumerate(F)) +
              "\n\nWrite: title, subtitle, line (one sentence), synopsis (3-5 sentences, second person 'you', concrete "
              "materials, light, motion and what the visitor does), keywords (3), quote (the philosophy in one line), and "
              f"why: one item per layout fact, in the same order ({len(F)} items), each with a short headline t and one "
              "sentence of meaning.")
    v, asks, probs = _ask(ctx, "story", prompt, sch, extra=extra)
    if probs:
        raise StepFailed("story", probs)
    out = {k: v[k] for k in ("title", "subtitle", "line", "synopsis", "keywords", "quote")}
    out["why"] = [{"t": w["t"], "d": f"{F[i]} {w['meaning']}"} for i, w in enumerate(v["why"])]
    return _decide(ctx, "story", out, asks, facts=F)


# ------------------------------------------------------------------ 6. palette and material names
def _materials(ctx, job):
    """Four distinct presets in order of how much of the room they cover; `where` from the roles. Code, not model."""
    room, c = ctx.got("room"), ctx.got("cast")
    use = {}
    for k in ("floor", "wall", "ceiling"):
        use.setdefault(room[k], []).append(k + ("s" if k == "wall" else ""))
    for r, x in c.items():
        if x["shape"] not in ("zone", "door"):
            use.setdefault(x["material"], []).append(x["label"].lower())
    order = sorted(use, key=lambda m: -len(use[m]))
    for m in ("concrete", "steel", "glass", "wood"):
        if len(order) >= 4:
            break
        if m not in order:
            order.append(m)
            use[m] = ["details"]
    return [{"preset": m, "where": ", ".join(dict.fromkeys(use[m]))[:60]} for m in order[:4]]


def _rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def pick_palette(ctx) -> dict:
    b = ctx.got("brief")
    _, job = _cast_job(ctx)
    mats = _materials(ctx, job)
    sch = {"type": "object", "properties": {
        "palette": {"type": "array", "minItems": 5, "maxItems": 5, "items": {"type": "object", "properties": {
            "hex": {"type": "string", "pattern": r"#[0-9a-fA-F]{6}"}, "name": _str(24)}}},
        "accent": {"type": "string", "enum": ["1", "2", "3", "4", "5"], "description": "which palette colour is the accent"},
        "material_names": {"type": "array", "minItems": 4, "maxItems": 4, "items": _str(30)}}}

    def extra(v):
        bad, cols = [], [_rgb(p["hex"]) for p in v["palette"]]
        for i in range(5):
            for j in range(i + 1, 5):
                if sum((a - b_) ** 2 for a, b_ in zip(cols[i], cols[j])) ** .5 < 30:
                    bad.append(f"colours {i + 1} and {j + 1} ({v['palette'][i]['hex']}, {v['palette'][j]['hex']}) are almost the same")
        if len({p["name"].lower() for p in v["palette"]}) < 5:
            bad.append("two colours share a name")
        return bad

    prompt = (f"Brand: {b['brand']}\nTheme: {b['theme']}\nMood: {', '.join(b['mood'])}\n\n"
              "Give a palette of 5 colours (#rrggbb and a short evocative name), say which one is the accent "
              "(the one bright signal colour), and name these 4 materials as a designer would write them on a board:\n"
              + "\n".join(f"{i + 1}. {m['preset']} (used for: {m['where']})" for i, m in enumerate(mats)))
    v, asks, probs = _ask(ctx, "palette", prompt, sch, extra=extra)
    if probs:
        raise StepFailed("palette", probs)
    pal = [{"hex": p["hex"].lower(), "name": p["name"]} for p in v["palette"]]
    out = {"palette": pal, "accent": pal[int(v["accent"]) - 1]["hex"],
           "materials": [{"name": v["material_names"][i], "where": m["where"], "preset": m["preset"]} for i, m in enumerate(mats)]}
    return _decide(ctx, "palette", out, asks)


# ------------------------------------------------------------------ 7. stops
def write_stops(ctx) -> dict:
    b, c, st = ctx.got("brief"), ctx.got("cast"), ctx.got("story")
    p, job = _cast_job(ctx)
    anchors = PL.PLANS[p["plan"]]["stops"]
    sch = {"type": "object", "properties": {"stops": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "object", "properties": {
        "cap": _str(80, sentences=[1, 1], description="first person, one line: what I see or do here"),
        "sub": _str(110, sentences=[1, 2], description="one line under it")}}}}}

    def extra(v):
        return [f"stop {i + 1} cap is not in the first person (use I, my or me)" for i, s in enumerate(v["stops"])
                if not re.search(r"\b(I|my|me)\b", s["cap"])]

    prompt = (f"Title: {st['title']}\nSynopsis: {st['synopsis']}\n\nThe walkthrough video holds at 3 moments. For each, write a "
              "caption in the first person (cap) and one line under it (sub):\n"
              + "\n".join(f"{i + 1}. {where}; you look at the {c[role]['label']} ({c[role]['shape']})." for i, (role, where) in enumerate(anchors)))
    v, asks, probs = _ask(ctx, "stops", prompt, sch, extra=extra)
    if probs:
        raise StepFailed("stops", probs)
    out = [dict(pt, cap=s["cap"], sub=s["sub"]) for pt, s in zip(PL.stop_points(job), v["stops"])]
    return _decide(ctx, "stops", out, asks)


# ------------------------------------------------------------------ 8. assemble and judge
def assemble(ctx) -> dict:
    """Code only. Builds job.json, runs the pinned spec.check; a cast that breaks the geometry is reverted role by role."""
    b, c, room, st, pal, stops = (ctx.got(s) for s in ("brief", "cast", "room", "story", "palette", "stops"))
    p, base = _geometry(ctx)
    roles = PL.PLANS[p["plan"]]["roles"]

    def build(cast):
        j = PL.cast(base, p["plan"], cast)
        L = j["layout"]
        L["name"] = f"{st['title']} — {b['brand']}"
        L["flows"][0]["color"] = pal["accent"]
        job = {"brand": b["brand"], **st, **pal, "room": room, "layout": L, "stops": stops}
        return job

    cast, reverted = dict(c), []
    job = build(cast)
    probs = ctx.spec.check(job)
    for r, rs in roles.items():
        if not probs:
            break
        hit = any(any(i in pr for i in rs["ids"]) for pr in probs)
        if hit:
            it = PL.items(base["layout"], rs["ids"])[0]
            cast[r] = {"shape": it.get("shape", "box"), "material": it.get("material", "concrete"), "label": c[r]["label"]}
            reverted.append(r)
            job = build(cast)
            probs = ctx.spec.check(job)
    if reverted:
        ctx.L.log("REPAIR", step="assemble", reverted=reverted, why="the cast shape broke the measured layout; the plan's shape is used, the label kept")
    ctx.L.log("GATE", step="assemble", problems=probs)
    out = {"job": job, "problems": probs, "reverted": reverted}
    _decide(ctx, "assemble", {"problems": probs, "reverted": reverted}, 0)
    return out


# ------------------------------------------------------------------ vision (the reference read, PREP C2)
def vision(ctx, catalog):
    """An ask_vision for gentle_monster.moodboard: the same question, answered under a schema."""
    sch = {"type": "object", "properties": {
        "sequence": {"type": "array", "minItems": 2, "maxItems": len(catalog), "items": {"type": "string", "enum": list(catalog)}},
        "masthead": {"type": "string", "enum": ["stencil", "solid", "outline"]},
        "type": {"type": "string", "enum": ["grotesk", "serif"]},
        "mood": {"type": "array", "minItems": 3, "maxItems": 3, "items": _str(20)}}}

    def ask_vision(prompt, ref):
        from pathlib import Path
        data = Path(ref).read_bytes()
        mime = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ("image/webp" if data[8:12] == b"WEBP" else "image/jpeg")
        res = ctx.g.ask("vision", prompt, sch, images=[(mime, data)], system=SYSTEM)
        return json.dumps(res["value"] or {})
    return ask_vision
