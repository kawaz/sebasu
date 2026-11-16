#!/usr/bin/env python3
"""
APIキーフォーマットの検証
"""

import os
from dotenv import load_dotenv

# .envファイル読み込み
load_dotenv()

# APIキー取得
key = os.environ.get('PICOVOICE_ACCESS_KEY')

print("APIキー分析:")
print(f"長さ: {len(key)} 文字")
print(f"最初の10文字: {key[:10]}...")
print(f"最後の10文字: ...{key[-10:]}")
print()

# 特殊文字チェック
special_chars = []
for char in key:
    if not char.isalnum() and char not in ['-', '_', '.']:
        if char not in special_chars:
            special_chars.append(char)

if special_chars:
    print(f"特殊文字が含まれています: {special_chars}")
    print("これが原因でパースエラーが発生している可能性があります")
else:
    print("特殊文字は含まれていません")

# 基本的な構造チェック
parts = key.split('.')
print(f"\nドット区切りの部分数: {len(parts)}")

# 推奨事項
print("\n推奨事項:")
print("1. Picovoice Consoleで新しいAPIキーを生成してみてください")
print("2. キーに特殊文字（!など）が含まれないものを選択してください")
print("3. または、キーを引用符で囲んでみてください")