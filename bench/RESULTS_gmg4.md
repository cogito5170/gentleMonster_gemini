# Results -- CMD-GMG4: H1, H2, H3 and a fresh-brief re-measure

Protocol: [`PROTOCOL_gmg4.md`](PROTOCOL_gmg4.md). The fresh briefs ([`fresh_briefs.json`](fresh_briefs.json)) were committed at `23cb443`, before any run. Each amendment was written before the run that followed it. Raw data: [`results_gmg4/metrics.json`](results_gmg4/metrics.json), with per-run transcripts and ledgers.

## S1 / D1 -- H2: which model serves (finding)

| Gemini CLI | `-m gemini-3.1-flash-lite` with an API key | evidence |
|---|---|---|
| 0.46.0, 0.54.0, 0.58.0, **0.60.0** | served **gemini-3.1-flash-lite** | the bundles have no mapping. A 0.60.0 run's stats and its chat recording name `gemini-3.1-flash-lite` |
| **0.61.0**, 0.62.0 | served **gemini-3.5-flash-lite** | `getBackendModelMappings()` adds `gemini-3.1-flash-lite -> gemini-3.5-flash-lite` when `hasLatestFlashLiteGAAccess()`. That is always true for `gemini-api-key`, `vertex-ai` and `gateway` auth (`isGemini31LaunchedForAuthType`) |

- No setting, flag or environment variable disables the mapping. The CLI is not patched.
- **Chosen path:** install `@google/gemini-cli@0.60.0` (README). `gmg doctor` fails on 0.61 or newer and passes on 0.60.0 (both checked).
- **S2, in all cases:**
  - Recording: the served model is recorded as a SERVED event in the job's ledger. Under the CLI, the AfterAgent hook reads it from the CLI's own chat recording (`transcript_path`, a `"model"` on every response). Under the API loop, it comes from `modelVersion`.
  - Warnings: when the served model is not 3.1, every tool result carries a `served` warning, and `say` and `gm_explain` say so.

## S3 -- H1: placeholders never reach a page
- `gm_new`: a bracketed or stock brand (`(none named)`, `N/A`, `TBD`, `없음` …) counts as "not named". The default brand is used, with a note and closed options (keep the default, or name the brand). Known brand spellings are canonicalised (`gentleMonster` → `Gentle Monster`). Only a brand **written in the request** may correct the product.
- `gm_finish`: refuses any page-bound text that is a placeholder (brand, title, keywords, labels, colour and material names, captions).
- The harness prompt no longer writes a placeholder when there is no brand.

## S4 / S5 / D3 -- the fresh-brief re-measure

| | rev 2 run 4 (b1-b6) | **GMG4 run 1 (f1-f6, held out, all 16 tools)** | GMG4 post-fix, store server (f1-f6, **not** held out) |
|---|---|---|---|
| gate passed | 6/6 | **5/6** | 6/6 |
| completeness | 72/72 | 60/72 | 72/72 |
| re-asks | 4 | 25 (f2: 22) | 6 |
| off-list calls | 0 | 0 | 1 |
| model turns / HTTP calls | 40 / 42 | 55 / 60 | 40 / 41 |
| tokens, total (cached) | 164,163 | 446,879 (152,569) | 190,138 (24,111) |
| **tokens per job** | **27,360** | 36,725 per DONE job (f2 alone: 263,256) | **31,690** (min 20,633 · max 44,891) |
| served model, every run | gemini-3.1-flash-lite | gemini-3.1-flash-lite (6/6, also in each ledger) | gemini-3.1-flash-lite (6/6) |
| brand and product as the brief | 5/6 (b6 printed `(none named)`) | **4/6**: f2 and f6 printed the brand `gentleMonster` | **6/6** |
| answer states only the ledger's verdict | 6/6 | 6/6 | 6/6 |

### What the held-out run showed, and what was fixed (post-fix, not held out)
1. **f2 hit the 24-turn cap.**
   - What happened: one colour came back as `"#E0E0E0,name:"`. My error said only "palette needs exactly 5 items", so the agent sent the same thing 21 times.
   - Fix: code repairs a value that still holds one `#rrggbb`, and names any other bad item with its value.
   - **This is the clearest instance so far of principle (6): an error must carry the fix.**
2. **The extension's name became the brand** (f2, f6: `gentleMonster`, from "Design a store with gentleMonster").
   - First fix: canonicalise to "Gentle Monster". That then set eyewear on f2's bag pop-up.
   - Final rule: the name in the prompt is not a brand claim; only a brand written in the request may correct the product.
3. **H3 was not met; it got worse.**
   - The ten CMD-GMG3 tools doubled the declarations resent on every turn.
   - Fix: two MCP servers (store `gm_*`, portfolio `pf_*`), 8 tools each. Store declarations dropped from 12.2k to 7.2k characters.
   - Also from S4: `gm_new` takes the plan (one turn fewer), and offers no longer repeat schema enums (results 7.2k → 5.7k characters per job).

### Where it still falls short
- **Tokens per job are still above rev 2** (31.7k vs 27.4k on the mean; per turn 4.1-5.6k vs 3.8-4.4k).
  - The best case (4 calls) is 20.6k.
  - The extra turns are `gm_finish` re-asks: near-identical colours (4 of 6) and captions not in the first person (2 of 6).
  - Proposal, not done: code nudges a near-duplicate colour apart (a closed operation, said in a note) instead of asking again. Store declarations still include gm_amend and gm_render; a third server for production would cut them too.
- **Caching:** only 24k of 190k prompt tokens were cached in the API loop. The real CLI cached 57k of 87k on its run (rev 2 arm E).

Total Gemini use for GMG4: 107 calls, 674,061 tokens (plus one 0.60.0 check run).
