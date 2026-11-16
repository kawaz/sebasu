#!/usr/bin/env python3
"""
Porcupineヘルパー関数
言語に応じたモデルファイルの自動ダウンロードを含む
"""
import os
import urllib.request
from pathlib import Path

# 言語モデルのURLマッピング
MODEL_URLS = {
    'ja': 'https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_ja.pv',
    'en': 'https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_en.pv',
    'de': 'https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_de.pv',
    'es': 'https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_es.pv',
    'fr': 'https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_fr.pv',
    'it': 'https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_it.pv',
    'ko': 'https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_ko.pv',
    'pt': 'https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_pt.pv',
    'zh': 'https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_zh.pv',
}

def detect_language_from_ppn(ppn_path):
    """PPNファイル名から言語を検出"""
    filename = Path(ppn_path).name
    
    # ファイル名から言語コードを抽出
    # 例: "オッケーセバス_ja_mac_v3_0_0.ppn" -> "ja"
    parts = filename.split('_')
    for part in parts:
        if part in MODEL_URLS:
            return part
    
    # デフォルトは英語
    return 'en'

def get_model_path(language='en', model_dir=None):
    """言語に対応したモデルファイルのパスを取得（必要に応じてダウンロード）"""
    if model_dir is None:
        model_dir = Path(__file__).parent / 'models'
    else:
        model_dir = Path(model_dir)
    
    # モデルディレクトリを作成
    model_dir.mkdir(exist_ok=True)
    
    # モデルファイル名
    model_filename = f'porcupine_params_{language}.pv'
    model_path = model_dir / model_filename
    
    # 既に存在する場合はそのパスを返す
    if model_path.exists():
        return str(model_path)
    
    # ダウンロードが必要
    if language not in MODEL_URLS:
        raise ValueError(f"サポートされていない言語: {language}")
    
    print(f"🌐 {language}モデルをダウンロード中...")
    url = MODEL_URLS[language]
    
    try:
        urllib.request.urlretrieve(url, model_path)
        print(f"✅ ダウンロード完了: {model_path}")
        return str(model_path)
    except Exception as e:
        print(f"❌ ダウンロードエラー: {e}")
        raise

def create_porcupine_with_auto_model(access_key, keyword_paths, sensitivities=None, model_dir=None):
    """
    PPNファイルの言語を自動検出して、適切なモデルでPorcupineを作成
    """
    import pvporcupine
    
    # 最初のキーワードファイルから言語を検出
    if isinstance(keyword_paths, str):
        keyword_paths = [keyword_paths]
    
    language = detect_language_from_ppn(keyword_paths[0])
    print(f"🔍 検出された言語: {language}")
    
    # モデルファイルを取得（必要に応じてダウンロード）
    model_path = get_model_path(language, model_dir)
    
    # Porcupineインスタンスを作成
    if sensitivities is None:
        sensitivities = [0.5] * len(keyword_paths)
    
    return pvporcupine.create(
        access_key=access_key,
        keyword_paths=keyword_paths,
        sensitivities=sensitivities,
        model_path=model_path
    )

if __name__ == "__main__":
    # テスト
    print("Porcupineヘルパーのテスト")
    print("=" * 60)
    
    # 言語検出テスト
    test_files = [
        "オッケーセバス_ja_mac_v3_0_0.ppn",
        "hey_house_en_windows_v3_0_0.ppn",
        "test.ppn"
    ]
    
    for filename in test_files:
        lang = detect_language_from_ppn(filename)
        print(f"{filename} -> {lang}")