# VOICEVOX 常駐 + vsay CLI (保管物)

kawaz/voice-agent の `sandbox/tts-comparison/` で運用していた、VOICEVOX エンジンの launchd 常駐と、それを叩く読み上げ CLI `vsay` の一式を写したもの。ここにあるのは入れ直すための材料で、置いただけでは常駐も `vsay` コマンドも有効にならない。エンジン本体 (約 2 GB) は含めていない。

## 中身

| パス | 内容 |
| --- | --- |
| `scripts/` | 元の `sandbox/tts-comparison/` の git 管理下ファイル (生成物の `outputs/*.aiff` とエンジンへの symlink を除く)。uv プロジェクト |
| `scripts/vsay` | 統合 CLI。サブコマンド `direct` (既定) / `api` / `server` / `engine` / `list` |
| `scripts/vsay_direct.py` | エンジンの HTTP API (port 50021) を直接叩いて `afplay` で再生する本体 |
| `scripts/vsay_api.py`、`scripts/tts_api_*.py` | 間に立てる TTS API サーバ (port 8000 / 8002 / 8003) とそのクライアントの試作 |
| `scripts/voicevox_manager.py` | エンジンの setup (取得・展開) / start / stop / status |
| `scripts/bench_tts.py` | HTTP API と Python バインディング (voicevox_core) の速度比較 |
| `scripts/FINDINGS.md`、`scripts/voicevox_setup.md`、`scripts/README*.md` | 比較検証時のメモとセットアップ手順 |
| `scripts/archive/`、`scripts/vsay_old`、`scripts/vsay2_old` | 比較検証で使った個別スクリプトと旧版 CLI |
| `docs/DR-001-voicevox-tts-setup.md` | HTTP API 方式・launchd 常駐・発話先頭対策・vsay 設計の判断記録 |
| `docs/2026-09-30-voicevox-engine-slowdown-over-uptime.md` | 常駐エンジンが稼働時間とともに 3〜4 倍遅くなる件 (原因未特定) |
| `docs/tts-implementation-guide.md`、`docs/20250625T2000-tts-comparison.md`、`docs/20250627T1445-tts-implementation.md` | TTS 実装ガイドと作業ログ |
| `launchd/com.voicevox.engine.plist` | ログイン時起動 + KeepAlive のテンプレ |
| `launchd/com.voicevox.engine.restart.plist` | 毎日 2:00 に `launchctl kickstart -k` で再起動するテンプレ |

写した文書の中のパス (`sandbox/tts-comparison/` 等) は voice-agent 側の配置のまま。ここでは `scripts/` に読み替える。

## 入れ直す手順

### 1. エンジンを置く

`vsay` は `uv run` の作業ディレクトリを `scripts/` に固定し、エンジンを `scripts/voicevox_engine` (展開ディレクトリへの symlink) から探す。

```sh
cd poc/voicevox-vsay/scripts
uv run python voicevox_manager.py setup
```

`setup` は GitHub Releases から `voicevox_engine-macos-<arm64|x64>-0.25.1.7z.001` を `curl` で取得し、`7z` (`brew install p7zip`) で `voicevox_engine-macos-<arch>-0.25.1/` に展開して `run` に実行権限を付け、`voicevox_engine` の symlink を張る。版はスクリプト内で 0.25.1 固定。最後に使っていたのは 0.25.2 で、別の版を使う時は手で展開して `voicevox_engine` の symlink を張り替える。

- 未確認: 現行版のアーカイブが `.7z.001` 1 本で完結するか (分割の 2 本目以降が要る場合、`setup` は対応していない)
- `setup_voicevox_manual.sh` は同じ処理のシェル版で、版が 0.23.1 固定
- `scripts/.gitignore` の `voicevox_engine/` は symlink にはマッチしない。symlink を張ると VCS の変更に出るので、コミットしないよう注意する

### 2. vsay を動かす

uv と Python 3.11 (`scripts/.python-version`) が要る。依存は `scripts/pyproject.toml` (`requests` 等)。

```sh
cd poc/voicevox-vsay/scripts
uv run python voicevox_manager.py start   # フォアグラウンドで起動 (常駐させるなら 3. の launchd)
./vsay "こんにちは"                         # = vsay direct。話者 3 (ずんだもん)、話速 1.2
./vsay --speaker 2 --rate 1.5 "テキスト"
echo "標準入力から" | ./vsay
./vsay list                                # 話者一覧
./vsay engine status
```

`vsay` は `os.path.realpath(__file__)` で実体の位置を解決するので、PATH 上に symlink を置けばどこからでも使える (例: `ln -s "$PWD/vsay" ~/bin/vsay`)。

- `vsay api` / `vsay server` が使う `tts_api_server.py` の依存 (fastapi、uvicorn、aiohttp、aiofiles) は `pyproject.toml` に入っていない。`../tts-irodori-voicevox/README.md` の計測では `uv run --with fastapi --with aiohttp --with aiofiles --with uvicorn python tts_api_server.py` で補った
- `bench_tts.py` の Python バインディング側は `voicevox_core` を import するが、これも `pyproject.toml` に入っていない。入れ方は未確認

### 3. launchd に常駐させる

`launchd/` の 2 本は置き換え箇所をプレースホルダにしたテンプレ。

| プレースホルダ | 置き換える値 |
| --- | --- |
| `__VOICEVOX_ENGINE_DIR__` | エンジンの置き場 (`scripts/voicevox_engine` の symlink の絶対パス)。`run` はこの下 |
| `__LOG_DIR__` | stdout / stderr のログの置き場 (元は `scripts/` 相当の場所。`*.log` は `scripts/.gitignore` 済み) |
| `__UID__` | ログインユーザの uid (`id -u` の値)。`gui/<uid>/com.voicevox.engine` のドメイン指定に使う |

置き換えた 2 本を `~/Library/LaunchAgents/` に置いて launchd に読み込ませる。元の環境で登録に使ったコマンドは記録に残っていない (未確認)。現行の launchctl で書くなら `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.voicevox.engine.plist` (restart 側も同様) だが、この形で登録して動くことは未検証。

## 既知の知見

- 発話先頭が欠ける: macOS のオーディオデバイスがスリープから復帰する間に先頭が欠けるため、`vsay_direct.py` は `prePhonemeLength` を 0.5 にし、先頭 3 モーラの pitch と母音長を強調する (`--emphasis-*` で調整、`--emphasis-moras 0` で無効)。判断は `docs/DR-001-voicevox-tts-setup.md` の 3 節
- HTTP API 方式を採る理由 (常駐エンジンの方が初期化がなく合成も速い): DR-001 の 1 節
- 稼働時間による劣化: 2:00 の再起動から約 19 時間後で短文 1.39 / 中文 5.93 / 長文 12.70 秒、再起動直後は 0.54 / 1.23 / 2.94 秒。新規起動で解消し原因は未特定。`docs/2026-09-30-voicevox-engine-slowdown-over-uptime.md`、版ごとの実測は `../tts-irodori-voicevox/README.md` (計測スクリプトは同ディレクトリの `bench_voicevox.py`)
- 他の TTS 候補との比較: `scripts/FINDINGS.md`、`../tts-more/README.md`
