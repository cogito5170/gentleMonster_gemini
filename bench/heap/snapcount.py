import json, sys
from collections import Counter
for p in sys.argv[1:]:
    snap = json.load(open(p))
    meta = snap["snapshot"]["meta"]; nf = meta["node_fields"]; ntypes = meta["node_types"][0]
    N, S = snap["nodes"], snap["strings"]; NL = len(nf)
    it, iname, isize = nf.index("type"), nf.index("name"), nf.index("self_size")
    c = Counter(); strs = Counter()
    for k in range(len(N) // NL):
        t = ntypes[N[k * NL + it]]; nm = S[N[k * NL + iname]]
        if t == "object" and nm in ("SchemaEnv", "Ajv", "ValueScope", "LogRecordImpl", "SpanImpl", "ApiRequestEvent", "ApiResponseEvent", "ToolCallEvent"):
            c[nm] += 1
        if t == "string" and nm.startswith('const schema') or (t == "string" and "validate" in nm[:40] and "errors" in nm[:400]):
            strs[nm[:160]] += 1
    print(p.split("/")[-2], dict(c))
    for s, n in strs.most_common(4): print("   ", n, repr(s))
