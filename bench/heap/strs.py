import json, sys
from collections import Counter, defaultdict
snap = json.load(open(sys.argv[1]))
meta = snap["snapshot"]["meta"]; nf = meta["node_fields"]; ef = meta["edge_fields"]
ntypes = meta["node_types"][0]; etypes = meta["edge_types"][0]
N, E, S = snap["nodes"], snap["edges"], snap["strings"]
NL, EL = len(nf), len(ef)
it, iname, isize, iedges = nf.index("type"), nf.index("name"), nf.index("self_size"), nf.index("edge_count")
et_, en_, eto = ef.index("type"), ef.index("name_or_index"), ef.index("to_node")
n = len(N) // NL
fe = [0] * (n + 1)
for k in range(n): fe[k + 1] = fe[k] + N[k * NL + iedges] * EL
rev = defaultdict(list)
for k in range(n):
    for e in range(fe[k], fe[k + 1], EL):
        t = etypes[E[e + et_]]
        if t == "weak": continue
        lab = S[E[e + en_]] if t in ("property", "internal", "shortcut", "context") else f"[{E[e + en_]}]"
        rev[E[e + eto] // NL].append((k, lab))
tn = lambda k: ntypes[N[k * NL + it]]; nm = lambda k: S[N[k * NL + iname]]; sz = lambda k: N[k * NL + isize]
strs = [k for k in range(n) if tn(k) == "string"]
big = sorted(strs, key=sz, reverse=True)
print("strings", len(strs), round(sum(map(sz, strs)) / 2**20, 1), "MB; >=10KB:", sum(1 for k in strs if sz(k) >= 10240), round(sum(sz(k) for k in strs if sz(k) >= 10240) / 2**20, 1), "MB")
def path(k, depth=12):
    out, seen = [], {k}
    for _ in range(depth):
        rs = [r for r in rev.get(k, []) if r[0] not in seen]
        if not rs: break
        r = sorted(rs, key=lambda x: (x[1].startswith("["), tn(x[0]) in ("hidden", "code", "synthetic")))[0]
        out.append(f"{tn(r[0])}:{nm(r[0])[:30]}.{r[1][:30]}"); seen.add(r[0]); k = r[0]
        if tn(k) == "synthetic": break
    return out
groups = defaultdict(lambda: [0, 0])
for k in strs:
    if sz(k) < 4096: continue
    p = " <- ".join(path(k, 6))
    g = groups[p]; g[0] += 1; g[1] += sz(k)
for p, (c, s) in sorted(groups.items(), key=lambda x: -x[1][1])[:8]:
    print(f"{c:5d} strings {s/2**20:6.1f} MB  {p[:300]}")
for k in big[:6]:
    print(sz(k), repr(nm(k)[:100]))
