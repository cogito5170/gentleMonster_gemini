# PREP — gentleMonster 를 Gemini API 로 (CMD-GMG1, 2026-10-03; 당시 모형 gemini-3.1-flash-lite, 지금 기본 모형은 gemini-3-flash-preview — BD-212)

> 지시: baseline#16 CMD-GMG1 rev 1. 근거: baseline `GA_RLO.md` §7 · BD-166.
> 이 문서는 **비용 0 준비**다. 모형 생성 호출은 하지 않았다. 모형 목록 읽기(models.list) 한 번만 했다.
> 표기: **사실**(읽거나 돌려서 확인) · **근거**(파일:줄) · **제안**(아직 하지 않았다) · **assumption**(확인하지 못했다).
> 읽은 판: gentleMonster `5fdc25e` · well_used_gemini `a24cc62` · baseline 통합 `6aca014`.

## 0. 요약

- `gemini-3.1-flash-lite` 는 이 키로 **목록에 있고 `generateContent` 를 받는다**(verified, §1.4).
- gentleMonster 가 모형을 부르는 곳은 **둘**이다. 시놉시스(텍스트)와 레퍼런스 읽기(비전)다. 둘 다 `gentle_monster/llm.py` 의 `ask()` 하나를 지난다. 나머지 명령(blueprint · video · site · status · list · check)은 모형을 부르지 않는다.
- 모형만 바꾸는 일은 환경 변수 하나(`GEMINI_MODEL=gemini-3.1-flash-lite`)로 된다. 하지만 작은 모형으로 **그대로 쓰려면** 막힐 자리가 다섯 있다(§1.3). 출력 꼴을 구조화하지 않았다, 잘린 답을 모른다, 막힌 답을 되풀이한다, 검사기가 잘못된 타입에 무너진다, 상태가 파일 존재로만 정해진다.
- 제안의 뼈대(§5): gentleMonster_gemini 는 well_used_gemini 가 se_new 를 쓰는 것처럼 **gentleMonster 를 고정 커밋으로 받아 감싸는 얇은 층**이다. 모형 호출 · 원장 · 관문 · MCP 입구만 가진다. gentleMonster 안을 고쳐야 할 것은 `요청:` 으로 올린다.

## 1. 사실 — gentleMonster 가 모형을 부르는 곳

### 1.1 클라이언트 `gentle_monster/llm.py`

| 항목 | 사실 | 근거 |
|---|---|---|
| 통로 | REST `v1beta/models/{model}:generateContent`, `urllib`, 헤더 `x-goog-api-key`. SDK 없음 | llm.py:19, 36 |
| 키 | `GEMINI_API_KEY`, 없으면 `GOOGLE_API_KEY`. 둘 다 없으면 `RuntimeError("no Gemini key …")` | llm.py:22-29 |
| 모형 | 인자 `model` → 환경 `GEMINI_MODEL` → 기본값 **`gemini-2.5-flash`**. 인자를 주는 호출자는 없다 | llm.py:33 |
| 요청 | 사용자 턴 하나: 텍스트 + 이미지마다 `inline_data`. `generationConfig` = `temperature 0.9`, `maxOutputTokens 8192` 뿐. `responseMimeType` · `responseSchema` · `systemInstruction` · `thinkingConfig` · `safetySettings` 없음 | llm.py:30-32 |
| 응답 | `candidates[0].content.parts` 의 text 를 잇는다. `finishReason` · `promptFeedback` · `usageMetadata` · `modelVersion` 을 보지 않는다 | llm.py:40 |
| 되풀이 | 3 번 시도. HTTP 429/5xx 와 `URLError` · `TimeoutError` · `KeyError` · `IndexError` 를 되풀이한다. 그 밖의 HTTP(400/401/403/404)는 곧 멈춘다. 대기는 `2*(i+1)` 초이고, 마지막 시도 뒤에도 잔다. `Retry-After` 를 보지 않는다 | llm.py:35-48 |

### 1.2 호출 자리

