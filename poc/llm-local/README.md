# ローカル LLM・日本語音声アシスタント PoC

Apple M1 Max 64GB（macOS 26）で、日本語の音声起こし相当の入力から家電操作を選ぶ評価。実家電への接続、音声認識、音声合成は含まない。モデルの出力を JSON として解釈するテキスト上の模擬 tool calling であり、ランタイム固有の function calling API ではない。家電へ接続する前に引数検証・部屋の正規化・不明時の確認が必要。

## セットアップと実行

```sh
uv venv .venv
uv pip install --python .venv/bin/python mlx-lm huggingface-hub
uv pip install --python .venv/bin/python llama-cpp-python --config-settings cmake.args='-DGGML_METAL=on'
uvx --from huggingface-hub hf download mlx-community/Qwen3-4B-4bit --local-dir models/qwen3-4b-mlx
.venv/bin/python bench.py --runtime mlx --model models/qwen3-4b-mlx --repeat 3 --output results/qwen3-4b-mlx.jsonl
```

モデル取得・実行は `llm-local/` ディレクトリで行う。`--runtime llama` では `--model` に GGUF ファイルのパスを渡す。`--repeat` の既定は 3。各試行の生レスポンス、妥当性、正否、TTFT、全体時間は `results/*.jsonl` に保存する。依存ライブラリのバージョンはこの PoC では固定していない。

## モデル

