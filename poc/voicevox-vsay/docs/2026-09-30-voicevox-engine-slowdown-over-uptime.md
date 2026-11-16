---
title: VOICEVOX 常駐 engine が稼働時間で 3〜4 倍遅くなる
status: open
category: bug
created: 2026-09-30T23:10:39+09:00
last_read:
open_entered: 2026-09-30T23:10:39+09:00
wip_entered:
blocked_entered:
pending_entered:
discarded_entered:
resolved_entered:
discard_reason:
pending_reason:
close_reason:
blocked_by:
origin: 自リポ TODO
---

# VOICEVOX 常駐 engine が稼働時間で 3〜4 倍遅くなる

## 概要

VOICEVOX 常駐 engine (launchd com.voicevox.engine) が稼働時間で 3〜4 倍遅くなる。2:00 の定期再起動から約 19 時間後の計測で短文 1.39 / 中文 5.93 / 長文 12.70 秒、再起動直後は 0.54 / 1.23 / 2.94 秒。同一バイナリ (SHA 一致) の新規起動で解消するので版の問題ではなく、原因は未特定 (メモリ / スレッド / ONNX セッションの状態が候補)。

## 背景

- 計測スクリプト: workboard-personal incubator の ideas/irodori-tts/bench_voicevox.py、実測は同 README
- 関連変更 (2026-09-30): plist の ProgramArguments / WorkingDirectory を symlink (voicevox_engine/run) 経由に変更、symlink を 0.25.2 に切替済み (0.25.1 ディレクトリは残置)

## 対処候補

- 再起動間隔の短縮
- /version の応答時間を監視して閾値超過で kickstart
- 原因調査 (メモリ / スレッド / ONNX セッションの状態)

## 受け入れ条件

- [ ] 稼働時間によらず合成時間が再起動直後の水準を維持する、または劣化時に自動復旧する

## TODO

