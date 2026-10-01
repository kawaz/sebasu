#!/bin/sh
set -eu

cd "$(dirname "$0")/Irodori-TTS"
mkdir -p ../out
uv run --no-sync --python 3.11 python infer.py \
  --hf-checkpoint Aratako/Irodori-TTS-v4.1-Small \
  --text 'こんにちは。これはイロドリ TTS のローカル動作テストです。' \
  --no-ref \
  --model-device "${IRODORI_DEVICE:-mps}" \
  --codec-device "${IRODORI_DEVICE:-mps}" \
  --output-wav ../out/sample.wav
