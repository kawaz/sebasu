#!/usr/bin/env python3
"""VOICEVOX の audio_query から WAV 受信完了までの時間を計測する。"""

import argparse
import statistics
import time

import requests

SPEAKER_ID = 3
TEXTS = {
    "短文": "はい、わかりました。",
    "中文": "こんにちは。これはイロドリ TTS のローカル動作テストです。",
    "長文": "今日は早めに仕事を切り上げ、近くの公園へ散歩に出かけました。夕暮れの空を眺めながら、明日の予定をゆっくり考えています。帰り道には温かい飲み物を買います。",
}


def synthesize(session, base_url, text):
    query_response = session.post(
        f"{base_url}/audio_query", params={"text": text, "speaker": SPEAKER_ID}, timeout=60
    )
    query_response.raise_for_status()
    audio_query = query_response.json()
    audio_query["speedScale"] = 1.2
    audio_query["pauseLength"] = 0.1
    audio_query["pauseLengthScale"] = 0.3
    audio_query["prePhonemeLength"] = 0.5
    count = 0
    for phrase in audio_query.get("accent_phrases", []):
        for mora in phrase.get("moras", []):
            if count >= 3:
                break
            if mora.get("pitch", 0) > 0:
                mora["pitch"] += 0.1
            if mora.get("vowel_length") is not None:
                mora["vowel_length"] *= 1.3
            count += 1
        if count >= 3:
            break
    synthesis_response = session.post(
        f"{base_url}/synthesis",
        params={"speaker": SPEAKER_ID},
        json=audio_query,
        timeout=120,
    )
    synthesis_response.raise_for_status()
    return len(synthesis_response.content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=int, help="VOICEVOX engine の待受ポート")
    args = parser.parse_args()
    base_url = f"http://127.0.0.1:{args.port}"
    with requests.Session() as session:
        for label, text in TEXTS.items():
            synthesize(session, base_url, text)
            times = []
            for _ in range(3):
                start = time.perf_counter()
                wav_bytes = synthesize(session, base_url, text)
                times.append(time.perf_counter() - start)
            print(f"{label}: {statistics.median(times):.3f} 秒 (試行: {', '.join(f'{t:.3f}' for t in times)}; WAV {wav_bytes} bytes)", flush=True)


if __name__ == "__main__":
    main()
