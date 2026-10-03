#!/bin/bash
# A/B: the private Gemini CLI 0.62.0 + gentleMonster's portfolio MCP server + a fake model calling pf_sort every turn.
# usage: GEMINI_JS=.../bundle/gemini.js TURNS=300 MODE=tool TOOL=mcp_gm_pf_sort ARGS_LIST='[{"by":"brightest"},...]' gm_run.sh NAME PORT FIX(0|1)
# FIX=1 writes the fix with `gmg cli-settings` into a private GEMINI_CLI_HOME, as the launcher does. See bench/preview/HEAP.md.
# CMD-GMG9 S2 options: PREP_FILES=200 with TOOL=read_file (WUG's long-run workload: the CLI's built-in read_file on local files,
#   ARGS_LIST is filled in), DELAY (fake model latency, s), HEAPSNAP_AT_MB (one heap snapshot when the heap passes it),
#   EXT (another copy of this repository, e.g. with a changed tool schema).
HB=$(cd "$(dirname "$0")" && pwd); NAME=$1; PORT=$2; FIX=$3
D=$HB/out/$NAME; rm -rf $D; mkdir -p $D/home/.gemini $D/work $D/gmout
EXT=${EXT:-$(cd "$HB/../.." && pwd)}; PY=/home/user/.venv-gmg/bin/python3
cat > $D/home/.gemini/settings.json <<JSON
{"security":{"auth":{"selectedType":"gemini-api-key"}},"model":{"name":"gemini-3-flash-preview"},
 "mcpServers":{"gm":{"command":"$PY","args":["$EXT/server.py","--tools","portfolio"],"cwd":"$EXT",
   "env":{"GMG_OUT":"$D/gmout","GMG_UPSTREAM":"/home/user/gentleMonster","GMG_NO_REEXEC":"1"},"timeout":600000}}${USERX:-}}
JSON
GMG_OUT=$D/gmout GMG_UPSTREAM=/home/user/gentleMonster $PY -c "
import json,sys; sys.path.insert(0,'$EXT')
from gmg import portfolio as PF, upstream; upstream.load()
from pathlib import Path; PF.seed(json.load(open('$EXT/bench/gmg3/seed.json')), Path('$EXT/bench/gmg3'))"
EXTRA=""; if [ "$FIX" = 1 ]; then mkdir -p $D/clihome/.gemini; cp $D/home/.gemini/settings.json $D/clihome/.gemini/settings.json; HOME=$D/home GEMINI_CLI_HOME=$D/clihome PYTHONPATH=$EXT $PY -m gmg.cli cli-settings; EXTRA="GEMINI_CLI_HOME=$D/clihome"; fi
if [ -n "${PREP_FILES:-}" ]; then python3 -c "
import sys
for i in range(int(sys.argv[1])):
    open(f'$D/work/f{i:03d}.txt','w').write(''.join(f'line {j:05d} of file {i:03d} -- padding padding padding\\n' for j in range(330)))
" $PREP_FILES; export ARGS_LIST=$(python3 -c "import json,sys;print(json.dumps([{'file_path':f'$D/work/f{i:03d}.txt'} for i in range(int(sys.argv[1]))]))" $PREP_FILES); fi
python3 $HB/fakeloop.py $PORT $D/api.log > $D/fake.out 2>&1 &
FP=$!; sleep 1; cd $D/work
env HOME=$D/home $EXTRA GEMINI_API_KEY=AIzaFAKEFAKEFAKE GOOGLE_GEMINI_BASE_URL=http://127.0.0.1:$PORT NO_PROXY=127.0.0.1 no_proxy=127.0.0.1 \
  HEAPLOG=$D/heap.log HEAPSNAP_AT_MB=${HEAPSNAP_AT_MB:-0} HEAPSNAP_DIR=$D NODE_OPTIONS="--expose-gc --require $HB/heaplog.cjs ${NODE_EXTRA:-}" PATH=/opt/node22/bin:/usr/bin:/bin \
  timeout ${TMO:-1500} node $GEMINI_JS -p "start" -m gemini-3-flash-preview -o json --skip-trust --approval-mode yolo > $D/out.json 2> $D/err.txt
echo "exit=$?" > $D/exit.txt; kill $FP 2>/dev/null
