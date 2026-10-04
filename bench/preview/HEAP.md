# The Gemini CLI heap fix on path B (CMD-GMG8, BD-259)

This ports well_used_gemini's fix for "JavaScript heap out of memory" (WUG HEAP.md, heapbench at `2b89ee3`) to the `gentlemonster` launcher. That launcher runs a private Gemini CLI 0.62.0.

## The bug (WUG's root cause, adopted)
- Telemetry is off by default in Gemini CLI 0.62.0.
- With it off, `bufferTelemetryEvent` still pushes, for every model request, a closure that holds the whole request JSON into `telemetryBuffer`.
- That buffer is drained only when telemetry is initialized, which never happens. So each turn keeps a copy of the full history, and the heap grows as turns².

The fix is `{"telemetry": {"enabled": true, "target": "local", "outfile": "/dev/null", "logPrompts": false}}`. Telemetry is initialized, so the buffer is drained, but nothing is sent or kept.

## Where the setting goes (S1)
- **The private CLI's own home.** The launcher now runs the CLI with `GEMINI_CLI_HOME=~/.gentlemonster/cli-home`, unless you set `GEMINI_CLI_HOME` yourself. Gemini CLI 0.62 then keeps its settings, extensions and sign-in in `~/.gentlemonster/cli-home/.gemini/`.
- **Written when needed.** Before each start, the launcher runs `gmg cli-settings`. It writes the block into that settings file only when the file does not already enable telemetry.
  - A config there with `telemetry.enabled: true` is left exactly as it is.
  - Other keys in the file are kept.
- **The first time,** the sign-in choice (`security.auth.selectedType`) is copied from your `~/.gemini/settings.json`. That file is only read.
- **Never touched:** your own `~/.gemini`, and your own `gemini`.
- **Doctor.** `gmg doctor` (not `--host agy`) has one line for it:
  - it fails when the installed launcher predates the fix;
  - it fails when the private settings do not enable telemetry;
  - otherwise it says whether the setting is ours or yours.
- **The install block** now installs the extension into the private home. The README tells anyone who installed before to paste the block again.

### A route that did not work: system settings
- The first try put the block in a file named by `GEMINI_CLI_SYSTEM_SETTINGS_PATH` (and then `GEMINI_CLI_SYSTEM_DEFAULTS_PATH`). The aim was to leave every user file alone.
- Measured, it changed nothing: 534.9 KB/turn against 533.8 (`fixed` in [`../heap/ab.txt`](../heap/ab.txt)).
- The CLI logged "Security Warning: Skipping ... Parent directory ... is insecure". In 0.62, system settings are read only when the file and every parent directory are owned by root and not writable by group or others (`checkPosixStatsSecurity`). That needs sudo, which the install block does not use.
- So the private home is the route.
- A probe with `model.name` in `$GEMINI_CLI_HOME/.gemini/settings.json` confirmed that the CLI reads that file.

## Measurement
- **Harness.** WUG's heapbench, copied to [`../heap/`](../heap/):
  - `fakeloop.py` is a fake Gemini API, reached through `GOOGLE_GEMINI_BASE_URL`. It asks for one tool call per turn.
  - `heaplog.cjs` logs the heap after a forced GC, once per second.
  - `analyze.py` fits the slope.
- **The tools.** gentleMonster's own portfolio MCP server, on a seeded workspace, calls `pf_sort` with `by` cycling through 9 values. Identical calls are stopped by the CLI's loop detection, so the arguments must vary. The median tool result is 2168 characters.
- **No real Gemini call** was made: the key is fake and the API is local.

| run | settings | turns | heap (MB) | slope |
|---|---|---|---|---|
| default | none (telemetry off) | 294 | 104 → 236 | **533.8 KB/turn** |
| default2 | none, repeated | 290 | 102 → 232 | 532.7 KB/turn |
| **clihome** | the fix in the private `GEMINI_CLI_HOME`, written by `gmg cli-settings` (what ships) | 290 | 104 → 132 | **79.5 KB/turn** |
| userfix | the fix in the user's `~/.gemini/settings.json` (control) | 144 | 104 → 118 | 55.5 KB/turn |
| fixed | the fix in a system settings file (not root-owned) | 292 | 104 → 234 | 534.9 KB/turn: no effect |

- The shipped route cuts the heap growth by about **6.7×** (533.8 → 79.5 KB/turn).
- What remains is explained below (CMD-GMG9): mostly the run's length, and Gemini CLI compiling a new parameter validator for every MCP tool call.

