"""The extension's tools: a small state machine that flash-lite walks itself.

    gm_new -> gm_plan -> gm_cast -> gm_story -> gm_finish      (gm_explain at any time)

The agent (the model Gemini CLI runs; gemini-3-flash-preview by default, first built on gemini-3.1-flash-lite) fills each slot through the tool's arguments. Every result says
`ok`, what code measured or decided, and `next`: the closed list of calls that may come next, with the values each
argument may take. Code does plan, geometry, facts, materials, stops and the verdict. Nothing here calls a model.

- Wrong or missing values in a *choice* are replaced by the plan's own value and said in `notes` (the run goes on).
- Wrong *text* (Korean, sentence count, a missing word) returns ok:false with the facts and the same tool in `next`.
- Over-long display text is cut at a word boundary by code (NORMALIZE), never sent back: the model cannot count letters.
- Every call is idempotent: the same call again gives the same state. Re-deciding a step makes later steps stale.
- The verdict is the ledger's. Model text inside a job is data.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from gmg import asked_model, plans as PL, schema as S, upstream
from gmg.ledger import Ledger

ORDER = ["new", "plan", "cast", "story", "finish"]
PRODUCTS = ["eyewear", "fragrance", "skincare", "fashion", "objects"]
# brands of the four bundled gentleMonster jobs -> what they sell (closed: code, not the model, knows these)
KNOWN = {"gentle monster": ["eyewear"], "tamburins": ["fragrance", "skincare", "objects"], "aesop": ["skincare", "fragrance"],
         "acne studios": ["fashion", "eyewear"]}
FOG = {"none": 0.0, "light": 0.02, "dense": 0.045}
SURFACE = {"floor": ["concrete", "polished_concrete", "granite", "black_stone", "wood", "mineral_white", "white_gloss",
                     "graphite_wax", "strata_clay", "red_wax"],
           "wall": ["concrete", "mineral_white", "lime_plaster", "strata_clay", "wood", "aluminium", "mirror_aluminium",
                    "black_stone", "granite", "white_gloss"],
           "ceiling": ["concrete", "black_stone", "mineral_white", "lime_plaster", "wood", "aluminium", "mirror_aluminium",
                       "textile_light"],
           "light": ["dark_gallery", "white_gallery", "daylight", "warm_spot"],
           "fog": list(FOG)}
LIMIT = {"title": 40, "subtitle": 70, "line": 180, "quote": 110, "keyword": 24, "why": 180, "label": 40, "color": 24,
         "material": 30, "cap": 80, "sub": 110, "theme": 160, "hero_idea": 60, "mood": 20}
DIMS = [re.compile(r"(\d+(?:\.\d+)?)\s*(?:m|미터)?\s*[x×X*]\s*(\d+(?:\.\d+)?)\s*(?:m|미터)"),
        re.compile(r"(?:폭|너비|가로|width)\s*(\d+(?:\.\d+)?)\s*(?:m|미터)?.{0,12}?(?:깊이|세로|depth)\s*(\d+(?:\.\d+)?)", re.I)]
HANGUL = S.HANGUL


PLACEHOLDER = re.compile(r"^\s*([\(\[<{].*[\)\]>}]|none|n/?a|unknown|tbd|todo|null|nil|-+|—|brand|no brand|none named|not named|"
                         r"없음|미정|모름|해당 없음|브랜드 없음)\s*$", re.I)


def placeholder(t) -> bool:
    """Empty, bracketed or stock filler text ('(none named)', 'N/A', 'TBD', '없음') -- never printed on a page (H1)."""
    return not str(t or "").strip() or bool(PLACEHOLDER.match(str(t))) or "none named" in str(t).lower()


class ToolError(Exception):
    """Bad call: comes back to the agent as ok:false with the facts and the calls that fix it."""
    def __init__(self, problems, nxt):
        super().__init__("; ".join(problems))
        self.problems, self.next = problems, nxt


# ------------------------------------------------------------------ small helpers
def stated_size(text: str):
    for rx in DIMS:
        m = rx.search(text)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None


def cut(text, n):
    """Display text over n characters is cut at the last word boundary (code does what the model cannot: count)."""
    t = " ".join(str(text).split())
    if len(t) <= n:
        return t, False
    c = t[:n].rsplit(" ", 1)[0].rstrip(",;:-— ")
    return c, True


def _env():
    spec, paths = upstream.load()
    return spec, paths


def job_id(request: str, brand: str) -> str:
    return "gm-" + hashlib.sha256(f"{request}\n{brand}".encode()).hexdigest()[:8]


def _ledger(job: str) -> Ledger:
    spec, paths = _env()
    if not re.fullmatch(r"gm-[0-9a-f]{8}", job or ""):
        raise ToolError([f"job {job!r} is not a job id (gm- and 8 hex digits, from gm_new)"],
                        [{"tool": "gm_new", "why": "start a job; it returns the job id"}])
    L = Ledger(paths.job_dir(job))
    if not L.run():
        raise ToolError([f"there is no job {job}"], [{"tool": "gm_new", "why": "start a job; it returns the job id"}])
    return L


def decided(L: Ledger, step: str):
    """The step's latest decision, unless an earlier step was re-decided after it (then it is stale)."""
    run = L.run()
    last = {}
    for i, e in enumerate(run):
        if e.get("kind") == "DECISION" and e.get("step") in ORDER:
            last[e["step"]] = i
    if step not in last:
        return None
    k = ORDER.index(step)
    if any(last.get(s, -1) > last[step] for s in ORDER[:k]):
        return None
    return run[last[step]]["output"]


