#!/usr/bin/env python3
"""
VOICEVOXのアクセント・イントネーション調整のテスト
"""
import requests
import json
import time

def generate_with_accent_phrase(text, speaker_id, modifications=None):
    """アクセント句を調整して音声を生成"""
    
    # 音声クエリの生成
    params = {'text': text, 'speaker': speaker_id}
    query_response = requests.post(
        'http://localhost:50021/audio_query',
        params=params
    )
    audio_query = query_response.json()
    
    # アクセント句の確認と調整
    print(f"\n元のアクセント句:")
    for i, phrase in enumerate(audio_query['accent_phrases']):
        print(f"  {i}: {phrase['pause_mora']}") if 'pause_mora' in phrase else None
        for j, mora in enumerate(phrase['moras']):
            text = mora['text']
            pitch = mora['pitch']
            print(f"    [{j}] {text}: pitch={pitch}")
    
    # アクセントの調整
    if modifications:
        for mod in modifications:
            phrase_idx = mod['phrase']
            mora_idx = mod['mora']
            new_pitch = mod['pitch']
            if phrase_idx < len(audio_query['accent_phrases']):
                if mora_idx < len(audio_query['accent_phrases'][phrase_idx]['moras']):
                    audio_query['accent_phrases'][phrase_idx]['moras'][mora_idx]['pitch'] = new_pitch
                    print(f"\n✓ 調整: 句{phrase_idx} モーラ{mora_idx} → pitch={new_pitch}")
    
    return audio_query

def test_basara_accent():
    """バサラさんのアクセントパターンをテスト"""
    
    print("=== VOICEVOXアクセント調整テスト ===\n")
    
    # テスト対象
    test_cases = [
        {
            'name': 'オリジナル',
            'text': 'バサラさんはすごいのだ！',
            'speaker': 3,
            'modifications': None
        },
        {
            'name': '平板型（フラット）',
            'text': 'バサラさんはすごいのだ！',
            'speaker': 3,
            'modifications': [
                {'phrase': 0, 'mora': 0, 'pitch': 5.0},  # バ
                {'phrase': 0, 'mora': 1, 'pitch': 5.0},  # サ
                {'phrase': 0, 'mora': 2, 'pitch': 5.0},  # ラ
                {'phrase': 0, 'mora': 3, 'pitch': 5.0},  # さ
                {'phrase': 0, 'mora': 4, 'pitch': 5.0},  # ん
            ]
        },
        {
            'name': '頭高型（最初にアクセント）',
            'text': 'バサラさんはすごいのだ！',
            'speaker': 3,
            'modifications': [
                {'phrase': 0, 'mora': 0, 'pitch': 6.5},  # バ（高）
                {'phrase': 0, 'mora': 1, 'pitch': 4.5},  # サ（低）
                {'phrase': 0, 'mora': 2, 'pitch': 4.5},  # ラ（低）
                {'phrase': 0, 'mora': 3, 'pitch': 4.5},  # さ（低）
                {'phrase': 0, 'mora': 4, 'pitch': 4.5},  # ん（低）
            ]
        },
        {
            'name': '中高型（真ん中にアクセント）',
            'text': 'バサラさんはすごいのだ！',
            'speaker': 3,
            'modifications': [
                {'phrase': 0, 'mora': 0, 'pitch': 4.5},  # バ（低）
                {'phrase': 0, 'mora': 1, 'pitch': 6.0},  # サ（高）
                {'phrase': 0, 'mora': 2, 'pitch': 6.0},  # ラ（高）
                {'phrase': 0, 'mora': 3, 'pitch': 4.5},  # さ（低）
                {'phrase': 0, 'mora': 4, 'pitch': 4.5},  # ん（低）
            ]
        }
    ]
    
    # 各パターンで音声を生成
    for i, test in enumerate(test_cases):
        print(f"\n{'='*50}")
        print(f"テスト{i+1}: {test['name']}")
        print(f"テキスト: {test['text']}")
        
        # アクセント句の調整
        audio_query = generate_with_accent_phrase(
            test['text'], 
            test['speaker'], 
            test['modifications']
        )
        
        # 音声の合成
        synthesis_response = requests.post(
            'http://localhost:50021/synthesis',
            params={'speaker': test['speaker']},
            json=audio_query,
            headers={'Content-Type': 'application/json'}
        )
        
        # 保存
        filename = f"outputs/accent_test_{i}_{test['name']}.wav"
        with open(filename, 'wb') as f:
            f.write(synthesis_response.content)
        
        print(f"\n✓ 保存: {filename}")
        time.sleep(0.5)
    
    # その他の調整方法の説明
    print("\n" + "="*50)
    print("\nその他の調整パラメータ:")
    print("1. speedScale: 話速（0.5-2.0）")
    print("2. pitchScale: 音高（0.8-1.2）")
    print("3. intonationScale: 抑揚の強さ（0.0-2.0）")
    print("4. volumeScale: 音量（0.0-2.0）")
    print("5. prePhonemeLength: 音素前の無音長")
    print("6. postPhonemeLength: 音素後の無音長")
    
    # 速度とピッチを調整した例
    print("\n追加テスト: パラメータ調整")
    
    params = {'text': 'バサラさんの歌は最高なのだ！', 'speaker': 3}
    audio_query = requests.post('http://localhost:50021/audio_query', params=params).json()
    
    # パラメータを調整
    audio_query['speedScale'] = 0.9  # 少しゆっくり
    audio_query['pitchScale'] = 1.05  # 少し高め
    audio_query['intonationScale'] = 1.3  # 抑揚を強く
    
    synthesis_response = requests.post(
        'http://localhost:50021/synthesis',
        params={'speaker': 3},
        json=audio_query,
        headers={'Content-Type': 'application/json'}
    )
    
    with open("outputs/accent_test_parameter.wav", 'wb') as f:
        f.write(synthesis_response.content)
    
    print("✓ パラメータ調整版: outputs/accent_test_parameter.wav")
    print("  - 速度: 0.9倍")
    print("  - ピッチ: 1.05倍")
    print("  - 抑揚: 1.3倍")

if __name__ == "__main__":
    test_basara_accent()