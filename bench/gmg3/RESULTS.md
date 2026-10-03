# Results -- CMD-GMG3: tools from the real user questions, held-out replay of questions 32-42

Pre-registration:
- D1 at `3b52776`: split, expected paths and states, seed, stand-ins, Opus mapping
- frozen code at `3125bc8` (RUN.md)

Raw data: [`results_eval/`](results_eval/) (`rows.json`, `transcript.json`, `state.json`, the workspace ledger).
One run, no repeats, served model `gemini-3.1-flash-lite` on every response.

## 1. Numbers

| | **F · extension + flash-lite (held out)** | A · Opus (original session) |
|---|---|---|
| tool path matches the pre-registered path | **4 / 11** (32, 33, 35, 40) | – (no tools) |
| expected state holds | **1 / 11** (33); 2 / 11 if Q40's served-model event is not counted (§3) | – |
| text gates (direct register: language, abstract words) | 9 / 9 texts pass, mean abstract-word ratio 1.0 % | 9 / 9 pass, 0.0 % |
| re-asks (tool `ok:false`) | 5 (four in Q36) | – |
| off-list calls | 0 | – |
| model turns · tokens | 24 · 220,592 (about 20k per question) | – |

Per question:

| q | asked | F called | path | state | what F did |
|---|---|---|---|---|---|
| 32 | answer three fashion questions | pf_write | ✅ | ❌ | wrote all three answers as **one** text (the check wants ≥ 3) |
| 33 | "too abstract, more direct" | pf_revise more_direct | ✅ | ✅ | abstract ratio 5.1 % → 0 % |
| 34 | storyline into the first page | pf_write (storyline) | ❌ | ❌ | one storyline, no page map, no three options |
| 35 | refocus on "style" | pf_revise → pf_write | ✅ | ❌ | the refocus call lacked `arg`; it then stored a new text instead of the revision |
| 36 | "다시 시도" | pf_revise ×5 | ❌ | ❌ | repeated the last operation, not pf_choose; refused 3× because the topic was `style` against a Korean text (my check is literal) |
| 37 | widen the categories of a sentence | pf_write (storyline) | ❌ | ❌ | the widening is in the text (hair, clothes, accessories, gait, expression, attitude), but not as a checked revision |
| 38 | adopt A, next storyline | pf_write (storyline) | ❌ | ❌ | no adoption recorded, no options |
| 39 | SECTOR A from a photo | pf_write (sector) | ❌ | ❌ | **did not measure the photo**; wrote from looking at it (no measured colours) |
| 40 | commit to the repository | none | ✅ | ❌* | said rightly that this is the host's job (*see §3) |
| 41 | page 4 PICTURE direction (2 page images) | pf_write (storyline) | ❌ | ❌ | no page map, no three options |
| 42 | which photos for One To One | none | ❌ | ❌ | **ranked nothing**; proposed photos that are not in the library |

## 2. Where flash-lite falls short of Opus, and why

1. **Routing collapses onto the most general tool.**
   - What happened: 7 of the 9 tool-using questions went to `pf_write`.
   - Cause (my design): `pf_write` accepts any `kind`, including `storyline` and `sector`. The closed list therefore had an open door, and flash-lite took the path that accepts everything. The GEMINI.md routing table did not override that.
   - Opus kept a page map (storyline.md), wrote three separate answers, adopted A and continued.
2. **Photos are looked at, not measured.**
   - What happened: with images attached (39, 41, 42), flash-lite never called `pf_photos`. In 42 it recommended photos that do not exist.
   - Opus measured the cover photos (cover.md: brightness 0.11 / 0.55, saturation 0.31 / 0) and ranked the applicant's real photos (02_picture.md).
   - S1's code measurement only helps if the agent is made to call it.
3. **Terse replies.**
   - What happened: "다시 시도" was handled by repeating the previous tool, not by `pf_choose`. It got there, but only after three refusals.
   - Cause: my refocus check matched `style` literally against Korean text, which is a code defect.
4. **Multi-part answers become one text** (32), so per-answer revision and adoption are lost.
5. **The text gates do not separate the arms.** Both pass 9/9; the abstract-word ratio is 1 % vs 0 %. They catch abstract wording, not missing structure or invented content. The quality difference here is behavioural (path and state), and the blind reading is the user's.

## 3. Deviations and disclosures
- **Q40's state check.** It counted one new ledger event, and that event is the SERVED record that CMD-GMG4 added (each turn's served model). Excluding SERVED, the state holds: **2/11**. The primary number stays 1/11 as registered.
- **Stand-ins.** Every attachment is a stand-in, and so is the photo library; F describing a stand-in is not F describing the applicant's photos.
- **Peek.** While building pf_photos I printed the seed-library measurements (RUN.md).
- **GEMINI.md and the tool set changed after D1** (design-set replay and CMD-GMG4). All of that was frozen before this run.

## 4. Proposals (to be checked on the design set 1-31 only, not on 32-42)
- Close the door:
  - `pf_write` drops `storyline` (page flow goes through `pf_pages propose`, three options).
  - `kind=sector`/`caption` about a photo requires a measured photo id in `about`.
  - `items` is required to be one item per question when `kind=answer` and the request lists questions.
- When a user turn carries images, the first tool result says "N attached images not measured -- call pf_photos". The MCP server cannot see attachments, so the hook or a BeforeAgent hook (the CLI passes the prompt) would have to record them.
- `pf_choose` should be the only way to act on "다시/again/1/A안": a BeforeTool hook can redirect a repeated identical call.
- refocus/widen checks accept the topic in either language (a small alias table: style↔스타일 …).
