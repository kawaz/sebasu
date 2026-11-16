# TTS（Text-to-Speech）検証結果

## 検証日
2025年6月25日

## 検証環境
- macOS (Apple Silicon)
- Python 3.11.3
- 完全オフライン動作を優先

## 検証結果サマリー

| ライブラリ | オフライン動作 | 日本語品質 | セットアップ | レイテンシ | 特徴 |
|-----------|--------------|-----------|------------|-----------|------|
| macOS say | ✅ 完全 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 低い | macOS限定、即座に利用可能 |
| pyopenjtalk | ✅ 完全 | ⭐⭐ | ⭐⭐⭐⭐ | 非常に低い | 軽量、機械的だが明瞭 |
| VOICEVOX | ✅ ローカル | ⭐⭐⭐⭐⭐ | ⭐⭐ | 中程度 | 高品質、キャラクターボイス |
| pyttsx3 | ✅ 完全 | ⭐ | ⭐⭐⭐ | 低い | macOSで問題あり |

## 詳細評価

### 1. macOS sayコマンド

**メリット:**
- macOSに標準搭載、追加インストール不要
- 完全オフライン動作
- 高品質な日本語音声（Kyoko）
- 低レイテンシ（0.7-0.8秒/文）
- 速度調整可能（-r オプション）

**デメリット:**
- macOS限定
- 音声の種類が限定的（日本語は1種類のみ）
- AIFFフォーマット（WAVへの変換が必要な場合あり）

**実装例:**
```python
subprocess.run(['say', '-v', 'Kyoko', '-o', 'output.aiff', 'こんにちは'])
```

**推奨用途:**
- macOSでの開発・プロトタイピング
- シンプルな音声合成が必要な場合

### 2. pyopenjtalk

**メリット:**
- 完全オフライン動作
- 軽量・高速（初回以降は0.03-0.09秒/文）
- 依存関係が少ない
- 日本語特化
- 音響特徴の詳細な取得が可能

**デメリット:**
- 音質が機械的
- 感情表現が乏しい
- 速度調整は後処理が必要

**実装例:**
```python
import pyopenjtalk
audio, sr = pyopenjtalk.tts("こんにちは")
```

**推奨用途:**
- リソース制約のある環境（Raspberry Pi等）
- 基本的な音声合成で十分な場合
- 低レイテンシが重要な場合

### 3. VOICEVOX

**メリット:**
- 非常に高品質な日本語音声
- 多彩なキャラクターボイス（ずんだもん等）
- 感情表現が豊か
- 速度・ピッチ・音量などの細かい調整可能
- 完全無料・商用利用可能
- APIでの制御が柔軟

**デメリット:**
- 別途エンジンのダウンロード・起動が必要
- 初回セットアップがやや複雑
- HTTPサーバー経由のため若干のオーバーヘッド
- メモリ使用量が大きい（エンジン起動時）

**実装例:**
```python
# エンジンをローカルで起動後
params = {'text': 'こんにちは', 'speaker': 3}
query = requests.post('http://localhost:50021/audio_query', params=params)
audio = requests.post('http://localhost:50021/synthesis', 
                     params={'speaker': 3}, 
                     json=query.json())
```

**推奨用途:**
- 高品質な音声合成が必要な場合
- キャラクターボイスを活用したい場合
- エンターテイメント性のあるアプリケーション

### 4. pyttsx3

**メリット:**
- クロスプラットフォーム対応（理論上）
- シンプルなAPI

**デメリット:**
- macOSで実行時エラーが発生
- 日本語音声の品質が低い
- 実用性に課題

## 推奨構成

### Voice Agent プロジェクトでの推奨

**開発フェーズ:**
1. **第一選択**: macOS sayコマンド
   - 即座に利用可能
   - 十分な品質
   - 低レイテンシ

2. **第二選択**: pyopenjtalk
   - クロスプラットフォーム
   - 軽量・高速

**本番フェーズ（高品質が必要な場合）:**
- VOICEVOX
  - エンジンの自動起動スクリプトを整備
  - Dockerでの運用も検討

### 実装アーキテクチャ案

```python
class TTSManager:
    def __init__(self, engine='auto'):
        if engine == 'auto':
            # 利用可能なエンジンを自動選択
            if platform.system() == 'Darwin':
                self.engine = MacOSSayEngine()
            else:
                self.engine = PyOpenJTalkEngine()
        elif engine == 'voicevox':
            self.engine = VoiceVoxEngine()
        # ... 他のエンジン
    
    def speak(self, text):
        return self.engine.synthesize(text)
```

## セットアップ手順

### macOS say
```bash
# 追加セットアップ不要
```

### pyopenjtalk
```bash
uv add pyopenjtalk
```

### VOICEVOX
```bash
# 方法1: アプリケーション版
# https://voicevox.hiroshiba.jp/ からダウンロード

# 方法2: Docker版
docker run --rm -it -p '127.0.0.1:50021:50021' \
  voicevox/voicevox_engine:cpu-ubuntu20.04-latest

# 方法3: エンジン版
# GitHubからダウンロードして ./run を実行
```

## 結論

Voice Agentプロジェクトでは、以下の段階的アプローチを推奨：

1. **MVP/開発**: macOS sayコマンドまたはpyopenjtalk
2. **品質向上**: VOICEVOXの導入
3. **マルチプラットフォーム**: 各OSネイティブのTTSをラップする抽象化層

オフライン動作を重視する場合は、macOS sayとpyopenjltalkの組み合わせが最も実用的です。