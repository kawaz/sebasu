#!/usr/bin/env python3
"""Load Irodori once, then synthesize three comparison sentences repeatedly."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "Irodori-TTS"))

from irodori_tts.inference_runtime import (  # noqa: E402
    InferenceRuntime,
    RuntimeKey,
    SamplingRequest,
    download_hf_checkpoint,
    save_wav,
)

TEXTS = {
    "short": "はい、わかりました。",
    "medium": "こんにちは。これはイロドリ TTS のローカル動作テストです。",
    "long": "今日は早めに仕事を切り上げ、近くの公園へ散歩に出かけました。夕暮れの空を眺めながら、明日の予定をゆっくり考えています。帰り道には温かい飲み物を買います。",
}


def main() -> None:
    checkpoint = download_hf_checkpoint("Aratako/Irodori-TTS-v4.1-Small")
    runtime = InferenceRuntime.from_key(
        RuntimeKey(checkpoint=str(checkpoint), model_device="mps", codec_device="mps")
    )
    output = ROOT / "out"
    output.mkdir(exist_ok=True)
    for run in range(1, 4):
        for label, text in TEXTS.items():
            result = runtime.synthesize(SamplingRequest(text=text, no_ref=True), log_fn=None)
            save_wav(output / f"bench-{label}-{run}.wav", result.audio, result.sample_rate)
            duration = result.audio.numel() / result.sample_rate
            print(f"{run} {label} total_to_decode={result.total_to_decode:.3f}s duration={duration:.3f}s", flush=True)


if __name__ == "__main__":
    main()
