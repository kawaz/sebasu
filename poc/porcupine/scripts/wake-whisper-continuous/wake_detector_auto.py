"""自動判定ウェイクワード検出器ファクトリー"""
from typing import Union
from loguru import logger
from config import Config
from wake_detector import WakeWordDetector
from multilingual_wake_detector import MultilingualWakeWordDetector
from porcupine_helper import detect_language_from_ppn

def create_wake_detector() -> Union[WakeWordDetector, MultilingualWakeWordDetector]:
    """
    ウェイクワード設定から自動的に適切な検出器を作成
    
    複数言語のウェイクワードがある場合は多言語検出器を使用
    単一言語の場合は通常の検出器を使用
    """
    # 使用するウェイクワードを取得
    wake_words = Config.get_wake_words()
    
    if not wake_words:
        raise ValueError("使用可能なウェイクワードがありません")
    
    # 言語を判定
    languages = set()
    
    for wake_word in wake_words:
        if wake_word['type'] == 'custom':
            # カスタムppnファイルから言語を検出
            language = detect_language_from_ppn(wake_word['path'])
            languages.add(language)
        else:
            # ビルトインキーワードは英語と仮定
            languages.add('en')
    
    # 言語数に応じて検出器を選択
    if len(languages) > 1:
        logger.info(f"複数言語を検出 ({', '.join(languages)}) - 多言語検出器を使用")
        return MultilingualWakeWordDetector()
    else:
        logger.info(f"単一言語を検出 ({list(languages)[0]}) - 通常の検出器を使用")
        return WakeWordDetector()