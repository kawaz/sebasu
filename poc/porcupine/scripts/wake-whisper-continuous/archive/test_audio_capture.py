#!/usr/bin/env python3
"""音声キャプチャのテスト"""

import time
from config import Config
from audio_recorder import MultiLevelAudioRecorder

def test_audio_capture():
    recorder = MultiLevelAudioRecorder()
    
    print("音声レコーダー初期化...")
    if not recorder.start_stream():
        print("ストリーム開始失敗")
        return
    
    print("音声キャプチャテスト開始...")
    
    for i in range(50):
        chunk = recorder.read_chunk()
        if chunk is not None:
            print(f"チャンク {i}: サイズ={len(chunk)}, 最大値={max(chunk)}, 最小値={min(chunk)}")
        else:
            print(f"チャンク {i}: None")
        time.sleep(0.1)
    
    recorder.cleanup()
    print("テスト完了")

if __name__ == "__main__":
    test_audio_capture()