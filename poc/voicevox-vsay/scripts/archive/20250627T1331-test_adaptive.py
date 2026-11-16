#!/usr/bin/env python3
"""
環境適応型音量のテスト
"""
import requests
import time

API_URL = "http://localhost:8003"

def test_adaptive_volume():
    print("=== 環境適応型音量テスト ===\n")
    
    # 現在の環境状態を確認
    response = requests.get(f"{API_URL}/status")
    if response.status_code == 200:
        status = response.json()
        print("現在の環境:")
        print(f"  時刻: {status['current_time']} ({status['time_period']})")
        print(f"  騒音レベル: {status['noise_level_db']:.1f} dB ({status['noise_description']})")
        print(f"  推奨音量:")
        for location, volume in status['suggested_volumes'].items():
            print(f"    {location}: {volume:.1f}x")
        print()
    
    # 各場所での音声テスト
    locations = ["living_room", "bedroom", "kitchen"]
    
    for location in locations:
        print(f"\n{location}での音声:")
        
        # 適応型音量で再生
        response = requests.post(f"{API_URL}/speak", json={
            "text": f"これは{location}での音声テストです",
            "location": location,
            "adaptive": True
        })
        
        if response.status_code == 200:
            result = response.json()
            print(f"  使用音量: {result['volume_used']:.1f}x")
            print(f"  騒音レベル: {result['noise_level']:.1f} dB")
        
        time.sleep(3)
    
    # 手動音量設定のテスト
    print("\n\n手動音量設定:")
    response = requests.post(f"{API_URL}/speak", json={
        "text": "これは手動で音量を2倍に設定した音声です",
        "volume_override": 2.0,
        "adaptive": False
    })
    if response.status_code == 200:
        result = response.json()
        print(f"  使用音量: {result['volume_used']:.1f}x（手動設定）")

if __name__ == "__main__":
    test_adaptive_volume()