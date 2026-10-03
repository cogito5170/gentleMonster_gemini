# Preview 0.4.0 (CMD-GMG6)

**Frozen preview sha:** `4de9c1c36ef6120eede3514814a840dcb4cecde3`. The install block in [`../../USAGE.md`](../../USAGE.md) installs exactly this commit.

## What it contains
- **The GMG4 extension** (the H1 guard, the served-model record, the 0.60.0 pin, two MCP servers), with GMG3's portfolio tools.
- **Design work from 1–42:**
  - proposals 1–4 and the H3 colour nudge;
  - the BeforeAgent turn note;
  - routing for embedded questions, adoption, page flow and widening.

  See [`../gmg3/DESIGN_AFTER.md`](../gmg3/DESIGN_AFTER.md). This is more than `cf028dc + gmg export`, which CMD-GMG6 named: it ships the tested state of the branch.
- **`gmg export`** and the use log (S2).
- **A Python 3.9 floor** (macOS ships python3 3.9), and the server restarts under `~/.gentlemonster/venv`.
- **`gmg doctor`** now also checks that Chromium starts.

## Install test (S1)
[`install_emptyhome.log`](install_emptyhome.log) records the block from USAGE.md run in an **empty HOME** with interactive zsh (`zsh -i`), stdin closed:
- npm installed Gemini CLI 0.60.0;
- the extension installed at the sha above, with no prompt;
- the venv and its packages installed, and `gmg setup` cloned the pinned gentleMonster;
- `GEMINI_API_KEY is set`, and the key never appears in the log;
- **every `gmg doctor` line is `ok`**;
- `gemini mcp list` shows both servers **Connected**.

`playwright install chromium` could not download here: `cdn.playwright.dev` is blocked by this sandbox's network policy. Doctor still passes, because the pinned code's launcher finds the preinstalled Chromium. On a Mac, that line downloads Chromium normally.

**Not tested:**
- a real macOS machine;
- a live CLI turn after install, because the free-tier daily quota was used up on 2026-10-03.

## Evaluate, then learn (S4)
For each export batch that the user pushes to `gm-photos/usage/`:
1. **Read** the batch.
2. **Commit** the expected tool path and expected state per turn (`replay.check_spec` conditions), before any run.
3. **Replay** the user turns at the frozen preview sha with `bench/gmg3/replay.py eval --set`. Attached photos are used only if the user put them in `gm-photos`; otherwise they are stand-ins, marked as such.
4. **Score:** path, state, re-asks, gates and tokens.
5. **Post the score** on baseline#16.
6. **Only then tune** on that batch. A batch used for tuning is never scored again; the next score needs a new batch.
