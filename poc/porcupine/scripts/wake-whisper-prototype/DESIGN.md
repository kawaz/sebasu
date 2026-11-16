# ウェイクワード + Whisper 連続記録プロトタイプ設計書

## 概要
ウェイクワードを検出したら即座にWhisperによる音声認識を開始し、認識結果をDuckDBに記録し続けるプロトタイプ。

## アーキテクチャ

### コンポーネント構成
```
┌─────────────────────┐
│  メインプロセス      │
│  (main.py)          │
└──────┬──────────────┘
       │
       ├─────────────────┐
       │                 │
┌──────▼────────┐ ┌─────▼──────────┐
│ ウェイクワード │ │ 音声認識       │
│ 検出スレッド   │ │ スレッド       │
│ (Porcupine)   │ │ (Whisper)      │
└───────────────┘ └────────────────┘
       │                 │
       └────────┬────────┘
                │
        ┌───────▼────────┐
        │   DuckDB       │
        │   データベース  │
        └────────────────┘
```

### 状態遷移
```
待機中 → ウェイクワード検出 → 録音開始 → 音声認識 → DB保存 → 待機中
```

## データベース設計

### テーブル: voice_requests
```sql
CREATE TABLE voice_requests (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    wake_word TEXT,                    -- 検出されたウェイクワード
    audio_duration_seconds REAL,       -- 音声の長さ
    transcribed_text TEXT,             -- 認識されたテキスト
    confidence REAL,                   -- 認識の信頼度
    language TEXT,                     -- 検出された言語
    audio_file_path TEXT,              -- 保存された音声ファイルパス（オプション）
    processing_time_ms INTEGER         -- 処理時間（ミリ秒）
);
```

## 実装方針

### 1. 音声入力の管理
- PyAudioで単一のストリームを開き、両方のコンポーネントで共有
- リングバッファを使用して音声データを管理

### 2. スレッド設計
- **メインスレッド**: 全体の制御とUI表示
- **ウェイクワード検出スレッド**: Porcupineで常時監視
- **音声認識スレッド**: ウェイクワード検出後に起動

### 3. 音声録音の区切り判定
- 無音検出（1.5秒以上の無音で区切り）
- 最大録音時間（30秒）
- ユーザーによる中断（Ctrl+C）

### 4. エラーハンドリング
- ネットワークエラー時はローカルWhisperにフォールバック
- 音声デバイスエラー時は再接続を試行
- DB書き込みエラー時はローカルファイルにバックアップ

## ディレクトリ構造
```
wake-whisper-prototype/
├── DESIGN.md              # この設計書
├── pyproject.toml         # プロジェクト設定
├── .env                   # 環境変数（Picovoice APIキー）
├── main.py                # メインエントリーポイント
├── src/
│   ├── __init__.py
│   ├── wake_word.py       # ウェイクワード検出
│   ├── audio_recorder.py  # 音声録音管理
│   ├── transcriber.py     # Whisper音声認識
│   ├── database.py        # DuckDB操作
│   └── config.py          # 設定管理
├── data/
│   ├── voice_requests.db  # DuckDBデータベース
│   └── audio/             # 音声ファイル保存（オプション）
└── logs/                  # ログファイル
```

## 依存パッケージ
- pvporcupine (ウェイクワード検出)
- openai-whisper (音声認識)
- pyaudio (音声入力)
- duckdb (データベース)
- python-dotenv (環境変数)
- numpy (音声処理)
- loguru (ロギング)

## 設定項目
- PICOVOICE_ACCESS_KEY: Picovoice APIキー
- WAKE_WORD: 使用するウェイクワード（デフォルト: "jarvis"）
- WHISPER_MODEL: Whisperモデルサイズ（デフォルト: "base"）
- SILENCE_THRESHOLD: 無音判定の閾値
- MAX_RECORDING_SECONDS: 最大録音時間
- SAVE_AUDIO_FILES: 音声ファイルを保存するか（デフォルト: False）

## 今後の拡張性
1. 複数のウェイクワード対応
2. リアルタイムストリーミング音声認識
3. 音声コマンドの解析と分類
4. WebUIでの履歴表示
5. 音声フィードバック（認識開始/終了の音）