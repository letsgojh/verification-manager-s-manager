"""
phase 04의 문서 초안을 PM에게 Discord 개인 DM으로 보내고, 수락/거절/보류 버튼을 눌러
응답할 때까지 기다린 뒤 shared.schemas.PmApprovalOutput 형태로 stdout에 출력한다.

향후 정식 서비스에서는 전용 웹페이지에서 승인을 받을 예정이지만, 이 검증 단계에서는
Discord DM + 버튼으로 "사람이 승인해야 다음 단계로 넘어간다"는 게이트 로직만 확인한다.

사용법:
    # mock: 실제 DM 없이 fixtures/sample_draft.json을 "수락"으로 간주하고 바로 출력
    python phases/05-pm-approval/run.py --mock

    # 실제: PM에게 DM을 보내고 버튼 클릭을 기다림 (DISCORD_BOT_TOKEN, DISCORD_PM_USER_ID 필요)
    python phases/05-pm-approval/run.py --input phases/05-pm-approval/fixtures/sample_draft.json
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import discord
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.schemas import DocDraftOutput, PmApprovalOutput  # noqa: E402

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sample_draft.json"
TIMEOUT_SECONDS = 300  # 5분 안에 응답 없으면 "보류"로 처리


class ApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=TIMEOUT_SECONDS)
        self.decision = None

    @discord.ui.button(label="수락", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.decision = "approved"
        await interaction.response.edit_message(content="✅ 수락 처리되었습니다.", view=None)
        self.stop()

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.decision = "rejected"
        await interaction.response.edit_message(content="❌ 거절 처리되었습니다.", view=None)
        self.stop()

    @discord.ui.button(label="보류", style=discord.ButtonStyle.secondary)
    async def hold(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.decision = "held"
        await interaction.response.edit_message(content="⏸️ 보류 처리되었습니다.", view=None)
        self.stop()


def _format_dm(draft: DocDraftOutput) -> str:
    s = draft.structured
    return (
        f"**[승인 요청 · {s.type}]**\n"
        f"작업: {s.task}\n"
        f"담당자: {s.assignee or '-'}\n"
        f"마감일: {s.due_date or '-'}\n\n"
        f"{draft.doc_text}"
    )


async def _request_approval(draft: DocDraftOutput, pm_user_id: str) -> str:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN 환경변수가 설정되어 있지 않습니다.")

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    decision_holder = {}

    @client.event
    async def on_ready():
        try:
            user = await client.fetch_user(int(pm_user_id))
            view = ApprovalView()
            await user.send(_format_dm(draft), view=view)
            timed_out = await view.wait()
            decision_holder["decision"] = "held" if timed_out else view.decision
        finally:
            await client.close()

    await client.start(token)
    return decision_holder.get("decision", "held")


def run_mock(input_path: str | None = None) -> PmApprovalOutput:
    path = Path(input_path) if input_path else FIXTURE_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    draft = DocDraftOutput.model_validate(data)
    return PmApprovalOutput(decision="approved", structured=draft.structured, doc_text=draft.doc_text)


def run_real(input_path: str, pm_user_id: str) -> PmApprovalOutput:
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    draft = DocDraftOutput.model_validate(data)
    decision = asyncio.run(_request_approval(draft, pm_user_id))
    return PmApprovalOutput(decision=decision, structured=draft.structured, doc_text=draft.doc_text)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="실제 DM 없이 '수락'으로 간주")
    parser.add_argument(
        "--input",
        help="DocDraftOutput 스키마의 JSON 파일 경로 (--mock과 같이 쓰면 fixtures 대신 이 파일을 사용)",
    )
    parser.add_argument("--pm-user-id", help="DM 받을 PM의 Discord 사용자 ID (기본: DISCORD_PM_USER_ID)")
    args = parser.parse_args()

    if args.mock:
        output = run_mock(args.input)
    else:
        pm_user_id = args.pm_user_id or os.environ.get("DISCORD_PM_USER_ID")
        if not args.input or not pm_user_id:
            parser.error("--mock이 아니면 --input과 --pm-user-id(또는 DISCORD_PM_USER_ID env)가 필요합니다.")
        output = run_real(args.input, pm_user_id)

    print(output.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
