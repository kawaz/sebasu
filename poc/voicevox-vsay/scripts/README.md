# TTS（Text-to-Speech）比較検証サンドボックス

## 目的

Voice Agentプロジェクトで使用する音声合成エンジンを選定するため、複数のTTSライブラリを検証し比較する。

## 検証対象

1. **edge-tts** - Microsoft Edge TTSのPythonラッパー（無料、高品質）
2. **VOICEVOX** - 日本語特化の高品質音声合成（無料、ローカル動作）
3. **pyttsx3** - クロスプラットフォーム対応のオフラインTTS
4. **gTTS** - Google Text-to-Speech（要インターネット接続）
5. **py-openjtalk** - 日本語音声合成（オープンソース）

## 評価基準

- **音質**: 自然さ、聞き取りやすさ
- **速度**: レスポンスタイム、処理速度
- **日本語対応**: 日本語の発音精度
- **オフライン動作**: インターネット接続不要かどうか
- **リソース使用**: CPU/メモリ使用量
- **ライセンス**: 商用利用可能か
- **セットアップの容易さ**: インストールと設定の手間

## ディレクトリ構造

```
tts-comparison/
├── README.md          # このファイル
├── pyproject.toml     # 依存関係
├── edge_tts_test.py   # edge-ttsのテスト
├── voicevox_test.py   # VOICEVOXのテスト
├── pyttsx3_test.py    # pyttsx3のテスト
├── gtts_test.py       # gTTSのテスト
├── openjtalk_test.py  # OpenJTalkのテスト
├── benchmark.py       # 統合ベンチマーク
├── outputs/           # 生成された音声ファイル
└── FINDINGS.md        # 検証結果まとめ
```

## セットアップ

```bash
cd sandbox/tts-comparison
uv init
uv sync
```

## 実行方法

各スクリプトを個別に実行：
```bash
uv run python edge_tts_test.py
uv run python voicevox_test.py
# など
```

統合ベンチマーク：
```bash
uv run python benchmark.py
```