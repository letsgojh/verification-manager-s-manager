"""
Discord 채널 메시지를 폴링해 shared.schemas.ChatPollingOutput 형태로 stdout에 출력한다.

사용법:
    python phases/01-chat-polling/run.py --mock
    python phases/01-chat-polling/run.py --channel-id <id> --since 2026-08-25T09:00:00+00:00
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.schemas import ChatMessage, ChatPollingOutput  # noqa: E402

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sample_channel_messages.json"
DISCORD_API_BASE = "https://discord.com/api/v10"


def run_mock() -> ChatPollingOutput:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return ChatPollingOutput.model_validate(data)


def run_real(channel_id: str, since: str | None) -> ChatPollingOutput:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN 환경변수가 설정되어 있지 않습니다.")

    resp = requests.get(
        f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
        headers={"Authorization": f"Bot {token}"},
        params={"limit": 100},
        timeout=10,
    )
    resp.raise_for_status()
    raw_messages = resp.json()

    messages = [
        ChatMessage(
            author=m["author"]["username"],
            content=m["content"],
            timestamp=m["timestamp"],
        )
        for m in raw_messages
        if since is None or m["timestamp"] > since
    ]
    # Discord는 최신순으로 반환하므로 시간순으로 뒤집는다.
    messages.reverse()

    return ChatPollingOutput(channel_id=channel_id, messages=messages)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="fixtures/sample_channel_messages.json 사용")
    parser.add_argument("--channel-id", help="실제 모드에서 사용할 Discord 채널 ID")
    parser.add_argument("--since", help="이 timestamp(ISO8601) 이후 메시지만 반환")
    args = parser.parse_args()

    if args.mock:
        output = run_mock()
    else:
        if not args.channel_id:
            parser.error("--mock이 아니면 --channel-id가 필요합니다.")
        output = run_real(args.channel_id, args.since)

    print(output.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
