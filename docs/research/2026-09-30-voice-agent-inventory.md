# voice-agent 棚卸し (2026-09-30)

対象: `~/.local/share/repos/github.com/kawaz/voice-agent/` (読み取りのみ。主な作業は 2025-06-22〜27、最終コミットは 2026-03-08 の DR-001 / vsay 改善)。以下のパスはリポルートからの相対パス。

## 要約 (10 行)

1. kawaz が「軽くて精度よかった」と記憶しているのは **Picovoice Porcupine** とみてほぼ確実。実測が残っているのは Porcupine だけで、M1 Mac で CPU 2.4% / メモリ 32.5MB、約 4 分で 9 回検出、誤検出ほぼなし (`sandbox/porcupine/PERFORMANCE_RESULTS.md`)
2. openWakeWord v0.6.0 は macOS で動かず (モデルが取れない / tflite 非対応。SIGSEGV という記述もある) 不採用。whisper ベースのウェイクワードは「Whisper + VAD」案として挙がっただけで、実装はされなかった
3. 日本語カスタムウェイクワード「オッケーセバス」(.ppn、**mac 専用ビルド**) を作り、Porcupine → Whisper の連続動作まで確認済み (2025-06-27)
4. STT は Whisper ローカル (開発は base、本番は small) を選んだ。数値の実測は「small で 2〜8 倍速」程度しか残っていない
5. TTS は VOICEVOX の HTTP API を DR-001 で採用。合成 0.87s (平均)。pyopenjtalk は 0.03〜0.09s と速いが音が機械的なので、低スペック向けの控え
6. 未解決: 環境ノイズ下での発話終了判定 (VAD) と、統合したことによる複雑化。結論は「単機能プロセスを疎結合にする」
7. 前提は **Mac で開発し、本番は Raspberry Pi 4 単体** (マイク HAT を付けて全部をデバイス内で処理)。ESP32 に触れているのは比較表の 1 行だけで、音声をサーバに送る (WebRTC) 構成は検討されていない
8. 話者分離は pyannote を使う案の文書だけで、実装も検証もしていない。話者判定 (誰の声か) は検討されていない
9. 今回の構想で詰まりそうな点: Porcupine の .ppn はプラットフォームごとのビルドで、ESP32-S3 向けに出せるか・無料枠の条件が今どうなっているかは**未確認**

## 1. 何を試して、どう結論したか

### ウェイクワード

| 方式 | 結論 | 根拠 |
|---|---|---|
| Porcupine | **採用**。完全ローカルで動く (API キーは初回認証だけ)。日本語のカスタムワードを作れる | `docs/technical-decisions.md` §2, `sandbox/porcupine/FINDINGS.md` |
| openWakeWord v0.6.0 | 不採用。macOS でモデルを使えず、検出まで行かなかった | `sandbox/openwakeword/docs/FINDINGS.md`, `docs/SUMMARY.md` |
| Whisper + VAD (ウェイクワードを使わない) | 代替案として名前が出ただけ。未実装 | `docs/technical-decisions.md` |

- openWakeWord が動かなかった理由は文書によって違う。`docs/sandbox-findings.md` は「推論時に SIGSEGV」、`sandbox/openwakeword/docs/FINDINGS.md` は「モデルがダウンロードされず、tflite も入らない」と書いている。openWakeWord 自体の欠陥ではなく環境構築の問題だった可能性があり、今の版で動くかは未確認
- Porcupine は **1 インスタンスで 1 言語**しか扱えない (`All keywords must belong to the same language`)。そのため言語ごとにインスタンスを分けて、日本語と英語を同時に検出する実装にした (`docs/work-logs/20250627T1040-multilingual-wake-word.md`, `sandbox/wake-whisper-continuous/multilingual_wake_detector.py`)
- `docs/wake-word-detection-comparison.md` の比較はネットで調べた公称値 (97%、<1 誤検出/10h、openWakeWord は「ESP32-S3 では数秒かかる可能性」など) で、実測ではない

