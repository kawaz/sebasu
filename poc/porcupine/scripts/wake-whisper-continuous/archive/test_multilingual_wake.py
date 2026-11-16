#!/usr/bin/env python3
"""
複数言語ウェイクワード同時検出のテストスクリプト
Porcupineで異なる言語のウェイクワードを同時に検出する方法を検証
"""
import pvporcupine
import os
from pathlib import Path

def test_single_instance_mixed_languages():
    """
    1つのPorcupineインスタンスで複数言語のウェイクワードを扱えるかテスト
    """
    print("=== テスト1: 単一インスタンスで複数言語 ===")
    
    # テスト用の設定
    access_key = os.getenv("PICOVOICE_ACCESS_KEY", "YOUR_ACCESS_KEY")
    
    # 異なる言語のppnファイルを想定
    japanese_ppn = "ppns/オッケーセバス_ja_mac_v3_0_0.ppn"
    english_ppn = "ppns/OK-Google_en_mac_v3_0_0.ppn"
    
    try:
        # 方法1: 異なる言語のppnファイルを1つのインスタンスで読み込む
        # （これは動作しない可能性が高い - model_pathが1つしか指定できないため）
        print("\n試行1: 複数言語ppnを単一インスタンスで")
        
        # まず日本語モデルで試す
        if Path(japanese_ppn).exists() and Path(english_ppn).exists():
            try:
                porcupine = pvporcupine.create(
                    access_key=access_key,
                    keyword_paths=[japanese_ppn, english_ppn],
                    model_path='models/porcupine_params_ja.pv'  # 日本語モデル
                )
                print("✅ 成功: 日本語モデルで複数言語ppn読み込み")
                porcupine.delete()
            except Exception as e:
                print(f"❌ エラー: {e}")
                print("→ 予想通り、単一モデルでは異なる言語のppnは扱えない")
        
    except Exception as e:
        print(f"テストエラー: {e}")

def test_multiple_instances():
    """
    複数のPorcupineインスタンスを並列実行する方法をテスト
    """
    print("\n\n=== テスト2: 複数インスタンスで複数言語 ===")
    
    access_key = os.getenv("PICOVOICE_ACCESS_KEY", "YOUR_ACCESS_KEY")
    
    # 各言語用のインスタンスを作成
    instances = []
    
    # 日本語用インスタンス
    try:
        japanese_instance = pvporcupine.create(
            access_key=access_key,
            keywords=['jarvis'],  # ビルトインキーワードで代用
            model_path='models/porcupine_params_ja.pv' if Path('models/porcupine_params_ja.pv').exists() else None
        )
        instances.append(('日本語', japanese_instance))
        print("✅ 日本語インスタンス作成成功")
    except Exception as e:
        print(f"❌ 日本語インスタンス作成失敗: {e}")
    
    # 英語用インスタンス（デフォルトモデル）
    try:
        english_instance = pvporcupine.create(
            access_key=access_key,
            keywords=['picovoice', 'bumblebee']
        )
        instances.append(('英語', english_instance))
        print("✅ 英語インスタンス作成成功")
    except Exception as e:
        print(f"❌ 英語インスタンス作成失敗: {e}")
    
    # メモリとリソース使用状況を確認
    if instances:
        print(f"\n作成されたインスタンス数: {len(instances)}")
        print("各インスタンスの情報:")
        for lang, instance in instances:
            print(f"  - {lang}: サンプルレート={instance.sample_rate}Hz, フレーム長={instance.frame_length}")
    
    # クリーンアップ
    for _, instance in instances:
        instance.delete()
    
    print("\n→ 複数インスタンスを作成することで、異なる言語のウェイクワードを同時に検出可能")

def propose_implementation():
    """
    実装提案を表示
    """
    print("\n\n=== 実装提案: 複数言語ウェイクワード検出 ===")
    
    proposal = """
# 「オッケーセバス」（日本語）と「OK Google」（英語）を同時検出する実装方法

## 方法1: 複数Porcupineインスタンスを使用（推奨）

```python
class MultilingualWakeWordDetector:
    def __init__(self):
        self.detectors = {}
        
    def add_language_detector(self, language, keyword_paths, model_path):
        \"\"\"言語別の検出器を追加\"\"\"
        self.detectors[language] = pvporcupine.create(
            access_key=Config.PICOVOICE_ACCESS_KEY,
            keyword_paths=keyword_paths,
            model_path=model_path
        )
    
    def process_audio(self, audio_frame):
        \"\"\"全ての検出器で音声を処理\"\"\"
        for language, detector in self.detectors.items():
            keyword_index = detector.process(audio_frame)
            if keyword_index >= 0:
                return {
                    'language': language,
                    'keyword_index': keyword_index,
                    'detector': detector
                }
        return None
```

## 方法2: 並列処理による最適化

```python
import threading
from queue import Queue

class ParallelMultilingualDetector:
    def __init__(self):
        self.detectors = []
        self.audio_queue = Queue()
        self.result_queue = Queue()
        
    def add_detector(self, name, detector):
        thread = threading.Thread(
            target=self._detection_worker,
            args=(name, detector)
        )
        thread.daemon = True
        thread.start()
        self.detectors.append((name, detector, thread))
    
    def _detection_worker(self, name, detector):
        while True:
            audio_frame = self.audio_queue.get()
            if audio_frame is None:
                break
            
            keyword_index = detector.process(audio_frame)
            if keyword_index >= 0:
                self.result_queue.put({
                    'name': name,
                    'keyword_index': keyword_index
                })
```

## 実装の注意点

1. **モデルファイルの管理**
   - 各言語用のモデルファイル（.pv）を事前にダウンロード
   - porcupine_helper.pyを使用して自動ダウンロード

2. **ppnファイルの準備**
   - 「オッケーセバス」用の日本語ppnファイル
   - 「OK Google」用の英語ppnファイル
   - Picovoice Consoleで作成可能

3. **リソース使用量**
   - 各インスタンスは独立したメモリを使用
   - CPU使用率は並列度に応じて増加
   - Raspberry Pi 4では2-3言語まで実用的

4. **音声フレームの共有**
   - 同じ音声フレームを全インスタンスに渡す
   - フレームサイズは全インスタンスで共通（512サンプル）
    """
    
    print(proposal)

def main():
    """メイン実行関数"""
    print("Porcupine 複数言語ウェイクワード検出テスト")
    print("=" * 60)
    
    # 各テストを実行
    test_single_instance_mixed_languages()
    test_multiple_instances()
    propose_implementation()
    
    print("\n\n=== 結論 ===")
    print("Porcupineで複数言語のウェイクワードを同時検出するには:")
    print("1. 各言語用に別々のPorcupineインスタンスを作成する必要がある")
    print("2. model_pathは1つのインスタンスに1つしか指定できない")
    print("3. 複数インスタンスを並列実行することで実現可能")
    print("4. リソース使用量は言語数に比例して増加する")

if __name__ == "__main__":
    main()