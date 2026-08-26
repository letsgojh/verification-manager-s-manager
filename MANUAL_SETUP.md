# 수동 설정 가이드

이 레포를 실제 모드(mock/dry-run 아님)로 돌리려면 코드 밖에서 사람이 직접 해야 하는 작업들.
`.env.example`의 각 키를 어디서 어떻게 얻는지 순서대로 정리했다. 완료 상태: 아래 전부 실제로
설정하고 검증까지 통과함 (phases 00~06).

```
DISCORD_BOT_TOKEN=
DISCORD_CHANNEL_ID=
DISCORD_PM_USER_ID=
GEMINI_API_KEY=
NOTION_API_KEY=
NOTION_DATABASE_ID=
```

---

## 1. Discord 봇 만들기 (`DISCORD_BOT_TOKEN`)

1. https://discord.com/developers/applications 접속 (Discord 로그인 필요)
2. **New Application** → 이름 입력(예: `meeting-bot`) → 생성
3. 왼쪽 메뉴 **Bot** 탭 → 처음이면 **Add Bot**, 이후엔 **Reset Token** → **Copy**
4. 복사한 값을 `.env`의 `DISCORD_BOT_TOKEN=`에 붙여넣기 (한 번만 보여주므로 바로 저장)

### 1-1. MESSAGE CONTENT INTENT 켜기 (필수)

같은 **Bot** 탭 → **Privileged Gateway Intents** 섹션 → **MESSAGE CONTENT INTENT** 토글 ON.
꺼져 있으면 `phases/01-chat-polling`이 메시지를 읽어도 `content`가 항상 빈 문자열로 온다.

### 1-2. 서버에 봇 초대 + 권한 부여

1. 왼쪽 메뉴 **OAuth2 → URL Generator**
2. SCOPES: `bot` 체크
3. BOT PERMISSIONS: `View Channel`, `Read Message History` 체크 (채팅 읽기만 하므로 `Send Messages`는 불필요)
4. 생성된 URL을 브라우저에서 열고, 봇을 넣을 서버 선택 → 초대
5. 이미 권한 없이 초대해버렸다면: 서버 설정 → **Roles** → 봇 이름의 역할 → `View Channel`,
   `Read Message History` 켜기 (또는 OAuth2 URL로 재초대해서 권한 갱신)

## 2. Discord 채널/유저 ID 얻기 (`DISCORD_CHANNEL_ID`, `DISCORD_PM_USER_ID`)

1. Discord 앱 → 좌측 하단 톱니바퀴(사용자 설정) → **고급(Advanced)** → **개발자 모드** 토글 ON
2. **채널 ID**: 봇이 메시지를 읽을 텍스트 채널(음성 채널 아님) 우클릭 → **채널 ID 복사** →
   `.env`의 `DISCORD_CHANNEL_ID=`
3. **PM 유저 ID**: 승인 DM을 받을 사람 우클릭 → **사용자 ID 복사** → `.env`의 `DISCORD_PM_USER_ID=`
   - 이 사람이 봇과 같은 서버에 있어야 봇이 DM을 보낼 수 있다 (1-2에서 초대한 서버에 있으면 됨)

## 3. Gemini API 키 (`GEMINI_API_KEY`)

1. https://aistudio.google.com/apikey 접속 (Google 계정 로그인)
2. **Create API key** → 키 복사
3. `.env`의 `GEMINI_API_KEY=`에 붙여넣기

> 참고: 원래 계획은 `gemini-2.5-flash-lite` 모델이었으나 신규 발급 키에는 더 이상 제공되지
> 않아(`404 no longer available to new users`) 코드에서 `gemini-3.5-flash-lite`로 대체했다
> (`phases/03-semantic-judge`, `phases/04-doc-draft`).

## 4. Notion 연동 (`NOTION_API_KEY`, `NOTION_DATABASE_ID`)

### 4-1. Integration 생성 → API 키

1. https://www.notion.so/my-integrations 접속
2. **New integration** → 이름 입력(예: `verification-bot`) → 연결할 워크스페이스 선택 → **Submit**
3. **Internal Integration Secret** 복사 (`ntn_`로 시작) → `.env`의 `NOTION_API_KEY=`

### 4-2. 대상 데이터베이스 생성

1. Notion에서 새 페이지 → **Table**(데이터베이스) 생성
2. 프로퍼티를 아래 이름으로 맞춘다 (`phases/06-notion-sync/run.py`가 이 이름을 그대로 씀):
   - `Name` — 제목(타이틀), 기본으로 있음
   - `Assignee` — Text
   - `Due date` — Date
   - `Type` — Select (옵션은 미리 안 만들어도 됨, API가 값 쓰면서 자동 생성)

### 4-3. Integration을 데이터베이스에 연결 (Connection)

**이 단계를 빼먹으면 API 키가 있어도 "object not found" 에러가 난다.**

1. 만든 데이터베이스 페이지 열기
2. 우측 상단 `...`(더보기) → **Connections**
3. 4-1에서 만든 Integration 검색해서 연결

### 4-4. Database ID 추출 → `.env`

데이터베이스 페이지를 브라우저에서 열면 주소창에 이런 형태의 URL이 뜬다:

```
https://www.notion.so/3c843ce9004a809c8c8ae174685ab78c?v=3c843ce9004a8003ae6b000c391512a4&source=copy_link
```

**`.env`에는 이 URL 전체가 아니라, `notion.so/` 뒤에 오는 32자리 영숫자(=Database ID)만
넣어야 한다.** (`?v=` 뒤쪽은 view ID라 다른 값이고 안 씀)

```
NOTION_DATABASE_ID=3c843ce9004a809c8c8ae174685ab78c
```

## 5. 다 넣은 뒤 확인 명령어

```bash
source venv/bin/activate

python phases/01-chat-polling/run.py --channel-id "$DISCORD_CHANNEL_ID"
python phases/05-pm-approval/run.py --input phases/05-pm-approval/fixtures/sample_draft.json
python phases/06-notion-sync/run.py --input phases/06-notion-sync/fixtures/sample_approved_doc.json --dry-run
python phases/06-notion-sync/run.py --input phases/06-notion-sync/fixtures/sample_approved_doc.json
```

## 자주 겪는 에러

- **Discord: `content`가 항상 빈 문자열** → 1-1(MESSAGE CONTENT INTENT) 안 켠 경우
- **Discord: 메시지를 못 읽거나 DM이 안 감** → 1-2(채널 권한) 또는 봇-PM이 같은 서버에 없는 경우
- **Notion: `APIResponseError: Could not find database ... make sure ... has permission`**
  → 4-3(Connections) 빼먹은 경우
- **Notion: `NOTION_DATABASE_ID`에 URL 전체가 들어간 경우** → 4-4처럼 32자리 ID만 남기기
- **Notion: `properties.XXX is not a property that exists`** → 4-2의 프로퍼티 이름이 DB와
  정확히 일치하는지 확인(대소문자, 띄어쓰기 포함)
- **Gemini: `404 ... no longer available to new users`** → 코드가 이미 `gemini-3.5-flash-lite`로
  고정되어 있으므로 재발생하지 않아야 함. 다른 모델명으로 직접 바꿨다면 원복.
