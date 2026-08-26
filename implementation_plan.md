# Implementation Plan — PM Agent 플로우 검증 파이프라인

## 0. 배경 / 목적

실제 서비스(디스코드 봇 + 상시 서버)를 만들기 전에, 아래 agent flow가 논리적으로 성립하는지를 GitHub Actions 기반으로 먼저 검증한다.

```
1-1. Discord Voice 녹음 → 전사
1-2. Discord 채팅 폴링
2.   의미 있는 변화 판단 (Schedule/담당자/일정 변경 등)
3.   문서화 초안/수정 생성
4.   PM 승인
5.   재폴링 + 사이클 반복 (새 회의 발생 시 1-1부터 재시작)
```

검증 대상은 "인프라가 완성됐는가"가 아니라 **"각 단계의 로직이 말이 되는가"** 다. 실시간 디스코드 음성봇 인프라(상시 프로세스 필요)는 이 검증 범위에서 제외하고, 사전 녹음된 샘플 오디오로 대체한다.

## 1. 핵심 제약조건 (반드시 지킬 것)

- **비용 $0.** 유료 API 절대 호출하지 않는다.
- STT는 `faster-whisper`(오픈소스, self-host)만 사용한다. `gpt-4o-transcribe`, Whisper API 등 유료 API 금지.
- LLM 호출(의미 판단, 문서화 초안)은 **Google Gemini API 무료 티어**만 사용한다(`gemini-2.5-flash` 또는 `gemini-2.5-flash-lite`). Claude API, OpenAI API는 상시 무료 티어가 없으므로 이번 검증 단계에서 사용하지 않는다.
- Discord Bot API, Notion API는 원래 무료이므로 그대로 사용.
- 오케스트레이션은 GitHub Actions(같은 레포 안 `.github/workflows/*.yml` 여러 개)로 처리한다. 레포는 **하나만** 만든다.
- 실시간 음성 캡처 봇(Pycord 상시 프로세스)은 이번 검증 범위 밖. `phases/00-sample-audio/`에 미리 녹음해둔 샘플 파일로 대체한다.

## 2. 디렉토리 구조

각 phase 디렉토리는 **독립적으로 실행·검증 가능**해야 한다. 즉 앞 단계가 실행되지 않은 상태에서도, `fixtures/`에 있는 샘플 입력만으로 그 디렉토리 하나를 단독 실행해서 결과를 확인할 수 있어야 한다.

```
repo/
├── implementation_plan.md
├── .github/
│   └── workflows/
│       ├── chat-poll.yml            # 1-2 → 2 → 3 → 4 → 6 (cron)
│       └── process-meeting.yml      # 00 → 1-1 → 2 → 3 → 4 → 6 (workflow_dispatch)
├── .env.example
├── requirements.txt
├── shared/
│   └── schemas.py                   # 단계 간 입출력 JSON 스키마 (pydantic 등)
└── phases/
    ├── 00-sample-audio/
    │   ├── README.md
    │   └── fixtures/sample_meeting.wav
    ├── 01-chat-polling/
    │   ├── run.py
    │   ├── README.md
    │   └── fixtures/sample_channel_messages.json
    ├── 02-meeting-transcribe/
    │   ├── run.py
    │   ├── README.md
    │   └── fixtures/ (00의 sample_meeting.wav 참조)
    ├── 03-semantic-judge/
    │   ├── run.py
    │   ├── README.md
    │   └── fixtures/sample_transcript.json
    ├── 04-doc-draft/
    │   ├── run.py
    │   ├── README.md
    │   └── fixtures/sample_judged_change.json
    ├── 05-pm-approval/
    │   ├── run.py                  # Discord DM + 수락/거절/보류 버튼으로 PM 승인 요청
    │   ├── README.md
    │   └── fixtures/sample_draft.json
    ├── 06-notion-sync/
    │   ├── run.py
    │   ├── README.md
    │   └── fixtures/sample_approved_doc.json
    └── 07-cycle-integration/
        ├── README.md               # 전체 통합 시나리오 체크리스트
        └── run_all_local.sh        # 로컬에서 00→06까지 순서대로 다 돌려보는 스크립트
```

## 3. Phase별 스펙

### phases/00-sample-audio
- 목적: 실시간 음성봇 없이도 뒷단(전사~반영)을 검증할 수 있도록, 팀 회의를 미리 한 번 녹음해서 넣어둔다.
- 산출물: `fixtures/sample_meeting.wav` (5~10분 분량이면 충분, 화자 2명 이상 포함)
- 검증 기준: 파일이 존재하고 재생 가능하면 통과. 코드 작성 불필요.

