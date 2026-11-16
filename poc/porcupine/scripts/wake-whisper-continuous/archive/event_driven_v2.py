#!/usr/bin/env python3
"""イベント駆動型音声認識システム V2
- ウェイクワード検出は独立したマイク入力
- リングバッファは文字起こし専用
"""

import json
import sys
import time
import threading
import queue
from collections import deque
from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np
import pyaudio

from config import Config
from wake_detector_auto import create_wake_detector
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

class EventDrivenVoiceAssistantV2:
    def __init__(self):
        Config.validate()
        
        # コンポーネント
        self.wake_detector = create_wake_detector()
        self.whisper_processor = SimpleWhisperProcessor()
        self.database = VoiceRequestDB(Config.DATABASE_PATH)
        
        # 共有リングバッファ（5分間）- 文字起こし用
        self.buffer_duration = 300
        self.audio_buffer = deque(maxlen=self.buffer_duration * Config.SAMPLE_RATE)
        self.buffer_lock = threading.Lock()
        self.total_samples = 0
        
        # イベントキュー
        self.event_queue = queue.Queue()
        
        # 状態管理
        self.is_running = True
        self.active_sessions = {}
        
        # PyAudio（2つのストリーム用）
        self.pa = pyaudio.PyAudio()
    
    def initialize(self):
        """初期化"""
        log_json("system", {"status": "initializing"})
        
        # ウェイクワード検出器
        if not self.wake_detector.initialize():
            return False
        
        self.wake_detector.set_detection_callback(self.on_wake_word_detected)
        
        # ストリーム開始時刻を記録
        self.stream_start_time = time.time()
        
        # ウェイクワード用ストリーム（独立）
        self.wake_stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=Config.SAMPLE_RATE,
            input=True,
            frames_per_buffer=self.wake_detector.get_frame_length()
        )
        
        # 文字起こし用ストリーム（リングバッファ用）
        self.transcribe_stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=Config.SAMPLE_RATE,
            input=True,
            frames_per_buffer=Config.CHUNK_SIZE
        )
        
        # ワーカースレッド開始
        threading.Thread(target=self.wake_detector_worker, daemon=True).start()
        threading.Thread(target=self.audio_buffer_worker, daemon=True).start()
        threading.Thread(target=self.event_processor_worker, daemon=True).start()
        
        log_json("system", {
            "status": "ready",
            "buffer_duration_seconds": self.buffer_duration,
            "wake_frame_length": self.wake_detector.get_frame_length()
        })
        
        return True
    
    def get_stream_position(self) -> float:
        """現在のストリーム位置を取得（秒）"""
        return self.total_samples / Config.SAMPLE_RATE
    
    def wake_detector_worker(self):
        """ウェイクワード検出専用ワーカー（独立ストリーム）"""
        log_json("worker", {"name": "wake_detector", "status": "started"})
        
        frame_length = self.wake_detector.get_frame_length()
        frames_processed = 0
        
        # 初回のデバッグ情報
        log_json("debug_wake_detector_init", {
            "frame_length": frame_length,
            "sample_rate": self.wake_detector.get_sample_rate() if hasattr(self.wake_detector, 'get_sample_rate') else Config.SAMPLE_RATE,
            "supported_languages": self.wake_detector.get_supported_languages() if hasattr(self.wake_detector, 'get_supported_languages') else [],
            "wake_words": [w['name'] for w in self.wake_detector.get_all_wake_words()] if hasattr(self.wake_detector, 'get_all_wake_words') else []
        })
        
        while self.is_running:
            try:
                # ウェイクワード用ストリームから直接読み取り
                audio_data = self.wake_stream.read(frame_length, exception_on_overflow=False)
                audio_frame = np.frombuffer(audio_data, dtype=np.int16)
                
                # デバッグ: 最初のフレームと定期的にオーディオレベルを確認
                if frames_processed == 0 or frames_processed % 100 == 0:
                    rms = np.sqrt(np.mean(audio_frame.astype(np.float32) ** 2))
                    log_json("debug_audio_level", {
                        "frame": frames_processed,
                        "rms": float(rms),
                        "max": int(np.max(audio_frame)),
                        "min": int(np.min(audio_frame))
                    })
                
                # ウェイクワード検出処理
                result = self.wake_detector.process_audio(audio_frame)
                if result is not None and frames_processed % 100 == 0:
                    log_json("debug_detection_result", {"frame": frames_processed, "result": result})
                
                frames_processed += 1
                
                # 定期的な状態出力（10秒ごと）
                if frames_processed % (10 * Config.SAMPLE_RATE // frame_length) == 0:
                    log_json("wake_detector_stats", {
                        "frames_processed": frames_processed,
                        "uptime_seconds": frames_processed * frame_length / Config.SAMPLE_RATE
                    })
                    
            except Exception as e:
                log_json("error", {"worker": "wake_detector", "error": str(e)})
                time.sleep(0.1)
    
    def audio_buffer_worker(self):
        """音声バッファ管理ワーカー（文字起こし用）"""
        log_json("worker", {"name": "audio_buffer", "status": "started"})
        
        chunks_processed = 0
        
        while self.is_running:
            try:
                # 文字起こし用ストリームから読み取り
                audio_data = self.transcribe_stream.read(Config.CHUNK_SIZE, exception_on_overflow=False)
                audio_chunk = np.frombuffer(audio_data, dtype=np.int16)
                
                # リングバッファに追加
                with self.buffer_lock:
                    self.audio_buffer.extend(audio_chunk)
                    self.total_samples += len(audio_chunk)
                
                chunks_processed += 1
                
                # 簡易無音検出
                if chunks_processed % 10 == 0:  # 100msごと
                    self.detect_silence(audio_chunk)
                    
                # セッション状態のデバッグ（5秒ごと）
                if chunks_processed % 500 == 0 and self.active_sessions:
                    log_json("debug_sessions", {
                        "active_count": len(self.active_sessions),
                        "sessions": {sid: {
                            "wake_word": s["wake_word"].metadata["wake_word"],
                            "duration": self.get_stream_position() - s["wake_word"].end,
                            "silence_count": s.get("silence_count", 0)
                        } for sid, s in self.active_sessions.items()}
                    })
                
                # 定期的な状態出力（10秒ごと）
                if chunks_processed % (10 * Config.SAMPLE_RATE // Config.CHUNK_SIZE) == 0:
                    log_json("buffer_stats", {
                        "chunks_processed": chunks_processed,
                        "buffer_seconds": len(self.audio_buffer) / Config.SAMPLE_RATE,
                        "stream_position": self.get_stream_position()
                    })
                    
            except Exception as e:
                log_json("error", {"worker": "audio_buffer", "error": str(e)})
                time.sleep(0.1)
    
    def detect_silence(self, audio_chunk):
        """簡易無音検出"""
        if len(audio_chunk) == 0:
            return
        
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
        
        # デバッグ: RMS値を定期的に出力
        if len(self.active_sessions) > 0:
            log_json("debug_silence_detection", {
                "rms": float(rms),
                "threshold": Config.SILENCE_THRESHOLD,
                "is_silence": bool(rms < Config.SILENCE_THRESHOLD)
            })
        
        # アクティブセッションがある場合のみ無音検出
        if self.active_sessions and rms < Config.SILENCE_THRESHOLD:
            for session_id, session in list(self.active_sessions.items()):
                # ウェイクワード後の初期無音期間を無視
                wake_end_time = session["wake_word"].end
                current_time = self.get_stream_position()
                
                if current_time - wake_end_time < Config.INITIAL_SILENCE_IGNORE:
                    continue
                
                # 無音カウンターを管理
                if "silence_count" not in session:
                    session["silence_count"] = 0
                
                session["silence_count"] += 1
                
                # 2秒間の無音で終了（100msごとのチェックなので20回）
                if session["silence_count"] >= 20:
                    event = AudioEvent(
                        timestamp=time.time(),
                        stream_position=current_time,
                        event_type="silence",
                        start=current_time - 2.0,
                        end=current_time,
                        metadata={"session_id": session_id}
                    )
                    self.event_queue.put(event)
                    break
        else:
            # 音声がある場合はカウンターをリセット
            for session in self.active_sessions.values():
                session["silence_count"] = 0
    
    def on_wake_word_detected(self, wake_word_info):
        """ウェイクワード検出コールバック"""
        stream_pos = self.get_stream_position()
        
        # タイムスタンプが設定されていない場合は現在位置から推定
        if wake_word_info.get('timestamp_start', 0) == 0:
            wake_word_info['timestamp_end'] = stream_pos
            wake_word_info['timestamp_start'] = stream_pos - 1.5
        
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
                                
                                # データベースに保存
                                db_data = {
                                    'wake_word': session["wake_word"].metadata["wake_word"],
                                    'wake_word_type': 'unknown',
                                    'audio_duration_seconds': result.duration,
                                    'transcribed_text': result.text,
                                    'transcription_level': 'final',
                                    'language': Config.WHISPER_LANGUAGE,
                                    'processing_time_ms': result.processing_time_ms,
                                    'timestamp_start': result.timestamp_start,
                                    'timestamp_end': result.timestamp_end,
                                    'session_id': session_id
                                }
                                self.database.insert_request(db_data)
                        
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
        
        # ストリームを閉じる
        self.wake_stream.stop_stream()
        self.wake_stream.close()
        self.transcribe_stream.stop_stream()
        self.transcribe_stream.close()
        self.pa.terminate()
        
        self.wake_detector.cleanup()
        self.database.close()
        
        log_json("system", {"status": "stopped"})

def main():
    assistant = EventDrivenVoiceAssistantV2()
    
    if not assistant.initialize():
        return 1
    
    assistant.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())