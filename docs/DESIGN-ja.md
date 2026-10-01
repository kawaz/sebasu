# Sebasu 設計

> [English](./DESIGN.md) | 日本語

## 目的と責務境界

各部屋の ESP32-S3 + XVF3800 サテライトから音声を Mac サーバへ送り、ウェイクワード検出 → VAD → STT → 話者識別 → LLM・ツール選択 → TTS → 再生へつなぐ。運用時はクラウドを使わない。モデル取得は初期設定時の操作と区別する。Linux 対応は [SB-Q2](./QUESTIONS.md) で裁定待ち。家電の実制御プロトコルは tools アダプタの責務であり、アシスタント本体には入れない。現在は設計と候補技術の PoC 段階で、複数部屋の本体は未実装。

## コンポーネントとストリーミング入出力

実装言語は未確定。以下は Python `typing.Protocol` による**疑似コード**であり、各アダプタの入力ストリーム型 → 出力ストリーム型と設定を表す。`AsyncIterator` を正とし、非ストリーミングエンジンはアダプタで 1 要素のストリームに包む。SpeechTranscriber の途中結果や TTS の分割音声を契約上表現できるようにするためである。音声チャンクにはサンプルレート、チャネル、時刻、部屋・セッション識別子、PCM を持たせ、認識結果には `partial` / `final` とターン識別子を持たせる。副作用のあるツールの呼び出しは確定結果のみを対象とする。

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

パイプライン側でターン・部屋を結び、キャンセル、割り込み、バックプレッシャーとターン終端を管理する。`SpeechSegment` は音声チャンクと境界イベント、`ConversationTurn` は確定済み認識結果と話者情報を持つ。別プロセスのアダプタ間では各言語固有の iterator ではなく意味上のイベントをシリアライズする。輸送候補はサテライト側 ESP-IDF `esp_webrtc` とサーバ側 Pion 系 WebRTC 実装。組み合わせの実機検証はまだない。

## 最初のアダプタ候補

| 入出力 | 候補と根拠 | 未検証の点 |
| --- | --- | --- |
| audio-in / audio-out | ESP32-S3 + XVF3800、`esp_webrtc` ↔ Pion 系 | 実機と双方向輸送 |
| wake | サーバ側 openWakeWord、サテライト側 microWakeWord または ESP-SR WakeNet | 合成英語 `hey_jarvis` で最大スコア 0.999191。日本語・実機・モデルの利用条件を要確認 |
| vad | Silero ONNX | 合成音声 8.475 秒の処理 34–63 ms。ライブ発話終端は未計測 |
| stt | Apple SpeechTranscriber、Mac の次点として mlx-whisper large-v3-turbo | 合成音声の final は音声終端後 0.043–0.126 秒。MLX のオフライン推論は 0.358–0.472 秒。Apple 側は Swift/macOS 必須 |
| speaker-id | SpeechBrain ECAPA | [話者識別 PoC](../poc/speaker-id/README.md)。実生活の録音と登録方針 |
| llm | llama.cpp 経由の Qwen3-4B GGUF | [LLM PoC](../poc/llm-local/README.md)。ツール実行の認可はモデル外で扱う |
| tts | 速度重視 Kokoro、音質重視 Irodori | [TTS PoC](../poc/tts-more/README.md) と [Irodori 比較](../poc/tts-irodori-voicevox/README.md)。WAV 完成時刻は初回音声出力時刻ではない |
| tools | ローカルアダプタ登録、統合 PoC は模擬実行 | 家電の実制御と天気接続は未実装 |

## 統合実測

モデルをロード済みの M1 Max Mac で、合成発話 4 件の STT `final` から Kokoro による応答音声完成まで **1.554–1.902 秒**、LLM 初回トークンまで 0.442–0.481 秒。Irodori に替えた 1 件は音声完成まで 3.750 秒。模擬ツールと `--no-play` を利用し、ウェイクワード、話者判定、サテライト輸送、音声入力から `final` まで、実際の再生開始は含まない。生活環境での体感速度の予測値ではない。[測定の手順と各件の記録](../poc/e2e/README.md)。

## 関連文書

- [QUESTIONS.md](./QUESTIONS.md) — 実装言語、Linux 対応、ファームウェアの裁定。
- [STRUCTURE.md](./STRUCTURE.md) — リポジトリ構造。
- [decisions/INDEX.md](./decisions/INDEX.md) — 設計判断一覧。
- [調査](./research/) — エンジンとシステム構成。
