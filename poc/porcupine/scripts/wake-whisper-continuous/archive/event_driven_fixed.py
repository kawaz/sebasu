#!/usr/bin/env python3
"""イベント駆動型音声認識システム（修正版）"""

import json
import sys
import time
import threading
import queue
from collections import deque
from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np

from config import Config
from wake_detector_auto import create_wake_detector
from audio_recorder import MultiLevelAudioRecorder
from simple_whisper_processor import SimpleWhisperProcessor
from database import VoiceRequestDB

@dataclass
class AudioEvent:
    """音声イベント"""
    timestamp: float
    stream_position: float
    event_type: str
    start: float
    end: float
    metadata: Dict[str, Any]

def log_json(event_type, data):
    """JSON形式でログ出力"""
    log_entry = {
        "timestamp": time.time(),
        "event": event_type,
        "data": data
    }
    print(json.dumps(log_entry, ensure_ascii=False))
    sys.stdout.flush()

class EventDrivenVoiceAssistant:
    def __init__(self):
        Config.validate()
        
        # コンポーネント
        self.wake_detector = create_wake_detector()
        self.audio_recorder = MultiLevelAudioRecorder()
        self.whisper_processor = SimpleWhisperProcessor()
        self.database = VoiceRequestDB(Config.DATABASE_PATH)
        
        # 共有リングバッファ（5分間）
        self.buffer_duration = 300
        self.audio_buffer = deque(maxlen=self.buffer_duration * Config.SAMPLE_RATE)
        self.buffer_lock = threading.Lock()
        self.total_samples = 0
        
        # イベントキュー
        self.event_queue = queue.Queue()
        
        # 状態管理
        self.is_running = True  # 初期値をTrueに
        self.active_sessions = {}
    
    def initialize(self):
        """初期化"""
        log_json("system", {"status": "initializing"})
        
        # ウェイクワード検出器
        if not self.wake_detector.initialize():
            return False
        
        self.wake_detector.set_detection_callback(self.on_wake_word_detected)
        
        # AudioRecorderの参照を設定
        if hasattr(self.wake_detector, 'set_audio_recorder'):
            self.wake_detector.set_audio_recorder(self.audio_recorder)
        
        # 音声ストリーム開始
        if not self.audio_recorder.start_stream():
            return False
        
        # ワーカースレッド開始（シンプルに）
        threading.Thread(target=self.audio_capture_worker, daemon=True).start()
        threading.Thread(target=self.event_processor_worker, daemon=True).start()
        
        log_json("system", {
            "status": "ready",
            "buffer_duration_seconds": self.buffer_duration
        })
        
        return True
    
    def get_stream_position(self) -> float:
        """現在のストリーム位置を取得（秒）"""
        return self.total_samples / Config.SAMPLE_RATE
    
    def audio_capture_worker(self):
        """音声キャプチャワーカー"""
        log_json("worker", {"name": "audio_capture", "status": "started"})
        
        frame_length = self.wake_detector.get_frame_length()
        log_json("debug_porcupine", {
            "frame_length": frame_length,
            "chunk_size": Config.CHUNK_SIZE,
            "sample_rate": self.wake_detector.get_sample_rate() if hasattr(self.wake_detector, 'get_sample_rate') else Config.SAMPLE_RATE
        })
        
        chunks_processed = 0
        audio_accumulator = np.array([], dtype=np.int16)
        
        while self.is_running:
            try:
                # 音声読み取り
                audio_chunk = self.audio_recorder.read_chunk()
                
                if audio_chunk is None:
                    time.sleep(0.01)
                    continue
                
                # バッファに追加
                with self.buffer_lock:
                    self.audio_buffer.extend(audio_chunk)
                    self.total_samples += len(audio_chunk)
                
                chunks_processed += 1
                
                # 定期的な状態出力（1秒ごと）
                if chunks_processed % (Config.SAMPLE_RATE // Config.CHUNK_SIZE) == 0:
                    log_json("audio_stats", {
                        "chunks_processed": chunks_processed,
                        "buffer_seconds": len(self.audio_buffer) / Config.SAMPLE_RATE,
                        "stream_position": self.get_stream_position()
                    })
                
                # ウェイクワード検出（アキュムレータを使用）
                audio_accumulator = np.concatenate([audio_accumulator, audio_chunk])
                
                # 必要なフレーム長以上になったら処理
                while len(audio_accumulator) >= frame_length:
                    # フレーム長分を切り出して処理
                    frame = audio_accumulator[:frame_length]
                    self.wake_detector.process_audio(frame)
                    
                    # 処理済み部分を削除
                    audio_accumulator = audio_accumulator[frame_length:]
                
                # 簡易無音検出
                if chunks_processed % 10 == 0:  # 100msごと
                    self.detect_silence(audio_chunk)
                    
            except Exception as e:
                log_json("error", {"worker": "audio_capture", "error": str(e)})
                time.sleep(0.1)
    
    def detect_silence(self, audio_chunk):
        """簡易無音検出"""
        if len(audio_chunk) == 0:
            return
        
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
        
        # アクティブセッションがある場合のみ無音検出
        if self.active_sessions and rms < Config.SILENCE_THRESHOLD:
            # 簡易的に最初のセッションに対して無音イベントを送信
            for session_id in list(self.active_sessions.keys()):
                event = AudioEvent(
                    timestamp=time.time(),
                    stream_position=self.get_stream_position(),
                    event_type="silence",
                    start=self.get_stream_position() - 2.0,
                    end=self.get_stream_position(),
                    metadata={"session_id": session_id}
                )
                self.event_queue.put(event)
                break
    
    def on_wake_word_detected(self, wake_word_info):
        """ウェイクワード検出コールバック"""
        stream_pos = self.get_stream_position()
        
        log_json("wake_word_detected", {
            "wake_word": wake_word_info['name'],
            "timestamp_start": wake_word_info.get('timestamp_start', 0),
            "timestamp_end": wake_word_info.get('timestamp_end', 0),
            "stream_position": stream_pos
        })
        
        event = AudioEvent(
            timestamp=time.time(),
            stream_position=stream_pos,
            event_type="wake_word",
            start=wake_word_info.get('timestamp_start', stream_pos - 1.5),
            end=wake_word_info.get('timestamp_end', stream_pos),
            metadata={
                "wake_word": wake_word_info['name']
            }
        )
        
        self.event_queue.put(event)
    
    def event_processor_worker(self):
        """イベント処理ワーカー"""
        log_json("worker", {"name": "event_processor", "status": "started"})
        
        while self.is_running:
            try:
                event = self.event_queue.get(timeout=0.1)
                
                if event.event_type == "wake_word":
                    # セッション開始
                    session_id = f"session_{int(event.timestamp * 1000)}"
                    self.active_sessions[session_id] = {
                        "wake_word": event,
                        "start_time": event.timestamp
                    }
                    
                    log_json("session_start", {
                        "session_id": session_id,
                        "wake_word": event.metadata["wake_word"]
                    })
                    
                elif event.event_type == "silence":
                    # セッション終了と文字起こし
                    session_id = event.metadata.get("session_id")
                    if session_id in self.active_sessions:
                        session = self.active_sessions[session_id]
                        wake_end = session["wake_word"].end
                        
                        # 音声データを抽出
                        audio_segment = self.extract_audio_segment(wake_end, event.start)
                        
                        if audio_segment is not None and len(audio_segment) > Config.SAMPLE_RATE * 0.5:
                            # 文字起こし
                            result = self.whisper_processor.transcribe(
                                audio_segment,
                                timestamp_start=wake_end,
                                wake_word_end_time=0
                            )
                            
                            if result:
                                log_json("transcription_result", {
                                    "session_id": session_id,
                                    "text": result.text,
                                    "duration": result.duration,
                                    "processing_time_ms": result.processing_time_ms
                                })
                        
                        # セッション削除
                        del self.active_sessions[session_id]
                        
                        log_json("session_end", {
                            "session_id": session_id
                        })
                
            except queue.Empty:
                continue
            except Exception as e:
                log_json("error", {"worker": "event_processor", "error": str(e)})
    
    def extract_audio_segment(self, start: float, end: float) -> Optional[np.ndarray]:
        """バッファから指定範囲の音声を抽出"""
        with self.buffer_lock:
            current_position = self.get_stream_position()
            buffer_array = np.array(self.audio_buffer)
        
        if len(buffer_array) == 0:
            return None
        
        # バッファ内での位置を計算
        buffer_duration = len(buffer_array) / Config.SAMPLE_RATE
        buffer_start_time = current_position - buffer_duration
        
        # サンプル位置を計算
        start_sample = int(max(0, (start - buffer_start_time) * Config.SAMPLE_RATE))
        end_sample = int(min(len(buffer_array), (end - buffer_start_time) * Config.SAMPLE_RATE))
        
        if start_sample >= end_sample:
            return None
        
        return buffer_array[start_sample:end_sample]
    
    def run(self):
        """メインループ"""
        try:
            while self.is_running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            pass
        
        self.stop()
    
    def stop(self):
        """終了処理"""
        log_json("system", {"status": "shutting_down"})
        self.is_running = False
        
        time.sleep(0.5)  # ワーカー終了を待つ
        
        self.wake_detector.cleanup()
        self.audio_recorder.cleanup()
        self.database.close()
        
        log_json("system", {"status": "stopped"})

def main():
    assistant = EventDrivenVoiceAssistant()
    
    if not assistant.initialize():
        return 1
    
    assistant.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())