# DR-001: VOICEVOX TTS セットアップと運用設計

## 背景

Voice Agentプロジェクトの音声合成コンポーネントとして、複数のTTSライブラリを比較検討した結果、VOICEVOXを採用した。本DRでは、採用理由と運用上の設計判断を記録する。

## 決定

### 1. HTTP API方式を採用（Pythonバインディングは不採用）

VOICEVOXには2つの利用方式がある：

| 方式 | 初期化 | 合成(avg) | エンジン常駐 |
|---|---|---|---|
| HTTP API | 不要（常駐済み） | 0.870s | 必要 |
| Python バインディング | 0.735s | 0.913s | 不要 |

**選択理由**: ベンチマーク結果、HTTP APIの方が合成速度も速く、初期化コストもない。Pythonバインディングはモデル読み込みが毎回必要で、常駐エンジンの方が効率的。

### 2. launchd で自動起動・定期再起動

- `com.voicevox.engine.plist`: ログイン時起動 + KeepAlive（クラッシュ時自動復帰）
- `com.voicevox.engine.restart.plist`: 毎日AM2:00に `launchctl kickstart -k` で再起動

**選択理由**: メモリリークの実績データがないため、予防的に日次再起動。KeepAliveにより再起動後も自動復帰する。

### 3. 発話先頭の聞き取りにくさ対策

- `prePhonemeLength` を 0.1（デフォルト）→ 0.5 に変更
- 先頭モーラのpitch/vowel_length強調機能を追加（オプション）

**選択理由**: macOSのオーディオデバイスがスリープから復帰する間に先頭の音声が欠ける。500msの無音挿入で解消。モーラ強調は補助的効果。

### 4. vsay CLIの設計

- サブコマンドなしでテキストを渡した場合、`direct` サブコマンドとして扱う（`vsay "テキスト"` で即使える）
- `uv run` 経由で実行し、依存パッケージの解決をuvに委譲
- `os.path.realpath(__file__)` でsymlink先を解決し、どこからでも実行可能

## 不採用技術

### edge-tts
- 音質は高いがクラウド依存。ローカルファースト設計方針に反する。

### pyttsx3
- macOSでAttributeError。動作不安定。

### pyopenjtalk
- 軽量・高速（0.03-0.09秒）だが音質が機械的。Raspberry Pi向けの代替として残す。

## ファイル構成

```
sandbox/tts-comparison/
├── vsay                    # 統合CLIエントリポイント（~/bin/vsay からsymlink）
├── vsay_direct.py          # VOICEVOX直接利用の実装
├── vsay_api.py             # APIサーバー経由の実装
├── voicevox_manager.py     # エンジン管理（setup/start/stop）
├── voicevox_engine -> voicevox_engine-macos-arm64-0.25.1/
└── bench_tts.py            # HTTP API vs Pythonバインディングのベンチマーク

~/Library/LaunchAgents/
├── com.voicevox.engine.plist          # 自動起動設定
└── com.voicevox.engine.restart.plist  # 日次再起動設定
```
