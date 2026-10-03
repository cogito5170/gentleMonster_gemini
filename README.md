# gentleMonster_gemini

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
