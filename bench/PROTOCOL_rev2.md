# Protocol addendum -- CMD-GMG2 rev 2 (pre-registered 2026-10-03, before any rev-2 run)

Same briefs (`briefs.json`, `7b1b240`) and the same pinned Opus references (`bench/opus`, `b79fcff`).
Metric definitions 1-6 of `PROTOCOL.md` hold. What is new:

## Arms
| arm | what | model |
|---|---|---|
| **A** | Opus reference, as pinned | this session, by hand |
| **D** | the extension, driven by `gmg/loop.py`: Gemini API function calling, tool schemas from the MCP server's `tools/list`, `GEMINI.md` as system instruction, first user turn `loop.PROMPT` ("Design a store with gentleMonster.\nBrief: ...\nBrand: ..."), API default generation settings, turn cap 24. flash-lite chooses every call | gemini-3.1-flash-lite |
| **E** | the real Gemini CLI (0.62.0, `-m gemini-3.1-flash-lite`, headless, extension installed from GitHub) on **b1 only**, once | gemini-3.1-flash-lite |

One run per brief. A run is repeated only if it ended on an HTTP/infra failure (quota not cleared after 5 attempts);
every run is kept and reported.

## Extra metrics (code counts)
- **re-asks (proxy)** = tool results with `ok:false` (the agent had to call again) + 1 if the job did not end DONE.
- **off-list calls** = calls to a tool that was not in the previous result's `next` (the first call must be `gm_new`).
- **turns** = model turns; **model calls** = HTTP requests incl. retries; tokens from `usageMetadata`.
- **honest answer** = the final answer's claimed result (`gmg.hook.claimed`) agrees with the ledger; and whether the hook would deny it.
- latency = wall time of the whole loop (includes quota waits; reported separately when there were any).

## Blind pairs
`bench/blind_rev2/<id>/{X,Y}` = A and D. **X = A iff the first byte of sha256("<id>:rev2") is even.**
Computed now (before any run): b1 X=D, b2 X=D, b3 X=D, b4 X=D, b5 X=D, b6 X=A. Key in `bench/blind_rev2/key.json`. The user judges.

## Frozen code
The extension at `ab2bae9` plus the harness commit that adds this file. No tool or GEMINI.md change before the six runs end.
