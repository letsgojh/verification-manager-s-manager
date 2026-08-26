"""
마감일이 임박한(기본 3일 이내) 작업의 담당자에게 PM 말투로 진행 확인 DM을 보낸다.

- 답장이 명확하면(예: "다 끝냈습니다") 바로 체크리스트를 채우고 마무리한다.
- 답장이 애매하면(예: "어느 정도 했는데 다 될지 모르겠어요") 작업을 하위 항목
  체크리스트로 쪼개서 항목별 진행 여부를 되묻고, 두 번째 답장으로 체크리스트를 채운다.
- 체크리스트가 확정되면 Notion에 체크박스(to_do 블록)로 반영한 뒤, 질문으로 끝나지 않는
  PM 마무리 메시지를 보낸다.

진행률(%)은 따로 계산하지 않는다 — 체크리스트 항목의 done/not done만 본다.

지금은 담당자를 Notion에서 조회하지 않고, 한 명(DISCORD_ASSIGNEE_USER_ID)에게만
--input으로 넘긴 작업 하나에 대해 보내는 단순화된 버전이다.

사용법:
    python phases/09-deadline-remind/run.py --input phases/09-deadline-remind/fixtures/sample_task.json
    python phases/09-deadline-remind/run.py --input <path> --force  # D-3 조건 무시하고 강제 실행
"""

import argparse
import asyncio
import json
import os
import random
import re
import sys
from datetime import date
from pathlib import Path

import discord
import google.generativeai as genai
from dotenv import load_dotenv
from notion_client import Client as NotionClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.schemas import DeadlineRemindInput, DeadlineRemindOutput  # noqa: E402

# phase 03/04와 동일한 이유로 gemini-2.5-flash-lite 대신 gemini-3.5-flash-lite 사용
MODEL_NAME = "gemini-3.5-flash-lite"
REMIND_THRESHOLD_DAYS = 3
# 답장 받자마자 바로 답하면 봇 티가 나므로, 마무리 메시지 전송 전 사람이 읽고 타이핑하는
# 것처럼 랜덤 딜레이를 준다.
REPLY_DELAY_MIN_SECONDS = 30
REPLY_DELAY_MAX_SECONDS = 90
REPLY_TIMEOUT_SECONDS = 300  # 5분 안에 답장 없으면 no_reply로 종료 (테스트용, 운영에선 더 길게)

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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

FIRST_ASSESS_PROMPT = """당신은 PM입니다. 담당자에게 진행 상황을 물어봤고 아래와 같은 답장을 받았습니다.
{tone_guide}

작업: {task}
마감일: {due_date} (D-{days_left})
담당자 답장: {reply}

이 답장만으로 작업을 하위 항목별로 얼마나 진행했는지 명확히 판단할 수 있는지 보세요.

- 명확하다면(예: "다 끝냈습니다", "전부 완료했습니다" 등): clear=true로 하고, 작업을
  체크리스트 항목 1~3개로 나눠 답장 내용에 맞게 각 항목의 done을 true/false로 채우세요.
  그리고 마감일 안에 완수 가능한지 판단해 assessment("on_track" 또는 "at_risk")와
  마무리 메시지(message)도 함께 작성하세요. 마무리 메시지는 절대 질문으로 끝내지 마세요.
- 불명확하다면(예: "어느 정도 했는데 다 될지 모르겠다"처럼 구체성이 없는 답변): clear=false로
  하고, 작업을 구체적인 하위 항목 2~4개로 나눠 체크리스트를 만들되 각 항목의 done은
  아직 모르니 null로 두세요. 그 항목들을 번호로 나열하며 각각 어느 정도 진행했는지
  물어보는 clarifying_question을 작성하세요(예: "1. ... 2. ... 3. ... 에 대해 각각 어느
  정도 진행하셨는지 알려주실 수 있나요?"). 이 경우 assessment와 message는 null로 두세요.

다음 JSON 스키마로만 답하세요. 다른 설명 없이.
{{
  "clear": true 또는 false,
  "checklist": [{{"item": "string", "done": true 또는 false 또는 null}}, ...],
  "clarifying_question": "string 또는 null",
  "assessment": "on_track" 또는 "at_risk" 또는 null,
  "message": "string 또는 null"
}}
"""

SECOND_ASSESS_PROMPT = """당신은 PM입니다. 아래 작업을 체크리스트로 나눠서 담당자에게 항목별
진행 상황을 다시 물어봤고 답장을 받았습니다.
{tone_guide}

작업: {task}
마감일: {due_date} (D-{days_left})
체크리스트: {checklist_json}
담당자의 두 번째 답장: {reply}

답장 내용을 바탕으로 각 체크리스트 항목의 완료 여부(done: true/false)를 확정하고,
전체적으로 마감일 안에 완수 가능할지 판단하세요(assessment: "on_track" 또는 "at_risk").

**중요**: 이 마무리 메시지가 대화의 마지막입니다. 절대 질문으로 끝내지 마세요. 담당자가
다시 답장할 필요가 없는, 확인/마무리하는 문장으로 작성하세요.

다음 JSON 스키마로만 답하세요. 다른 설명 없이.
{{
  "checklist": [{{"item": "string", "done": true 또는 false}}, ...],
  "assessment": "on_track" 또는 "at_risk",
  "message": "담당자에게 보낼 마무리 메시지"
}}
"""


