# 구현 작업 목록 (Phase별)

> 출처: `implementation_plan.md`. 각 phase는 독립적으로 실행·검증 가능해야 하므로, 순서대로 진행하되 앞 phase 완료를 기다리지 않고도 fixtures만으로 착수할 수 있다.

## Phase -1. 레포 공통 구조 (선행 작업)

- [x] 레포 초기화 (`git init`), `.gitignore` (`.env`, `__pycache__/`, `*.pyc`, `venv/` 등)
- [x] `requirements.txt` 작성 (`faster-whisper`, `google-generativeai`, `requests`, `notion-client`, `pydantic`, `python-dotenv`)
- [x] `.env.example` 작성 (섹션 5의 5개 키: `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `GEMINI_API_KEY`, `NOTION_API_KEY`, `NOTION_DATABASE_ID`)
- [x] `shared/schemas.py` — pydantic으로 각 phase 입출력 스키마 정의 (01~06에서 공통 재사용)
- [x] 디렉토리 스켈레톤 생성 (`phases/00-sample-audio` ~ `phases/07-cycle-integration`, 각 `README.md`/`fixtures/`)

## Phase 00. sample-audio

- [x] `phases/00-sample-audio/fixtures/sample_meeting.wav` 준비 (5~10분, 화자 2명 이상, 실제 녹음 또는 TTS로 대체 생성)
- [x] `phases/00-sample-audio/README.md` 작성 (파일 출처, 재생 확인 방법)
- [x] 통과 기준 확인: 파일 존재 + 재생 가능 여부만 체크 (코드 불필요)

## Phase 01. chat-polling

- [x] `phases/01-chat-polling/fixtures/sample_channel_messages.json` 작성 (출력 스키마와 동일한 형태의 mock 데이터)
- [x] `phases/01-chat-polling/run.py` 구현
  - [x] `--mock` 플래그: fixtures 읽어서 스키마대로 출력
  - [x] 실제 모드: `DISCORD_BOT_TOKEN`, `--channel-id`, `--since` 로 Discord REST API 폴링
  - [x] 출력 스키마: `{"channel_id": str, "messages": [{"author": str, "content": str, "timestamp": str}]}`
- [x] `phases/01-chat-polling/README.md` 작성 (실행법, 스키마, 통과 기준)
- [x] 검증: mock 모드 실행 + 실제 모드 실행(새 메시지 없을 때 빈 배열 반환 케이스 포함) — 실제 Discord 채널로 확인 완료

## Phase 02. meeting-transcribe

- [x] `phases/02-meeting-transcribe/run.py` 구현 (`faster-whisper`, `--audio`, `--model` 인자)
  - [x] 출력 스키마: `{"segments": [{"speaker": str|null, "start": float, "end": float, "text": str}]}`
  - [x] `speaker`는 mono 파일 기준 `null` 허용
- [x] `phases/02-meeting-transcribe/README.md` 작성 (모델 크기 선택 기준: tiny→small 튜닝 가이드 포함)
- [x] 검증: `00`의 `sample_meeting.wav`를 `--model tiny`로 전사 → segments 비어있지 않음(185줄) 확인, 한국어 텍스트 품질 확인(의미 파악 가능한 수준, `base`와 비교해도 뚜렷한 개선 없어 `tiny` 유지)

## Phase 03. semantic-judge

- [x] `phases/03-semantic-judge/fixtures/sample_transcript.json` — 의미 있는 변화 포함 케이스
- [x] `phases/03-semantic-judge/fixtures/` — 의미 없는 잡담 케이스 (최소 2개 fixture) — `sample_chitchat_1.json`, `sample_chitchat_2.json`
- [x] `phases/03-semantic-judge/run.py` 구현
  - [x] 입력: `{"source": "meeting"|"chat", "text": str}`
  - [x] 출력: `{"is_meaningful": bool, "category": "schedule"|"assignee"|"scope"|"decision"|"none", "confidence": float, "evidence": str}`
  - [x] Gemini 호출 (`GEMINI_API_KEY`) — 원안 `gemini-2.5-flash-lite`가 신규 키에 미제공되어 `gemini-3.5-flash-lite`로 대체
- [x] `phases/03-semantic-judge/README.md` 작성
- [x] 검증: 세 fixture(의미 O/X 2개)가 올바르게 구분됨 확인

## Phase 04. doc-draft

- [x] `phases/04-doc-draft/fixtures/sample_judged_change.json` 작성 (03 출력 + 원문 텍스트 형태)
- [x] `phases/04-doc-draft/run.py` 구현
  - [x] 출력: `{"structured": {"task": str, "assignee": str|null, "due_date": str|null, "type": str}, "doc_text": str}`
  - [x] Gemini 호출로 구조화 데이터 + 자연어 초안 생성 (모델은 03과 동일 사유로 `gemini-3.5-flash-lite`)
- [x] `phases/04-doc-draft/README.md` 작성
- [x] 검증: `structured` 비어있지 않음 + `doc_text` 육안 한국어 자연스러움 확인 — 통과

## Phase 05. pm-approval

> 설계 변경: GitHub Environment(Required reviewers) 대신 **Discord 개인 DM + 버튼(수락/거절/보류)**
> 방식으로 구현. 실제 서비스는 추후 전용 웹페이지로 대체 예정이며, 이 단계는 "사람이 승인해야
> 다음 단계로 넘어간다"는 게이트 로직 검증용.

- [x] `requirements.txt`에 `discord.py` 추가, `.env.example`에 `DISCORD_PM_USER_ID` 추가
- [x] `shared/schemas.py`에 `PmApprovalOutput` 추가 (`decision: approved|rejected|held` + structured + doc_text)
- [x] `phases/05-pm-approval/fixtures/sample_draft.json` 작성 (04 출력 예시)
- [x] `phases/05-pm-approval/run.py` 구현
  - [x] `--mock`: fixtures를 "수락"으로 간주하고 바로 출력
  - [x] 실제 모드: PM에게 DM으로 문서 초안 + 수락/거절/보류 버튼 전송, 클릭 결과 대기(5분 타임아웃 시 `held`)
- [x] `phases/05-pm-approval/README.md` 작성
- [x] 검증: mock 모드 + 실제 모드로 PM에게 DM 전송 후 수락/거절/보류 버튼 각각 클릭 →
  `decision: "approved"`/`"rejected"`/`"held"` 전부 정확히 반영됨 확인

## Phase 06. notion-sync

- [x] `phases/06-notion-sync/fixtures/sample_approved_doc.json` 작성 (04 출력 스키마)
- [x] `phases/06-notion-sync/run.py` 구현
  - [x] `--dry-run`: 실제 API 호출 없이 payload만 출력 (NOTION_DATABASE_ID 없어도 동작, 더미 ID 사용)
  - [x] 실제 모드: `NOTION_API_KEY`, `NOTION_DATABASE_ID`로 Notion 페이지/DB에 기록
- [x] `phases/06-notion-sync/README.md` 작성 (대상 DB 준비 절차 포함)
- [x] 검증: dry-run payload가 Notion API 스펙에 맞는지 확인 + 실제 실행 시 `verification-test` DB에 페이지 생성(Name/Assignee/Due date/Type 모두 정상 반영) 확인

## Phase 07. cycle-integration

- [x] `phases/07-cycle-integration/run_all_local.sh` 작성
  - [x] 순서: `00 오디오 → 02 전사 → 03 판단 → 04 초안 → 05(--mock으로 대체) → decision==approved면 06 --dry-run`
    (원안의 "y/n 프롬프트" 대신, 이제 05가 실제 코드가 있으므로 `--mock --input <04결과>`로 대체해
    스키마 호환성까지 같이 확인)
  - [x] 각 단계 출력을 다음 단계 입력으로 자동 연결 (수동 값 수정 불필요, 인라인 파이썬으로 변환)
- [x] `phases/07-cycle-integration/README.md` — 통합 시나리오 체크리스트
- [x] 검증: 스크립트가 에러 없이 끝까지 실행됨 확인 (exit code 0)

## Phase 08. GitHub Actions 워크플로 연결

> 설계 변경: [[05-pm-approval]]이 GitHub Environment 대신 Discord DM으로 바뀌어서,
> `environment: pm-approval` 대신 `05-pm-approval/run.py`를 job 스텝으로 직접 실행하고
> 그 `decision` 출력값으로 다음 job(`sync`) 실행 여부를 결정하는 구조로 변경.

- [x] `.github/workflows/chat-poll.yml` 작성
  - [x] 트리거: `schedule` (`*/5 * * * *`, 검증 단계 기준) + `workflow_dispatch`(수동 테스트용 추가)
  - [x] 순서: `poll(01)` → `judge(03, 의미 있으면 다음 진행)` → `draft(04)` → `approve(05, Discord DM 대기)` → `decision==approved면 sync(06)`
  - [x] job 간 아티팩트 전달: `actions/upload-artifact` / `download-artifact`
- [x] `.github/workflows/process-meeting.yml` 작성
  - [x] 트리거: `workflow_dispatch` (오디오 경로 input, 기본값은 00의 sample_meeting.wav)
  - [x] 순서: `transcribe(02)` → `judge(03)` → `draft(04)` → `approve(05)` → `decision==approved면 sync(06)`
    (원안엔 없었지만 chat-poll과 일관되게 04 전에 `is_meaningful` 게이트 추가)
- [ ] 레포 Settings → Secrets에 `.env.example`의 6개 키 등록 — **원격 저장소(GitHub remote)가
  아직 연결 안 되어 있어 대기 중.** repo 생성 + push 후 진행 필요.

**⚠️ 주의**: `chat-poll.yml`의 `schedule` 트리거는 default 브랜치에 merge된 순간부터 실제로
5분마다 자동 실행되어 Discord DM/Gemini/Notion 호출이 진짜로 발생한다(테스트 중 PM에게
반복 DM 갈 수 있음). merge 전에 `workflow_dispatch`로 먼저 1회 수동 테스트할 것.

## Phase 09. deadline-remind (신규, 대화 중 추가된 기능)

> 기존 00~08 파이프라인(회의/채팅 → 문서화)과는 별개의 새 기능. 마감일이 임박한 작업의
> 담당자에게 PM 말투로 진행 확인 DM을 보내고, 답장을 받아 완수 가능성을 판단해
> 응원/독촉 메시지를 이어서 보낸다. `implementation_plan.md`에는 없던 것을 대화 중 설계해
> 추가했다 (자세한 배경은 `phases/09-deadline-remind/README.md` 참고).

- [x] `shared/schemas.py`에 `DeadlineRemindInput`/`DeadlineRemindOutput` 추가
- [x] `.env.example`에 `DISCORD_ASSIGNEE_USER_ID` 추가
- [x] `phases/09-deadline-remind/fixtures/sample_task.json` 작성
- [x] `phases/09-deadline-remind/run.py` 구현
  - [x] D-3(기본값) 이내 작업만 진행, 아니면 `skipped: true`로 조용히 종료 (`--force`로 무시 가능)
  - [x] Gemini로 체크인 메시지 생성(인사+작업+D-day+진행 상황 질문 형식) → DM 발송
  - [x] 담당자 답장을 최대 5분 대기, 타임아웃 시 `assessment: "no_reply"`
  - [x] 답장 오면 Gemini로 완수 가능성 판단(`on_track`/`at_risk`) + 마무리 메시지 생성
    (질문으로 끝나지 않도록 명시 — PM 질문→담당자 답장→Notion 반영→PM 마무리로 정확히 끝남)
  - [x] 답장 받으면 Notion DB에 `progress_check` 페이지로 반영 (`06-notion-sync`의
    `build_payload()` 재사용) — 마무리 메시지 발송 전에 실행
  - [x] 마무리 메시지 발송 전 30~90초 랜덤 딜레이("입력 중..." 표시) — 즉답하면 봇 티가 나서 추가
- [x] `phases/09-deadline-remind/README.md` 작성 (MVP 단순화 범위, 대화 흐름 명시)
- [x] 검증: 실제 Discord DM으로 체크인→답장→Notion 반영→마무리 메시지까지 왕복 확인,
  답장 내용에 따라 `assessment`/메시지가 실제로 달라지는 것 확인, 무응답 타임아웃도 확인
- [ ] **MVP 범위 밖(향후 과제)**: 담당자 여러 명(Notion에서 이름↔Discord ID 조회), 기존 task
  페이지 업데이트(지금은 로그성 새 페이지만 생성), 매일 도는 GitHub Actions 워크플로 연결

## Phase 10. Definition of Done 최종 점검

- [ ] `phases/00~06` 각 디렉토리 fixtures만으로 단독 실행 시 전부 통과
- [ ] `07-cycle-integration/run_all_local.sh` 로컬 완주
- [ ] `chat-poll.yml` 5분 간격 최소 2회 정상 실행 + 의미 없는 결과일 때 04 이후 스킵 확인
- [ ] `process-meeting.yml` 수동 실행 → 전사~승인 대기까지 정상 진행 확인
- [ ] PM이 Discord DM의 버튼(수락/거절/보류)을 눌러야 `decision`이 확정되고, `approved`일 때만
  Notion 반영이 실행되는 것 확인 (GitHub Environment 아님, [[05-pm-approval]] 참고)
- [ ] 전체 과정 유료 API 호출 0건 확인 (Gemini/Actions 무료 티어 내)
