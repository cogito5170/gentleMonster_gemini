# A · Opus 기준 (사전 고정, flash-lite 를 돌리기 전)

- 이 세션(Claude)이 gentleMonster `synopsis.prompt(brief, brand)` 의 지시를 받은 것으로 하고 job JSON 을 **손으로** 썼다.
  기하를 계산하는 도구나 gmg 도구는 쓰지 않았다.
- 수리 고리는 gentleMonster 와 같다. 고정 커밋 `5fdc25e` 의 `spec.check` 를 돌려 사실 문장이 나오면 고친다(최대 3 바퀴).
- 결과: 여섯 모두 **1 바퀴에 통과**(문제 0). 그래서 `bN.r1.json` 이 최종이다.

| 브리프 | 바퀴 | 문제 | 동선 최소 여유 |
|---|---|---|---|
| b1 | 1 | 0 | 0.40 m (rain_l) |
| b2 | 1 | 0 | 0.80 m (lane1) |
| b3 | 1 | 0 | 0.37 m (basin) |
| b4 | 1 | 0 | 1.00 m (pay) |
| b5 | 1 | 0 | 1.00 m (pay) |
| b6 | 1 | 0 | 0.60 m (screen) |

**쏠림(숨기지 않음):** 이 세션은 쓰기 전에 `spec.py` 를 읽었다. 그래서 지시문에 없는 검사 규칙(겹침 허용 0.25 m · cable_curtain 예외 · 원형 basin 거리)을 알고 썼다.
그 밖의 브랜드 규칙: 지시문대로 브랜드가 비면 Gentle Monster 로 했다(b2 · b6).
