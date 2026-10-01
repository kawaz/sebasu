# リポジトリ物理構造

```text
sebasu/main/
  README.md / README-ja.md  # 利用者向け概要
  LICENSE                   # MIT License
  justfile                  # lint と push の入口
  docs/
    DESIGN.md / DESIGN-ja.md # 構成とストリーミング契約
    QUESTIONS.md            # 裁定待ち
    STRUCTURE.md            # この文書
    decisions/INDEX.md      # Decision Records 一覧
    research/               # 音声技術と構成の調査
  poc/                      # エンジンと統合の実測用コード・記録
    speech-transcriber/     # Apple STT
    stt-local/              # STT 候補比較
    wake-vad/               # ウェイクワードと VAD
    speaker-id/             # 話者識別
    llm-local/              # ローカル LLM
    tts-more/               # TTS 候補比較
    tts-irodori-voicevox/   # Irodori と VOICEVOX 比較
    e2e/                    # 統合 PoC
```

サテライトのファームウェア、サーバ本体、実行時モデルと生成音声は含めません。
