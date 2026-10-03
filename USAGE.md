# gentleMonster for Gemini CLI: preview 0.4.0

**This is a preview, not a release.** It is pinned to one commit, `4de9c1c36ef6120eede3514814a840dcb4cecde3`. It is not published to any package index. Real use of it becomes the data for the next fixes (CMD-GMG6).

## 1. Install (macOS, zsh)

Before you start:
- **Node.js** must be installed (`node --version` prints a version).
- **Python 3.9 or newer**: `python3 --version`.
- **A Gemini API key**, in `GEMINI_API_KEY`.

Paste the whole block below into Terminal. It has no comment lines and no placeholders, so zsh runs it as is. It does five things:
- installs Gemini CLI **0.60.0**, the last CLI that serves `gemini-3.1-flash-lite` as asked (README, H2);
- installs the extension at the pinned commit;
- puts the Python parts in their own folder, `~/.gentlemonster/venv`;
- checks that `GEMINI_API_KEY` is set, without printing it;
- runs `gmg doctor`.

```
npm install -g @google/gemini-cli@0.60.0
gemini extensions uninstall gentlemonster ; true
gemini extensions install https://github.com/cogito5170/gentleMonster_gemini --ref 4de9c1c36ef6120eede3514814a840dcb4cecde3 --consent --skip-settings
python3 -m venv "$HOME/.gentlemonster/venv"
"$HOME/.gentlemonster/venv/bin/python3" -m pip install --quiet --upgrade pip
"$HOME/.gentlemonster/venv/bin/python3" -m pip install --quiet "$HOME/.gemini/extensions/gentlemonster[render]"
"$HOME/.gentlemonster/venv/bin/python3" -m playwright install chromium
"$HOME/.gentlemonster/venv/bin/gmg" setup
if [ -n "$GEMINI_API_KEY" ]; then echo "GEMINI_API_KEY is set"; else echo "GEMINI_API_KEY is NOT set: see USAGE.md step 1"; fi
"$HOME/.gentlemonster/venv/bin/gmg" doctor
```

If `npm install -g` fails with `EACCES`, run that one line again with `sudo` in front, then paste the block again.

If the block says `GEMINI_API_KEY is NOT set`, run `export GEMINI_API_KEY=` followed by your key, with no space. Add the same line to `~/.zshrc`, then paste the block again.

`gmg doctor` should end with every line `ok`. A `FAIL` line names what is missing.

## 2. Use

```
gemini -m gemini-3.1-flash-lite
```

Ask in your own words. For example: design a store for a brand; write cover lines; sort or measure your photos (attach them with `@` and a path); propose the next page.
- The extension's tools run every check in code. The answer may state only the verdict that the job's ledger holds.
- Everything stays on your Mac, in `~/gentleMonster_gemini_out`. That folder holds the workspace, the ledgers and `usage.jsonl` (your turns and the tools each one used).

If an answer says it was served by a model other than `gemini-3.1-flash-lite`, the CLI is not 0.60.0. Run the install block again.

## 3. Export (when you want to share what happened)

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

## 4. Where exports go

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
gemini extensions uninstall gentlemonster
rm -rf "$HOME/.gentlemonster"
```

Your data in `~/gentleMonster_gemini_out` stays until you delete it.
