# ウェイクワード・VAD ファイル入力 PoC (2026-09-30)

Apple M1 Max / macOS 26、Python 3.13.4 (`uv venv`)、16 kHz mono。マイク・音声再生・既存 AccessKey は使わない。`say -v Kyoko -o ja.aiff 'オッケーセバス。今日の天気を教えて。'` と `say -v Samantha -o hey-jarvis.aiff 'hey jarvis'` の出力を `ffmpeg -ar 16000 -ac 1` で WAV 化。`bench.py` が日本語音声を 1 秒の先行無音・600 ms の中間無音・1 秒の末尾無音を挟んで 2 回配置する。もう一方は同一波形に seed=42 の白色ノイズを振幅 0.01 (フルスケール基準 −40 dB、RMS は約 −40 dBFS) 加算したもの。参照区間は 1.000–3.938 秒 / 4.538–7.475 秒。参照境界は合成ファイルの配置位置であって、`say` 自体の内部無音を除去した音素境界ではない。

## VAD

`uv pip install silero-vad onnxruntime webrtcvad sherpa-onnx numpy soundfile 'setuptools<81'`。`webrtcvad` 2.0.10 は `pkg_resources` が必要で、setuptools 84 では import に失敗したため `<81` に固定。Silero 6.2.3、sherpa-onnx 1.13.8、openwakeword 0.6.0。`python bench.py` は WAV を作り直し、処理とモデル初期化時間を標準出力に出す。

| 条件 | VAD | 検出区間 (秒) | 対参照の開始ずれ (ms; 2 発話) | 対参照の終了ずれ (ms; 2 発話) | 処理時間 (音声 8.475 秒) | 入力チャンク | 終了待ち設定 |
|---|---|---|---|---|---|---|---|
| 無音 | Silero ONNX | 1.024–4.000 / 4.576–7.552 | +24 / +38 | +62 / +77 | 63.1 ms | 32 ms | `min_silence_duration_ms=300` |
| 無音 | WebRTC (aggressiveness 2) | 1.040–4.040 / 4.580–7.580 | +40 / +42 | +102 / +105 | 1.3 ms | 20 ms | アプリ側 15 frames = 300 ms |
| 無音 | sherpa-onnx Silero | 1.012–4.052 / 4.564–7.604 | +12 / +26 | +114 / +129 | 37.1 ms | 32 ms | `min_silence_duration=0.3` 秒 |
| 白色ノイズ | Silero ONNX | 1.056–4.064 / 4.576–7.616 | +56 / +38 | +126 / +141 | 34.1 ms | 32 ms | 同上 |
| 白色ノイズ | WebRTC | 0–0.080 (誤検出) / 1.040–2.060 / 2.360–4.000 / 4.580–7.520 | 一つ目が分裂 / +42 | 一つ目が分裂 / +45 | 1.0 ms | 20 ms | 同上 |
| 白色ノイズ | sherpa-onnx Silero | 1.012–4.116 / 4.564–7.700 | +12 / +26 | +178 / +225 | 36.5 ms | 32 ms | 同上 |

処理時間は一度の wall-clock 計測で初期化・WAV 生成を除外し、負荷・実時間遅延の保証値ではない。終了ずれは**音声末尾の推定位置**であり、**終了イベントが届くまでの待ち時間ではない**。Silero の `get_speech_timestamps` はファイル全体の offline 処理であり、32 ms は内部推論窓。実時間終了イベントはおおよそ「最後の有音判定から 300 ms + 最大 32 ms の窓待ち」だがこの PoC では時刻を観測していない。WebRTC の判定は 20 ms ごとだが、内部 hangover にアプリ側の 300 ms が加わる。ここでの終了位置は最後の有音フレームの後端を返しており、15 フレームを確認した時点で初めて確定する。sherpa-onnx は 300 ms の内蔵設定を持つ。生活音そのものは白色ノイズでは再現できない。

**Mac 側推奨:** Silero ONNX。軽いノイズで区間が分裂せず、依存性と推論パスが単純。ストリーミングの endpoint 通知と生活音・複数話者の実録音評価は次段階。sherpa-onnx も利用できるがこのサンプルでは終了側が長く出た。

