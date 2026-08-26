"""
승인된 문서 초안(shared.schemas.NotionSyncInput)을 Notion 데이터베이스에 페이지로 기록한다.

사용법:
    python phases/06-notion-sync/run.py --input phases/06-notion-sync/fixtures/sample_approved_doc.json --dry-run
    python phases/06-notion-sync/run.py --input phases/06-notion-sync/fixtures/sample_approved_doc.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from notion_client import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.schemas import NotionSyncInput  # noqa: E402

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def build_payload(data: NotionSyncInput, database_id: str) -> dict:
    s = data.structured

    properties = {
        "Name": {"title": [{"text": {"content": s.task}}]},
        "Type": {"select": {"name": s.type}},
    }
    if s.assignee:
        properties["Assignee"] = {"rich_text": [{"text": {"content": s.assignee}}]}
    if s.due_date and ISO_DATE_RE.match(s.due_date):
        properties["Due date"] = {"date": {"start": s.due_date}}

    doc_text = data.doc_text
    if s.due_date and not ISO_DATE_RE.match(s.due_date):
        # 상대 날짜("다음 주 금요일" 등)는 Notion date 프로퍼티에 못 넣으므로 본문에 남긴다.
        doc_text = f"{doc_text}\n(마감일: {s.due_date})"

    return {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": doc_text}}]},
            }
        ],
    }


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="NotionSyncInput 스키마의 JSON 파일 경로")
    parser.add_argument("--dry-run", action="store_true", help="실제 API 호출 없이 payload만 출력")
    args = parser.parse_args()

    data = NotionSyncInput.model_validate(json.loads(Path(args.input).read_text(encoding="utf-8")))

    database_id = os.environ.get("NOTION_DATABASE_ID")
    if not database_id:
        if not args.dry_run:
            raise RuntimeError("NOTION_DATABASE_ID 환경변수가 설정되어 있지 않습니다.")
        database_id = "DUMMY_DATABASE_ID"  # dry-run은 실제 DB 없이도 payload 모양만 확인 가능해야 함

    payload = build_payload(data, database_id)

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        raise RuntimeError("NOTION_API_KEY 환경변수가 설정되어 있지 않습니다.")

    client = Client(auth=api_key)
    page = client.pages.create(**payload)
    print(json.dumps({"page_id": page["id"], "url": page["url"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
