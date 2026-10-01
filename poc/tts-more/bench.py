import argparse
import statistics
import subprocess
import time
import wave
from pathlib import Path

OUT = Path(__file__).parent / "out"
TEXTS = {
    "short": "はい、わかりました。",
    "mid": "こんにちは。これはイロドリ TTS のローカル動作テストです。",
    "long": "今日は早めに仕事を切り上げ、近くの公園へ散歩に出かけました。夕暮れの空を眺めながら、明日の予定をゆっくり考えています。帰り道には温かい飲み物を買います。",
}


def duration(path):
    with wave.open(str(path)) as wav:
        return wav.getnframes() / wav.getframerate()


def benchmark_say():
    start = time.perf_counter()
    subprocess.run(["/usr/bin/say", "-v", "Kyoko", "-o", str(OUT / "warmup.aiff"), "起動準備。"], check=True)
    (OUT / "warmup.aiff").unlink()
    print(f"say initialization: {time.perf_counter() - start:.3f}s")
    for name, text in TEXTS.items():
        path = OUT / f"say-kyoko-{name}.aiff"
        times = []
        for _ in range(3):
            start = time.perf_counter()
            subprocess.run(["/usr/bin/say", "-v", "Kyoko", "-o", str(path), text], check=True)
            times.append(time.perf_counter() - start)
        wav_path = OUT / f"say-kyoko-{name}.wav"
        subprocess.run(["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@22050", str(path), str(wav_path)], check=True)
        seconds = duration(wav_path)
        median = statistics.median(times)
        print(f"say-kyoko {name}: {median:.3f}s, audio {seconds:.3f}s, RTF {median / seconds:.3f}, trials {times}")
        path.unlink()


def benchmark_openjtalk():
    start = time.perf_counter()
    import pyopenjtalk
    import soundfile as sf
    print(f"pyopenjtalk module load: {time.perf_counter() - start:.3f}s")
    start = time.perf_counter()
    pyopenjtalk.tts("起動準備。")
    print(f"pyopenjtalk dictionary initialization: {time.perf_counter() - start:.3f}s")
    for name, text in TEXTS.items():
        path = OUT / f"pyopenjtalk-{name}.wav"
        times = []
        for _ in range(3):
            start = time.perf_counter()
            audio, sample_rate = pyopenjtalk.tts(text)
            times.append(time.perf_counter() - start)
        sf.write(path, audio, sample_rate)
        seconds = duration(path)
        median = statistics.median(times)
        print(f"pyopenjtalk {name}: {median:.3f}s, audio {seconds:.3f}s, RTF {median / seconds:.3f}, trials {times}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", choices=["say", "pyopenjtalk"])
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    {"say": benchmark_say, "pyopenjtalk": benchmark_openjtalk}[args.candidate]()
