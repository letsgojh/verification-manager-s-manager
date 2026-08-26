"""
phase 03의 판단 결과(SemanticJudgeOutput) + 원문 텍스트를 받아 Gemini로 구조화 데이터와
자연어 문서 초안을 생성해 shared.schemas.DocDraftOutput 형태로 stdout에 출력한다.

사용법:
    python phases/04-doc-draft/run.py --input phases/04-doc-draft/fixtures/sample_judged_change.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

import google.generativeai as genai
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.schemas import DocDraftInput, DocDraftOutput, StructuredChange  # noqa: E402

# phase 03과 동일한 이유로 gemini-2.5-flash-lite 대신 gemini-3.5-flash-lite 사용
MODEL_NAME = "gemini-3.5-flash-lite"

PROMPT_TEMPLATE = """당신은 회의/채팅에서 나온 변경 사항을 팀 문서(작업 관리 도구 항목)로 정리하는 어시스턴트입니다.

아래는 이미 "문서화할 가치가 있다"고 판단된 내용입니다. 이 내용을 보고 다음 JSON 스키마로만 답하세요.
다른 설명은 절대 출력하지 마세요.

{{
  "task": "무엇을 해야 하는지 한 문장으로",
  "assignee": "담당자 이름 (텍스트에 명시되지 않으면 null)",
  "due_date": "마감일 (텍스트에 명시되지 않으면 null, 명시되면 가능한 한 YYYY-MM-DD 형식, 상대 날짜면 원문 표현 그대로)",
  "doc_text": "이 변경사항을 팀 문서에 남길 자연스러운 한국어 한두 문장 초안"
}}

분류(category): {category}
근거(evidence): {evidence}
원문 텍스트: {text}
"""


def build_prompt(judged, text: str) -> str:
    return PROMPT_TEMPLATE.format(category=judged.category, evidence=judged.evidence, text=text)


def run(doc_input: DocDraftInput) -> DocDraftOutput:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    response = model.generate_content(
        build_prompt(doc_input.judged, doc_input.text),
        generation_config={"response_mime_type": "application/json"},
    )
    data = json.loads(response.text)

    structured = StructuredChange(
        task=data["task"],
        assignee=data.get("assignee"),
        due_date=data.get("due_date"),
        type=doc_input.judged.category,
    )
    return DocDraftOutput(structured=structured, doc_text=data["doc_text"])


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="DocDraftInput 스키마의 JSON 파일 경로")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    doc_input = DocDraftInput.model_validate(data)

    output = run(doc_input)
    print(output.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
