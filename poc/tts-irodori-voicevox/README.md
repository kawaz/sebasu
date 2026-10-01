# Irodori-TTS ローカル動作検証

## セットアップ

Apple Silicon の macOS では公式 README の `cpu` extra が PyPI の PyTorch wheel にフォールバックし、MPS も使用できます。Python 3.11 は `uv` がインストール済みのものを指定します。

```sh
cd poc/tts-irodori-voicevox
# Irodori-TTS/ がなければ: git clone https://github.com/Aratako/Irodori-TTS Irodori-TTS
cd Irodori-TTS
uv sync --extra cpu --python 3.11
cd ..
/usr/bin/time -p sh synth.sh
/usr/bin/afinfo out/sample.wav
ls -la out/
```

`synth.sh` は公式の `infer.py` に `--no-ref` を渡すため、参照音声を必要としません。推論 device はデフォルトで MPS、失敗したときは `IRODORI_DEVICE=cpu /usr/bin/time -p sh synth.sh` でモデルと codec の両方を CPU に切り替えます。初回推論では Hugging Face から checkpoint と codec がダウンロードされます。

## 実測結果

| 実行環境 | device | 生成時間 | WAV の `afinfo` | 状態 |
| --- | --- | --- | --- | --- |
| Apple M1 Max / macOS Darwin 25.5 / 64GB | MPS (model + codec) | 初回 378.85 秒 (HF ダウンロード込み)、キャッシュ利用時 23.81 秒 (ロード後の decode まで 5.233 秒。初回キャッシュ利用時は 56.85 秒) | 48 kHz / 16 bit / mono / 4.64 秒 / 445,484 bytes | 正常終了。初回は HF ダウンロードの時間が大部分を占める |
| Apple M1 Max / macOS Darwin 25.5 / 64GB | CPU | 未測定 | 未測定 | MPS が正常終了したため未実施 |

検証対象の公式リポジトリは `89f9d8f`。`uv` と `git` は利用可能、Python 3.11.3 は uv の管理下に導入済みです。`python3.11` コマンドは PATH にありませんが、`uv sync --python 3.11` で選択できます。

## vsay (VOICEVOX) との速度比較

Apple M1 Max / macOS Darwin 25.5 / 64GB、2026-09-30。3 回の中央値。短文「はい、わかりました。」、中文「こんにちは。これはイロドリ TTS のローカル動作テストです。」、長文 (76 文字)「今日は早めに仕事を切り上げ、近くの公園へ散歩に出かけました。夕暮れの空を眺めながら、明日の予定をゆっくり考えています。帰り道には温かい飲み物を買います。」を使用しました。

| 文 | vsay direct WAV 完了 | vsay API WAV 受信完了 | Irodori 常駐 `total_to_decode` | 音声長 direct / API / Irodori |
| --- | ---: | ---: | ---: | --- |
| 短文 | 1.123 秒 | 2.533 秒 | 3.223 秒 | 1.792 / 1.355 / 2.920 秒 |
| 中文 | 6.081 秒 | 5.324 秒 | 3.313 秒 | 4.416 / 4.011 / 4.640 秒 |
| 長文 | 12.706 秒 | 12.916 秒 | 6.611 秒 | 11.029 / 10.635 / 15.000 秒 |

`vsay` は既に稼働中のローカル VOICEVOX engine (port 50021) を使用。direct は `uv run` によるプロセス起動から WAV 作成完了までを計測し、`afplay` だけをベンチマーク中に置換して音を鳴らしていません。API は FastAPI サーバーを常駐させ、`/generate` のリクエスト開始から WAV 全体の受信までを計測しています。既存 `vsay api` は `/speak` に `play: true` を固定で送信するため、再生しない `/generate` を直接使いました。API サーバーの依存パッケージは既存 `pyproject.toml` に未登録だったため、`uv run --with fastapi --with aiohttp --with aiofiles --with uvicorn python tts_api_server.py` で一時的に補いました。

Irodori は MPS (model + codec)、`Aratako/Irodori-TTS-v4.1-Small`、参照音声なし。`bench.py` でモデルを一度だけロードし、3 文を各 3 回連続生成した `total_to_decode` (モデルロード後から decode 完了、保存処理は含まない) です。別途、中文の `synth.sh` をキャッシュ利用状態で `hyperfine --runs 3 --warmup 0 --show-output` により起動から WAV 完了まで測定した結果は 13.166〜18.170 秒、中央値 約 14.387 秒、平均 15.241 秒 (標準偏差 2.609 秒)。各試行の `total_to_decode` は 3.278 / 2.849 / 3.808 秒でした。これは Irodori を毎回起動するときのモデルロード・初期化の影響を示します。長文は Irodori の予測音声長が 15 秒に到達しています。

