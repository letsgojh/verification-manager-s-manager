# 05-pm-approval

## 목적

phase 04에서 만든 문서 초안을 사람(PM)이 승인해야 phase 06(Notion 반영)으로 넘어가는
게이트를 구현한다.

**설계 변경**: 원안(`implementation_plan.md`)은 GitHub Environment의 Required reviewers
기능으로 이 게이트를 구현했으나, 실제 서비스 방향이 "PM에게 Discord DM으로 승인 요청을
보내고 버튼(수락/거절/보류)으로 응답받는" 구조로 바뀌어 그에 맞게 다시 구현했다.
(추후 정식 서비스에서는 전용 웹페이지에서 승인받을 예정이지만, 이번 검증 단계에서는
Discord DM + 버튼으로 "사람이 눌러야 다음 단계로 진행된다"는 게이트 로직만 확인한다.)

## 동작 방식

1. `discord.py`로 봇이 게이트웨이에 접속
2. `DISCORD_PM_USER_ID`로 PM에게 DM 채널을 열고, 문서 초안 내용 + 수락/거절/보류 버튼을 전송
3. PM이 버튼을 누르면 그 결과를 받아 `decision`으로 반환하고 봇 접속을 종료
4. 5분(`TIMEOUT_SECONDS`) 안에 응답이 없으면 `held`(보류)로 간주

## 실행법

```bash
source venv/bin/activate

# mock: 실제 DM 없이 fixtures를 "수락"으로 간주하고 바로 출력 (로직/스키마 확인용)
python phases/05-pm-approval/run.py --mock

# 실제: PM에게 DM 전송 후 버튼 클릭 대기
python phases/05-pm-approval/run.py --input phases/05-pm-approval/fixtures/sample_draft.json
```

`.env`에 `DISCORD_BOT_TOKEN`, `DISCORD_PM_USER_ID`(DM 받을 PM의 Discord 사용자 ID)가 필요하다.
봇이 DM을 보내려면 PM과 같은 서버(길드)에 봇이 먼저 들어가 있어야 한다(01-chat-polling에서
이미 초대한 서버 재사용 가능).

## 입출력 스키마

입력 (phase 04 출력, `shared.schemas.DocDraftOutput`):
```json
{
  "structured": {"task": "string", "assignee": "string|null", "due_date": "string|null", "type": "string"},
  "doc_text": "string"
}
```

출력 (`shared.schemas.PmApprovalOutput`):
```json
{
  "decision": "approved" | "rejected" | "held",
  "structured": {"task": "string", "assignee": "string|null", "due_date": "string|null", "type": "string"},
  "doc_text": "string"
}
```

## 통과 기준

- `--mock` 실행 시 `fixtures/sample_draft.json`이 스키마 검증을 통과하고 `decision: "approved"`로 출력됨
- 실제 모드 실행 시 PM이 DM으로 승인 요청과 버튼을 받고, 버튼을 누르면 그 결과(`decision`)가
  정확히 반영되어 스크립트가 종료됨 (수락/거절/보류 각각 확인)
- 타임아웃(5분) 동안 무응답이면 에러 없이 `decision: "held"`로 종료됨
