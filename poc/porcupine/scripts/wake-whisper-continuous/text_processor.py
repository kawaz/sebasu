"""テキスト処理ユーティリティ"""
import re
from typing import Optional, List

# ウェイクワードのバリエーション（正規化用）
WAKE_WORD_VARIATIONS = {
    'オッケーセバス': ['おっけーせばす', 'okせばす', 'おっけーセバス', 'オッケーセバス'],
    'ok google': ['ok google', 'okay google', 'おけーぐーぐる', 'okぐるぐる', 'okが来る'],
    'alexa': ['alexa', 'アレクサ'],
    'jarvis': ['jarvis', 'ジャービス'],
    'computer': ['computer', 'コンピューター'],
    'picovoice': ['picovoice', 'ピコボイス']
}

def remove_wake_word(text: str, wake_word_name: str) -> str:
    """
    テキストからウェイクワードを除去
    
    Args:
        text: 認識されたテキスト
        wake_word_name: 検出されたウェイクワード名
        
    Returns:
        ウェイクワードを除去したテキスト
    """
    if not text or not wake_word_name:
        return text
    
    # ウェイクワードのバリエーションを取得
    variations = []
    for key, values in WAKE_WORD_VARIATIONS.items():
        if key.lower() == wake_word_name.lower() or wake_word_name.lower() in [v.lower() for v in values]:
            variations.extend(values)
            variations.append(key)
            break
    
    # バリエーションがない場合は元のウェイクワード名を使用
    if not variations:
        variations = [wake_word_name]
    
    # 各バリエーションを試して除去
    result = text
    for variation in variations:
        # 文頭のウェイクワードを除去（大文字小文字を無視）
        pattern = f'^{re.escape(variation)}[\\s　,、.。]*'
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        
        # 除去できたら終了
        if result != text:
            break
    
    # 前後の空白を除去
    result = result.strip()
    
    # 何も残らなかった場合は元のテキストを返す
    return result if result else text

def is_wake_word_only(text: str, wake_word_name: str) -> bool:
    """
    テキストがウェイクワードのみかどうかを判定
    
    Args:
        text: 認識されたテキスト
        wake_word_name: 検出されたウェイクワード名
        
    Returns:
        ウェイクワードのみの場合True
    """
    cleaned = remove_wake_word(text, wake_word_name)
    # 除去後が空または記号のみの場合はウェイクワードのみ
    return not cleaned or re.match(r'^[\\s　,、.。…]*$', cleaned) is not None