| # | 자리 | 입력 | 기대 출력 · 판정 | 실패 모양 | 근거 |
|---|---|---|---|---|---|
| C1 | **시놉시스** `synopsis.generate` ← `pipeline.synopsis` ← `make` | 자유 텍스트 지시와 필드 목록, `spec` 의 enum(TYPES · SHAPES · MATERIALS · LIGHTS · CLEAR 0.30 m), 번들 `gm` 예제 job 전체(JSON). 이미지 없음 | `{`…`}` 를 잘라 `json.loads` → `spec.check(job)`. 문제가 있으면 원 지시 + 이전 답 + 문제 목록으로 다시 묻는다. **최대 3 바퀴**, 바퀴마다 HTTP 최대 3 번 | 3 바퀴 안에 못 맞추면 `job=None` → `RuntimeError`(문제 12 개까지 보임). `ask()` 예외는 잡지 않고 올라간다 | synopsis.py:29-60, 63-68, 71-94 · pipeline.py:55-66 |
| C2 | **레퍼런스 읽기(비전)** `moodboard._llm_read` ← `style()` ← `layout`/`moodboard`/`make`/`example` | 고정 지시 + 레퍼런스 이미지 **첫 장** 하나. mime 은 확장자로 추측한다 | JSON `{sequence, masthead, type, mood}`. sequence 는 CATALOG 로 거른다. cover 로 시작하고 board 를 포함해야 한다. 나머지 필드는 기본값으로 돌린다 | **어떤 예외든** `None` → 측정한 스타일을 그대로 쓴다. 파이프라인은 실패하지 않는다. 키가 없으면 부르지 않는다 | moodboard.py:34-58 |

- `example` 은 "모형 호출 없음" 으로 적혀 있다(README · `__main__.py:8`). 하지만 키가 있고 `--ref` 가 있으며 `--no-llm` 이 없으면 C2 가 돈다. 엄밀히는 사실이 아니다(근거 `__main__.py:34`).
- 무거운 비모형 작업: Playwright PDF(documents.py:44-57) · WebGL 스틸 4 장(pipeline.py:99, 123-130) · 영상(Playwright+ffmpeg, 12–18 분, render.py:6, 71-90) · site 판정(engine/judge.py, 후보마다 3 번 적재).
- 모든 CLI 예외는 `__main__.py:93-95` 에서 `[gentle_monster <cmd> 실패] …` 와 rc 1 로 끝난다.

### 1.3 작은 모형으로 그대로 쓸 때 막힐 자리 (사실 + 영향은 assumption)

| # | 사실 | 근거 | flash-lite 에서의 영향 |
|---|---|---|---|
| F1 | 출력 꼴을 지시문으로만 요구한다. JSON 모드도 스키마도 없다 | llm.py:31-32 | 필드 · 타입 어긋남이 늘 것이다(assumption). C1 의 3 바퀴를 빨리 쓴다 |
| F2 | `finishReason` 를 보지 않는다. 사고 토큰도 `maxOutputTokens` 안에 든다 | llm.py:40 | MAX_TOKENS 로 잘린 답을 완성된 답으로 받는다. 그러면 파싱 실패가 나는데, 원인은 "형식" 으로 잘못 보고된다 |
| F3 | 안전 차단이나 빈 candidates 는 `KeyError` 가 되어 **같은 요청을 3 번** 되풀이한다. HTTP 본문이 JSON 이 아니면 `JSONDecodeError` 가 그대로 빠진다 | llm.py:39, 45 | 비용은 들고 얻는 것은 없다. 실패 사유도 모호하다 |
| F4 | `spec.check` 는 타입이 틀리면 **예외를 던진다**(palette 가 문자열, `at` 길이, 숫자가 아닌 좌표). `save_job` 은 check 가 보지 않는 `why[i].t/d` 를 인덱싱한다 | spec.py:107-222 · pipeline.py:45-52 | 작은 모형의 흔한 실수가 수리 고리로 가지 않는다. 대신 C1 전체가 죽는다 |
| F5 | 지시문의 범위와 검사 범위가 다르다. 지시는 W·D 10-24 · H 3.5-7 · 눈높이 1.1-1.62, 검사는 6-40 · 2.8-8 · 1.0-1.8 이다. `subtitle` 은 요구하지만 필수는 아니다 | synopsis.py:44, 55 · spec.py:142, 215 | 해는 없다. 다만 "무엇이 정답인가" 가 두 곳에 있다 |
| F6 | `status` 는 **파일이 있는지만** 본다 | pipeline.py:176-178 | 반쯤 쓰인 파일 · 손으로 넣은 파일도 "됨" 이 된다. MCP 철학의 '원장에서만 그린' 과 어긋난다 |
| F7 | 기하(동선이 고체에서 0.30 m 떨어짐 · 정지점 3 개가 경로에서 0.6 m 안 · 문이 y=0 에 하나)를 **모형이 좌표로 직접** 맞춰야 한다 | spec.py:145-221 · synopsis.py:44-58 | 작은 모형에 가장 어려운 부분일 것이다(assumption, 측정 안 함) |

