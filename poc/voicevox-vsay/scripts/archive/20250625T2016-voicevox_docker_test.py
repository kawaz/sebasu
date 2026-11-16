#!/usr/bin/env python3
"""
VOICEVOX Dockerを使用したテスト
Dockerがインストールされている場合の最も簡単な方法
"""
import subprocess
import time
import requests
import json
import os

def check_docker():
    """Dockerがインストールされているか確認"""
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def start_voicevox_docker():
    """VOICEVOX Dockerコンテナを起動"""
    print("VOICEVOXコンテナを起動中...")
    
    # 既存のコンテナを停止
    subprocess.run(['docker', 'stop', 'voicevox-engine'], capture_output=True)
    subprocess.run(['docker', 'rm', 'voicevox-engine'], capture_output=True)
    
    # コンテナを起動
    cmd = [
        'docker', 'run',
        '--rm',
        '-d',
        '--name', 'voicevox-engine',
        '-p', '127.0.0.1:50021:50021',
        'voicevox/voicevox_engine:cpu-ubuntu20.04-latest'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"エラー: {result.stderr}")
        return False
    
    # 起動を待つ
    print("起動を待っています", end="")
    for i in range(30):
        try:
            response = requests.get('http://localhost:50021/version', timeout=1)
            if response.status_code == 200:
                print("\n✓ VOICEVOXが起動しました")
                return True
        except:
            pass
        print(".", end="", flush=True)
        time.sleep(1)
    
    print("\nタイムアウト")
    return False

def test_voicevox_docker():
    """Docker版VOICEVOXのテスト"""
    print("=== VOICEVOX Docker テスト ===")
    
    # Dockerの確認
    if not check_docker():
        print("エラー: Dockerがインストールされていません")
        print("以下の方法でVOICEVOXを使用できます：")
        print("1. VOICEVOXアプリをダウンロード: https://voicevox.hiroshiba.jp/")
        print("2. Dockerをインストール: https://www.docker.com/")
        return
    
    print("✓ Dockerが利用可能です")
    
    # VOICEVOXコンテナを起動
    if not start_voicevox_docker():
        return
    
    # APIテスト
    print("\nAPIテスト:")
    
    # バージョン確認
    response = requests.get('http://localhost:50021/version')
    print(f"バージョン: {response.text}")
    
    # 話者一覧
    response = requests.get('http://localhost:50021/speakers')
    speakers = response.json()
    print(f"話者数: {len(speakers)}")
    
    # 音声合成テスト
    print("\n音声合成テスト:")
    text = "こんにちは、私はずんだもんなのだ！"
    speaker_id = 3
    
    # クエリ生成
    params = {'text': text, 'speaker': speaker_id}
    response = requests.post('http://localhost:50021/audio_query', params=params)
    audio_query = response.json()
    
    # 音声合成
    headers = {'Content-Type': 'application/json'}
    response = requests.post(
        'http://localhost:50021/synthesis',
        params={'speaker': speaker_id},
        data=json.dumps(audio_query),
        headers=headers
    )
    
    # 保存
    filename = 'outputs/voicevox_docker_test.wav'
    with open(filename, 'wb') as f:
        f.write(response.content)
    
    print(f"✓ 音声を生成しました: {filename}")
    
    # コンテナを停止
    print("\nコンテナを停止しますか？ (y/N): ", end="")
    if input().lower() == 'y':
        subprocess.run(['docker', 'stop', 'voicevox-engine'])
        print("停止しました")
    else:
        print("コンテナは起動したままです")
        print("停止するには: docker stop voicevox-engine")

if __name__ == "__main__":
    test_voicevox_docker()