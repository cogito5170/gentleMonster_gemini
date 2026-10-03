# gentleMonster in Antigravity CLI (`agy`): CMD-GMG7

The same tools run in agy, signed in with the user's Google account. There is no API key and no Gemini API quota.
- **The decision code is not forked.** agy starts the extension's own `server.py`, from a checkout at the pinned commit, as two stdio MCP servers.
- **This session never ran the real agy.** It has no Google sign-in, and agy cannot keep a login in a Linux container (antigravity-cli#479). So:
  - everything was built and tested here against a **fake agy**;
  - the sign-in and the live turn are the user's steps on the Mac (USAGE.md, A).

## What it consists of
| piece | what it does |
|---|---|
| `~/gentlemonster/.agents/mcp_config.json` | `gentlemonster` (store tools) and `gentlemonster-portfolio` (portfolio tools); each runs `~/.gentlemonster/venv/bin/python3 ~/.gentlemonster/ext/server.py --tools ...` with `GENTLEMONSTER_HOST=agy` |
| `~/gentlemonster/.agents/rules/gentlemonster.md` | GEMINI.md's instructions plus one agy line (see "Rules, not a skill" below) |
| `gmg agy-setup` | writes both files only when they differ, so a rerun changes nothing; the launcher runs it on every start |
| `gentlemonster-agy` | starts agy in `~/gentlemonster` with `--model` = agy's own name for Gemini 3 Flash; passes other arguments; `--check` runs one headless turn |
| `gmg agy-model` | picks that name from `agy models --output-format json`; **if agy has none, it stops, lists the models agy offers, and leaves the choice to the user** (`GENTLEMONSTER_AGY_MODEL`) |
| `gmg agy-served` | reads the served model from an `agy -p --output-format json` run, records it (source `agy`), and names a refused tool call |
| served-model marking | under agy, every tool result says "served model unknown" until a `--check` has recorded a model in the last 12 h; a different model is warned |
| `gmg doctor --host agy` | asks for no key; checks that agy is on PATH and that the workspace files are this extension's |

**Rules, not a skill.** GEMINI.md is a routing table that must apply on every turn, which is what a rule is. Skills load on demand.
- agy's CHANGELOG documents rule files (user and workspace rules with a 20,000-token budget; `rules/` and `AGENTS.md`/`GEMINI.md` under `~/.gemini/config`) and `.agents/` customization folders.
- A workspace rule keeps the user's global config untouched.

## Facts, with sources
"Verified" means stated in agy's own repository: [google-antigravity/antigravity-cli](https://github.com/google-antigravity/antigravity-cli), README and CHANGELOG, read at 1.2.16 on 2026-10-03. antigravity.google (the docs) is blocked from this session.

| fact | status |
|---|---|
| Sign-in: system keyring, otherwise Google Sign-In in the browser; `/logout` signs out | verified (README) |
| Install: `curl -fsSL https://antigravity.google/cli/install.sh \| bash` | verified (README) |
| Install location (the block adds `~/.local/bin` to `PATH`) | **assumption** |
| `--model <slug>`; `agy models --output-format json` lists the slugs; in print mode an unknown `--model` fails and lists the models | verified (CHANGELOG 1.x: "stable, user-facing model slugs", `models` subcommand, print-mode hard fail) |
| agy's slug for `gemini-3-flash-preview` | **unknown**: `gentlemonster-agy` finds it at run time, or stops and asks |
| `-p`, `--output-format text\|json\|stream-json`; `AGY_ERROR` line and exit 3 on model/agent failure; `denied_actions` in JSON when a tool is refused | verified (CHANGELOG) |
| a `model` field in the json/stream-json output | **assumption**. The status-line payload has `.model.display_name` (verified, examples/statusline). `agy-served` reads any `model` string or object. |
| MCP: stdio servers in `mcp_config.json` (user level `~/.gemini/config/mcp_config.json`, `agy mcp add/list/remove`) | verified (CHANGELOG) |
| a **workspace** `.agents/mcp_config.json` | **assumption** (`.agents/` holds skills, rules, hooks.json, agents per the CHANGELOG; the MCP file there is not named). If `--check` calls no gentleMonster tool, `agy mcp list` settles it. |
| workspace rules in `.agents/rules/` | **assumption** (workspace rules exist; the folder name follows `.agents/skills/`) |
| headless runs may refuse tool calls not yet permitted (`denied_actions`) | verified; whether an MCP call needs one interactive approval first is **unknown** |

## Quota (S3)
- **Verified:**
  - `agy -p "/usage"` and `"/quota"` print quota and reset times without spending any.
  - The status line can show quota usage.
  - When the plan quota runs out, agy can use AI credits ("Use AI Credits" / G1 credits). Otherwise it says "Your AI credits balance is too low to continue."
  - agy stops at once on a daily cap instead of retrying.
- **Unknown here:** requests per day or minute per model for a Google account. They are not in the repository, and the docs site is blocked. The Mac run's `agy -p "/usage"`, the first line the block prints after sign-in, will show them.
- **What the extension shows.** The MCP server never sees agy's quota. agy reports limits itself, and `gentlemonster-agy` does not hide them.

## Fallback: Gemini CLI with Login with Google (S5)
- **Install.** The B block plus `env -u GEMINI_API_KEY gentlemonster`, then choose "Login with Google". This uses the Code Assist free tier, not the API key.
- **Which model serves** (CLI 0.62.0, from source):
  - With OAuth, `hasAccessToPreviewModel` is set by `refreshUserQuota()`: true only if the account's quota lists a preview-model bucket.
  - With access, `gemini-3-flash-preview` is served as asked.
  - Without access, the model config redirects it to the latest Flash: `gemini-3.8-flash` when `LATEST_FLASH_GA_LAUNCHED` is on, else `gemini-3.5-flash`.
  - So the result depends on the account. The AfterAgent hook records the served model, and every tool result says so when it differs.
- **Not verified live.**

## Tests
- **`tests/test_agy.py`** uses a fake agy on PATH. It covers:
  - the generated files: paths under `$HOME` only, no key or token, rerun-safe;
  - the model pick, including the stop when agy has no Gemini 3 Flash;
  - served-model parsing for the assumed json and stream-json shapes, plus unknown and refused cases;
  - the warning under agy;
  - the launcher: workspace, `--model`, argument pass-through, user override, the no-agy line, `--check`;
  - `doctor --host agy`;
  - the install block.
- **Mutations** in `tests/mutate.py`: MCP server path wrong, instructions file missing, `--model` dropped, served model not checked or not recorded, unknown not marked, flash-lite taken for flash, a refused call passing, a silent model choice.
- **[`install_agy_emptyhome.log`](install_agy_emptyhome.log)** records the A block in an empty HOME with zsh, run twice:
  - the second run changed nothing;
  - doctor is all ok;
  - `--check` printed the (fake) served model;
  - both MCP servers started exactly as the config says, with 8 tools each.

**The user's steps (not done here):** the Google sign-in, the first real `agy -p "/usage"`, `agy models`, and `gentlemonster-agy --check` against the real agy.
