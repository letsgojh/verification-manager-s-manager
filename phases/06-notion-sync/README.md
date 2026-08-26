# 06-notion-sync

## 목적

phase 05에서 승인된 문서 초안을 Notion 데이터베이스에 페이지로 기록한다. 파이프라인의 마지막 단계.

## 실행법

```bash
source venv/bin/activate

# dry-run: 실제 API 호출 없이 payload만 출력 (NOTION_DATABASE_ID 없어도 동작)
python phases/06-notion-sync/run.py --input phases/06-notion-sync/fixtures/sample_approved_doc.json --dry-run

# 실제: Notion 페이지 생성
python phases/06-notion-sync/run.py --input phases/06-notion-sync/fixtures/sample_approved_doc.json
```

실제 모드는 `.env`에 `NOTION_API_KEY`, `NOTION_DATABASE_ID`가 필요하다.

## 대상 Notion 데이터베이스 준비

Integration 발급, 데이터베이스 프로퍼티 구성, Connection 연결, Database ID 추출까지의
수동 설정 절차는 레포 루트의 [`MANUAL_SETUP.md`](../../MANUAL_SETUP.md) 4장 참고.

## 입력 스키마

`shared.schemas.NotionSyncInput` (phase 04/05 출력과 동일한 `structured`+`doc_text` 형태):
```json
{
  "structured": {"task": "string", "assignee": "string|null", "due_date": "string|null", "type": "string"},
  "doc_text": "string"
}
```

`due_date`가 `YYYY-MM-DD` 형식이면 Notion `date` 프로퍼티에 매핑하고, "다음 주 금요일" 같은
상대 표현이면 date 프로퍼티는 비우고 본문(`doc_text`)에 원문 그대로 덧붙인다(Notion date
프로퍼티는 ISO 날짜만 허용하므로).

## 통과 기준 / 검증 결과

- `--dry-run` 실행 시 payload가 Notion `pages.create` API 스펙(`parent.database_id`,
  `properties`, `children`)에 맞게 출력됨 — 확인 완료
- 실제 실행 시 대상 데이터베이스에 새 페이지(Name/Assignee/Due date/Type 프로퍼티 + 본문
  단락)가 생성되는지 확인 — `NOTION_API_KEY`/`NOTION_DATABASE_ID` 필요, 아직 미검증
