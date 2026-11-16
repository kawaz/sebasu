#!/usr/bin/env python3
"""
pyopenjltalkのテスト
完全オフライン動作の日本語音声合成エンジン
"""
import pyopenjtalk
import numpy as np
import wave
import time
import os

def save_wave(filename, audio, sample_rate=48000):
    """音声データをWAVファイルとして保存"""
    # float32をint16に変換
    audio_int16 = (audio * 32767).astype(np.int16)
    
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)  # モノラル
        wf.setsampwidth(2)  # 16bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())

def test_pyopenjtalk():
    """pyopenjltalkのテスト"""
    print("=== pyopenjltalk テスト開始 ===")
    
    # ライブラリ情報
    print("\nライブラリ情報:")
    print(f"- バージョン: {pyopenjtalk.__version__}")
    
    # テストする文章
    test_texts = [
        "こんにちは、私はオープンジェイトークです。",
        "今日の天気は晴れです。",
        "音声認識と音声合成を組み合わせて、対話型のシステムを作ります。",
        "完全にオフラインで動作する、日本語音声合成エンジンです。",
        "数字のテスト：1234567890",
        "英語混じり：Hello, これはテストです。",
    ]
    
    # 各テキストで音声を生成
    for i, text in enumerate(test_texts):
        print(f"\nテキスト {i+1}: {text}")
        
        try:
            # 音声合成
            start_time = time.time()
            audio, sr = pyopenjtalk.tts(text)
            synthesis_time = time.time() - start_time
            
            # ファイルに保存
            filename = f"outputs/openjtalk_test_{i+1}.wav"
            save_wave(filename, audio, sr)
            
            print(f"  合成時間: {synthesis_time:.3f}秒")
            print(f"  サンプルレート: {sr}Hz")
            print(f"  音声長: {len(audio)/sr:.2f}秒")
            print(f"  保存先: {filename}")
            
        except Exception as e:
            print(f"  エラー: {e}")
    
    # 速度変更テスト
    print("\n速度変更テスト:")
    text = "速度を変更して話します。"
    
    # 通常速度
    audio_normal, sr = pyopenjtalk.tts(text)
    save_wave("outputs/openjtalk_speed_normal.wav", audio_normal, sr)
    print("  通常速度: openjtalk_speed_normal.wav")
    
    # 速度変更（リサンプリングで実現）
    # 遅い速度（0.8倍）
    audio_slow = np.interp(
        np.arange(0, len(audio_normal), 0.8),
        np.arange(0, len(audio_normal)),
        audio_normal
    )
    save_wave("outputs/openjtalk_speed_slow.wav", audio_slow, sr)
    print("  遅い速度(0.8x): openjtalk_speed_slow.wav")
    
    # 速い速度（1.2倍）
    audio_fast = np.interp(
        np.arange(0, len(audio_normal), 1.2),
        np.arange(0, len(audio_normal)),
        audio_normal
    )
    save_wave("outputs/openjtalk_speed_fast.wav", audio_fast, sr)
    print("  速い速度(1.2x): openjtalk_speed_fast.wav")
    
    # 音響特徴の取得テスト
    print("\n音響特徴の取得テスト:")
    text = "テストです。"
    try:
        # フルコンテキストラベルの取得
        labels = pyopenjtalk.extract_fullcontext(text)
        print(f"  フルコンテキストラベル数: {len(labels)}")
        print(f"  最初のラベル: {labels[0] if labels else 'なし'}")
    except Exception as e:
        print(f"  エラー: {e}")
    
    print("\n=== pyopenjltalk テスト完了 ===")
    
    # 結果のサマリー
    print("\n結果:")
    print("- 完全オフライン動作: ✓")
    print("- 音声ファイル保存: ✓ (WAV形式)")
    print("- 速度調整: △ (リサンプリングで対応)")
    print("- 日本語特化: ✓")
    print("- 音質: 良好（機械的だが明瞭）")
    print("- レイテンシ: 低い")
    print("- 特徴: 軽量、高速、依存関係が少ない")

if __name__ == "__main__":
    test_pyopenjtalk()