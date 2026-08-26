# 04-doc-draft

## 목적

phase 03에서 "의미 있음"으로 판단된 변경사항을 구조화된 데이터(작업/담당자/마감일/유형)와
팀 문서에 남길 자연어 초안으로 정리한다. 다음 단계(05 pm-approval)에서 사람이 검토할 대상.

## 모델

`gemini-3.5-flash-lite` 사용 ([[03-semantic-judge]]와 동일한 이유로 `gemini-2.5-flash-lite` 대체).

## 실행법

```bash
source venv/bin/activate
python phases/04-doc-draft/run.py --input phases/04-doc-draft/fixtures/sample_judged_change.json
```

`GEMINI_API_KEY`가 `.env`에 있어야 한다.

## 입출력 스키마

입력 (phase 03 출력 + 원문 텍스트):
```json
{
  "judged": {"is_meaningful": true, "category": "schedule", "confidence": 0.0, "evidence": "string"},
  "text": "string"
}
```

출력:
```json
{
  "structured": {"task": "string", "assignee": "string|null", "due_date": "string|null", "type": "string"},
  "doc_text": "string"
}
```

`structured.type`은 Gemini에 다시 묻지 않고 입력의 `judged.category`를 그대로 사용한다
(phase 03에서 이미 신뢰할 수 있게 분류했으므로 재추론으로 인한 불일치 위험을 없앰).

## 통과 기준 / 검증 결과

`fixtures/sample_judged_change.json`(마감일 연기 + 담당자 지정 케이스) 실행 결과:

- `structured` 비어있지 않음: `task`, `assignee: "민수"`, `due_date: "다음 주 금요일"`, `type: "schedule"` 모두 채워짐
- `doc_text`가 육안으로 자연스러운 한국어 문장("지난주 논의했던 로그인 API 마감일이 다음 주
  금요일로 연기되었습니다. 또한, 결제 모듈 개발은 민수님이 담당하기로 확정되었습니다.")
