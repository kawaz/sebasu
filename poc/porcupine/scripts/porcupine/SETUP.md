# Picovoice Porcupine セットアップガイド

## 1. アカウント作成とAPIキー取得

### Picovoice Consoleでアカウント作成
1. https://console.picovoice.ai/ にアクセス
2. 「Sign Up」から無料アカウントを作成
3. メールアドレスの確認

### APIキー（Access Key）の取得
1. ダッシュボードにログイン
2. 左メニューの「AccessKey」をクリック
3. 「Show」ボタンでキーを表示
4. キーをコピー

### 環境変数の設定
```bash
# ~/.bashrc または ~/.zshrc に追加
export PICOVOICE_ACCESS_KEY='your-access-key-here'

# 即座に反映
source ~/.bashrc  # または source ~/.zshrc
```

## 2. 依存関係のインストール

```bash
cd sandbox/porcupine
uv sync
```

## 3. 動作確認

### 基本情報の確認（APIキー不要）
```bash
uv run python test_basic.py
```

### 実際の動作テスト（APIキー必要）
```bash
uv run python test_with_key.py
```

## 4. 無料枠の制限

### Personal Tier（無料）
- **月間使用量**: 無制限
- **同時ユーザー数**: 3ユーザーまで
- **商用利用**: 可能（3ユーザーまで）
- **カスタムウェイクワード**: 月3つまで作成可能
- **サポート**: コミュニティフォーラム

### 注意事項
- APIキーは認証のみに使用
- 音声データは外部送信されない
- 初回認証後はオフライン動作可能

## 5. 日本語ウェイクワードの作成

1. Picovoice Consoleにログイン
2. 「Wake Word」→「Train Wake Word」
3. 設定：
   - Phrase: 日本語フレーズ（例：「ねえアシスタント」）
   - Language: Japanese
   - Target Platform: 使用するプラットフォームを選択
4. 「Train」をクリック（数分かかります）
5. 完了後、`.ppn`ファイルをダウンロード

## 6. トラブルシューティング

### "Access key required"エラー
```bash
# APIキーが設定されているか確認
echo $PICOVOICE_ACCESS_KEY

# 設定されていない場合
export PICOVOICE_ACCESS_KEY='your-key-here'
```

### マイクが認識されない
```bash
# 利用可能なデバイスを確認
uv run python -c "import pvrecorder; print(pvrecorder.PvRecorder.get_available_devices())"
```

### オフライン環境での使用
1. オンライン環境で一度認証を実行
2. その後はインターネット接続なしで使用可能

## 7. 本番環境への移行

### コード例
```python
import pvporcupine
import pvrecorder

# 本番用の設定
porcupine = pvporcupine.create(
    access_key=os.environ['PICOVOICE_ACCESS_KEY'],
    keyword_paths=['./models/hey_assistant_ja.ppn'],  # カスタムモデル
    sensitivities=[0.5]  # 感度調整（0-1）
)
```

### Raspberry Piでの使用
- Raspberry Pi 3以上を推奨
- 32-bit/64-bit OSどちらも対応
- CPU使用率: 約10-15%