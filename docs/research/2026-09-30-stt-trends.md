# 自作スマートスピーカーのローカル音声処理調査（2026-09-30）

## 構想への所見

各部屋の ESP32-S3 + XVF3800 で wake word と双方向音声、Mac / Linux サーバで STT → 自作 pipeline → LLM → TTS を行い、クラウドには送らない。輸送の第一候補は **LAN 内 WebRTC の双方向 PeerConnection（DTLS-SRTP / Opus）**。Espressif の ESP32-S3 OpenAI Realtime demo は Opus encode/decode と AEC の実例だが、相手を自前サーバへ置換する部分は実装・検証が必要。まず Mac では **Apple SpeechTranscriber の `ja-JP` 対応を実機で照会**し、対応すれば partial を評価、次に Whisper large-v3 / kotoba-whisper / ReazonSpeech を同じ家庭内録音で比較する。Linux GPU は SimulStreaming + Whisper large-v3 が partial の有力候補。XVF3800 の 48 kHz 2ch I2S 入力・再生中 AEC・日本語 wake word・短い発話の話者判定が難所。モデル処理速度と wake から初音までの実測レイテンシは混同しない。

## 1. ローカル STT：モデルと逐次出力

「逐次」は**発話中の音声を増分で受け、partial を返すこと**であり、完成ファイルの転記結果を SSE 分割で返すことではない。精度の数値は評価コーパスと条件を必ず併記する。