## ウェイクワード

| 候補 | 観測 / 条件 | 日本語カスタム経路と ESP32-S3 |
|---|---|---|
| Porcupine | 既存実験で macOS の「オッケーセバス」専用 `.ppn` + 日本語 `.pv` があり、別の四つの既製語では CPU 2.4% / 32.5 MB と記録。今回 AccessKey を読まず、推論も実施しない | Picovoice Console でカスタムワードを作るにはアカウント / AccessKey が必要。既存 mac 用 `.ppn` は ESP32 用として流用できない。公式 Microcontroller SDK ドキュメントは Arm Cortex-M4 のみを列挙し ESP32-S3 の対応を確認できなかった。料金ページの本文を取得できず、2026 年現在の無料枠・商用条件は**未確認**。契約前に公式へ問い合わせる。 |
| openWakeWord | v0.6.0 / macOS Apple Silicon / ONNX モデルを `openwakeword.utils.download_models(['hey_jarvis'])` で取得し、`say -v Samantha 'hey jarvis'` に前後 1 秒の無音を付加。80 ms ごと推論して `hey_jarvis_v0.1` 最大 **0.999191**、ピーク 2.00 秒。実際に検出できた。 | [公式自動学習 notebook](https://github.com/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb) と [簡易 Colab](https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb?usp=sharing)。日本語 TTS で「オッケーセバス」を多声種・速度・ノイズで数千件生成、非対象語の negative 音声を用意し、共有 feature extractor の上で分類器を訓練、実録音で false accept / false reject を測る。[合成音声手順](https://github.com/dscripka/openWakeWord/blob/main/docs/synthetic_data_generation.md)。日本語学習は時間・データ量を要するため未実施。コード Apache-2.0、配布済みモデルは CC BY-NC-SA 4.0。ESP32-S3 向け動作は未確認。 |
| ESP-SR WakeNet / MultiNet | 実機なし、調査のみ。WakeNet9 は ESP32-S3 に対応、WakeNet の custom は Espressif に依頼、公式には 2～3 週間、トレーニング有償、独自コーパスなら 20,000 件・500 人以上の条件 | [公式カスタム手順](https://docs.espressif.com/projects/esp-sr/en/latest/esp32s3/wake_word_engine/ESP_Wake_Words_Customization.html)。日本語対応は資料で明示されず問い合わせが必要。MultiNet はコマンド認識で、wake word 自体の代替ではない。[ESP-SR](https://github.com/espressif/esp-sr) のモデル個別ライセンスと量産費用は導入前に要確認。 |
| microWakeWord | 実機なし、調査のみ。ESP32-S3 用 ESPHome との連携実績がある [microWakeWord](https://github.com/kahrendt/microWakeWord) は Apache-2.0 | [学習 notebook](https://github.com/kahrendt/microWakeWord/tree/main/notebooks) で自前モデルを訓練できる。ただし公式 README は notebook を出発点とし、既定の学習結果をそのまま実用品と見なさないよう注意。日本語の多話者 TTS・negative データを作り、実機で誤検出率を測る。ライブラリ自体の利用は無償だが訓練計算資源とデータ収集に費用がかかる。 |

**ESP32-S3 側推奨:** 自前学習でき、ESP32-S3 への適用経路がある microWakeWord を最初に試す。量産品質での日本語カスタムモデルが必要なら WakeNet の有償カスタムについて Espressif に可否と費用を確認する。Porcupine は Arm Cortex-M4 SDK のみ確認できたので現時点では選ばない。検出品質の推奨ではなく、調達・実装可能性を優先した暫定判断。

再現例: `uv venv .venv; uv pip install --python .venv/bin/python silero-vad onnxruntime webrtcvad sherpa-onnx openwakeword numpy soundfile 'setuptools<81'; .venv/bin/python bench.py`。合成原音 `ja.wav` は作成済み。音声合成エンジンが出す間合いで参照区間の端点が変化する。`openwakeword` のモデルは仮想環境内へダウンロードされる。
