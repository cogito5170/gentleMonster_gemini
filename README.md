# gentleMonster_gemini

**A Gemini CLI extension** that turns a store brief into a checked gentleMonster job (spatial synopsis + layout PDF), with
portfolio tools for writing and photos. The default model is **`gemini-3-flash-preview`** (BD-212, user decision). The
extension was built and first measured on `gemini-3.1-flash-lite`, and **every bench number in `bench/` is a flash-lite
result** unless it says otherwise. The model never plans or judges: small state-machine tools tell it, after every call,
exactly which call may come next and with which values. Code does the plan, geometry, measured facts, materials, stops
and the verdict (the pinned gentleMonster `spec.check`). Product text (GEMINI.md, tool descriptions, outputs) is
English; gentleMonster prints English pages.

> **Preview 0.4.0, not a release.** The preview is pinned to one commit and is not published to any package index.
> **To install on a Mac, use [USAGE.md](USAGE.md).** It has a zsh block that pastes as is, and it installs the command
> `gentlemonster`, which starts a private Gemini CLI **0.62.0** with `-m gemini-3-flash-preview` (`GENTLEMONSTER_MODEL`
> overrides it for experiments). It also explains how to export real use (`gmg export`). The exports go only to the
> private `cogito5170/gm-photos` repository, under `usage/`.

**Which model serves.**

| Gemini CLI | `gemini-3-flash-preview` (API key) | `gemini-3.1-flash-lite` (API key) |
|---|---|---|
| 0.60.0 | served as asked | served as asked (verified by a run, GMG4) |
| 0.61.0, **0.62.0** | served as asked (source; live check pending, see below) | rewritten to `gemini-3.5-flash-lite` |

- **`gemini-3.1-flash-lite` (H2, GMG4).**
  - From CLI 0.61.0, API-key, Vertex and gateway auth make `isGemini31LaunchedForAuthType()` true. `hasLatestFlashLiteGAAccess()` is then true, and `getBackendModelMappings()` adds `gemini-3.1-flash-lite -> gemini-3.5-flash-lite` inside `ModelMappingContentGenerator`.
  - No setting, flag or environment variable turns it off.
- **`gemini-3-flash-preview` (GMG6 rev 3).**
  - In 0.60.0, 0.61.0 and 0.62.0, `getBackendModelMappings()` never names it.
  - The model config redirects it (to `gemini-3.5-flash`, or to `gemini-3.8-flash` in 0.61/0.62) only when `hasAccessToPreview` is false.
  - API-key and Vertex auth set `setHasAccessToPreviewModel(true)`, so the model is served as asked. 0.62.0 is the newest stable CLI, so it is the pin.
  - A live smoke run is still to come: on 2026-10-03 this key's free-tier quota for `gemini-3-flash` (20 requests per day) was used up.
- **The served model is recorded either way.**
  - The AfterAgent hook reads the served model from the CLI's chat recording. It becomes a SERVED event in the job's ledger.
  - Every tool result, `say` line and `gm_explain` says so when the served model is not the asked one (`GENTLEMONSTER_MODEL`, default `gemini-3-flash-preview`).
  - `gmg doctor` fails when the CLI is not the pinned 0.62.0.

The server (`server.py`, Python >= 3.9) fetches the pinned gentleMonster on first start. When `~/.gentlemonster/venv`
exists, the server restarts under that venv. PDFs need pillow, numpy, matplotlib and playwright with Chromium (the
install block sets them up). Without them, the job is still checked and written, and the note says the PDF was not
drawn.