def need(L, step, tool, job):
    """The step's decision, or a ToolError whose `next` is the full offer for the first undecided step."""
    d = decided(L, step)
    if d is not None:
        return d
    first = next(s for s in ORDER if decided(L, s) is None)
    return _missing(L, first, job)


def _missing(L, step, job):
    spec, _ = _env()
    why = f"{step} is not decided yet (or an earlier step changed after it); decide it first"
    if step == "new":
        raise ToolError([why], [{"tool": "gm_new", "why": "start the job again"}])
    if step == "plan":
        n = decided(L, "new")
        raise ToolError([why], [offer_plan(spec, job, n["W"], n["D"])])
    if step == "cast":
        p, built = _built(spec, L)
        raise ToolError([why], [offer_cast(spec, job, p["plan"], built)])
    c = decided(L, "cast")
    raise ToolError([why], [offer_story(job, c["facts"], c["cast"]["hero"]["label"])])


def _decide(L, step, args, output, **kw):
    """Log a decision. A finished job that gets an earlier step re-decided is no longer finished."""
    run = L.run()
    if step != "finish" and any(e.get("kind") == "END" for e in run):
        L.log("END", state="(reopened)", rc=None, why=f"{step} was decided again after the job ended")
    L.log("DECISION", step=step, args=args, output=output, **kw)


def _same(L, step, args):
    d = next((e for e in reversed(L.run()) if e.get("kind") == "DECISION" and e.get("step") == step), None)
    return d is not None and d.get("args") == args and decided(L, step) is not None


# ------------------------------------------------------------------ what each step offers next
def offer_plan(spec, job, W, D):
    ex = spec.examples()
    return {"tool": "gm_plan", "args": {"job": job, "plan": list(PL.PLANS)},
            "options": {k: f"{p['short']} Size: {PL.size_note(spec, ex[p['example']], W, D)}." for k, p in PL.PLANS.items()},
            "why": "choose the floor plan that best stages the theme"}


def offer_cast(spec, job, plan_id, built):
    roles = {}
    for r, rs in PL.PLANS[plan_id]["roles"].items():
        it = PL.items(built["layout"], rs["ids"])[0]
        roles[r] = {"what": rs["desc"], "count": len(rs["ids"]), "size_m": [round(it["x1"] - it["x0"], 1), round(it["y1"] - it["y0"], 1)],
                    "shape": rs["shapes"]}
    # materials and room values are enums in the tool schema already: not repeated here (H3)
    return {"tool": "gm_cast", "args": {"job": job, "roles": "one {role, shape (from that role's list), material, label} per role"},
            "roles": roles, "shapes": {s: spec.SHAPES[s].split(";")[0] for s in sorted({x for r in roles.values() for x in r["shape"]})},
            "why": "shape, material and a short English label for every role; then the room surfaces and light"}


def offer_story(job, facts, hero):
    return {"tool": "gm_story", "args": {"job": job, "title": f"<= {LIMIT['title']} chars", "subtitle": f"<= {LIMIT['subtitle']} chars",
                                         "line": "one sentence", "synopsis": f"3-5 sentences, second person (you), mentions the {hero}",
                                         "keywords": "3 different words or short phrases", "quote": "the philosophy in one line",
                                         "why": f"{len(facts)} items, one per fact, in order: {{t: a 2-6 word headline, d: one sentence on what that fact does for the visitor}}"},
            "facts": facts, "why": "write the story in English"}


def offer_finish(job, anchors, mats):
    return {"tool": "gm_finish", "args": {"job": job, "palette": "5 items {hex: '#rrggbb', name}", "accent": ["1", "2", "3", "4", "5"],
                                          "material_names": [f"name for {m['preset']} (used for {m['where']})" for m in mats],
                                          "stops": [f"stop {i + 1}: {a}" for i, a in enumerate(anchors)]},
            "why": "colours, the accent (which palette colour), names for the 4 materials, and a first-person caption (cap) "
                   "with one line under it (sub) for each of the 3 walkthrough stops"}


EXPLAIN = lambda job: {"tool": "gm_explain", "args": {"job": job}, "why": "show the verdict and why the job came out this way"}  # noqa: E731


