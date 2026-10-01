#!/usr/bin/env python3
"""同じ 16 kHz 日本語 WAV でローカル音声認識を比較する。"""
import argparse
import json
import os
import statistics
import time
import unicodedata
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SAMPLES = {
    "A": (Path("/tmp/stt-ja-a.wav"), "こんにちは。これはイロドリ TTS のローカル動作テストです。"),
    "B": (Path("/tmp/say-ja.wav"), "明日の天気を教えて。リビングの電気を消して。"),
    "C": (Path("/tmp/say-ja-long.wav"), "明日の天気を教えて。リビングの電気を消して。今朝は少し肌寒いですね。週末は家族と公園に出かける予定です。おすすめの映画も教えてください。"),
}


def load_audio(path):
    with wave.open(str(path)) as src:
        assert src.getframerate() == 16000 and src.getnchannels() == 1 and src.getsampwidth() == 2, path
        samples = np.frombuffer(src.readframes(src.getnframes()), dtype="<i2").astype(np.float32) / 32768
    return samples


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).lower() if c.isalnum())


def cer(reference, hypothesis):
    a, b = normalize(reference), normalize(hypothesis)
    row = list(range(len(b) + 1))
    for i, char in enumerate(a, 1):
        next_row = [i]
        for j, other in enumerate(b, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (char != other)))
        row = next_row
    return round(row[-1] / len(a), 4)


def create_engine(name):
    if name == "mlx":
        import mlx_whisper
        from mlx_whisper.transcribe import ModelHolder
        repo = "mlx-community/whisper-large-v3-turbo"
        import mlx.core as mx
        ModelHolder.get_model(repo, mx.float16)
        return lambda audio: mlx_whisper.transcribe(audio, path_or_hf_repo=repo, language="ja")["text"].strip()
    if name == "faster":
        from faster_whisper import WhisperModel
        model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=8)
        return lambda audio: "".join(s.text for s in model.transcribe(audio, language="ja", beam_size=5)[0]).strip()
    if name == "cpp":
        from pywhispercpp.model import Model
        model = Model(str(ROOT / "models/kotoba/ggml-kotoba-whisper-v2.0-q5_0.bin"), redirect_whispercpp_logs_to=None, print_progress=False, language="ja")
        return lambda audio: "".join(s.text for s in model.transcribe(audio)).strip()
    if name == "sherpa":
        import sherpa_onnx
        base = ROOT / "models/reazonspeech"
        model = sherpa_onnx.OfflineRecognizer.from_transducer(
            tokens=str(base / "tokens.txt"), encoder=str(base / "encoder-epoch-99-avg-1.int8.onnx"),
            decoder=str(base / "decoder-epoch-99-avg-1.onnx"), joiner=str(base / "joiner-epoch-99-avg-1.onnx"),
            num_threads=4, sample_rate=16000, feature_dim=80,
        )

        def recognize(audio):
            stream = model.create_stream()
            stream.accept_waveform(16000, audio)
            model.decode_stream(stream)
            return stream.result.text.strip()
        return recognize
    if name == "streaming":
        import sherpa_onnx
        base = ROOT / "models/streaming"
        model = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(base / "tokens.txt"),
            encoder=str(base / "encoder-epoch-75-avg-11-chunk-16-left-128.int8.onnx"),
            decoder=str(base / "decoder-epoch-75-avg-11-chunk-16-left-128.onnx"),
            joiner=str(base / "joiner-epoch-75-avg-11-chunk-16-left-128.int8.onnx"),
            num_threads=4, sample_rate=16000, feature_dim=80, modeling_unit="bpe", bpe_vocab=str(base / "bpe.model"),
        )

        def recognize(audio):
            stream = model.create_stream()
            partials = []
            for start in range(0, len(audio), 1600):
                stream.accept_waveform(16000, audio[start:start + 1600])
                while model.is_ready(stream):
                    model.decode_stream(stream)
                text = model.get_result(stream)
                if text and (not partials or text != partials[-1]["text"]):
                    partials.append({"at_audio_sec": round(min(start + 1600, len(audio)) / 16000, 2), "text": text})
            stream.input_finished()
            while model.is_ready(stream):
                model.decode_stream(stream)
            result = model.get_result(stream)
            return result.strip(), partials
        return recognize
    raise ValueError(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=["mlx", "faster", "cpp", "sherpa", "streaming"])
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    start = time.perf_counter()
    engine = create_engine(args.engine)
    load_sec = time.perf_counter() - start
    results = []
    for label, (path, reference) in SAMPLES.items():
        audio = load_audio(path)
        durations = []
        for _ in range(args.runs):
            start = time.perf_counter()
            output = engine(audio)
            durations.append(time.perf_counter() - start)
        transcript, partials = output if isinstance(output, tuple) else (output, [])
        duration = len(audio) / 16000
        results.append({"sample": label, "audio_sec": round(duration, 3), "reference": reference,
                        "transcript": transcript, "cer": cer(reference, transcript),
                        "inference_sec_median": round(statistics.median(durations), 3),
                        "rtf": round(statistics.median(durations) / duration, 3),
                        "individual_runs_sec": [round(t, 3) for t in durations], "partials": partials})
    print(json.dumps({"engine": args.engine, "model_load_sec": round(load_sec, 3), "results": results}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