### STT

- 決定したのは Whisper ローカル版。開発は base (74MB)、本番は small (244MB)。whisper.cpp も選択肢として挙がっている (`docs/technical-decisions.md` §1)
- `docs/speech-recognition-engine-comparison.md` は机上の比較 (Web Speech / Whisper / Google / Azure / Amazon / Julius) で、推奨は「MVP は Web Speech、本番は Google」。これはローカルファーストの決定と食い違っていて、technical-decisions の方が後から書かれた正本と読める
- 実装で得た知見 (`docs/sandbox-findings.md`): 3 秒 / 8 秒 / 20 秒 / 無音区切りの多段認識、オーバーラップ処理が必須、無音時に Whisper が定型句を幻聴する、固有名詞と数字を誤認識する

### TTS

- DR-001 (`docs/decision-records/DR-001-voicevox-tts-setup.md`) で VOICEVOX を HTTP API で常駐させ、launchd で自動起動し毎日再起動する形にした。`prePhonemeLength` を 0.5 にして、スリープ明けのデバイスで発話の頭が欠ける問題を回避
- 不採用にしたもの: edge-tts (クラウド)、pyttsx3 (macOS で落ちる)、pyopenjtalk (音質が低いので Raspberry Pi 向けの控え)。macOS の say (Kyoko) は開発用として良好 (`sandbox/tts-comparison/FINDINGS.md`)

### アーキテクチャ

- DR は DR-001 の 1 本だけ。アーキテクチャの決定は `docs/technical-decisions.md` に書かれていて、ローカルファースト、Porcupine を常駐させて検出したときだけ Whisper を動かす、という内容
- 実装してみての結論 (`sandbox/wake-whisper-continuous/README.md`): ウェイクワード検出は文字起こしとは別のマイクストリームで処理し、リングバッファは文字起こし専用にする。単機能プロセスを疎結合でつなぐ (マイクロサービス化 + オーケストレーター)

## 2. 実測値

| 項目 | 値 | 日付 | 環境 | 出典 |
|---|---|---|---|---|
| Porcupine のプロセス CPU | 2.4% | 2025-06-22 | M1 Mac、4 語 (picovoice/computer/jarvis/alexa) を常時検出 | `sandbox/porcupine/PERFORMANCE_RESULTS.md` |
| Porcupine のメモリ | 32.5MB | 同上 | 同上 | 同上 |
| Porcupine の検出 | 約 4 分で 9 回検出、誤検出「ほぼなし」(母数と試行数の記録なし) | 同上 | 同上 | 同上 |
| Porcupine のセットアップ | 約 15 分 | 同上 | | `sandbox/porcupine/FINDINGS.md` |
| Whisper small の速度 | 実時間の 2〜8 倍 (音声の長さによる) | 2025-06-22 | Mac (機種の記載なし) | `docs/sandbox-findings.md` |
| Whisper を常時動かしたときの CPU | 20〜50% (実測かどうか不明、未確認) | | | `sandbox/porcupine/PERFORMANCE_RESULTS.md` |
| 音声検出の RMS 閾値 | 200〜250 が最適 / 実環境の無音 RMS は 20〜100 | 06-22 / 06-27 | Mac | `docs/sandbox-findings.md`, `docs/work-logs/20250627T1727-v3-improvements.md` |
| VOICEVOX HTTP API の合成 | 平均 0.870s (Python バインディングは 0.913s、初期化に 0.735s) | 2026-03 頃 | Apple Silicon, engine 0.25.1 | DR-001 |
| VOICEVOX を最適化した後 | 0.3〜0.6s | 2025-06-27 | 同上 | `docs/work-logs/20250627T1445-tts-implementation.md` |
| pyopenjtalk | 0.03〜0.09s / 文 | 2025-06-25 | Apple Silicon | `sandbox/tts-comparison/FINDINGS.md` |
| macOS say | 0.7〜0.8s / 文 | 同上 | 同上 | 同上 |

