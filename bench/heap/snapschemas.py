import json, sys
from collections import Counter
snap = json.load(open(sys.argv[1]))
meta = snap["snapshot"]["meta"]; nf = meta["node_fields"]; ef = meta["edge_fields"]
ntypes = meta["node_types"][0]; etypes = meta["edge_types"][0]
N, E, S = snap["nodes"], snap["edges"], snap["strings"]; NL, EL = len(nf), len(ef)
it, iname, iedges, isize = nf.index("type"), nf.index("name"), nf.index("edge_count"), nf.index("self_size")
et_, en_, eto = ef.index("type"), ef.index("name_or_index"), ef.index("to_node")
n = len(N) // NL
fe = [0] * (n + 1)
for k in range(n): fe[k + 1] = fe[k] + N[k * NL + iedges] * EL
def edges(k):
    for e in range(fe[k], fe[k + 1], EL):
        t = etypes[E[e + et_]]
        lab = S[E[e + en_]] if t in ("property", "internal", "context", "shortcut") else f"[{E[e + en_]}]"
        yield t, lab, E[e + eto] // NL
tn = lambda k: ntypes[N[k * NL + it]]; nm = lambda k: S[N[k * NL + iname]]
def keys(k, depth=2):
    if depth == 0: return "…"
    out = []
    for t, lab, to in edges(k):
        if t != "property" or lab in ("__proto__", "constructor"): continue
        if tn(to) == "object": out.append(f"{lab}:{{{keys(to, depth-1)}}}")
        elif tn(to) in ("string", "number"): out.append(f"{lab}={nm(to)[:25]}")
        else: out.append(lab)
    return ",".join(out[:12])
envs = [k for k in range(n) if tn(k) == "object" and nm(k) == "SchemaEnv"]
c = Counter()
for k in envs:
    sch = next((to for t, lab, to in edges(k) if lab == "schema"), None)
    c[keys(sch) if sch is not None else "?"] += 1
for s, m in c.most_common(8): print(m, s[:400])
