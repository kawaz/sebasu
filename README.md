# Sebasu

[日本語](./README-ja.md)

Sebasu is a local-first, self-hosted voice assistant for ESP32-S3 + XVF3800 satellites in each room and a Mac server. The intended pipeline is wake word → voice activity detection → speech-to-text → local language model and tools → text-to-speech → playback. It does not require a cloud service at runtime.

Every component has an explicit streaming input/output interface. Engine adapters can be replaced independently without coupling the assistant to any one wake-word detector, recognizer, model, synthesizer or transport. A Linux server is under consideration.

**Status:** Architecture stage. The included PoCs measure candidate engines and an integration path; the multi-room assistant and satellite firmware are not yet implemented.

- [Design and candidate engines](./docs/DESIGN.md)
- [Open decisions](./docs/QUESTIONS.md)
- [Research](./docs/research/)
- [Measured PoCs](./poc/)
- [Repository structure](./docs/STRUCTURE.md)

MIT licensed; see [LICENSE](./LICENSE).