### phases/01-chat-polling
- 목적: Discord 채널의 최근 메시지를 REST API로 가져온다.
- 입력: 없음(직접 실행 시 fixtures 사용) / 실제 실행 시 `DISCORD_BOT_TOKEN`, `CHANNEL_ID` 환경변수
- 출력 스키마: `{"channel_id": str, "messages": [{"author": str, "content": str, "timestamp": str}]}`
- 독립 실행: `python phases/01-chat-polling/run.py --mock` → fixtures의 `sample_channel_messages.json`을 읽어 동일 스키마로 출력하는지 확인
- 실제 실행: `python phases/01-chat-polling/run.py --channel-id $CHANNEL_ID --since 1h`
- 통과 기준: mock/실제 모드 둘 다 위 출력 스키마를 만족하고, 새 메시지가 없을 때 빈 배열을 정상 반환한다.

### phases/02-meeting-transcribe
- 목적: `00`의 샘플 오디오를 `faster-whisper`로 전사한다.
- 입력: 오디오 파일 경로
- 출력 스키마: `{"segments": [{"speaker": str|null, "start": float, "end": float, "text": str}]}`
- 독립 실행: `python phases/02-meeting-transcribe/run.py --audio phases/00-sample-audio/fixtures/sample_meeting.wav --model tiny`
- 통과 기준: segments가 비어있지 않고, 한국어 텍스트가 읽을 수 있는 수준으로 나온다. (모델은 속도 위해 `tiny`/`base`로 시작, 품질 부족하면 `small`로 조정)
- 참고: 화자 분리(`speaker`)는 디스코드 사용자별 트랙을 쓸 경우 트랙 자체가 화자 정보를 담고 있으므로, 여기서는 단일 트랙 mono 파일 기준으로 `speaker: null`이어도 무방. 실제 서비스 전환 시에만 트랙별 처리로 보강.

### phases/03-semantic-judge
- 목적: 전사 결과(또는 채팅 폴링 결과)를 Gemini 무료 티어에 넣어 "의미 있는 변화"인지 판단.
- 입력 스키마: `{"source": "meeting"|"chat", "text": str}`
- 출력 스키마: `{"is_meaningful": bool, "category": "schedule"|"assignee"|"scope"|"decision"|"none", "confidence": float, "evidence": str}`
- 독립 실행: `python phases/03-semantic-judge/run.py --input fixtures/sample_transcript.json`
- 사용 모델: `gemini-2.5-flash-lite` (무료 티어 RPM이 더 넉넉함, 분당 30회)
- 통과 기준: 의미 있는 변화가 포함된 fixture와 의미 없는 잡담 fixture를 각각 하나씩 만들어서, 둘을 구분해내는지 확인 (최소 2개 케이스 테스트).

### phases/04-doc-draft
- 목적: `is_meaningful: true`인 결과를 받아 노션에 올릴 구조화 데이터 + 자연어 문서 초안을 생성.
- 입력 스키마: `03`의 출력 + 원문 텍스트
- 출력 스키마: `{"structured": {"task": str, "assignee": str|null, "due_date": str|null, "type": str}, "doc_text": str}`
- 독립 실행: `python phases/04-doc-draft/run.py --input fixtures/sample_judged_change.json`
- 통과 기준: `structured` 필드가 비어있지 않고, `doc_text`가 사람이 읽었을 때 자연스러운 한국어 문장인지 육안 확인.

### phases/05-pm-approval
- 목적: 사람(PM)이 승인해야 다음 단계(Notion 반영)로 넘어가는 게이트를 구현.
- **설계 변경**: 원안은 GitHub Environment(Required reviewers)로 게이트를 구현했으나, 실제
  서비스가 "PM에게 Discord DM으로 승인 요청을 보내고 버튼(수락/거절/보류)으로 응답받는" 구조로
  가는 게 확정되어 그에 맞춰 구현. (정식 서비스에서는 전용 웹페이지로 대체 예정이며, 이 단계는
  "사람이 눌러야 다음으로 넘어간다"는 게이트 로직만 검증한다.)
- `phases/05-pm-approval/run.py`: `discord.py`로 게이트웨이 접속 → `DISCORD_PM_USER_ID`에게
  DM으로 문서 초안 + 수락/거절/보류 버튼 전송 → 클릭 결과를 `decision`으로 반환 (5분 무응답 시 `held`)
