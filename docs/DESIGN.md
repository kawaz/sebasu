# Sebasu Design

> English | [日本語](./DESIGN-ja.md)

## Domain and boundaries

Sebasu is a local-first voice assistant with ESP32-S3 + XVF3800 satellites in each room and a Mac server. Audio travels from the satellite to the server, then passes through wake detection, VAD, STT, speaker identification, LLM/tool selection, TTS, and audio playback. No cloud service is required for operation; downloading model assets during setup is separate from runtime. The same component interfaces permit alternative engines and, subject to [SB-Q2](./QUESTIONS.md), a Linux server.

The assistant owns tool invocation and its adapter contract, but appliance-specific control protocols belong to tools adapters. Authentication, permission checks, and side-effect confirmation must occur at that boundary. The current stage is architecture and measured PoCs, not a working multi-room assistant.

## Streaming component interfaces

The signatures below are **Python `typing.Protocol` pseudocode**, not a commitment to Python as the implementation language. `AsyncIterator` is the canonical contract. An offline engine yields one result or audio chunk from its adapter; this keeps SpeechTranscriber partial transcripts and chunked TTS output expressible without changing the interface later. Configuration is explicit per adapter and describes model, thresholds, sample format, device and runtime policy as applicable. Audio chunks carry sample rate, channel layout, timestamp, room/session identity and PCM payload; transcript updates carry `partial`/`final` status and turn identity. A final update alone may authorize side-effecting tools.

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

The orchestration layer joins each stream by turn/session and routes the matching room's output; it handles cancellation, interruption, backpressure and end-of-turn decisions rather than hiding these inside individual engines. `SpeechSegment` contains audio chunks and boundary events, and `ConversationTurn` contains final transcript plus speaker context. Cross-process adapters serialize these semantic events, not language-specific iterators. The transport candidate is ESP-IDF `esp_webrtc` on the satellite with a Pion-family WebRTC endpoint on the server; this pairing is a research candidate, not a measured end-to-end implementation.

## Initial adapter candidates

| Interface | Candidate and evidence | Open constraint |
| --- | --- | --- |
| audio-in / audio-out | ESP32-S3 + XVF3800 satellite, WebRTC `esp_webrtc` ↔ Pion-family server | Hardware and full-duplex transport untested |
| wake | openWakeWord on server; ESP-SR WakeNet or microWakeWord on satellite | English `hey_jarvis` score 0.999191 on synthetic audio; Japanese custom word and ESP hardware untested; bundled model licensing must be checked |
| vad | Silero ONNX on server | Synthetic 8.475 s clip processed in 34–63 ms; endpoint notification in live audio unmeasured |
| stt | Apple SpeechTranscriber; mlx-whisper large-v3-turbo as next Mac candidate | SpeechTranscriber final 0.043–0.126 s after synthetic clip end; MLX 0.358–0.472 s offline inference for tested clips; Apple implementation requires Swift/macOS |
| speaker-id | SpeechBrain ECAPA | See [speaker-id PoC](../poc/speaker-id/README.md); household recordings and enrollment policy need validation |
| llm | Qwen3-4B GGUF via llama.cpp | See [local LLM PoC](../poc/llm-local/README.md); tool authorization belongs outside the model |
| tts | Kokoro for response speed; Irodori for voice quality | See [TTS PoCs](../poc/tts-more/README.md) and [Irodori comparison](../poc/tts-irodori-voicevox/README.md); full-file completion is not first audible sample |
| tools | Local adapter registry and simulated tool calls in integration PoC | Appliance protocols and real weather integrations are not implemented |

## Measured integration snapshot

On an M1 Max Mac with models preloaded, four synthetic utterances took **1.554–1.902 s from the first STT `final` event to completed Kokoro response audio**, with LLM first token at 0.442–0.481 s. One Irodori substitution took 3.750 s to completed response audio. The runs used mocked tools and `--no-play`: wake detection, speaker identity, real satellite transport, capture-to-final delay and playback start were not included. These values do not predict perceived household latency. [Raw procedure and per-utterance results](../poc/e2e/README.md).

## Open decisions and related documents

- [QUESTIONS.md](./QUESTIONS.md) — implementation language, Linux support, firmware foundation.
- [STRUCTURE.md](./STRUCTURE.md) — repository layout.
- [decisions/INDEX.md](./decisions/INDEX.md) — decision records.
- [Research](./research/) — engine and system survey.
