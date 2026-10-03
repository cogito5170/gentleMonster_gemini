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
