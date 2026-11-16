# カスタムウェイクワードガイド

## 家族向けウェイクワードの提案

### 推奨ウェイクワード案

#### 1. 愛称系（親しみやすい）
- **「ねえ、ハウス」** - 家を擬人化、短くて言いやすい
- **「オーケー、ホーム」** - OK Googleに似た形式で馴染みやすい
- **「ハロー、アシスタント」** - 子供も発音しやすい
- **「ねえ、ロボット」** - 子供受けが良い

#### 2. 日本語の自然な呼びかけ
- **「おーい」** - 最も自然な日本語の呼びかけ
- **「ちょっと」** - 日常的に使う言葉
- **「すみません」** - 丁寧で誤認識が少ない

#### 3. オリジナルキャラクター系
- **「ねえ、ピコ」** - Picovoiceから取った愛称
- **「オーケー、ミライ」** - 未来の家をイメージ
- **「ハロー、スマート」** - スマートホームから

### 選定のポイント

1. **発音しやすさ**
   - 子供（小学2年生）でも言いやすい
   - 日本語として自然
   - 3-4音節が理想的

2. **誤認識の少なさ**
   - 日常会話で使わない組み合わせ
   - 独特な音の並び
   - 母音が明確

3. **覚えやすさ**
   - 家族全員が自然に使える
   - 意味が分かりやすい

## おすすめトップ3

### 🥇 1位：「ねえ、ハウス」
- **理由**：短い、覚えやすい、子供も言いやすい
- **利点**：「ねえ」で注意喚起、「ハウス」で家を表現

### 🥈 2位：「オーケー、ホーム」
- **理由**：既存のスマートスピーカーに似た形式
- **利点**：直感的、英語学習にもなる

### 🥉 3位：「おーい」
- **理由**：最も自然な日本語
- **利点**：誰でも使える、短い

## カスタムウェイクワードの作成方法

### 1. Picovoice Consoleにアクセス
```
https://console.picovoice.ai/
```

### 2. ウェイクワード作成手順

#### Step 1: ログイン
- アカウントでログイン
- 左メニューから「Wake Word」を選択

#### Step 2: 新規作成
1. 「Train Wake Word」をクリック
2. 以下を入力：
   - **Wake phrase**: ウェイクワード（例：ねえハウス）
   - **Language**: Japanese (ja)
   - **Target Platform**: 使用するデバイス選択

#### Step 3: トレーニング
- 「Train」ボタンをクリック
- 約3-5分待つ（サーバーでモデル生成）

#### Step 4: ダウンロード
- 完成したら.ppnファイルをダウンロード
- ファイル名例：`ねえハウス_ja_mac_v3_0_0.ppn`

### 3. 実装方法

```python
# カスタムウェイクワードの使用
porcupine = pvporcupine.create(
    access_key=access_key,
    keyword_paths=['path/to/ねえハウス_ja_mac_v3_0_0.ppn']
)
```

## テスト用スクリプト

カスタムウェイクワードをテストするスクリプトを作成しましょう：

```python
#!/usr/bin/env python3
"""
カスタムウェイクワードテスト
"""
import os
import pvporcupine
import pvrecorder

def test_custom_wake_word(ppn_path, wake_phrase):
    """カスタムウェイクワードのテスト"""
    access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
    
    print(f"カスタムウェイクワード '{wake_phrase}' をテスト中...")
    
    # Porcupine作成
    porcupine = pvporcupine.create(
        access_key=access_key,
        keyword_paths=[ppn_path]
    )
    
    # レコーダー作成
    recorder = pvrecorder.PvRecorder(
        frame_length=porcupine.frame_length
    )
    
    print(f"\n'{wake_phrase}' と話してください...")
    recorder.start()
    
    try:
        while True:
            pcm = recorder.read()
            result = porcupine.process(pcm)
            
            if result >= 0:
                print(f"✅ 検出！ '{wake_phrase}'")
                
    except KeyboardInterrupt:
        print("\n終了")
    finally:
        recorder.stop()
        recorder.delete()
        porcupine.delete()

if __name__ == "__main__":
    # 使用例
    test_custom_wake_word(
        "wake_words/ねえハウス_ja_mac_v3_0_0.ppn",
        "ねえハウス"
    )
```

## 複数ウェイクワード対応

家族それぞれの好みに合わせて複数登録も可能：

```python
# 複数のウェイクワード
keywords = [
    "wake_words/ねえハウス.ppn",      # メイン
    "wake_words/おーい.ppn",          # シンプル版
    "wake_words/オーケーホーム.ppn"   # 英語風
]

porcupine = pvporcupine.create(
    access_key=access_key,
    keyword_paths=keywords
)
```

## トラブルシューティング

### 認識率が低い場合
1. **感度調整**
   ```python
   sensitivities = [0.7, 0.7, 0.5]  # 各ウェイクワードの感度
   ```

2. **発音の明瞭化**
   - ゆっくりはっきり発音
   - 子供には練習してもらう

3. **環境ノイズ対策**
   - マイクの位置調整
   - ノイズの少ない場所に設置

### 誤認識が多い場合
- 感度を下げる（0.3-0.4）
- より独特なフレーズに変更

## 次のステップ

1. Picovoice Consoleでウェイクワード作成
2. ダウンロードした.ppnファイルをプロジェクトに配置
3. test_custom_wake_word.pyでテスト
4. 家族全員で試して調整

ウェイクワードが決まったら、実装をお手伝いします！