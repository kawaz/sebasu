# ローカル日本語 TTS 追加比較

Apple M1 Max / 64 GB / macOS Darwin 25.5、2026-09-30。自動再生なし。音質の主観評価は WAV を聞いていないため未評価。生成時間はモデル常駐状態で同一文を 3 回生成した中央値で、ファイル保存は含まない。RTF = 生成時間 ÷ 出力音声長。`say` だけは CLI 起動と AIFF 書き出しを含み、WAV 変換は含まない。異なる話速・音声長・測定境界のため、厳密に同条件の音質・速度順位にはならない。

## 再現手順

```sh
cd poc/tts-more
uv run --no-project --python 3.11 python bench.py say
uv run --no-project --python 3.11 --with pyopenjtalk --with soundfile python bench.py pyopenjtalk
uv run --no-project --python 3.11 --with kokoro --with 'misaki[ja]' --with unidic-lite --with soundfile python bench_kokoro.py
uv run --no-project --python 3.11 --with style-bert-vits2 --with 'numpy<2' --with soundfile --with huggingface_hub python bench_style.py
ls -la out/
```

`uv` の隔離環境ごとに辞書や Hugging Face モデルの初回取得が発生する。`bench_kokoro.py` は `misaki[ja]` が依存する `unidic` の辞書本体が未取得でも動くよう、`unidic-lite` の辞書を指定している。Style-Bert-VITS2 は公式ライブラリ・JP-Extra 対応の `litagin/style_bert_vits2_jvnv` の `jvnv-F1-jp` 音声モデル、BERT は `ku-nlp/deberta-v2-large-japanese-char-wwm`、CPU 推論。Hugging Face キャッシュへのモデル取得が完了している場合のロード時間を記録した。BERT 側を明示的に float32 にするのは実際の checkpoint が half 精度で読み込まれ、float32 の TTS モデルと dtype が一致しなかったため。

各文は既存の `../tts-irodori-voicevox/README.md` の比較節と同一。短文「はい、わかりました。」、中文「こんにちは。これはイロドリ TTS のローカル動作テストです。」、長文「今日は早めに仕事を切り上げ、近くの公園へ散歩に出かけました。夕暮れの空を眺めながら、明日の予定をゆっくり考えています。帰り道には温かい飲み物を買います。」。

## 比較

| 候補 | ロード・初期化 | 短文 生成秒 / 音声秒 / RTF | 中文 生成秒 / 音声秒 / RTF | 長文 生成秒 / 音声秒 / RTF | ストリーミング・分割出力 | ライセンス |
| --- | ---: | --- | --- | --- | --- | --- |
| VOICEVOX 健全時 | 未測定 | 0.54 / 未測定 / — | 1.23 / 未測定 / — | 2.94 / 未測定 / — | エンジンの合成 API は完成 WAV | エンジン LGPL-3.0、音声はキャラクター別規約 |
| Irodori-TTS MPS 常駐 | 未測定（既存 PoC に独立したロード計測なし） | 3.22 / 2.920 / 1.103 | 3.31 / 4.640 / 0.714 | 6.61 / 15.000 / 0.441 | 既存 PoC は完成 WAV | モデル・実装の個別規約を利用前に要確認 |
| Style-Bert-VITS2 JP-Extra CPU | 2.867 秒（Python import 除く、キャッシュ済み） | 0.573 / 1.718 / 0.333 | 1.038 / 4.087 / 0.254 | 2.065 / 12.794 / 0.161 | `infer()` は完成音声を返す。入力の改行分割は可能だが逐次音声出力 API は未確認 | 実装 AGPL-3.0、使用した音声モデル CC-BY-SA-4.0 |
| Kokoro-82M `jf_alpha` CPU | 1.169 秒（pipeline 初期化、import 除く）、モデル・初回推論 0.462 秒（キャッシュ済み） | 0.301 / 1.975 / 0.152 | 0.537 / 4.800 / 0.112 | 1.505 / 13.925 / 0.108 | `KPipeline` が文ごとの generator を返す。今回の 3 文はいずれも 1 chunk だったため、短文中の低遅延逐次 PCM は未検証 | モデル Apache-2.0 |
| macOS `say -v Kyoko` | 1.107 秒（別プロセスの試し書き） | 1.124 / 1.243 / 0.904 | 1.102 / 4.604 / 0.239 | 1.248 / 13.706 / 0.091 | CLI のファイル出力は完成音声。音声再生には OS API を別途使用 | macOS 同梱、Apple ソフトウェアライセンス |
| pyopenjtalk CPU | import 5.387 秒、辞書初回ダウンロード・初期化 55.065 秒 | 0.032 / 2.075 / 0.015 | 0.090 / 5.780 / 0.016 | 0.217 / 13.460 / 0.016 | `tts()` は完成音声。文分割で擬似逐次化可能 | pyopenjtalk BSD-3-Clause、辞書・音声データは別途ライセンス確認 |
| Fish Speech S2 Pro | 未測定 | — | — | — | 公式が SGLang streaming を案内 | Fish Audio Research License（商用条件は要確認） |
| Fun-CosyVoice3-0.5B-2512 | 未測定 | — | — | — | 公式 README が双方向 streaming 対応と明記 | Apache-2.0 |

