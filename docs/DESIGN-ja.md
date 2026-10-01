# Sebasu 設計

> [English](./DESIGN.md) | 日本語

## 目的と責務境界

各部屋の ESP32-S3 + XVF3800 サテライトから音声を Mac サーバへ送り、ウェイクワード検出 → VAD → STT → 話者識別 → LLM・ツール選択 → TTS → 再生へつなぐ。運用時はクラウドを使わない。モデル取得は初期設定時の操作と区別する。Linux 対応は [SB-Q2](./QUESTIONS.md) で裁定待ち。家電の実制御プロトコルは tools アダプタの責務であり、アシスタント本体には入れない。現在は設計と候補技術の PoC 段階で、複数部屋の本体は未実装。

## コンポーネントとストリーミング入出力

実装言語は未確定。以下は Python `typing.Protocol` による**疑似コード**であり、各アダプタの入力ストリーム型 → 出力ストリーム型と設定を表す。`AsyncIterator` を正とし、非ストリーミングエンジンはアダプタで 1 要素のストリームに包む。SpeechTranscriber の途中結果や TTS の分割音声を契約上表現できるようにするためである。音声チャンクにはサンプルレート、`device_id`、`room`、`channel_layout`、時刻、任意の到来方向（`doa`）、ルーティング用のセッション識別子、PCM を持たせる。XVF3800 の 4 マイクからの多チャンネル音声を単一チャンネルへ強制変換せずに表現できる契約とする。認識結果には `partial` / `final` とターン識別子を持たせる。副作用のあるツールの呼び出しは確定結果のみを対象とする。

```python
from typing import AsyncIterator, Protocol

class AudioIn(Protocol):
    def capture(self, config: AudioInConfig) -> AsyncIterator[AudioChunk]: ...
class Wake(Protocol):
    def detect(self, audio: AsyncIterator[AudioChunk], config: WakeConfig) -> AsyncIterator[WakeEvent]: ...
class Vad(Protocol):
    def segment(self, audio: AsyncIterator[AudioChunk], config: VadConfig) -> AsyncIterator[SpeechSegment]: ...
class Stt(Protocol):
    def transcribe(self, speech: AsyncIterator[SpeechSegment], config: SttConfig) -> AsyncIterator[TranscriptUpdate]: ...
class SpeakerId(Protocol):
    def identify(self, speech: AsyncIterator[SpeechSegment], config: SpeakerConfig) -> AsyncIterator[SpeakerMatch]: ...
class Llm(Protocol):
    def respond(self, turns: AsyncIterator[ConversationTurn], config: LlmConfig) -> AsyncIterator[ResponseDelta]: ...
class Tts(Protocol):
    def synthesize(self, text: AsyncIterator[ResponseDelta], config: TtsConfig) -> AsyncIterator[AudioChunk]: ...
class AudioOut(Protocol):
    def play(self, audio: AsyncIterator[AudioChunk], config: AudioOutConfig) -> AsyncIterator[PlaybackEvent]: ...
class Tools(Protocol):
    def invoke(self, calls: AsyncIterator[ToolCall], config: ToolsConfig) -> AsyncIterator[ToolResult]: ...
```

パイプライン側でキャンセル、割り込み、バックプレッシャーとターン終端を管理する。`SpeechSegment` は音声チャンクと境界イベント、`ConversationTurn` は確定済み認識結果と話者情報を持つ。別プロセスのアダプタ間では各言語固有の iterator ではなく意味上のイベントをシリアライズする。音声輸送の候補は下表で比較する。サテライト実機でのエンドツーエンド実測はまだない。

## 複数デバイスのルーティング

`AudioChunk` は `device_id`、`room`、`channel_layout`、任意の到来方向 `doa` を保つ。XVF3800 の 4 マイクの音声を単一チャンネルへ強制変換しない。一方、STT や TTS などのエンジン IF は各々 1 ストリームを扱う。セッションは**ルーティング単位**であり、必ずしも 1 発話ではない。

- `assistant_turn`: 通常のアシスタント応答を選択した部屋へ送る。
- `broadcast`: 発信元の部屋を除く対象 audio-out すべてへ音声を配信する。LLM からも tools アダプタ `broadcast(text, exclude_room)` として要求できる。認可と配信先の決定を LLM に委ねない。
- `call`: 2 部屋の audio-in と audio-out をサーバ経由で接続する。WebRTC を使う場合は両部屋の音声 track を中継する。通話中も音声入力を tee して wake と STT に渡し、アシスタントを利用できるようにする。

