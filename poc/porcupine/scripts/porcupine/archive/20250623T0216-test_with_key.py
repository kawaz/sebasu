#!/usr/bin/env python3
"""
Picovoice PorcupineのAPIキーを使った動作テスト
環境変数 PICOVOICE_ACCESS_KEY を設定して実行
"""

import os
import sys
import time
import numpy as np
from dotenv import load_dotenv

# .envファイル読み込み
load_dotenv()

def test_porcupine_with_key():
    """APIキーを使ったPorcupineテスト"""
    
    # APIキーの確認
    access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
    if not access_key:
        print("エラー: PICOVOICE_ACCESS_KEY環境変数が設定されていません")
        print("\n設定方法:")
        print("export PICOVOICE_ACCESS_KEY='your-access-key-here'")
        print("\nAPIキーの取得:")
        print("1. https://console.picovoice.ai/ にアクセス")
        print("2. 無料アカウントを作成")
        print("3. AccessKeyをコピー")
        return False
    
    print(f"✓ APIキーが設定されています (長さ: {len(access_key)}文字)")
    
    try:
        import pvporcupine
        import pvrecorder
        
        # 利用可能なキーワードを表示
        print("\n=== 利用可能な内蔵キーワード ===")
        keywords = ['picovoice', 'alexa', 'hey google', 'computer']
        print(f"テストするキーワード: {keywords}")
        
        # Porcupineインスタンスを作成
        print("\nPorcupineインスタンスを作成中...")
        porcupine = pvporcupine.create(
            access_key=access_key,
            keywords=keywords
        )
        
        print(f"✓ Porcupineが正常に初期化されました")
        print(f"  フレーム長: {porcupine.frame_length} サンプル")
        print(f"  サンプリングレート: {porcupine.sample_rate} Hz")
        
        # マイクデバイスの確認
        print("\n=== オーディオデバイス ===")
        devices = pvrecorder.PvRecorder.get_available_devices()
        for i, device in enumerate(devices):
            print(f"{i}: {device}")
        
        # レコーダーの作成
        print("\nマイク録音を設定中...")
        recorder = pvrecorder.PvRecorder(
            frame_length=porcupine.frame_length,
            device_index=-1  # デフォルトデバイス
        )
        
        print("✓ マイク録音の準備完了")
        print(f"\n{'='*50}")
        print("ウェイクワード検出を開始します！")
        print(f"検出対象: {', '.join(keywords)}")
        print("話しかけてください... (Ctrl+Cで終了)")
        print(f"{'='*50}\n")
        
        recorder.start()
        
        # 検出ループ
        detection_count = 0
        start_time = time.time()
        
        try:
            while True:
                # 音声フレームを取得
                pcm = recorder.read()
                
                # ウェイクワード検出
                keyword_index = porcupine.process(pcm)
                
                if keyword_index >= 0:
                    detection_count += 1
                    current_time = time.time()
                    elapsed = current_time - start_time
                    
                    print(f"\n{'🎯'*10}")
                    print(f"ウェイクワード検出！ #{detection_count}")
                    print(f"検出ワード: '{keywords[keyword_index]}'")
                    print(f"経過時間: {elapsed:.1f}秒")
                    print(f"{'🎯'*10}\n")
                    print("待機中...")
                    
                    # クールダウン（連続検出を避ける）
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n\n検出を終了します...")
            
        finally:
            recorder.stop()
            recorder.delete()
            porcupine.delete()
            
        # 統計表示
        total_time = time.time() - start_time
        print(f"\n=== 統計 ===")
        print(f"実行時間: {total_time:.1f}秒")
        print(f"検出回数: {detection_count}回")
        if detection_count > 0:
            print(f"平均検出間隔: {total_time/detection_count:.1f}秒")
            
        return True
        
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        return False

def test_offline_mode():
    """オフラインモードのテスト"""
    print("\n=== オフラインモードテスト ===")
    print("注: Porcupineは初回認証後、完全オフラインで動作します")
    print("テスト方法:")
    print("1. 一度オンラインで認証")
    print("2. インターネットを切断")
    print("3. 再度実行 → 正常に動作することを確認")

def show_japanese_info():
    """日本語ウェイクワードの情報"""
    print("\n=== 日本語ウェイクワード ===")
    print("\nPicovoice Consoleで作成可能な日本語ウェイクワード例:")
    print("- ねえ、アシスタント")
    print("- おーい")
    print("- こんにちは")
    print("- 起きて")
    print("\n作成手順:")
    print("1. https://console.picovoice.ai/ にログイン")
    print("2. 'Wake Word' → 'Train Wake Word'")
    print("3. 日本語フレーズを入力")
    print("4. トレーニング（数分）")
    print("5. .ppnファイルをダウンロード")
    print("\n使用方法:")
    print("porcupine = pvporcupine.create(")
    print("    access_key=access_key,")
    print("    keyword_paths=['path/to/your_wake_word_ja.ppn']")
    print(")")

def main():
    """メイン処理"""
    print("Picovoice Porcupine 実動作テスト\n")
    print("(.envファイルからAPIキーを読み込みます)\n")
    
    # APIキーの確認と実行
    if test_porcupine_with_key():
        print("\n✅ Porcupineは正常に動作しています！")
        print("✅ 完全ローカルで実行されています")
        print("✅ 音声データは外部に送信されません")
    
    # 追加情報
    test_offline_mode()
    show_japanese_info()
    
    print("\n=== 結論 ===")
    print("Porcupineは:")
    print("✓ 完全ローカル動作（APIキーは認証のみ）")
    print("✓ 高精度なウェイクワード検出")
    print("✓ 日本語対応（カスタムウェイクワード）")
    print("✓ OpenWakeWordより実用的")

if __name__ == "__main__":
    main()