# ------------------------------------------------------------------ the tools
def gm_new(request: str, theme: str, mood, hero_idea: str, product: str, brand: str = "", plan: str = "") -> dict:
    spec, paths = _env()
    request = str(request or "").strip()
    if not request:
        raise ToolError(["request is empty; pass the user's request text verbatim"], [{"tool": "gm_new", "why": "call again with request"}])
    mood = [mood] if isinstance(mood, str) else list(mood or [])
    probs, notes = [], []
    for k, v in (("theme", theme), ("hero_idea", hero_idea)):
        if not str(v or "").strip():
            probs.append(f"{k} is empty")
        elif HANGUL.search(str(v)):
            probs.append(f"{k} contains Korean; write it in English")
    if len(mood) != 3 or any(not str(m).strip() or HANGUL.search(str(m)) for m in mood):
        probs.append(f"mood has {len(mood)} items; give exactly 3 English words")
    if probs:
        raise ToolError(probs, [{"tool": "gm_new", "why": "call again with the fields fixed"}])
    # The agent passes both `request` and `brand`, so the request is no proof of the brand: the brand is kept and,
    # if its letters are not in the request text, the note says so (run 1 of rev 2 overrode real brands here).
    b = str(brand or "").strip()
    options = []
    if b and placeholder(b):
        notes.append(f"brand {b!r} is a placeholder, not a brand; using Gentle Monster (the gentleMonster default)")
        options = [{"n": 1, "label": "1", "title": "keep Gentle Monster (the gentleMonster default)"},
                   {"n": 2, "label": "2", "title": "the user names the brand: call gm_new again with brand"}]
        b = ""
    if b and not any(w.lower() in request.lower() for w in re.findall(r"[A-Za-z]{2,}", b)):
        notes.append(f"brand {b!r} is not in the request text passed; kept -- check it is the user's")
    canon = {re.sub(r"[^a-z]", "", k): k.title() for k in KNOWN}          # 'gentleMonster', 'GENTLE-MONSTER' -> 'Gentle Monster'
    if re.sub(r"[^a-z]", "", b.lower()) in canon and b != canon[re.sub(r"[^a-z]", "", b.lower())]:
        notes.append(f"brand {b!r} read as {canon[re.sub(r'[^a-z]', '', b.lower())]!r}")
        b = canon[re.sub(r"[^a-z]", "", b.lower())]
    # only a brand written in the request with its own spelling may correct the product: the extension's name
    # ("gentleMonster" in "Design a store with gentleMonster") is not a brand claim
    named = bool(b) and b.lower() in request.lower()
    b = b or "Gentle Monster"
    if placeholder(product):
        product = ""
    known = KNOWN.get(b.lower()) if named else None      # the default brand never overrides what the brief sells
    if known and product not in known:
        notes.append(f"{b} sells {', '.join(known)}; product set to {known[0]}")
        product = known[0]
    if product not in PRODUCTS:
        notes.append(f"product {product!r} is not one of {PRODUCTS}; using objects")
        product = "objects"
    theme, c1 = cut(theme, LIMIT["theme"])
    hero_idea, c2 = cut(hero_idea, LIMIT["hero_idea"])
    W, D = stated_size(request)
    job = job_id(request, brand or "")
    L = Ledger(paths.job_dir(job))
    args = {"request": request, "brand": brand or "", "theme": theme, "mood": [cut(m, LIMIT["mood"])[0] for m in mood],
            "hero_idea": hero_idea, "product": product}
    if not _same(L, "new", args):
        L.log("START", run=hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:12], job=job, brief=request,
              brand=b, model="(the Gemini CLI agent)", upstream=upstream.LOCK["commit"])
        if c1 or c2:
            L.log("NORMALIZE", step="new", cut=[k for k, c in (("theme", c1), ("hero_idea", c2)) if c])
        _decide(L, "new", args, dict(args, brand=b, W=W, D=D), notes=notes)
    out = {"ok": True, "job": job, "brand": b, "product": product, "size_m": [W, D] if W else "not stated",
           "notes": notes, "next": [offer_plan(spec, job, W, D)]}
    if plan in PL.PLANS:                 # the plan chosen in the same call: one model turn fewer (H3)
        r = gm_plan(job, plan)
        out["built_m"], out["next"] = r["built_m"], r["next"]
        out["notes"] = notes + r["notes"]
    if options:
        out["options"] = options
    return out


def gm_plan(job: str, plan: str) -> dict:
    spec, _ = _env()
    L = _ledger(job)
    n = need(L, "new", "gm_new", job)
    notes = []
    if plan not in PL.PLANS:
        raise ToolError([f"plan {plan!r} is not one of {list(PL.PLANS)}"], [offer_plan(spec, job, n["W"], n["D"])])
    f = PL.fit(spec, spec.examples()[PL.PLANS[plan]["example"]], n["W"], n["D"])
    built = f["job"]
    out = {"plan": plan, "sx": f["sx"], "sy": f["sy"], "W": built["layout"]["W"], "D": built["layout"]["D"], "H": built["layout"]["H"]}
    if n["W"] and (abs(out["W"] - n["W"]) > .05 or abs(out["D"] - (n["D"] or out["D"])) > .05):
        notes.append(f"the stated {n['W']:g} x {n['D']:g} m does not fit this plan; built at {out['W']:g} x {out['D']:g} m")
    if not _same(L, "plan", {"plan": plan}):
        _decide(L, "plan", {"plan": plan}, out, scale_tries=f["tries"], notes=notes)
    return {"ok": True, "job": job, "built_m": [out["W"], out["D"], out["H"]], "notes": notes, "next": [offer_cast(spec, job, plan, built)]}


def _built(spec, L):
    p = decided(L, "plan")
    return p, PL.scale(spec.examples()[PL.PLANS[p["plan"]]["example"]], p["sx"], p["sy"])


