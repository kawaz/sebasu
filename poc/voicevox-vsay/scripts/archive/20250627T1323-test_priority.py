#!/usr/bin/env python3
"""
優先度・割り込み機能のテスト
"""
import asyncio
import aiohttp
import time

API_URL = "http://localhost:8002"

async def speak_with_priority(text, priority="normal", volume=1.0, speaker=3):
    """優先度付きで音声再生"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/speak",
            json={
                "text": text,
                "speaker": speaker,
                "priority": priority,
                "volume": volume
            }
        ) as response:
            result = await response.json()
            print(f"[{priority:6}] {text[:30]:30} (音量:{volume})")
            return result

async def interrupt_speech(text, volume=1.5):
    """緊急割り込み"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/interrupt",
            json={
                "text": text,
                "speaker": 2,  # 別の話者で
                "volume": volume
            }
        ) as response:
            result = await response.json()
            print(f"[URGENT!] {text} (音量:{volume})")
            return result

async def test_priority_queue():
    """優先度キューのテスト"""
    print("=== 優先度キューテスト ===\n")
    
    # 異なる優先度でタスクを投入
    tasks = [
        speak_with_priority("これは低優先度のメッセージです", "low"),
        speak_with_priority("これは通常優先度のメッセージです", "normal"),
        speak_with_priority("これは高優先度のメッセージです", "high"),
        speak_with_priority("もう一つの低優先度メッセージ", "low"),
        speak_with_priority("もう一つの高優先度メッセージ", "high"),
    ]
    
    await asyncio.gather(*tasks)
    print("\n優先度順に再生されるはずです（high → normal → low）")
    await asyncio.sleep(10)

async def test_interrupt():
    """割り込みテスト"""
    print("\n\n=== 割り込みテスト ===\n")
    
    # 長い文章を再生開始
    await speak_with_priority(
        "これは非常に長いメッセージです。今から約10秒間話し続けます。" +
        "途中で緊急メッセージが割り込んでくるはずです。" +
        "割り込み後は、このメッセージの続きが再生されます。" +
        "テストテストテストテストテスト。",
        "normal"
    )
    
    # 2秒後に緊急割り込み
    await asyncio.sleep(2)
    print("\n*** 緊急割り込み発生！ ***\n")
    await interrupt_speech("緊急！火事です！すぐに避難してください！", volume=2.0)
    
    # さらに通常のメッセージを追加
    await speak_with_priority("割り込み後の通常メッセージ", "normal")
    
    await asyncio.sleep(15)

async def test_multiple_interrupts():
    """複数の割り込みテスト"""
    print("\n\n=== 複数割り込みテスト ===\n")
    
    # 通常のタスクをいくつか投入
    tasks = []
    for i in range(3):
        tasks.append(speak_with_priority(f"通常メッセージ{i+1}番目", "normal"))
    await asyncio.gather(*tasks)
    
    # 連続で緊急割り込み
    await asyncio.sleep(1)
    await interrupt_speech("緊急その1！", volume=1.5)
    await asyncio.sleep(0.5)
    await interrupt_speech("もっと緊急その2！", volume=2.0)
    
    await asyncio.sleep(10)

async def check_status():
    """ステータス確認"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/status") as response:
            status = await response.json()
            print("\n--- 現在の状態 ---")
            print(f"再生中: {status['currently_playing']}")
            print(f"キューサイズ: {status['queue_size']}")
            if status['queue']:
                print("キュー内容:")
                for item in status['queue']:
                    print(f"  [{item['priority']}] {item['text']}")

async def main():
    print("Priority TTS API テスト開始\n")
    
    # 各テストを順番に実行
    await test_priority_queue()
    await check_status()
    
    await test_interrupt()
    await check_status()
    
    await test_multiple_interrupts()
    await check_status()
    
    print("\n\nテスト完了！")

if __name__ == "__main__":
    asyncio.run(main())