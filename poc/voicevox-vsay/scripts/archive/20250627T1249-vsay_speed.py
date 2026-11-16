#!/usr/bin/env python3
"""
vsayの応答速度を測定（音声生成のみ）
"""
import requests
import time

def measure_voicevox_api(text, speaker=3):
    """VOICEVOXのAPI応答速度を測定"""
    
    # クエリ生成時間
    start = time.time()
    params = {'text': text, 'speaker': speaker}
    query_response = requests.post(
        'http://localhost:50021/audio_query',
        params=params,
        timeout=5.0
    )
    query_time = time.time() - start
    
    audio_query = query_response.json()
    audio_query['speedScale'] = 1.2
    audio_query['pauseLength'] = 0.1
    audio_query['pauseLengthScale'] = 0.3
    
    # 合成時間
    start = time.time()
    synthesis_response = requests.post(
        'http://localhost:50021/synthesis',
        params={'speaker': speaker},
        json=audio_query,
        headers={'Content-Type': 'application/json'},
        timeout=10.0
    )
    synthesis_time = time.time() - start
    
    # 音声の長さを推定（44.1kHz, 16bit, モノラル）
    audio_size = len(synthesis_response.content)
    audio_duration = (audio_size - 44) / (44100 * 2)  # WAVヘッダー分を引く
    
    return query_time, synthesis_time, audio_duration

def main():
    print("=== VOICEVOX API速度測定（音声生成のみ）===\n")
    
    test_phrases = [
        "こんにちは",
        "今日はいい天気です",
        "バサラさんは最高なのだ",
        "音声合成のテストをしています",
    ]
    
    print("フレーズ | クエリ時間 | 合成時間 | 音声長 | 生成時間合計")
    print("-" * 70)
    
    total_query = 0
    total_synthesis = 0
    
    for phrase in test_phrases:
        query_time, synthesis_time, audio_duration = measure_voicevox_api(phrase)
        total_time = query_time + synthesis_time
        total_query += query_time
        total_synthesis += synthesis_time
        
        print(f"{phrase:<20} | {query_time:.3f}秒 | {synthesis_time:.3f}秒 | {audio_duration:.2f}秒 | {total_time:.3f}秒")
    
    print("-" * 70)
    print(f"平均 | {total_query/len(test_phrases):.3f}秒 | {total_synthesis/len(test_phrases):.3f}秒 | - | {(total_query+total_synthesis)/len(test_phrases):.3f}秒")
    
    print("\n※ 音声再生時間は含まれていません")
    print("※ 実際の体感レイテンシ = 生成時間 + 音声再生時間")

if __name__ == "__main__":
    main()