def _mats(room, cast):
    use = {}
    for k in ("floor", "wall", "ceiling"):
        use.setdefault(room[k], []).append(k + ("s" if k == "wall" else ""))
    for x in cast.values():
        if x["shape"] not in ("zone", "door"):
            use.setdefault(x["material"], []).append(x["label"].lower())
    order = sorted(use, key=lambda m: -len(use[m]))
    for m in ("concrete", "steel", "glass", "wood"):
        if len(order) >= 4:
            break
        if m not in order:
            order.append(m)
            use[m] = ["details"]
    return [{"preset": m, "where": cut(", ".join(dict.fromkeys(use[m])), 60)[0]} for m in order[:4]]


def gm_cast(job: str, roles, room) -> dict:
    spec, _ = _env()
    L = _ledger(job)
    p = need(L, "plan", "gm_plan", job)
    _, built = _built(spec, L)
    R = PL.PLANS[p["plan"]]["roles"]
    given = {}
    for x in ([roles] if isinstance(roles, dict) and "role" in roles else roles if isinstance(roles, list) else
              [dict(v, role=k) for k, v in roles.items()] if isinstance(roles, dict) else []):
        if isinstance(x, dict) and x.get("role") in R:
            given[x["role"]] = x
    cast, notes = {}, []
    for r, rs in R.items():
        it = PL.items(built["layout"], rs["ids"])[0]
        own = {"shape": it.get("shape", "box"), "material": it.get("material", "concrete"), "label": it.get("label", r)}
        g = given.get(r, {})
        c, fb = {}, []
        for k in ("shape", "material"):
            ok_ = g.get(k) in (rs["shapes"] if k == "shape" else spec.MATERIALS)
            c[k] = g.get(k) if ok_ else own[k]
            fb += [] if ok_ else [k]
        lab = str(g.get("label") or "").strip()
        c["label"] = cut(lab, LIMIT["label"])[0] if lab and not HANGUL.search(lab) else own["label"]
        fb += [] if lab and not HANGUL.search(lab) else ["label"]
        if fb:
            notes.append(f"{r}: used the plan's own {'/'.join(fb)} ({', '.join(str(c[k]) for k in fb)})"
                         + ("" if g else " -- the role was not given"))
        cast[r] = c
    room = room if isinstance(room, dict) else {}
    rm = {}
    for k, opts in SURFACE.items():
        rm[k] = room.get(k) if room.get(k) in opts else (built["room"].get(k) if k != "fog" else "none")
        if room.get(k) not in opts:
            notes.append(f"room.{k}: used {rm[k]}")
    rm = {**{k: rm[k] for k in ("floor", "wall", "ceiling", "light")}, "fog": FOG[rm["fog"] if rm["fog"] in FOG else "none"],
          "beams": rm["light"] == "dark_gallery"}
    if built["room"].get("dome"):
        rm["dome"] = True
    cj = PL.cast(built, p["plan"], cast)
    facts = PL.facts(spec, p["plan"], cj)
    anchors = [f"{where}; you look at the {cast[role]['label']} ({cast[role]['shape']})" for role, where in PL.PLANS[p["plan"]]["stops"]]
    args = {"roles": cast, "room": rm}
    if not _same(L, "cast", args):
        _decide(L, "cast", args, {"cast": cast, "room": rm, "facts": facts, "anchors": anchors, "materials": _mats(rm, cast)}, notes=notes)
        if notes:
            L.log("FALLBACK", step="cast", used="the plan's own value", problems=notes)
    return {"ok": True, "job": job, "notes": notes, "next": [offer_story(job, facts, cast["hero"]["label"])]}


def _text_checks(v: str, where: str, sentences=None, must=()):
    out = []
    if not str(v or "").strip():
        return [f"{where} is empty"]
    if HANGUL.search(v):
        out.append(f"{where} contains Korean; write it in English")
    if sentences:
        n = S.sentences(v)
        if not sentences[0] <= n <= sentences[1]:
            out.append(f"{where} has {n} sentences; write {sentences[0]}-{sentences[1]}")
    for w in must:
        if not re.search(r"\b%s" % re.escape(w), v, re.I):
            out.append(f"{where} does not mention {w!r}")
    return out