def _gemini_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)


def _generate_json(model, prompt: str) -> dict:
    raw = model.generate_content(
        prompt, generation_config={"response_mime_type": "application/json"}
    ).text
    return json.loads(raw)


def _days_left(due_date: str) -> int:
    return (date.fromisoformat(due_date) - date.today()).days


async def _wait_for_reply(client: discord.Client, assignee_user_id: str, dm: discord.DMChannel):
    def is_reply(message: discord.Message) -> bool:
        return message.author.id == int(assignee_user_id) and message.channel.id == dm.id

    try:
        msg = await client.wait_for("message", check=is_reply, timeout=REPLY_TIMEOUT_SECONDS)
        return msg.content
    except asyncio.TimeoutError:
        return None


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
    result = {"assessment": "no_reply"}

    @client.event
    async def on_ready():
        try:
            user = await client.fetch_user(int(assignee_user_id))
            dm = await user.create_dm()
            await dm.send(check_in_message)

            reply1 = await _wait_for_reply(client, assignee_user_id, dm)
            if reply1 is None:
                return
            result["assignee_reply"] = reply1

            first = _generate_json(
                model,
                FIRST_ASSESS_PROMPT.format(
                    tone_guide=TONE_GUIDE,
                    task=task_input.task,
                    due_date=task_input.due_date,
                    days_left=days_left,
                    reply=reply1,
                ),
            )

            if first["clear"]:
                checklist = first["checklist"]
                assessment = first["assessment"]
                message = first["message"]
            else:
                # 애매한 답변 -> 체크리스트로 쪼개서 되묻는다.
                clarifying_question = first["clarifying_question"]
                result["clarifying_question"] = clarifying_question
                async with dm.typing():
                    await asyncio.sleep(random.uniform(REPLY_DELAY_MIN_SECONDS, REPLY_DELAY_MAX_SECONDS))
                await dm.send(clarifying_question)

                reply2 = await _wait_for_reply(client, assignee_user_id, dm)
                if reply2 is None:
                    return
                result["assignee_reply_2"] = reply2

                second = _generate_json(
                    model,
                    SECOND_ASSESS_PROMPT.format(
                        tone_guide=TONE_GUIDE,
                        task=task_input.task,
                        due_date=task_input.due_date,
                        days_left=days_left,
                        checklist_json=json.dumps(first["checklist"], ensure_ascii=False),
                        reply=reply2,
                    ),
                )
                checklist = second["checklist"]
                assessment = second["assessment"]
                message = second["message"]

            result["checklist"] = checklist
            result["assessment"] = assessment

            # 담당자 답장 -> Notion 반영 -> PM 마무리 메시지 순서를 지킨다.
            result["notion_synced"] = _sync_to_notion(task_input, days_left, checklist, assessment, message)

            async with dm.typing():
                await asyncio.sleep(random.uniform(REPLY_DELAY_MIN_SECONDS, REPLY_DELAY_MAX_SECONDS))
            await dm.send(message)
            result["closing_message"] = message
        finally:
            await client.close()

    await client.start(token)

    return DeadlineRemindOutput(
        days_left=days_left,
        check_in_message=check_in_message,
        assignee_reply=result.get("assignee_reply"),
        clarifying_question=result.get("clarifying_question"),
        assignee_reply_2=result.get("assignee_reply_2"),
        checklist=result.get("checklist"),
        assessment=result.get("assessment", "no_reply"),
        notion_synced=result.get("notion_synced", False),
        closing_message=result.get("closing_message"),
    )


def _sync_to_notion(task_input: DeadlineRemindInput, days_left: int, checklist: list, assessment: str, message: str) -> bool:
    api_key = os.environ.get("NOTION_API_KEY")
    database_id = os.environ.get("NOTION_DATABASE_ID")
    if not api_key or not database_id:
        raise RuntimeError("NOTION_API_KEY / NOTION_DATABASE_ID 환경변수가 설정되어 있지 않습니다.")

    properties = {
        "Name": {"title": [{"text": {"content": task_input.task}}]},
        "Type": {"select": {"name": "progress_check"}},
        "Assignee": {"rich_text": [{"text": {"content": task_input.assignee}}]},
    }
    if ISO_DATE_RE.match(task_input.due_date):
        properties["Due date"] = {"date": {"start": task_input.due_date}}

    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"[D-{days_left} 진행 확인] 판단: {assessment}"}}
                ]
            },
        }
    ]
    for item in checklist:
        children.append(
            {
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"type": "text", "text": {"content": item["item"]}}],
                    "checked": bool(item.get("done")),
                },
            }
        )

    payload = {"parent": {"database_id": database_id}, "properties": properties, "children": children}
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