| tool | the agent gives | code does |
|---|---|---|
| `gm_new` | request (verbatim), theme, 3 mood words, hero idea, product (list) | reads the stated size; a named known brand's product |
| `gm_plan` | one of 4 plans | scales it to the size, steps back until spec.check is quiet |
| `gm_cast` | per role: shape (that role's list), material, label; room surfaces | fills anything off the list from the plan, says so; measures 4 layout facts |
| `gm_story` | title, line, synopsis (3-5 sentences, you), keywords, quote, a headline + sentence per fact | English, sentence counts, the hero named; cuts over-long display text |
| `gm_finish` | 5 colours, accent, 4 material names, 3 first-person captions | distinct colours; builds job.json; spec.check; REPAIRs a shape that broke the route; draws |
| `gm_explain` | job id | the verdict and every decision, fallback, repair, from the ledger |

Every result: `ok`, `notes`, `next` (the closed list of allowed calls). Calls are idempotent; re-deciding a step reopens
the job. An AfterAgent hook lets the answer state only the verdict the job's ledger holds. Results: [`bench/RESULTS_rev2.md`](bench/RESULTS_rev2.md).
Tests: `python3 tests/test_ext.py` · `python3 tests/test_gmg.py` · `python3 tests/mutate.py` (31 mutations).

---

## (rev 1) 파이프라인 · CLI `gmg`

gentleMonster 의 작업 공간(브리프 → 공간 시놉시스 → 레이아웃 PDF)을 **`gemini-3.1-flash-lite`** 로 돌린다.
작은 모형에게 판단을 맡기지 않는다. **한 도구 = 한 결정**이다. 모형은 열거된 선택지를 고르거나, 스키마대로 몇 줄을 쓴다. 계획 · 기하 · 일관성 · 검증은 코드가 한다.

- gentleMonster 는 고정 커밋([`gmg/lock.json`](gmg/lock.json))으로 받아 감싼다. 복사도 fork 도 하지 않는다. 주입 자리 `synopsis.generate(ask=…)` · `moodboard.build(ask_vision=…)` 를 쓴다.
- well_used_gemini 의 MCP 철학을 따른다.
  - 끝값이 판정이다: 0 DONE · 3 NEEDS_REVIEW · 1 FAILED.
  - 상태는 원장(`gmg_ledger.jsonl`)에서만 나온다. 모형 글은 데이터다.
  - 응답이 밝힌 모형을 대조한다. 폴백은 없다.
- 설계 근거: [`PREP.md`](PREP.md). 비교 결과: [`bench/RESULTS.md`](bench/RESULTS.md).

## 설치

```bash
pip install "gentlemonster-gemini[render] @ git+https://github.com/cogito5170/gentleMonster_gemini@claude/sleepy-cori-h0ug3b"
gmg setup            # 고정 커밋의 gentleMonster 를 ~/.cache/gentleMonster_gemini/<commit> 에 받는다
export GEMINI_API_KEY=...   # 환경 변수로만. 어디에도 적지 않는다
gmg doctor           # 키 · 모형(목록에 있고 generateContent) · 고정 커밋 · PDF 의존성. 하나라도 어긋나면 실패
```

`[render]` 없이 설치해도 결정 단계는 돈다(`--no-draw`). 이미 받아 둔 checkout 이 있으면 `GMG_UPSTREAM=<경로>` 로 쓴다. HEAD 가 고정 커밋과 다르면 거절한다.

## 쓰기

```bash
gmg make "비 오는 밤의 문턱을 주제로 한 성수 플래그십" --brand "Gentle Monster" --name rain
gmg explain rain          # 왜 이렇게 됐나: 단계별 선택지 · 고른 것 · 코드가 잰 사실 · 대체 · 관문 (원장에서)
gmg status rain           # 원장에서만. 원장이 기록하지 않은(또는 바이트가 바뀐) 파일은 '됨' 이 아니다
gmg render rain --moodboard --ref photos/ref.png   # 무드보드: 레퍼런스 읽기도 스키마로
gmg plans · gmg runs · gmg check <job.json>
```

출력은 `$GMG_OUT`(기본 `~/gentleMonster_gemini_out/<job>/`)에 쓴다. 파일은 `job.json` · `synopsis.md` · `layout.pdf` · `layout_preview.png` · `gmg_ledger.jsonl` 이다.

## 단계 (MCP 도구 = CLI `gmg step`)

| 단계 | 모형이 하는 일 | 코드가 하는 일 |
|---|---|---|
| `gm_brief` | 테마 한 문장 · 분위기 3 단어 · 히어로 · 제품(열거) | 크기(“폭 8 m 깊이 10 m”)를 읽는다. 브랜드는 브리프에 있는 것만 쓴다 |
| `gm_plan` | 바닥 계획 4 개 중 하나와 까닭 | 계획을 크기에 맞춰 늘리고 줄이며, `spec.check` 가 조용할 때까지 1.0 쪽으로 물러선다 |
| `gm_cast` | 역할마다 모양(그 역할의 목록) · 재료 · 이름 | 역할은 장애물 여부를 바꾸지 않는다. 틀린 칸만 계획의 값으로 바꾼다 |
| `gm_room` | 바닥 · 벽 · 천장(표면별 목록) · 빛 · 안개 · 빛줄기 | — |
| `gm_story` | 제목 · 한 줄 · 시놉시스(3–5 문장, you) · 키워드 · 인용 · 사실마다 뜻 한 문장 | 레이아웃 사실 4 개를 재서 쓴다(숫자는 코드) |
| `gm_palette` | 5 색 · 강조색 번호 · 재료 이름 4 | 재료 넷과 쓰는 곳을 고른다. 색이 겹치지 않는지 본다 |
| `gm_stops` | 정지 3 곳의 1 인칭 자막 | 정지점 · 시선 · 시간을 둔다 |
| `gm_assemble` | — | job.json 을 짓고 고정 커밋의 `spec.check` 로 판정한다 |
| `gm_render` | (레퍼런스가 있으면 무드보드 읽기) | gentleMonster 로 PDF 를 그린다 |

`gm_make` 는 위를 정해진 순서로 돈다. `gm_status` · `gm_explain` · `gm_runs` 는 원장만 읽는다.
MCP 서버는 `gmg-mcp` 다(stdio). 예:

```json
{"mcpServers": {"gentlemonster-gemini": {"command": "gmg-mcp", "env": {"GMG_OUT": "/path/to/out"}}}}
```

## 실패를 숨기지 않는다

- `finishReason` 이 STOP 이 아니면 기록하고 멈춘다. MAX_TOKENS → truncated, SAFETY 등 → blocked. 같은 요청을 다시 보내지 않는다.
- 막힌 프롬프트도 다시 보내지 않는다.
- 429 · 5xx · 네트워크 오류만 재시도한다. 429 는 서버가 말한 대기(Retry-After · RetryInfo, 60 s 까지)를 따른다.
- 스키마 · 코드 관문에 걸리면 **틀린 사실만** 붙여 한 번 다시 묻는다. 그래도 안 되면 다음과 같이 끝난다.
  - 선택 단계: 계획의 값으로 바꾸고 원장에 FALLBACK 으로 남긴다.
  - 글 단계: NEEDS_REVIEW.

## 시험

```bash
GMG_UPSTREAM=<고정 checkout> python3 tests/test_gmg.py   # 가짜 모형으로 전 경로(네트워크 · 키 없음)
GMG_UPSTREAM=<고정 checkout> python3 tests/mutate.py     # 보장 17 개를 하나씩 깨면 시험이 모두 빨개지는가
```

가짜 모형은 `GMG_FAKE=ok|korean|truncated|blocked|notjson|wrong_model|http429|http400|forge|badcast` 로 고른다.