VOICEVOX の 0.54 / 1.23 / 2.94 秒は既知の健全時ベースラインで、この環境で今回再計測していない。既存の Irodori 検証 README に記録された実測 VOICEVOX は版・常駐状態で数値が異なるため、この行を既存 README の実測だと誤認しないこと。Irodori の音声長・生成秒は既存 README の数値。Irodori のモデルロードの概算には初回 BERT 等の時間が混ざり得るため、独立したロード計測とは扱わない。

出力は `out/<candidate>-<short|mid|long>.wav` に保存される。Style-Bert-VITS2 は日本語発音と調整可能な話し方に強みがあり、モデル・大規模 BERT の取得、AGPL と声モデルの再頒布・表示義務の検討が組み込み上の注意点。Kokoro はパッケージだけで導入しやすくモデルの配布条件も緩いが、辞書の選択・G2P のアクセントおよび実際の読み上げ品質は聴取していない。pyopenjtalk は圧倒的に低遅延だが音色は従来型で、品質は未聴取。`say` は OS 依存で、呼び出すたび別プロセスを起動する条件で測った。

## 動作しなかった／今回測定しなかった候補

- Fish Speech: 公式の現行 README は S2 Pro で日本語を Tier 1 に挙げる一方、推奨 inference は SGLang-Omni / vLLM-Omni と NVIDIA H200 CUDA Graph による高速化。Mac MPS 向けの公式手順を確認できず、checkpoint サイズ・専用 runtime と認証条件を精査しないままモデルを取得して実行することは避けた。実行エラーは**未取得・未実行のため存在しない**。純 CPU 経路も未検証であり「Mac で不可能」とは断定しない。
- CosyVoice: 公式 README は日本語・streaming 対応、依存の `requirements.txt` は macOS に `onnxruntime==1.18.0` を指定。`uv run --no-project --python 3.10 --with 'torch==2.3.1' --with 'torchaudio==2.3.1' python -c 'import torch,torchaudio;print(torch.__version__)'` は `2.3.1` と出力し、Torch 自体は Mac で動く。しかし公式リポと checkpoint のセットアップから音声推論まで未実施で、動作可否と速度は未確定。失敗出力は存在しない。
- Kokoro を初めて `misaki[ja]` のみで起動した際、`RuntimeError: Failed initializing MeCab`、詳細は `param.cpp(69) [ifs] no such file or directory: .../unidic/dicdir/mecabrc`。`unidic-lite` を与えて解消した。
- Style-Bert-VITS2 の依存解決で NumPy 2 を選んだ際は `ValueError: numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88 from PyObject`。`numpy<2` で解消。その後、checkpoint 由来の half 精度で `RuntimeError: Input type (c10::Half) and bias type (float) should be the same` が出たが、スクリプトで BERT を float32 にして解消した。

参照: [Style-Bert-VITS2](https://github.com/litagin02/Style-Bert-VITS2)、[jvnv 音声モデル](https://huggingface.co/litagin/style_bert_vits2_jvnv)、[Kokoro](https://github.com/hexgrad/kokoro)、[Fish Speech](https://github.com/fishaudio/fish-speech)、[CosyVoice](https://github.com/FunAudioLLM/CosyVoice)。
