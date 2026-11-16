# Porcupine 複数言語ウェイクワード同時検出の実装ガイド

## 概要

Porcupineで「オッケーセバス」（日本語）と「OK Google」（英語）のような異なる言語のウェイクワードを同時に検出する方法について調査した結果をまとめます。

## 調査結果

### 1. Porcupineの制限事項

**重要な発見**: Porcupineの`create()`関数の`model_path`パラメータは**単一のモデルファイルしか受け付けません**。

```python
# これは動作しない
porcupine = pvporcupine.create(
    access_key=access_key,
    keyword_paths=['オッケーセバス_ja.ppn', 'OK-Google_en.ppn'],
    model_path='porcupine_params_ja.pv'  # 日本語モデルのみ
)
# → 英語のppnファイルは日本語モデルでは処理できない
```

### 2. Porcupineの複数言語サポート

公式ドキュメントによると：
- Porcupineは**複数のウェイクワードを同時に検出可能**
- **複数の言語を同時にサポート**
- ただし、これは「複数のモデルを同時に実行することで実現」という意味

## 実装方法

### 方法1: 複数インスタンスによる実装（推奨）

各言語用に別々のPorcupineインスタンスを作成し、並列で実行します。

```python
class MultilingualWakeWordDetector:
    def __init__(self):
        self.detectors = {}
        self.wake_words = {}
        
    def initialize(self):
        """複数言語の検出器を初期化"""
        
        # 日本語検出器
        self.detectors['ja'] = pvporcupine.create(
            access_key=Config.PICOVOICE_ACCESS_KEY,
            keyword_paths=['ppns/オッケーセバス_ja_mac_v3_0_0.ppn'],
            model_path='models/porcupine_params_ja.pv'
        )
        self.wake_words['ja'] = ['オッケーセバス']
        
        # 英語検出器
        self.detectors['en'] = pvporcupine.create(
            access_key=Config.PICOVOICE_ACCESS_KEY,
            keyword_paths=['ppns/OK-Google_en_mac_v3_0_0.ppn'],
            model_path='models/porcupine_params_en.pv'  # または省略（デフォルト）
        )
        self.wake_words['en'] = ['OK Google']
    
    def process_audio(self, audio_frame):
        """全ての言語で音声を処理"""
        for lang, detector in self.detectors.items():
            keyword_index = detector.process(audio_frame)
            if keyword_index >= 0:
                return {
                    'language': lang,
                    'wake_word': self.wake_words[lang][keyword_index],
                    'index': keyword_index
                }
        return None
    
    def cleanup(self):
        """全ての検出器をクリーンアップ"""
        for detector in self.detectors.values():
            detector.delete()
```

### 方法2: 既存のWakeWordDetectorを拡張

現在のプロジェクトの`wake_detector.py`を拡張する実装案：

```python
class MultilingualWakeWordDetector(WakeWordDetector):
    def __init__(self):
        super().__init__()
        self.language_detectors = {}
        
    def initialize(self):
        """複数言語対応の初期化"""
        try:
            # 言語別にウェイクワードをグループ化
            wake_words_by_lang = self._group_by_language()
            
            # 各言語用の検出器を作成
            for lang, words in wake_words_by_lang.items():
                detector = self._create_language_detector(lang, words)
                if detector:
                    self.language_detectors[lang] = {
                        'detector': detector,
                        'wake_words': words
                    }
            
            return len(self.language_detectors) > 0
            
        except Exception as e:
            logger.error(f"初期化エラー: {e}")
            return False
    
    def _group_by_language(self):
        """ウェイクワードを言語別にグループ化"""
        groups = {}
        for wake_word in Config.get_wake_words():
            lang = self._detect_language(wake_word)
            if lang not in groups:
                groups[lang] = []
            groups[lang].append(wake_word)
        return groups
    
    def _detect_language(self, wake_word):
        """ウェイクワードから言語を検出"""
        if wake_word['type'] == 'custom':
            # ppnファイル名から言語を検出
            return detect_language_from_ppn(wake_word['path'])
        else:
            # ビルトインは基本的に英語
            return 'en'
    
    def _create_language_detector(self, lang, wake_words):
        """言語別の検出器を作成"""
        keyword_paths = []
        keywords = []
        
        for word in wake_words:
            if word['type'] == 'custom':
                keyword_paths.append(word['path'])
            else:
                keywords.append(word['keyword'])
        
        # モデルパスを取得
        model_path = get_model_path(lang) if lang != 'en' else None
        
        # Porcupineインスタンスを作成
        if keyword_paths:
            return pvporcupine.create(
                access_key=Config.PICOVOICE_ACCESS_KEY,
                keyword_paths=keyword_paths,
                model_path=model_path
            )
        elif keywords:
            return pvporcupine.create(
                access_key=Config.PICOVOICE_ACCESS_KEY,
                keywords=keywords,
                model_path=model_path
            )
        
        return None
```

