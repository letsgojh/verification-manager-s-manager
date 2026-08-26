# 02-meeting-transcribe

## 목적

오디오 파일을 `faster-whisper`로 전사해 공통 스키마(`shared.schemas.TranscribeOutput`)로 출력한다.
phase 03(semantic-judge)의 입력 소스 중 하나(`source: "meeting"`)로 쓰인다.

## 실행법

```bash
source venv/bin/activate
python phases/02-meeting-transcribe/run.py --audio phases/00-sample-audio/fixtures/sample_meeting.wav
python phases/02-meeting-transcribe/run.py --audio <path> --model small
```

## 출력 스키마

```json
{
  "segments": [
    {"speaker": null, "start": 0.0, "end": 6.9, "text": "string"}
  ]
}
```

`sample_meeting.wav`가 mono라 `speaker`는 항상 `null`이다(화자분리 미구현, phase 범위 밖).

## 모델 크기 선택 기준

기본값은 `tiny`. `phases/00-sample-audio/fixtures/sample_meeting.wav`(Zeroth-Korean 발화 이어붙인 합성
샘플)로 `tiny`/`base` 비교 결과:

- `tiny`: 세그먼트 다수 생성, 단어 단위 오류 존재(예: "장동련"→"장동량", "몬터규"→"모터 기운")하지만
  전체 의미는 알아볼 수 있는 수준
- `base`: 일부 단어는 개선되지만 오류가 여전히 남아있고, 구간을 통째로 건너뛰는 경우도 있어
  `tiny` 대비 뚜렷한 개선은 아님

이 프로젝트의 목적은 STT **파이프라인 로직** 검증(phase 03 이후 단계가 segments를 정상적으로
소비하는지)이지 전사 품질 자체가 아니므로, 기본은 `tiny`로 두고 실제 회의 녹음 투입 시 결과가
눈에 띄게 나쁘면 `--model base` 또는 `--model small`로 올려서 재확인한다.

## 통과 기준

- `--audio phases/00-sample-audio/fixtures/sample_meeting.wav --model tiny` 실행 시
  `segments`가 비어있지 않음
- 각 segment의 한국어 텍스트가 원문 의미를 알아볼 수 있는 수준임
  (`fixtures/sample_meeting_reference.txt`와 육안 비교, 완전 일치는 요구하지 않음)
