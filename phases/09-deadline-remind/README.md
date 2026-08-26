# 09-deadline-remind

## 목적

마감일이 임박한(기본 D-3 이내) 작업의 담당자에게 PM 말투로 진행 상황을 확인하는 DM을 보내고,
답장을 받으면 Gemini로 완수 가능성을 판단해 응원(on_track) 또는 독촉(at_risk) 메시지를
이어서 보낸다. 기존 00~08 파이프라인과는 별개의 새 기능(진행 관리/리마인드)이며,
`implementation_plan.md`/`TASKS.md` 원안에는 없던 것을 대화 중 추가했다.

## 대화 흐름

**PM 질문(체크인) → 담당자 답장 → Notion 반영 → PM 마무리 메시지**로 정확히 3턴에서
끝난다. 마무리 메시지는 절대 질문으로 끝나지 않도록 프롬프트에 명시했다(질문으로 끝나면
담당자가 또 답장해야 해서 대화가 안 끝남).

## 지금 범위(MVP 단순화)

- **담당자 한 명만**: Notion에서 담당자를 조회하지 않고, 고정된 `DISCORD_ASSIGNEE_USER_ID`
  한 명에게만 보낸다. 여러 담당자/실제 이름↔Discord ID 매핑은 다음 단계 과제.
- **Notion 반영**: 답장을 받으면 `06-notion-sync`의 `build_payload()`를 그대로 재사용해
  `Type: progress_check` 페이지로 기록한다(담당자 답장 + 판단 + PM 마무리 메시지 본문에 남김).
  기존 task 페이지를 업데이트하는 게 아니라 새 로그성 페이지를 만드는 방식(단순화).
- **PM 말투**: 실제 PM 메시지 샘플이 없어 프롬프트의 톤 가이드(`TONE_GUIDE`)로 대체했다.
  실제 샘플이 생기면 few-shot으로 바꿀 수 있다.
- **트리거**: 매일 1회 cron으로 도는 것을 전제로 설계했지만(운영 시 여러 작업을 훑어야 함),
  지금은 `run.py`가 입력으로 받은 작업 하나만 처리한다. 실제 여러 작업을 도는 워크플로는
  아직 없음(GitHub Actions 연결은 후속 작업).

## 실행법

```bash
source venv/bin/activate

# D-3 이내 작업만 실제로 DM (그 외엔 skipped: true로 조용히 종료)
python phases/09-deadline-remind/run.py --input phases/09-deadline-remind/fixtures/sample_task.json

# D-3 조건 무시하고 강제 실행 (테스트용)
python phases/09-deadline-remind/run.py --input <path> --force
```

`.env`에 `DISCORD_BOT_TOKEN`, `DISCORD_ASSIGNEE_USER_ID`, `GEMINI_API_KEY`,
`NOTION_API_KEY`, `NOTION_DATABASE_ID` 필요. 담당자가 봇과 같은 서버에 있어야 DM을 받을 수 있다.

## 동작 방식

1. `due_date`에서 오늘까지 남은 일수(`days_left`)를 계산. `REMIND_THRESHOLD_DAYS`(3)보다
   많이 남았으면 `skipped: true`로 종료(`--force`면 무시)
2. Gemini로 체크인 메시지 생성(인사 + 작업 언급 + D-day + 진행 상황 질문 형식 고정) → DM 발송
3. 담당자 답장을 최대 `REPLY_TIMEOUT_SECONDS`(5분, 테스트용 값)까지 대기
   - 타임아웃이면 `assessment: "no_reply"`로 종료 (Notion 반영/마무리 메시지 없이 끝)
4. 답장이 오면 Gemini로 완수 가능성 판단 + 마무리 메시지 생성(질문 금지, 응원 또는 독촉)
5. Notion DB에 `progress_check` 페이지로 기록 (`06-notion-sync`의 payload 로직 재사용)
6. 30~90초 랜덤 딜레이(그 동안 "입력 중..." 표시) 후 마무리 메시지 DM 발송 — 답장 받자마자
   즉답하면 봇 티가 나서 사람이 읽고 타이핑하는 것처럼 텀을 준다

## 입출력 스키마

입력 (`shared.schemas.DeadlineRemindInput`):
```json
{"task": "string", "assignee": "string", "due_date": "YYYY-MM-DD", "type": "string"}
```

출력 (`shared.schemas.DeadlineRemindOutput`):
```json
{
  "skipped": false,
  "days_left": 2,
  "check_in_message": "string",
  "assignee_reply": "string|null",
  "assessment": "on_track" | "at_risk" | "no_reply",
  "notion_synced": false,
  "closing_message": "string|null"
}
```

## 통과 기준 / 검증 결과

- D-3 초과 작업 → `skipped: true` 확인 완료
- D-3 이내 작업 실제 DM 왕복 테스트: 체크인 메시지가 요청한 형식(인사+작업+D-day+진행
  질문)대로 나옴 → 담당자 답장("결제 모듈 개발 중, 내일 로그인 API까지 가능할 듯")에
  `assessment: "at_risk"`로 판단 → Notion에 `progress_check` 페이지로 반영(`notion_synced: true`,
  본문에 답장/판단/마무리 메시지 기록 확인) → 질문 없이 끝나는 마무리 메시지 발송까지 전부 확인
- 무응답 타임아웃 시 `assessment: "no_reply"`로 에러 없이 종료(Notion 반영 없이 종료)되는 것도 확인