独立した **Router** が同時に複数のデバイスで検出された同一発話を時刻・認識文の近似・音量・利用可能な DoA で重複判定し、応答先を 1 部屋選ぶ。broadcast の fan-out と call の配線も Router の責務とし、ルーティングポリシーとデバイスの group は設定で定める。これらは設計上の契約であり、実装・測定済みの機能ではない。実機では 4 マイクをミックスして 1ch で STT に渡すか各チャンネルを処理するか、DoA が話者識別・部屋選択に役立つか、call 中の再生音のマイクへの回り込みを調べる。

### エコーとハウリング

**デバイス内エコー**（自分の再生音を自分のマイクが拾う）は XVF3800 のハードウェア AEC が担う。再生音のリファレンスを XVF3800 に戻す配線が基板設計の前提であり、配線なしで AEC が効くとは扱わない。実機での効果は未測定。

**デバイス間エコー**（A の再生音を B のマイクが拾う）は A 側の AEC で消せない。複数台を同じ机に並べる試験では生じ、設置後も隣室間で起こりうる。Router は各デバイスへの再生内容を把握し、B の認識文が現在 A で再生中の文に近ければ自己再生として破棄する。再生中は同じ group に属する他デバイスの wake 感度を下げるか一時的に mute する。`call` では遅延した音声ループを検出し、片側の音量を絞る。文の近似閾値とループ検出は実機検証を要し、group 外のアシスタントまで無断で無効化しない。

設定上の **device group** は同じ音響空間を共有するデバイスの集合である。group 内では 1 台が再生中は他が聞かない。設置後は部屋を group とし、机上試験では全台を 1 group にまとめる。この制御は各デバイスの AEC 用再生リファレンスを置き換えるものではない。

## 設定で切り替えるアダプタ一覧

各 IF のアダプタは設定で選択する。PoC で動作した候補は速度や精度で序列を付けず、すべて差し替え対象に含める。**本体側のアダプタ実装と設定切替はまだ存在しない**。表の「PoC 動作」は「製品アダプタ実装済み」を意味しない。未実行・障害のある候補も理由を添えて未対応と記録する。数値は特記なければ M1 Max と合成音声による実測で、測定条件と利用条件の詳細は各 PoC を参照。モデルの初期取得と運用時のクラウド接続は区別する。

### 音声入出力・輸送

| アダプタ | 実測・状態 | 動作環境 | 制約・ライセンス |
| --- | --- | --- | --- |
| ESP32-S3 + XVF3800、`esp_webrtc` ↔ Pion WebRTC | 未対応: 実機の双方向疎通は未測定 | ESP32-S3 ↔ Mac/Linux、Go endpoint | Opus、I2S、AEC と部屋ルーティングの実機検証が必要 |
| `esp_webrtc` ↔ aiortc | 未対応: 調査のみ | ESP32-S3 ↔ Mac/Linux、Python endpoint | WebRTC 相互接続と遅延が未検証 |
| `esp_webrtc` ↔ str0m / webrtc-rs | 未対応: 調査のみ | ESP32-S3 ↔ Mac/Linux、Rust endpoint | WebRTC 相互接続と遅延が未検証 |
| WebSocket PCM / Wyoming | 未対応: 比較対象としての調査のみ | ESP32 ↔ Mac/Linux | プロトコルとセキュリティ設計が必要。Wyoming の素の TCP 輸送には認証・暗号化がない |
| Mac マイク / `afplay` | 無発話マイク入力とファイル再生経路を PoC で確認。実発話と実際の可聴再生は未確認 | macOS 26 | マイク権限が必要。Mac ローカルの音声入出力はサテライト輸送の代替ではない |

[輸送の調査](./research/2026-09-30-stt-trends.md)・[統合 PoC](../poc/e2e/README.md)

### ウェイクワード検出

| アダプタ | 実測・状態 | 動作環境 | 制約・ライセンス |
| --- | --- | --- | --- |
| openWakeWord | 合成英語 `hey_jarvis` を検出、最大スコア 0.999191 | macOS Apple Silicon、ONNX | 日本語独自モデルは未学習。コード Apache-2.0、配布モデル CC BY-NC-SA 4.0 |
| Porcupine | 今回は未対応: 過去に日本語モデルと既製語で CPU 2.4% / 32.5 MB の記録があるが、この PoC では推論未実行 | 既存 macOS 資産。ESP32-S3 対応未確認 | アカウント・AccessKey、商用条件を要確認。Mac 用モデルは ESP32 へ流用不可 |
| microWakeWord | 未対応: 実機・モデルの試験なし | ESP32-S3、ESPHome | 日本語モデルを自前学習する必要。コード Apache-2.0 |
| ESP-SR WakeNet | 未対応: 実機・モデルの試験なし | ESP32-S3 | 独自ワードは Espressif 経由。日本語対応・モデル利用条件は未確認 |

