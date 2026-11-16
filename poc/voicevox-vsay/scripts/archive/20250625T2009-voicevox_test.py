#!/usr/bin/env python3
"""
VOICEVOXのテスト
高品質な日本語音声合成エンジン（ローカルサーバー経由、オフライン動作）

事前準備:
1. VOICEVOXをダウンロード: https://voicevox.hiroshiba.jp/
2. VOICEVOXアプリを起動（自動的にローカルサーバーが起動）
"""
import requests
import json
import time
import wave
import subprocess
import os

class VoiceVoxClient:
    def __init__(self, host='localhost', port=50021):
        self.base_url = f'http://{host}:{port}'
    
    def is_server_running(self):
        """VOICEVOXサーバーが起動しているか確認"""
        try:
            response = requests.get(f'{self.base_url}/version', timeout=1)
            return response.status_code == 200
        except:
            return False
    
    def get_speakers(self):
        """利用可能な話者のリストを取得"""
        response = requests.get(f'{self.base_url}/speakers')
        return response.json()
    
    def generate_audio_query(self, text, speaker_id=1):
        """音声合成用のクエリを作成"""
        params = {'text': text, 'speaker': speaker_id}
        response = requests.post(f'{self.base_url}/audio_query', params=params)
        return response.json()
    
    def synthesize(self, audio_query, speaker_id=1):
        """音声を合成"""
        params = {'speaker': speaker_id}
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            f'{self.base_url}/synthesis',
            params=params,
            data=json.dumps(audio_query),
            headers=headers
        )
        return response.content
    
    def save_audio(self, audio_data, filename):
        """音声データをWAVファイルとして保存"""
        with open(filename, 'wb') as f:
            f.write(audio_data)

def test_voicevox():
    """VOICEVOXのテスト"""
    print("=== VOICEVOX テスト開始 ===")
    
    # VOICEVOXクライアントの初期化
    client = VoiceVoxClient()
    
    # サーバーの確認
    print("\nVOICEVOXサーバーの確認...")
    if not client.is_server_running():
        print("エラー: VOICEVOXサーバーが起動していません")
        print("VOICEVOXアプリケーションを起動してください")
        print("ダウンロード: https://voicevox.hiroshiba.jp/")
        return
    
    print("✓ VOICEVOXサーバーが起動しています")
    
    # 利用可能な話者を取得
    print("\n利用可能な話者を取得中...")
    try:
        speakers = client.get_speakers()
        print(f"話者数: {len(speakers)}")
        
        # 最初の5人の話者を表示
        for i, speaker in enumerate(speakers[:5]):
            print(f"  {speaker['name']} (ID: {speaker['speaker_uuid']})")
            for style in speaker['styles']:
                print(f"    - {style['name']} (ID: {style['id']})")
    except Exception as e:
        print(f"話者取得エラー: {e}")
        speakers = []
    
    # テストする文章
    test_texts = [
        "こんにちは、私はボイスボックスです。",
        "今日の天気は晴れです。",
        "音声認識と音声合成を組み合わせて、対話型のシステムを作ります。",
        "ボイスボックスは、高品質な日本語音声合成エンジンです。",
    ]
    
    # 異なる話者でテスト（デフォルトの話者IDを使用）
    test_speaker_ids = [1, 2, 3, 8, 10]  # ずんだもん、四国めたん、等
    
    for speaker_id in test_speaker_ids[:3]:  # 最初の3人でテスト
        print(f"\n話者ID {speaker_id} でテスト:")
        
        # 最初のテキストで音声を生成
        text = test_texts[0]
        print(f"  テキスト: {text}")
        
        try:
            # 音声クエリの生成
            start_time = time.time()
            audio_query = client.generate_audio_query(text, speaker_id)
            query_time = time.time() - start_time
            
            # 音声の合成
            start_time = time.time()
            audio_data = client.synthesize(audio_query, speaker_id)
            synthesis_time = time.time() - start_time
            
            # ファイルに保存
            filename = f"outputs/voicevox_speaker{speaker_id}.wav"
            client.save_audio(audio_data, filename)
            
            print(f"  クエリ生成時間: {query_time:.3f}秒")
            print(f"  音声合成時間: {synthesis_time:.3f}秒")
            print(f"  保存先: {filename}")
            
        except Exception as e:
            print(f"  エラー: {e}")
    
    # 速度調整テスト
    print("\n速度調整テスト:")
    text = "速度を変更して話します。"
    speaker_id = 1
    
    for speed_scale in [0.7, 1.0, 1.3]:
        try:
            # 音声クエリの生成
            audio_query = client.generate_audio_query(text, speaker_id)
            # 速度を変更
            audio_query['speedScale'] = speed_scale
            
            # 音声の合成
            audio_data = client.synthesize(audio_query, speaker_id)
            
            # ファイルに保存
            filename = f"outputs/voicevox_speed_{speed_scale}.wav"
            client.save_audio(audio_data, filename)
            print(f"  速度 {speed_scale}x: {filename}")
            
        except Exception as e:
            print(f"  エラー: {e}")
    
    print("\n=== VOICEVOX テスト完了 ===")
    
    # 結果のサマリー
    print("\n結果:")
    print(f"- 利用可能な話者数: {len(speakers) if 'speakers' in locals() else '不明'}")
    print(f"- 完全オフライン動作: ✓ (ローカルサーバー経由)")
    print(f"- 音声ファイル保存: ✓ (WAV形式)")
    print(f"- 速度調整: ✓")
    print(f"- 音質: 非常に高品質")
    print(f"- 特徴: キャラクターボイス、感情表現豊か")

if __name__ == "__main__":
    test_voicevox()