To rerun one row: `GEMINI_JS=<path to the 0.62.0 bundle/gemini.js> TURNS=300 MODE=tool TOOL=mcp_gm_pf_sort ARGS_LIST='[{"by":"brightest"},{"by":"darkest"},{"by":"most_saturated"},{"by":"most_muted"},{"by":"warmest"},{"by":"coolest"},{"by":"sharpest"},{"by":"softest"},{"by":"single_subject"}]' bench/heap/gm_run.sh clihome 18985 1`, then `python3 bench/heap/analyze.py bench/heap/out/clihome`.

## The residual, explained (CMD-GMG9 S2)
**The question.** With the fix, this workload measured 79.5 KB/turn. WUG measured 3.9 KB/turn in a long run. Numbers are in [`../heap/residual.txt`](../heap/residual.txt). No Gemini request was made: the model is fake.

1. **Most of the gap from 79.5 to ~30 is the fit window; part is run-to-run noise.** (Corrected after BD-274.)
   - GMG8 fitted turns 58–290 of a 290-turn run, and the early turns grow fastest: 84–87 KB/turn in turns 0–100 and 48–51 in turns 100–300.
   - The same workload over 1,000 turns fits **29.6 and 34.3 KB/turn** (two runs); WUG's own 300-turn runs gave 30 KB/turn.
   - Fitted over the same turns 58–290, those two runs give 71.4 and 63.2 against GMG8's 79.5. So a 230-turn window varies by roughly ±10 KB/turn between runs.
   - The logs behind every slope are in [`../heap/runs/`](../heap/runs/) (`python3 bench/heap/analyze.py bench/heap/runs/NAME`).
2. **This harness reproduces WUG's number.** WUG's long-run workload on this harness gave **−4.2 KB/turn** over 2,829 turns (103 → 116 MB). That workload is the CLI's built-in `read_file` on 200 local files, 16,938 characters per result, with a 0.4 s model delay. So neither the harness nor the private-home route is the difference; the workload is.
3. **What holds the memory.** I compared heap snapshots at turn 133 and turn 745 of the pf_sort run. Self size grew by 28.0 MB, or 46 KB/turn:
   - **Parameter validators, about 2 per turn.** `SchemaEnv` objects went from 280 to 1,502. 1,490 of them hold the pf_sort parameter schema, with the `wait_for_previous` property the CLI adds. Their generated code takes 8.6 MB: validator source strings, `ValueScope` and `ValueScopeName` objects, and `_Code`. Most of the 8.8 MB of compiled code is probably theirs too, since every compile creates a new function.
   - **The current request,** 6.2 MB. Two holders, the stream generator and its listener, keep the latest request JSON, and it grows with the history.
   - **Telemetry log records,** 1.1 MB. Their count fell from 358 to 235, so they are bounded.
4. **Why a validator is compiled on every call** (Gemini CLI 0.62.0 core, `BaseDeclarativeTool` and `SchemaValidator`):
   - The `schema` getter calls `getSchema()`, which returns a new object each time: `addWaitForPreviousParameter` spreads the schema and adds `wait_for_previous`.
   - `validateToolParams` passes that new object to `SchemaValidator.validate`, which calls `ajv.compile(schema)` on a shared Ajv instance.
   - Ajv caches compiled schemas by object identity. So every call compiles a new validator, and the cache keeps all of them.
   - The built-in `read_file` holds only 13 SchemaEnv objects at turn 404, so built-in tools escape this. I did not trace why.
   - An almost empty schema (`pf_show`) still leaks: 1,670 SchemaEnv objects at turn 828, and 25.2 KB/turn.
5. **Causal check.** A scratch copy gave pf_sort's schema an `"$id"`. Ajv then refuses to compile a second schema with the same id, and the CLI logs "Skipping parameter validation" (1,999 times in 1,000 turns).
   - The slope fell from 29.6–34.3 to **5.7 KB/turn**, WUG's level.
   - SchemaEnv objects still pile up (984 at turn 486), but they are never compiled, and the compiled validators are what costs memory.

**Is it ours?** No. It is the CLI's validator cache, and any MCP tool triggers it. A larger parameter schema costs more per call: about 30 KB/turn for pf_sort against 25 for pf_show.

**Not shipped: the `$id` mitigation.** It turns off the CLI's parameter check for our tools. Our servers check every argument anyway. But whether the Gemini API accepts `$id` in a function declaration is unverified, and checking it would take a live request.

