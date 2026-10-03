# gentleMonster

The gm_* tools turn a store brief into a checked spatial synopsis and a layout PDF.

1. Start with `gm_new`. Pass the user's request verbatim as `request`.
2. After every tool result, call exactly one tool from its `next` list, with only the values it lists. Do not plan ahead: each result tells you what comes next.
3. If a result has `"ok": false`, fix what `problems` says and call the tool in `next` again.
4. Write every tool argument in English, except `request`.
5. When `gm_finish` returns, show its `say` line word for word, then the title and the synopsis. Never state a check, result or status yourself.
6. If the user asks why, call `gm_explain`.
