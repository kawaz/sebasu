# Apple SpeechTranscriber 日本語実機 PoC

2026-09-30、Apple M1 Max / macOS 26.5 (Darwin 25.5)、Swift 6.3.3、MacOSX SDK 26.5。Speech framework の `SpeechAnalyzer` + `SpeechTranscriber(locale: ja-JP)` がオンデバイスの日本語文字起こしと発話中の volatile partial を返すことを確認した。Apple の [SpeechTranscriber](https://developer.apple.com/documentation/speech/speechtranscriber)、[SpeechAnalyzer](https://developer.apple.com/documentation/speech/speechanalyzer)、[AssetInventory](https://developer.apple.com/documentation/speech/assetinventory)、[WWDC25 動画](https://developer.apple.com/videos/play/wwdc2025/277/) に対応。型とメソッドは macOS SDK の `Speech.swiftinterface` と実機コンパイルで確認した。

## ビルド・実行

このディレクトリで `swiftc -parse-as-library -o transcribe transcribe.swift` を実行。`./transcribe /path/to/sample.wav` は実時間ペース、`./transcribe /path/to/sample.wav --fast` は待機せず入力し、`./transcribe say-ja.wav` は添付した 16 kHz mono 音声。48 kHz mono の音声も内部で 16 kHz mono Int16 に変換する。`./transcribe --mic` は現在の許可済みマイクを 10 秒間読む。`--fast` の `lagFromRangeEnd` は音声時間軸と実時計が同期しないため負数となり、レイテンシの指標に使わない。

二本目の生成（スピーカーからは鳴らない）: `/usr/bin/say -v Kyoko -o /tmp/say-ja.aiff '明日の天気を教えて。リビングの電気を消して。'`、`afconvert -f WAVE -d LEI16@16000 -c 1 /tmp/say-ja.aiff say-ja.wav`。元の Irodori 音声は `../tts-irodori-voicevox/out/sample.wav` にある。

## ロケールとモデル

実際の `supportedLocales` 出力（Swift の Locale identifier は `_` 表記）:

```text
["de_AT", "de_CH", "de_DE", "en_AU", "en_CA", "en_GB", "en_IE", "en_IN", "en_NZ", "en_SG", "en_US", "en_ZA", "es_CL", "es_ES", "es_MX", "es_US", "fr_BE", "fr_CA", "fr_CH", "fr_FR", "it_CH", "it_IT", "ja_JP", "ko_KR", "pt_BR", "pt_PT", "yue_CN", "zh_CN", "zh_HK", "zh_TW"]
```

`installedLocales` は `["en_AU", "en_CA", "en_GB", "en_IE", "en_IN", "en_NZ", "en_SG", "en_US", "en_ZA", "ja_JP"]`。初回 `AssetInventory.status(forModules:)` は `supported`、`assetInstallationRequest(...).downloadAndInstall()` は **0.977 秒**、直後 `installed`。`installedLocales` に `ja_JP` があっても対象 transcriber の asset status は `supported` だったため、両者を同一視してはいけない。二回目は `installed` で再取得なし。

## 文字起こしと遅延

音声は 2048 frame ずつ入力し、入力済みフレーム数に対応する経過時間まで待機。`t` は解析開始後の実時間、`audio` は Speech が返す `range`、`lagFromRangeEnd = t − range.end`。`range` は結果全体を覆う累積範囲であり、**単語単位の発話時刻を指さない**。負値はバッファ供給と内部の音声範囲報告の差であり、負の認識遅延の証拠ではない。単語の正確な遅延は音声波形の語境界アノテーションが必要。下表の語の発話完了時刻は音声データから推定しておらず、partial が現れた `t` と範囲終端を示す。

| 音声 | 初回 partial (`t` / 範囲終端) | 発話中の partial 例 (`t`) | 最終 partial (`t`) | final (`t`) | final − 音声終端 |
|---|---|---|---|---|---|
| Irodori 4.640 秒 | `こ` (1.105 / 1.109 秒) | `こんにちは。これは` (2.026 秒)、`こんにちは。これは彩り T` (2.960 秒)、`…ローカル` (3.903 秒) | `…テストです。` (4.674 秒) | 4.766 秒 | 0.126 秒 |
| Kyoko 3.472 秒 | `明` (1.043 / 1.152 秒) | `明日の天気を教えて。` (1.939 秒)、`…リビングの電` (2.966 秒) | `…電気を消して。` (3.496 秒) | 3.515 秒 | 0.043 秒 |

期待 Irodori: `こんにちは。これはイロドリ TTS のローカル動作テストです。`。final: `こんにちは。これは彩り TTSのローカル動作テストです。`。固有名詞「イロドリ」は漢字の「彩り」に誤変換され、空白にも差がある。期待 Kyoko: `明日の天気を教えて。リビングの電気を消して。`、final は完全一致。短い合成音声二本だけで家庭内雑音下の精度は判断できない。

`--fast` の Irodori は 4.640 秒を 0.003 秒で供給し、final は 0.125 秒、総所要時間 0.127 秒、RTF = 0.127 / 4.640 = **0.0274**（モデル取得済み、プロセス起動と asset 確認時間は計測外）。fast モードの partial は 0.061 秒から出るが発話中の出力性能評価には用いない。実時間ペースでは字単位で複数の partial が 1 秒程度ごとにまとまって出た。表示された partial は全発話の累積文字列であり、後続 partial に置き換えて描画する必要がある。確定前に家電操作を実行する用途には使わない。

## マイク

`./transcribe --mic` の 10 秒無発話試験では `microphoneAuthorization=3`（許可済み）、`micStarted=true`、`totalElapsed=10.539`、partial / final はゼロ件でクラッシュせず終了した。マイク権限ダイアログは表示されなかった。未許可の場合はダイアログを要求せず終了する実装であり、権限未許可環境の実動作は未検証。実発話を試す際はマイクアクセスを許可した Terminal から `./transcribe --mic` を実行して 10 秒以内に日本語で話しかけ、`partial` / `final` を観察する。発話試験はユーザー本人が行うため、今回の無音実行からマイク発話時のレイテンシは断定しない。