def gm_story(job, title, subtitle, line, synopsis, keywords, quote, why) -> dict:
    L = _ledger(job)
    c = need(L, "cast", "gm_cast", job)
    keywords = [keywords] if isinstance(keywords, str) else list(keywords or [])
    why = [why] if isinstance(why, str) else list(why or [])
    hero = c["cast"]["hero"]["label"]
    hw = [w for w in re.findall(r"[A-Za-z]{4,}", hero)]
    probs = []
    for k, v in (("title", title), ("subtitle", subtitle), ("quote", quote)):
        probs += _text_checks(v, k)
    probs += _text_checks(line, "line", (1, 1))
    probs += _text_checks(synopsis, "synopsis", (3, 5), ("you",))
    if hw and synopsis and not any(re.search(r"\b%s" % re.escape(w), synopsis, re.I) for w in hw):
        probs.append(f"synopsis never mentions the {hero}, the object at the centre of the walk")
    if len(keywords) != 3 or len({str(k).strip().lower() for k in keywords}) != 3:
        probs.append(f"keywords: give 3 different ones (got {len(keywords)})")
    probs += [p for k in keywords for p in _text_checks(k, "a keyword")]
    if len(why) != len(c["facts"]):
        probs.append(f"why has {len(why)} sentences; give {len(c['facts'])}, one per fact, in order")
    # each why is {t: a 2-6 word headline, d: one sentence}; a bare sentence is accepted and its headline left to fix
    why = [w if isinstance(w, dict) else {"t": "", "d": str(w)} for w in why]
    probs += [p for i, w in enumerate(why) for p in _text_checks(w.get("d"), f"why[{i + 1}].d") + _text_checks(w.get("t"), f"why[{i + 1}].t")]
    if probs:
        L.log("REJECT", step="story", problems=probs)
        raise ToolError(probs, [offer_story(job, c["facts"], hero)])
    cutn = []
    out = {}
    for k, v in (("title", title), ("subtitle", subtitle), ("line", line), ("quote", quote)):
        out[k], was = cut(v, LIMIT[k])
        cutn += [k] if was else []
    out["synopsis"] = " ".join(str(synopsis).split())
    out["keywords"] = [cut(k, LIMIT["keyword"])[0] for k in keywords]
    out["why"] = []
    for i, w in enumerate(why):
        m, was = cut(w["d"], LIMIT["why"])
        cutn += [f"why[{i + 1}]"] if was else []
        out["why"].append({"t": cut(w["t"], 48)[0], "d": f"{c['facts'][i]} {m}"})
    args = {"title": title, "subtitle": subtitle, "line": line, "synopsis": synopsis, "keywords": keywords, "quote": quote, "why": why}
    if not _same(L, "story", args):
        if cutn:
            L.log("NORMALIZE", step="story", cut=cutn)
        _decide(L, "story", args, out)
    return {"ok": True, "job": job, "notes": [f"cut to length: {', '.join(cutn)}"] if cutn else [],
            "next": [offer_finish(job, c["anchors"], c["materials"])]}


def _nudge(palette, gap: float = 30) -> "list[str]":
    """Move a colour that sits within `gap` (RGB distance) of an earlier one: lighter if dark, darker if light, in
    steps of 12 per channel, until it clears every earlier colour. Returns what changed."""
    out = []
    for j in range(1, len(palette)):
        c = _rgb(palette[j]["hex"])
        step = 12 if sum(c) / 3 < 128 else -12
        moved = False
        for _ in range(30):
            if all(sum((a - b) ** 2 for a, b in zip(c, _rgb(palette[i]["hex"]))) ** .5 >= gap for i in range(j)):
                break
            c = [min(255, max(0, v + step)) for v in c]
            moved = True
        if moved:
            new = "#%02x%02x%02x" % tuple(c)
            out.append(f"colour {j + 1} {palette[j]['hex']} -> {new} (too close to an earlier colour)")
            palette[j] = dict(palette[j], hex=new)
    return out


