# CMD-GMG4 re-measure (pre-registered 2026-10-03, before any run on these briefs)

- **Briefs:** `fresh_briefs.json` (f1-f6). They are new; the six registered rev-1 briefs are not used for any tuning.
- **Arm D′:** the extension after the H1/H2/H3 changes, driven by `gmg/loop.py` exactly as rev-2 arm D (Gemini API function calling, the tool schemas, GEMINI.md as system instruction, turn cap 24). One run per brief; a run is repeated only after an HTTP or infra failure.
- **Reported next to rev-2 run 4** (D on b1-b6):
  - gate passed, spec completeness, re-asks, off-list calls
  - model turns, tokens per job (prompt / output / **cached** / total)
  - Gemini calls
  - **the served model per run** (modelVersion, also as a SERVED event in each job's ledger)
  - H1 check: the brand and product of each job against the brief (code: `briefs` brand or the gentleMonster default; product read by me below, before the run)
- **Expected products** (read from the briefs now): f1 eyewear · f2 objects (bags: none of the five product enums fits better than objects or fashion; both are accepted) · f3 skincare or fragrance · f4 skincare or fragrance · f5 fashion · f6 fragrance.
- The code is frozen at the commit that adds this file.

## After run 1 (written before the f2 rerun)
Run 1 is the held-out measurement and stays as is. f2 hit the turn cap: one palette hex came back garbled
(`"#E0E0E0,name:"`) and the error ("palette needs exactly 5 items ...") did not say which item or value, so the agent
repeated gm_finish 21 times. Its brand also came out as `gentleMonster` (the extension's name in the prompt).
Fix (generic): code repairs a hex that still holds one `#rrggbb` and names any other bad item with its value; known
brand spellings are canonicalised. **f2 is rerun once after the fix and reported as post-fix, not held out.**

## After the f2 rerun (written before the store-server run)
The f2 rerun finished DONE but with product eyewear for a bag pop-up: the agent passed the extension's own name
("gentleMonster") as the brand, the canonicalisation made it the known brand, and the known brand set the product.
Fix: only a brand written in the request with its own spelling may correct the product. And run 1 showed H3 was
**not** met: tokens per DONE job rose (36.7k vs 27.4k in rev-2 run 4) because CMD-GMG3's ten tools doubled the
declarations resent every turn. Fix: the extension runs as two MCP servers (store `gm_*`, portfolio `pf_*`); a store
session loads 8 tools. **All six fresh briefs run once more against the store server only, reported as post-fix (not
held out), next to run 1.**
