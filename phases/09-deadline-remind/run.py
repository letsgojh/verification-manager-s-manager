"""
마감일이 임박한(기본 3일 이내) 작업의 담당자에게 PM 말투로 진행 확인 DM을 보내고,
답장을 받으면 Gemini로 완수 가능성을 판단해 응원/독촉 메시지를 이어서 보낸다.

지금은 담당자를 Notion에서 조회하지 않고, 한 명(DISCORD_ASSIGNEE_USER_ID)에게만
--input으로 넘긴 작업 하나에 대해 보내는 단순화된 버전이다.

사용법:
    python phases/09-deadline-remind/run.py --input phases/09-deadline-remind/fixtures/sample_task.json
    python phases/09-deadline-remind/run.py --input <path> --force  # D-3 조건 무시하고 강제 실행
"""

import argparse
import asyncio
import importlib.util
import json
import os
import random
import sys
from datetime import date
from pathlib import Path

import discord
import google.generativeai as genai
from dotenv import load_dotenv
from notion_client import Client as NotionClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.schemas import DeadlineRemindInput, DeadlineRemindOutput, NotionSyncInput, StructuredChange  # noqa: E402


def _import_notion_sync():
    # 06-notion-sync/run.py의 build_payload()를 재사용 (디렉토리명에 하이픈이 있어 일반
    # import가 안 되므로 파일 경로로 직접 로드)
    path = Path(__file__).resolve().parents[1] / "06-notion-sync" / "run.py"
    spec = importlib.util.spec_from_file_location("notion_sync_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# phase 03/04와 동일한 이유로 gemini-2.5-flash-lite 대신 gemini-3.5-flash-lite 사용
MODEL_NAME = "gemini-3.5-flash-lite"
REMIND_THRESHOLD_DAYS = 3
# 답장 받자마자 바로 답하면 봇 티가 나므로, follow-up 전송 전 사람이 읽고 타이핑하는
# 것처럼 랜덤 딜레이를 준다.
FOLLOW_UP_MIN_DELAY_SECONDS = 30
FOLLOW_UP_MAX_DELAY_SECONDS = 90
REPLY_TIMEOUT_SECONDS = 300  # 5분 안에 답장 없으면 no_reply로 종료 (테스트용, 운영에선 더 길게)

# PM 말투 실제 샘플이 없어서 일단 컨텍스트 지침으로 대체. 나중에 실제 PM 메시지
# 샘플을 구하면 few-shot으로 바꿀 수 있다.
TONE_GUIDE = "정중하지만 부담을 주지 않는, 팀 리더다운 톤. 이모지나 과한 격식은 쓰지 않는다."

CHECK_IN_PROMPT = """당신은 PM입니다. 아래 작업을 맡은 담당자에게 진행 상황을 확인하는 DM을 보내려고 합니다.
{tone_guide}

반드시 아래 구성을 따르세요:
1. "안녕하세요 {assignee}님" 같은 인사로 시작
2. 어떤 작업인지 짧게 언급
3. 마감까지 D-{days_left}(며칠 남았는지)를 알려주기
4. "어디까지 진행하셨을까요?" 처럼 구체적인 진행 상황을 묻는 질문으로 마무리

한두 문장으로만 작성하세요. 따옴표나 설명 없이 메시지 본문만 출력하세요.

작업: {task}
담당자: {assignee}
마감일: {due_date} (D-{days_left})
"""

CLOSING_PROMPT = """당신은 PM입니다. 담당자에게 진행 상황을 물어봤고 아래와 같은 답장을 받았습니다.
{tone_guide}

작업: {task}
마감일: {due_date} (D-{days_left})
담당자 답장: {reply}

이 답장을 보고 마감일 안에 완수할 수 있을지 판단하세요.
- 완수 가능해 보이면: 짧게 응원하는 마무리 메시지를 작성하세요.
- 완수 어려워 보이면: 다그치지 않되 긴장감을 주는 마무리 메시지를 작성하세요.

**중요**: 이 메시지가 대화의 마지막입니다(PM 질문 → 담당자 답장 → 이 메시지로 종료).
절대 질문으로 끝내지 마세요. 담당자가 다시 답장할 필요가 없는, 확인/마무리하는 문장으로
작성하세요.

다음 JSON 스키마로만 답하세요. 다른 설명은 출력하지 마세요.
{{"assessment": "on_track" 또는 "at_risk", "message": "담당자에게 보낼 마무리 메시지"}}
"""


def _gemini_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)


def _days_left(due_date: str) -> int:
    return (date.fromisoformat(due_date) - date.today()).days


