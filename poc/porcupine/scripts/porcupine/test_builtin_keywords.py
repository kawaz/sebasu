#!/usr/bin/env python3
"""
組み込みキーワードのテスト（動作確認用）
"""
import os
import pvporcupine
import pvrecorder

# APIキー確認
access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
if not access_key:
    raise ValueError("PICOVOICE_ACCESS_KEY環境変数が設定されていません")

print("組み込みキーワードのテスト")
print("=" * 60)

# 組み込みキーワードをテスト
try:
    # 英語の組み込みキーワード "picovoice" を使用
    porcupine = pvporcupine.create(
        access_key=access_key,
        keywords=["picovoice"]
    )
    
    print("✅ 初期化成功！")
    print(f"フレーム長: {porcupine.frame_length}")
    print(f"サンプルレート: {porcupine.sample_rate} Hz")
    
    recorder = pvrecorder.PvRecorder(
        frame_length=porcupine.frame_length,
        device_index=-1
    )
    
    print("\n🎤 'picovoice' と話してください（10秒間）...")
    print("終了: Ctrl+C\n")
    
    recorder.start()
    
    import time
    start = time.time()
    
    try:
        while time.time() - start < 10:
            pcm = recorder.read()
            result = porcupine.process(pcm)
            
            if result >= 0:
                print(f"✅ 検出！ 'picovoice' @ {time.strftime('%H:%M:%S')}")
                time.sleep(1)  # 連続検出防止
                
    except KeyboardInterrupt:
        print("\n中断されました")
    finally:
        recorder.stop()
        recorder.delete()
        porcupine.delete()
        
except Exception as e:
    print(f"❌ エラー: {e}")
    
print("\n" + "=" * 60)
print("テスト完了")