def _rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def gm_finish(job, palette, accent, material_names, stops, draw: bool = True) -> dict:
    spec, paths = _env()
    L = _ledger(job)
    n, p, c, st = (need(L, s, "gm_" + s, job) for s in ("new", "plan", "cast", "story"))
    palette = list(palette or []) if isinstance(palette, list) else []
    material_names = [material_names] if isinstance(material_names, str) else list(material_names or [])
    stops = list(stops or []) if isinstance(stops, list) else []
    probs, fixed = [], []
    for i, x in enumerate(palette):          # a garbled value that still holds one #rrggbb is repaired by code (NORMALIZE)
        if isinstance(x, dict) and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(x.get("hex", ""))):
            m = re.search(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])", str(x.get("hex", "")))
            if m:
                fixed.append(f"colour {i + 1} hex {x['hex']!r} -> {m.group(0)}")
                palette[i] = dict(x, hex=m.group(0))
    if fixed:
        L.log("NORMALIZE", step="finish", cut=fixed)
    if len(palette) != 5:
        probs.append(f"palette has {len(palette)} items; give exactly 5, each {{hex: '#rrggbb', name}}")
    bad_hex = [f"colour {i + 1} hex {str(x.get('hex') if isinstance(x, dict) else x)!r} is not #rrggbb" for i, x in enumerate(palette)
               if not (isinstance(x, dict) and re.fullmatch(r"#[0-9a-fA-F]{6}", str(x.get("hex", ""))))]
    probs += bad_hex
    if not probs:
        nudged = _nudge(palette)            # near-identical colours are pushed apart by code, not sent back (H3)
        if nudged:
            L.log("NORMALIZE", step="finish", cut=nudged)
        probs += [q for x in palette for q in _text_checks(x.get("name"), "a colour name")]
    if str(accent) not in ("1", "2", "3", "4", "5"):
        probs.append(f"accent {accent!r} must be 1-5 (which palette colour)")
    if len(material_names) != 4:
        probs.append(f"material_names has {len(material_names)} names; give 4, in order")
    probs += [q for m in material_names for q in _text_checks(m, "a material name")]
    if len(stops) != 3 or not all(isinstance(s, dict) for s in stops):
        probs.append("stops needs exactly 3 items, each {cap, sub}")
    else:
        for i, s in enumerate(stops):
            probs += _text_checks(s.get("cap"), f"stop {i + 1} cap", (1, 1))
            probs += _text_checks(s.get("sub"), f"stop {i + 1} sub", (1, 2))
            if s.get("cap") and not re.search(r"\b(I|my|me)\b", s["cap"]):
                probs.append(f"stop {i + 1} cap is not first person (use I, my or me)")
    page = [("brand", n["brand"]), ("title", st["title"]), ("subtitle", st["subtitle"]), ("line", st["line"]), ("quote", st["quote"])]
    page += [(f"keyword {i + 1}", k) for i, k in enumerate(st["keywords"])] + [(f"why {i + 1}", w["t"]) for i, w in enumerate(st["why"])]
    page += [(f"{r} label", x["label"]) for r, x in c["cast"].items()] + [(f"colour {i + 1} name", x.get("name")) for i, x in enumerate(palette) if isinstance(x, dict)]
    page += [(f"material {i + 1}", m) for i, m in enumerate(material_names)] + [(f"stop {i + 1} {k}", s_.get(k)) for i, s_ in enumerate(stops) if isinstance(s_, dict) for k in ("cap", "sub")]
    probs += [f"{k} is placeholder text ({v!r}); write the real text" for k, v in page if placeholder(v)]
    if probs:
        L.log("REJECT", step="finish", problems=probs)
        raise ToolError(probs, [offer_finish(job, c["anchors"], c["materials"])])
    pal = [{"hex": x["hex"].lower(), "name": cut(x["name"], LIMIT["color"])[0]} for x in palette]
    mats = [{"name": cut(material_names[i], LIMIT["material"])[0], "where": m["where"], "preset": m["preset"]} for i, m in enumerate(c["materials"])]
    _, built = _built(spec, L)
    built = PL.cast(built, p["plan"], c["cast"])
    pts = PL.stop_points(built)
    sts = [dict(pt, cap=cut(s["cap"], LIMIT["cap"])[0], sub=cut(s["sub"], LIMIT["sub"])[0]) for pt, s in zip(pts, stops)]
    lay = built["layout"]
    lay["name"] = f"{st['title']} — {n['brand']}"
    lay["flows"][0]["color"] = pal[int(accent) - 1]["hex"]
    jobj = {"brand": n["brand"], **st, "palette": pal, "accent": pal[int(accent) - 1]["hex"], "materials": mats,
            "room": c["room"], "layout": lay, "stops": sts}
    args = {"palette": palette, "accent": str(accent), "material_names": material_names, "stops": stops}
    already = _same(L, "finish", args) and L.status()["state"] in ("DONE", "NEEDS_REVIEW")
    if not already:
        problems = spec.check(jobj)
        # A shape swap can change measured geometry (a round basin is measured as a circle, a box as a rectangle).
        # Code repairs that itself: the role whose items the problems name gets the plan's own shape back.
        reverted = []
        base = _built(spec, L)[1]
        for r, rs in PL.PLANS[p["plan"]]["roles"].items():
            if problems and any(any(i in pr for i in rs["ids"]) for pr in problems):
                own = PL.items(base["layout"], rs["ids"])[0].get("shape", "box")
                if c["cast"][r]["shape"] != own:
                    for it in PL.items(jobj["layout"], rs["ids"]):
                        it["shape"] = own
                    reverted.append(f"{r} -> {own}")
                    problems = spec.check(jobj)
        if reverted:
            L.log("REPAIR", step="finish", reverted=reverted, why="the cast shape broke the measured route clearance; the plan's own shape is used, the label kept")
        L.log("GATE", step="finish", problems=problems)
        L.log("DECISION", step="finish", args=args, output={"problems": problems})
        if problems:
            L.log("END", state="NEEDS_REVIEW", rc=3, why="spec.check: " + "; ".join(problems[:6]))
        else:
            from gentle_monster import pipeline
            jp = pipeline.save_job(job, jobj)
            L.artifact(jp, "job")
            L.artifact(jp.parent / "synopsis.md", "synopsis")
            drawn = ""
            if draw:
                drawn = _draw(L, pipeline, job)
            L.log("END", state="DONE", rc=0, drawn=drawn)
    return verdict(job)


def _draw(L, pipeline, job) -> str:
    import contextlib
    import sys
    try:
        with contextlib.redirect_stdout(sys.stderr):
            r = pipeline.layout(job, moodboard=False, use_llm=False, log=lambda m: None)
        L.artifact(r["pdf"], "layout")
        L.artifact(r["preview"], "layout_preview")
        return "layout.pdf"
    except Exception as e:                                  # noqa: BLE001 -- the job stands; the drawing is said to be missing
        L.log("NOTE", step="draw", why=f"layout PDF not drawn: {type(e).__name__} (pip install 'gentlemonster-gemini[render]')")
        return f"not drawn ({type(e).__name__})"


