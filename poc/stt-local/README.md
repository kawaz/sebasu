# ローカル日本語 STT 比較 PoC

Apple M1 Max / 64 GB、macOS 26（Darwin 25.5）、Python 3.11。音声を再生せず、全エンジンに同じ 16 kHz・mono・PCM16 音声を入力した。結果はこの環境・この三音声での測定値であり、実発話の精度を示すものではない。

## 再現

以下はこのディレクトリをカレントディレクトリとして実行する。`uv`、macOS 付属の `/usr/bin/say` と `afconvert` を使用する。初回のモデル取得にはネットワーク接続が必要。モデル本体は `models/` に置く（MLX および faster-whisper は Hugging Face の標準キャッシュ）。

```bash
mkdir -p models/kotoba models/reazonspeech models/streaming
/usr/bin/say -v Kyoko -o /tmp/say-ja.aiff '明日の天気を教えて。リビングの電気を消して。'
/usr/bin/say -v Kyoko -o /tmp/say-ja-long.aiff '明日の天気を教えて。リビングの電気を消して。今朝は少し肌寒いですね。週末は家族と公園に出かける予定です。おすすめの映画も教えてください。'
afconvert -f WAVE -d LEI16@16000 /tmp/say-ja.aiff /tmp/say-ja.wav
afconvert -f WAVE -d LEI16@16000 /tmp/say-ja-long.aiff /tmp/say-ja-long.wav
afconvert -f WAVE -d LEI16@16000 ../tts-irodori-voicevox/out/sample.wav /tmp/stt-ja-a.wav
uv run --python 3.11 --with huggingface-hub python -c 'from huggingface_hub import hf_hub_download, snapshot_download; hf_hub_download("kotoba-tech/kotoba-whisper-v2.0-ggml", "ggml-kotoba-whisper-v2.0-q5_0.bin", local_dir="models/kotoba"); snapshot_download("DeL-TaiseiOzaki/sherpa-onnx-zipformer-ja-reazonspeech-2024-08-01", local_dir="models/reazonspeech", allow_patterns=["*.onnx", "tokens.txt"]); snapshot_download("csukuangfj/sherpa-onnx-streaming-zipformer-ar_en_id_ja_ru_th_vi_zh-2025-02-10", local_dir="models/streaming", allow_patterns=["*.onnx", "tokens.txt", "bpe.model"])'
for engine in mlx faster cpp sherpa streaming; do
  /usr/bin/time -l uv run --python 3.11 --with mlx-whisper --with faster-whisper --with pywhispercpp --with sherpa-onnx --with numpy python bench.py "$engine" > "$engine.json" 2> "$engine.stderr"
done
```

`A` は既存の 4.640 秒の TTS サンプル（正解「こんにちは。これはイロドリ TTS のローカル動作テストです。」）。`B` は Kyoko による家電操作（3.472 秒）、`C` は Kyoko による質問・家電操作・雑談の長文（11.959 秒）。CER は Unicode NFKC と小文字化の後、空白・句読点を除く英数字・かな漢字について編集距離を計算した値。例えば A の「イロドリ」→「彩り」は音として妥当でも文字ベースでは誤りになる。各モデルのロード後に各音声を連続 3 回認識し、その所要時間の中央値を記録した。RTF は中央値秒数 ÷ 音声秒数。モデルロード時間には初回ダウンロードや Python 起動が含まれ得るため、冷スタート性能とは区別する。最大 RSS は別プロセスとして実行した `/usr/bin/time -l` の値で、Metal GPU の共有メモリ全量を示すとは限らない。複数候補を並行実行したため、CPU やメモリ帯域の競合があり、厳密な相対性能順位には使用しない。

## 実測結果

| エンジン／モデル | A CER / 秒 / RTF | B CER / 秒 / RTF | C CER / 秒 / RTF | ロード秒 | 最大 RSS GiB | partial |
|---|---:|---:|---:|---:|---:|---|
| mlx-whisper / large-v3-turbo | 0.1481 / 0.359 / 0.077 | 0 / 0.358 / 0.103 | 0 / 0.472 / 0.039 | 119.043 | 1.73 | 非対応 |
| faster-whisper / large-v3-turbo CPU int8 | 0.1481 / 2.547 / 0.549 | 0 / 2.657 / 0.765 | 0 / 4.132 / 0.346 | 420.927 | 2.26 | 非対応 |
| pywhispercpp / kotoba-whisper-v2.0 q5_0 Metal | 0.1481 / 0.459 / 0.099 | 0 / 0.459 / 0.132 | 0.2381 / 0.512 / 0.043 | 18.012 | 0.69 | 非対応（この API では完成セグメントのみ） |
| sherpa-onnx / ReazonSpeech offline zipformer | 0.3333 / 0.088 / 0.019 | 0.1500 / 0.083 / 0.024 | 0.7619 / 0.199 / 0.017 | 1.016 | 0.65 | **非対応** |
| sherpa-onnx / 多言語 streaming zipformer（ReazonSpeech ではない） | 0.4444 / 0.308 / 0.066 | 0.8500 / 0.205 / 0.059 | 0.3492 / 0.854 / 0.071 | 1.728 | 0.88 | **対応** |

