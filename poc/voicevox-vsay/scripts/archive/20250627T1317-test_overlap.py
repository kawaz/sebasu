#!/usr/bin/env python3
"""
音声のオーバーラップテスト
"""
import asyncio
import aiohttp
import time

API_URL = "http://localhost:8000"

async def speak_async(session, text, speaker=3):
    """非同期で音声再生リクエストを送信"""
    async with session.post(
        f"{API_URL}/speak",
        json={
            "text": text,
            "speaker": speaker,
            "play": True
        }
    ) as response:
        result = await response.json()
        print(f"[{time.strftime('%H:%M:%S')}] {text}: {result['message']}")

async def test_overlap():
    """複数の音声を同時に再生"""
    print("=== オーバーラップテスト ===\n")
    print("3つの音声を同時に再生します...\n")
    
    async with aiohttp.ClientSession() as session:
        # 同時に3つのリクエストを送信
        tasks = [
            speak_async(session, "これは最初の音声です", 3),    # ずんだもん
            speak_async(session, "これは二番目の音声です", 2),  # 四国めたん
            speak_async(session, "これは三番目の音声です", 8),  # 春日部つむぎ
        ]
        await asyncio.gather(*tasks)
    
    print("\n音声が同時に再生されているはずです")
    await asyncio.sleep(3)  # 再生完了待ち
    
    print("\n今度は少しずつずらして再生します...\n")
    
    async with aiohttp.ClientSession() as session:
        # 0.5秒ずつずらして送信
        for i, (text, speaker) in enumerate([
            ("一番目です", 3),
            ("二番目です", 2),
            ("三番目です", 8)
        ]):
            asyncio.create_task(speak_async(session, text, speaker))
            await asyncio.sleep(0.5)
    
    await asyncio.sleep(3)  # 再生完了待ち

if __name__ == "__main__":
    asyncio.run(test_overlap())