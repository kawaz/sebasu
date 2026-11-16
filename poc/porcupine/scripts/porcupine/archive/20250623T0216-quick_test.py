#!/usr/bin/env python3
"""
クイックテスト - 10秒間だけウェイクワード検出
"""

import os
import sys
import time
import pvporcupine
import pvrecorder

def quick_test():
    access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
    if not access_key:
        print("エラー: PICOVOICE_ACCESS_KEY が設定されていません")
        return
    
    print("🎤 10秒間のウェイクワード検出テスト")
    print("話してください: 'picovoice' または 'computer'\n")
    
    # 初期化
    porcupine = pvporcupine.create(
        access_key=access_key,
        keywords=['picovoice', 'computer']
    )
    
    recorder = pvrecorder.PvRecorder(
        frame_length=porcupine.frame_length,
        device_index=-1
    )
    
    # 10秒間検出
    recorder.start()
    start_time = time.time()
    detected = False
    
    try:
        while time.time() - start_time < 10:
            remaining = 10 - int(time.time() - start_time)
            print(f"\r残り {remaining} 秒...", end='', flush=True)
            
            pcm = recorder.read()
            keyword_index = porcupine.process(pcm)
            
            if keyword_index >= 0:
                word = ['picovoice', 'computer'][keyword_index]
                print(f"\n\n✅ 検出成功！ '{word}' を認識しました！")
                detected = True
                break
                
    except Exception as e:
        print(f"\nエラー: {e}")
    finally:
        recorder.stop()
        recorder.delete()
        porcupine.delete()
    
    if not detected:
        print("\n\n⏱️ タイムアウト - ウェイクワードは検出されませんでした")
    
    print("\nテスト完了")

if __name__ == "__main__":
    quick_test()