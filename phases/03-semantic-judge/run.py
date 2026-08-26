"""
회의/채팅 텍스트 한 조각이 문서화할 가치가 있는 의미 있는 변화인지 Gemini로 판단해
shared.schemas.SemanticJudgeOutput 형태로 stdout에 출력한다.

사용법:
    python phases/03-semantic-judge/run.py --input phases/03-semantic-judge/fixtures/sample_transcript.json
    python phases/03-semantic-judge/run.py --source chat --text "오늘 점심 뭐 먹지"
"""

import argparse
import json
import os
import sys
from pathlib import Path

import google.generativeai as genai
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.schemas import SemanticJudgeInput, SemanticJudgeOutput  # noqa: E402

# TASKS.md 원안은 gemini-2.5-flash-lite였으나, 신규 API 키에는 더 이상 제공되지 않아
# (404 "no longer available to new users") gemini-3.5-flash-lite로 대체했다.
MODEL_NAME = "gemini-3.5-flash-lite"

PROMPT_TEMPLATE = """당신은 회의/채팅 로그에서 문서화할 가치가 있는 의미 있는 변화만 걸러내는 판단기입니다.

아래 텍스트를 보고 다음 JSON 스키마로만 답하세요. 다른 설명은 절대 출력하지 마세요.

{{
  "is_meaningful": true 또는 false,
  "category": "schedule" | "assignee" | "scope" | "decision" | "none",
  "confidence": 0.0~1.0 사이 숫자,
  "evidence": "판단 근거가 되는 원문 발췌 또는 요약"
}}

판단 기준:
- is_meaningful=true는 일정 변경(schedule), 담당자 변경/지정(assignee), 작업 범위 변경(scope),
  명확한 결정사항(decision) 중 하나를 실제로 포함할 때만.
- 잡담, 인사, 감탄사, 마이크 테스트 등은 is_meaningful=false, category="none".
- 애매하면 confidence를 낮게 잡는다.

source: {source}
text: {text}
"""


def build_prompt(source: str, text: str) -> str:
    return PROMPT_TEMPLATE.format(source=source, text=text)


def run(source: str, text: str) -> SemanticJudgeOutput:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    response = model.generate_content(
        build_prompt(source, text),
        generation_config={"response_mime_type": "application/json"},
    )
    data = json.loads(response.text)
    return SemanticJudgeOutput.model_validate(data)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="SemanticJudgeInput 스키마의 JSON 파일 경로")
    parser.add_argument("--source", choices=["meeting", "chat"])
    parser.add_argument("--text")
    args = parser.parse_args()

    if args.input:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        judge_input = SemanticJudgeInput.model_validate(data)
    elif args.source and args.text:
        judge_input = SemanticJudgeInput(source=args.source, text=args.text)
    else:
        parser.error("--input 또는 (--source, --text)를 지정하세요.")

    output = run(judge_input.source, judge_input.text)
    print(output.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
