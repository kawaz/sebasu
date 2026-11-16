#!/usr/bin/env python3
"""
マイクの動作確認
"""
import pvrecorder
import numpy as np
import time

def test_microphone():
    """マイクの動作とレベルを確認"""
    print("🎤 マイクテスト")
    print("=" * 60)
    
    # 利用可能なデバイスを表示
    devices = pvrecorder.PvRecorder.get_available_devices()
    print("利用可能な録音デバイス:")
    for i, device in enumerate(devices):
        print(f"  [{i}] {device}")
    
    print("\nデフォルトデバイスを使用します")
    
    # レコーダー作成
    recorder = pvrecorder.PvRecorder(frame_length=512, device_index=-1)
    
    print("\n10秒間、音声レベルを表示します")
    print("何か話してみてください...\n")
    
    recorder.start()
    
    start_time = time.time()
    max_level = 0
    
    try:
        while time.time() - start_time < 10:
            pcm = recorder.read()
            
            # 音声レベルを計算（RMS）
            rms = np.sqrt(np.mean(np.square(pcm)))
            level = int(rms / 32768 * 50)  # 0-50のスケールに正規化
            
            # 最大レベルを記録
            if level > max_level:
                max_level = level
            
            # レベルメーター表示
            bar = "█" * level + "░" * (50 - level)
            print(f"\r音声レベル: [{bar}] {level:2d}/50", end='', flush=True)
            
            # 音声検出
            if level > 5:
                print(" 🔊 音声検出！", end='', flush=True)
            else:
                print("            ", end='', flush=True)
                
    except KeyboardInterrupt:
        print("\n\n中断されました")
    finally:
        recorder.stop()
        recorder.delete()
    
    print(f"\n\n最大レベル: {max_level}/50")
    
    if max_level > 10:
        print("✅ マイクは正常に動作しています")
    elif max_level > 5:
        print("⚠️  マイクの感度が低いか、音量が小さいです")
    else:
        print("❌ マイクが正しく動作していない可能性があります")

if __name__ == "__main__":
    test_microphone()