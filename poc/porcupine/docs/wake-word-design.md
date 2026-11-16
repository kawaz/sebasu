# ウェイクワード機能設計書

## 目次
1. [概要](#概要)
2. [ウェイクワード検出の仕組み](#ウェイクワード検出の仕組み)
3. [既存ライブラリの比較](#既存ライブラリの比較)
4. [カスタムウェイクワードの実装方法](#カスタムウェイクワードの実装方法)
5. [省電力での常時待機方法](#省電力での常時待機方法)
6. [開発環境向け推奨](#開発環境向け推奨)
7. [本番環境向け推奨](#本番環境向け推奨)

## 概要

ウェイクワード検出は、音声アシスタントが常時音声を監視し、特定のキーワード（「OK Google」「Hey Siri」など）が発話されたときにアクティブになる技術です。本設計書では、ウェイクワード機能の実装に必要な技術的検討事項と推奨事項をまとめます。

## ウェイクワード検出の仕組み

### 基本的な処理フロー

1. **音声キャプチャ**
   - 16-44.1kHz サンプリングレートで連続的に音声を取得
   - 1024サンプル（16kHzで64ms）のバッファサイズが一般的

2. **特徴量抽出**
   - メルスペクトログラム：人間の聴覚特性に基づく周波数分析
   - MFCC（メル周波数ケプストラム係数）：音声認識で広く使用される特徴量

3. **音響モデリング**
   - DNN（深層ニューラルネットワーク）ベースのアプローチが主流
   - CNN、RNN/LSTM、またはハイブリッドアーキテクチャを使用

4. **判定処理**
   - スコアリング：モデル出力の確率値を計算
   - 閾値判定：設定された閾値を超えた場合にウェイクワードとして検出

### 主要なアプローチ

| アプローチ | 精度 | 特徴 |
|----------|------|------|
| DNN-HMM ハイブリッド | 〜92% | 従来型、安定性が高い |
| CNN ベース | 94.93% | 組み込みシステムに最適 |
| RNN/LSTM | 93.9% | 時系列モデリングに優れる |
| CNN-LSTM-GRU ハイブリッド | 99.87% | 最高精度だが計算負荷大 |

### パフォーマンス指標

- **精度メトリクス**
  - 誤棄却率（FRR）：< 5%
  - 誤受理率（FAR）：< 1回/10時間
  - 応答精度率（RAR）：> 95%

- **レイテンシ**
  - ウェイクワード検出遅延：< 200-500ms

- **リソース使用量**
  - 消費電力：1-10mW（常時動作時）
  - メモリフットプリント：< 1MB
  - CPU使用率：< 5%（ARM Cortex-M4相当）

## 既存ライブラリの比較

### 比較表

| 特徴 | Porcupine | OpenWakeWord |
|-----|-----------|--------------|
| **ライセンス** | 商用（無料枠あり） | Apache 2.0（完全無料） |
| **精度** | 97%以上 | 90-95% |
| **誤検出率** | <1回/10時間 | 1-2回/時間 |
| **対応言語** | 17言語以上 | 主に英語 |
| **モデルサイズ** | 200KB（Tiny）〜1.6MB | 1-3MB |
| **対応プラットフォーム** | 組み込み含む全般 | Linux/Mac/Windows |
| **最小要件** | ARM Cortex-M4 | Raspberry Pi 3以上 |
| **レイテンシ** | <100ms | 80ms（フレーム処理） |
| **カスタマイズ** | 有料オプション | 完全カスタマイズ可能 |

### Porcupine（Picovoice）

**メリット**
- 業界最高クラスの精度（97%以上）
- 極めて低い誤検出率
- 組み込みデバイスでの動作に最適化
- 多言語対応（日本語含む）
- 商用サポートあり

**デメリット**
- 商用利用には有料ライセンスが必要
- カスタムウェイクワードは追加料金
- ソースコードは非公開

**推奨用途**
- 商用製品
- 組み込み/IoTデバイス
- 多言語対応が必要なアプリケーション
- 高精度が要求される環境

### OpenWakeWord

**メリット**
- 完全オープンソース（Apache 2.0）
- 無料でカスタムウェイクワード作成可能
- 活発なコミュニティ
- 柔軟なカスタマイズ

**デメリット**
- Porcupineと比較して精度が劣る
- 主に英語のみ対応
- より高いハードウェア要件
- 商用サポートなし

**推奨用途**
- オープンソースプロジェクト
- プロトタイピング
- 教育・研究目的
- 予算に制約がある場合

## カスタムウェイクワードの実装方法

### 実装ステップ

1. **データ収集**
   ```python
   # 合成音声によるデータ生成例
   from TTS.api import TTS
   
   tts = TTS("tts_models/en/ljspeech/tacotron2-DDC")
   wake_word = "hey assistant"
   
   # 様々な話者で生成
   for voice_params in voice_variations:
       audio = tts.tts(wake_word, **voice_params)
       save_audio(audio, f"wake_word_{i}.wav")
   ```

2. **データ拡張**
   ```python
   # ピッチシフト、ノイズ追加、リバーブなど
   augmented = pitch_shift(audio, semitones=[-2, -1, 0, 1, 2])
   augmented = add_noise(augmented, snr_db=[10, 20, 30])
   augmented = add_reverb(augmented, room_size=[0.1, 0.3, 0.5])
   ```

3. **特徴量抽出**
   ```python
   # MFCC特徴量の抽出
   mfcc_features = librosa.feature.mfcc(
       y=audio, sr=16000, n_mfcc=40,
       n_fft=512, hop_length=160
   )
   ```

4. **モデル構築**
   ```python
   # CNN-LSTMハイブリッドモデル
   model = tf.keras.Sequential([
       Conv2D(32, (3, 3), activation='relu'),
       MaxPooling2D(2, 2),
       LSTM(64, return_sequences=True),
       Dense(1, activation='sigmoid')
   ])
   ```

5. **デプロイメント**
   ```python
   # TensorFlow Liteへの変換
   converter = tf.lite.TFLiteConverter.from_keras_model(model)
   converter.optimizations = [tf.lite.Optimize.DEFAULT]
   tflite_model = converter.convert()
   ```

### 必要なデータ量

- **最小要件**：300-500個の正例サンプル
- **推奨**：1,000-2,000個の正例、10,000個以上の負例
- **転移学習使用時**：100-500個で可能

### 推奨フレームワーク

| フレームワーク | 利点 | 欠点 |
|--------------|------|------|
| TensorFlow Lite | エッジ展開に最適、量子化サポート | 開発の柔軟性が低い |
| PyTorch Mobile | 開発しやすい、デバッグ容易 | モデルサイズが大きめ |
| ONNX Runtime | クロスプラットフォーム | 最適化が手動 |

## 省電力での常時待機方法

### ハードウェアアプローチ

1. **専用チップの使用**
   - **Syntiant NDP120**：140μW以下で動作
   - **Ambiq Apollo**：390μWでウェイクワード検出
   - 通常のマイコンと比較して200倍の電力効率

2. **DSP/NPU活用**
   - Qualcomm Hexagon DSP：専用低電力モード
   - Apple Neural Engine：最適化された推論

### ソフトウェア最適化

1. **カスケード型アーキテクチャ**
   ```
   [軽量モデル] → 初期検出 → [高精度モデル] → 最終判定
        ↓                           ↓
   消費電力: 低                 消費電力: 高（必要時のみ）
   ```

2. **モデル圧縮技術**
   - **INT8量子化**：75%のメモリ/帯域削減、精度低下なし
   - **プルーニング**：50%以上のパラメータ削減可能
   - **知識蒸留**：大規模モデルから小規模モデルへ

3. **動的電力管理**
   ```python
   # 段階的ウェイクアップ
   if detect_voice_activity():  # 5μW
       if detect_wake_word_light():  # 100μW
           if verify_wake_word_full():  # 5mW
               activate_main_system()  # フル電力
   ```

### デバイス別電力目標

| デバイスタイプ | 電力目標 | バッテリー影響 |
|--------------|---------|--------------|
| スマートフォン | <5mW | 1日あたり<1% |
| スマートスピーカー | <50mW | 年間<1kWh |
| IoT/ウェアラブル | <400μW | コイン電池で1年以上 |

## 開発環境向け推奨

### クイックスタート構成

```python
# requirements.txt
openWakeWord==0.6.0
pyaudio==0.2.13
numpy==1.24.3

# simple_wake_word.py
import openwakeword
from openwakeword.model import Model
import pyaudio
import numpy as np

# モデルの初期化
model = Model(
    wakeword_models=["hey_assistant"],
    inference_framework="onnx"
)

# 音声ストリーミング
p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    input=True,
    frames_per_buffer=1280
)

# 検出ループ
while True:
    audio = np.frombuffer(
        stream.read(1280), 
        dtype=np.int16
    )
    
    prediction = model.predict(audio)
    if prediction["hey_assistant"] > 0.5:
        print("Wake word detected!")
```

### 開発環境の推奨事項

1. **ライブラリ選択**
   - プロトタイプ：OpenWakeWord（無料、簡単）
   - 精度重視：Porcupine無料版（3ユーザーまで）

2. **テスト環境**
   - 複数の話者でテスト
   - 背景ノイズありでテスト
   - 異なる距離からテスト

3. **パフォーマンス測定**
   ```python
   # CPU使用率とレイテンシ測定
   import time
   import psutil
   
   start_time = time.time()
   cpu_before = psutil.cpu_percent()
   
   # ウェイクワード処理
   result = model.predict(audio_chunk)
   
   latency = (time.time() - start_time) * 1000
   cpu_usage = psutil.cpu_percent() - cpu_before
   ```

## 本番環境向け推奨

### アーキテクチャ設計

```
┌─────────────────┐
│  マイクアレイ    │
└────────┬────────┘
         │
┌────────▼────────┐
│ ノイズキャンセリング │
└────────┬────────┘
         │
┌────────▼────────┐
│ 第1段階検出      │ ← 超低電力（<1mW）
│ (簡易モデル)     │
└────────┬────────┘
         │
┌────────▼────────┐
│ 第2段階検証      │ ← 低電力（<10mW）
│ (高精度モデル)   │
└────────┬────────┘
         │
┌────────▼────────┐
│ メインシステム起動 │ ← フル電力
└─────────────────┘
```

### 実装チェックリスト

- [ ] **音声品質**
  - [ ] ノイズ抑制/エコーキャンセレーション実装
  - [ ] 適応的ゲインコントロール
  - [ ] ビームフォーミング（複数マイク時）

- [ ] **モデル最適化**
  - [ ] 量子化（INT8以下）
  - [ ] プルーニング（50%以上削減）
  - [ ] プラットフォーム固有最適化

- [ ] **電力管理**
  - [ ] Wake-on-Sound実装
  - [ ] 動的周波数スケーリング
  - [ ] 段階的ウェイクアップ

- [ ] **信頼性**
  - [ ] フォールバック機構
  - [ ] エラーリカバリー
  - [ ] OTA更新対応

### 本番環境推奨構成

**組み込み/IoTデバイス**
- Porcupine + 専用ハードウェア（Syntiant等）
- 電力効率と精度の最適バランス

**モバイルアプリ**
- Porcupine（商用）またはTensorFlow Lite（カスタム）
- プラットフォームAPIとの統合

**スマートスピーカー/家電**
- 2段階検出システム
- DSP/NPU活用必須

### セキュリティ考慮事項

1. **プライバシー保護**
   - オンデバイス処理を優先
   - 音声データの暗号化
   - 最小限のデータ保持

2. **攻撃対策**
   - 敵対的サンプル検出
   - 話者認証の追加
   - レート制限実装

## まとめ

ウェイクワード機能の実装において、開発フェーズではOpenWakeWordを使用した迅速なプロトタイピングを推奨し、本番環境では要件に応じてPorcupineまたはカスタム実装を選択することを推奨します。省電力化には専用ハードウェアとソフトウェア最適化の組み合わせが不可欠であり、デバイスタイプに応じた適切な設計が重要です。