[ウェイクワード PoC](../poc/wake-vad/README.md)

### 発話区間検出

| アダプタ | 実測・状態 | 動作環境 | 制約・ライセンス |
| --- | --- | --- | --- |
| Silero ONNX | 合成 8.475 秒の処理 34–63 ms | Mac、ONNX Runtime | オフライン境界の測定でライブの終端イベント遅延ではない。モデルの利用条件を要確認 |
| WebRTC VAD | 1.0–1.3 ms。ノイズ下で最初の発話が分裂し冒頭で誤検出 | Mac、Python `webrtcvad` | アプリ側で hangover を追加。試験したパッケージには `setuptools<81` が必要 |
| sherpa-onnx Silero VAD | 36.5–37.1 ms。ノイズ下の終端は参照より後ろ | Mac、sherpa-onnx | ライブの終端遅延は未測定。配布モデルの条件を要確認 |

[VAD PoC](../poc/wake-vad/README.md)

### 音声認識

| アダプタ | 実測・状態 | 動作環境 | 制約・ライセンス |
| --- | --- | --- | --- |
| Apple SpeechTranscriber | 発話中の partial を確認。合成音声の final は音声終了後 0.043–0.126 秒 | macOS 26.5、Swift / Speech framework | Apple/macOS 専用。実際の生活音声は未評価 |
| mlx-whisper large-v3-turbo | 3 音声の推論 0.358–0.472 秒。試験した API は final のみ | Apple Silicon / MLX | モデルの利用条件を要確認 |
| faster-whisper large-v3-turbo int8 | 2.547–4.132 秒。final のみ | Mac CPU。Linux の CPU 実装にも関連 | GPU との資源・速度条件は異なる。モデル条件を要確認 |
| pywhispercpp kotoba-whisper-v2.0 q5_0 | 0.459–0.512 秒。final のみ | Mac Metal | 長い音声の末尾文を欠落。モデル条件を要確認 |
| sherpa-onnx ReazonSpeech offline zipformer | 0.083–0.199 秒。final のみ | Mac CPU / ONNX | 長い音声の冒頭を欠落。ストリーミング認識器には読み込めない |
| sherpa-onnx 多言語 streaming zipformer | 0.205–0.854 秒。partial を確認 | Mac CPU / ONNX | 試験した日本語の認識精度は低かった。ReazonSpeech とは別モデル |

[SpeechTranscriber PoC](../poc/speech-transcriber/README.md)・[STT 比較](../poc/stt-local/README.md)

### 話者識別

| アダプタ | 実測・状態 | 動作環境 | 制約・ライセンス |
| --- | --- | --- | --- |
| SpeechBrain ECAPA-TDNN | 合成 3 話者の先頭 1 秒で 18/18、埋め込み中央値 0.020 秒 | Mac CPU、Python 3.11 | 実際の人の声と登録運用は未評価。コード・モデル Apache-2.0 |
| WeSpeaker ResNet34 / CAM++ | 未対応: `s3prl` が削除済みの `torchaudio.set_audio_backend` を呼び、import 失敗 | 試験時の Mac Python 環境 | ソース Apache-2.0。依存を修復してからモデル評価が必要 |
| 3D-Speaker CAM++ | 未対応: checkpoint と API の試験なし | 環境未確認 | ソース Apache-2.0。モデル利用条件を要確認 |
| pyannote embedding | 未対応: gated checkpoint の承認を取得していない | 環境未確認 | コード MIT。モデルの条件は model card に従う |
| NVIDIA NeMo TitaNet | 未対応: 依存・モデル未導入 | macOS 対応未確認 | コード Apache-2.0。モデルの条件は別に確認 |

[話者識別 PoC](../poc/speaker-id/README.md)

### 言語モデル

| アダプタ | 実測・状態 | 動作環境 | 制約・ライセンス |
| --- | --- | --- | --- |
| Qwen3-4B Q4_K_M / llama.cpp | 24/30、初回トークン中央値 0.06 秒、全体 0.43 秒 | M1 Max Metal | Apache-2.0。全 Qwen 構成で部屋未指定時に不正確な補完があった |
| Qwen3-8B Q4_K_M / llama.cpp | 24/30、0.09 / 0.67 秒 | M1 Max Metal | Apache-2.0。同じ部屋指定検証が必要 |
| Qwen3-4B 4bit / mlx-lm | 24/30、0.55 / 0.86 秒 | Apple Silicon / MLX | Apache-2.0。同じ部屋指定検証が必要 |
| Qwen3-8B 4bit / mlx-lm | 21/30、1.45 / 2.25 秒 | Apple Silicon / MLX | Apache-2.0。同じ部屋指定検証が必要 |
| Gemma 3 4B 4bit / mlx-lm | PoC 実行は成功したが 0/30、JSON 破損 27/30 | Apple Silicon / MLX | Gemma Terms of Use。試験した無制約 prompt は実運用に不向き |
| Gemma 3 4B Q4_K_M / llama.cpp | PoC 実行は成功したが 0/30、JSON 破損 27/30 | M1 Max Metal | Gemma Terms of Use。同じ prompt の制約あり |
| Ollama / LM Studio / ELYZA / Swallow | 未対応: 未導入・未測定 | 未確認 | 実行系とモデルごとに条件・挙動が異なる |

