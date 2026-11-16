# 複数ウェイクワード戦略の分析

## 複数パターン登録のメリット・デメリット

### ✅ メリット
1. **家族全員が使いやすい**
   - 大人：「おーけーはうす」
   - 子供：「おっけーはうす」
   - 急いでる時：「おっけー」だけでも反応

2. **認識率の向上**
   - 発音の個人差をカバー
   - 状況に応じた自然な発話に対応

3. **ストレスフリー**
   - 「正しく言わなきゃ」というプレッシャーがない
   - 自然な会話の流れで使える

### ⚠️ デメリット
1. **誤認識のリスク**
   - パターンが多いほど誤検出の可能性が上がる
   - 特に短いパターン（「おっけー」のみ）は危険

2. **リソース使用**
   - 各パターンで少しずつCPU/メモリを使用
   - ただし実測では1パターンあたり+0.5%程度

3. **管理の複雑さ**
   - 各パターンの感度調整が必要
   - どのパターンで認識したか区別できない

## 推奨構成

### 🎯 おすすめ：2-3パターンの組み合わせ

```python
# 実用的な構成
wake_words = [
    {
        "file": "おっけーはうす.ppn",
        "sensitivity": 0.5,      # メイン
        "description": "標準"
    },
    {
        "file": "おーけーはうす.ppn", 
        "sensitivity": 0.4,      # サブ（感度やや低め）
        "description": "丁寧版"
    }
]
```

### 作成するパターン候補

#### 必須パターン（2つ）
1. **「おっけーはうす」** - メイン、感度0.5
2. **「おーけーはうす」** - サブ、感度0.4

#### オプション（必要に応じて追加）
3. **「ねえはうす」** - より短い代替案、感度0.3
4. **「はろーはうす」** - 英語練習用、感度0.4

## 感度設定の指針

```python
# 感度設定例
sensitivities = {
    "メインパターン": 0.5,      # 標準
    "類似パターン": 0.4,        # やや低め
    "短いパターン": 0.3,        # 誤認識防止で低め
    "長いパターン": 0.6         # 認識しやすく高め
}
```

## 実装例

```python
class MultiWakeWordEngine:
    def __init__(self):
        self.wake_words = [
            ("wake_words/おっけーはうす.ppn", 0.5),
            ("wake_words/おーけーはうす.ppn", 0.4),
        ]
        
        # Porcupine初期化
        self.porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[w[0] for w in self.wake_words],
            sensitivities=[w[1] for w in self.wake_words]
        )
    
    def process(self, audio_frame):
        result = self.porcupine.process(audio_frame)
        if result >= 0:
            # どのパターンで認識したかログに記録
            pattern = self.wake_words[result][0]
            print(f"検出: {pattern}")
            return True
        return False
```

## テスト計画

### Step 1: 個別テスト
各パターンを単独でテスト
```bash
# おっけーはうす（メイン）
uv run python test_custom_wake_word.py wake_words/おっけーはうす.ppn "おっけーはうす" -s 0.5

# おーけーはうす（サブ）
uv run python test_custom_wake_word.py wake_words/おーけーはうす.ppn "おーけーはうす" -s 0.4
```

### Step 2: 統合テスト
全パターンを同時に登録してテスト

### Step 3: 家族テスト
- 各家族メンバーが10回ずつ試す
- 認識率と誤認識を記録
- 感度を微調整

## 誤認識対策

### 監視すべき誤認識パターン
- 「オッケー」→ 日常会話での「OK」
- 「ハウス」→ 単独での「house」
- 類似音→ 「おっけい」「おけ」

### 対策
1. **文脈フィルター**
   ```python
   # 2秒以内に複数回検出したら無視
   if time.time() - last_detection < 2.0:
       return False
   ```

2. **ノイズゲート**
   ```python
   # 音量が一定以下なら無視
   if audio_volume < threshold:
       return False
   ```

## 結論と推奨

### 💡 推奨アプローチ

1. **まず2パターンから始める**
   - おっけーはうす（メイン）
   - おーけーはうす（サブ）

2. **1週間使ってみて調整**
   - 誤認識が多い → 感度を下げる
   - 認識しない → 感度を上げる

3. **必要なら3つ目を追加**
   - 家族の要望に応じて

### 設定例
```
おっけーはうす: 感度0.5（言いやすいのでメイン）
おーけーはうす: 感度0.4（フォーマルな場面用）
```

これなら家族全員が自然に使えて、誤認識も最小限に抑えられます！