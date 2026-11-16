#!/usr/bin/env python3
"""
「バサラさん」のアクセントパターン比較
"""
import requests
import json
import time

def generate_basara_accent(pattern_name, modifications=None):
    """バサラさんのアクセントパターンを生成"""
    
    text = "バサラさん"
    speaker_id = 3  # ずんだもん
    
    # 音声クエリの生成
    params = {'text': text, 'speaker': speaker_id}
    query_response = requests.post(
        'http://localhost:50021/audio_query',
        params=params
    )
    audio_query = query_response.json()
    
    # アクセント句の確認
    print(f"\n{pattern_name}:")
    print(f"テキスト: {text}")
    for i, phrase in enumerate(audio_query['accent_phrases']):
        for j, mora in enumerate(phrase['moras']):
            text_mora = mora['text']
            pitch = mora['pitch']
            print(f"  [{j}] {text_mora}: pitch={pitch:.2f}")
    
    # アクセントの調整
    if modifications:
        for mod in modifications:
            phrase_idx = mod.get('phrase', 0)
            mora_idx = mod['mora']
            new_pitch = mod['pitch']
            if phrase_idx < len(audio_query['accent_phrases']):
                if mora_idx < len(audio_query['accent_phrases'][phrase_idx]['moras']):
                    audio_query['accent_phrases'][phrase_idx]['moras'][mora_idx]['pitch'] = new_pitch
        
        print("調整後:")
        for i, phrase in enumerate(audio_query['accent_phrases']):
            for j, mora in enumerate(phrase['moras']):
                text_mora = mora['text']
                pitch = mora['pitch']
                print(f"  [{j}] {text_mora}: pitch={pitch:.2f}")
    
    # 音声の合成
    synthesis_response = requests.post(
        'http://localhost:50021/synthesis',
        params={'speaker': speaker_id},
        json=audio_query,
        headers={'Content-Type': 'application/json'}
    )
    
    # 保存
    filename = f"outputs/basara_{pattern_name}.wav"
    with open(filename, 'wb') as f:
        f.write(synthesis_response.content)
    
    print(f"✓ 保存: {filename}")
    
    return filename

def main():
    print("=== 「バサラさん」アクセントパターン比較 ===")
    
    # VOICEVOXエンジンの確認
    try:
        response = requests.get('http://localhost:50021/version', timeout=1)
        print(f"\nVOICEVOX Engine: {response.text.strip()}")
    except:
        print("\nエラー: VOICEVOXエンジンが起動していません")
        return
    
    # アクセントパターンの定義
    patterns = [
        {
            'name': '1_オリジナル',
            'modifications': None
        },
        {
            'name': '2_平板型',
            'modifications': [
                {'mora': 0, 'pitch': 5.5},  # バ
                {'mora': 1, 'pitch': 5.5},  # サ
                {'mora': 2, 'pitch': 5.5},  # ラ
                {'mora': 3, 'pitch': 5.5},  # さ
                {'mora': 4, 'pitch': 5.5},  # ん
            ]
        },
        {
            'name': '3_頭高型',
            'modifications': [
                {'mora': 0, 'pitch': 6.8},  # バ（高）
                {'mora': 1, 'pitch': 4.8},  # サ（低）
                {'mora': 2, 'pitch': 4.8},  # ラ（低）
                {'mora': 3, 'pitch': 4.8},  # さ（低）
                {'mora': 4, 'pitch': 4.8},  # ん（低）
            ]
        },
        {
            'name': '4_中高型_サラ',
            'modifications': [
                {'mora': 0, 'pitch': 5.0},  # バ（低）
                {'mora': 1, 'pitch': 6.5},  # サ（高）
                {'mora': 2, 'pitch': 6.5},  # ラ（高）
                {'mora': 3, 'pitch': 5.0},  # さ（低）
                {'mora': 4, 'pitch': 5.0},  # ん（低）
            ]
        },
        {
            'name': '5_尾高型',
            'modifications': [
                {'mora': 0, 'pitch': 5.0},  # バ（低）
                {'mora': 1, 'pitch': 5.5},  # サ（中）
                {'mora': 2, 'pitch': 6.0},  # ラ（高）
                {'mora': 3, 'pitch': 6.0},  # さ（高）
                {'mora': 4, 'pitch': 5.0},  # ん（低）
            ]
        },
        {
            'name': '6_強調型_バ',
            'modifications': [
                {'mora': 0, 'pitch': 7.0},  # バ（最高）
                {'mora': 1, 'pitch': 5.0},  # サ
                {'mora': 2, 'pitch': 5.0},  # ラ
                {'mora': 3, 'pitch': 5.0},  # さ
                {'mora': 4, 'pitch': 5.0},  # ん
            ]
        }
    ]
    
    # 各パターンを生成
    generated_files = []
    for pattern in patterns:
        filename = generate_basara_accent(
            pattern['name'],
            pattern['modifications']
        )
        generated_files.append(filename)
        time.sleep(0.3)
    
    print("\n" + "="*50)
    print("生成完了！連続再生するには:")
    print("for file in outputs/basara_*.wav; do afplay \"$file\"; done")

if __name__ == "__main__":
    main()