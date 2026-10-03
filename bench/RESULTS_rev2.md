# Results -- CMD-GMG2 rev 2: the Gemini CLI extension, flash-lite choosing every tool call

Protocol: [`PROTOCOL_rev2.md`](PROTOCOL_rev2.md), pre-registered at `5b09970`, plus three amendments, each written before the next run. The briefs and the Opus references are the same as rev 1 (pinned at `7b1b240` and `b79fcff`).
Raw data: [`results_rev2/metrics.json`](results_rev2/metrics.json). Per run: `D_<id>[.runN]/transcript.json`, the ledger and the job files.

## 1. Final run (run 4, code frozen) against the Opus reference

| | A · Opus (by hand) | **D · extension + flash-lite (run 4)** | rev 1 C · pipeline + flash-lite | rev 1 B · gentleMonster as is + flash-lite |
|---|---|---|---|---|
| gate passed (spec.check) | 6/6 | **6/6** | 5/6 | 3/6 |
| spec completeness | 72/72 | **72/72** | 60/72 | 36/72 |
| re-asks (proxy) | 0 | 4 | 3 | 10 |
| off-list tool calls | – | **0** | – | – |
| tool calls / model turns | – | 34 / 40 | – | – |
| median latency | n/a | 14.5 s (two runs include a quota wait) | 11.1 s | 16.5 s |
| Gemini calls (HTTP) | 0 | 42 | 45 | 16 |
| tokens | – | 164,163 (prompt 156,065 · output 8,098) | 22,549 | 75,535 |
| model the responses named | – | gemini-3.1-flash-lite on every call | same | same |
| answer states only the ledger's verdict | – | 6/6 (hook would deny 0) | – | – |

Run 4 by brief:

| brief | state | re-asks | tool calls | turns | tokens | s | what was re-asked / repaired |
|---|---|---|---|---|---|---|---|
| b1 | DONE | 1 | 6 | 7 | 30,890 | 13.0 | a stop caption was not first person |
| b2 | DONE | 0 | 5 | 6 | 22,565 | 9.7 | – |
| b3 | DONE | 0 | 5 | 6 | 22,609 | 68.6* | – |
| b4 | DONE | 1 | 6 | 7 | 28,596 | 11.0 | two near-identical whites in the palette |
| b5 | DONE | 0 | 5 | 6 | 24,240 | 43.5* | – |
| b6 | DONE | 2 | 7 | 8 | 35,263 | 16.0 | near-identical colours, a caption; code put the round basin back (REPAIR) on the 8 m plan |

\* includes a per-minute quota (HTTP 429) wait.

## 2. All runs (nothing hidden)

| run | code | DONE | complete | re-asks | off-list | tokens | what the run showed |
|---|---|---|---|---|---|---|---|
| 1 | `ab2bae9` | 6/6 | 72/72 | 5 | 0 | 168,647 | **b3 and b4 lost their brand; b6 lost its product.** Cause: the brand gate checked the brand against text the agent itself passed. The metrics did not see it |
| 2 | `425004e` | 5/6 | 60/72 | 7 | 2 | 209,947 | **b6 NEEDS_REVIEW after 13 calls.** A box replaced the round basin and the route came 0.12 m from it. The geometry repair was missing, and the result did not point to the step that fixes it |
| 3 | `4b5d09c` | 6/6 | 72/72 | 2 | 0 | 146,756 | brands and products right; the `why` headlines were cut by code into fragments |
| 4 | `a7602c4` | 6/6 | 72/72 | 4 | 0 | 164,163 | final; see §3 for the defect it still shows |
| E | `4b5d09c` | 1/1 | – | 0 | 0 | 92,519 (CLI count) | **real Gemini CLI 0.62.0 on b1**: DONE in 22 s, five gm_* calls in order, the `say` line quoted |

- Rev 2 total for arm D: 24 runs, 171 Gemini calls, 689,513 tokens.
- Arm E: 6 CLI requests, 92,519 tokens, 56,827 of them cached.

## 3. Where D still falls short of Opus, and why

| # | where | example | cause | proposal (not done) |
|---|---|---|---|---|
| H1 | **a placeholder became the brand** | b6 run 4: brand `(none named)` is printed on the page | my harness prompt writes "Brand: (none named)"; flash-lite copied it; the code keeps any named brand (the run-2 fix) and has no placeholder guard | treat parenthesised or "none" brands as empty; make the prompt line empty when there is no brand |
| H2 | **the CLI swaps the model** | arm E ran `gemini-3.5-flash-lite`, not 3.1 | Gemini CLI 0.62 maps `gemini-3.1-flash-lite` to the latest flash-lite when the account has GA access (`hasLatestFlashLiteGAAccess`) | user decision: accept 3.5, pin an older CLI, or find a setting that holds 3.1 (not found) |
| H3 | **tokens** | about 27k per job, against 3.7k for the rev-1 pipeline | function calling resends the growing history and every `next` offer each turn | slimmer offers (send role options only once); result payloads without repetition |
| H4 | layout novelty, generic wording, "details" filler | as in rev 1 G1, G3, G5 | four plans; flash-lite's idiom ("ethereal", "sanctuary"); code pads to four materials | as in rev 1 |
| H5 | the hook in the real CLI | the AfterAgent hook is configured and tested as a script; whether CLI 0.62 ran it in arm E is **not verified** (the answer made no false claim, so it had nothing to deny) | – | one CLI run with `--debug`, or a forced false claim |
| H6 | no PDF in the real CLI | arm E: `job.json` and `synopsis.md` only | the extension's server ran on a `python3` without the draw dependencies; the note says so | doctor-style first-run message, or a venv bootstrap like well_used_gemini's `setup` |

## 4. Blind pairs (the user judges)

- [`blind_rev2/`](blind_rev2/): A against D run 4. Each brief has `X/` and `Y/` (`synopsis.md` and `layout_preview.png`) and `brief.txt`.
- The pre-registered salted rule gives b1-b5 X = D and b6 X = A. The key is in `key.json`; do not open it before judging.
- Not fully blind: D's `why` lines start with code-measured facts with bracketed labels. And b6's D side shows the H1 defect.
- The rev-1 pairs (A against C) stay in [`blind/`](blind/).
