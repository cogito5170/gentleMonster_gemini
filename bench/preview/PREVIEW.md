# Preview 0.4.0 (CMD-GMG6)

**Frozen preview sha, B block (Gemini CLI):** `deffd8e2f89f5572316a9ab5542d2cc48b8b95d4` (CMD-GMG9, BD-274: a disabled private telemetry block is merged, not replaced; empty-HOME rerun [`install_emptyhome_gmg9.log`](install_emptyhome_gmg9.log)); before it `b9cc1eb3853d8d57c20a5944736e3ca965922a10` (CMD-GMG8: the heap fix and the tool-result cap, [HEAP.md](HEAP.md); the B block installs into the private CLI home `~/.gentlemonster/cli-home`, and its empty-HOME rerun is [`install_emptyhome_gmg8.log`](install_emptyhome_gmg8.log)).

**Frozen preview sha, A block (agy):** `2453034609aa8d3b19f74c54431b6028ded1575e` (agy default gemini-3.8-flash-high; before it `62af1a5d85ef026e8c83036441a2369ef587f78d`) (CMD-GMG7: adds the Antigravity path, [AGY.md](AGY.md); the GMG6 record below was made at `86ae399`, and the B block was rerun at `62af1a5d85ef026e8c83036441a2369ef587f78d` with every doctor line ok). The install block in [`../../USAGE.md`](../../USAGE.md) installs exactly this commit.

## What it contains
- **The GMG4 extension** (the H1 guard, the served-model record, two MCP servers; the CLI pin is now 0.62.0), with GMG3's portfolio tools.
- **Design work from 1–42:**
  - proposals 1–4 and the H3 colour nudge;
  - the BeforeAgent turn note;
  - routing for embedded questions, adoption, page flow and widening.

  See [`../gmg3/DESIGN_AFTER.md`](../gmg3/DESIGN_AFTER.md). This is more than `cf028dc + gmg export`, which CMD-GMG6 named: it ships the tested state of the branch.
- **`gmg export`** and the use log (S2).
- **The `gentlemonster` launcher** (S6): it runs a private Gemini CLI **0.62.0** with `-m gemini-3-flash-preview`, the default model since BD-212. `GENTLEMONSTER_MODEL` overrides the model for experiments, and the extension's served-model check compares against it.
- **Earlier bench numbers are flash-lite results** (`gmg.FLASH_LITE`); none were re-run on the new model.
- **A Python 3.9 floor** (macOS ships python3 3.9), and the server restarts under `~/.gentlemonster/venv`.
- **`gmg doctor`** now also checks that Chromium starts.

## Install test (S1, S6 / D5)
[`install_emptyhome.log`](install_emptyhome.log) records the block from USAGE.md run in an **empty HOME** with interactive zsh (`zsh -i`), stdin closed. The block was run twice.
- **Private CLI.** Gemini CLI 0.62.0 installed with `npm --prefix` under `~/.gentlemonster/cli`, with no global install.
- **Extension.** It installed at the sha above, with no prompt. The launcher was copied to `~/.gentlemonster/bin`, and one `PATH` line was added to `~/.zshrc`.
- **Python parts.** The venv and its packages installed, and `gmg setup` cloned the pinned gentleMonster.
- **Key.** `GEMINI_API_KEY is set`, and the key never appears in the log.
- **`gentlemonster --version`** prints `0.62.0`, from the private CLI.
- **Every `gmg doctor` line is `ok`**, including "gemini-3-flash-preview is listed and takes generateContent" and "Gemini CLI 0.62.0 (private, used by `gentlemonster`)".
- **`gentlemonster mcp list`** shows both servers **Connected**. Management commands (mcp, extensions, skills, hooks, gemma) pass through without `-m`; this was found and fixed in the test.
- **Second run: no change.** `~/.zshrc`, the launcher's sha256, the extension ref and the private CLI version are all the same.
- **Wrong version.** With the private CLI replaced by 0.61.0, `gentlemonster` stops with one line naming the `npm install --prefix ... @0.62.0` to run (exit 1).

`playwright install chromium` could not download here: `cdn.playwright.dev` is blocked by this sandbox's network policy. Doctor still passes, because the pinned code's launcher finds the preinstalled Chromium. On a Mac, that line downloads Chromium normally.

**Not tested yet:**
- **A live session's served model (D5, D6).**
  - At 13:44 UTC on 2026-10-03, smoke runs with CLI 0.60.0, 0.61.0 and 0.62.0 (`-m gemini-3-flash-preview -p`) each got HTTP 429.
  - This key's free-tier quota for `gemini-3-flash` is **20 requests per day**, and it was already used up.
  - At 00:16 UTC on 2026-10-04, one `gentlemonster -p` turn from the B install at `b9cc1eb` got HTTP 429 again: `generate_content_free_tier_requests, limit: 20, model: gemini-3-flash`, "retry in 23h43m". The key's quota is shared with other sessions; the recording holds no response, so no served model ([`install_emptyhome_gmg8.log`](install_emptyhome_gmg8.log)).
  - Next: one turn after 2026-10-05 00:00 UTC, unless the quota is used up before then again.
- **A real macOS machine.**

## Model and CLI pin (S7)
- **models.list.** It lists `models/gemini-3-flash-preview` (version `3-flash-preview-12-2025`) with `generateContent`. This call costs nothing.
- **Which CLI versions serve it as asked** (from the source of each published bundle):
  - In 0.60.0, 0.61.0 and 0.62.0, `getBackendModelMappings()` never names `gemini-3-flash-preview`.
  - The model config redirects it only when `hasAccessToPreview` is false; the target is `gemini-3.5-flash` in 0.60, and the latest flash, `gemini-3.8-flash`, in 0.61/0.62.
  - API-key and Vertex auth always call `setHasAccessToPreviewModel(true)`.
  - So all three serve it as asked. 0.62.0 is the newest stable CLI (`latest` dist-tag), so it is the pin.
- **Not checked live yet** (quota, above). The served-model record would show any change.
- **The free tier will not carry real use.** It allows 20 requests per day for this model. USAGE.md says a billing-enabled key is needed for real use.

## Evaluate, then learn (S4)
For each export batch that the user pushes to `gm-photos/usage/`:
1. **Read** the batch.
2. **Commit** the expected tool path and expected state per turn (`replay.check_spec` conditions), before any run.
3. **Replay** the user turns at the frozen preview sha with `bench/gmg3/replay.py eval --set`. Attached photos are used only if the user put them in `gm-photos`; otherwise they are stand-ins, marked as such.
4. **Score:** path, state, re-asks, gates and tokens.
5. **Post the score** on baseline#16.
6. **Only then tune** on that batch. A batch used for tuning is never scored again; the next score needs a new batch.