def verdict(job: str) -> dict:
    L = _ledger(job)
    s = L.status()
    run = L.run()
    end = next((e for e in reversed(run) if e.get("kind") == "END"), None)
    files = {k: str(L.dir / Path(e["path"]).name) for k, v in s["artifacts"].items() if v == "done"
             for e in run if e.get("kind") == "ARTIFACT" and e.get("what") == k}
    out = {"ok": s["state"] == "DONE", "job": job, "verdict": s["state"],
           "say": f"{job}: {s['state']}" + (f" -- {end.get('why')}" if end and end.get("why") else "") +
                  (f" -- files: {', '.join(Path(f).name for f in files.values())}" if files else ""),
           "files": files}
    sv = [e for e in run if e.get("kind") == "SERVED"]
    if sv and sv[-1].get("differs"):
        out["say"] += f" -- note: served by {sv[-1]['model']}, not {sv[-1].get('asked') or asked_model()}"
    if s["state"] == "NEEDS_REVIEW":
        gate = next((e for e in reversed(run) if e.get("kind") == "GATE"), {})
        out["problems"] = gate.get("problems", [])
        spec, _ = _env()
        p, c = decided(L, "plan"), decided(L, "cast")
        geometric = any(w in pr for pr in out["problems"] for w in ("circulation", "overlap", "envelope", "door", "stop "))
        if geometric and p:
            out["next"] = [offer_cast(spec, job, p["plan"], _built(spec, L)[1]), EXPLAIN(job)]
            out["fix"] = "the layout check failed: change the shapes in gm_cast (keep each role's listed shapes), then gm_story and gm_finish again"
        else:
            out["next"] = [offer_finish(job, c["anchors"], c["materials"]) if c else EXPLAIN(job), EXPLAIN(job)]
    else:
        out["next"] = [EXPLAIN(job)]
    return out


def gm_explain(job: str) -> dict:
    L = _ledger(job)
    run = L.run()
    lines = []
    for e in run:
        k = e.get("kind")
        if k == "DECISION":
            o = e["output"]
            s = e["step"]
            if s == "new":
                lines.append(f"brief: brand {o['brand']} · {o['product']} · theme: {o['theme']} · size {o['W'] or '-'} x {o['D'] or '-'} m (read by code)")
            elif s == "plan":
                lines.append(f"plan: {o['plan']}, built {o['W']:g} x {o['D']:g} x {o['H']:g} m")
            elif s == "cast":
                lines.append("cast: " + "; ".join(f"{r} = {x['label']} ({x['shape']}, {x['material']})" for r, x in o["cast"].items()))
                lines += [f"fact {i + 1} (measured by code): {f}" for i, f in enumerate(o["facts"])]
            elif s == "story":
                lines.append(f"story: {o['title']} — {o['line']}")
            elif s == "finish":
                lines.append("spec.check: " + ("passed" if not o["problems"] else "; ".join(o["problems"])))
        elif k in ("FALLBACK", "NORMALIZE", "REJECT", "NOTE"):
            lines.append(f"{k.lower()} ({e.get('step')}): " + "; ".join(map(str, e.get("problems") or e.get("cut") or [e.get("why", "")]))[:400])
        elif k == "END":
            lines.append(f"END: {e['state']}" + (f" ({e.get('why')})" if e.get("why") else ""))
        elif k == "SERVED":
            lines.append(f"served by {e['model']} ({e['source']})" + (f" -- NOT {e.get('asked') or asked_model()}" if e.get("differs") else ""))
    v = verdict(job)
    return {"ok": True, "job": job, "verdict": v["verdict"], "say": v["say"], "explain": lines, "files": v["files"],
            "next": [n_ for n_ in v["next"] if n_["tool"] != "gm_explain"] or [{"tool": "gm_new", "why": "start another job"}]}


# ------------------------------------------------------------------ S6 / S8: constraints on a job, render options
CONSTRAINTS = {"language": ["en_only", "ko_and_en"], "text_size": ["small", "normal"], "pages": ["one", "multi"],
               "include_rationale": [True, False], "generated_photos": [True, False], "follow_route": [True, False]}
OUTPUTS = ["layout_pdf", "moodboard_pdf", "blueprint_pdf", "video"]
# what gentleMonster @ the pinned commit can honour, and what it cannot -- said, not faked
SUPPORT = {("language", "en_only"): "printed pages are English already (spec.check refuses Korean text)",
           ("language", "ko_and_en"): "NOT supported: gentleMonster prints English only (spec.check refuses Korean)",
           ("text_size", "small"): "NOT supported by the pinned layout/moodboard templates (fixed type sizes); recorded",
           ("text_size", "normal"): "the templates' size",
           ("pages", "one"): "the layout PDF is one page; the moodboard is several spreads (NOT one page)",
           ("pages", "multi"): "the moodboard has several spreads",
           ("include_rationale", True): "the job's `why` (design intent) is printed on the layout page",
           ("include_rationale", False): "NOT supported: the layout page always prints the design intent",
           ("generated_photos", True): "with fewer than 3 photos the moodboard fills with renders of the room (labelled generated)",
           ("generated_photos", False): "recorded; the moodboard then needs 3 or more photos",
           ("follow_route", True): "the video camera walks the drawn route (flows[0]) and holds at the 3 stops",
           ("follow_route", False): "NOT supported: the video always follows the drawn route"}


