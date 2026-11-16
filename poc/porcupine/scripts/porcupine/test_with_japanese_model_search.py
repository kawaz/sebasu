#!/usr/bin/env python3
"""
日本語モデルの自動ダウンロードを試みる
"""
import os
import sys
import pvporcupine
import urllib.request
from pathlib import Path

# APIキー確認
access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
if not access_key:
    raise ValueError("PICOVOICE_ACCESS_KEY環境変数が設定されていません")

print("日本語モデルサポートの確認")
print("=" * 60)

# Porcupineのバージョン確認
try:
    print(f"Porcupineバージョン: {pvporcupine.__version__}")
except:
    print("バージョン情報なし")

# サポートされている言語を確認
try:
    # Porcupineの内部メソッドを探索
    import inspect
    members = inspect.getmembers(pvporcupine)
    for name, obj in members:
        if 'language' in name.lower() or 'model' in name.lower():
            print(f"Found: {name}")
except:
    pass

# 利用可能なキーワードを確認
print("\n利用可能な組み込みキーワード:")
try:
    print(pvporcupine.KEYWORDS)
except:
    print("キーワードリストが見つかりません")

# モデルパスの構築を試みる
print("\n日本語モデルパスの推測:")
base_path = Path(pvporcupine.__file__).parent
possible_paths = [
    base_path / "lib" / "common" / "porcupine_params_ja.pv",
    base_path / "lib" / "mac" / "porcupine_params_ja.pv",
    base_path / "resources" / "porcupine_params_ja.pv",
    base_path / "models" / "porcupine_params_ja.pv",
]

for path in possible_paths:
    if path.exists():
        print(f"✅ 見つかりました: {path}")
    else:
        print(f"❌ 存在しません: {path}")

# Picovoiceのモデルダウンロードを試みる
print("\n代替案: pvporcupineパッケージの再インストール")
print("以下のコマンドで日本語サポートを含む完全版をインストールできるかもしれません:")
print("uv pip install pvporcupine[ja]")
print("または")
print("uv pip install pvporcupine-ja")