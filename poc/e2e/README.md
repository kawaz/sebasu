# Mac ローカル音声アシスタント統合 PoC

M1 Max / 64 GB、macOS 26。Apple SpeechTranscriber（別 Swift プロセス）→ Qwen3-4B GGUF / llama-cpp-python Metal → 模擬ツール → Kokoro `jf_alpha`（`--tts irodori` では Irodori MPS）→ `afplay`。LLM・TTS・Silero VAD を先にロードしてから認識を開始する。家電・天気の実 API には接続しない。ウェイクワードと話者判定は対象外。`--no-play` を指定したファイル検証ではスピーカーから音を出さない。

## 実行

```sh
cd poc/e2e
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python llama-cpp-python transformers torch silero-vad soundfile kokoro 'misaki[ja]' unidic-lite onnxruntime --config-settings cmake.args='-DGGML_METAL=on'
.venv/bin/python assistant.py --wav living.wav --no-play
.venv/bin/python assistant.py --wav hello.wav --no-play --tts irodori
.venv/bin/python assistant.py --mic
```

`--tts irodori` は既存 `../tts-irodori-voicevox/Irodori-TTS/.venv/bin/python` を起動する。別モデル用依存を e2e 環境に混在させず、`irodori_worker.py` 内でロードして複数リクエストに対し常駐する。音声認識は既存 `../speech-transcriber/transcribe` バイナリを利用する。Silero VAD はファイルの発話有無を確認する。マイクでは Swift の録音・認識側が現在 10 秒で終了するため、連続対話や VAD によるターン区切りは未実装。起動は 1 回で複数の `final` を受け取る間は順次処理するが、10 秒後には子プロセスの終了に伴い終わる。

マイク発話テストは PC の前で `--mic` を実行し、`micStarted=true` の後 10 秒以内に「リビングの電気を消して」と発話する。再生を有効にした状態で `final`、`MOCK light.set`、`RESPONSE`、`tts_done`、`play_start` を確認する。マイク権限がないと既存 Swift コードはダイアログを表示せず終了する。実発話・実再生の官能確認は未実施。

## ファイル入力の実測

`/usr/bin/say -v Kyoko -o <name>.aiff '<発話>'` → `/usr/bin/afconvert -f WAVE -d LEI16 <name>.aiff <name>.wav`。4 ケースとも `--no-play` を使用。各測定でモデルを新規ロードし、`ready` 後の SpeechTranscriber の最初の `final` を t=0 とした。以下の時刻は各段の**累積**時間（秒）で、モデルの初期ロードとマイク音声終了までの待機時間を含まない。`play_start` は `--no-play` のため計測していない。ファイルでは Apple SpeechTranscriber が入力を実時間の速度で送り、Silero が音声の有無を検出した後に認識結果を受け取る。

| Kyoko の入力 | STT final | LLM first token | LLM done | TTS done | 応答 |
| --- | --- | ---: | ---: | ---: | --- |
| リビングの電気を消して | リビングの電気を消して | 0.481 | 0.861 | 1.554 | リビングの電気を消しました。（`MOCK light.set {"room": "リビング", "on": false}`） |
| 明日の天気は | 明日の天気は | 0.471 | 0.683 | 1.589 | 天気情報にはまだ接続していません。（`MOCK weather.get {"when": "明日"}`） |
| おはよう | おはよう | 0.442 | 0.879 | 1.902 | おはようございます。何かお手伝いできますか？ |
| 電気つけて | 電気つけて。 | 0.470 | 0.824 | 1.617 | どの部屋の電気をつけてほしいですか？（`ask`。家電操作なし） |

Irodori 切替は「おはよう」で別途 `--no-play` 実測し、`llm_first_token=0.441`、`llm_done=0.876`、`tts_done=3.750` 秒、応答「おはようございます。何かお手伝いできますか？」を確認した。マイクは 5 秒経過後にプロセスが継続していることを確認したほか、`ready` → `microphoneAuthorization=3` → `micStarted=true` → 開始から 17.11 秒で正常終了（モデルロードを含む）を確認した。権限ダイアログは表示されなかった。

数値は他の実行中ワーカーと GPU・CPU を共有していた時点の観測値。`final` より前の STT 遅延、音声先頭から再生開始までの総レイテンシ、再生自体の時間は未測定。マイクでの実発話を試すまで、実生活の体感遅延を結論づけない。
