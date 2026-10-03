# gentleMonster for Gemini: preview 0.4.0

**This is a preview, not a release.** It is pinned to one commit. It is not published to any package index. Real use of it becomes the data for the next fixes (CMD-GMG6).

There are two ways to run it on a Mac. Both use the same tools, and both keep your work in `~/gentleMonster_gemini_out`.

| | needs | command |
|---|---|---|
| **A. Antigravity CLI** (`agy`, BD-229) | your Google sign-in; no API key, no Gemini API quota | `gentlemonster-agy` |
| **B. Gemini CLI** (GMG6) | a Gemini API key (free tier: 20 requests per day), **or** Login with Google | `gentlemonster` |

## A. Antigravity CLI

Paste the whole block into Terminal (zsh). It has no comment lines and no placeholders, and it is safe to run again. It does the following:
- installs `agy` from Google's install script, if it is missing;
- asks agy for your quota with `agy -p "/usage"`. **The first time, agy opens the Google sign-in page in your browser**: sign in, and the block continues. This step spends no quota;
- puts the gentleMonster tools at the pinned commit in `~/.gentlemonster`;
- sets up the folder `~/gentlemonster` as the agy workspace. Its `.agents/` holds the MCP servers and the rules. Your global agy settings are not touched;
- runs `gentlemonster-agy --check`: one headless turn that calls a gentleMonster tool and prints the model that served it. **This step is yours.** It needs your sign-in, so it was not run when the preview was built.

```
INSTALL_BLOCK_AGY
```

Then type **`gentlemonster-agy`**.
- **Model.** It starts agy in `~/gentlemonster` with `--model` set to agy's own name for **Gemini 3 Flash** (`gemini-3-flash-preview`), taken from `agy models`.
- **If agy does not offer that model,** it stops and lists the models agy does offer. Choosing one is your decision: `export GENTLEMONSTER_AGY_MODEL=` followed by its name, then run it again.
- **Served model.** An interactive agy session does not tell the extension which model served it, so tool results say "served model unknown". `gentlemonster-agy --check` runs one turn and records it.
- **Quota.** `agy -p "/usage"` or `"/quota"` shows it without spending any. When the plan quota runs out, agy says so itself.

What the preview could not check without your Mac:
- that agy reads the MCP servers from `~/gentlemonster/.agents/mcp_config.json` and the rules from `.agents/rules/`. If `--check` reports no gentleMonster tool called, run `agy mcp list` and tell baseline;
- where agy installs itself. The block adds `~/.local/bin` to `PATH`.

## B. Gemini CLI

**With Login with Google (no API key).** Run the B install block below. Then start with `env -u GEMINI_API_KEY gentlemonster` and choose **Login with Google** when the CLI asks.
- This uses the Code Assist free tier, not the API key's quota.
- **Model.** CLI 0.62.0 serves `gemini-3-flash-preview` as asked only when your account has preview-model access. Otherwise it switches to the latest Gemini Flash. Every tool result says so when that happens.
- **Checks.** `"$HOME/.gentlemonster/venv/bin/gmg" doctor --host google` checks everything except the key.

### B1. Install (macOS, zsh)

Before you start:
- **Node.js** must be installed (`node --version` prints a version).
- **Python 3.9 or newer**: `python3 --version`.
- **A Gemini API key**, in `GEMINI_API_KEY`.
- **A billing-enabled key, for real use.** The free tier allows only **20 requests per day** for `gemini-3-flash-preview`, and one store job took about 7 requests in the flash-lite bench (more when the model is asked again). When the quota runs out, the CLI stops with a quota error until the next day.

Paste the whole block below into Terminal. It has no comment lines and no placeholders, so zsh runs it as is. It does five things:
- installs a **private** Gemini CLI **0.62.0** under `~/.gentlemonster`. Your own `gemini`, if you have one, is not touched, and no `sudo` is needed. 0.62.0 serves `gemini-3-flash-preview` as asked (README, "Which model serves");
- installs the extension at the pinned commit, and the command **`gentlemonster`**. Its folder is added to `PATH` with one line in `~/.zshrc`, added once;
- puts the Python parts in their own folder, `~/.gentlemonster/venv`;
- checks that `GEMINI_API_KEY` is set, without printing it;
- runs `gmg doctor`.

```
INSTALL_BLOCK
```

Running the block again is safe. It reinstalls the same pinned versions and does not add the `PATH` line twice.

For the API key: if the block says `GEMINI_API_KEY is NOT set`, run `export GEMINI_API_KEY=` followed by your key, with no space. Add the same line to `~/.zshrc`, then paste the block again.

`gmg doctor` should end with every line `ok`. A `FAIL` line names what is missing.

### B2. Use

```
gentlemonster
```

`gentlemonster` always starts the private Gemini CLI 0.62.0 with `gemini-3-flash-preview`; you never type the model. (For an experiment, `GENTLEMONSTER_MODEL=gemini-3.1-flash-lite gentlemonster` asks for another model.) Any other arguments pass through, for example `gentlemonster -p "..."`. If the private CLI is not exactly 0.62.0, or the extension is missing, it stops with one line that says what to run.

Ask in your own words. For example: design a store for a brand; write cover lines; sort or measure your photos (attach them with `@` and a path); propose the next page.
- The extension's tools run every check in code. The answer may state only the verdict that the job's ledger holds.
- Everything stays on your Mac, in `~/gentleMonster_gemini_out`. That folder holds the workspace, the ledgers and `usage.jsonl` (your turns and the tools each one used).

## Export (when you want to share what happened)

```
"$HOME/.gentlemonster/venv/bin/gmg" export
```

This writes one file per session into `~/gentleMonster_gemini_out/export/`. Each line is one of your turns. It holds:
- what you wrote;
- the tools called, in order;
- refusals and re-asks;
- the served model;
- the answer.

In those files:
- an attached photo becomes its sha256 and measured values (brightness, colours …), never the image;
- other file paths become `[path]`;
- key-like strings become `***`.

**Read the files before sharing them.** Delete any line you do not want to share.

## Where exports go

Only into the **private** repository `cogito5170/gm-photos`, folder `usage/`. Never into a public repository, an issue or a comment.

Pushing is your action:

```
cd "$HOME/gm-photos"
mkdir -p usage
cp "$HOME/gentleMonster_gemini_out/export/"*.jsonl usage/
git add usage
git commit -m "usage export"
git push
```

(This assumes a clone of `gm-photos` in your home folder.)

Each batch is scored at the frozen commit before anything is tuned on it. A batch used for tuning is never scored again.

## Remove

```
"$HOME/.gentlemonster/cli/node_modules/.bin/gemini" extensions uninstall gentlemonster
rm -rf "$HOME/.gentlemonster" "$HOME/gentlemonster/.agents"
```

Then delete the `.gentlemonster/bin` line from `~/.zshrc`. Your data in `~/gentleMonster_gemini_out` stays until you delete it.
