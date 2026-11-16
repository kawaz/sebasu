#!/usr/bin/env python3
"""スマート連続ウェイクワード対応版"""

import json
import sys
import time
import threading
from collections import deque
from typing import List, Dict, Any, Optional
import numpy as np

from config import Config
from wake_detector_auto import create_wake_detector
from audio_recorder import MultiLevelAudioRecorder
from simple_whisper_processor import SimpleWhisperProcessor
from database import VoiceRequestDB

def log_json(event_type, data):
    """JSON形式でログ出力（タイムスタンプ付き）"""
    log_entry = {
        "timestamp": time.time(),  # UNIX epoch time
        "event": event_type,
        "data": data
    }
    print(json.dumps(log_entry, ensure_ascii=False))
    sys.stdout.flush()

class SmartContinuousVoiceAssistant:
    def __init__(self):
        Config.validate()
        
        # コンポーネント初期化
        self.wake_detector = create_wake_detector()
        self.audio_recorder = MultiLevelAudioRecorder()
        self.whisper_processor = SimpleWhisperProcessor()
        self.database = VoiceRequestDB(Config.DATABASE_PATH)
        
        # 状態管理
        self.is_running = False
        
        # 連続録音バッファ（常に最新30秒を保持）
        self.continuous_buffer = deque(maxlen=30 * Config.SAMPLE_RATE)
        self.buffer_lock = threading.Lock()
        
        # ウェイクワード検出履歴
        self.wake_word_events = deque(maxlen=100)
        
        # 処理スレッド
        self.processor_thread = None
    
    def initialize(self):
        """初期化"""
        log_json("system", {"status": "initializing"})
        
        if not self.wake_detector.initialize():
            return False
        
        self.wake_detector.set_detection_callback(self.on_wake_word_detected)
        
        if hasattr(self.wake_detector, 'set_audio_recorder'):
            self.wake_detector.set_audio_recorder(self.audio_recorder)
        
        if not self.audio_recorder.start_stream():
            return False
        
        wake_words = []
        if hasattr(self.wake_detector, 'get_all_wake_words'):
            wake_words = [w['name'] for w in self.wake_detector.get_all_wake_words()]
        
        log_json("system", {
            "status": "ready",
            "wake_words": wake_words,
            "sample_rate": Config.SAMPLE_RATE,
            "strategy": "continuous_buffer_with_smart_segmentation"
        })
        
        # 処理スレッド開始
        self.processor_thread = threading.Thread(target=self.process_wake_words, daemon=True)
        self.processor_thread.start()
        
        return True
    
    def on_wake_word_detected(self, wake_word_info):
        """ウェイクワード検出"""
        detection_time = time.time()
        stream_timestamp = self.audio_recorder.get_current_timestamp()
        
        # イベント記録
        event = {
            "wake_word": wake_word_info['name'],
            "timestamp_start": wake_word_info.get('timestamp_start', 0),
            "timestamp_end": wake_word_info.get('timestamp_end', 0),
            "detection_time": detection_time,
            "stream_timestamp": stream_timestamp,
            "processed": False
        }
        
        self.wake_word_events.append(event)
        
        log_json("wake_word_detected", {
            "wake_word": event['wake_word'],
            "timestamp_start": event['timestamp_start'],
            "timestamp_end": event['timestamp_end'],
            "stream_timestamp": stream_timestamp,
            "pending_events": len([e for e in self.wake_word_events if not e['processed']])
        })
    
    def process_wake_words(self):
        """ウェイクワードイベントを処理"""
        while self.is_running:
            # 未処理のイベントを確認
            unprocessed = [e for e in self.wake_word_events if not e['processed']]
            
            if unprocessed:
                # 最も古い未処理イベントを処理
                event = unprocessed[0]
                
                # 適切な待機時間（ウェイクワード後の発話を待つ）
                time_since_detection = time.time() - event['detection_time']
                if time_since_detection < 1.0:  # 1秒待つ
                    time.sleep(0.1)
                    continue
                
                # このイベントを処理
                self.process_single_command(event)
                event['processed'] = True
            
            time.sleep(0.1)
    
    def process_single_command(self, wake_event):
        """単一のコマンドを処理"""
        session_id = f"{int(wake_event['detection_time'] * 1000)}"
        wake_word_end = wake_event['timestamp_end']
        
        log_json("session_start", {
            "session_id": session_id,
            "wake_word": wake_event['wake_word'],
            "wake_word_end_timestamp": wake_word_end
        })
        
        # 次のウェイクワードまたは無音までの音声を取得
        audio_segment = self.extract_command_audio(wake_event)
        
        if audio_segment is None or len(audio_segment) < Config.SAMPLE_RATE * 0.5:
            log_json("session_end", {
                "session_id": session_id,
                "status": "too_short"
            })
            return
        
        # 文字起こし
        duration = len(audio_segment) / Config.SAMPLE_RATE
        result = self.whisper_processor.transcribe(
            audio_segment,
            timestamp_start=wake_word_end,
            wake_word_end_time=wake_word_end
        )
        
        if result and result.text:
            # 他のウェイクワードが含まれているか確認
            overlapping_wake_words = []
            for other_event in self.wake_word_events:
                if other_event != wake_event:
                    if wake_word_end <= other_event['timestamp_start'] <= wake_word_end + duration:
                        overlapping_wake_words.append({
                            "wake_word": other_event['wake_word'],
                            "timestamp_start": other_event['timestamp_start'],
                            "timestamp_end": other_event['timestamp_end'],
                            "position_in_text": self.estimate_position_in_text(
                                result.segments,
                                other_event['timestamp_start'] - wake_word_end
                            )
                        })
            
            log_json("recognition_result", {
                "session_id": session_id,
                "text": result.text,
                "timestamp_start": result.timestamp_start,
                "timestamp_end": result.timestamp_end,
                "duration": result.duration,
                "processing_time_ms": result.processing_time_ms,
                "overlapping_wake_words": overlapping_wake_words,
                "segment_count": len(result.segments) if result.segments else 0
            })
            
            # データベース保存
            db_data = {
                'wake_word': wake_event['wake_word'],
                'wake_word_type': 'custom',
                'audio_duration_seconds': result.duration,
                'transcribed_text': result.text,
                'transcription_level': 'command',
                'language': Config.WHISPER_LANGUAGE,
                'processing_time_ms': result.processing_time_ms,
                'timestamp_start': result.timestamp_start,
                'timestamp_end': result.timestamp_end,
                'session_id': session_id
            }
            self.database.insert_request(db_data)
        
        log_json("session_end", {
            "session_id": session_id,
            "status": "completed"
        })
    
    def extract_command_audio(self, wake_event):
        """コマンドの音声を抽出"""
        with self.buffer_lock:
            buffer_copy = np.array(self.continuous_buffer)
        
        if len(buffer_copy) == 0:
            return None
        
        # バッファ内の位置を計算
        current_stream_time = self.audio_recorder.get_current_timestamp()
        buffer_duration = len(buffer_copy) / Config.SAMPLE_RATE
        buffer_start_time = current_stream_time - buffer_duration
        
        # ウェイクワード終了位置
        wake_end_pos = int((wake_event['timestamp_end'] - buffer_start_time) * Config.SAMPLE_RATE)
        
        if wake_end_pos < 0 or wake_end_pos >= len(buffer_copy):
            return None
        
        # 次のウェイクワードまたは無音を探す
        next_wake_events = [
            e for e in self.wake_word_events 
            if e['timestamp_start'] > wake_event['timestamp_end'] and e != wake_event
        ]
        
        if next_wake_events:
            # 次のウェイクワードの開始位置
            next_wake = min(next_wake_events, key=lambda e: e['timestamp_start'])
            end_pos = int((next_wake['timestamp_start'] - buffer_start_time) * Config.SAMPLE_RATE)
        else:
            # 無音を探す（簡易版）
            search_start = wake_end_pos + int(Config.INITIAL_SILENCE_IGNORE * Config.SAMPLE_RATE)
            end_pos = self.find_silence_end(buffer_copy, search_start)
        
        if end_pos <= wake_end_pos:
            return None
        
        return buffer_copy[wake_end_pos:end_pos]
    
    def find_silence_end(self, audio_data, start_pos):
        """無音位置を探す"""
        chunk_size = int(0.1 * Config.SAMPLE_RATE)  # 100ms chunks
        silence_chunks_needed = int(Config.SILENCE_DURATION / 0.1)
        silence_count = 0
        
        for i in range(start_pos, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            if len(chunk) == 0:
                break
            
            rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))
            if rms < Config.SILENCE_THRESHOLD:
                silence_count += 1
                if silence_count >= silence_chunks_needed:
                    return i
            else:
                silence_count = 0
        
        return len(audio_data)
    
    def estimate_position_in_text(self, segments, relative_timestamp):
        """セグメント情報から文中の位置を推定"""
        if not segments:
            return "unknown"
        
        for i, segment in enumerate(segments):
            if segment['start'] <= relative_timestamp <= segment['end']:
                return f"segment_{i}"
        
        return "between_segments"
    
    def run(self):
        """メインループ"""
        self.is_running = True
        
        try:
            while self.is_running:
                audio_chunk = self.audio_recorder.read_chunk()
                
                if audio_chunk is None:
                    time.sleep(0.01)
                    continue
                
                # 連続バッファに追加
                with self.buffer_lock:
                    self.continuous_buffer.extend(audio_chunk)
                
                # ウェイクワード検出
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
        
        if self.processor_thread:
            self.processor_thread.join(timeout=2)
        
        self.wake_detector.cleanup()
        self.audio_recorder.cleanup()
        self.database.close()
        
        log_json("system", {"status": "stopped"})

def main():
    assistant = SmartContinuousVoiceAssistant()
    
    if not assistant.initialize():
        return 1
    
    assistant.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())