### 1.4 모형 확인 (verified, 2026-10-03)

- 환경에 `GEMINI_API_KEY` 가 **있다**(값은 읽거나 적지 않았다). `GOOGLE_API_KEY` 는 없다.
- `GET v1beta/models?pageSize=1000` 을 한 번 불렀다. HTTP 200, 모형 61 개, 다음 쪽은 없었다.
- `models/gemini-3.1-flash-lite`(표시 이름 "Gemini 3.1 Flash Lite"): `supportedGenerationMethods` = generateContent · countTokens · createCachedContent · batchGenerateContent. 입력 한도 1,048,576, 출력 한도 65,536, `thinking: true`.
- 같은 목록에 `gemini-3.1-flash-lite-preview` · `gemini-2.5-flash` · `gemini-3.1-flash-image` · `gemini-3.1-flash-lite-image` 가 있다.
- **확인하지 않은 것:** 실제 `generateContent` 응답(생성 호출 0 회), `responseSchema` 를 받는지, `modelVersion` 이 무엇으로 오는지, 단가.

## 2. 사실 — well_used_gemini 의 MCP 철학 (근거만, 고칠 것 없음)

well_used_gemini 는 se_new `agentic/` 를 고정 커밋(`se_new.lock`)으로 받아 부르는 얇은 층이다. 원장 · Gate01 · 위조 검사기 · 샌드박스의 속은 se_new 에 있다. 이 저장소에서는 읽을 수 없었다(`~/.cache/well_used_gemini` 없음).

| 원칙 | 이 저장소에서 보이는 모양 | 근거 |
|---|---|---|
| 런타임이 판정하는 게이트 | 판정은 끝값이다(0 = DONE, 그 밖 = 상태). 고정 커밋 검사 · doctor 4 점검 · 모형 이름 검사(`generateContent` 를 받아야 설정을 쓴다) · 글쓰기 하드/소프트 관문(LLM 없음). "돌지 못한 점검은 통과로 세지 않는다" | wug.py:25, 257-270, 286-335, 385-429 · wug_essay.py:84-138 |
| 원장에서만 그린 상태 | `events.jsonl` 의 마지막 `TERMINAL` 만 상태가 된다. 기록이 없으면 "(끝 기록 없음)" 이다. 읽는 쪽은 아무것도 쓰지 않는다. 글쓰기 원장 `ledger.jsonl` 의 MODEL_CALL 에는 요청한 모형과 응답이 밝힌 모형이 같이 남는다 | wug_inspect.py:10, 41-54 · wug_essay.py:142-165 |
| 위조 거절 | 최종 답에서 런타임 플래그 어휘를 찾으면 AfterAgent 훅이 deny 한 번, 그다음은 경고다. **어휘를 알려 주지 않는다**(알려 주면 흉내 낼 어휘가 된다). 요청 모형과 보고 모형을 대조한다 | hooks/flag_gate.py:3-14, 96-136 · wug_media.py:172-176 |
| sandbox 도구 | MCP 19 개(stdio JSON-RPC). 실행은 자식 프로세스이고 결과는 끝값이다. GitHub 는 GET 전용 · 소유자 허용 목록 · `..` 거절 · '신뢰 안 함' 머리. 출력은 덮어쓰지 않는다 | wug_mcp.py:50-240 · wug_github.py:27-84 · wug_media.py:82-101 |
| 작은 모형 보완 | "작은 모델 하나의 바깥에 단계를 친다. 판정은 코드가 한다." 역할은 정규식으로 정한다. 후보 5 개 중 번호만 고르게 한다. 위반 목록만 돌려준다("알려 주면 검사가 사양서가 된다"). 배열 대신 문자열이 와도 받는다 | README.md:90 · wug_essay.py:68-81, 208-230, 266-271 · wug_mcp.py:195-197 |

