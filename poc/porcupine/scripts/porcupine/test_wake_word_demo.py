#!/usr/bin/env python3
"""
ウェイクワード検出デモ - インタラクティブ版
"""

import os
import sys
import time
import threading
import pvporcupine
import pvrecorder

class WakeWordDemo:
    def __init__(self):
        self.access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
        if not self.access_key:
            raise ValueError("PICOVOICE_ACCESS_KEY環境変数が設定されていません")
        
        self.porcupine = None
        self.recorder = None
        self.is_running = False
        
    def initialize(self):
        """初期化"""
        print("初期化中...")
        
        # 利用可能なキーワード
        keywords = ['picovoice', 'computer', 'jarvis', 'alexa']
        print(f"検出するウェイクワード: {', '.join(keywords)}")
        
        # Porcupine作成
        self.porcupine = pvporcupine.create(
            access_key=self.access_key,
            keywords=keywords
        )
        
        # レコーダー作成
        self.recorder = pvrecorder.PvRecorder(
            frame_length=self.porcupine.frame_length,
            device_index=-1
        )
        
        print("✓ 初期化完了\n")
        
    def run(self):
        """メインループ"""
        self.is_running = True
        keywords = ['picovoice', 'computer', 'jarvis', 'alexa']
        
        print("=" * 60)
        print("🎤 ウェイクワード検出デモ")
        print("=" * 60)
        print("以下のワードを話してください:")
        for i, word in enumerate(keywords):
            print(f"  {i+1}. '{word}'")
        print("\n終了: Ctrl+C")
        print("=" * 60)
        print("\n待機中...\n")
        
        self.recorder.start()
        
        try:
            detection_count = 0
            while self.is_running:
                pcm = self.recorder.read()
                keyword_index = self.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    detection_count += 1
                    detected_word = keywords[keyword_index]
                    
                    print(f"\n{'🎯' * 15}")
                    print(f"検出！ #{detection_count}")
                    print(f"ワード: '{detected_word}'")
                    print(f"時刻: {time.strftime('%H:%M:%S')}")
                    print(f"{'🎯' * 15}\n")
                    
                    # 効果音的な表示
                    for i in range(3):
                        print(f"  {'✨' * (i+1)}", end='', flush=True)
                        time.sleep(0.2)
                    print("\n\n待機中...\n")
                    
                    # 連続検出防止
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n\n終了中...")
        finally:
            self.cleanup()
            
    def cleanup(self):
        """クリーンアップ"""
        self.is_running = False
        if self.recorder:
            self.recorder.stop()
            self.recorder.delete()
        if self.porcupine:
            self.porcupine.delete()
        print("✓ クリーンアップ完了")

def main():
    """メイン関数"""
    try:
        demo = WakeWordDemo()
        demo.initialize()
        demo.run()
    except Exception as e:
        print(f"エラー: {e}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())