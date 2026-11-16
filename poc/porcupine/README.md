# Porcupine ウェイクワード (保管物)

kawaz/voice-agent で試した Picovoice Porcupine (ウェイクワード検出) の資産を写したもの。日本語カスタムウェイクワード「オッケーセバス」の `.ppn`、日本語モデル `.pv`、Porcupine を使うスクリプト 3 系統、ウェイクワードの調査・作業記録が入っている。スクリプトは移しただけで、ここでは実行していない。

## 中身

| パス | 内容 |
| --- | --- |
| `keywords/オッケーセバス_ja_mac_v3_0_0.ppn` | Picovoice Console で作った「オッケーセバス」のキーワードファイル (3,636 bytes)。言語 ja、macOS 用、v3.0.0 |
| `keywords/LICENSE.txt` | `.ppn` に同梱されていた 1 行の利用条件 (`https://picovoice.ai/docs/terms-of-use/` への案内) |
| `models/porcupine_params_ja.pv` | Porcupine の日本語モデル (986,511 bytes)。`porcupine_helper.py` の取得元と同じ Picovoice の GitHub (`lib/common/porcupine_params_ja.pv`) のもの |
| `scripts/porcupine/` | 元の `sandbox/porcupine/`。既製語 4 つでの CPU / メモリ計測 (`resource_monitor.py`)、カスタムワードの試験スクリプト群、`SETUP.md`、`FINDINGS.md`、`PERFORMANCE_RESULTS.md`、`VALIDATION.md`、`docs/` (カスタムワード作成・複数ワード戦略)、`archive/` (初期の認証・動作確認スクリプト)。uv プロジェクト |
| `scripts/wake-whisper-continuous/` | 元の `sandbox/wake-whisper-continuous/`。Porcupine と Whisper の統合。`multilingual_wake_detector.py` (言語ごとに Porcupine を分ける)、`porcupine_helper.py`、`multilevel_main.py`、`event_driven_v3.py`、`DESIGN.md`、`docs/multilingual-wake-word-implementation.md`。uv プロジェクト |
| `scripts/wake-whisper-prototype/` | 元の `sandbox/wake-whisper-prototype/`。Porcupine の既製語 (既定 `jarvis`) と Whisper で発話を DuckDB に記録する試作。`wake-whisper-continuous` より前の版 |
| `docs/` | voice-agent の `docs/` のうち Porcupine / ウェイクワードが主題の文書 (セットアップ、カスタムワード、設計、ライブラリ比較、技術概要、低消費電力) |
| `docs/work-logs/` | 同じく作業日誌 (Porcupine 導入、カスタムワード対応、統合プロトタイプ、多言語対応、イベント駆動版で検出しない問題、v3 の改善) |
| `docs/ja/` | `docs/` の英語文書 3 本 (`wake-word-detection-comparison.md`、`wake-word-detection-technical-overview.md`、`wake-word-low-power-recommendations.md`) の日本語訳 |

`scripts/porcupine/wake_words/`、`scripts/porcupine/porcupine_params_ja.pv`、`scripts/porcupine/models/`、`scripts/wake-whisper-continuous/ppn/` の `.ppn`、`scripts/wake-whisper-continuous/models/` は、`keywords/` と `models/` の実体を指す symlink。各スクリプトが探す場所に置いてある。

写した文書の中のパス (`sandbox/porcupine/` 等) は voice-agent 側の配置のまま。ここでは `scripts/` の下に読み替える。

## 動かす手順の要点

### 前提

- Picovoice Console (`https://console.picovoice.ai/`) のアカウントと AccessKey が要る。どのスクリプトも AccessKey を環境変数 `PICOVOICE_ACCESS_KEY` から読む (`wake-whisper-prototype` は `python-dotenv` で `.env` も読む)。キーをファイルに書いてコミットしない
- AccessKey は起動時の認証に使い、音声は外部に送らない。認証後はオフラインで動く (`scripts/porcupine/FINDINGS.md`)
- uv と Python。`wake-whisper-continuous` と `wake-whisper-prototype` は 3.11 (`.python-version`)。`uv.lock` の pvporcupine は 3.0.5
- マイク入力の権限 (macOS)

### `.ppn` と `.pv` の組

- `.ppn` は作成時に選んだプラットフォーム用のビルドで、この `.ppn` は macOS 用 (ファイル名の `_mac_`)。Raspberry Pi・ESP32 等の別プラットフォームには流用できず、Picovoice Console で対象プラットフォーム向けに作り直す
- `.ppn` とモデル `.pv` は同じ言語でないと `Keyword file (.ppn) and model file (.pv) should belong to the same language` で失敗する。日本語の `.ppn` には `models/porcupine_params_ja.pv` を `model_path` に渡す。pvporcupine の既定モデルは英語
- `porcupine_helper.py` はファイル名の `_ja_` 等から言語を判定し、`<スクリプトの場所>/models/porcupine_params_<言語>.pv` が無ければ Picovoice の GitHub から取得する

### 1 インスタンス 1 言語

1 つの Porcupine インスタンスには同じ言語のキーワードしか渡せない (`All keywords must belong to the same language`)。日本語と英語を同時に待つ時は言語ごとにインスタンスを作り、同じ音声フレームを両方に渡す (`scripts/wake-whisper-continuous/multilingual_wake_detector.py`、`docs/work-logs/20250627T1040-multilingual-wake-word.md`)。同じインスタンスでカスタム `.ppn` と既製語 (`keywords=`) を混ぜる構成は、この実装では扱っていない (混ぜると既製語だけを使う)。

