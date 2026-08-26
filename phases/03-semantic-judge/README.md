# 03-semantic-judge

## 목적

회의 전사(phase 02) 또는 채팅(phase 01)에서 나온 텍스트 한 조각이 문서화할 가치가 있는
의미 있는 변화(일정/담당자/범위/결정)인지 Gemini로 판단한다. `false`면 phase 04 이후로
넘기지 않고 여기서 걸러낸다.

## 모델

`gemini-3.5-flash-lite`를 사용한다. (TASKS.md 원안은 `gemini-2.5-flash-lite`였으나,
신규 발급 API 키에는 더 이상 제공되지 않아 — 호출 시 `404 no longer available to new users` —
API가 안내하는 대체 모델로 교체했다.)

## 실행법

```bash
source venv/bin/activate
python phases/03-semantic-judge/run.py --input phases/03-semantic-judge/fixtures/sample_transcript.json
python phases/03-semantic-judge/run.py --source chat --text "오늘 점심 뭐 먹지"
```

`GEMINI_API_KEY`가 `.env`에 있어야 한다.

## 입출력 스키마

입력:
```json
{"source": "meeting" | "chat", "text": "string"}
```

출력:
```json
{
  "is_meaningful": true,
  "category": "schedule" | "assignee" | "scope" | "decision" | "none",
  "confidence": 0.0,
  "evidence": "string"
}
```

## fixtures

- `sample_transcript.json` — 마감일/담당자 변경이 담긴 의미 있는 케이스
- `sample_chitchat_1.json`, `sample_chitchat_2.json` — 잡담/마이크 테스트 등 의미 없는 케이스

## 통과 기준 / 검증 결과

세 fixture 모두 기대대로 판단됨:
- `sample_transcript.json` → `is_meaningful: true`, `category: schedule`
- `sample_chitchat_1.json` → `is_meaningful: false`, `category: none`
- `sample_chitchat_2.json` → `is_meaningful: false`, `category: none`