- 입력 스키마: `04`의 출력 (`DocDraftOutput`)
- 출력 스키마: `{"decision": "approved"|"rejected"|"held", "structured": {...}, "doc_text": str}`
- 독립 실행: `python phases/05-pm-approval/run.py --mock` (실제 DM 없이 fixtures로 로직 확인) /
  `python phases/05-pm-approval/run.py --input fixtures/sample_draft.json` (실제 DM 전송)
- 통과 기준: PM이 DM으로 승인 요청과 버튼을 받고, 버튼을 누르면 그 결과(`decision`)가 정확히
  반영되어 스크립트가 종료되는 것을 확인 (수락/거절/보류 각각).

### phases/06-notion-sync
- 목적: 승인된 데이터를 실제 Notion 페이지/DB에 기록.
- 입력: `04`의 출력 스키마
- 독립 실행: `python phases/06-notion-sync/run.py --input fixtures/sample_approved_doc.json --dry-run` (dry-run은 실제 API 호출 없이 payload만 출력)
- 실제 실행: `--dry-run` 제거, `NOTION_API_KEY`, `NOTION_DATABASE_ID` 필요
- 통과 기준: dry-run 결과 payload가 Notion API 스펙에 맞고, 실제 실행 시 Notion 페이지에 새 행/블록이 생기는 것을 확인.

### phases/07-cycle-integration
- 목적: 00~06을 순서대로 한 번에 실행해서 전체 파이프라인이 로컬에서 끊기지 않고 도는지 확인. GitHub Actions로 옮기기 전 마지막 점검.
- `run_all_local.sh`: `00 오디오 → 02 전사 → 03 판단 → 04 초안 → (05는 로컬에서 스킵, 수동 y/n 프롬프트로 대체) → 06 dry-run` 순서로 셸에서 순차 실행
- 통과 기준: 스크립트가 에러 없이 끝까지 실행되고, 각 단계의 출력이 다음 단계 입력 스키마와 맞아 수동으로 값을 고치지 않아도 이어진다.

## 4. GitHub Actions 워크플로 연결

### `.github/workflows/chat-poll.yml`
- 트리거: `schedule` (검증 단계는 `*/5 * * * *`, 이후 운영 단계에서 1시간으로 조정)
- 순서: `01-chat-polling` → `03-semantic-judge` → (의미 있으면) `04-doc-draft` → `05-pm-approval`(Discord DM 승인 대기, 최대 5분) → `decision == approved`일 때만 `06-notion-sync`

### `.github/workflows/process-meeting.yml`
- 트리거: `workflow_dispatch` (input: 오디오 파일 경로 또는 레포 내 고정 경로 사용)
- 순서: `02-meeting-transcribe` → `03-semantic-judge` → `04-doc-draft` → `05-pm-approval`(Discord DM 승인 대기, 최대 5분) → `decision == approved`일 때만 `06-notion-sync`

두 워크플로 모두 `shared/schemas.py`의 스키마를 그대로 job 간 아티팩트(`actions/upload-artifact` / `download-artifact`)로 주고받는다. `05-pm-approval`은 GitHub Environment 승인 기능을 쓰지 않고
`run.py`가 job 스텝 안에서 직접 Discord DM을 보내고 버튼 클릭까지 대기한다.

## 5. 환경변수 / Secrets

`.env.example`에 아래 키를 정의하고, 실제 값은 로컬은 `.env`(gitignore), Actions는 repo Settings → Secrets에 등록:

```
DISCORD_BOT_TOKEN=
DISCORD_CHANNEL_ID=
DISCORD_PM_USER_ID=
GEMINI_API_KEY=
NOTION_API_KEY=
NOTION_DATABASE_ID=
```

## 6. Definition of Done

- [ ] `phases/00~06` 각 디렉토리를 fixtures만으로 단독 실행했을 때 전부 통과 기준을 만족한다.
- [ ] `07-cycle-integration/run_all_local.sh`가 로컬에서 끝까지 에러 없이 완주한다.
- [ ] `chat-poll.yml`이 5분 간격으로 최소 2회 이상 정상 실행되고, 의미 없는 폴링 결과에서는 04 이후 단계가 스킵된다.
- [ ] `process-meeting.yml`을 수동 실행(workflow_dispatch)해서 샘플 오디오가 전사→판단→초안→승인 대기까지 끊기지 않고 간다.
- [ ] PM이 Discord DM의 버튼(수락/거절/보류)을 눌러야 `decision`이 확정되고, `approved`일 때만 Notion 반영이 실행되는 것을 확인했다.
- [ ] 전체 과정에서 유료 API 호출이 0건이다(Gemini/GitHub Actions 무료 티어 한도 안에서 완료).