| 候補 | 日本語・精度 | 発話中 partial | Apple Silicon / Linux GPU / CPU | 速度・一次資料 |
|---|---|---|---|---|
| **Apple SpeechAnalyzer / SpeechTranscriber** | `SpeechTranscriber.supportedLocales` に `ja-JP` が存在するか**実機未確認**。Whisper との同条件精度ベンチ未確認 | `.volatileResults` は後続結果で同じ時間範囲を置換し、`isFinal` で確定。`AssetInventory` がモデルを取得 | macOS 26 の Apple 対応ハードウェアのみ。Linux なし。CLI/非 GUI のマイク権限運用は未確認 | Apple は低遅延を述べるがミリ秒値なし。話者 ID は提供を確認できず。旧 `SFSpeechRecognizer` とは異なる新しい on-device module。[WWDC25](https://developer.apple.com/videos/play/wwdc2025/277/)、[SpeechTranscriber](https://developer.apple.com/documentation/speech/speechtranscriber) |
| Whisper large-v3 / large-v3-turbo | 日本語対応。モデル間の家庭内音声の精度は未計測 | 本体は offline。SimulStreaming で増分推論 | whisper.cpp: Metal / CUDA / Vulkan / CPU、mlx-whisper: Apple GPU、faster-whisper: CUDA / CPU | whisper.cpp の `stream` は窓再処理の簡易例で、真の incremental decoder ではない。[Whisper](https://github.com/openai/whisper)、[turbo](https://huggingface.co/openai/whisper-large-v3-turbo)、[whisper.cpp](https://github.com/ggml-org/whisper.cpp)、[mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) |
| **kotoba-whisper-v2.0** | 日本語特化。ReazonSpeech test CER 11.6 対 large-v3 14.9（モデルカード内の同条件比較） | モデル単体は offline。SimulStreaming との適合は未確認 | faster-whisper / whisper.cpp 派生が公開。対応 backend の GPU / CPU | 同カードに large-v3 比 6.3 倍高速との記述。ただし発話レイテンシではない。[モデルカード](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0) |
| **ReazonSpeech k2 / NeMo / ESPnet** | 日本語コーパス由来。各々159M / 619M / 120M パラメータ | Transducer 系だが各公開 checkpoint のライブ partial API・確定ポリシーは未確認 | sherpa-onnx / NeMo / ESPnet。モデルごとの Mac GPU と Linux GPU は要検証 | 小型 k2 を実測する価値あり。[公式](https://github.com/reazon-research/ReazonSpeech) |
| faster-whisper / Distil-Whisper | 前者は推論 runtime で日本語精度は checkpoint 次第。Distil checkpoint の言語対応は個別確認 | faster-whisper の segment generator は**ファイル処理の遅延評価**でライブではない | CUDA / CPU。Metal は whisper.cpp / MLX を選ぶ | 最大 4 倍速はオフライン throughput ベンチ。[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[Distil-Whisper](https://github.com/huggingface/distil-whisper) |
| NVIDIA Parakeet v3 / Canary | **Parakeet v3 は欧州 25 言語で日本語なし**。Canary は checkpoint 単位で確認 | Parakeet v3 の streaming 例は 2 秒 chunk + 2 秒右文脈 | NeMo は主に NVIDIA GPU。Mac 実用経路未確認 | 日本語の主候補にしない。[Parakeet v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)、[Canary](https://huggingface.co/nvidia/canary-1b-v2) |
| Moonshine / Kyutai STT | Moonshine の日本語 streaming checkpoint は未確認。公開 Kyutai 1B は英仏、2.6B は英語で日本語なし | 両者 streaming を実装 | Moonshine: Mac/Linux/CPU; Kyutai: PyTorch GPU、1B MLX | Kyutai 公称モデル遅延 0.5 秒 / 2.5 秒は日本語に転用不可。[Moonshine](https://github.com/usefulsensors/moonshine)、[Kyutai 1B](https://huggingface.co/kyutai/stt-1b-en_fr) |
| クラウド STT（比較対象のみ） | OpenAI / Google / Deepgram / AssemblyAI / ElevenLabs Scribe の日本語・partial はサービス別 | ライブ音声 API と完成ファイルの stream は区別 | **ローカル完結条件に合わないため採用候補外** | [OpenAI](https://developers.openai.com/api/docs/guides/speech-to-text)、[Google](https://cloud.google.com/speech-to-text/docs/streaming-recognize)、[Deepgram](https://developers.deepgram.com/docs/live-streaming-audio) |

### 発話中 partial と endpoint

| 方式 | 確定と遅延 | 一次資料 |
|---|---|---|
| **SimulStreaming + large-v3** | AlignAtt で prefix を逐次確定。Whisper の日本語に対応。GPU 10 GB 以上推奨、CPU リアルタイムは厳しい。旧版比約 5 倍高速という記載は E2E 実測値ではない | [SimulStreaming](https://github.com/ufal/SimulStreaming) |
| Whisper-Streaming + faster-whisper | 連続 2 推論の一致 prefix を確定。旧論文の平均 3.3 秒は評価条件依存で、作者は SimulStreaming を推奨 | [Whisper-Streaming](https://github.com/ufal/whisper_streaming) |
| Silero VAD + kotoba / Reazon 完成発話 | speech onset / silence で終端。発話途中の partial は出ないが比較基準線になる | [Silero VAD](https://github.com/snakers4/silero-vad) |

VAD の pre-roll / 無音閾値 / 最大発話長は家庭内録音で調整し、partial を家電制御の確定指示に直結させない。Apple の partial と Whisper の確定 prefix は意味が違うので、確定 transcript までの時間を同一条件で比較する。`SpeechTranscriber` のロケール・モデル容量・権限・CLI 起動は実機未検証。

## 2. 自作 pipeline に輸入できる部品

| 出所 | 単独で取り出すもの | 依存・未確認点 / 一次資料 |
|---|---|---|
| **ESPHome** | ESP32 Wi-Fi、OTA、I2S microphone / speaker、`micro_wake_word`、external component の C++ 拡張をファーム土台に使う | `voice_assistant` は Home Assistant pipeline に結び付くため、**自作 WebRTC external component** は mic/speaker コンポーネントの C++ API と同期・DMA 競合を実装検証する必要がある。ESPHome の microWakeWord は独自モデル JSON/TFLite を受け付ける。ESPHome が esp_peer を component としてビルドできるか未確認。[ESPHome external components](https://esphome.io/components/external_components/)、[voice_assistant](https://esphome.io/components/voice_assistant/)、[micro_wake_word](https://esphome.io/components/micro_wake_word/) |
| Home Assistant Assist / Wyoming | HA の WebSocket pipeline event 定義、Wyoming の `audio-start/chunk/stop` と TTS streaming event を設計参考として採取 | HA 本体へ乗る必要はない。Wyoming は JSONL + PCM TCP で認証・暗号化がなく、WebRTC endpoint の代替にはしない。[HA pipeline](https://developers.home-assistant.io/docs/voice/pipelines/)、[Wyoming](https://github.com/OHF-Voice/wyoming) |
| Willow / Rhasspy / OpenVoiceOS / Pipecat | 端末 firmware・会話 skill・stage 境界・VAD の設計参考 | XVF3800 + XIAO、各部品の単独導入に必要なライセンスと依存は個別確認。統合フレームワーク全体への移行候補ではない。[Willow](https://github.com/toverainc/willow)、[Rhasspy](https://github.com/rhasspy/rhasspy)、[OVOS](https://github.com/OpenVoiceOS/ovos-core)、[Pipecat](https://github.com/pipecat-ai/pipecat) |
| ReSpeaker XVF3800 + XIAO ESP32-S3 | DSP 前処理・I2S 入出力、TLV320AIC3104 codec、3.5 mm / スピーカー端子 | ESP32 用 I2S firmware が必要。HA 用 48 kHz 2ch firmware は ch0 ASR / ch1 wake word。ESPHome は 16 kHz 16-bit mono 入力を求めるため ch 選択・resampling・AEC reference・同時再生を実機確認。[Seeed XVF3800](https://wiki.seeedstudio.com/respeaker_xvf3800_introduction/) |

日本語 wake word は [microWakeWord 学習](https://github.com/kahrendt/microWakeWord) の合成陽性 / 家庭内陰性データと real-world ambient 評価を試す。学習 repo は初回 notebook のモデルが実用にならない可能性と tuning の必要性を明記。[openWakeWord](https://github.com/dscripka/openWakeWord) の公開学習フローは英語中心で、ESP32 向け microWakeWord へ変換できる保証はない。過去の openWakeWord / Porcupine 比較を繰り返さず、ESP32-S3 上の誤起動/時間・取りこぼしと日本語データ生成を検証する。

## 3. WebRTC 音声輸送：LAN 内 1 本の PeerConnection

**目標経路:** XVF3800 I2S → ESP32-S3 DSP/AEC → Opus encoder → RTP/DTLS-SRTP → Mac/Linux の WebRTC peer → PCM → VAD/STT。一方で TTS PCM → Opus → **同一 PeerConnection の返り音声 track** → ESP32 Opus decoder → I2S speaker。送受信共に 1 接続で表現できる設計だが、XVF3800 ボードでの双方向実装・AEC reference 入力は未確認。音声はローカル LAN のみに流す。

| 検討軸 | 観測した実例・採用判断 / 一次資料 |
|---|---|
| Espressif `esp-webrtc-solution` | `esp_webrtc` は peer / capture / render をまとめ、内部の `esp_peer` が PeerConnection を担当。`peer_demo` は ESP32-S3 設定ありだが**偽音声のみ**で実音声疎通の根拠にはならない。`doorbell_demo` は ESP32-S3 設定とブラウザとの双方向音声を記載。[総覧](https://github.com/espressif/esp-webrtc-solution)、[peer_demo](https://github.com/espressif/esp-webrtc-solution/tree/main/solutions/peer_demo)、[doorbell_demo](https://github.com/espressif/esp-webrtc-solution/tree/main/solutions/doorbell_demo) |
| 双方向 Opus / AEC の実例 | `openai_demo` は ESP32-S3 Korvo-2 をデフォルト対象とし、`esp_audio_codec` の Opus encode/decode と AEC、双方向 voice を記載。**音声実装の参考**だがデモの API はクラウドなのでその接続先は採用しない。[openai_demo](https://github.com/espressif/esp-webrtc-solution/tree/main/solutions/openai_demo) |
| LAN シグナリング / ICE | 家庭内では host candidate のみ・STUN/TURN なしの構成を目指す。OpenAI demo は STUN/TURN を使わず SDP を HTTP POST で交換する実例だが、相手サーバが ICE-Lite か・host candidate のみで通るかは別途検証。LAN でも ICE / DTLS-SRTP の互換実装は必要。HTTP 1 往復で offer/answer を交換する WHIP 型を自作する案。HTTP の再ネゴシエーションと ICE の詳細は未確認。[openai_demo](https://github.com/espressif/esp-webrtc-solution/tree/main/solutions/openai_demo)、[WHIP RFC 9725](https://www.rfc-editor.org/rfc/rfc9725.html) |
| CPU・PSRAM・遅延 | ESP32-S3 + XVF3800 + Opus encode/decode + DTLS + AEC 同時動作の**PSRAM 要件・ピーク RAM・DTLS ハンドシェイク・first audio latency の一次資料実測値は未確認**。demo の `i` で load を観測し、ヒープ最小値、RTT と P50/P95 を自前測定する | [Espressif demo](https://github.com/espressif/esp-webrtc-solution/tree/main/solutions/openai_demo) |
| `libpeer` 系 | Espressif `esp_peer` とは別実装・API。CPU/メモリ優位を一次資料の同条件数値で確認できず、互換性/保守性を比較する予備候補に留める | [libpeer](https://github.com/sepfy/libpeer)、[esp_peer](https://github.com/espressif/esp-webrtc-solution) |
| 他経路との関係 | ESPHome native API → HA は動作比較の基準線、Wyoming TCP / 独自 WebSocket PCM は WebRTC が動かない場合の切り分け用。素の RTP/Opus は選択肢に含めない（DTLS-SRTP 込み）。WebSocket が必ず低遅延とは主張できない | [ESPHome](https://esphome.io/components/voice_assistant/)、[Wyoming](https://github.com/OHF-Voice/wyoming) |

サーバ側実装は以下から選び、自作 pipeline に接続する。`ICE-Lite` と双方向 audio track、Opus codec、HTTP offer/answer の適合は候補ごとに実機検証する。

| 候補 | 用途と制約 / 一次資料 |
|---|---|
| **Pion WebRTC (Go)** | Go の PeerConnection を自作サーバへ直接組み込む候補。ICE-Lite の API と Opus track を確認する。[Pion](https://github.com/pion/webrtc) |
| str0m / webrtc-rs (Rust) | Rust の peer 実装候補。str0m は Sans-I/O で自前 event loop が必要、webrtc-rs は async runtime を伴う。[str0m](https://github.com/algesten/str0m)、[webrtc-rs](https://github.com/webrtc-rs/webrtc) |
| aiortc (Python) | Python の VAD/STT/TTS に近い試験用 peer。実時間音声の GIL/CPU と Opus 依存は検証する。[aiortc](https://github.com/aiortc/aiortc) |
| LiveKit self-host | ローカルで運用可能な SFU。1 端末対 1 自作サーバなら SFU の追加運用は正当化しにくい。[LiveKit](https://github.com/livekit/livekit) |
| 時雨堂 momo / webrtc-build | momo は libwebrtc ベースの非ブラウザ**クライアント**参考実装。webrtc-build は Mac / Linux の libwebrtc ビルド入手経路でありサーバではない。ライセンスと配布条件は repo で確認する。[momo](https://github.com/shiguredo/momo)、[shiguredo-webrtc-build](https://github.com/shiguredo/shiguredo-webrtc-build) |
| 時雨堂 sora-cpp-sdk / sora-python-sdk | Sora との接続 SDK で、単体で一般 WebRTC server を立てる実装ではない。商用 Sora 本体なしに音声 peer の設計・ビルド例を参考にできる範囲を確認する。[sora-cpp-sdk](https://github.com/shiguredo/sora-cpp-sdk)、[sora-python-sdk](https://github.com/shiguredo/sora-python-sdk) |

## 4. サーバ → ESP32 の TTS 再生

| 方法 | 結果と制約 / 一次資料 |
|---|---|
| **同一 WebRTC PeerConnection の Opus 音声 track** | サーバで文単位 TTS PCM を Opus 化し送信、ESP32 で decode → I2S。ESP32-S3 の双方向 Opus/AEC は Espressif demo に実例があるが、XVF3800 の playback reference と割り込み/バージインは要測定。[openai_demo](https://github.com/espressif/esp-webrtc-solution/tree/main/solutions/openai_demo) |
| ESPHome `speaker` / `media_player` | 土台比較用。`voice_assistant` は二者排他で、前者に TTS stream hook、後者に TTS URL。HTTP chunked が再生開始前にどれだけ buffer するかは実装・実機依存。[voice_assistant](https://esphome.io/components/voice_assistant/)、[speaker media_player](https://esphome.io/components/media_player/speaker/) |
| Wyoming streaming TTS | `synthesize-start/chunk/stop` → PCM `audio-start/chunk/stop` の stage 間プロトコルをサーバ内部で参考にできる。端末輸送は WebRTC を優先。[Wyoming](https://github.com/OHF-Voice/wyoming) |

**E2E 計測点:** wake 判定 → 送信開始 → 初回 partial → 発話終端 → final STT → LLM 初回 token → TTS 初回 PCM → ESP32 初音。first audio と全量生成時間を分離する。

## 5. 実機比較候補（カテゴリ内は推奨順）

列の「逐次」は発話中の partial、「環境」は確認できた実行先であり、未記載は対応の保証ではない。LLM・TTS 等では「逐次」を音声 / text の逐次生成に読み替える。**以下は候補表であり、個々の精度・レイテンシは実機未測定。**

### STT モデル・ランタイム

| 名前 | 種別 | 日本語 | 逐次 | 環境 | 一次資料 | 試す価値 |
|---|---|---|---|---|---|---|
| Apple SpeechTranscriber | OS API | `ja-JP` 実機照会要 | volatile partial | Apple Silicon/macOS 26 | [WWDC25](https://developer.apple.com/videos/play/wwdc2025/277/) | GPU 設定なしの macOS 基準線 |
| SimulStreaming + Whisper large-v3 | アプリ+モデル | ○ | ○ | Linux GPU / Mac GPU は要検証 | [repo](https://github.com/ufal/SimulStreaming) | 日本語 partial 第一候補 |
| kotoba-whisper-v2.0 + whisper.cpp | モデル+ランタイム | ○ | 窓再処理 | Apple Silicon / Linux GPU / CPU | [model](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0) | CER と処理時間の比較 |
| ReazonSpeech k2 + sherpa-onnx | モデル+ランタイム | ○ | 要検証 | CPU / GPU はモデル別確認 | [repo](https://github.com/reazon-research/ReazonSpeech) | 小型日本語推論の候補 |
| large-v3-turbo + mlx-whisper / faster-whisper | モデル+ランタイム | ○ | 窓再処理 | Apple Silicon / Linux GPU / CPU | [model](https://huggingface.co/openai/whisper-large-v3-turbo) | 汎用 checkpoint 基準線 |

### VAD / エンドポイント検出

| 名前 | 種別 | 日本語 | 逐次 | 環境 | 一次資料 | 試す価値 |
|---|---|---|---|---|---|---|
| Silero VAD | ライブラリ/モデル | 言語非依存 | ○ | CPU / Apple Silicon / Linux GPU | [repo](https://github.com/snakers4/silero-vad) | 先頭の基準線 |
| WebRTC VAD | ライブラリ | 言語非依存 | ○ | CPU | [py-webrtcvad](https://github.com/wiseman/py-webrtcvad) | 軽量な対照条件 |
| sherpa-onnx VAD + endpoint | ライブラリ | 言語非依存 | ○ | CPU / backend 別 | [repo](https://github.com/k2-fsa/sherpa-onnx) | STT と近い API で統合 |

### ウェイクワード（ESP32 / サーバ）

| 名前 | 種別 | 日本語 | 逐次 | 環境 | 一次資料 | 試す価値 |
|---|---|---|---|---|---|---|
| microWakeWord + 自作モデル | モデル/ファーム部品 | 学習要 | ○ | ESP32-S3 | [training](https://github.com/kahrendt/microWakeWord)、[ESPHome](https://esphome.io/components/micro_wake_word/) | エッジ検出第一候補 |
| openWakeWord + 自作モデル | ライブラリ/モデル | 公式学習は英語中心、日本語未検証 | ○ | サーバ CPU | [repo](https://github.com/dscripka/openWakeWord) | 日本語 wake 学習の比較用 |
| ESPHome `micro_wake_word` | ファーム component | モデル依存 | ○ | ESP32-S3 | [docs](https://esphome.io/components/micro_wake_word/) | 単体輸入できるか検証 |

### ローカル LLM 推論

| 名前 | 種別 | 日本語 | 逐次 | 環境 | 一次資料 | 試す価値 |
|---|---|---|---|---|---|---|
| llama.cpp + Qwen3 Instruct | ランタイム+モデル | ○（モデル仕様） | token stream、tool use はモデル依存 | Apple Silicon / Linux GPU / CPU | [llama.cpp](https://github.com/ggml-org/llama.cpp)、[Qwen3](https://huggingface.co/Qwen/Qwen3-8B) | JSON/tool-call の schema 順守率を実測 |
| Ollama + Qwen3 | アプリ+モデル | ○ | stream、tool calling | Apple Silicon / Linux GPU / CPU | [Ollama tools](https://docs.ollama.com/capabilities/tool-calling) | 家電操作 PoC の最短経路 |
| mlx-lm + Qwen3 | ライブラリ+モデル | ○ | token stream、tool schema は要検証 | Apple Silicon | [mlx-lm](https://github.com/ml-explore/mlx-lm) | Mac ネイティブ性能比較 |
| LM Studio + Qwen3 | アプリ+モデル | ○ | stream、tool calling はモデル/API 依存 | Apple Silicon / Linux GPU | [LM Studio](https://lmstudio.ai/docs/app) | GUI で評価、常駐依存を比較 |

### ローカル日本語 TTS

| 名前 | 種別 | 日本語 | 逐次 | 環境 | 一次資料 | 試す価値 |
|---|---|---|---|---|---|---|
| Irodori-TTS | モデル/アプリ | ○ | 要検証 | Apple Silicon / Linux GPU は実装別 | [公式](https://github.com/Aratako/Irodori-TTS) | 既知の主候補、初音時間を実測 |
| VOICEVOX | アプリ | ○ | 文単位 HTTP。真の音声逐次は要検証 | Mac / Linux CPU・GPU は配布別 | [engine](https://github.com/VOICEVOX/voicevox_engine) | 安定した日本語基準線 |
| Style-Bert-VITS2 | モデル/アプリ | ○ | 文単位、partial 未確認 | GPU / CPU は実装別 | [repo](https://github.com/litagin02/Style-Bert-VITS2) | 話者/表情を重視する場合 |
| Kokoro | モデル | 日本語 voice の提供を個別確認 | 文単位、partial 未確認 | CPU / GPU backend 別 | [model](https://huggingface.co/hexgrad/Kokoro-82M) | 小型軽量候補 |
| Fish-Speech / CosyVoice | モデル/アプリ | 日本語対応は checkpoint ごとに要確認 | 実装別 | Linux GPU 主、Mac 要検証 | [Fish-Speech](https://github.com/fishaudio/fish-speech)、[CosyVoice](https://github.com/FunAudioLLM/CosyVoice) | first-chunk latency とライセンスを確認 |

### 話者分離・話者判定（家庭内登録話者）

diarization は「話者が何人・どの区間」、identification は「登録された誰か」。単一 wake 発話は後者の speaker embedding + enrollment + 類似度閾値を試す。**1〜3 秒の短い発話は誤判定の懸念が大きく、一次資料の同条件精度は未確認。**「未知の人」を無理に家族へ割り当てない閾値を設定する。

| 名前 | 種別 | 日本語 | 逐次 | 環境 | 一次資料 | 試す価値 |
|---|---|---|---|---|---|---|
| SpeechBrain ECAPA-TDNN | 話者埋め込みモデル | 言語横断は実測要 | 短区間 final | CPU / Linux GPU、Apple MPS 要検証 | [SpeechBrain](https://github.com/speechbrain/speechbrain)、[ECAPA](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb) | 登録家族の照合を先に試す |
| pyannote.audio | diarization ライブラリ/モデル | 言語横断は実測要 | segment final | CPU / Linux GPU、Mac MPS 要検証 | [repo](https://github.com/pyannote/pyannote-audio) | 複数人同時発話の評価。checkpoint は利用規約同意・HF token を求める場合あり、コードとモデルのライセンスを別確認 |
| WeSpeaker / 3D-Speaker CAM++ | 埋め込みモデル | 日本語評価要 | 短区間 final | CPU / Linux GPU、Mac 要検証 | [WeSpeaker](https://github.com/wenet-e2e/wespeaker)、[3D-Speaker](https://github.com/modelscope/3D-Speaker) | ECAPA と 1〜3 秒照合率を比較 |
| NVIDIA NeMo Sortformer | diarization モデル | 日本語評価要 | モデル別 | Linux GPU、Mac 要検証 | [NeMo](https://github.com/NVIDIA/NeMo) | 重なり音声の話者分離候補 |
| whisperX | STT と diarization の統合アプリ | Whisper による日本語 | オフライン segment | Linux GPU、Mac 要検証 | [repo](https://github.com/m-bain/whisperX) | 一連の発話ログから話者を評価 |

### 輸入する統合部品（全体には乗らない）

| 名前 | 種別 | 日本語 | 逐次 | 環境 | 一次資料 | 試す価値 |
|---|---|---|---|---|---|---|
| ESPHome | ファーム土台/OTA | wake モデル依存 | 音声入出力可 | ESP32-S3 | [repo](https://github.com/esphome/esphome) | external component に WebRTC を載せられるか |
| Wyoming | 音声 event 仕様 | 音声モデル依存 | PCM chunk | Mac / Linux / CPU | [repo](https://github.com/OHF-Voice/wyoming) | stage 間 event のみ再利用 |
| Home Assistant Assist | pipeline 参考実装 | エンジン依存 | 入力 chunk / TTS event | Mac/Linux サーバ | [docs](https://developers.home-assistant.io/docs/voice/pipelines/) | endpoint/event 設計を採取 |
| Willow / Rhasspy / OVOS | firmware/skills 参考 | 実装別 | 実装別 | ESP32 / Mac/Linux 別 | [Willow](https://github.com/toverainc/willow)、[Rhasspy](https://github.com/rhasspy/rhasspy)、[OVOS](https://github.com/OpenVoiceOS/ovos-core) | firmware / skill 部品の依存を評価 |
| Pipecat | pipeline 参考ライブラリ | モデル依存 | ○ | サーバ CPU/GPU | [repo](https://github.com/pipecat-ai/pipecat) | turn-taking / event 分割を参照 |

### 音声輸送

| 名前 | 種別 | 日本語 | 逐次 | 環境 | 一次資料 | 試す価値 |
|---|---|---|---|---|---|---|
| **esp_webrtc / esp_peer ↔ Pion** | ファーム+サーバライブラリ | 音声非依存 | 双方向 Opus RTP | ESP32-S3 / Mac / Linux | [Espressif](https://github.com/espressif/esp-webrtc-solution)、[Pion](https://github.com/pion/webrtc) | 第一候補、LAN で host ICE と双方向音声を試す |
| esp_webrtc ↔ aiortc | ファーム+Python ライブラリ | 音声非依存 | 双方向 | ESP32-S3 / Mac / Linux | [aiortc](https://github.com/aiortc/aiortc) | Python pipeline 接続 PoC |
| esp_webrtc ↔ str0m / webrtc-rs | ファーム+Rust ライブラリ | 音声非依存 | 双方向 | ESP32-S3 / Mac / Linux | [str0m](https://github.com/algesten/str0m)、[webrtc-rs](https://github.com/webrtc-rs/webrtc) | Rust サーバ構築時の候補 |
| WebSocket PCM / Wyoming | 比較用 protocol | 音声非依存 | PCM chunk | ESP32 / Mac / Linux | [ESP WebSocket](https://docs.espressif.com/projects/esp-protocols/esp_websocket_client/docs/latest/index.html)、[Wyoming](https://github.com/OHF-Voice/wyoming) | WebRTC 問題の切り分け基準線 |
