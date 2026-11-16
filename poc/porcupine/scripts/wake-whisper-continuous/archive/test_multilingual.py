#!/usr/bin/env python3
"""多言語ウェイクワード検出のテスト"""

import sys
from pathlib import Path
from config import Config
from multilingual_wake_detector import MultilingualWakeWordDetector
from loguru import logger

def test_multilingual_detection():
    """多言語検出の設定をテスト"""
    logger.info("多言語ウェイクワード検出のテストを開始...")
    
    # 検出器を作成
    detector = MultilingualWakeWordDetector()
    
    # 初期化
    if not detector.initialize():
        logger.error("初期化に失敗しました")
        return False
    
    # 結果表示
    print(f"\n✅ 多言語検出器初期化成功!")
    print(f"サポート言語: {', '.join(detector.get_supported_languages())}")
    
    print(f"\n📋 登録されたウェイクワード:")
    for lang, wake_words in detector.wake_words_by_lang.items():
        print(f"\n言語: {lang}")
        for ww in wake_words:
            print(f"  - {ww['name']} ({ww['type']})")
    
    # クリーンアップ
    detector.cleanup()
    
    return True

if __name__ == "__main__":
    # 設定の検証
    Config.validate()
    
    # ログ設定
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # テスト実行
    if test_multilingual_detection():
        print("\n✅ テスト成功: 多言語ウェイクワードが設定できます！")
    else:
        print("\n❌ テスト失敗")
        sys.exit(1)