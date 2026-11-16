# VOICEVOX セットアップガイド

## 概要

VOICEVOXは3つのコンポーネントで構成されています：
- **エディター**: GUI部分（アプリケーション）
- **エンジン**: HTTPサーバー部分（APIを提供）
- **コア**: 実際の音声合成を行う部分

Pythonから使用する場合は、エンジンのみが必要です。

## セットアップ手順

### 1. VOICEVOXエンジンのダウンロード

VOICEVOXエンジンをGitHubからダウンロードします：
https://github.com/VOICEVOX/voicevox_engine/releases

macOS用の選択肢：
- `voicevox_engine-macos-x64-cpu-{version}.zip` - Intel Mac用
- `voicevox_engine-macos-arm64-cpu-{version}.zip` - Apple Silicon Mac用

### 2. エンジンの起動

```bash
# ダウンロードしたzipを解凍
unzip voicevox_engine-macos-arm64-cpu-*.zip
cd voicevox_engine-macos-arm64-cpu-*

# 実行権限を付与
chmod +x run

# エンジンを起動
./run
```

起動すると、デフォルトでは `http://localhost:50021` でAPIサーバーが起動します。

### 3. APIドキュメントの確認

エンジン起動後、ブラウザで以下にアクセス：
- API Docs: http://localhost:50021/docs
- 話者一覧: http://localhost:50021/speakers

## 簡易起動スクリプト

VOICEVOXエンジンを自動的に起動するスクリプトを作成できます：

```python
import subprocess
import time
import os
import requests

def start_voicevox_engine(engine_path):
    """VOICEVOXエンジンを起動"""
    run_path = os.path.join(engine_path, "run")
    
    # エンジンを起動
    process = subprocess.Popen([run_path])
    
    # 起動を待つ
    for i in range(30):  # 最大30秒待つ
        try:
            response = requests.get('http://localhost:50021/version', timeout=1)
            if response.status_code == 200:
                print("VOICEVOXエンジンが起動しました")
                return process
        except:
            pass
        time.sleep(1)
    
    raise Exception("VOICEVOXエンジンの起動に失敗しました")
```

## Docker版の使用（オプション）

Dockerを使用する場合：

```bash
# CPU版
docker pull voicevox/voicevox_engine:cpu-ubuntu20.04-latest
docker run --rm -it -p '127.0.0.1:50021:50021' voicevox/voicevox_engine:cpu-ubuntu20.04-latest

# GPU版（NVIDIA GPUが必要）
docker pull voicevox/voicevox_engine:nvidia-ubuntu20.04-latest
docker run --rm --gpus all -it -p '127.0.0.1:50021:50021' voicevox/voicevox_engine:nvidia-ubuntu20.04-latest
```

## トラブルシューティング

### macOSでの実行権限エラー
```bash
# 実行権限を付与
chmod +x run
xattr -dr com.apple.quarantine .
```

### ポートが使用中の場合
```bash
# 別のポートで起動
./run --port 50022
```

### セキュリティ設定
VOICEVOXはデフォルトでlocalhost/127.0.0.1からのアクセスのみを許可しています。
外部からアクセスする場合は、`--cors_policy_mode all` オプションを使用します（セキュリティリスクがあるため推奨されません）。