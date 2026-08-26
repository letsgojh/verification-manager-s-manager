#!/usr/bin/env bash
# 00(오디오) → 02(전사) → 03(의미판단) → 04(문서초안) → 05(승인, --mock) → 06(Notion, --dry-run)
# 순서로 로컬에서 전부 실행해 파이프라인이 끊기지 않고 이어지는지 확인한다.
#
# 05는 실제 Discord DM을 기다리지 않고 --mock(무조건 수락)으로 대체한다. 실제 승인
# 흐름은 phases/05-pm-approval/README.md에서 별도로 검증한다.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [ -d venv ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

AUDIO_PATH="phases/00-sample-audio/fixtures/sample_meeting.wav"

echo "== 00: 샘플 오디오 확인 =="
if [ ! -f "$AUDIO_PATH" ]; then
  echo "샘플 오디오가 없습니다: $AUDIO_PATH" >&2
  echo "먼저 실행하세요: python phases/00-sample-audio/build_sample.py" >&2
  exit 1
fi
echo "OK: $AUDIO_PATH"

echo "== 02: 전사 =="
python phases/02-meeting-transcribe/run.py --audio "$AUDIO_PATH" --model tiny > "$WORKDIR/02_transcribe.json"
echo "OK: $(python -c "import json; print(len(json.load(open('$WORKDIR/02_transcribe.json'))['segments']))") segments"

echo "== 03: 의미 판단 =="
python - "$WORKDIR/02_transcribe.json" "$WORKDIR/03_input.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
text = " ".join(seg["text"] for seg in data["segments"])
json.dump({"source": "meeting", "text": text}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
PY
python phases/03-semantic-judge/run.py --input "$WORKDIR/03_input.json" > "$WORKDIR/03_judged.json"
cat "$WORKDIR/03_judged.json"

echo "== 04: 문서 초안 =="
python - "$WORKDIR/02_transcribe.json" "$WORKDIR/03_judged.json" "$WORKDIR/04_input.json" <<'PY'
import json, sys
transcribe = json.load(open(sys.argv[1], encoding="utf-8"))
judged = json.load(open(sys.argv[2], encoding="utf-8"))
text = " ".join(seg["text"] for seg in transcribe["segments"])
json.dump({"judged": judged, "text": text}, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False)
PY
python phases/04-doc-draft/run.py --input "$WORKDIR/04_input.json" > "$WORKDIR/04_draft.json"
cat "$WORKDIR/04_draft.json"

echo "== 05: PM 승인 (로컬 통합 실행이라 --mock으로 대체) =="
python phases/05-pm-approval/run.py --mock --input "$WORKDIR/04_draft.json" > "$WORKDIR/05_approval.json"
cat "$WORKDIR/05_approval.json"

DECISION="$(python -c "import json; print(json.load(open('$WORKDIR/05_approval.json'))['decision'])")"
if [ "$DECISION" != "approved" ]; then
  echo "승인되지 않음(decision=$DECISION) — 06 스킵" >&2
  exit 0
fi

echo "== 06: Notion 반영 (dry-run) =="
python - "$WORKDIR/05_approval.json" "$WORKDIR/06_input.json" <<'PY'
import json, sys
approval = json.load(open(sys.argv[1], encoding="utf-8"))
out = {"structured": approval["structured"], "doc_text": approval["doc_text"]}
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
PY
python phases/06-notion-sync/run.py --input "$WORKDIR/06_input.json" --dry-run

echo
echo "✅ 00 → 02 → 03 → 04 → 05(mock) → 06(dry-run) 전체 파이프라인 통과"