async def _run_dm_flow(task_input: DeadlineRemindInput, assignee_user_id: str, days_left: int) -> DeadlineRemindOutput:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN 환경변수가 설정되어 있지 않습니다.")

    model = _gemini_model()
    check_in_message = model.generate_content(
        CHECK_IN_PROMPT.format(
            tone_guide=TONE_GUIDE,
            task=task_input.task,
            assignee=task_input.assignee,
            due_date=task_input.due_date,
            days_left=days_left,
        )
    ).text.strip()

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    result = {}

    @client.event
    async def on_ready():
        try:
            user = await client.fetch_user(int(assignee_user_id))
            dm = await user.create_dm()
            await dm.send(check_in_message)

            def is_reply(message: discord.Message) -> bool:
                return message.author.id == int(assignee_user_id) and message.channel.id == dm.id

            try:
                reply_msg = await client.wait_for("message", check=is_reply, timeout=REPLY_TIMEOUT_SECONDS)
                reply_text = reply_msg.content
            except asyncio.TimeoutError:
                reply_text = None

            if reply_text is None:
                result["assessment"] = "no_reply"
            else:
                raw = model.generate_content(
                    CLOSING_PROMPT.format(
                        tone_guide=TONE_GUIDE,
                        task=task_input.task,
                        due_date=task_input.due_date,
                        days_left=days_left,
                        reply=reply_text,
                    ),
                    generation_config={"response_mime_type": "application/json"},
                ).text
                data = json.loads(raw)

                # PM 질문 -> 담당자 답장 -> Notion 반영 -> PM 마무리 메시지 순서를 지킨다.
                result["notion_synced"] = _sync_to_notion(task_input, days_left, reply_text, data)

                delay = random.uniform(FOLLOW_UP_MIN_DELAY_SECONDS, FOLLOW_UP_MAX_DELAY_SECONDS)
                async with dm.typing():
                    await asyncio.sleep(delay)
                await dm.send(data["message"])
                result["assessment"] = data["assessment"]
                result["closing_message"] = data["message"]
                result["assignee_reply"] = reply_text
        finally:
            await client.close()

    await client.start(token)

    return DeadlineRemindOutput(
        days_left=days_left,
        check_in_message=check_in_message,
        assignee_reply=result.get("assignee_reply"),
        assessment=result.get("assessment", "no_reply"),
        notion_synced=result.get("notion_synced", False),
        closing_message=result.get("closing_message"),
    )


def _sync_to_notion(task_input: DeadlineRemindInput, days_left: int, reply_text: str, closing: dict) -> bool:
    api_key = os.environ.get("NOTION_API_KEY")
    database_id = os.environ.get("NOTION_DATABASE_ID")
    if not api_key or not database_id:
        raise RuntimeError("NOTION_API_KEY / NOTION_DATABASE_ID 환경변수가 설정되어 있지 않습니다.")

    notion_sync = _import_notion_sync()
    sync_input = NotionSyncInput(
        structured=StructuredChange(
            task=task_input.task,
            assignee=task_input.assignee,
            due_date=task_input.due_date,
            type="progress_check",
        ),
        doc_text=(
            f"[D-{days_left} 진행 확인] 담당자 답장: {reply_text}\n"
            f"판단: {closing['assessment']}\n"
            f"PM 마무리 메시지: {closing['message']}"
        ),
    )
    payload = notion_sync.build_payload(sync_input, database_id)
    NotionClient(auth=api_key).pages.create(**payload)
    return True


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="DeadlineRemindInput 스키마의 JSON 파일 경로")
    parser.add_argument(
        "--assignee-user-id", help="DM 받을 담당자의 Discord 사용자 ID (기본: DISCORD_ASSIGNEE_USER_ID)"
    )
    parser.add_argument("--force", action="store_true", help=f"D-{REMIND_THRESHOLD_DAYS} 조건 무시하고 강제 실행")
    args = parser.parse_args()

    task_input = DeadlineRemindInput.model_validate(
        json.loads(Path(args.input).read_text(encoding="utf-8"))
    )
    days_left = _days_left(task_input.due_date)

    if not args.force and days_left > REMIND_THRESHOLD_DAYS:
        print(
            DeadlineRemindOutput(skipped=True, days_left=days_left).model_dump_json(indent=2)
        )
        return

    assignee_user_id = args.assignee_user_id or os.environ.get("DISCORD_ASSIGNEE_USER_ID")
    if not assignee_user_id:
        parser.error("--assignee-user-id 또는 DISCORD_ASSIGNEE_USER_ID env가 필요합니다.")

    output = asyncio.run(_run_dm_flow(task_input, assignee_user_id, days_left))
    print(output.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
