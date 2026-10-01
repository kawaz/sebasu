# Sebasu Design

> English | [日本語](./DESIGN-ja.md)

## Domain and boundaries

Sebasu is a local-first voice assistant with ESP32-S3 + XVF3800 satellites in each room and a Mac server. Audio travels from the satellite to the server, then passes through wake detection, VAD, STT, speaker identification, LLM/tool selection, TTS, and audio playback. No cloud service is required for operation; downloading model assets during setup is separate from runtime. The same component interfaces permit alternative engines and, subject to [SB-Q2](./QUESTIONS.md), a Linux server.

The assistant owns tool invocation and its adapter contract, but appliance-specific control protocols belong to tools adapters. Authentication, permission checks, and side-effect confirmation must occur at that boundary. The current stage is architecture and measured PoCs, not a working multi-room assistant.

Room telemetry (temperature, humidity, CO2, illuminance, passive BLE scanning for presence and lost-item hints) is a separate component, `telemetry`, with responsibilities distinct from the voice pipeline. It shares only the per-room ESP32 hardware and the transport to the server; it is orthogonal to the audio interfaces such as `AudioChunk`. Telemetry owns collection, time-series storage, and queries; the assistant reads it only through tools (for example, replying in the occupied room or naming where a lost item was last seen). Details are in [telemetry-sensor-platform](./issue/telemetry-sensor-platform.md).

## Streaming component interfaces

The signatures below are **Python `typing.Protocol` pseudocode**, not a commitment to Python as the implementation language. `AsyncIterator` is the canonical contract. An offline engine yields one result or audio chunk from its adapter; this keeps SpeechTranscriber partial transcripts and chunked TTS output expressible without changing the interface later. Configuration is explicit per adapter and describes model, thresholds, sample format, device and runtime policy as applicable. Audio chunks carry sample rate, `device_id`, `room`, `channel_layout`, timestamp, optional direction of arrival (`doa`), routing session identity and PCM payload. XVF3800 has four microphones; the contract preserves multichannel capture without assuming a mono mix. Transcript updates carry `partial`/`final` status and turn identity. A final update alone may authorize side-effecting tools.

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

The orchestration layer joins each stream by turn/session; it handles cancellation, interruption, backpressure and end-of-turn decisions rather than hiding these inside individual engines. `SpeechSegment` contains audio chunks and boundary events, and `ConversationTurn` contains final transcript plus speaker context. Cross-process adapters serialize these semantic events, not language-specific iterators. Transport adapters are compared below; none has been measured end to end on satellite hardware.

## Multi-device routing

`AudioChunk` preserves `device_id`, `room`, `channel_layout` and optional direction of arrival (`doa`). XVF3800 has four microphones; the input contract can preserve their channels instead of forcing a mono mix. STT, TTS and the other engine interfaces still process one stream at a time. A session is a **routing unit**, not necessarily one utterance:

- `assistant_turn`: Route one assistant interaction to the selected room.
- `broadcast`: Fan out speech to every eligible audio-out except the source room. The LLM can request this via a `broadcast(text, exclude_room)` tools adapter; authorization and destination policy remain outside the model.
- `call`: Connect two rooms' audio-in and audio-out through the server (relaying their WebRTC tracks when using WebRTC). Tee each input to wake detection and STT while connected so the assistant remains available during the call.

A separate **Router** owns simultaneous-device deduplication and destination selection, broadcast fan-out, and call wiring. To select one response room when multiple satellites hear an utterance, it compares timestamps, approximate transcripts, levels and available DoA; configuration defines its routing policies and device groups. These are design contracts, not implemented or measured behaviors. Hardware research must determine whether to mix the four microphone channels for STT or process channels separately, whether DoA helps speaker identification and room selection, and how call playback leaks into microphones.

### Echo and howling

**Intra-device echo**—a satellite hearing its own playback—is handled by XVF3800 hardware AEC. The board must feed the playback reference back to XVF3800; this is a board-design requirement, not an assumption that AEC works without wiring. Its effectiveness on the actual board remains unmeasured.