| モデル | ランタイム | 量子化・サイズ | ライセンス | 状態 |
|---|---|---|---|---|
| [mlx-community/Qwen3-4B-4bit](https://huggingface.co/mlx-community/Qwen3-4B-4bit) | mlx-lm | 4bit、約 2.2 GB | Apache-2.0 | 測定済み |
| [mlx-community/gemma-3-4b-it-4bit](https://huggingface.co/mlx-community/gemma-3-4b-it-4bit) | mlx-lm | 4bit、約 3.3 GB | Gemma Terms of Use | 測定済み |
| [mlx-community/Qwen3-8B-4bit](https://huggingface.co/mlx-community/Qwen3-8B-4bit) | mlx-lm | 4bit、約 4.3 GB | Apache-2.0 | 測定済み |
| [bartowski/Qwen_Qwen3-4B-GGUF](https://huggingface.co/bartowski/Qwen_Qwen3-4B-GGUF) | llama.cpp Metal | Q4_K_M、約 2.4 GB | Apache-2.0 | 測定済み |
| [bartowski/Qwen_Qwen3-8B-GGUF](https://huggingface.co/bartowski/Qwen_Qwen3-8B-GGUF) | llama.cpp Metal | Q4_K_M、約 4.7 GB | Apache-2.0 | 測定済み |
| [unsloth/gemma-3-4b-it-GGUF](https://huggingface.co/unsloth/gemma-3-4b-it-GGUF) | llama.cpp Metal | Q4_K_M、約 2.4 GB | Gemma Terms of Use | 測定済み |

`llama-cpp-python` の GPU offload 対応は当該 M1 Max 実機で `True` と確認済み。Ollama と LM Studio はインストールされていない。ELYZA / Swallow 系は今回は未測定。

## 条件・採点

`bench.py` に同一の system prompt と 5 種のツール定義（`light.set`、`aircon.set`、`timer.set`、`weather.get`、`answer`）および 10 発話を固定。モデルごとに 3 回、temperature 0、最大 180 token。正答は JSON 構文、ツールの種類・回数、主要引数、曖昧な部屋の確認を検査。TTFT は最初の生成 token（llama.cpp 側は最初の非空 content）まで、全体時間は生成終了まで。モデルロードと初期化は計測対象外、初回生成にかかるウォームアップは計測対象。自然さは自動採点していない。

| 入力 | Qwen4 MLX | Qwen8 MLX | Gemma4 MLX | Qwen4 GGUF | Qwen8 GGUF | Gemma4 GGUF |
|---|---:|---:|---:|---:|---:|---:|
| リビングの電気消して | 3 | 3 | 0 | 3 | 3 | 0 |
| 寝室のエアコン 26 度で冷房 | 3 | 3 | 0 | 3 | 3 | 0 |
| 10 分後にお茶って教えて | 3 | 3 | 0 | 3 | 3 | 0 |
| 明日の天気は | 3 | 3 | 0 | 3 | 3 | 0 |
| おはよう | 3 | 3 | 0 | 3 | 3 | 0 |
| 電気つけて、あと少し暗めで | 0 | 0 | 0 | 0 | 0 | 0 |
| エアコン止めて | 0 | 0 | 0 | 0 | 0 | 0 |
| 今何時 | 3 | 3 | 0 | 3 | 3 | 0 |
| ありがとう | 3 | 3 | 0 | 3 | 3 | 0 |
| ダイニングとリビング両方消して | 3 | 0 | 0 | 3 | 3 | 0 |

| ランタイム・モデル | 正答 | JSON 破損 | TTFT 中央値 | 全体中央値 |
|---|---:|---:|---:|---:|
| mlx-lm Qwen3 4B 4bit | 24/30 | 0/30 | 0.55 秒 | 0.86 秒 |
| mlx-lm Qwen3 8B 4bit | 21/30 | 0/30 | 1.45 秒 | 2.25 秒 |
| mlx-lm Gemma 3 4B 4bit | 0/30 | 27/30 | 0.65 秒 | 1.03 秒 |
| llama.cpp Qwen3 4B Q4_K_M | 24/30 | 0/30 | 0.06 秒 | 0.43 秒 |
| llama.cpp Qwen3 8B Q4_K_M | 24/30 | 0/30 | 0.09 秒 | 0.67 秒 |
| llama.cpp Gemma 3 4B Q4_K_M | 0/30 | 27/30 | 0.09 秒 | 0.90 秒 |

**用途上の候補 2 件:** ① Qwen3 4B GGUF は最高速（TTFT 0.06 秒、24/30）で低遅延の基準モデル。② Qwen3 8B GGUF は 24/30 を維持しつつ、雑談応答の文面が 4B より自然なケースがあり、TTFT 0.09 秒で比較用の次候補。大きいモデルが一律に優れているとはいえず、同じ 8B の MLX は複数対象の指示を 3/3 回取り違えた。いずれも**家電直結は不可**: 部屋未指定の 2 ケースを全 Qwen 構成が 6/6 回誤操作し、`room="部屋"`、`room="全体"` 等を勝手に補完する。実システム側で部屋指定のホワイトリスト検証・未指定時の確認を必須とする。

Gemma 3 4B は JSON をコードフェンスで囲む、欠落した括弧や雑談への空配列などの誤出力が多く、今回の system prompt・無制約デコードでは候補にしない。Gemma は 27/30 が JSON 破損、残り 3 件も誤答。Qwen の `今何時` は `answer` を返すが、時刻を取得するツールを与えていないため正しい時刻は答えられず、文面も「現在の時刻を教えてください。」など不自然な回答がある。採点は tool と引数が主で、自然さの主観評価は参考情報にとどまる。

Qwen3 は tokenizer の `enable_thinking=False` で思考出力を抑制する。GGUF は同じチャットテンプレートの生成済み prompt を llama.cpp に入力し、8B GGUF のみ先頭に残る空の `<think>\n\n</think>` ブロックを除外した。思考抑制を省くと `<think>` から始まる出力が JSON として解釈できず、最大 180 token で JSON 自体が切れる（初回試行で観測し、同一条件に揃えて再測定）。同一 30 ケースでも測定は複数モデルを並行実行しているため、速度比較は共有 GPU 負荷の影響を受ける。結果はこの構成の観測値であり、厳密な孤立ベンチマークではない。なお GGUF の TTFT は prompt を組み立てる Python 時間を含まないが、MLX 側も prompt 構築は計測外。モデルロードは両方とも除外。
