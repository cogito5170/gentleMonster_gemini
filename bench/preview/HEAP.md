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
- What remains grows linearly, as the history itself does: the request size grows from 53 KB to 544 KB over 290 turns.

To rerun one row: `GEMINI_JS=<path to the 0.62.0 bundle/gemini.js> TURNS=300 MODE=tool TOOL=mcp_gm_pf_sort ARGS_LIST='[{"by":"brightest"},{"by":"darkest"},{"by":"most_saturated"},{"by":"most_muted"},{"by":"warmest"},{"by":"coolest"},{"by":"sharpest"},{"by":"softest"},{"by":"single_subject"}]' bench/heap/gm_run.sh clihome 18985 1`, then `python3 bench/heap/analyze.py bench/heap/out/clihome`.

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

## Tests
- **`tests/test_heapfix.py`** checks the following:
  - the fix is written to the private settings when telemetry is off, and the sign-in choice is copied;
  - the user's `~/.gemini/settings.json` stays byte-identical, including when the launcher writes the fix;
  - a rerun changes nothing;
  - a private config that enables telemetry is left alone, and other keys are kept;
  - a `GEMINI_CLI_HOME` you set yourself is respected;
  - doctor flags an old launcher and settings without the fix;
  - the launcher runs the CLI in the private home;
  - the cap: small results unchanged, big ones under 4000 characters with `next` whole and the full result on disk, essentials kept.
- **`tests/test_install.py`** checks that the block installs into the private home.
- **Mutations** (`tests/mutate.py`) that the suites must catch:
  - setting not written;
  - your telemetry config overwritten;
  - your `~/.gemini` written;
  - prompts logged;
  - doctor not flagging;
  - launcher not applying the fix;
  - private home not exported;
  - results not capped;
  - `next` cut.
