#!/usr/bin/env python3
"""
複数ウェイクワードパターンのテスト
どのパターンがどれくらい認識されるか統計を取る
"""

import os
import sys
import time
import json
from pathlib import Path
from collections import defaultdict
import pvporcupine
import pvrecorder

class MultiPatternTester:
    def __init__(self, patterns):
        """
        patterns: [(ppn_path, phrase, sensitivity), ...]
        """
        self.patterns = patterns
        self.access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
        if not self.access_key:
            raise ValueError("PICOVOICE_ACCESS_KEY環境変数が設定されていません")
        
        # 統計情報
        self.stats = defaultdict(int)
        self.detection_log = []
        
    def test(self, duration=180):  # 3分間
        """複数パターンのテスト実行"""
        print("複数ウェイクワードパターンテスト")
        print("=" * 70)
        print("登録パターン:")
        for i, (path, phrase, sens) in enumerate(self.patterns):
            print(f"  {i+1}. '{phrase}' (感度: {sens})")
        print(f"\nテスト時間: {duration}秒")
        print("=" * 70)
        
        # 存在チェック
        for path, _, _ in self.patterns:
            if not Path(path).exists():
                print(f"⚠️ ファイルが見つかりません: {path}")
                print("テストをスキップします")
                return
        
        # Porcupine初期化
        print("\n初期化中...")
        keyword_paths = [p[0] for p in self.patterns]
        sensitivities = [p[2] for p in self.patterns]
        
        porcupine = pvporcupine.create(
            access_key=self.access_key,
            keyword_paths=keyword_paths,
            sensitivities=sensitivities
        )
        
        recorder = pvrecorder.PvRecorder(
            frame_length=porcupine.frame_length,
            device_index=-1
        )
        
        print("✓ 準備完了！\n")
        print("🎤 以下のパターンを試してください:")
        print("   - おっけーはうす（言いやすい）")
        print("   - おーけーはうす（丁寧）")
        print("   - OK house（英語風）")
        print("   - 早口や遅口でも試してみてください")
        print("\n終了: Ctrl+C\n")
        
        recorder.start()
        start_time = time.time()
        last_update = time.time()
        
        try:
            while True:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # 時間制限
                if elapsed >= duration:
                    print(f"\n\nテスト完了（{duration}秒）")
                    break
                
                # ステータス更新（5秒ごと）
                if current_time - last_update >= 5:
                    self._print_status(elapsed, duration)
                    last_update = current_time
                
                # 音声処理
                pcm = recorder.read()
                result = porcupine.process(pcm)
                
                if result >= 0:
                    pattern = self.patterns[result]
                    phrase = pattern[1]
                    
                    # 統計更新
                    self.stats[phrase] += 1
                    self.detection_log.append({
                        "time": elapsed,
                        "phrase": phrase,
                        "index": result
                    })
                    
                    # 表示
                    total = sum(self.stats.values())
                    percentage = (self.stats[phrase] / total) * 100
                    
                    print(f"\n✅ 検出 #{total}: '{phrase}'")
                    print(f"   このパターン: {self.stats[phrase]}回 ({percentage:.1f}%)")
                    
                    # 連続検出防止
                    time.sleep(1.5)
                    
        except KeyboardInterrupt:
            print("\n\nテスト中断")
        finally:
            recorder.stop()
            recorder.delete()
            porcupine.delete()
            
        # 結果表示
        self.show_results(time.time() - start_time)
    
    def _print_status(self, elapsed, duration):
        """ステータス表示"""
        remaining = duration - int(elapsed)
        total = sum(self.stats.values())
        
        status = f"\r⏱️ 残り: {remaining:3d}秒 | 総検出: {total}回"
        if total > 0:
            status += " | 内訳: "
            for phrase, count in self.stats.items():
                pct = (count / total) * 100
                status += f"{phrase}:{count}({pct:.0f}%) "
        
        print(status, end='', flush=True)
    
    def show_results(self, total_time):
        """詳細な結果表示"""
        print("\n" + "=" * 70)
        print("📊 テスト結果サマリー")
        print("=" * 70)
        
        total_detections = sum(self.stats.values())
        print(f"テスト時間: {total_time:.1f}秒")
        print(f"総検出回数: {total_detections}回")
        
        if total_detections == 0:
            print("\n⚠️ 検出されませんでした")
            return
        
        print(f"\n検出パターン分析:")
        print("-" * 40)
        
        # 各パターンの統計
        for phrase, count in sorted(self.stats.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_detections) * 100
            print(f"{phrase:20s}: {count:3d}回 ({percentage:5.1f}%)")
        
        # 時系列分析
        print(f"\n時系列分析:")
        print("-" * 40)
        
        # 30秒ごとの検出数
        time_buckets = defaultdict(lambda: defaultdict(int))
        for detection in self.detection_log:
            bucket = int(detection['time'] / 30) * 30
            time_buckets[bucket][detection['phrase']] += 1
        
        for bucket in sorted(time_buckets.keys()):
            print(f"{bucket:3d}-{bucket+30:3d}秒: ", end="")
            for phrase, count in time_buckets[bucket].items():
                print(f"{phrase}:{count} ", end="")
            print()
        
        # 推奨事項
        print(f"\n💡 分析と推奨:")
        print("-" * 40)
        
        # 最も認識されたパターン
        best_pattern = max(self.stats.items(), key=lambda x: x[1])
        print(f"最も認識されやすい: '{best_pattern[0]}' ({best_pattern[1]}回)")
        
        # バランス分析
        if len(self.stats) > 1:
            counts = list(self.stats.values())
            max_count = max(counts)
            min_count = min(counts)
            
            if min_count == 0:
                print("⚠️ 認識されないパターンがあります。感度調整が必要です。")
            elif max_count / min_count > 3:
                print("📊 パターン間の認識率に大きな差があります。")
                print("   → 認識率の低いパターンの感度を上げることを検討してください。")
            else:
                print("✅ 各パターンがバランスよく認識されています。")
        
        # 保存
        self.save_results()
    
    def save_results(self):
        """結果をJSONで保存"""
        result_file = "test_results.json"
        
        data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "patterns": [
                {
                    "phrase": p[1],
                    "sensitivity": p[2],
                    "detections": self.stats.get(p[1], 0)
                }
                for p in self.patterns
            ],
            "detection_log": self.detection_log
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n📁 詳細ログを保存: {result_file}")

def main():
    # テストパターン定義
    # 実際のファイルパスに置き換えてください
    patterns = [
        ("wake_words/おっけーはうす.ppn", "おっけーはうす", 0.5),
        ("wake_words/おーけーはうす.ppn", "おーけーはうす", 0.4),
        # 必要に応じて追加
        # ("wake_words/ねえはうす.ppn", "ねえはうす", 0.3),
    ]
    
    # ダミーパターン（実際のファイルがない場合のテスト用）
    print("注意: 実際のテストには.ppnファイルが必要です")
    print("Picovoice Consoleで作成してください\n")
    
    try:
        tester = MultiPatternTester(patterns)
        tester.test(duration=180)  # 3分間
    except Exception as e:
        print(f"エラー: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())