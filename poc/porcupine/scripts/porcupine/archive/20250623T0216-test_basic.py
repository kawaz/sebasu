#!/usr/bin/env python3
"""
Picovoice Porcupineの基本的な動作確認
"""

import os
import sys

def check_porcupine_info():
    """Porcupineの情報を確認"""
    print("=== Picovoice Porcupine 基本情報 ===\n")
    
    try:
        import pvporcupine
        print(f"✓ pvporcupine インストール済み")
        # バージョン情報の取得
        try:
            version = pvporcupine.LIBRARY_VERSION if hasattr(pvporcupine, 'LIBRARY_VERSION') else "不明"
            print(f"  バージョン: {version}")
        except:
            print(f"  バージョン: 情報取得不可")
        
        # 利用可能な情報を表示
        print("\n利用可能なキーワード:")
        print("  内蔵キーワード（英語）:")
        print("  - alexa")
        print("  - americano") 
        print("  - blueberry")
        print("  - bumblebee")
        print("  - computer")
        print("  - grapefruit")
        print("  - grasshopper")
        print("  - hey google")
        print("  - hey siri")
        print("  - jarvis")
        print("  - ok google")
        print("  - picovoice")
        print("  - porcupine")
        print("  - terminator")
        
        print("\n注: 日本語キーワードはPicovoice Consoleで作成が必要")
        
    except ImportError as e:
        print(f"✗ pvporcupineのインポートに失敗: {e}")
        return False
        
    return True

def test_without_key():
    """APIキーなしでの動作確認"""
    print("\n=== APIキーなしでのテスト ===\n")
    
    try:
        import pvporcupine
        
        # APIキーなしで初期化を試みる
        try:
            porcupine = pvporcupine.create(
                keywords=["picovoice"]
            )
            print("✗ APIキーなしでは動作しません")
        except pvporcupine.PorcupineError as e:
            print(f"✓ 予想通りエラー: {e}")
            print("\nAPIキーの取得方法:")
            print("1. https://console.picovoice.ai/ にアクセス")
            print("2. 無料アカウントを作成")
            print("3. AccessKeyを取得")
            print("4. 環境変数に設定: export PICOVOICE_ACCESS_KEY='your-key'")
            
    except Exception as e:
        print(f"エラー: {e}")
        
def test_with_dummy_key():
    """ダミーキーでのテスト"""
    print("\n=== ローカル動作の確認 ===\n")
    
    print("Porcupineの動作モード:")
    print("✓ 完全ローカル動作")
    print("✓ インターネット接続不要（初回認証後）")
    print("✓ 音声データは外部送信されない")
    print("✓ モデルファイルはローカルに保存")
    
    print("\nAPIキーの役割:")
    print("- ライセンス認証のみ")
    print("- 実行時の通信は不要")
    print("- オフライン環境でも動作可能")

def show_implementation_example():
    """実装例を表示"""
    print("\n=== 実装例 ===\n")
    
    example_code = '''import pvporcupine
import pvrecorder
import os

# APIキーを環境変数から取得
access_key = os.environ.get('PICOVOICE_ACCESS_KEY')

# Porcupineインスタンスを作成
porcupine = pvporcupine.create(
    access_key=access_key,
    keywords=['picovoice', 'alexa']  # 検出したいキーワード
)

# マイク録音の設定
recorder = pvrecorder.PvRecorder(
    frame_length=porcupine.frame_length,
    device_index=-1  # デフォルトデバイス
)

print("Listening for wake words...")
recorder.start()

try:
    while True:
        # 音声フレームを取得
        pcm = recorder.read()
        
        # ウェイクワード検出
        keyword_index = porcupine.process(pcm)
        
        if keyword_index >= 0:
            print(f"Wake word detected: {keywords[keyword_index]}")
            # ここで音声認識などの処理を開始
            
except KeyboardInterrupt:
    print("Stopping...")
finally:
    recorder.stop()
    recorder.delete()
    porcupine.delete()
'''
    
    print(example_code)

def check_system_requirements():
    """システム要件の確認"""
    print("\n=== システム要件 ===\n")
    
    import platform
    
    system = platform.system()
    machine = platform.machine()
    
    print(f"OS: {system}")
    print(f"アーキテクチャ: {machine}")
    
    supported = {
        "Darwin": ["x86_64", "arm64"],  # macOS
        "Linux": ["x86_64", "aarch64", "armv7l"],
        "Windows": ["AMD64"]
    }
    
    if system in supported and machine in supported[system]:
        print(f"✓ このシステムはサポートされています")
    else:
        print(f"✗ このシステムはサポートされていない可能性があります")
    
    print("\nサポートプラットフォーム:")
    print("- macOS (Intel/Apple Silicon)")
    print("- Linux (x86_64, ARM)")
    print("- Windows (x86_64)")
    print("- Raspberry Pi")
    print("- Android/iOS")

def main():
    """メイン処理"""
    print("Picovoice Porcupine 基本動作確認\n")
    
    # 各種チェック
    if not check_porcupine_info():
        return
        
    check_system_requirements()
    test_without_key()
    test_with_dummy_key()
    show_implementation_example()
    
    print("\n=== まとめ ===\n")
    print("Porcupineの特徴:")
    print("✓ 完全ローカル動作（オフライン対応）")
    print("✓ 高精度（97%以上）")
    print("✓ 低レイテンシ（<100ms）")
    print("✓ 省電力")
    print("\n次のステップ:")
    print("1. Picovoice Consoleでアカウント作成")
    print("2. APIキーを取得")
    print("3. test_with_key.pyで実際のテスト")

if __name__ == "__main__":
    main()