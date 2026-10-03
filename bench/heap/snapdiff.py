import json, sys
from collections import Counter, defaultdict
def load(p):
    snap = json.load(open(p))
    meta = snap["snapshot"]["meta"]; nf = meta["node_fields"]; ef = meta["edge_fields"]
    ntypes = meta["node_types"][0]; etypes = meta["edge_types"][0]
    N, E, S = snap["nodes"], snap["edges"], snap["strings"]
    NL, EL = len(nf), len(ef)
    it, iname, isize, iedges = nf.index("type"), nf.index("name"), nf.index("self_size"), nf.index("edge_count")
    et_, en_, eto = ef.index("type"), ef.index("name_or_index"), ef.index("to_node")
    n = len(N) // NL
    fe = [0] * (n + 1)
    for k in range(n): fe[k + 1] = fe[k] + N[k * NL + iedges] * EL
    parent = {}
    for k in range(n):
        for e in range(fe[k], fe[k + 1], EL):
            t = etypes[E[e + et_]]
            if t == "weak": continue
            to = E[e + eto] // NL
            lab = S[E[e + en_]] if t in ("property", "internal", "context") else "[]"
            if to not in parent or (parent[to][1] == "[]" and lab != "[]"):
                parent[to] = (k, lab)
    tn = lambda k: ntypes[N[k * NL + it]]; nm = lambda k: S[N[k * NL + iname]]
    def owner(k, depth=10):
        # walk up to the first named object (constructor not Object/Array) and record the property chain
        chain = []
        for _ in range(depth):
            if k not in parent: break
            k, lab = parent[k]
            chain.append(lab)
            if tn(k) == "object" and nm(k) not in ("Object", "Array", "(object elements)", "system / Context"):
                return f"{nm(k)}." + ".".join(reversed([c for c in chain if c != "[]"][-3:]))
        return "?"
    agg = Counter()
    for k in range(n):
        t = tn(k)
        key = (t, nm(k)[:40] if t in ("object", "closure") else "", owner(k) if t in ("string", "concatenated string", "array", "object") else "")
        agg[key] += N[k * NL + isize]
    return agg
a, b = load(sys.argv[1]), load(sys.argv[2])
d = Counter({k: b[k] - a.get(k, 0) for k in b})
tot = sum(b.values()) - sum(a.values())
print(f"total self size growth {tot/2**20:.1f} MB")
for k, v in d.most_common(25):
    print(f"{v/2**20:7.2f} MB  {k}")
