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

## Amendment after run 1 (written before run 2)
Run 1 ended 6/6 DONE, but **b3 and b4 lost their brand** (Aesop, Tamburins -> Gentle Monster) and **b6 its product**
(knitwear -> eyewear). Cause, in code: the brand gate checked the brand against `request`, a text the agent itself
passes (it passed the brief without the "Brand:" line); the default brand then forced Gentle Monster's product.
The pre-registered metrics do not see this. Fix: a named brand is kept (a note says when its letters are not in the
request text); only a *named* known brand can correct the product, and only to one it sells. All six briefs are
run again (run 2) on the fixed code; run 1 stays in `metrics.json` and is reported. A post-hoc check, labelled as
post-hoc, is added to the report: brand and product of the job match the brief (`briefs.json` brand, or the
gentleMonster default when none; product read from the brief by me, listed in the report).

## Amendment after run 2 (written before run 3)
Run 2: b1-b5 DONE, **b6 NEEDS_REVIEW**. On the 8 m-wide ritual plan the agent cast the hero as a box where the plan
has a round basin; spec.check measures a basin as a circle and a box as a rectangle, so the route came 0.12 m from it.
Rev 1's pipeline reverted such shapes in code; rev 2 had lost that repair. And the NEEDS_REVIEW result neither listed
the problems nor pointed to the step that fixes them, so flash-lite looped (cast -> story -> finish, 13 calls).
Harness defect found at the same time: runs shared job folders, so a failed run could carry an earlier run's files.
Fix: gm_finish reverts a role whose shape broke the measured layout (REPAIR, said in the ledger); a NEEDS_REVIEW
result carries `problems` and, for layout problems, offers gm_cast; each run writes to its own folder and only files the
ledger recorded in that run are kept. All six briefs run again (run 3). Runs 1-2 stay reported.

## Amendment after run 3 (written before run 4, the last run)
Run 3: 6/6 DONE, brands and products right, 0 off-list, all answers honest. Reading the outputs showed one more
code defect: the `why` headlines were cut by code from the agent's sentence (48 characters, split at hyphens), giving
fragments ("The floor path draws you downward into the", "The glass"); material `where` lists were cut mid-word.
Fix: gm_story's `why` items are {t: 2-6 word headline, d: one sentence} written by the agent (as rev 1 did);
`where` is cut at a word boundary. All six run once more (run 4); **the code is frozen after run 4 whatever it shows**,
and the blind pairs use run 4. Arm E (real Gemini CLI, b1) ran once on the run-3 code (`4b5d09c`) and is not repeated.
