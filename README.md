# verification-manager's-manager

PM Agent 플로우(회의/채팅 → 의미 판단 → 문서화 → 승인 → Notion 반영, + 마감일 리마인드)를
실제 서비스 제작 전에 무료 티어 도구만으로 검증하는 레포. 상세 설계는
[`implementation_plan.md`](implementation_plan.md), 작업 체크리스트는 [`TASKS.md`](TASKS.md),
수동 설정은 [`MANUAL_SETUP.md`](MANUAL_SETUP.md) 참고.

## Phase별 검증 내용

| Phase | 검증 대상 | 검증 방법 | 상태 |
|---|---|---|---|
| [00](phases/00-sample-audio) | 샘플 회의 오디오 | 파일 존재 + 재생 가능 여부 | ✅ |
| [01](phases/01-chat-polling) | Discord 채팅 폴링 | mock + 실제 REST API 호출, 신규 메시지 없을 때 빈 배열 | ✅ |
| [02](phases/02-meeting-transcribe) | 회의 전사 | faster-whisper(tiny)로 세그먼트 비어있지 않음 + 한국어 품질 육안 확인 | ✅ |
| [03](phases/03-semantic-judge) | 의미 있는 변화 판단 | Gemini로 의미 O/X 케이스 구분 (대화 조각 **단독** 판단 — 기존 Notion 항목 대비 비교는 미구현) | ⚠️ 부분 |
| [04](phases/04-doc-draft) | 문서 초안 생성 | 구조화 데이터(task/assignee/due_date) + 자연어 초안 육안 확인 | ✅ |
| [05](phases/05-pm-approval) | PM 승인 게이트 | Discord DM 버튼(수락/거절/보류) 실제 클릭 테스트 | ✅ 3개 버튼 전부 검증 |
| [06](phases/06-notion-sync) | Notion 반영 | dry-run payload 검증 + 실제 페이지 생성 확인 | ✅ |
| [07](phases/07-cycle-integration) | 로컬 통합 실행 | 00→02→03→04→05(mock)→06(dry-run) 체이닝, 에러 없이 완주 | ✅ |
| [08](.github/workflows) | GitHub Actions 연결 | job 체인 + 조건부 스킵(artifact로 데이터 전달) | ⚠️ process-meeting 1회 수동 실행만, chat-poll 반복 실행 미검증(비활성화 상태) |
| [09](phases/09-deadline-remind) | 마감일 리마인드 DM 루프 | 체크인→답장→(애매하면 체크리스트로 되묻기)→Notion 반영→마무리 메시지 | ⚠️ 애매한 답변 경로만 검증 |

⚠️ 항목별 세부 미검증 사유는 각 phase README 참고. 전체 미검증 목록 요약:

1. Notion 다중 뷰(간트/칸반/캘린더/담당자별) — 기술적 실현 가능성만 확인, 미구현
2. 회의록 오디오 아카이브 — Notion audio 블록 재생은 확인, 파일 직접 업로드는 미검증
3. 03의 기존 Notion 항목 대비 신규/수정 비교 — 설계만 하고 미구현
4. 09 담당자 다중 처리(Notion 이름↔Discord ID 조회) — 미구현, 고정 ID 한 명만
5. 09 GitHub Actions 자동 트리거(매일 cron) — 미구현
6. process-meeting.yml 자동 트리거(신규 오디오 업로드 시) — workflow_dispatch(수동)만 구현
7. chat-poll.yml 반복 스케줄 실행(5분 간격 2회 이상) — 미검증
8. 09 명확한 답변(단일 라운드 종료) 경로 — 미검증
