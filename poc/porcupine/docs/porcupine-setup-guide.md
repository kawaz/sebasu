# Picovoice Porcupine セットアップガイド

> **最終更新**: 2025-06-22
> **カテゴリ**: Guide
> **関連文書**: [技術決定事項](technical-decisions.md), [最終実装計画](final-implementation-plan.md)

## 概要

Picovoice Porcupineは、高精度で低リソースなウェイクワード検出エンジンです。このガイドでは、セットアップから実装までの手順を説明します。

## クイックスタート

### 1. アカウント作成とAPIキー取得

1. [Picovoice Console](https://console.picovoice.ai/)でアカウント作成
2. ダッシュボードから「AccessKey」を取得
3. 環境変数に設定:
   ```bash
   export PICOVOICE_ACCESS_KEY='your-access-key-here'
   ```

### 2. パッケージインストール

```bash
# Python環境（uvを推奨）
uv pip install pvporcupine pvrecorder
```

### 3. 基本実装

```python
import pvporcupine
import pvrecorder

# Porcupine初期化
porcupine = pvporcupine.create(
    access_key="your-key",
    keywords=["alexa", "computer"]  # プリセットキーワード
)

# レコーダー初期化
recorder = pvrecorder.PvRecorder(frame_length=porcupine.frame_length)
recorder.start()

# 検出ループ
while True:
    pcm = recorder.read()
    keyword_index = porcupine.process(pcm)
    
    if keyword_index >= 0:
        print(f"Wake word detected: {keywords[keyword_index]}")
```

## カスタム日本語ウェイクワード

### 作成手順

1. [Picovoice Console](https://console.picovoice.ai/)にログイン
2. 「Wake Word」→「Train Wake Word」
3. 設定:
   - **Wake phrase**: 日本語フレーズ（例：「ねえハウス」）
   - **Language**: Japanese (ja)
   - **Target Platform**: 使用するプラットフォーム
4. 「Train」をクリック（約3-5分）
5. `.ppn`ファイルをダウンロード

### 推奨ウェイクワード

家族向けの使いやすいウェイクワード:
- **「ねえハウス」** - 短くて言いやすい
- **「おっけーはうす」** - 子供にも発音しやすい
- **「おーけーはうす」** - より丁寧な発音

### 実装例

```python
# カスタムウェイクワードの使用
porcupine = pvporcupine.create(
    access_key=access_key,
    keyword_paths=['wake_words/ねえハウス.ppn'],
    sensitivities=[0.5]  # 感度調整（0-1）
)
```

### 日本語モデルの注意点（2025-06-25追記）

**重要**: 日本語のウェイクワードを使用する場合、対応する日本語モデルファイル（`porcupine_params_ja.pv`）が必要です。

```python
# 日本語ウェイクワードの正しい使用方法
porcupine = pvporcupine.create(
    access_key=access_key,
    keyword_paths=['wake_words/オッケーセバス_ja_mac_v3_0_0.ppn'],
    model_path='path/to/porcupine_params_ja.pv',  # 日本語モデルを指定
    sensitivities=[0.7]
)
```

モデルファイルは以下から取得可能:
- GitHubリポジトリ: `https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_ja.pv`
- ファイルサイズ: 約1MB

自動ダウンロード機能の実装例は[sandbox/porcupine/porcupine_helper.py](../sandbox/porcupine/porcupine_helper.py)を参照。

## 複数ウェイクワード対応

異なる発音パターンに対応するための実装:

```python
# 複数パターン登録
keywords = [
    ('wake_words/おっけーはうす.ppn', 0.5),  # メイン
    ('wake_words/おーけーはうす.ppn', 0.4),  # サブ
]

porcupine = pvporcupine.create(
    access_key=access_key,
    keyword_paths=[k[0] for k in keywords],
    sensitivities=[k[1] for k in keywords]
)
```

## パフォーマンス特性

実測値（macOS、2025年6月22日）:
- **CPU使用率**: 2.4%
- **メモリ使用量**: 32.5MB
- **検出精度**: 97%以上
- **レイテンシ**: <100ms

## トラブルシューティング

### APIキーエラー
```bash
# 環境変数が設定されているか確認
echo $PICOVOICE_ACCESS_KEY

# .envファイルを使用する場合
python -m dotenv run python your_script.py
```

### マイクが認識されない
```python
# 利用可能なデバイスを確認
import pvrecorder
print(pvrecorder.PvRecorder.get_available_devices())

# 特定のデバイスを使用
recorder = pvrecorder.PvRecorder(
    frame_length=512,
    device_index=1  # 例: MacBook Proのマイク
)
```

マイクテストツール: [sandbox/porcupine/test_microphone.py](../sandbox/porcupine/test_microphone.py)

### 検出精度の調整
- 感度を上げる: 0.6-0.8（検出しやすくなるが誤検出も増える）
- 感度を下げる: 0.3-0.4（誤検出は減るが検出しにくくなる）

### 言語モデルエラー
```
Keyword file (.ppn) and model file (.pv) should belong to the same language
```
このエラーは言語の不一致を示しています。日本語ウェイクワードには日本語モデルを使用してください。

## 統合例（Whisperとの連携）

```python
class VoiceAssistant:
    def __init__(self):
        # Porcupine（ウェイクワード）
        self.porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=['wake_words/ねえハウス.ppn']
        )
        
        # Whisper（音声認識）
        self.whisper_model = whisper.load_model("base")
        
    def run(self):
        recorder = pvrecorder.PvRecorder(
            frame_length=self.porcupine.frame_length
        )
        recorder.start()
        
        while True:
            # ウェイクワード待機（低消費電力）
            pcm = recorder.read()
            if self.porcupine.process(pcm) >= 0:
                print("ウェイクワード検出！")
                
                # 音声認識開始
                audio = self.record_audio(5)  # 5秒録音
                text = self.whisper_model.transcribe(audio, language='ja')
                print(f"認識結果: {text['text']}")
```

## ライセンスと料金

### 無料枠（Personal Tier）
- 個人利用: 無制限
- 商用利用: 3ユーザーまで
- カスタムウェイクワード: 月3つまで
- APIキー: 必要（認証のみ）

### 注意事項
- 音声データは外部送信されない
- 完全ローカル動作
- オフライン環境でも使用可能

## 関連ドキュメント

- [サンドボックス検証結果](sandbox-findings.md#3-porcupine2025年6月22日)
- [技術決定事項](technical-decisions.md#2-ウェイクワード検出)
- [Porcupine公式ドキュメント](https://picovoice.ai/docs/porcupine/)