### 実行例

```sh
cd poc/porcupine/scripts/porcupine
uv sync
export PICOVOICE_ACCESS_KEY="$(security find-generic-password -s sebasu -a picovoice/access-key -w)"   # macOS のキーチェーンから読む
uv run python test_microphone.py                       # マイクの入力レベル確認
uv run python test_wake_word_now.py wake_words/オッケーセバス_ja_mac_v3_0_0.ppn "オッケーセバス" -s 0.7
uv run python resource_monitor.py --duration 3         # 既製語 4 つで CPU / メモリを計測
```

`wake-whisper-continuous` は作業ディレクトリ直下の `ppn/*.ppn` を全部読み、既製語 (`ok google`、`alexa`、`jarvis`、`computer`、`picovoice`) と合わせて待つ (`config.py`)。DuckDB の記録 (`data/voice_requests.db`) も作業ディレクトリ基準に作る。

```sh
cd poc/porcupine/scripts/wake-whisper-continuous
uv sync
uv run python multilevel_main.py
```

`wake-whisper-prototype` は `src/config.py` が `PICOVOICE_ACCESS_KEY`、`WAKE_WORD`、`WHISPER_MODEL`、`WHISPER_LANGUAGE`、`SILENCE_THRESHOLD`、`SILENCE_DURATION_SECONDS`、`MAX_RECORDING_SECONDS`、`DATABASE_PATH`、`SAVE_AUDIO_FILES`、`AUDIO_SAVE_PATH`、`LOG_LEVEL` を環境変数 (または `.env`) から読む。

## 既知の知見

- 実測値: M1 Mac で既製語 4 つ (picovoice / computer / jarvis / alexa) を常時検出してプロセス CPU 2.4%、メモリ 32.5 MB、約 4 分で 9 回検出 (2025-06-22、`scripts/porcupine/PERFORMANCE_RESULTS.md`。計測スクリプトは `scripts/porcupine/resource_monitor.py`)。日本語モデル・カスタム `.ppn` での CPU / メモリの実測記録は無い。`scripts/wake-whisper-continuous/docs/multilingual-wake-word-implementation.md` の「1 インスタンスあたり約 10-20MB」と `scripts/porcupine/SETUP.md` の Raspberry Pi で「CPU 約 10-15%」は、計測の記録が無い数値
- セットアップは約 15 分 (`scripts/porcupine/FINDINGS.md`)
- 「オッケーセバス」の `.ppn` での検出は、`test_wake_word_now.py` で利用者が「うまくいきました」と答えた記録がある (`docs/work-logs/20250625T1200-porcupine-custom-wake-word.md`)。検出率・誤検出の数値は無い
- 感度は 0.5 が既定。上げると検出しやすく誤検出も増える (`docs/porcupine-setup-guide.md`、`docs/custom-wake-word-guide.md`)
- ウェイクワード検出は文字起こしとは別のマイクストリームで処理する方がよい、という結論 (`scripts/wake-whisper-continuous/README.md`)
- Picovoice Console からのカスタムワードの取得は「月 1 回しかダウンロードできない」と作業日誌にある (`docs/work-logs/20250625T1200-porcupine-custom-wake-word.md`)。無料枠の条件は `scripts/porcupine/SETUP.md` に 2025-06 時点の記述がある
- `docs/ja/wake-word-low-power-recommendations.md` には訳の誤りがある (Syntiant NDP の消費電力が原文の「<140 µW」に対して「40µW未満」)。数値は英語版を正とする
- `scripts/wake-whisper-prototype/README.md` は日本語部分の文字コードが壊れている (元の stash の時点で同じ)。内容は同ディレクトリの `DESIGN.md` と `docs/work-logs/20250625T1906-wake-whisper-prototype.md` で追える

## 未解決・未確認

- 未確認: 現行の pvporcupine (3.0.5 より新しい版) でこの v3.0.0 の `.ppn` を読めるか
- 未確認: この `.ppn` が作成したアカウントの AccessKey 以外でも動くか、有効期限があるか
- 未確認: `.ppn` の再配布条件。同梱の `keywords/LICENSE.txt` は利用規約の URL を示すだけで、voice-agent の文書に再配布の記述は無い
- 未確認: 2026 年時点の無料枠・商用条件 (`../wake-vad/README.md` と同じ)
- 未解決: イベント駆動版 (`archive/event_driven_fixed.py`、`archive/event_driven_v2.py`) でウェイクワードを検出しない問題。原因候補 (感度・音声フォーマット・コールバック) を挙げたまま解決の記録が無い (`docs/work-logs/20250627T1707-wake-word-detection-issue.md`)。後継の `event_driven_v3.py` で解消したかは未確認
- 未解決: v3 で無音検出によるセッション終了が効かず、Whisper の結果にウェイクワードが混ざる (`docs/work-logs/20250627T1727-v3-improvements.md`)
- 未確認: `docs/work-logs/20250627T1015-wake-whisper-prototype-kansei.md` が使ったとする `src/utils/porcupine_helper.py` の `get_porcupine_resources()` は、voice-agent のどの版にも見つからなかった
