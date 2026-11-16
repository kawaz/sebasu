# ファイル構成

## 本番用ファイル

### 基本機能
- `voicevox_manager.py` - VOICEVOXエンジンの管理（起動・停止・セットアップ）
- `vsay` - コマンドラインTTSツール（VOICEVOX直接利用）
- `vsay2` - コマンドラインTTSツール（APIサーバー経由）

### APIサーバー
- `tts_api_server.py` - シンプルAPIサーバー（ポート8000）
- `tts_api_priority.py` - 優先度・割り込み機能付きAPIサーバー（ポート8002）
- `tts_api_adaptive.py` - 環境適応型APIサーバー（ポート8003）

### その他
- `outputs/` - 音声ファイルの出力ディレクトリ
- `voicevox_engine/` - VOICEVOXエンジン本体（.gitignore済み）

## アーカイブ済みファイル

`archive/`ディレクトリに以下のファイルが保存されています：

### テスト・デモ
- バサラさん関連のデモファイル
- 各種テストスクリプト
- 測定・ベンチマークスクリプト

### 実験的機能
- 環境適応の詳細実装
- マルチセンサー統合のプロトタイプ
- デバッグ用スクリプト

## 使い方

### 基本的な音声合成
```bash
# VOICEVOXエンジンを起動
uv run python voicevox_manager.py start

# 音声を再生
./vsay "こんにちは"
```

### APIサーバー経由
```bash
# APIサーバーを起動
uv run python tts_api_server.py

# 別ターミナルから利用
./vsay2 "APIサーバー経由で話します"
```

### 高度な機能
```bash
# 優先度付きAPIサーバー
uv run python tts_api_priority.py

# 環境適応型APIサーバー
uv run python tts_api_adaptive.py
```