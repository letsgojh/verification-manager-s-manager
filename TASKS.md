# 구현 작업 목록 (Phase별)

> 출처: `implementation_plan.md`. 각 phase는 독립적으로 실행·검증 가능해야 하므로, 순서대로 진행하되 앞 phase 완료를 기다리지 않고도 fixtures만으로 착수할 수 있다.

## Phase -1. 레포 공통 구조 (선행 작업)

- [x] 레포 초기화 (`git init`), `.gitignore` (`.env`, `__pycache__/`, `*.pyc`, `venv/` 등)
- [x] `requirements.txt` 작성 (`faster-whisper`, `google-generativeai`, `requests`, `notion-client`, `pydantic`, `python-dotenv`)
- [x] `.env.example` 작성 (섹션 5의 5개 키: `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `GEMINI_API_KEY`, `NOTION_API_KEY`, `NOTION_DATABASE_ID`)
- [x] `shared/schemas.py` — pydantic으로 각 phase 입출력 스키마 정의 (01~06에서 공통 재사용)
- [x] 디렉토리 스켈레톤 생성 (`phases/00-sample-audio` ~ `phases/07-cycle-integration`, 각 `README.md`/`fixtures/`)

## Phase 00. sample-audio

- [ ] `phases/00-sample-audio/fixtures/sample_meeting.wav` 준비 (5~10분, 화자 2명 이상, 실제 녹음 또는 TTS로 대체 생성)
- [ ] `phases/00-sample-audio/README.md` 작성 (파일 출처, 재생 확인 방법)
- [ ] 통과 기준 확인: 파일 존재 + 재생 가능 여부만 체크 (코드 불필요)

## Phase 01. chat-polling

- [ ] `phases/01-chat-polling/fixtures/sample_channel_messages.json` 작성 (출력 스키마와 동일한 형태의 mock 데이터)
- [ ] `phases/01-chat-polling/run.py` 구현
  - [ ] `--mock` 플래그: fixtures 읽어서 스키마대로 출력
  - [ ] 실제 모드: `DISCORD_BOT_TOKEN`, `--channel-id`, `--since` 로 Discord REST API 폴링
  - [ ] 출력 스키마: `{"channel_id": str, "messages": [{"author": str, "content": str, "timestamp": str}]}`
- [ ] `phases/01-chat-polling/README.md` 작성 (실행법, 스키마, 통과 기준)
- [ ] 검증: mock 모드 실행 + 실제 모드 실행(새 메시지 없을 때 빈 배열 반환 케이스 포함)

## Phase 02. meeting-transcribe

- [ ] `phases/02-meeting-transcribe/run.py` 구현 (`faster-whisper`, `--audio`, `--model` 인자)
  - [ ] 출력 스키마: `{"segments": [{"speaker": str|null, "start": float, "end": float, "text": str}]}`
  - [ ] `speaker`는 mono 파일 기준 `null` 허용
- [ ] `phases/02-meeting-transcribe/README.md` 작성 (모델 크기 선택 기준: tiny→small 튜닝 가이드 포함)
- [ ] 검증: `00`의 `sample_meeting.wav`를 `--model tiny`로 전사 → segments 비어있지 않은지, 한국어 텍스트 품질 확인. 필요 시 `base`/`small`로 조정

## Phase 03. semantic-judge

- [ ] `phases/03-semantic-judge/fixtures/sample_transcript.json` — 의미 있는 변화 포함 케이스
- [ ] `phases/03-semantic-judge/fixtures/` — 의미 없는 잡담 케이스 (최소 2개 fixture)
- [ ] `phases/03-semantic-judge/run.py` 구현
  - [ ] 입력: `{"source": "meeting"|"chat", "text": str}`
  - [ ] 출력: `{"is_meaningful": bool, "category": "schedule"|"assignee"|"scope"|"decision"|"none", "confidence": float, "evidence": str}`
  - [ ] Gemini `gemini-2.5-flash-lite` 호출 (`GEMINI_API_KEY`)
- [ ] `phases/03-semantic-judge/README.md` 작성
- [ ] 검증: 두 fixture(의미 O/X)가 올바르게 구분되는지 확인

## Phase 04. doc-draft

- [ ] `phases/04-doc-draft/fixtures/sample_judged_change.json` 작성 (03 출력 + 원문 텍스트 형태)
- [ ] `phases/04-doc-draft/run.py` 구현
  - [ ] 출력: `{"structured": {"task": str, "assignee": str|null, "due_date": str|null, "type": str}, "doc_text": str}`
  - [ ] Gemini 호출로 구조화 데이터 + 자연어 초안 생성
- [ ] `phases/04-doc-draft/README.md` 작성
- [ ] 검증: `structured` 비어있지 않음 + `doc_text` 육안 한국어 자연스러움 확인

## Phase 05. pm-approval (코드 없음, 설정 가이드)

- [ ] `phases/05-pm-approval/fixtures/sample_draft.json` 작성 (04 출력 예시)
- [ ] `phases/05-pm-approval/README.md`에 설정 절차 문서화
  - [ ] Settings → Environments → `pm-approval` 생성
  - [ ] Required reviewers 지정
  - [ ] `process-meeting.yml`/`chat-poll.yml`의 Notion job에 `environment: pm-approval` 추가 방법
- [ ] 검증: 실제 워크플로 실행 시 Notion job이 "Review pending"에서 멈추고 Approve 후에만 진행되는지 확인

## Phase 06. notion-sync

- [ ] `phases/06-notion-sync/fixtures/sample_approved_doc.json` 작성 (04 출력 스키마)
- [ ] `phases/06-notion-sync/run.py` 구현
  - [ ] `--dry-run`: 실제 API 호출 없이 payload만 출력
  - [ ] 실제 모드: `NOTION_API_KEY`, `NOTION_DATABASE_ID`로 Notion 페이지/DB에 기록
- [ ] `phases/06-notion-sync/README.md` 작성
- [ ] 검증: dry-run payload가 Notion API 스펙에 맞는지 확인 + 실제 실행 시 페이지/블록 생성 확인

## Phase 07. cycle-integration

- [ ] `phases/07-cycle-integration/run_all_local.sh` 작성
  - [ ] 순서: `00 오디오 → 02 전사 → 03 판단 → 04 초안 → (05는 y/n 프롬프트로 대체) → 06 --dry-run`
  - [ ] 각 단계 출력을 다음 단계 입력으로 자동 연결 (수동 값 수정 불필요)
- [ ] `phases/07-cycle-integration/README.md` — 통합 시나리오 체크리스트
- [ ] 검증: 스크립트가 에러 없이 끝까지 실행되는지 확인

## Phase 08. GitHub Actions 워크플로 연결

- [ ] `.github/workflows/chat-poll.yml` 작성
  - [ ] 트리거: `schedule` (`*/5 * * * *`, 검증 단계 기준)
  - [ ] 순서: `01` → `03` → (의미 있으면) `04` → `environment: pm-approval` → `06`
  - [ ] job 간 아티팩트 전달: `actions/upload-artifact` / `download-artifact`
- [ ] `.github/workflows/process-meeting.yml` 작성
  - [ ] 트리거: `workflow_dispatch` (오디오 경로 input)
  - [ ] 순서: `02` → `03` → `04` → `environment: pm-approval` → `06`
- [ ] 레포 Settings → Secrets에 `.env.example`의 5개 키 등록

## Phase 09. Definition of Done 최종 점검

- [ ] `phases/00~06` 각 디렉토리 fixtures만으로 단독 실행 시 전부 통과
- [ ] `07-cycle-integration/run_all_local.sh` 로컬 완주
- [ ] `chat-poll.yml` 5분 간격 최소 2회 정상 실행 + 의미 없는 결과일 때 04 이후 스킵 확인
- [ ] `process-meeting.yml` 수동 실행 → 전사~승인 대기까지 정상 진행 확인
- [ ] `pm-approval` environment에서 실제 Approve 후에만 Notion 반영되는 것 확인
- [ ] 전체 과정 유료 API 호출 0건 확인 (Gemini/Actions 무료 티어 내)