def gm_amend(job: str, constraints=None, reference_image: str = "") -> dict:
    L = _ledger(job)
    cs = dict(constraints or {})
    probs, said = [], {}
    for k, v in cs.items():
        if k not in CONSTRAINTS or v not in CONSTRAINTS[k]:
            probs.append(f"{k}={v!r}: allowed {k} values are {CONSTRAINTS.get(k, 'none (unknown constraint)')}")
        else:
            said[k] = SUPPORT[(k, v)]
    if reference_image:
        if not Path(reference_image).is_file():
            probs.append(f"reference_image {reference_image!r} is not a file")
        else:
            cs["reference_image"] = str(Path(reference_image).resolve())
            said["reference_image"] = "the moodboard reads its spread order and masthead from it (measured; the vision read needs a model)"
    if probs:
        raise ToolError(probs, [{"tool": "gm_amend", "args": {"job": job, "constraints": CONSTRAINTS}}])
    L.log("CONSTRAINT", constraints=cs, effect=said)
    return {"ok": True, "job": job, "effect": said, "next": [{"tool": "gm_render", "args": {"job": job, "outputs": OUTPUTS}}]}


def gm_render(job: str, outputs=None) -> dict:
    """Draw what is asked with the pinned gentleMonster. Heavy outputs (blueprint, video) only when named."""
    import contextlib
    import sys
    L = _ledger(job)
    if L.status()["artifacts"].get("job") != "done":
        raise ToolError(["the job has not passed gm_finish (or job.json changed since)"], [EXPLAIN(job)])
    outputs = [outputs] if isinstance(outputs, str) else list(outputs or ["layout_pdf"])
    bad = [o for o in outputs if o not in OUTPUTS]
    if bad:
        raise ToolError([f"outputs {bad} are not in {OUTPUTS}"], [{"tool": "gm_render", "args": {"job": job, "outputs": OUTPUTS}}])
    cons = {}
    for e in L.run():
        if e.get("kind") == "CONSTRAINT":
            cons.update(e["constraints"])
    from gentle_monster import pipeline
    done, notes = {}, []
    for o in outputs:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                if o == "layout_pdf":
                    r = pipeline.layout(job, moodboard=False, use_llm=False, log=lambda m: None)
                    L.artifact(r["pdf"], "layout")
                    done[o] = Path(r["pdf"]).name
                elif o == "moodboard_pdf":
                    refs = [cons["reference_image"]] if cons.get("reference_image") else []
                    if cons.get("generated_photos") is False and len(pipeline._kept(job, "photos")) < 3:
                        raise RuntimeError("generated photos are not allowed and the job has fewer than 3 photos")
                    r = pipeline.layout(job, refs=refs, moodboard=True, use_llm=False, log=lambda m: None)
                    L.artifact(r["moodboard"], "moodboard")
                    done[o] = Path(r["moodboard"]).name
                elif o == "blueprint_pdf":
                    r = pipeline.blueprint(job, log=lambda m: None)
                    L.artifact(r["pdf"], "blueprint")
                    done[o] = Path(r["pdf"]).name
                elif o == "video":
                    mp4 = pipeline.video(job, log=lambda m: None)
                    L.artifact(mp4, "video")
                    done[o] = Path(mp4).name
        except Exception as e:                              # noqa: BLE001 -- a failed output is said, with its cause, not hidden
            why = f"{o} failed: {type(e).__name__}: {str(e)[:200]}"
            L.log("NOTE", step="render", why=why)
            notes.append(why)
    for k, v in cons.items():
        if (k, v) in SUPPORT and "NOT supported" in SUPPORT[(k, v)]:
            notes.append(f"{k}={v}: {SUPPORT[(k, v)]}")
    return {"ok": not [n for n in notes if "failed" in n], "job": job, "drawn": done, "notes": notes, "next": [EXPLAIN(job)]}


PREREQ = {"gm_plan": "new", "gm_cast": "plan", "gm_story": "cast", "gm_finish": "story"}
TOOLS = {"gm_new": gm_new, "gm_plan": gm_plan, "gm_cast": gm_cast, "gm_story": gm_story, "gm_finish": gm_finish, "gm_explain": gm_explain,
         "gm_amend": gm_amend, "gm_render": gm_render}


def call(name: str, args: dict) -> dict:
    """One tool call -> a result dict. Never raises for a bad call: the result says what to fix and what to call."""
    if name.startswith("pf_"):
        from gmg import portfolio
        if name in portfolio.TOOLS:
            return portfolio.call(name, args)
    if name not in TOOLS:
        return {"ok": False, "problems": [f"there is no tool {name}"], "next": [{"tool": "gm_new", "why": "start here"}]}
    try:
        if name in PREREQ and (args or {}).get("job"):
            need(_ledger(args["job"]), PREREQ[name], "gm_" + PREREQ[name], args["job"])   # order before arguments
        return TOOLS[name](**{k: v for k, v in (args or {}).items() if k in TOOLS[name].__code__.co_varnames})
    except ToolError as e:
        return {"ok": False, "problems": e.problems, "next": e.next}
    except TypeError as e:
        m = re.search(r"argument[s]?:? (.*)$", str(e))
        return {"ok": False, "problems": [f"missing argument(s): {m.group(1) if m else e}"],
                "next": [{"tool": name, "why": "call again with every argument"}]}
