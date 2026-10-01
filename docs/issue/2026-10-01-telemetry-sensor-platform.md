---
title: 各部屋センサーデータの蓄積基盤 (telemetry)
status: open
category: design
created: 2026-10-01T10:17:01+09:00
last_read:
open_entered: 2026-10-01T10:17:01+09:00
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

# 各部屋センサーデータの蓄積基盤 (telemetry)

## 概要

各部屋の ESP32 を、音声衛星としてだけでなくセンサーデータをサーバに蓄積して活用する基盤にもしたい。

- 温湿度: 音声衛星 (ESP32-S3 + XVF3800 + スピーカー) と同じケースに入れると自己発熱で値がずれる懸念がある。ケース設計の問題も絡む
- BLE 受動スキャン: 家庭内の数十台 (100 未満) の BT デバイスの addr と RSSI を passive scan で拾い、在室確認と紛失物の探し場所の補助に使う

telemetry は音声 pipeline と責務が別。共通なのは「各部屋に ESP32 がある」「サーバに集める」という物理と輸送だけで、`AudioChunk` 等の音声 IF とは直交する (境界は docs/DESIGN.md の Domain and boundaries 節)。

## 構成案

- ESP32 ファームは音声衛星とセンサー衛星の両役を担える
- データ側は別コンポーネント `telemetry`: 収集 → 時系列 DB → 活用
- 音声アシスタントは tools 経由で telemetry を参照する。例: 在室している部屋に返事する、紛失物を最後に拾った部屋と時刻を答える

## 温湿度の選択肢

| 案 | 内容 | 利点 | 欠点 |
|---|---|---|---|
| A. 同一ケース + ケーブル | 音声衛星にセンサーをケーブルで外出し | デバイス数が増えない | 自己発熱の影響を完全には切れない、ケース設計が複雑 |
| B. 別デバイス | ESP32-C3 級 + SHT40、電池駆動、BLE advertise で値を吐く (Xiaomi / SwitchBot 温湿度計と同方式) | 発熱と無縁、置き場所自由、音声衛星の BLE scan が拾うので追加の輸送が不要 | デバイスと電池管理が増える |

推し: **B (別デバイス)**。BLE scan の受信経路をそのまま流用でき、既製品 (Xiaomi / SwitchBot) も同じ経路で取り込める。

## BLE scan の設計注意

1. ESP32 側で間引く: 同一 addr は N 秒に 1 回、RSSI 変化が閾値未満なら送らない
2. MAC ランダム化: iPhone / Apple Watch 等は約 15 分で addr が変わる。在室判定は製造者データ / サービス UUID / 名前付け済みデバイスに限定する割り切り
3. RSSI は「最も強い部屋」程度の判定に留め、距離推定はしない。紛失物は「最後に拾った部屋と時刻」を返す

## 実機検証項目

- Wi-Fi + BLE 共存: 音声ストリーミング中の BLE scan は無線を取り合う。音声優先で scan を間欠にした時の音声途切れと scan 取りこぼし率
- 間引き条件 (N 秒、RSSI 閾値) と送信量
- 別デバイス案の電池寿命と advertise 間隔
- 部屋判定の正答率 (隣室との RSSI 差)

## 受け入れ条件

- [ ] 裁定待ち 3 点 (温湿度を別デバイスにするか / 時系列 DB の選定 / 紛失物の UI) が決まる
- [ ] 実機検証項目が検証され結果が記録される

## 裁定待ち

- 温湿度を別デバイスにするか (推し: 別デバイス)
- 時系列 DB の選定
- 紛失物の UI (音声応答のみか、画面も持つか)
