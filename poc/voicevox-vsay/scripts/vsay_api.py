#!/usr/bin/env python3
"""
vsay api - Simple TTS APIを使った音声合成
元のvsay2の実装
"""
import sys
import requests
import argparse
import subprocess
import time

API_URL = "http://localhost:8000"

def check_api_server():
    """APIサーバーが起動しているか確認"""
    try:
        response = requests.get(f"{API_URL}/", timeout=0.5)
        return response.status_code == 200
    except:
        return False

def start_api_server():
    """APIサーバーを自動起動"""
    # まずVOICEVOXがインストールされているか確認
    from pathlib import Path
    if not Path("voicevox_engine").exists():
        print("\nエラー: VOICEVOXがインストールされていません", file=sys.stderr)
        # 標準入力が端末でない場合（パイプ等）は自動セットアップをスキップ
        if not sys.stdin.isatty():
            print("セットアップ: vsay engine setup", file=sys.stderr)
            print("起動: vsay engine start", file=sys.stderr)
            sys.exit(1)
        
        print("VOICEVOXをセットアップしますか？ (y/N)", file=sys.stderr)
        response = input().strip().lower()
        if response in ['y', 'yes']:
            print("\nセットアップを実行します...", file=sys.stderr)
            subprocess.run(['uv', 'run', 'python', 'voicevox_manager.py', 'setup'])
            sys.exit(0)
        else:
            print("セットアップ: vsay engine setup", file=sys.stderr)
            print("起動: vsay engine start", file=sys.stderr)
            sys.exit(1)
    
    print("APIサーバーを起動しています...", file=sys.stderr)
    subprocess.Popen(
        ['uv', 'run', 'python', 'tts_api_server.py'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    # サーバー起動待ち
    for _ in range(10):
        time.sleep(0.5)
        if check_api_server():
            print("APIサーバーが起動しました", file=sys.stderr)
            return True
    return False

def speak(text, speaker=3, speed=1.2):
    """Simple TTS APIで音声を再生"""
    # APIサーバーの確認と自動起動
    if not check_api_server():
        if not start_api_server():
            print("エラー: APIサーバーの起動に失敗しました", file=sys.stderr)
            sys.exit(1)
    
    try:
        response = requests.post(
            f"{API_URL}/speak",
            json={
                "text": text,
                "speaker": speaker,
                "speed": speed,
                "play": True
            }
        )
        if response.status_code == 200:
            return True
        else:
            print(f"エラー: {response.status_code} - {response.text}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)

def main(args):
    if not args.text:
        # 標準入力から読む
        text = sys.stdin.read().strip()
    else:
        text = ' '.join(args.text)
    
    if text:
        speak(text, args.speaker, args.rate)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='VOICEVOXで音声合成（API経由）')
    parser.add_argument('text', nargs='*', help='読み上げるテキスト')
    parser.add_argument('-s', '--speaker', type=int, default=3, help='話者ID (デフォルト: 3=ずんだもん)')
    parser.add_argument('-r', '--rate', type=float, default=1.2, help='話速 (デフォルト: 1.2)')
    args = parser.parse_args()
    main(args)