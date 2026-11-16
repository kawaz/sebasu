#!/usr/bin/env python3
"""HTTP API vs Python バインディングのベンチマーク比較"""
import time
import sys
import subprocess
import tempfile
import os

TEXT = "こんにちは、ずんだもんなのだ！今日もいい天気なのだ！"
SPEAKER_ID = 3  # ずんだもん
ENGINE_DIR = "voicevox_engine"

def bench_http_api(text, speaker_id, warmup=1, runs=5):
    """HTTP API方式のベンチマーク"""
    import requests

    # warmup
    for _ in range(warmup):
        q = requests.post(
            "http://localhost:50021/audio_query",
            params={"text": text, "speaker": speaker_id},
            timeout=10,
        ).json()
        requests.post(
            "http://localhost:50021/synthesis",
            params={"speaker": speaker_id},
            json=q,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

    # benchmark
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        q = requests.post(
            "http://localhost:50021/audio_query",
            params={"text": text, "speaker": speaker_id},
            timeout=10,
        ).json()
        wav = requests.post(
            "http://localhost:50021/synthesis",
            params={"speaker": speaker_id},
            json=q,
            headers={"Content-Type": "application/json"},
            timeout=10,
        ).content
        elapsed = time.perf_counter() - t0
        times.append(elapsed)

    return times


def bench_python_binding(text, speaker_id, runs=5):
    """Pythonバインディング方式のベンチマーク（初期化込み・初期化別）"""
    from pathlib import Path
    import multiprocessing
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile

    onnxruntime_path = f"{ENGINE_DIR}/libvoicevox_onnxruntime.dylib"
    dict_dir = f"{ENGINE_DIR}/engine_internal/pyopenjtalk/open_jtalk_dic_utf_8-1.11"

    # --- 初期化時間の計測 ---
    t_init_start = time.perf_counter()
    onnxruntime = Onnxruntime.load_once(filename=onnxruntime_path)
    synthesizer = Synthesizer(
        onnxruntime,
        OpenJtalk(dict_dir),
        acceleration_mode="AUTO",
        cpu_num_threads=multiprocessing.cpu_count(),
    )
    # ずんだもんのモデルを探してロード (speaker_id=3 は model 0.vvm に含まれる想定)
    for vvm_path in sorted(Path(f"{ENGINE_DIR}/model").glob("*.vvm")):
        try:
            with VoiceModelFile.open(vvm_path) as model:
                synthesizer.load_voice_model(model)
                # speaker_id が含まれるか確認
                metas = synthesizer.metas()
                found = any(
                    s.id == speaker_id
                    for m in metas
                    for s in m.styles
                )
                if found:
                    break
        except Exception:
            continue
    t_init = time.perf_counter() - t_init_start

    # --- 合成時間の計測 (warmup 1回) ---
    aq = synthesizer.create_audio_query(text, speaker_id)
    synthesizer.synthesis(aq, speaker_id)

    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        aq = synthesizer.create_audio_query(text, speaker_id)
        wav = synthesizer.synthesis(aq, speaker_id)
        elapsed = time.perf_counter() - t0
        times.append(elapsed)

    return t_init, times


def fmt_times(times):
    avg = sum(times) / len(times)
    mn = min(times)
    mx = max(times)
    return f"avg={avg:.3f}s  min={mn:.3f}s  max={mx:.3f}s  (n={len(times)})"


def main():
    runs = 5
    print(f"テキスト: {TEXT}")
    print(f"話者ID: {SPEAKER_ID} (ずんだもん)")
    print(f"実行回数: {runs}")
    print()

    # --- Python バインディング ---
    print("=" * 50)
    print("[Python バインディング]")
    print("  初期化中...")
    t_init, bind_times = bench_python_binding(TEXT, SPEAKER_ID, runs=runs)
    print(f"  初期化時間: {t_init:.3f}s")
    print(f"  合成時間:   {fmt_times(bind_times)}")
    print()

    # --- HTTP API ---
    print("=" * 50)
    print("[HTTP API (localhost:50021)]")
    # エンジンが起動しているか確認
    try:
        import requests
        requests.get("http://localhost:50021/version", timeout=1)
        print("  エンジン起動済み")
    except Exception:
        print("  エンジン未起動 → スキップ")
        print("  (vsay engine start で起動してから再実行)")
        return

    http_times = bench_http_api(TEXT, SPEAKER_ID, warmup=1, runs=runs)
    print(f"  合成時間:   {fmt_times(http_times)}")
    print()

    # --- 比較 ---
    print("=" * 50)
    print("[比較]")
    bind_avg = sum(bind_times) / len(bind_times)
    http_avg = sum(http_times) / len(http_times)
    print(f"  Python binding 合成: {bind_avg:.3f}s")
    print(f"  HTTP API 合成:       {http_avg:.3f}s")
    print(f"  Python binding 初期化: {t_init:.3f}s (毎回起動だとこれが加算)")
    print(f"  差分 (合成のみ): {abs(bind_avg - http_avg):.3f}s {'(binding が速い)' if bind_avg < http_avg else '(HTTP が速い)'}")


if __name__ == "__main__":
    main()