30 ケースの採点はテキストからのツール選択で、ランタイム固有の function calling ではない。モデル出力を家電操作の認可に直接使用しない。[LLM PoC](../poc/llm-local/README.md)

### 音声合成

| アダプタ | 実測・状態 | 動作環境 | 制約・ライセンス |
| --- | --- | --- | --- |
| Kokoro-82M `jf_alpha` | 短文・中文・長文で 0.301 / 0.537 / 1.505 秒 | M1 Max CPU | モデル Apache-2.0。3 入力はいずれも 1 chunk で、文中の逐次 PCM は未検証 |
| Irodori-TTS v4.1 Small | 常駐時 3.223 / 3.313 / 6.611 秒 | M1 Max MPS | モデル・実装の個別条件を別途確認。音声の decode 完了時間で、初回音声ではない |
| VOICEVOX | 新規起動した 0.25.1 では完成 WAV が 0.803 / 1.606 / 3.416 秒 | M1 Max macOS、常駐サーバ | エンジン LGPL-3.0、話者ごとの利用規約。稼働中の別インスタンスでは測定値が大きく異なった |
| Style-Bert-VITS2 JP-Extra | 0.573 / 1.038 / 2.065 秒 | M1 Max CPU | 実装 AGPL-3.0、試験した声モデル CC-BY-SA-4.0 |
| macOS `say -v Kyoko` | CLI 起動・ファイル出力込み 1.124 / 1.102 / 1.248 秒 | macOS | Apple 同梱ソフトウェアの条件。Linux では利用不可 |
| pyopenjtalk | 0.032 / 0.090 / 0.217 秒 | M1 Max CPU | コード BSD-3-Clause。辞書・音声の個別ライセンスを要確認 |
| Fish Speech S2 Pro | 未対応: checkpoint / runtime 未取得・未実行 | Mac MPS 推論経路未確認 | Fish Audio Research License。商用条件の確認が必要 |
| Fun-CosyVoice3-0.5B-2512 | 未対応: Torch の import は確認、音声合成は未試験 | Mac Python 3.10、全体の動作環境は未確認 | Apache-2.0。依存と checkpoint のセットアップ、ストリーミング要検証 |

数値は完成音声または decode までで**最初に聴こえる時刻ではない**。条件の異なる測定を速度順位と解釈しない。[追加 TTS PoC](../poc/tts-more/README.md)・[Irodori と VOICEVOX の比較](../poc/tts-irodori-voicevox/README.md)

### ツール

| アダプタ | 実測・状態 | 動作環境 | 制約・ライセンス |
| --- | --- | --- | --- |
| 模擬 `light.set`、`aircon.set`、`timer.set`、`weather.get`、`answer`、`ask` | 統合 PoC でテキストから選択。家電・天気は模擬実行 | Mac、ローカル LLM パイプライン | 家電固有の制御プロトコル、外部データ、認可・副作用の方針は未実装。天気データを外部へ問い合わせるならオフライン運用とは両立しない |

## 統合実測

モデルをロード済みの M1 Max Mac で、合成発話 4 件の STT `final` から Kokoro による応答音声完成まで **1.554–1.902 秒**、LLM 初回トークンまで 0.442–0.481 秒。Irodori に替えた 1 件は音声完成まで 3.750 秒。模擬ツールと `--no-play` を利用し、ウェイクワード、話者判定、サテライト輸送、音声入力から `final` まで、実際の再生開始は含まない。生活環境での体感速度の予測値ではない。[測定の手順と各件の記録](../poc/e2e/README.md)。

## 関連文書

- [QUESTIONS.md](./QUESTIONS.md) — 実装言語、Linux 対応、ファームウェアの裁定。
- [STRUCTURE.md](./STRUCTURE.md) — リポジトリ構造。
- [decisions/INDEX.md](./decisions/INDEX.md) — 設計判断一覧。
- [調査](./research/) — エンジンとシステム構成。
