# CMD-GMG3 protocol (pre-registered 2026-10-03, before any GMG3 tool exists)

Source: cogito5170/gentleMonster@35073f7 `docs/portfolio/questions.md` (44 real user questions, verbatim).

## Split (D1, fixed now)
- **Design set: questions 1-31.** Tools, GEMINI.md and any tuning use only these.
- **Evaluation set: questions 32-42** (11). For each, `eval.json` fixes the following now, before any tool is written:
  - the question text, verbatim
  - its attachments (stand-ins, below)
  - the **required** tools and the **allowed** extra tools
  - the **expected state**, checked by code on the workspace before and after the question
  - the part of the Opus reference it maps to
- **No tuning on 32-42** (D5). If the evaluation reveals a defect, it is reported; a fix is re-evaluated only on 1-31.

## Arms
| arm | what |
|---|---|
| **A · Opus reference** | What the original session (Claude Opus, with no gentleMonster_gemini tools) produced for 32-42, as committed in gentleMonster@35073f7 `docs/portfolio/*.md`. Mapping per question in `eval.json`. These texts were written before this directive existed, so this session cannot bias them. |
| **F · extension + flash-lite** | A **conversation replay**: the questions 32-42 are the user's turns, in order, in one conversation. flash-lite (`gemini-3.1-flash-lite`, Gemini API function calling, the extension's tool schemas, GEMINI.md as the system instruction) chooses every tool call. State carries over: the workspace is seeded from `seed.json` (the state after question 31), and every question builds on the previous ones. At most 12 model turns per question. One run; it is repeated only after an HTTP or infra failure, and every run is kept. |

## Attachments are stand-ins
The real attachments were never committed. `make_images.py` draws deterministic stand-ins that imitate only what the log says each attachment was:
- 32: the cover page
- 39: a style photo
- 41: pages 1-2 and 3-4
- 42: the One To One case page

The photo library (seed) holds six stand-ins for the applicant's earlier photos. **Every measured value in F is a measurement of a stand-in.** A user turn with attachments sends the images inline, and the text says `[attached: <path>]`.

## Metrics (code counts)
1. **Tool-path match** (F): the rule in `eval.json` holds for each question.
2. **Expected state** (F): the `eval.json` assertion holds.
3. **Code-gate pass rate**: the same text gates run on F's texts and on A's texts:
   - length cap
   - abstract-word ratio (the list is fixed in code before the run, built from general vocabulary and not from 32-42)
   - language as asked
4. **Re-asks** (F): tool results with `ok:false` + retries the agent made within the question.
5. **Tokens and Gemini calls** (F); latency per question.
6. **Where F falls short of A, and why**: observations, reported next to the numbers.

Code is frozen at the commit that adds `bench/gmg3/RUN.md` (written just before the run).
