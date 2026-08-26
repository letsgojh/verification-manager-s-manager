"""
Zeroth-Korean(kresnik/zeroth_korean, CC BY 4.0) test split에서 서로 다른 화자 2명의
발화를 번갈아 이어붙여 5~10분 분량의 가짜 "회의 녹음" 샘플을 만든다.

실제 회의 녹음이 아니라 STT(phases/02) 검증용 대체 자료이므로,
자연스러운 회의 내용이 아니라 "화자 2명 이상 + 한국어 음성 + 5~10분" 조건만 맞추면 된다.

사용법:
    source venv/bin/activate
    python phases/00-sample-audio/build_sample.py
"""

import io

import soundfile as sf
import numpy as np
from datasets import load_dataset, Audio

TARGET_SECONDS = 6 * 60  # 6분 목표 (5~10분 범위)
OUT_PATH = "phases/00-sample-audio/fixtures/sample_meeting.wav"
SAMPLE_RATE = 16000
SILENCE_SECONDS = 0.4  # 화자 교대 사이 무음(턴 구분)


def _load_audio_array(raw):
    # decode=False로 받은 {"bytes": ..., "path": ...}를 soundfile로 직접 디코딩.
    # (최신 datasets는 decode=True일 때 torchcodec을 요구하므로 회피)
    if raw.get("bytes") is not None:
        data, sr = sf.read(io.BytesIO(raw["bytes"]), dtype="float32")
    else:
        data, sr = sf.read(raw["path"], dtype="float32")
    return data, sr


def main():
    ds = load_dataset("kresnik/zeroth_korean", split="test")
    ds = ds.cast_column("audio", Audio(decode=False))

    # speaker_id별로 묶기
    by_speaker = {}
    for ex in ds:
        by_speaker.setdefault(ex["speaker_id"], []).append(ex)

    speakers = sorted(by_speaker.keys())
    if len(speakers) < 2:
        raise RuntimeError("화자가 2명 미만입니다.")

    speaker_a, speaker_b = speakers[0], speakers[1]
    utts_a = by_speaker[speaker_a]
    utts_b = by_speaker[speaker_b]

    silence = np.zeros(int(SAMPLE_RATE * SILENCE_SECONDS), dtype=np.float32)

    chunks = []
    transcript_lines = []
    total_seconds = 0.0
    i = 0
    turn_speakers = [speaker_a, speaker_b]
    turn_utts = [utts_a, utts_b]

    while total_seconds < TARGET_SECONDS:
        turn = i % 2
        pool = turn_utts[turn]
        if not pool:
            break
        ex = pool[i // 2 % len(pool)]
        audio, sr = _load_audio_array(ex["audio"])
        if sr != SAMPLE_RATE:
            raise RuntimeError(f"예상치 못한 샘플레이트: {sr}")

        chunks.append(audio)
        chunks.append(silence)
        total_seconds += len(audio) / SAMPLE_RATE + SILENCE_SECONDS
        transcript_lines.append(f"[{turn_speakers[turn]}] {ex['text']}")
        i += 1

    combined = np.concatenate(chunks)
    sf.write(OUT_PATH, combined, SAMPLE_RATE)

    ref_path = OUT_PATH.replace(".wav", "_reference.txt")
    with open(ref_path, "w", encoding="utf-8") as f:
        f.write("\n".join(transcript_lines))

    print(f"wrote {OUT_PATH} ({total_seconds/60:.1f} min, speakers={speakers[:2]})")
    print(f"wrote reference transcript: {ref_path}")


if __name__ == "__main__":
    main()