**比較上の注意**: いずれもストリーミング再生の最初の PCM サンプルまでの実測ではなく、WAV 全体が生成・取得できた時間を再生開始可能時刻の代替として用いています。direct はプロセス起動とファイル保存、API は HTTP と転送、Irodori 常駐値はファイル保存を含まないため、表の列を同一条件の厳密な速度順位とは解釈できません。VOICEVOX の direct は冒頭無音 0.5 秒と先頭強調 3 モーラを設定し、API はその設定を持たないため、生成音声の長さも異なります。短文では常駐 VOICEVOX direct が速く、中文・長文では Irodori のモデル常駐時 decode 完了が短い一方、毎回起動する Irodori はロード時間が支配的です。

### VOICEVOX engine 版間の生成速度

同じ Apple M1 Max / macOS Darwin 25.5 / 64GB で、上記と同じ短文・中文・長文を話者 3（ずんだもん）で生成しました。各版を別ポートで常駐させ、`bench_voicevox.py` で各文のウォームアップ後に `/audio_query` の送信から `/synthesis` の WAV 全体の受信完了までを 3 回測り、中央値を記載します。`vsay_direct.py` と同じ話速 1.2、pauseLength 0.1、pauseLengthScale 0.3、冒頭無音 0.5 秒、先頭 3 モーラの強調を適用し、音声は再生していません。上の `vsay direct` 列とは異なり、Python プロセス起動と WAV ファイル保存は時間に含みません。

| 文 | 0.25.1 (port 50021) | 0.25.2 (port 50022) | 0.26.0-preview.1 (port 50023) |
| --- | ---: | ---: | ---: |
| 短文 | 1.387 秒 | 0.921 秒 | 0.752 秒 |
| 中文 | 5.929 秒 | 1.924 秒 | 1.589 秒 |
| 長文 | 12.702 秒 | 4.109 秒 | 4.133 秒 |

`GET /version` と `GET /core_versions` の実出力は次のとおりです。

| 起動版 | `/version` | `/core_versions` |
| --- | --- | --- |
| 0.25.1 | `"0.25.1"` | `["0.16.1"]` |
| 0.25.2 | `"0.25.2"` | `["0.16.1"]` |
| 0.26.0-preview.1 | `"0.26.0-preview.1"` | `["0.16.1"]` |

今回の macOS arm64 配布物はいずれも CORE 0.16.1 で、CORE 0.17 による速度差は検証できません。上表で旧版 0.25.1 が遅い点を切り分けるため、同じ公式 0.25.1 配布物を別途展開して port 50024 で新規起動し、同じ設定と手順で計測しました。

| 文 | 稼働中 0.25.1 (port 50021) | 新規起動 0.25.1 (port 50024) | 0.25.2 (port 50022) | preview (port 50023) |
| --- | ---: | ---: | ---: | ---: |
| 短文 | 1.387 秒 | 0.803 秒 | 0.921 秒 | 0.752 秒 |
| 中文 | 5.929 秒 | 1.606 秒 | 1.924 秒 | 1.589 秒 |
| 長文 | 12.702 秒 | 3.416 秒 | 4.109 秒 | 4.133 秒 |

新規起動した 0.25.1 の `GET /version` は `"0.25.1"`、`GET /core_versions` は `["0.16.1"]`。既存 0.25.1 と新規展開 0.25.1 の `run` は SHA-256 が一致しました。中文・長文の 3〜4 倍差はエンジンの版差だけでは説明できず、既存の稼働プロセスと新規起動プロセスの条件差が影響しています。稼働時間そのものによる劣化か、起動設定やほかの状態差によるものかは未特定です。`libvoicevox_onnxruntime.dylib` の Mach-O install name に記録された ONNX Runtime は 0.25.1 と 0.25.2 が `1.17.3`、preview が `1.23.2`。新規起動版同士では明確な新版の速度優位は見られません。

## 実行上の注意

`uv run --no-sync` が「プロジェクトの Python 3.10 要求と `.venv` の Python 3.11 が一致しない」と警告する場合は、`synth.sh` と同じく `--python 3.11` を明示してください。今回の `.venv` は Python 3.11.3 で、MPS 推論は正常終了しました。初回は checkpoint と watermark モデルの取得に時間がかかります。音声の自動再生はしません。
