#!/usr/bin/env python3
"""
リソースモニター付きウェイクワード検出
CPU使用率、メモリ使用量を表示しながら動作
"""

import os
import sys
import time
import threading
import psutil
import pvporcupine
import pvrecorder
from datetime import datetime

class ResourceMonitor:
    def __init__(self):
        self.process = psutil.Process()
        self.running = False
        self.cpu_percent = 0
        self.memory_mb = 0
        
    def start(self):
        """モニタリング開始"""
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        """モニタリング停止"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join()
            
    def _monitor_loop(self):
        """モニタリングループ"""
        while self.running:
            try:
                # CPU使用率（1秒間の平均）
                self.cpu_percent = self.process.cpu_percent(interval=1)
                # メモリ使用量（MB）
                self.memory_mb = self.process.memory_info().rss / 1024 / 1024
            except:
                pass

class WakeWordMonitor:
    def __init__(self, duration_minutes=3):
        self.access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
        if not self.access_key:
            raise ValueError("PICOVOICE_ACCESS_KEY環境変数が設定されていません")
        
        self.duration = duration_minutes * 60  # 秒に変換
        self.porcupine = None
        self.recorder = None
        self.resource_monitor = ResourceMonitor()
        self.detection_count = 0
        
    def initialize(self):
        """初期化"""
        print("初期化中...")
        
        # キーワード設定
        self.keywords = ['picovoice', 'computer', 'jarvis', 'alexa']
        
        # Porcupine初期化
        self.porcupine = pvporcupine.create(
            access_key=self.access_key,
            keywords=self.keywords
        )
        
        # レコーダー初期化
        self.recorder = pvrecorder.PvRecorder(
            frame_length=self.porcupine.frame_length,
            device_index=-1
        )
        
        print("✓ 初期化完了\n")
        
    def run(self):
        """メインループ"""
        print("=" * 70)
        print(f"🎤 リソースモニター付きウェイクワード検出 ({self.duration//60}分間)")
        print("=" * 70)
        print("検出対象:")
        for word in self.keywords:
            print(f"  • {word}")
        print("\n終了: Ctrl+C")
        print("=" * 70)
        
        # リソースモニター開始
        self.resource_monitor.start()
        
        # 録音開始
        self.recorder.start()
        start_time = time.time()
        last_update = 0
        
        try:
            while True:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # 終了条件
                if elapsed >= self.duration:
                    print(f"\n\n⏱️ {self.duration//60}分間のテスト完了")
                    break
                
                # ステータス更新（1秒ごと）
                if current_time - last_update >= 1:
                    self._print_status(elapsed)
                    last_update = current_time
                
                # ウェイクワード検出
                pcm = self.recorder.read()
                keyword_index = self.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    self.detection_count += 1
                    detected_word = self.keywords[keyword_index]
                    
                    # 検出表示
                    print(f"\n\n{'🎯' * 20}")
                    print(f"検出 #{self.detection_count}: '{detected_word}' @ {datetime.now().strftime('%H:%M:%S')}")
                    print(f"{'🎯' * 20}\n")
                    
                    # 連続検出防止
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n\nユーザーによる中断")
        finally:
            self.cleanup()
            self.show_summary(time.time() - start_time)
            
    def _print_status(self, elapsed):
        """ステータス行の更新"""
        remaining = self.duration - int(elapsed)
        minutes = remaining // 60
        seconds = remaining % 60
        
        process_cpu = self.resource_monitor.cpu_percent
        system_cpu = psutil.cpu_percent(interval=0.1)
        mem = self.resource_monitor.memory_mb
        
        status = (f"\r⏱️ 残り: {minutes:02d}:{seconds:02d} | "
                 f"プロセスCPU: {process_cpu:5.1f}% | "
                 f"システムCPU: {system_cpu:5.1f}% | "
                 f"メモリ: {mem:6.1f}MB | "
                 f"検出: {self.detection_count}回")
        
        print(status, end='', flush=True)
        
    def show_summary(self, total_time):
        """サマリー表示"""
        print("\n" + "=" * 70)
        print("📊 テストサマリー")
        print("=" * 70)
        print(f"実行時間: {total_time:.1f}秒")
        print(f"検出回数: {self.detection_count}回")
        if self.detection_count > 0:
            print(f"平均検出間隔: {total_time/self.detection_count:.1f}秒")
        
        print(f"\n最終リソース使用状況:")
        print(f"  プロセスCPU使用率: {self.resource_monitor.cpu_percent:.1f}%")
        print(f"  プロセスメモリ使用量: {self.resource_monitor.memory_mb:.1f}MB")
        
        # システム全体の情報
        print(f"\nシステム全体:")
        print(f"  システムCPU使用率: {psutil.cpu_percent(interval=1):.1f}%")
        print(f"  システムメモリ使用率: {psutil.virtual_memory().percent:.1f}%")
        
        print(f"\nPorcupineの効率性:")
        print(f"  → ウェイクワード検出にかかるCPU: わずか {self.resource_monitor.cpu_percent:.1f}%")
        print(f"  → メモリフットプリント: {self.resource_monitor.memory_mb:.1f}MB のみ")
        
    def cleanup(self):
        """クリーンアップ"""
        print("\nクリーンアップ中...")
        
        self.resource_monitor.stop()
        
        if self.recorder:
            self.recorder.stop()
            self.recorder.delete()
            
        if self.porcupine:
            self.porcupine.delete()
            
        print("✓ クリーンアップ完了")

def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='リソースモニター付きウェイクワード検出')
    parser.add_argument('--duration', type=int, default=3, 
                       help='テスト時間（分）デフォルト: 3分')
    args = parser.parse_args()
    
    try:
        monitor = WakeWordMonitor(duration_minutes=args.duration)
        monitor.initialize()
        monitor.run()
    except Exception as e:
        print(f"エラー: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())