- gentleMonster 에도 같은 씨앗이 이미 있다. `spec.check` 는 규칙 이름이 아니라 사실 문장을 돌려주는 결정적 관문이다(spec.py:107). site 엔진은 `policy.decide` 와 `site/ledger.jsonl` 을 쓴다(engine/policy.py:59-78).

## 3. 제안 — MCP 철학을 gentleMonster 에 입히기 (아직 하지 않았다)

| 원칙 | 제안 | 어디서 |
|---|---|---|
| 런타임 게이트 | (a) `spec.check` 를 **전함수**로: 타입이 틀려도 예외 대신 사실 문장을 낸다. `save_job` 이 쓰는 키(`why[].t/d`, `stops[].cap/sub`)도 검사한다(F4). (b) 명령마다 끝값이 판정이다. 0 = 관문 통과, 3 = 관문 미통과, 1 = 실행 실패. (c) "돌지 못한 검사는 통과가 아니다" — 키가 없으면 C2 를 '안 함' 으로 기록한다 | (a) gentleMonster `spec.py` → `요청:` · (b)(c) gentleMonster_gemini |
| 원장에서만 그린 | 작업 폴더마다 `ledger.jsonl` 을 둔다. `START` · `MODEL_CALL{step, asked, reported=modelVersion\|"미보고", finishReason, tokens}` · `GATE{step, problems_n}` · `ARTIFACT{path, sha256, bytes}` · `END{state}`. `status` 는 원장의 ARTIFACT 해시가 디스크와 같을 때만 "됨" 이다. 파일만 있으면 "기록 없음" 이다(F6) | gentleMonster_gemini (감싸는 층이 쓰고, 원본 `status` 는 그대로 둔다) |
| 위조 거절 | (a) 모형 출력은 **데이터**다. 시놉시스 JSON 에 스키마 밖의 키가 있으면 버리고, 상태 · 판정 단어가 텍스트 필드에 들어와도 상태로 읽지 않는다. (b) 요청 모형과 응답 `modelVersion` 이 다르면 MODEL_CALL 에 "(요청과 다르다)" 를 적고, 폴백하지 않는다. (c) 사람에게 보이는 보고는 원장에서 렌더하고, 모형이 쓴 요약은 싣지 않는다 | gentleMonster_gemini |
| sandbox 도구 | MCP 입구 `gm_*` 를 둔다(§4.3). 쓰기는 `GENTLE_MONSTER_OUT` 아래로만, slug 는 정규식으로. 입력 이미지는 허용 폴더에서만 받고 형식은 바이트로 판별한다. 영상 · blueprint 같은 무거운 일은 명시 플래그가 있어야 돈다 | gentleMonster_gemini |

## 4. 제안 — flash-lite 의 낮은 추론을 사용자 쪽에서 메우기

### 4.1 닫힌 연산 (모형이 고르는 공간을 줄인다)

1. **구조화 출력.** `responseMimeType: application/json` + `responseSchema` 를 `spec` 에서 **코드로 생성**한다. enum(TYPES · SHAPES · MATERIALS · LIGHTS · preset)과 배열 길이(keywords 3 · palette 5 · materials 4 · why 3-4 · stops 3)를 스키마에 넣는다(F1). — assumption: flash-lite 가 이 크기의 스키마를 받는지는 첫 실호출에서 확인한다.
2. **기하를 모형에서 떼어 낸다(F7).** 모형은 텍스트 필드와 **배치 템플릿 id + 몇 개의 수치 파라미터**만 고른다. 좌표 · 동선 · 정지점은 코드가 템플릿에서 계산하고, 그것이 `spec.check` 를 통과하도록 만든다. 번들 예제 넷(gm · tb · ac · ae)이 첫 템플릿 후보다. — 가장 효과가 클 것으로 보지만 측정하지 않았다(assumption).
3. **두 번으로 나눈 호출.** (i) 브리프 → 이야기 필드(title · line · synopsis · keywords · quote · why · palette · materials · accent) (ii) 고른 템플릿과 이야기 → 정지점 cap/sub. 한 번에 고르는 것을 줄인다.
4. **형식만 코드가 고친다.** 형식 오류(hex 대소문자 · 앞뒤 공백 · 문자열 하나가 배열 자리에 온 것)는 코드가 정규화하고 원장에 `NORMALIZE` 로 남긴다. 의미 · 기하 위반은 고치지 않고 수리 고리로 보낸다.

