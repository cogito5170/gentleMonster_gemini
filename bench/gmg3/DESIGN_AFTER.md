# Design work after the GMG3 evaluation (BD-186, BD-187, BD-190)

Everything here is **design**, not evaluation:
- questions 1–31 are the design set;
- 32–42 became design data once they had been seen (BD-187);
- the semantic data in `gentleMonster@4eb4ffa` `data/user_questions/` (BD-190) covers questions 1–44 only.

No new real question was read. The freeze for the next held-out set (BD-187) waits for CMD-GMG5, by baseline's order: its plans and thresholds are frozen with the rest.

## Runs (one each, served model `gemini-3.1-flash-lite`)

| run | questions | code | result |
|---|---|---|---|
| [`results_design_props/`](results_design_props/) | 4, 22–28, 30 | `d288055` (proposals 1–4, colour nudge) | P2 worked when a tool was called: in q22 a write was refused, the image was measured, then the write was retried. **q4 (five photos) and q30 (`a ? a:b`) called no tool**, so the tool-result routing never fired. |
| [`results_design_32_42/`](results_design_32_42/) | 32–42, scored with `eval.json`'s checks | `6c31a4e` (+ BeforeAgent turn note) | path **6/11**, state **3/11**, against 4/11 and 1/11 at the GMG3 freeze. 39, 41 and 42 ended on the free-tier daily quota (500 requests per day per model), so they are not results. |

Remaining misses in the 32–42 run, and what changed for each:

| q | what flash-lite did | change (code, not prompt wording) |
|---|---|---|
| 32 | measured the photo, but wrote the three answers as one text | `turn.questions_in`: a turn that lists questions ("..?, ..?, ..?") makes `pf_write kind=answer` refuse fewer items than questions |
| 34, 38 | wrote page text (`pf_write page_text`) for a story-line request; no adoption recorded | `turn.FLOW`: a story-line / page-flow turn redirects `pf_write` to `pf_pages` (set, then propose 3). `turn.adopted_in`: "A안을 채택" / "go with B" redirects to `pf_choose` first |
| 37 | `refocus` with `arg="style, expansion of categories"`, refused twice | refocus with a list of topics names `widen_categories` in its error; a widen request ("범주를 확장") gets a turn note |
| 39–42 | quota | the loop now stops at once when the server delay is over 600 s (a used-up daily quota), instead of waiting 4 × 60 s per turn |

Each redirect fires at most once per turn: if the agent cannot follow it (for example there is no option A to adopt), the turn goes on.

The detectors were checked against all 44 design questions:
- questions: hits q32 only;
- adoption: q38 only;
- page flow: 1, 4, 5, 34, 38 and 41;
- widen: q37 only. "사진 범주의 한 요소" in q42 is not a widen request.

## Not done
- **A live re-run after the last routing changes (questions, adoption, page flow, widen).** The daily quota was used up. These changes are checked by the fake-model tests and the mutations only.

## T1 on the real photos (BD-191, BD-193)
[`t1_real_photos.json`](t1_real_photos.json) compares `pf_photos` with the values recorded in `gentleMonster@4eb4ffa`:
- **Images:** the 14 top-level images of `gm-photos@780f412`, all 14 sha256 verified. `heldout/` was neither checked out nor read.
- **Measures:** brightness, contrast, saturation, warmth, dark share, centre focus and mono are **identical** (max absolute difference 0).
- **Palettes differ by design.** The recorded palette is the raw upstream palette, which keeps near-duplicates (for example four near-blacks in 3.webp). `pf_photos` keeps colours at least 30 RGB apart.
- **Layout flag:** `layout_like` is false for the 5 photos and true for all 9 layouts, drafts, notes and case studies, so 14/14 match the recorded roles.
