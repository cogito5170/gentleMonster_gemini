"""A fake flash-lite for the function-calling loop: it follows each result's `next`, fills arguments from the
listed options, and answers with the `say` line. For tests only (no network, no key).

Modes: ok · korean (first gm_story has a Korean title) · offlist (calls gm_story right after gm_plan) ·
liar (final answer claims DONE whatever happened) · badcast (a shape that is not on the role's list) ·
nocall (answers at once without calling a tool) · samecall (repeats gm_plan twice).
"""
from __future__ import annotations

import json


class FakeAgent:
    def __init__(self, mode: str = "ok"):
        self.mode, self.n, self.story_tries = mode, 0, 0

    def _reply(self, parts, model):
        usage = {"promptTokenCount": 500, "candidatesTokenCount": 60, "totalTokenCount": 560}
        return 200, json.dumps({"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": parts}}],
                                "usageMetadata": usage, "modelVersion": model}), {}

    def call(self, name, args, model):
        self.n += 1
        return self._reply([{"functionCall": {"name": name, "args": args, "id": f"c{self.n}"}}], model)

    def __call__(self, url, body, headers, hint):
        model = url.split("/models/")[1].split(":")[0]
        last = body["contents"][-1]
        if self.mode == "nocall":
            return self._reply([{"text": "Here is a design: all checks passed."}], model)
        if "text" in last["parts"][0]:
            req = last["parts"][0]["text"]
            return self.call("gm_new", {"request": req, "brand": "", "theme": "A quiet room of held rain.", "mood": ["quiet", "wet", "dark"],
                                        "hero_idea": "a black pool", "product": "eyewear"}, model)
        fr = last["parts"][-1]["functionResponse"]
        res, prev = fr["response"]["result"], fr["name"]
        if prev == "gm_finish" or prev == "gm_explain":
            say = res.get("say", "")
            if self.mode == "liar":
                return self._reply([{"text": "Done. All checks passed (DONE)."}], model)
            return self._reply([{"text": f"{say}\n\nThe Dry Threshold: you walk out of the rain."}], model)
        nxt = res["next"][0]
        job = res.get("job") or nxt.get("args", {}).get("job")
        t = nxt["tool"]
        if self.mode == "offlist" and prev == "gm_plan" and self.n < 4:
            return self.call("gm_story", {"job": job, "title": "x", "subtitle": "x", "line": "x.", "synopsis": "x", "keywords": [], "quote": "x", "why": []}, model)
        if self.mode == "samecall" and prev == "gm_plan" and self.n == 2:
            return self.call("gm_plan", {"job": job, "plan": "orbit"}, model)
        if t == "gm_plan":
            return self.call(t, {"job": job, "plan": nxt["args"]["plan"][0]}, model)
        if t == "gm_cast":
            roles = [{"role": r, "shape": ("door" if self.mode == "badcast" and r == "hero" else o["shape"][0]), "material": "black_stone",
                      "label": "black pool" if r == "hero" else f"{r} object"} for r, o in nxt["roles"].items()]
            from gmg.agent import SURFACE             # a real model reads these from the tool schema's enums
            room = {k: v[0] for k, v in SURFACE.items()}
            return self.call(t, {"job": job, "roles": roles, "room": room}, model)
        if t == "gm_story":
            self.story_tries += 1
            nf = len(nxt["facts"])
            title = "비 오는 밤" if self.mode == "korean" and self.story_tries == 1 else "The Dry Threshold"
            hero = nxt["args"]["synopsis"].split("mentions the ")[-1]
            return self.call(t, {"job": job, "title": title, "subtitle": "Where the rain is switched off",
                                 "line": "The rain stops at the door.",
                                 "synopsis": f"You come in out of the rain. You find the {hero} in the dark. You walk around it slowly.",
                                 "keywords": ["Threshold", "Held rain", "Silence"], "quote": "Inside, only the light is wet.",
                                 "why": [{"t": f"Step {i + 1} slows you", "d": f"It slows you down at step {i + 1}."} for i in range(nf)]}, model)
        if t == "gm_finish":
            return self.call(t, {"job": job, "palette": [{"hex": h, "name": n} for h, n in (("#121417", "Night stone"), ("#3a4148", "Wet concrete"),
                                                                                         ("#8d989f", "Steel rain"), ("#d8dde0", "Glow"), ("#c4422d", "Tail light"))],
                                 "accent": "5", "material_names": ["Basalt", "Concrete", "Steel", "Textile"],
                                 "stops": [{"cap": "I step out of the rain.", "sub": "The sound stops."},
                                           {"cap": "I see the pool move.", "sub": "Only the water moves."},
                                           {"cap": "I choose my frames.", "sub": "They wait at the edge."}]}, model)
        if t == "gm_explain":
            return self.call(t, {"job": job}, model)
        return self._reply([{"text": "stuck"}], model)