**Inter-device echo**—device B hearing device A's playback—cannot be removed by A's AEC. It occurs when satellites sit together on a test bench and may occur between adjacent rooms after installation. The Router knows each output stream: it discards B's transcript when sufficiently similar to A's currently playing text, reduces or temporarily mutes wake sensitivity for other devices in the same group during playback, and detects delayed audio loops in `call` mode so it can attenuate one side. Similarity thresholds and loop detection require real-device measurement; suppressing wake must not silently disable the assistant outside the configured group.

Configuration defines a **device group** as satellites sharing an acoustic space. Within a group, when one device plays, the others do not listen; deployment groups correspond to rooms, while a bench setup places every satellite in one group. This group policy complements—not replaces—the per-device playback reference for AEC.

## Configurable adapter inventory

Each interface selects an adapter by configuration. Every candidate that ran in a PoC remains eligible regardless of relative performance; **none of the production adapters or configuration switches are implemented yet**. “PoC ran” is not “adapter implemented.” Unrun or blocked candidates remain visible as unsupported so their integration can be revisited. Measurements below are from an M1 Max Mac with synthetic inputs unless stated otherwise; detailed methods and licensing caveats are in the linked PoCs. Setup-time model downloads do not imply cloud use at runtime.

### Audio input, output and transport

| Adapter | Measurement / status | Environment | Constraints and licensing |
| --- | --- | --- | --- |
| ESP32-S3 + XVF3800, `esp_webrtc` ↔ Pion WebRTC | Unsupported: no end-to-end hardware measurement | ESP32-S3 ↔ Mac/Linux, Go endpoint | Full-duplex Opus, I2S, AEC and room routing need hardware validation |
| `esp_webrtc` ↔ aiortc | Unsupported: research only | ESP32-S3 ↔ Mac/Linux, Python endpoint | WebRTC interoperation and latency untested |
| `esp_webrtc` ↔ str0m / webrtc-rs | Unsupported: research only | ESP32-S3 ↔ Mac/Linux, Rust endpoint | WebRTC interoperation and latency untested |
| WebSocket PCM / Wyoming | Unsupported: comparison route only | ESP32 ↔ Mac/Linux | Protocol and security require design; Wyoming's raw TCP transport provides no authentication or encryption |
| Mac microphone / `afplay` | PoC ran for silent microphone capture; playback code path exists but was not exercised in `--no-play` measurements; real speech and audible output were not assessed | macOS 26 | Microphone authorization required; Mac-local I/O is not a satellite transport |

[Transport survey](./research/2026-09-30-stt-trends.md) · [integration PoC](../poc/e2e/README.md)

### Wake detection

| Adapter | Measurement / status | Environment | Constraints and licensing |
| --- | --- | --- | --- |
| openWakeWord | PoC detected synthetic English `hey_jarvis`, peak score 0.999191 | macOS Apple Silicon, ONNX | Japanese custom model untrained; code Apache-2.0, bundled models CC BY-NC-SA 4.0 |
| Porcupine | Unsupported in this PoC: existing Japanese model and historical CPU 2.4% / 32.5 MB observation, but no inference run here | Existing macOS assets; ESP32-S3 support unconfirmed | Account/AccessKey and commercial terms need verification; macOS model cannot be reused on ESP32 |
| microWakeWord | Unsupported: no device/model test | ESP32-S3, ESPHome | Custom Japanese model requires training; code Apache-2.0 |
| ESP-SR WakeNet | Unsupported: no device/model test | ESP32-S3 | Custom word supplied through Espressif; Japanese availability and model licensing unconfirmed |

[Wake PoC](../poc/wake-vad/README.md)

### Voice activity detection

| Adapter | Measurement / status | Environment | Constraints and licensing |
| --- | --- | --- | --- |
| Silero ONNX | PoC ran: 8.475 s synthetic clip processed in 34–63 ms (clean/noise) | Mac, ONNX Runtime | Offline boundary measurement, not live endpoint latency; verify model license before distribution |
| WebRTC VAD | PoC ran: 1.0–1.3 ms; noisy first utterance split and initial false detection | Mac, Python `webrtcvad` | Extra hangover implemented by caller; `setuptools<81` required for tested package |
| sherpa-onnx Silero VAD | PoC ran: 36.5–37.1 ms; noisy endpoint boundaries trailed reference | Mac, sherpa-onnx | Streaming endpoint latency not measured; verify bundled model terms |

