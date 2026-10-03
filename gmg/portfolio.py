"""The portfolio workspace (CMD-GMG3 S1-S5, S7): photos, texts, terms, pages -- one state the agent works on.

State is folded from an append-only ledger (<GMG_OUT>/portfolio/gmg_ledger.jsonl), so every change keeps its
before and after, and the agent can always ask what is there (pf_show).

The agent writes the words; code measures photos, ranks and groups them, checks every text (language, length,
abstract-word ratio, the revision really did what was asked), keeps a page map, and numbers every option so a
terse reply ("1", "A안", "다시") resolves to one exact call (pf_choose).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from gmg import upstream
from gmg.ledger import Ledger

KINDS = ["answer", "cover_line", "statement", "question", "caption", "page_text", "sector"]   # page flow is pf_pages, not text
PHOTO_KINDS = ("caption", "sector")                                                             # need a measured photo
PATTERNS = ["plain", "signal", "couplet", "cycle", "reflection", "threshold", "question", "list"]
REGISTERS = ["direct", "poetic"]
LANGS = ["ko", "en", "ko+en"]
OPS = ["more_direct", "refocus", "widen_categories", "shorten", "translate"]
LETTERS = "ABCDEFGH"
# Abstract vocabulary, from general usage (fixed before the GMG3 evaluation run; not drawn from questions 32-42).
ABSTRACT = ["본질", "존재", "의미", "가치관", "철학", "정체성", "영감", "내면", "무의식", "세계관", "진정성", "조화", "균형", "서사", "감성",
            "상징", "영혼", "자아", "초월", "사유", "울림", "숨결", "여백", "잔상", "아우라", "미학", "본연", "궁극", "함의", "메타포", "결이",
            "essence", "existence", "meaning", "philosophy", "identity", "inspiration", "soul", "unconscious", "harmony", "balance",
            "narrative", "aesthetic", "ethereal", "transcend", "sublime", "resonance", "aura", "profound", "infinite", "poetic"]
LIMIT_DIRECT, LIMIT_POETIC = 0.06, 0.15
HANGUL = re.compile("[가-힣]")
LATIN = re.compile("[A-Za-z]")


class ToolError(Exception):
    def __init__(self, problems, nxt):
        super().__init__("; ".join(problems))
        self.problems, self.next = problems, nxt


# ------------------------------------------------------------------ text measures (code)
def words(t: str) -> "list[str]":
    return re.findall(r"[가-힣A-Za-z']+", t or "")


def abstract_ratio(t: str, keep=()) -> float:
    """Share of words built on an abstract stem. Words the user chose themselves (`keep`) are not counted."""
    w = words(t)
    if not w:
        return 0.0
    kept = [k.lower() for k in keep if k]
    hit = sum(1 for x in w if any(a in x.lower() for a in ABSTRACT) and not any(k in x.lower() for k in kept))
    return round(hit / len(w), 3)


def language(t: str) -> str:
    h, l = len(HANGUL.findall(t or "")), len(LATIN.findall(t or ""))
    if h and l and min(h, l) / max(h, l) > .25:
        return "ko+en"
    return "ko" if h >= l else "en"


def sentences(t: str) -> "list[str]":
    return [s for s in re.split(r"(?<=[.!?。다요])\s+", (t or "").strip()) if s]


def gates(t: str, register: str, lang: str, max_chars: int, pattern: str = "plain", keep=()) -> "tuple[list[str], dict]":
    """Facts about what is wrong with one text, and its measures."""
    meas = {"chars": len(t), "abstract_ratio": abstract_ratio(t, keep), "language": language(t)}
    bad = []
    if not t.strip():
        return ["the text is empty"], meas
    lim = LIMIT_DIRECT if register == "direct" else LIMIT_POETIC
    if meas["abstract_ratio"] > lim:
        hits = sorted({a for a in ABSTRACT for x in words(t) if a in x.lower() and not any(k.lower() in x.lower() for k in keep if k)})
        bad.append(f"{meas['abstract_ratio']:.0%} of the words are abstract ({', '.join(hits[:6])}); {register} allows {lim:.0%} -- name things the reader can see")
    if lang == "ko" and meas["language"] == "en" or lang == "en" and HANGUL.search(t) or lang == "ko+en" and meas["language"] != "ko+en":
        bad.append(f"the language is {meas['language']}; asked: {lang}")
    if max_chars and len(t) > max_chars * 1.2:
        bad.append(f"{len(t)} characters; the cap is {max_chars}")
    if pattern == "question" and not t.strip().endswith(("?", "？")):
        bad.append("a question pattern must end with a question mark")
    if pattern == "couplet" and len(re.split(r"[,.;—]\s*", t.strip().rstrip("."))) < 2:
        bad.append("a couplet needs two parallel halves")
    return bad, meas


# ------------------------------------------------------------------ state
def _ws() -> Ledger:
    _, paths = upstream.load()
    d = Path(paths.OUT) / "portfolio"
    d.mkdir(parents=True, exist_ok=True)
    return Ledger(d)


def state(L: "Ledger | None" = None) -> dict:
    L = L or _ws()
    st = {"terms": {}, "texts": [], "photos": [], "pages": {}, "proposals": [], "rankings": [], "concepts": [], "options": [], "last": None,
          "adopted": []}
    for e in L.events():
        k = e.get("kind")
        if k == "TERM":
            st["terms"].update(e["terms"])
        elif k == "TEXT":
            st["texts"].append(e["text"])
        elif k == "PHOTO":
            if all(p["id"] != e["photo"]["id"] for p in st["photos"]):
                st["photos"].append(e["photo"])
        elif k == "PAGE":
            for p in e["pages"]:
                st["pages"][str(p["n"])] = p
        elif k == "PROPOSAL":
            st["proposals"].append(e["proposal"])
        elif k == "ADOPT":
            st["adopted"].append(e["what"])
            for pr in st["proposals"]:
                if pr["id"] == e["what"].get("proposal"):
                    pr["adopted"] = e["what"]["option"]
        elif k == "RANKING":
            st["rankings"].append(e["ranking"])
        elif k == "CONCEPT":
            st["concepts"].append(e["concept"])
        elif k == "OPTIONS":
            st["options"] = e["options"]
        elif k == "CALL":
            st["last"] = e["call"]
    return st


def _text(st, tid):
    if tid == "last" and st["texts"]:
        return st["texts"][-1]
    return next((t for t in st["texts"] if t["id"] == tid), None)


def _new_text(L, st, kind, text, lang, **kw) -> dict:
    t = {"id": f"t{len(st['texts']) + 1}", "kind": kind, "lang": lang, "text": text, **kw}
    st["texts"].append(t)
    L.log("TEXT", text=t)
    return t


def _options(L, opts):
    """Number the choices; the same list goes to the agent and to the ledger (pf_choose resolves against it)."""
    L.log("OPTIONS", options=opts)
    return opts


def _call(L, tool, args):
    L.log("CALL", call={"tool": tool, "args": args})


def _brief_texts(ts, n=6):
    return [{"id": t["id"], "kind": t["kind"], "lang": t["lang"], "op": t.get("op"), "text": t["text"][:160] + ("…" if len(t["text"]) > 160 else "")}
            for t in ts[-n:]]


# ------------------------------------------------------------------ tools
def pf_show() -> dict:
    st = state()
    pages = [st["pages"][k] for k in sorted(st["pages"], key=lambda x: float(x))]
    return {"ok": True, "terms": st["terms"], "pages": pages,
            "texts": _brief_texts(st["texts"], 10), "photos": [{"id": p["id"], "file": p["file"], "brightness": p["brightness"], "saturation": p["saturation"],
                                                                 "hue": p["hue"], "subject_regions": p["subject_regions"], "colors": p["colors"][:3]} for p in st["photos"]],
            "proposals": [{"id": p["id"], "after_page": p["after"], "options": [f"{o['label']}: {o['title']}" for o in p["options"]], "adopted": p.get("adopted")}
                          for p in st["proposals"][-3:]],
            "next": [{"tool": "pf_photos", "why": "measure attached photos"}, {"tool": "pf_sort", "why": "rank or group measured photos"},
                     {"tool": "pf_write", "why": "write new text candidates"}, {"tool": "pf_revise", "why": "change a stored text"},
                     {"tool": "pf_concept", "why": "check a phrase against the terms"}, {"tool": "pf_pages", "why": "page map, next-page proposals, adopt"}]}


def pf_photos(paths) -> dict:
    from gmg import photo
    paths = [paths] if isinstance(paths, str) else list(paths or [])
    if not paths:
        raise ToolError(["paths is empty; pass the attached image paths"], [{"tool": "pf_photos"}])
    L = _ws()
    st = state(L)
    out, bad = [], []
    for p in paths:
        try:
            m = photo.measure(p)
        except ImportError:
            raise ToolError(["photo measuring needs Pillow and numpy: pip install pillow numpy"], [{"tool": "pf_show"}])
        except (ValueError, OSError) as e:
            bad.append(str(e))
            continue
        pid = "p" + hashlib.sha256(Path(p).read_bytes()).hexdigest()[:6]
        m = dict(m, id=pid, path=str(Path(p).resolve()))
        if all(x["id"] != pid for x in st["photos"]):
            L.log("PHOTO", photo=m)
        out.append(m)
    if not out:
        raise ToolError(bad, [{"tool": "pf_photos", "why": "pass existing image files"}])
    _call(L, "pf_photos", {"paths": paths})
    from gmg.photo import CRITERIA
    opts = _options(L, [{"n": i + 1, "label": str(i + 1), "title": f"rank all photos by {c}", "call": {"tool": "pf_sort", "args": {"by": c}}}
                        for i, c in enumerate(["single_subject", "brightest", "darkest", "most_saturated", "warmest"])])
    return {"ok": True, "photos": out, "problems": bad, "options": opts,
            "next": [{"tool": "pf_sort", "args": {"by": CRITERIA, "photos": [m["id"] for m in out]}, "why": "rank or group them"},
                     {"tool": "pf_write", "why": "write about them; use the measured colours and values"}]}


def pf_sort(by: str = "", photos=None, groups=None, k: int = 3) -> dict:
    from gmg import photo
    L = _ws()
    st = state(L)
    pool = [p for p in st["photos"] if not photos or p["id"] in photos or p["file"] in (photos or [])]
    if len(pool) < 1:
        raise ToolError(["no measured photos; measure them first"], [{"tool": "pf_photos", "why": "measure the photos"}])
    if groups:
        bad = [f"group {g.get('name')!r}: mood must be a list from {photo.MOODS}" for g in groups if not g.get("mood") or any(x not in photo.MOODS for x in g["mood"])]
        if bad:
            raise ToolError(bad, [{"tool": "pf_sort", "args": {"groups": [{"name": "…", "mood": photo.MOODS}]}}])
        assign = []
        for p in pool:
            fit = {g["name"]: round(photo.mood_fit(p, g["mood"]), 3) for g in groups}
            best = max(fit, key=fit.get)
            assign.append({"photo": p["id"], "file": p["file"], "group": best, "fit": fit,
                           "evidence": {k_: p[k_] for k_ in ("brightness", "saturation", "warmth", "sharpness", "hue")}})
        rk = {"id": f"r{len(st['rankings']) + 1}", "by": "groups", "groups": groups, "assign": assign, "order": [a["photo"] for a in assign]}
    else:
        if by not in photo.CRITERIA:
            raise ToolError([f"by {by!r} is not one of {photo.CRITERIA}"], [{"tool": "pf_sort", "args": {"by": photo.CRITERIA}}])
        ranked = sorted(pool, key=lambda p: -photo.score(p, by))
        rk = {"id": f"r{len(st['rankings']) + 1}", "by": by, "order": [p["id"] for p in ranked],
              "table": [{"rank": i + 1, "photo": p["id"], "file": p["file"], "score": round(photo.score(p, by), 3),
                         "evidence": {k_: p[k_] for k_ in ("brightness", "saturation", "sharpness", "subject_regions", "subject_share", "hue")}}
                        for i, p in enumerate(ranked)]}
    L.log("RANKING", ranking=rk)
    _call(L, "pf_sort", {"by": by, "photos": photos, "groups": groups})
    top = rk["order"][:max(1, min(k, 5))]
    opts = _options(L, [{"n": i + 1, "label": LETTERS[i], "title": f"use {pid}", "call": {"tool": "pf_write", "args": {"about": pid}}} for i, pid in enumerate(top)])
    return {"ok": True, "ranking": rk, "options": opts,
            "next": [{"tool": "pf_write", "why": "write the caption/word/page text for the chosen photo(s), citing the measured values"}]}


def pf_write(kind: str, items, register: str = "direct", language: str = "ko", max_chars: int = 0, about: str = "", keep=None) -> dict:
    L = _ws()
    st = state(L)
    if kind == "storyline":
        raise ToolError(["a storyline is page flow: propose it with pf_pages (action propose, exactly 3 options after a page)"],
                        [{"tool": "pf_pages", "args": {"action": "propose", "after": "page number", "options": "3 x {title, summary}"}}])
    if kind not in KINDS:
        raise ToolError([f"kind {kind!r} is not one of {KINDS}"], [{"tool": "pf_write", "args": {"kind": KINDS}}])
    if kind in PHOTO_KINDS and not any(p["id"] == about for p in st["photos"]):
        raise ToolError([f"a {kind} is about a photo: `about` must be the id of a measured photo (got {about!r})"],
                        [{"tool": "pf_photos", "why": "measure the photo first; its id goes in `about`"}, {"tool": "pf_sort", "why": "or pick from the measured photos"}])
    if register not in REGISTERS or language not in LANGS:
        raise ToolError([f"register must be one of {REGISTERS} and language one of {LANGS}"], [{"tool": "pf_write"}])
    items = [{"text": items}] if isinstance(items, str) else [i if isinstance(i, dict) else {"text": str(i)} for i in (items or [])]
    if not items:
        raise ToolError(["items is empty; give one or more {text, pattern, label}"], [{"tool": "pf_write"}])
    probs = []
    for i, it in enumerate(items):
        pat = it.get("pattern", "plain") if it.get("pattern") in PATTERNS else "plain"
        b, _ = gates(str(it.get("text", "")), register, language, int(max_chars or 0), pat, keep or ())
        probs += [f"item {i + 1}: {x}" for x in b]
    if probs:
        L.log("REJECT", step="pf_write", problems=probs)
        raise ToolError(probs, [{"tool": "pf_write", "why": "fix the items named and call again with all items"}])
    made = []
    for it in items:
        t = str(it["text"]).strip()
        _, meas = gates(t, register, language, int(max_chars or 0), keep=keep or ())
        made.append(_new_text(L, st, kind, t, language, keep=list(keep or []), register=register, pattern=it.get("pattern", "plain"), label=it.get("label", ""),
                              about=about, measures=meas))
    _call(L, "pf_write", {"kind": kind, "register": register, "language": language, "max_chars": max_chars, "about": about, "n": len(items)})
    opts = _options(L, [{"n": i + 1, "label": LETTERS[i], "title": f"adopt {t['id']}" + (f" ({t['label']})" if t.get("label") else ""),
                         "call": {"tool": "pf_pages", "args": {"action": "adopt", "choice": t["id"]}}} for i, t in enumerate(made)])
    return {"ok": True, "texts": [{"id": t["id"], "label": LETTERS[i], "measures": t["measures"]} for i, t in enumerate(made)], "options": opts,
            "next": [{"tool": "pf_revise", "args": {"op": OPS}, "why": "if the user asks for a change"},
                     {"tool": "pf_pages", "args": {"action": ["adopt", "propose"]}, "why": "adopt one or propose what comes next"}]}


ALIASES = [("style", "스타일"), ("fashion", "패션"), ("picture", "사진"), ("photo", "사진"), ("architecture", "건축"), ("space", "공간"),
           ("hair", "머리"), ("hair", "헤어"), ("eyewear", "안경"), ("glasses", "안경"), ("clothes", "옷"), ("shoes", "신발"),
           ("accessory", "액세서리"), ("accessory", "악세사리"), ("colour", "색"), ("color", "색"), ("scent", "향")]


def forms(word: str) -> "set[str]":
    """The word and its other-language forms (closed table), lower-case."""
    w = word.strip().lower()
    return {w} | {b for a, b in ALIASES if a == w} | {a for a, b in ALIASES if b == w}


def _has(text: str, word: str) -> int:
    return max(text.lower().count(f) for f in forms(word))


def _op_check(op, arg, old, new, lang, keep=()) -> "list[str]":
    bad = []
    if op == "more_direct":
        a0, a1 = abstract_ratio(old, keep), abstract_ratio(new, keep)
        if a1 > LIMIT_DIRECT or (a1 >= a0 and a0 > 0):
            bad.append(f"abstract words {a0:.0%} -> {a1:.0%}; more_direct must lower it (to <= {LIMIT_DIRECT:.0%}) -- use concrete things")
    elif op == "refocus":
        topic = (arg or "").strip()
        if not topic:
            bad.append("refocus needs arg = the topic")
        elif _has(new, topic) <= _has(old, topic) and not _has(new, topic):
            bad.append(f"the new text does not centre on {topic!r} (any of {sorted(forms(topic))} appears {_has(new, topic)} times)")
    elif op == "widen_categories":
        cats = [c.strip() for c in re.split(r"[,·/]", arg or "") if c.strip()]
        if not cats:
            bad.append("widen_categories needs arg = the categories, comma-separated")
        miss = [c for c in cats if not _has(new, c)]
        if miss:
            bad.append(f"these categories are not in the new text: {', '.join(miss)}")
    elif op == "shorten":
        if len(new) >= len(old) * .9:
            bad.append(f"{len(old)} -> {len(new)} characters; shorten must cut at least 10 %")
    elif op == "translate":
        if language(new) != (arg or lang):
            bad.append(f"the new text is {language(new)}; asked {arg}")
    if new.strip() == old.strip():
        bad.append("the new text is the same as the old one")
    return bad


def pf_revise(op: str, texts, targets=None, arg: str = "", source_text: str = "", register: str = "direct", keep=None) -> dict:
    L = _ws()
    st = state(L)
    if op not in OPS:
        raise ToolError([f"op {op!r} is not one of {OPS}"], [{"tool": "pf_revise", "args": {"op": OPS}}])
    texts = [texts] if isinstance(texts, str) else list(texts or [])
    targets = [targets] if isinstance(targets, str) else list(targets or [])
    olds = []
    if source_text:
        src = _new_text(L, st, "page_text", source_text.strip(), language(source_text), source="user")
        olds = [src]
    else:
        for tid in targets or ["last"]:
            t = _text(st, tid)
            if t is None:
                raise ToolError([f"there is no text {tid!r}"], [{"tool": "pf_show", "why": "see the stored text ids"}])
            olds.append(t)
    if len(texts) != len(olds):
        raise ToolError([f"{len(olds)} target(s) but {len(texts)} new text(s); give one new text per target, in order"],
                        [{"tool": "pf_revise", "args": {"targets": [t["id"] for t in olds]}}])
    probs = []
    kp = lambda o: list(keep or []) + list(o.get("keep") or [])      # noqa: E731 -- the user's own words stay allowed
    for i, (o, n) in enumerate(zip(olds, texts)):
        b = _op_check(op, arg, o["text"], str(n), o.get("lang", "ko"), kp(o))
        g, _ = gates(str(n), register, arg if op == "translate" else o.get("lang", "ko"), 0, keep=kp(o))
        probs += [f"{o['id']}: {x}" for x in b + [x for x in g if "abstract" not in x or op == "more_direct"]]
    if probs:
        L.log("REJECT", step="pf_revise", op=op, problems=probs)
        raise ToolError(probs, [{"tool": "pf_revise", "args": {"op": op, "targets": [t["id"] for t in olds]}, "why": "fix and call again"}])
    made = []
    for o, n in zip(olds, texts):
        n = str(n).strip()
        _, meas = gates(n, register, o.get("lang", "ko"), 0, keep=kp(o))
        made.append(_new_text(L, st, o["kind"], n, arg if op == "translate" else o.get("lang", "ko"), keep=kp(o), parent=o["id"], op=op, arg=arg,
                              register=register, measures=meas, before=o["text"]))
    _call(L, "pf_revise", {"op": op, "targets": [o["id"] for o in olds], "arg": arg})
    opts = _options(L, [{"n": i + 1, "label": LETTERS[i], "title": f"adopt {t['id']} ({t['parent']} {op})",
                         "call": {"tool": "pf_pages", "args": {"action": "adopt", "choice": t["id"]}}} for i, t in enumerate(made)])
    return {"ok": True, "texts": [{"id": t["id"], "parent": t["parent"], "label": LETTERS[i],
                                   "measures": t["measures"], "before_abstract": abstract_ratio(t["before"], t.get("keep", []))} for i, t in enumerate(made)],
            "options": opts, "next": [{"tool": "pf_pages", "args": {"action": ["adopt", "propose"]}}, {"tool": "pf_revise", "args": {"op": OPS}}]}


def pf_concept(phrase: str, verdicts, terms=None) -> dict:
    L = _ws()
    st = state(L)
    if terms:
        tt = {t["name"]: t.get("definition", "") for t in terms} if isinstance(terms, list) else dict(terms)
        L.log("TERM", terms=tt)
        st["terms"].update(tt)
    names = [k for k in st["terms"] if k != "SPA"] or list(st["terms"])
    if not names:
        raise ToolError(["no terms defined; pass terms [{name, definition}]"], [{"tool": "pf_concept"}])
    verdicts = list(verdicts or [])
    got = {v.get("term"): v for v in verdicts if isinstance(v, dict)}
    probs = [f"no verdict for {n}" for n in names if n not in got]
    for n in names:
        v = got.get(n, {})
        if v and v.get("connects") not in ("yes", "no", "partly"):
            probs.append(f"{n}: connects must be yes, no or partly")
        r = str(v.get("reason", ""))
        pool = set(w.lower() for w in words(phrase) + words(st["terms"].get(n, "")) + [n] if len(w) >= 2)
        if v and not any(w in r.lower() for w in pool):
            probs.append(f"{n}: the reason must quote a word from the phrase or from the definition of {n}")
    if probs:
        raise ToolError(probs, [{"tool": "pf_concept", "args": {"terms": names}, "why": "one verdict per term, each with a quoted reason"}])
    table = [{"term": n, "definition": st["terms"].get(n, ""), "connects": got[n]["connects"], "reason": got[n]["reason"]} for n in names]
    c = {"phrase": phrase, "table": table, "yes": sum(t["connects"] == "yes" for t in table), "of": len(table)}
    L.log("CONCEPT", concept=c)
    _call(L, "pf_concept", {"phrase": phrase})
    return {"ok": True, "concept": c, "say": f"\"{phrase}\" connects to {c['yes']} of {c['of']} terms (yes); partly: {sum(t['connects'] == 'partly' for t in table)}",
            "next": [{"tool": "pf_write", "why": "propose phrases that connect to every term"}]}


def pf_pages(action: str, pages=None, after=None, options=None, choice: str = "") -> dict:
    L = _ws()
    st = state(L)
    if action == "show":
        return {"ok": True, "pages": [st["pages"][k] for k in sorted(st["pages"], key=float)], "proposals": st["proposals"][-2:]}
    if action == "set":
        ps = [p for p in (pages or []) if isinstance(p, dict) and "n" in p]
        if not ps:
            raise ToolError(["pages: give [{n, title, role}]"], [{"tool": "pf_pages", "args": {"action": "set"}}])
        L.log("PAGE", pages=[{"n": p["n"], "title": str(p.get("title", "")), "role": str(p.get("role", ""))} for p in ps])
        _call(L, "pf_pages", {"action": "set"})
        st = state(L)
        return {"ok": True, "pages": [st["pages"][k] for k in sorted(st["pages"], key=float)],
                "next": [{"tool": "pf_pages", "args": {"action": "propose", "after": "page number"}, "why": "propose what comes next"}]}
    if action == "propose":
        opts = [o if isinstance(o, dict) else {"title": str(o), "summary": ""} for o in (options or [])]
        probs = []
        if len(opts) != 3:
            probs.append(f"give exactly 3 options (got {len(opts)})")
        if len({str(o.get('title', '')).strip().lower() for o in opts}) != len(opts):
            probs.append("two options have the same title")
        probs += [f"option {i + 1}: summary is empty" for i, o in enumerate(opts) if not str(o.get("summary", "")).strip()]
        probs += [f"option {i + 1}: {x}" for i, o in enumerate(opts) for x in gates(str(o.get("summary", "")), "direct", language(str(o.get("summary", ""))), 0)[0] if "abstract" in x]
        if after is None:
            probs.append("after: the page number these options follow")
        if probs:
            raise ToolError(probs, [{"tool": "pf_pages", "args": {"action": "propose", "after": after, "options": "3 x {title, summary}"}}])
        pr = {"id": f"q{len(st['proposals']) + 1}", "after": after, "options": [dict(o, label=LETTERS[i], n=i + 1) for i, o in enumerate(opts)], "adopted": None}
        L.log("PROPOSAL", proposal=pr)
        _call(L, "pf_pages", {"action": "propose", "after": after})
        o2 = _options(L, [{"n": i + 1, "label": LETTERS[i], "title": f"adopt {LETTERS[i]}: {o['title']}",
                           "call": {"tool": "pf_pages", "args": {"action": "adopt", "choice": f"{pr['id']}:{LETTERS[i]}"}}} for i, o in enumerate(opts)])
        return {"ok": True, "proposal": pr, "options": o2, "next": [{"tool": "pf_pages", "args": {"action": "adopt", "choice": [o["label"] for o in o2]}}]}
    if action == "adopt":
        ch = str(choice or "").strip()
        if re.fullmatch(r"t\d+", ch) and _text(st, ch):
            what = {"text": ch}
        else:
            m = re.fullmatch(r"(?:(q\d+):?)?([A-Ha-h1-8])", ch)
            pr = None
            if m:
                pr = next((p for p in st["proposals"] if p["id"] == m.group(1).lower()), None) if m.group(1) else (st["proposals"] or [None])[-1]
            opt = next((o for o in (pr or {}).get("options", []) if o["label"] == m.group(2).upper() or str(o["n"]) == m.group(2)), None) if m else None
            if not opt:
                raise ToolError([f"cannot resolve {choice!r} to a proposal option (A-C, or q<id>:A) or a text id (t<n>)"],
                                [{"tool": "pf_show", "why": "see proposals and text ids"}])
            what = {"proposal": pr["id"], "option": opt["label"], "title": opt["title"]}
        L.log("ADOPT", what=what)
        _call(L, "pf_pages", {"action": "adopt", "choice": ch})
        return {"ok": True, "adopted": what, "next": [{"tool": "pf_pages", "args": {"action": "propose"}, "why": "propose what comes after it"},
                                                      {"tool": "pf_write", "why": "write the adopted page"}]}
    raise ToolError([f"action {action!r} is not one of set, propose, adopt, show"], [{"tool": "pf_pages", "args": {"action": ["set", "propose", "adopt", "show"]}}])


def pf_choose(option: str) -> dict:
    """A terse reply -> one exact call: '1' / 'A' / 'A안' / 'a ? a:b' (the first that resolves) / 'retry' / '다시'."""
    L = _ws()
    st = state(L)
    o = str(option or "").strip()
    if re.search(r"retry|again|다시|재시도", o, re.I):
        last = st["last"]
        if not last:
            raise ToolError(["nothing to retry yet"], [{"tool": "pf_show"}])
        L.log("RETRY", call=last)
        prev = _brief_texts([t for t in st["texts"] if t.get("op") == last["args"].get("op") or last["tool"] == "pf_write"], 3)
        return {"ok": True, "retry": last, "avoid": prev,
                "next": [{"tool": last["tool"], "args": last["args"], "why": "call it again with a clearly different version than `avoid`"}]}
    for tok in re.findall(r"(?<![A-Za-z0-9])[A-Ha-h1-8](?![A-Za-z0-9])", o):     # a standalone label; 'A안' counts, 'zebra' does not
        opt = next((x for x in st["options"] if x["label"].lower() == tok.lower() or str(x["n"]) == tok), None)
        if opt:
            L.log("CHOSE", option=opt, said=o)
            r = call(opt["call"]["tool"], opt["call"]["args"]) if opt["call"]["tool"] == "pf_pages" or opt["call"]["tool"] == "pf_sort" else \
                {"ok": True, "next": [dict(opt["call"], why="write it")]}
            return dict(r, chose=opt)
    raise ToolError([f"{o!r} does not match a numbered option; the last options were: " + ", ".join(f"{x['label']}={x['title']}" for x in st["options"])],
                    [{"tool": "pf_show"}])


def seed(seed_json: dict, base: Path) -> None:
    """Load a starting state (bench only; not a tool)."""
    L = _ws()
    if L.events():
        return
    L.log("TERM", terms=seed_json["terms"])
    st = state(L)
    for t in seed_json["texts"]:
        _new_text(L, st, t["kind"], t["text"], t["lang"], source="seed")
    L.log("PAGE", pages=seed_json["pages"])
    pf_photos([str(base / p) for p in seed_json["photos"]])


TOOLS = {"pf_show": pf_show, "pf_photos": pf_photos, "pf_sort": pf_sort, "pf_write": pf_write, "pf_revise": pf_revise,
         "pf_concept": pf_concept, "pf_pages": pf_pages, "pf_choose": pf_choose}


def call(name: str, args: dict) -> dict:
    try:
        f = TOOLS[name]
        return f(**{k: v for k, v in (args or {}).items() if k in f.__code__.co_varnames[:f.__code__.co_argcount]})
    except ToolError as e:
        return {"ok": False, "problems": e.problems, "next": e.next}
    except TypeError as e:
        return {"ok": False, "problems": [f"missing or wrong argument: {e}"], "next": [{"tool": name, "why": "call again with every required argument"}]}
