#!/usr/bin/env python3
"""シンプルなウェイクワード + Whisper連続記録"""

import signal
import sys
import time
import threading
import numpy as np
from datetime import datetime
from loguru import logger

from config import Config
from wake_detector_auto import create_wake_detector
from audio_recorder import MultiLevelAudioRecorder
from simple_whisper_processor import SimpleWhisperProcessor
from database import VoiceRequestDB

class SimpleVoiceAssistant:
    def __init__(self):
        # 設定の検証
        Config.validate()
        
        # ログを簡潔に
        logger.remove()
        logger.add(sys.stderr, level="WARNING")
        
        # コンポーネント初期化
        self.wake_detector = create_wake_detector()
        self.audio_recorder = MultiLevelAudioRecorder()
        self.whisper_processor = SimpleWhisperProcessor()
        self.database = VoiceRequestDB(Config.DATABASE_PATH)
        
        # 状態管理
        self.is_running = False
        self.current_wake_word = None
    
    def initialize(self):
        """全コンポーネントを初期化"""
        print("🚀 Voice Assistant起動中...")
        
        # ウェイクワード検出器
        if not self.wake_detector.initialize():
            print("❌ ウェイクワード検出器の初期化に失敗")
            return False
        
        # コールバック設定
        self.wake_detector.set_detection_callback(self.on_wake_word_detected)
        
        # AudioRecorderの参照を渡す
        if hasattr(self.wake_detector, 'set_audio_recorder'):
            self.wake_detector.set_audio_recorder(self.audio_recorder)
        
        # 音声ストリーム開始
        if not self.audio_recorder.start_stream():
            print("❌ 音声ストリームの開始に失敗")
            return False
        
        # 使用可能なウェイクワードを表示
        print("\n📢 使用可能なウェイクワード:")
        if hasattr(self.wake_detector, 'get_all_wake_words'):
            wake_words = self.wake_detector.get_all_wake_words()
        else:
            wake_words = Config.get_wake_words()
        
        for ww in wake_words:
            print(f"  • {ww['name']}")
        
        print("\n👂 聞き取り準備完了。話しかけてください...")
        print("(Ctrl+Cで終了)\n")
        
        return True
    
    def on_wake_word_detected(self, wake_word_info):
        """ウェイクワード検出時の処理"""
        self.current_wake_word = wake_word_info
        
        # 簡潔な出力
        print(f"\n🎯 [{wake_word_info['name']}] 検出 ({wake_word_info['timestamp_start']:.1f}s - {wake_word_info['timestamp_end']:.1f}s)")
        
        # 音声録音開始
        self.audio_recorder.start_recording()
        
        # 音声処理を別スレッドで
        threading.Thread(target=self.process_voice_input, daemon=True).start()
    
    def process_voice_input(self):
        """音声入力を処理（シンプル版）"""
        start_time = time.time()
        wake_word_end = self.current_wake_word.get('timestamp_end', 0)
        
        # 無音検出まで録音
        while self.is_running:
            current_timestamp = self.audio_recorder.get_current_timestamp()
            
            # ウェイクワード後3秒は無音検出をスキップ
            if current_timestamp > wake_word_end + Config.INITIAL_SILENCE_IGNORE:
                audio_chunk = self.audio_recorder.read_chunk()
                if audio_chunk is not None and self.audio_recorder.detect_silence(audio_chunk):
                    break
            else:
                time.sleep(0.1)
            
            # 最大30秒で打ち切り
            if time.time() - start_time > 30:
                break
        
        # 録音停止
        self.audio_recorder.stop_recording()
        
        # 全音声データを取得
        audio_chunk = self.audio_recorder.get_ultra_chunk()
        if not audio_chunk or audio_chunk.duration < 0.5:
            print("  ⏭️  音声が短すぎます")
            return
        
        print(f"  🎙️  録音完了 ({audio_chunk.duration:.1f}秒)")
        
        # Whisperで文字起こし
        result = self.whisper_processor.transcribe(
            audio_chunk.audio,
            timestamp_start=audio_chunk.start_time,
            wake_word_end_time=wake_word_end
        )
        
        if result and result.text:
            # 結果表示
            print(f"  📝 「{result.text}」")
            print(f"  ⏱️  処理時間: {result.processing_time_ms}ms")
            
            # データベースに保存
            db_data = {
                'wake_word': self.current_wake_word['name'],
                'wake_word_type': self.current_wake_word['type'],
                'audio_duration_seconds': result.duration,
                'transcribed_text': result.text,
                'transcription_level': 'full',
                'language': Config.WHISPER_LANGUAGE,
                'processing_time_ms': result.processing_time_ms,
                'timestamp_start': result.timestamp_start,
                'timestamp_end': result.timestamp_end
            }
            self.database.insert_request(db_data)
            
            # セグメント情報があれば表示（デバッグ用）
            if hasattr(result, 'segments') and result.segments:
                print(f"  🔍 セグメント数: {len(result.segments)}")
        else:
            print("  ❓ 認識できませんでした")
    
    def run(self):
        """メインループ"""
        self.is_running = True
        
        try:
            while self.is_running:
                audio_chunk = self.audio_recorder.read_chunk()
                
                if audio_chunk is None:
                    time.sleep(0.01)
                    continue
                
                # ウェイクワード検出
                frame_length = self.wake_detector.get_frame_length()
                if len(audio_chunk) == frame_length:
                    self.wake_detector.process_audio(audio_chunk)
                
        except KeyboardInterrupt:
            pass
        
        self.stop()
    
    def stop(self):
        """終了処理"""
        print("\n\n👋 終了中...")
        self.is_running = False
        
        # クリーンアップ
        self.wake_detector.cleanup()
        self.audio_recorder.cleanup()
        self.database.close()
        
        print("✅ 終了しました")

def main():
    """メイン関数"""
    assistant = SimpleVoiceAssistant()
    
    if not assistant.initialize():
        return 1
    
    assistant.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())