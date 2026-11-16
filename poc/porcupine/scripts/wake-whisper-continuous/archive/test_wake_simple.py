#!/usr/bin/env python3
"""ウェイクワード検出器の単体テスト"""

import time
import numpy as np
from config import Config
from wake_detector_auto import create_wake_detector
from audio_recorder import MultiLevelAudioRecorder

def test_wake_detector():
    print("ウェイクワード検出テスト開始...")
    
    # 検出器作成
    detector = create_wake_detector()
    if not detector.initialize():
        print("検出器の初期化に失敗")
        return
    
    # コールバック設定
    detected_count = 0
    
    def on_detected(info):
        nonlocal detected_count
        detected_count += 1
        print(f"ウェイクワード検出！ #{detected_count}")
        print(f"  名前: {info['name']}")
        print(f"  タイプ: {info.get('type', 'unknown')}")
        print(f"  タイムスタンプ: {info.get('timestamp_start', 0)} - {info.get('timestamp_end', 0)}")
    
    detector.set_detection_callback(on_detected)
    
    # 音声レコーダー
    recorder = MultiLevelAudioRecorder()
    if not recorder.start_stream():
        print("音声ストリーム開始失敗")
        detector.cleanup()
        return
    
    # 必要なら参照を設定
    if hasattr(detector, 'set_audio_recorder'):
        detector.set_audio_recorder(recorder)
    
    # フレーム長確認
    frame_length = detector.get_frame_length()
    print(f"必要なフレーム長: {frame_length} サンプル")
    print(f"チャンクサイズ: {Config.CHUNK_SIZE} サンプル")
    
    # 使用可能なウェイクワード表示
    if hasattr(detector, 'get_all_wake_words'):
        wake_words = detector.get_all_wake_words()
        print(f"使用可能なウェイクワード: {[w['name'] for w in wake_words]}")
    
    print("\nウェイクワードを話してください...")
    print("Ctrl+Cで終了")
    
    chunks_processed = 0
    accumulator = np.array([], dtype=np.int16)
    
    try:
        while True:
            # 音声読み取り
            chunk = recorder.read_chunk()
            if chunk is None:
                time.sleep(0.01)
                continue
            
            chunks_processed += 1
            
            # アキュムレータに追加
            accumulator = np.concatenate([accumulator, chunk])
            
            # フレーム長以上になったら処理
            while len(accumulator) >= frame_length:
                frame = accumulator[:frame_length]
                detector.process_audio(frame)
                accumulator = accumulator[frame_length:]
            
            # 進捗表示（1秒ごと）
            if chunks_processed % (Config.SAMPLE_RATE // Config.CHUNK_SIZE) == 0:
                print(f"処理中... (チャンク数: {chunks_processed}, 検出数: {detected_count})")
    
    except KeyboardInterrupt:
        print("\n終了します...")
    
    finally:
        detector.cleanup()
        recorder.cleanup()
        print(f"合計検出数: {detected_count}")

if __name__ == "__main__":
    test_wake_detector()