### 方法3: スレッドプールによる並列処理（高度な実装）

```python
import concurrent.futures
from threading import Lock

class ThreadedMultilingualDetector:
    def __init__(self, max_workers=4):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.detectors = {}
        self.result_lock = Lock()
        self.latest_detection = None
        
    def add_detector(self, language, detector, wake_words):
        """言語別検出器を追加"""
        self.detectors[language] = {
            'detector': detector,
            'wake_words': wake_words
        }
    
    def process_audio_async(self, audio_frame):
        """非同期で全検出器を実行"""
        futures = []
        
        for lang, info in self.detectors.items():
            future = self.executor.submit(
                self._process_single_detector,
                lang, info['detector'], info['wake_words'], audio_frame
            )
            futures.append(future)
        
        # 最初に検出したものを返す
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                # 他のタスクをキャンセル
                for f in futures:
                    f.cancel()
                return result
        
        return None
    
    def _process_single_detector(self, language, detector, wake_words, audio_frame):
        """単一検出器での処理"""
        try:
            keyword_index = detector.process(audio_frame)
            if keyword_index >= 0:
                return {
                    'language': language,
                    'wake_word': wake_words[keyword_index]['name'],
                    'timestamp': time.time()
                }
        except Exception as e:
            logger.error(f"{language}検出器エラー: {e}")
        return None
```

## パフォーマンスとリソース使用量

### メモリ使用量
- 各Porcupineインスタンスは独立したメモリを使用
- 1インスタンスあたり約10-20MB（モデルサイズによる）
- 2言語なら約20-40MBの追加メモリ

### CPU使用率
- 各インスタンスは独立して処理を実行
- Raspberry Pi 4では3-4言語まで実用的
- 並列処理を使用する場合はCPUコア数を考慮

### レイテンシ
- 逐次処理: 言語数 × 処理時間
- 並列処理: 最も遅い検出器の処理時間

## 実装上の注意点

### 1. モデルファイルの管理
```python
# porcupine_helper.pyを使用して自動ダウンロード
model_path_ja = get_model_path('ja')
model_path_en = get_model_path('en')  # デフォルトなので不要
```

### 2. ppnファイルの作成
- Picovoice Consoleで各言語用のppnファイルを作成
- ファイル名に言語コードを含める（例: `オッケーセバス_ja_mac_v3_0_0.ppn`）

### 3. エラーハンドリング
```python
def safe_process_audio(self, audio_frame):
    """エラーに強い音声処理"""
    results = []
    
    for lang, detector_info in self.detectors.items():
        try:
            result = detector_info['detector'].process(audio_frame)
            if result >= 0:
                results.append((lang, result))
        except Exception as e:
            logger.warning(f"{lang}検出器でエラー: {e}")
            # エラーが発生しても他の言語の処理は継続
    
    return results
```

### 4. 設定ファイルの拡張
```python
# config.py の拡張例
WAKE_WORDS = [
    {
        'name': 'オッケーセバス',
        'type': 'custom',
        'path': 'ppns/オッケーセバス_ja_mac_v3_0_0.ppn',
        'language': 'ja'
    },
    {
        'name': 'OK Google',
        'type': 'custom',
        'path': 'ppns/OK-Google_en_mac_v3_0_0.ppn',
        'language': 'en'
    }
]
```

## まとめ

1. **Porcupineは1インスタンスで1言語モデルのみサポート**
2. **複数言語の同時検出には複数インスタンスが必要**
3. **推奨実装は方法1の複数インスタンス管理**
4. **リソース使用量は言語数に比例して増加**

この実装により、「オッケーセバス」と「OK Google」を同時に検出できるようになります。