[VAD PoC](../poc/wake-vad/README.md)

### Speech recognition

| Adapter | Measurement / status | Environment | Constraints and licensing |
| --- | --- | --- | --- |
| Apple SpeechTranscriber | PoC ran: partials during speech; synthetic final 0.043–0.126 s after audio end | macOS 26.5, Swift / Speech framework | Apple/macOS-specific; live household speech not evaluated |
| mlx-whisper large-v3-turbo | PoC ran: three clips 0.358–0.472 s, offline final only | Apple Silicon / MLX | No partial results in tested API; check model terms |
| faster-whisper large-v3-turbo int8 | PoC ran: 2.547–4.132 s, offline final only | Mac CPU; CPU path also relevant to Linux | Resource/latency profile differs from GPU; check model terms |
| pywhispercpp kotoba-whisper-v2.0 q5_0 | PoC ran: 0.459–0.512 s, offline final only | Mac Metal | Long test omitted final sentence; check model terms |
| sherpa-onnx ReazonSpeech offline zipformer | PoC ran: 0.083–0.199 s, offline final only | Mac CPU / ONNX | Long test omitted beginning; cannot load in streaming recognizer; check model terms |
| sherpa-onnx multilingual streaming zipformer | PoC ran: 0.205–0.854 s and partial output | Mac CPU / ONNX | Japanese transcript accuracy poor on tested clips; distinct from ReazonSpeech model |

[SpeechTranscriber PoC](../poc/speech-transcriber/README.md) · [STT comparison](../poc/stt-local/README.md)

### Speaker identification

| Adapter | Measurement / status | Environment | Constraints and licensing |
| --- | --- | --- | --- |
| SpeechBrain ECAPA-TDNN | PoC ran: 18/18 synthetic speakers at 1 s; embedding median 0.020 s | Mac CPU, Python 3.11 | Human voices and enrollment not evaluated; code and model Apache-2.0 |
| WeSpeaker ResNet34 / CAM++ | Unsupported: import fails because `s3prl` calls removed `torchaudio.set_audio_backend` | Tested Mac Python environment | Source Apache-2.0; dependency repair needed before model evaluation |
| 3D-Speaker CAM++ | Unsupported: checkpoint and API not tested | Environment unverified | Source Apache-2.0; model conditions require verification |
| pyannote embedding | Unsupported: gated checkpoint approval not obtained | Environment unverified | Code MIT; checkpoint use subject to model card |
| NVIDIA NeMo TitaNet | Unsupported: dependencies and model not installed | macOS support unverified | Code Apache-2.0; model license separate |

[Speaker identification PoC](../poc/speaker-id/README.md)

### Language model

| Adapter | Measurement / status | Environment | Constraints and licensing |
| --- | --- | --- | --- |
| Qwen3-4B Q4_K_M via llama.cpp | PoC ran: 24/30, median first token 0.06 s, complete 0.43 s | M1 Max Metal | Apache-2.0; all Qwen variants mishandled unspecified rooms without external validation |
| Qwen3-8B Q4_K_M via llama.cpp | PoC ran: 24/30, 0.09 / 0.67 s | M1 Max Metal | Apache-2.0; same room validation requirement |
| Qwen3-4B 4bit via mlx-lm | PoC ran: 24/30, 0.55 / 0.86 s | Apple Silicon / MLX | Apache-2.0; same room validation requirement |
| Qwen3-8B 4bit via mlx-lm | PoC ran: 21/30, 1.45 / 2.25 s | Apple Silicon / MLX | Apache-2.0; same room validation requirement |
| Gemma 3 4B 4bit via mlx-lm | PoC ran, but 0/30 and 27/30 malformed JSON | Apple Silicon / MLX | Gemma Terms of Use; unsuitable for tested unconstrained prompt until integration improved |
| Gemma 3 4B Q4_K_M via llama.cpp | PoC ran, but 0/30 and 27/30 malformed JSON | M1 Max Metal | Gemma Terms of Use; same prompt limitation |
| Ollama / LM Studio / ELYZA / Swallow | Unsupported: not installed or measured | Unverified | Licensing and behavior depend on runtime/model |

