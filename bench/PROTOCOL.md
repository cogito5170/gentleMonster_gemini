# 비교 규약 (CMD-GMG2, 사전 등록 2026-10-03)

이 문서와 `briefs.json` 은 **어느 쪽을 돌리기 전에** 커밋한다. 결과를 본 뒤 지표 정의를 바꾸지 않는다.
바꿔야 하면 바꾼 판을 따로 적고, 앞의 정의로 잰 값도 함께 남긴다.

## 세 갈래

| 갈래 | 무엇 | 모형 | 비고 |
|---|---|---|---|
| **A · Opus 기준** | gentleMonster 의 시놉시스 지시문(`synopsis.prompt`)을 받은 이 세션(Claude, 고급 추론 모형)이 job JSON 을 **도구 없이 직접** 쓴다. gentleMonster 와 같은 수리 고리: `spec.check` 의 사실 문장만 보고 고친다, 최대 3 바퀴 | 이 세션 | **flash-lite 를 돌리기 전에** 커밋으로 고정한다. 초안마다 남긴다 |
| **B · flash-lite 그대로** | gentleMonster `synopsis.generate` 를 고치지 않고 `GEMINI_MODEL=gemini-3.1-flash-lite` 로 | flash-lite | 참고 갈래. 도구가 무엇을 바꿨는지 보려고 둔다 |
| **C · flash-lite + gmg 도구** | `gmg make` — 한 도구 = 한 결정, 선택지 열거 · responseSchema, 기하 · 일관성 · 검증은 코드 | flash-lite | 이 지시의 산출 |

브리프마다 갈래마다 **1 회**. 결과가 나쁘다고 다시 돌려 고르지 않는다. 다시 돌리면 그 사실과 모든 회차를 적는다.

## 지표 (코드가 센다)

1. **관문 통과** — 마지막 job 에 `spec.check(job) == []` 이면 1 (gentleMonster 고정 커밋의 검사기 그대로).
2. **spec 완결성** — 아래 12 항목 가운데 맞는 수 / 12.
   brand · title · line · synopsis 길이 60-900 · keywords 3 · why 3-4 · palette 5 개 #rrggbb · accent #rrggbb ·
   materials 4 개 preset 유효 · room 재료 셋과 light 유효 · layout(envelope 안 · 문 하나 · 겹침 없음 · 동선 0.30 m) · stops 3 개(경로 위 · cap/sub 영어).
   job 이 아예 없으면 0.
3. **다시 물은 횟수(대리)** — 사용자가 결과를 받기까지 시스템이 모형에 **다시 물은** 횟수(수리 바퀴 + 단계 재질문).
   마지막에 관문을 못 넘으면 +1(사용자가 다시 물어야 한다).
4. **지연** — 브리프 → job.json 벽시계 초. A 는 세션 안에서 썼으므로 잴 수 없다(n/a).
5. **Gemini 호출 · 토큰** — 원장의 MODEL_CALL 합계(시도 수 · prompt · 출력 · 사고 토큰). A 는 0.
6. **응답이 밝힌 모형** — 요청과 다르면 따로 적는다.

## 맹검 묶음 (판정은 사용자)

- 브리프마다 A 와 C 의 산출을 **X · Y** 로 가린다. 어느 쪽이 X 인지는 동전 대신 `sha256(brief_id)` 의 첫 비트로 정한다(재현 가능, 결과를 보고 고를 수 없다).
- 묶음에 넣는 것: `synopsis.md`(gentleMonster 의 `save_job` 이 쓴 그대로) · 레이아웃 미리보기 PNG(`documents.layout_pdf`).
- 열쇠는 `blind/key.json` 에 따로 둔다. 판정 전에 열지 않는다.
- 이 세션은 승패를 매기지 않는다.

## 숨기지 않을 것

- C 가 A 에 못 미치는 자리와 그 까닭(지표 · 관찰 둘 다).
- A 는 이 세션이 `spec.check` 규칙을 읽은 뒤에 썼다 — A 에 유리한 쏠림이다(gentleMonster 지시문에 없는 규칙을 안다).
- C 의 배치는 템플릿에서 온다 — 새로움은 A 보다 낮을 것으로 본다(assumption, 판정은 사용자).
