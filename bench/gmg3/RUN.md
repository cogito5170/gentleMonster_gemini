# GMG3 evaluation run -- code frozen

- Code, GEMINI.md and tool schemas frozen at `bd85727` (after CMD-GMG4). No change before the evaluation ends.
- Command: `GMG_UPSTREAM=<gentleMonster 5fdc25e> python3 bench/gmg3/replay.py eval` -- both MCP servers' tools (16; a real CLI session with the extension loads both).
- Model: gemini-3.1-flash-lite via the Gemini API (the served model is recorded per question).
- One run. Repeated only after an HTTP or infra failure; every run kept.
- Since D1 (`3b52776`), only the design set was replayed (questions 4 and 22-28). Changes from it: `keep` words, no tool names in answers, user-defined terms. CMD-GMG4 changes (served model, placeholder guard, two servers, plan in gm_new) came from the store-brief runs, not from 32-42.
- Disclosed peek: while building pf_photos I printed the measurements of the seed library stand-ins (used by Q42) and then lowered the subject-region threshold (1 % -> 0.3 %) and de-duplicated palettes. The ranking rule itself (single_subject) was then fixed on synthetic test images, not on the library.
