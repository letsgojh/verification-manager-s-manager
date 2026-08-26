# 00-sample-audio

## 목적

실시간 음성봇 없이도 뒷단(전사~반영)을 검증할 수 있도록, 실제 회의 녹음 대신
공개 데이터셋으로 만든 "가짜 회의 녹음" 샘플을 넣어둔다.

## 데이터 출처

- 데이터셋: [`kresnik/zeroth_korean`](https://huggingface.co/datasets/kresnik/zeroth_korean) (Zeroth-Korean, test split)
- 라이선스: CC BY 4.0 (출처 표기 조건으로 자유 이용 가능)
- 원 데이터는 낭독체 단문 발화(1인 화자당 여러 발화) 모음이라 회의 녹음이 아니다.
  `build_sample.py`가 **서로 다른 화자 2명**의 발화를 번갈아 이어붙여
  화자 교대가 있는 것처럼 보이는 약 6분 분량의 wav를 합성한다.
  → STT 파이프라인(phase 02) 로직 검증이 목적이므로, 내용의 회의 적합성보다
  "한국어 음성 + 화자 2명 이상 + 5~10분" 조건 충족이 중요하다.

## 산출물

- `fixtures/sample_meeting.wav` — 16kHz mono, 약 6분, 화자 2명 교대
- `fixtures/sample_meeting_reference.txt` — 이어붙인 원문 스크립트(화자 태그 포함). phase 02 전사 품질을 눈으로 비교할 때 참고용(정답지 아님, STT 산출물과 문장이 다를 수 있음)

## 재생성 방법

```bash
source venv/bin/activate
pip install datasets soundfile
python phases/00-sample-audio/build_sample.py
```

## 통과 기준

파일이 존재하고 재생 가능하면 통과. 코드 작성 불필요(생성 스크립트는 재현용 보조 도구).