wake → STT → TTS を通したエンドツーエンドのレイテンシは記録がない。

## 3. 再利用できる資産 (ls と README で確認。実行はしていない)

- `sandbox/wake-whisper-continuous/`: Porcupine と Whisper を統合したもの。`multilingual_wake_detector.py` (言語ごとにインスタンスを分ける)、`porcupine_helper.py`、`event_driven_v3.py` / `multilevel_main.py`
  - `ppn/オッケーセバス_ja_mac_v3_0_0.ppn` (3.6KB、**mac 専用**)、`models/porcupine_params_ja.pv` (986KB、日本語モデル)
- `sandbox/porcupine/`: `resource_monitor.py` (CPU とメモリの計測)、`test_multiple_patterns.py`、`SETUP.md`
- `sandbox/tts-comparison/`: `vsay` CLI、`voicevox_manager.py`、`bench_tts.py`、優先度付きキューや環境音に合わせた音量調整をする API サーバの試作。`voicevox_engine-macos-arm64-0.25.1/` (2.0GB) が展開済みで、DR-001 によると `~/bin/vsay` からリンクされていて現役
- `sandbox/whisper/`: `mic_transcribe_*.py` (VAD と多段認識)
- `sandbox/openwakeword/`: `custom_threshold.py` (閾値をグラフで調整するツール)。検出そのものは動いていない
- どれも uv プロジェクト (`pyproject.toml` と `uv.lock` あり)。今も動くかは未確認。Porcupine の AccessKey は `.mise.local.toml` などにあるとみられる (中身は見ていない)

## 4. 未解決のまま・断念した点

- 生活音のある環境での無音検出と発話終了判定。単純な RMS 閾値では足りず VAD が要る (`sandbox/wake-whisper-continuous/README.md`)
- イベント駆動版でウェイクワードを検出できなかった問題。原因として感度・音声フォーマット・コールバックが候補に挙がったまま、解決の記録がない (`docs/work-logs/20250627T1707-wake-word-detection-issue.md`)
- Whisper が認識結果にウェイクワードを混ぜたり、無音時に幻聴したりする
- 統合を進めて複雑になり、マイクロサービスに分ける方針を出したところで止まっている
- 当初の予定だった Raspberry Pi 実機検証、LLM やコマンド処理との統合、家電操作は着手していない
- ストリーミング TTS は未実装
- DR に Status の欄はなく、issue 管理もされていない

## 5. 今回の構想との違い

| 観点 | voice-agent | 今回の構想 |
|---|---|---|
| 構成 | 1 台で完結 (開発は Mac、本番は Raspberry Pi 4 + ReSpeaker HAT) | ESP32-S3 + XVF3800 がエッジ、処理はサーバ |
| ウェイクワードを動かす場所 | ホスト CPU 上の Porcupine | エッジ (ESP32-S3) |
| 伝送 | なし | WebRTC |
| ESP32 | 比較表の 1 行 (openWakeWord は ESP32-S3 で遅い) だけ | 主役 |
| LLM | なし (コマンド処理は構想だけ) | あり |
| 話者分離 | pyannote の案だけ (`sandbox/whisper/docs/SPEAKER_DIARIZATION.md`)、実装していない | 要検討 |
| 話者判定 | 検討していない | 要検討 |
| マイク処理 (AEC/ビームフォーミング) | 検討していない (ReSpeaker の名前が出るだけ) | XVF3800 が担う |

今回の構想に引き継げるもの: Porcupine で作った日本語ウェイクワードの実績と感触、VOICEVOX の運用ノウハウ (DR-001、発話頭の欠け対策)、「ウェイクワード検出と STT はストリームを分ける」という知見、Whisper の幻聴や誤認識のパターン。
新たに調べる必要があるもの (未確認): Porcupine を ESP32-S3 で使えるか (公式の MCU 対応範囲と .ppn のプラットフォーム)、2026 年時点の Picovoice の無料枠、代替としての ESP-SR (WakeNet) や microWakeWord、openWakeWord の現行版。
