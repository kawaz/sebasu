# ローカル話者識別 PoC

Apple M1 Max、macOS 26、Python 3.11。音声再生・マイク取得なし。`say -o` で作った日本語合成音声 Kyoko / Flo (日本語（日本）) / Grandpa (日本語（日本）) を仮想話者として扱う。登録は各話者の異なる3文の埋め込み平均、判定は異なる6文の cosine 類似度最大値。標準速度 180 wpm、追加速度 150 / 220 wpm、16 kHz mono PCM。3話者×(登録3+判定6×3速度)=63ファイル。

## セットアップと再実行

```sh
cd poc/speaker-id
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python numpy scipy soundfile torch torchaudio speechbrain onnxruntime
.venv/bin/python enroll.py --generate
.venv/bin/python enroll.py --model speechbrain
.venv/bin/python identify.py --model speechbrain --seconds 1
.venv/bin/python identify.py --model speechbrain --seconds 2
.venv/bin/python identify.py --model speechbrain --seconds 3
.venv/bin/python identify.py --model speechbrain --rate 150
.venv/bin/python identify.py --model speechbrain --rate 220
```

モデル取得は初回にネットワーク接続が必要。キャッシュ、生成音声、登録結果と仮想環境は `.gitignore` 対象。埋め込み計算時間は各判定音声を3回計測し、その中央値を出したうえで全発話の中央値を集計。モデルロード時間はプロセスごとに計測。最初のモデル取得を含むコールドロード 43.544秒、キャッシュ利用時 0.85秒程度。

## 比較結果

| 候補 | ライセンス | この環境での結果 |
|---|---|---|
| SpeechBrain ECAPA-TDNN (`speechbrain/spkrec-ecapa-voxceleb`) | SpeechBrain Apache-2.0、モデル Apache-2.0 | 動作。1秒 18/18、中央値マージン +0.356、埋め込み中央値 0.020秒 |
| WeSpeaker ResNet34 / CAM++ | Apache-2.0 (ソース) | PyPI に `wespeaker` なし。GitHub 版はインストールできたが、import 時に依存 `s3prl` が削除済みの `torchaudio.set_audio_backend` を呼び AttributeError。モデルロード・計測不能 |
| 3D-Speaker CAM++ | Apache-2.0 (ソース) | 未計測。ModelScope からのモデル取得と推論 API 確認は未実施 |
| pyannote embedding (`pyannote/embedding`) | MIT (pyannote.audio コード)、モデル利用条件は Hugging Face 側のモデルカードで確認が必要 | 未計測。gated model の承認・token 取得は行わない |
| NVIDIA NeMo TitaNet | Apache-2.0 (NeMo コード)、モデルライセンスは各モデルカード参照 | 未計測。macOS の依存導入は未実施 |

**現時点の推奨は SpeechBrain に限定**。他候補の精度・速度を比較できていないため優劣は主張しない。WeSpeaker の `--model wespeaker` は障害の再現用であり、正常動作を保証しない。

### SpeechBrain 実測値

| 音声条件 | 判定 | マージン中央値 | 1発話埋め込み中央値 | ロード時間 |
|---|---:|---:|---:|---:|
| 180 wpm、先頭1秒 | 18/18 | +0.356 | 0.020秒 | 0.854秒 |
| 180 wpm、先頭2秒 | 18/18 | +0.361 | 0.021秒 | 0.861秒 |
| 180 wpm、先頭3秒 | 18/18 | +0.361 | 0.021秒 | 0.856秒 |
| 150 wpm、全文 | 18/18 | +0.387 | 0.021秒 | 1.346秒 |
| 220 wpm、全文 | 18/18 | +0.358 | 0.019秒 | 0.950秒 |

`say` が終了コード0で空音声を出力するケースがあったため、生成処理でサンプル数を確認して再試行する。空音声を再生成した後に150 wpmも18件で再測定した。

1秒行列の実出力（列は登録 voice0=Kyoko、voice1=Flo、voice2=Grandpa、末列は正解類似度−最大誤話者類似度）:

```
true utterance voice0 voice1 voice2 margin
voice0 0 0.468 0.302 0.179 +0.167
voice0 1 0.679 0.200 0.175 +0.479
voice0 2 0.809 0.251 0.202 +0.558
voice0 3 0.678 0.157 0.130 +0.520
voice0 4 0.774 0.090 0.073 +0.683
voice0 5 0.709 0.135 0.113 +0.574
voice1 0 0.215 0.621 0.293 +0.327
voice1 1 0.177 0.674 0.318 +0.355
voice1 2 0.236 0.700 0.318 +0.382
voice1 3 0.252 0.761 0.381 +0.379
voice1 4 0.217 0.752 0.378 +0.374
voice1 5 0.219 0.584 0.319 +0.265
voice2 0 0.133 0.283 0.494 +0.211
voice2 1 0.230 0.346 0.607 +0.261
voice2 2 0.122 0.433 0.780 +0.347
voice2 3 0.128 0.446 0.671 +0.224
voice2 4 0.078 0.344 0.701 +0.357
voice2 5 0.031 0.316 0.661 +0.345
accuracy=18/18 (100.0%); median_margin=+0.356; median_embedding_seconds=0.020
```

合成音声は声質が一定でノイズやマイク位置の変化もなく、実際の家族の類似声・環境音・短い発話の検証にはならない。1秒切断は実際の有声音が1秒存在する保証でもない。150/220 wpm も同じ音声合成器からの生成で、自然発話の速度変動とは異なる。

## 実話者での再評価

録音は kawaz 本人が行う。以下は macOS 標準 `sox` が導入済みの場合の例で、使用前に機器を確認し録音同意を得る。`rec` がなければ録音アプリで16 kHz mono WAV を書き出す。最初に `audio/` を別の場所に退避し、`voice0`、`voice1` 等へ参加者を割り当て、各参加者の独立した登録発話3個と別の判定発話6個を以下のファイル名で保存する。合成音声と混ぜない。

```sh
rec -q -r 16000 -c 1 -b 16 audio/voice0-enroll0-r180.wav trim 0 7
rec -q -r 16000 -c 1 -b 16 audio/voice0-test0-r180.wav trim 0 2
# 各参加者について enroll0..2、test0..5 を録り、同名規則で保存する
.venv/bin/python enroll.py --model speechbrain
.venv/bin/python identify.py --model speechbrain --seconds 1
```

現行スクリプトは3話者固定なので、参加者不足時は `enroll.py` の `VOICES` を参加者数に合わせて変更する。`--generate` は実話者音声を置いた後には実行しない。モデルや音声長を変えて正解率だけでなく負のマージンと誤認相手も確認する。
