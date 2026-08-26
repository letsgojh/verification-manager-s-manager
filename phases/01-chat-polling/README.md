# 01-chat-polling

## 목적

Discord 채널의 최근 메시지를 가져와 공통 스키마(`shared.schemas.ChatPollingOutput`)로 출력한다.
phase 03(semantic-judge)의 입력 소스 중 하나(`source: "chat"`)로 쓰인다.

## 실행법

```bash
source venv/bin/activate

# mock: fixtures/sample_channel_messages.json을 그대로 스키마 검증 후 출력
python phases/01-chat-polling/run.py --mock

# 실제: DISCORD_BOT_TOKEN 필요 (.env)
python phases/01-chat-polling/run.py --channel-id <채널ID>
python phases/01-chat-polling/run.py --channel-id <채널ID> --since 2026-08-25T09:00:00+00:00
```

`--since`를 주면 해당 timestamp(ISO8601) 이후 메시지만 반환한다. 새 메시지가 없으면
`messages`가 빈 배열인 결과를 출력한다(에러 아님).

## 출력 스키마

```json
{
  "channel_id": "string",
  "messages": [
    {"author": "string", "content": "string", "timestamp": "ISO8601 string"}
  ]
}
```

## 통과 기준

- `--mock` 실행 시 `fixtures/sample_channel_messages.json`이 스키마 검증을 통과하고 그대로 출력됨
- 실제 모드 실행 시 Discord REST API(`GET /channels/{id}/messages`)를 정상 호출하고,
  `--since` 이후 새 메시지가 없는 경우 `messages: []`를 반환함 (에러로 처리하지 않음)
- `--mock` 없이 `--channel-id` 누락 시 사용법 에러로 즉시 종료
