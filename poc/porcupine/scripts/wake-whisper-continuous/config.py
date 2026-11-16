"""設定管理モジュール"""
import os
from pathlib import Path

class Config:
    # Picovoice
    PICOVOICE_ACCESS_KEY = os.environ.get('PICOVOICE_ACCESS_KEY')
    
    # ウェイクワード設定
    # カスタムppnファイルがあればそれを使用、なければデフォルトキーワード
    CUSTOM_PPN_DIR = Path("ppn")
    DEFAULT_KEYWORDS = ["ok google", "alexa", "jarvis", "computer", "picovoice"]
    WAKE_SENSITIVITY = 0.5  # 感度 (0.3-1.0)
    
    # Whisper設定
    WHISPER_MODEL = "small"  # 既存実装と同じ
    WHISPER_LANGUAGE = "ja"
    
    # 音声録音設定
    SAMPLE_RATE = 16000
    CHUNK_SIZE = 512  # Porcupineの要求に合わせる
    
    # マルチレベルバッファ設定（オーバーラップ追加）
    BUFFER_LEVELS = {
        'short': {'duration': 3, 'overlap': 1.0, 'color': '\033[96m'},   # シアン
        'medium': {'duration': 8, 'overlap': 2.0, 'color': '\033[93m'},  # 黄色
        'long': {'duration': 20, 'overlap': 5.0, 'color': '\033[92m'},   # 緑
        'ultra': {'duration': 120, 'overlap': 0, 'color': '\033[95m'}, # マゼンタ（無音区切り）
    }
    
    # 無音検出
    SILENCE_THRESHOLD = 300  # 既存実装から
    SILENCE_DURATION = 2.0   # 2秒の無音で区切り
    INITIAL_SILENCE_IGNORE = 3.0  # ウェイクワード後の最初の3秒は無音検出を無視
    
    # フィードバック
    WAKE_SOUND_ENABLED = True  # ウェイクワード検出時の音声フィードバック
    
    # データベース
    DATABASE_PATH = Path("data/voice_requests.db")
    
    # 処理設定
    NUM_WORKERS = 2  # Whisper並列処理数
    
    # ログ設定
    LOG_LEVEL = "INFO"
    
    @classmethod
    def validate(cls):
        """設定の検証"""
        if not cls.PICOVOICE_ACCESS_KEY:
            raise ValueError("PICOVOICE_ACCESS_KEY環境変数が設定されていません")
        
        # ディレクトリ作成
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.CUSTOM_PPN_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def get_wake_words(cls):
        """使用するウェイクワードのリストを返す"""
        wake_words = []
        
        # カスタムppnを有効化（porcupine_helperが自動でモデルをダウンロード）
        use_custom = True
        
        # カスタムppnファイルを探す
        if use_custom and cls.CUSTOM_PPN_DIR.exists():
            ppn_files = list(cls.CUSTOM_PPN_DIR.glob("*.ppn"))
            if ppn_files:
                # ppnファイルがあればそれを使用
                for ppn_file in ppn_files:
                    wake_words.append({
                        'type': 'custom',
                        'path': str(ppn_file),
                        'name': ppn_file.stem
                    })
        
        # デフォルトキーワードも追加（カスタムppnと併用）
        for keyword in cls.DEFAULT_KEYWORDS:
            wake_words.append({
                'type': 'builtin',
                'keyword': keyword,
                'name': keyword
            })
        
        return wake_words