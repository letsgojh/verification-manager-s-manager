"""
오디오 파일을 faster-whisper로 전사해 shared.schemas.TranscribeOutput 형태로 stdout에 출력한다.

사용법:
    python phases/02-meeting-transcribe/run.py --audio phases/00-sample-audio/fixtures/sample_meeting.wav
    python phases/02-meeting-transcribe/run.py --audio <path> --model small
"""

import argparse
import sys
from pathlib import Path

from faster_whisper import WhisperModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.schemas import TranscribeOutput, TranscriptSegment  # noqa: E402


def run(audio_path: str, model_size: str) -> TranscribeOutput:
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio_path, language="ko")

    output_segments = [
        TranscriptSegment(speaker=None, start=seg.start, end=seg.end, text=seg.text.strip())
        for seg in segments
    ]
    return TranscribeOutput(segments=output_segments)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True, help="전사할 wav 파일 경로")
    parser.add_argument("--model", default="tiny", help="faster-whisper 모델 크기 (tiny/base/small/...)")
    args = parser.parse_args()

    output = run(args.audio, args.model)
    print(output.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