The 30-case score tests text-to-tool selection, not native function calling. Model output must not directly authorize an appliance action. [LLM PoC](../poc/llm-local/README.md)

### Speech synthesis

| Adapter | Measurement / status | Environment | Constraints and licensing |
| --- | --- | --- | --- |
| Kokoro-82M `jf_alpha` | PoC ran: short/mid/long generation 0.301 / 0.537 / 1.505 s | M1 Max CPU | Model Apache-2.0; tested three inputs each yielded one chunk, not low-latency intra-sentence streaming |
| Irodori-TTS v4.1 Small | PoC ran: 3.223 / 3.313 / 6.611 s resident generation | M1 Max MPS | Model/implementation licenses require separate verification; output measured through decode, not first sample |
| VOICEVOX | PoC ran: newly started 0.25.1, short/mid/long full WAV 0.803 / 1.606 / 3.416 s; 0.25.2 and 0.26.0-preview.1 also measured | M1 Max macOS, resident server | Engine LGPL-3.0 and voice-specific terms; resident instance state strongly affected measurements |
| Style-Bert-VITS2 JP-Extra | PoC ran: 0.573 / 1.038 / 2.065 s | M1 Max CPU | Implementation AGPL-3.0, tested voice CC-BY-SA-4.0 |
| macOS `say -v Kyoko` | PoC ran: 1.124 / 1.102 / 1.248 s including CLI/file output | macOS | Bundled Apple software license; no Linux route |
| pyopenjtalk | PoC ran: 0.032 / 0.090 / 0.217 s | M1 Max CPU | Code BSD-3-Clause; dictionaries/voices require separate license check |
| Fish Speech S2 Pro | Unsupported: checkpoint/runtime not downloaded or executed | Mac MPS inference route unverified | Fish Audio Research License, commercial conditions require review |
| Fun-CosyVoice3-0.5B-2512 | Unsupported: Torch imports on Mac, synthesis not attempted | Mac Python 3.10, final runtime unverified | Apache-2.0; dependency/checkpoint setup and streaming need testing |

Measurements cover completed audio (or decode), **not first audible sample**, and are not a controlled speed ranking. [Additional TTS PoC](../poc/tts-more/README.md) · [Irodori and VOICEVOX comparison](../poc/tts-irodori-voicevox/README.md)

### Tools

| Adapter | Measurement / status | Environment | Constraints and licensing |
| --- | --- | --- | --- |
| Simulated `light.set`, `aircon.set`, `timer.set`, `weather.get`, `answer`, `ask` | PoC ran: text-selected calls, with mock appliance/weather execution in integration | Mac, local LLM pipeline | Appliance-specific protocols, external data, authorization and side-effect policy are not implemented; external weather sources would violate offline operation unless locally available |

## Measured integration snapshot

On an M1 Max Mac with models preloaded, four synthetic utterances took **1.554–1.902 s from the first STT `final` event to completed Kokoro response audio**, with LLM first token at 0.442–0.481 s. One Irodori substitution took 3.750 s to completed response audio. The runs used mocked tools and `--no-play`: wake detection, speaker identity, real satellite transport, capture-to-final delay and playback start were not included. These values do not predict perceived household latency. [Raw procedure and per-utterance results](../poc/e2e/README.md).

## Open decisions and related documents

- [QUESTIONS.md](./QUESTIONS.md) — implementation language, Linux support, firmware foundation.
- [STRUCTURE.md](./STRUCTURE.md) — repository layout.
- [decisions/INDEX.md](./decisions/INDEX.md) — decision records.
- [Research](./research/) — engine and system survey.