### 4.2 코드 관문 (판정은 코드)

- 응답 관문: `finishReason != STOP` → MAX_TOKENS 이면 "잘림" 으로, SAFETY 이면 "막힘" 으로 기록한다. 막힌 요청은 **되풀이하지 않는다**(F2 · F3). 사고 예산(`thinkingConfig`)과 `maxOutputTokens` 는 설정값으로 고정하고 원장에 남긴다.
- 지시문과 검사 범위를 한 곳(spec 상수)에서 만든다(F5) → `요청:` gentleMonster.
- 수리 고리는 well_used_gemini 의 규칙을 따른다. 위반 **사실**만 돌려주고, 검사 방법은 알리지 않는다. 지금 gentleMonster 도 이미 그렇다.
- 바퀴 상한과 호출 상한은 원장으로 센다. 상한을 넘으면 끝값 3 과 "관문 미통과" 로 끝난다.

### 4.3 쉬운 입구

- 명령 하나: `gmg make "<브리프>" [사진…]`. 기본 모형은 `gemini-3.1-flash-lite`로 고정하고 폴백하지 않는다. 한국어 브리프를 받되 산출 텍스트는 영어다(spec 은 한글을 거절한다, spec.py:115-117). 그 규칙은 지시문이 아니라 관문이 지킨다.
- `gmg doctor`: 키가 있는지(값은 보이지 않는다) · 모형 목록에 있고 `generateContent` 를 받는지 · Python deps · Chromium · gentleMonster 고정 커밋을 점검한다. 하나라도 어긋나면 실패.
- `gmg status <작업>`: 원장에서만 렌더한다.
- MCP(stdio): `gm_make` · `gm_example` · `gm_check` · `gm_status` · `gm_layout` · `gm_blueprint` · `gm_video` · `gm_runs` · `gm_report`. 설명에는 "끝값과 원장이 판정이다 — 다시 말하거나 해석하지 말 것" 을 적는다. 인자가 배열 자리에 문자열로 와도 받는다.
- Gemini CLI 확장으로 얹을지(well_used_gemini 처럼 `gemini-extension.json` + GEMINI.md 라우팅 표)는 §6 질문 Q2.

## 5. 제안 — gentleMonster_gemini 의 모양

```
gentleMonster_gemini/
  gentleMonster.lock        {url, commit}  ← gentleMonster 고정(wug 의 se_new.lock 과 같은 방식)
  gmg.py                    입구: setup · doctor · make · example · status · check · …
  gmg_llm.py                llm.ask 를 대신하는 클라이언트: flash-lite 고정 · 스키마 · finishReason · modelVersion · 원장
  gmg_ledger.py             작업 원장 쓰기/읽기 · 산출물 해시
  gmg_mcp.py                stdio MCP 입구(gm_*)
  templates/                배치 템플릿(§4.1-2)
  tests/                    가짜 모형 · 가짜 HTTP 로만(실호출 0)
```

