#!/usr/bin/env python3
"""
Porcupine初期化のみのテスト
"""

import os
import sys

def test_init():
    """初期化テスト"""
    print("Porcupine初期化テスト\n")
    
    # APIキー確認
    access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
    if not access_key:
        print("エラー: PICOVOICE_ACCESS_KEY環境変数が設定されていません")
        print("source .envrc を実行してください")
        return False
    
    print(f"✓ APIキー検出 (長さ: {len(access_key)})")
    
    try:
        import pvporcupine
        print("✓ pvporcupineモジュールのインポート成功")
        
        # 最小限の初期化
        print("\n初期化中...")
        porcupine = pvporcupine.create(
            access_key=access_key,
            keywords=['picovoice']
        )
        
        print("✅ Porcupineの初期化に成功しました！")
        print(f"  - フレーム長: {porcupine.frame_length}")
        print(f"  - サンプリングレート: {porcupine.sample_rate}")
        
        # クリーンアップ
        porcupine.delete()
        print("\n✓ クリーンアップ完了")
        
        return True
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        return False

if __name__ == "__main__":
    if test_init():
        print("\n正常に動作しています。")
        print("次は test_with_key.py でウェイクワード検出を試してください。")
    else:
        print("\n初期化に失敗しました。")
        print("APIキーを確認してください。")