**What it means in practice:**
- At about 30 KB/turn, a session reaches 1 GB of heap after roughly 30,000 tool calls. Before the fix, the growth was quadratic.
- USAGE.md now says so: in a very long session, `/quit` and start again with `gentlemonster --resume latest`.

**Upstream issue text:**

> **Title:** MCP tool calls compile a new Ajv validator on every call (unbounded heap growth)
>
> In 0.62.0, the `BaseDeclarativeTool.schema` getter returns a new object each time (`addWaitForPreviousParameter` spreads the parameter schema).
> `validateToolParams` passes it to `SchemaValidator.validate`, which calls `ajv.compile(schema)` on a shared Ajv instance whose cache is keyed by schema object.
> Each MCP tool call therefore compiles and retains about two new validators: 1,222 new `SchemaEnv` objects over 612 calls of one tool, and about 25–30 KB/turn of retained heap with telemetry enabled.
> Building the schema once, or caching validators by tool name or by a schema hash, would stop it.

## Tool results (S2)
- **The cap.** Every result from the extension's MCP servers (`gmg/ext_mcp.py`, both `store` and `portfolio`) is now capped at **4000 characters**, as in WUG.
- **When a result is over the cap:**
  - the whole result is written to `~/gentleMonster_gemini_out/results/<result_id>.json`;
  - long lists keep their last 10 items, and long strings keep 800 characters;
  - a `truncated` field gives the result id, the full size and what was cut.
- **When that is still too big,** only the essentials are kept: `ok`, `next`, `problems`, `say`, `verdict`, `job`, `served`, `unmeasured_images`.
- **The closed `next` list is never cut.**
- **No image bytes.** The tools never returned image bytes. A photo is passed as a path, and results carry only measured values (brightness, colours, sizes …). Every MCP result is a single `text` content item.

## The agy path (S3)
- `gentlemonster-agy` runs the Antigravity CLI, not Gemini CLI, so this bug and this fix do not apply to it.
- The agy launcher, its workspace config and `gmg doctor --host agy` are unchanged.
- The doctor line for the heap fix is skipped with `--host agy`.

## Install test
[`install_emptyhome_gmg8.log`](install_emptyhome_gmg8.log) records the B block at `b9cc1eb3853d8d57c20a5944736e3ca965922a10`. It was run twice in an empty HOME with `zsh -i`, stdin closed.
- **Extension.** It is in `~/.gentlemonster/cli-home/.gemini/extensions/gentlemonster`, at that ref.
- **The fix.** The private `settings.json` holds exactly the block above.
- **Doctor.** Every `gmg doctor` line is `ok`, including "heap fix: the private Gemini CLI keeps telemetry local and discarded, with no prompts logged".
- **The second run changed nothing.**
- **MCP servers.** `gentlemonster mcp list` shows both servers **Connected** from the private home.
- **No `~/.gemini` in HOME after both runs.** The first run, at `d0854c8`, did leave one: `gmg doctor` ran the private CLI's `--version` without `GEMINI_CLI_HOME`, and the CLI wrote `projects.json` temp files into `~/.gemini`. That is fixed in `b9cc1eb`, with a test and a mutation.
- **Side effect: three notices on stderr.** With telemetry enabled, the CLI prints them to stderr only, never stdout: a clamped export timeout, a deprecated `metricReader` option and `[TELEMETRY] GEMINI_MEMORY_MONITOR_INTERVAL`. Nothing is exported: the target is local and the file is `/dev/null`.
- **Not tested here: a real Mac, and a live model turn.** No Gemini request was spent on this directive.

## Tests
- **`tests/test_heapfix.py`** checks the following:
  - the fix is written to the private settings when telemetry is off, and the sign-in choice is copied;
  - the user's `~/.gemini/settings.json` stays byte-identical, including when the launcher writes the fix;
  - a rerun changes nothing;
  - a private config that enables telemetry is left alone, and other keys are kept;
  - a `GEMINI_CLI_HOME` you set yourself is respected;
  - doctor flags an old launcher and settings without the fix, and runs the private CLI in its own home;
  - the launcher runs the CLI in the private home;
  - the cap: small results unchanged, big ones under 4000 characters with `next` whole and the full result on disk, essentials kept.
- **`tests/test_install.py`** checks that the block installs into the private home.
- **Mutations** (`tests/mutate.py`) that the suites must catch:
  - setting not written;
  - your telemetry config overwritten;
  - your `~/.gemini` written;
  - prompts logged;
  - doctor not flagging;
  - doctor running the private CLI in your home;
  - launcher not applying the fix;
  - private home not exported;
  - results not capped;
  - `next` cut.
