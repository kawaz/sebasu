#!/usr/bin/env python3
"""
vsayの実際のレイテンシを測定
"""
import subprocess
import time

def measure_vsay(text):
    """vsayコマンドの実行時間を測定"""
    start = time.time()
    subprocess.run(['./vsay', text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return time.time() - start

def main():
    print("=== vsay レイテンシ測定 ===\n")
    
    test_phrases = [
        "こんにちは",
        "今日はいい天気です",
        "バサラさんは最高なのだ",
        "音声合成のテストをしています",
        "リアルタイムで会話ができるようになりました"
    ]
    
    # ウォームアップ
    print("ウォームアップ中...")
    measure_vsay("テスト")
    
    print("\n測定開始:")
    total_time = 0
    for phrase in test_phrases:
        latency = measure_vsay(phrase)
        total_time += latency
        print(f"「{phrase}」 - {latency:.3f}秒")
    
    print(f"\n平均レイテンシ: {total_time/len(test_phrases):.3f}秒")
    
    # 連続実行テスト
    print("\n連続実行テスト（5回）:")
    start = time.time()
    for i in range(5):
        subprocess.run(['./vsay', f"これは{i+1}回目のテストです"], 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    total = time.time() - start
    print(f"合計時間: {total:.3f}秒 (平均: {total/5:.3f}秒/回)")

if __name__ == "__main__":
    main()