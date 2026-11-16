#!/usr/bin/env python3
"""
日本語モデルのテスト
"""
import os
import pvporcupine

# APIキー確認
access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
if not access_key:
    raise ValueError("PICOVOICE_ACCESS_KEY環境変数が設定されていません")

print("日本語モデルのパスを確認中...")

# Porcupineのモデルパスを確認
try:
    # デフォルトパスを確認
    default_model = pvporcupine.pv_model_path('')
    print(f"デフォルトモデルパス: {default_model}")
except Exception as e:
    print(f"デフォルトパス取得エラー: {e}")

# 言語別モデルパスを探す
languages = ['ja', 'en', 'de', 'es', 'fr']
for lang in languages:
    try:
        model_path = pvporcupine.pv_model_path(f'porcupine_params_{lang}.pv')
        print(f"{lang}: {model_path}")
    except:
        pass

# 日本語ウェイクワードでテスト
print("\n日本語ウェイクワードで初期化テスト...")
ppn_path = "wake_words/オッケーセバス_ja_mac_v3_0_0.ppn"

# 方法1: model_pathを指定しない（自動検出）
print("\n方法1: 自動検出")
try:
    porcupine = pvporcupine.create(
        access_key=access_key,
        keyword_paths=[ppn_path]
    )
    print("✅ 成功！")
    porcupine.delete()
except Exception as e:
    print(f"❌ 失敗: {e}")

# 方法2: 空文字列を指定
print("\n方法2: 空文字列")
try:
    porcupine = pvporcupine.create(
        access_key=access_key,
        keyword_paths=[ppn_path],
        model_path=""
    )
    print("✅ 成功！")
    porcupine.delete()
except Exception as e:
    print(f"❌ 失敗: {e}")