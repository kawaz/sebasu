#!/usr/bin/env python3
"""マルチレベル音声認識 with JSON出力"""

import json
import signal
import sys
import time
import threading
import numpy as np
from datetime import datetime
from collections import deque

from config import Config
from wake_detector_auto import create_wake_detector
from audio_recorder import MultiLevelAudioRecorder
from simple_whisper_processor import SimpleWhisperProcessor
from database import VoiceRequestDB

def log_json(event_type, data):
    """JSON形式でログ出力"""
    log_entry = {
        "timestamp": time.time(),
        "event": event_type,
        "data": data
    }
    print(json.dumps(log_entry, ensure_ascii=False))
    sys.stdout.flush()

class MultiLevelVoiceAssistant:
    def __init__(self):
        Config.validate()
        
        # コンポーネント初期化
        self.wake_detector = create_wake_detector()
        self.audio_recorder = MultiLevelAudioRecorder()
        self.whisper_processor = SimpleWhisperProcessor()
        self.database = VoiceRequestDB(Config.DATABASE_PATH)
        
        # 状態管理
        self.is_running = False
        self.is_processing = False
        self.current_session = None
        
        # 認識結果の履歴（レベル別）
        self.recognition_history = {}
    
    def initialize(self):
        """初期化"""
        log_json("system", {"status": "initializing"})
        
        if not self.wake_detector.initialize():
            log_json("error", {"component": "wake_detector", "message": "initialization failed"})
            return False
        
        self.wake_detector.set_detection_callback(self.on_wake_word_detected)
        
        if hasattr(self.wake_detector, 'set_audio_recorder'):
            self.wake_detector.set_audio_recorder(self.audio_recorder)
        
        if not self.audio_recorder.start_stream():
            log_json("error", {"component": "audio_recorder", "message": "stream start failed"})
            return False
        
        # 使用可能なウェイクワード
        wake_words = []
        if hasattr(self.wake_detector, 'get_all_wake_words'):
            wake_words = [w['name'] for w in self.wake_detector.get_all_wake_words()]
        else:
            wake_words = [w['name'] for w in Config.get_wake_words()]
        
        log_json("system", {
            "status": "ready",
            "wake_words": wake_words,
            "sample_rate": Config.SAMPLE_RATE,
            "levels": list(Config.BUFFER_LEVELS.keys())
        })
        
        return True
    
    def on_wake_word_detected(self, wake_word_info):
        """ウェイクワード検出"""
        if self.is_processing:
            return
        
        self.is_processing = True
        self.current_session = {
            "session_id": f"{int(time.time() * 1000)}",
            "wake_word": wake_word_info
        }
        self.recognition_history = {}
        
        log_json("wake_word_detected", {
            "session_id": self.current_session["session_id"],
            "wake_word": wake_word_info['name'],
            "timestamp_start": wake_word_info.get('timestamp_start', 0),
            "timestamp_end": wake_word_info.get('timestamp_end', 0)
        })
        
        # 音声録音開始
        self.audio_recorder.start_recording()
        
        # マルチレベル処理を開始
        threading.Thread(target=self.process_multilevel, daemon=True).start()
    
    def process_multilevel(self):
        """マルチレベル音声処理"""
        session_id = self.current_session["session_id"]
        wake_word_end = self.current_session["wake_word"].get('timestamp_end', 0)
        
        # 処理済みレベルの追跡
        processed_levels = set()
        last_process_time = {}
        
        # セッション開始
        log_json("session_start", {
            "session_id": session_id,
            "wake_word_end_timestamp": wake_word_end
        })
        
        while self.is_processing and self.is_running:
            current_time = time.time()
            current_timestamp = self.audio_recorder.get_current_timestamp()
            
            # 各レベルのチャンクを確認
            chunks = self.audio_recorder.get_audio_chunks()
            
            # デバッグ: チャンク数を記録
            if chunks:
                log_json("debug_chunks", {
                    "session_id": session_id,
                    "chunk_count": len(chunks),
                    "levels": [c.level for c in chunks],
                    "durations": [c.duration for c in chunks]
                })
            
            for chunk in chunks:
                level = chunk.level
                level_config = Config.BUFFER_LEVELS[level]
                
                # 処理間隔を確認（オーバーラップを考慮）
                min_interval = level_config['duration'] - level_config.get('overlap', 1.0)
                if level in last_process_time:
                    if current_time - last_process_time[level] < min_interval:
                        continue
                
                # 前のレベルの結果を取得（コンテキストとして使用）
                previous_text = ""
                if level == 'medium' and 'short' in self.recognition_history:
                    previous_text = self.recognition_history['short']['text']
                elif level == 'long' and 'medium' in self.recognition_history:
                    previous_text = self.recognition_history['medium']['text']
                
                # Whisper処理
                log_json("recognition_start", {
                    "session_id": session_id,
                    "level": level,
                    "duration": chunk.duration,
                    "timestamp": current_timestamp,
                    "has_context": bool(previous_text)
                })
                
                # ウェイクワード部分を除外
                audio_to_process = chunk.audio
                process_start_time = chunk.timestamp - chunk.duration
                
                # デバッグ情報
                log_json("debug_wake_word_skip", {
                    "session_id": session_id,
                    "level": level,
                    "wake_word_end": wake_word_end,
                    "process_start_time": process_start_time,
                    "chunk_timestamp": chunk.timestamp,
                    "chunk_duration": chunk.duration
                })
                
                if wake_word_end > process_start_time:
                    # ウェイクワード終了後の音声のみを使用
                    skip_duration = wake_word_end - process_start_time
                    skip_samples = int(skip_duration * Config.SAMPLE_RATE)
                    if skip_samples < len(audio_to_process):
                        audio_to_process = audio_to_process[skip_samples:]
                        process_start_time = wake_word_end
                        log_json("debug_skip_applied", {
                            "session_id": session_id,
                            "level": level,
                            "skip_duration": skip_duration,
                            "skip_samples": skip_samples,
                            "original_length": len(chunk.audio),
                            "processed_length": len(audio_to_process)
                        })
                
                result = self.whisper_processor.transcribe(
                    audio_to_process,
                    timestamp_start=process_start_time,
                    wake_word_end_time=wake_word_end
                )
                
                if result and result.text:
                    # 認識結果を保存
                    self.recognition_history[level] = {
                        "text": result.text,
                        "timestamp_start": result.timestamp_start,
                        "timestamp_end": result.timestamp_end,
                        "segments": result.segments
                    }
                    
                    # 結果をログ出力
                    log_json("recognition_result", {
                        "session_id": session_id,
                        "level": level,
                        "text": result.text,
                        "timestamp_start": result.timestamp_start,
                        "timestamp_end": result.timestamp_end,
                        "duration": result.duration,
                        "processing_time_ms": result.processing_time_ms,
                        "segment_count": len(result.segments) if result.segments else 0
                    })
                
                last_process_time[level] = current_time
                processed_levels.add(level)
            
            # 無音検出（ウェイクワード後3秒は無視）
            if current_timestamp > wake_word_end + Config.INITIAL_SILENCE_IGNORE:
                audio_chunk = self.audio_recorder.read_chunk()
                if audio_chunk is not None and self.audio_recorder.detect_silence(audio_chunk):
                    log_json("silence_detected", {
                        "session_id": session_id,
                        "timestamp": current_timestamp
                    })
                    break
            
            # 最大録音時間
            if self.audio_recorder.get_recording_duration() > 30:
                log_json("max_duration_reached", {
                    "session_id": session_id,
                    "duration": self.audio_recorder.get_recording_duration()
                })
                break
            
            time.sleep(0.1)
        
        # 録音停止
        self.audio_recorder.stop_recording()
        
        # 最終的な ultra レベル処理
        ultra_chunk = self.audio_recorder.get_ultra_chunk()
        if ultra_chunk and ultra_chunk.duration > 0.5:
            log_json("recognition_start", {
                "session_id": session_id,
                "level": "ultra",
                "duration": ultra_chunk.duration,
                "timestamp": ultra_chunk.end_time
            })
            
            # ウェイクワード部分を除外
            audio_to_process = ultra_chunk.audio
            process_start_time = ultra_chunk.timestamp - ultra_chunk.duration
            
            if wake_word_end > process_start_time:
                skip_duration = wake_word_end - process_start_time
                skip_samples = int(skip_duration * Config.SAMPLE_RATE)
                if skip_samples < len(audio_to_process):
                    audio_to_process = audio_to_process[skip_samples:]
                    process_start_time = wake_word_end
            
            result = self.whisper_processor.transcribe(
                audio_to_process,
                timestamp_start=process_start_time,
                wake_word_end_time=wake_word_end
            )
            
            if result and result.text:
                log_json("recognition_result", {
                    "session_id": session_id,
                    "level": "ultra",
                    "text": result.text,
                    "timestamp_start": result.timestamp_start,
                    "timestamp_end": result.timestamp_end,
                    "duration": result.duration,
                    "processing_time_ms": result.processing_time_ms,
                    "segment_count": len(result.segments) if result.segments else 0
                })
                
                # データベースに保存
                db_data = {
                    'wake_word': self.current_session["wake_word"]['name'],
                    'wake_word_type': self.current_session["wake_word"]['type'],
                    'audio_duration_seconds': result.duration,
                    'transcribed_text': result.text,
                    'transcription_level': 'ultra',
                    'language': Config.WHISPER_LANGUAGE,
                    'processing_time_ms': result.processing_time_ms,
                    'timestamp_start': result.timestamp_start,
                    'timestamp_end': result.timestamp_end,
                    'session_id': session_id
                }
                request_id = self.database.insert_request(db_data)
                
                log_json("database_saved", {
                    "session_id": session_id,
                    "request_id": request_id
                })
        
        # セッション終了
        log_json("session_end", {
            "session_id": session_id,
            "levels_processed": list(processed_levels)
        })
        
        self.is_processing = False
    
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
                if not self.is_processing:
                    frame_length = self.wake_detector.get_frame_length()
                    if len(audio_chunk) == frame_length:
                        self.wake_detector.process_audio(audio_chunk)
                
        except KeyboardInterrupt:
            pass
        
        self.stop()
    
    def stop(self):
        """終了処理"""
        log_json("system", {"status": "shutting_down"})
        self.is_running = False
        
        self.wake_detector.cleanup()
        self.audio_recorder.cleanup()
        self.database.close()
        
        log_json("system", {"status": "stopped"})

def main():
    assistant = MultiLevelVoiceAssistant()
    
    if not assistant.initialize():
        return 1
    
    assistant.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())