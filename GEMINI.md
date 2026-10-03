# gentleMonster

Tools for a store-design portfolio. Every result says `ok`, and `next`: the calls that may come next, with their allowed values. Call one of them; do not plan ahead.

| the user wants | call |
|---|---|
| a store space from a brief | `gm_new` → `gm_plan` → `gm_cast` → `gm_story` → `gm_finish` |
| conditions on a running store job / PDFs, render, video | `gm_amend` / `gm_render` |
| why a job came out this way, or failed | `gm_explain` |
| portfolio text, photos or pages | `pf_show` first |
| photos measured, ranked, grouped, chosen | `pf_photos` → `pf_sort` |
| new text (answers, cover lines, captions, page text, storyline) | `pf_write` |
| change a text (more direct, refocus, more categories, shorter, translate) | `pf_revise` |
| does a phrase fit the terms (e.g. SPA) | `pf_concept` |
| page flow, what comes next, adopt "A안" | `pf_pages` |
| a terse reply: "1", "A", "a ? a:b", "다시 시도" | `pf_choose` with the reply verbatim |
| git, commits, PRs, which harness or model to use | none of these tools: that is the host's job; say so |

- If `ok` is false, fix what `problems` says and call again.
- Write portfolio text in the user's language. Store-job arguments (gm_*) are in English, except `request`.
- Words the user chose for their own ideas go in `keep`; they are not counted as abstract.
- Show `say` lines word for word. Never state a check, result or status yourself.
- End with the latest result's numbered options, in plain words. Never show tool names to the user.
