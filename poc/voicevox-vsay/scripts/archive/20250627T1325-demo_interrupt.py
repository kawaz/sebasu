#!/usr/bin/env python3
"""
割り込みデモ - 長文読み上げ中に緊急メッセージ
"""
import asyncio
import aiohttp

API_URL = "http://localhost:8002"

async def demo():
    async with aiohttp.ClientSession() as session:
        # 長い文章を通常優先度で開始
        print("長文の読み上げを開始...")
        await session.post(f"{API_URL}/speak", json={
            "text": "これは長いお知らせです。本日の天気は晴れ、気温は20度で過ごしやすい一日となるでしょう。午後からは少し雲が出てきますが、雨の心配はありません。明日も引き続き良い天気が続く見込みです。",
            "priority": "normal",
            "speaker": 3
        })
        
        # 3秒後に緊急割り込み
        await asyncio.sleep(3)
        print("\n🚨 緊急割り込み！")
        
        await session.post(f"{API_URL}/interrupt", json={
            "text": "緊急！火事です！今すぐ避難してください！",
            "speaker": 2,  # 別の話者で
            "volume": 2.0  # 大音量
        })
        
        print("割り込み後、元の音声が再開されるはずです...")

if __name__ == "__main__":
    asyncio.run(demo())