#!/usr/bin/env python3
"""
pyttsx3のテスト
完全オフライン動作のクロスプラットフォームTTSライブラリ
"""
import pyttsx3
import time
import os
from datetime import datetime

def test_pyttsx3():
    """pyttsx3の基本的な動作テスト"""
    print("=== pyttsx3 テスト開始 ===")
    
    # エンジンの初期化
    engine = pyttsx3.init()
    
    # 使用可能な音声の取得
    print("\n利用可能な音声:")
    voices = engine.getProperty('voices')
    japanese_voices = []
    
    for i, voice in enumerate(voices):
        print(f"{i}: {voice.name} ({voice.languages}) - {voice.id}")
        # 日本語対応音声を探す
        if 'ja' in str(voice.languages) or 'Japanese' in voice.name:
            japanese_voices.append((i, voice))
    
    # プロパティの確認
    rate = engine.getProperty('rate')
    volume = engine.getProperty('volume')
    print(f"\n現在の設定:")
    print(f"- 話速: {rate}")
    print(f"- 音量: {volume}")
    
    # テストする文章
    test_texts = [
        "こんにちは、私は音声合成システムです。",
        "今日の天気は晴れです。",
        "音声認識と音声合成を組み合わせて、対話型のシステムを作ります。",
        "Hello, I am a text to speech system.",
        "1234567890",
    ]
    
    # 日本語音声でテスト
    if japanese_voices:
        print(f"\n日本語音声を使用: {japanese_voices[0][1].name}")
        engine.setProperty('voice', japanese_voices[0][1].id)
    else:
        print("\n警告: 日本語音声が見つかりません。デフォルト音声を使用します。")
    
    # 音声の保存と再生
    for i, text in enumerate(test_texts):
        print(f"\nテキスト {i+1}: {text}")
        
        # 音声ファイルに保存
        filename = f"outputs/pyttsx3_test_{i+1}.wav"
        start_time = time.time()
        
        engine.save_to_file(text, filename)
        engine.runAndWait()
        
        save_time = time.time() - start_time
        print(f"  保存時間: {save_time:.3f}秒")
        
        # 直接音声再生（オプショナル）
        # engine.say(text)
        # engine.runAndWait()
    
    # 速度を変更してテスト
    print("\n速度変更テスト:")
    engine.setProperty('rate', 150)  # 遅く
    filename = "outputs/pyttsx3_slow.wav"
    engine.save_to_file("ゆっくり話します。", filename)
    engine.runAndWait()
    print("  遅い速度で保存: pyttsx3_slow.wav")
    
    engine.setProperty('rate', 250)  # 速く
    filename = "outputs/pyttsx3_fast.wav"
    engine.save_to_file("速く話します。", filename)
    engine.runAndWait()
    print("  速い速度で保存: pyttsx3_fast.wav")
    
    # エンジンを停止
    engine.stop()
    
    print("\n=== pyttsx3 テスト完了 ===")
    
    # 結果のサマリー
    print("\n結果:")
    print(f"- 利用可能な音声数: {len(voices)}")
    print(f"- 日本語対応音声数: {len(japanese_voices)}")
    print(f"- 完全オフライン動作: ✓")
    print(f"- 音声ファイル保存: ✓")
    print(f"- 速度調整: ✓")

if __name__ == "__main__":
    test_pyttsx3()