表の元データは `mlx.json`、`faster.json`、`cpp.json`、`sherpa.json`、`streaming.json`。それぞれ `individual_runs_sec` に 3 回の生測定値、`partials` に音声投入時刻とその時点の出力を記録した。

## 実 transcript

| モデル | A | B | C |
|---|---|---|---|
| 正解 | こんにちは。これはイロドリ TTS のローカル動作テストです。 | 明日の天気を教えて。リビングの電気を消して。 | 明日の天気を教えて。リビングの電気を消して。今朝は少し肌寒いですね。週末は家族と公園に出かける予定です。おすすめの映画も教えてください。 |
| MLX | こんにちは。これは彩りTTSのローカル動作テストです。 | 明日の天気を教えて、リビングの電気を消して、 | 明日の天気を教えて、リビングの電気を消して、今朝は少し肌寒いですね。週末は家族と公園に出かける予定です。おすすめの映画も教えてください。 |
| faster | こんにちは。これは彩りTTSのローカル動作テストです。 | 明日の天気を教えて、リビングの電気を消して、 | 明日の天気を教えて、リビングの電気を消して、今朝は少し肌寒いですね。週末は家族と公園に出かける予定です。おすすめの映画も教えてください。 |
| kotoba | こんにちはこれは彩りTTSのローカル動作テストです | 明日の天気を教えてリビングの電気を消して | 明日の天気を教えて、リビングの電気を消して、今朝は少し肌寒いですね。週末は家族と公園に出かける予定です。 |
| ReazonSpeech | これは彩りTTSのローカル動作テストです | 天気を教えてリビングの電気を消して | おすすめの映画も教えてください |
| streaming 多言語 | こんにちは彩りTTSのローカル動作 | 地方の電気 | 地方の電気を消して今朝は少し肌寒いですね週末は家族とコウエンに出かける予定ですおすすめの映画も教え |

## 所見と制限

- この合成音声 3 本では MLX が B・C を完全に認識し、処理時間も短い。MLX は Apple Silicon / MLX が必要だが Python の単一 `transcribe` API で組み込みやすい。faster-whisper は CPU int8 で同じ transcript を出し、GPU 非依存だが約 2–4 秒を要した。どちらも逐次 partial を返さない。
- `pywhispercpp` の kotoba は低遅延だが C の最後の一文を欠落した。Python バインディングを介して Apple Metal を利用した。`new_segment_callback` はデコード済みセグメントを返すもので、ストリーム入力の途中で未確定テキストを返すものではない。
- ReazonSpeech 配布 zipformer は `sherpa_onnx.OfflineRecognizer.from_transducer` 対応の**オフライン**モデルだった。最初に `OnlineRecognizer.from_transducer` へ渡すと `online-zipformer2-transducer-model.cc:InitEncoder:116 'encoder_dims' does not exist in the metadata` で失敗した。offline API なら推論は成功するが、音声 C では冒頭を落とし、末尾の一文しか認識しなかった。冒頭の欠落がモデル・デコード設定・入力長のどれによるかは未特定。音声 C のような長い入力をそのまま使うべきではない。
- ReazonSpeech に streaming 用 ONNX が配布されていることは確認できなかった。このため partial の実証には**異なる**多言語対応 streaming zipformer を用いた。`streaming.json` の A では 0.8 秒投入時「こんにち」、1.2 秒で「こんにちは」、2.4 秒で「こんにちは彩」という逐次出力を確認。B の精度は著しく低い。ストリーミングで partial が出ることと、実利用で十分な日本語精度があることは別問題。
- どのモデルも本人の実発話や雑音下では検証していない。実用候補の選定には実マイク音声・話し方・周辺ノイズで追加測定が必要。
