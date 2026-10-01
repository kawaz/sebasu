"""既存 Irodori 仮想環境でモデルを常駐させる音声合成ワーカー。"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tts-irodori-voicevox/Irodori-TTS"))
from irodori_tts.inference_runtime import InferenceRuntime, RuntimeKey, SamplingRequest, download_hf_checkpoint, save_wav

protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", buffering=1)
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
checkpoint = download_hf_checkpoint("Aratako/Irodori-TTS-v4.1-Small")
runtime = InferenceRuntime.from_key(RuntimeKey(checkpoint=str(checkpoint), model_device="mps", codec_device="mps"))
print("ready", file=protocol, flush=True)
for line in sys.stdin:
    request = json.loads(line)
    result = runtime.synthesize(SamplingRequest(text=request["text"], no_ref=True), log_fn=None)
    save_wav(request["path"], result.audio, result.sample_rate)
    print("done", file=protocol, flush=True)
