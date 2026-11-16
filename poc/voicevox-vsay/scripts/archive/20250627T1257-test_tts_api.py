#!/usr/bin/env python3
"""
Simple TTS APIのテストスクリプト
"""
import requests
import time
import asyncio
import aiohttp

API_URL = "http://localhost:8000"

def test_sync_api():
    """同期的なAPIテスト"""
    print("=== 同期APIテスト ===\n")
    
    # 1. 基本的な音声再生
    print("1. 基本的な音声再生テスト")
    start = time.time()
    response = requests.post(
        f"{API_URL}/speak",
        json={"text": "これはテストです"}
    )
    print(f"  レスポンス時間: {time.time() - start:.3f}秒")
    print(f"  結果: {response.json()}\n")
    
    # 2. 異なる話者でテスト
    print("2. 異なる話者でテスト")
    speakers = [
        (3, "ずんだもん"),
        (2, "四国めたん"),
        (8, "春日部つむぎ")
    ]
    for speaker_id, name in speakers:
        response = requests.post(
            f"{API_URL}/speak",
            json={
                "text": f"私は{name}です",
                "speaker": speaker_id,
                "speed": 1.5
            }
        )
        print(f"  {name}: {response.json()['message']}")
        time.sleep(1)  # 連続再生を避ける
    
    print()

async def test_async_api():
    """非同期APIテスト（並列リクエスト）"""
    print("=== 非同期APIテスト（並列リクエスト）===\n")
    
    texts = [
        "おはようございます",
        "こんにちは",
        "こんばんは",
        "おやすみなさい"
    ]
    
    async with aiohttp.ClientSession() as session:
        # 並列でリクエストを送信
        start = time.time()
        tasks = []
        for i, text in enumerate(texts):
            task = session.post(
                f"{API_URL}/speak",
                json={
                    "text": text,
                    "speaker": 3,
                    "play": False  # 並列再生を避ける
                }
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        print(f"4つのリクエスト完了時間: {time.time() - start:.3f}秒")
        
        for i, response in enumerate(responses):
            data = await response.json()
            print(f"  {texts[i]}: {data['audio_length']:.2f}秒の音声")

def test_generate_api():
    """音声ファイル生成APIテスト"""
    print("\n=== 音声ファイル生成APIテスト ===\n")
    
    response = requests.post(
        f"{API_URL}/generate",
        json={"text": "これは音声ファイルです"}
    )
    
    if response.status_code == 200:
        with open("test_output.wav", "wb") as f:
            f.write(response.content)
        print("  test_output.wav として保存しました")
        print(f"  ファイルサイズ: {len(response.content)} bytes")

def test_speakers_api():
    """話者一覧APIテスト"""
    print("\n=== 話者一覧APIテスト ===\n")
    
    response = requests.get(f"{API_URL}/speakers")
    if response.status_code == 200:
        speakers = response.json()
        print(f"  利用可能な話者数: {len(speakers)}")
        for speaker in speakers[:3]:  # 最初の3人だけ表示
            print(f"  - {speaker['name']}: {len(speaker['styles'])}スタイル")

def main():
    # APIサーバーの確認
    try:
        response = requests.get(f"{API_URL}/")
        print(f"APIサーバー接続成功: {response.json()['message']}\n")
    except:
        print("エラー: APIサーバーに接続できません")
        print("起動してください: uv run python tts_api_server.py")
        return
    
    # 各種テスト実行
    test_sync_api()
    asyncio.run(test_async_api())
    test_generate_api()
    test_speakers_api()
    
    print("\n全てのテスト完了！")

if __name__ == "__main__":
    main()