- **결합 방식(제안):** gentleMonster 코드를 복사하지 않는다. 고정 커밋으로 받아 `synopsis.generate(ask=…)` 처럼 **이미 열린 주입 자리**에 끼운다(synopsis.py:71 `ask=` · moodboard.py:34 `ask_vision=`). 주입 자리가 없는 곳만 `요청:` 으로 올린다. ga_rlo 의 P1 · P2(결합층, 고칠 곳은 주인에게)와 같은 원칙이다.
- gentleMonster 쪽 `요청:` 후보 — 소유자가 정해진 뒤에 올린다: (1) `spec.check` 전함수화 + save_job 키 검사(F4) (2) 지시문 범위를 spec 상수에서 생성(F5) (3) `llm.ask` 에 `generationConfig` 덧붙임 주입 자리 (4) `example` 의 "모형 호출 없음" 문구 바로잡기.

## 6. 제안 — ga_rlo 로 세 저장소를 굴릴 때 필요한 것 (GA_RLO.md §7)

| 필요한 것 | 지금 상태 | 근거 |
|---|---|---|
| ga_rlo 1 단계(G1–G6) | GR 이 짓는 중이다. 이 검증은 그 뒤에 할 수 있다 | baseline#15 |
| 허브(gentleMonster)의 ga 설정 | `ga-rlo init` 이 쓴다(G3). Runner · 샌드박스 · 가드 · Judge · 예산 | GA_RLO.md §2 |
| 작업 세션(well_used_gemini) = 원격 세션 | send_message 로 깨운다. 가드는 **작업 저장소의 `.claude/settings.json`** 에 두고, 그 경로는 허브가 소유한다. 작업 세션이 그것을 고치는 커밋은 R1 에서 거절된다 | GA_RLO.md §7 |
| ga 의 전송 어댑터 | ga 1 판은 파일 우편함 + git 이다. GitHub · 원격 세션 전송은 "2 판" 으로 적혀 있다. 원격 작업 세션을 기본으로 하려면 이 어댑터가 필요하다(assumption: 아직 없다 — ga-SDK 를 읽지 않았다) | BD-131 (4) |
| 결과물(gentleMonster_gemini)의 소유 | 지금은 GMG 다. 검증 과제에서 허브가 소유를 다시 정한다 | #16 baseline 답 |
| 비밀값 | `GEMINI_API_KEY` 는 환경 변수로만 받는다. 원장 · 증거(G2)에 싣지 않는다 | BD-95 · GA_RLO.md §2 G2 |
| 실호출 예산 | 생성 호출은 사용자 허락 뒤에만 한다. 첫 실호출 계획: C1 1 회(최대 3 바퀴 × 3 시도 = 9 요청 상한) + C2 1 회. 단가는 확인하지 않았다(assumption) | GA_RLO.md §4-4 |
| 네트워크 | `generativelanguage.googleapis.com` 에 닿는다(models.list HTTP 200, 이번 확인) | §1.4 |

**질문 (baseline 판단 필요)**
- **Q1** "작업 세션 well_used_gemini" 의 작업자는 누구인가 — Claude Code 원격 세션인가, Gemini CLI(+ well_used_gemini 확장)인가? rlo 가드(`cc_tools_model.json`, Claude Code 훅)는 앞의 경우에만 그대로 걸린다. 뒤의 경우라면 가드 자리는 well_used_gemini 의 AfterAgent 훅이다.
- **Q2** 결과물은 CLI + MCP 입구인가, Gemini CLI 확장(well_used_gemini 처럼)까지인가?
- **Q3** 결합 방식: 고정 커밋으로 감싸기(§5, 권고)인가, 갈래(fork)인가?
- **Q4** 첫 실호출(§6 예산 줄)을 언제, 누구의 허락으로 하나?

## 7. 확인하지 못한 것

- gentleMonster 시험: `python3 tests/test_gentle_monster.py` 를 키 없이 돌렸다. 앞부분(의도 읽기 · 첨부)은 ok 였다. 그 뒤 `PIL` 이 없어 `ModuleNotFoundError` 로 멈췄다(playwright 도 없다). 의존성을 설치하지 않았으므로 **not verified**.
- se_new `agentic/`(원장 · forgery · sandbox)의 속: 이 환경에 checkout 이 없다. **not verified**.
- flash-lite 의 실제 출력 품질 · 스키마 수용 · `modelVersion` 값 · 단가: 생성 호출 0 회. **assumption**.
- ga-SDK 의 원격 세션 전송 어댑터가 있는지: 읽지 않았다. **assumption**.
