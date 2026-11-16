#!/usr/bin/env python3
"""イベント駆動型音声認識システム"""

import json
import sys
import time
import threading
import queue
from collections import deque
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from config import Config
from wake_detector_auto import create_wake_detector
from simple_whisper_processor import SimpleWhisperProcessor
from database import VoiceRequestDB

# イベントタイプ
@dataclass
class AudioEvent:
    """音声イベント"""
    timestamp: float  # イベント発生時刻（epoch）
    stream_position: float  # ストリーム内の位置（秒）
    event_type: str  # "wake_word", "silence", "speech", "noise"
    start: float  # イベント開始位置（ストリーム秒）
    end: float  # イベント終了位置（ストリーム秒）
    metadata: Dict[str, Any]  # 追加情報

@dataclass 
class TranscribeRequest:
    """文字起こしリクエスト"""
    request_id: str
    timestamp: float
    start: float
    end: float
    priority: str  # "realtime", "accurate", "final"
    context: Optional[str] = None  # 前の認識結果

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
        self.whisper_processor = SimpleWhisperProcessor()
        self.database = VoiceRequestDB(Config.DATABASE_PATH)
        
        # 共有リングバッファ（5分間）
        self.buffer_duration = 300  # 秒
        self.audio_buffer = deque(maxlen=self.buffer_duration * Config.SAMPLE_RATE)
        self.buffer_lock = threading.Lock()
        self.stream_start_time = None
        self.total_samples = 0
        
        # イベントキュー
        self.event_queue = queue.Queue()
        self.transcribe_queue = queue.Queue()
        
        # イベント履歴
        self.event_history = deque(maxlen=1000)
        
        # 状態管理
        self.is_running = False
        self.active_sessions = {}
        
        # ワーカースレッド
        self.threads = []
    
    def initialize(self):
        """初期化"""
        log_json("system", {"status": "initializing"})
        
        # ウェイクワード検出器
        if not self.wake_detector.initialize():
            return False
        
        self.wake_detector.set_detection_callback(self.on_wake_word_detected)
        
        # 音声レコーダー初期化（既存のMultiLevelAudioRecorderを使用）
        from audio_recorder import MultiLevelAudioRecorder
        self.audio_recorder = MultiLevelAudioRecorder()
        
        if hasattr(self.wake_detector, 'set_audio_recorder'):
            self.wake_detector.set_audio_recorder(self.audio_recorder)
        
        if not self.audio_recorder.start_stream():
            return False
        
        self.stream_start_time = time.time()
        
        # ワーカースレッド開始
        self.threads = [
            threading.Thread(target=self.audio_capture_worker, daemon=True),
            threading.Thread(target=self.event_processor_worker, daemon=True),
            threading.Thread(target=self.transcribe_worker, daemon=True),
            threading.Thread(target=self.silence_detector_worker, daemon=True)
        ]
        
        for i, thread in enumerate(self.threads):
            thread.start()
            log_json("debug_thread_started", {"thread_index": i, "thread_name": thread.name})
        
        log_json("system", {
            "status": "ready",
            "buffer_duration_seconds": self.buffer_duration,
            "architecture": "event_driven_shared_buffer",
            "threads_started": len(self.threads)
        })
        
        return True
    
    def get_stream_position(self) -> float:
        """現在のストリーム位置を取得（秒）"""
        return self.total_samples / Config.SAMPLE_RATE
    
    def audio_capture_worker(self):
        """音声キャプチャワーカー"""
        log_json("debug_worker_start", {"worker": "audio_capture"})
        chunks_processed = 0
        null_chunks = 0
        
        while self.is_running:
            try:
                # 音声読み取り（audio_recorderから）
                audio_chunk = self.audio_recorder.read_chunk()
                
                if audio_chunk is None:
                    null_chunks += 1
                    if null_chunks % 100 == 0:
                        log_json("debug_null_chunks", {"count": null_chunks})
                    time.sleep(0.01)
                    continue
                
                with self.buffer_lock:
                    # バッファに追加
                    self.audio_buffer.extend(audio_chunk)
                    self.total_samples += len(audio_chunk)
                
                chunks_processed += 1
                
                # デバッグ: 最初と定期的に状態を出力
                if chunks_processed == 1 or chunks_processed % 100 == 0:
                    log_json("debug_audio_capture", {
                        "chunks_processed": chunks_processed,
                        "chunk_size": len(audio_chunk),
                        "total_samples": self.total_samples,
                        "buffer_size": len(self.audio_buffer),
                        "stream_position": self.get_stream_position()
                    })
                
                # ウェイクワード検出
                frame_length = self.wake_detector.get_frame_length()
                if len(audio_chunk) == frame_length:
                    self.wake_detector.process_audio(audio_chunk)
                elif chunks_processed % 100 == 0:
                    log_json("debug_wake_detector", {
                        "chunk_size": len(audio_chunk),
                        "required_frame_length": frame_length,
                        "mismatch": True
                    })
                    
            except Exception as e:
                log_json("error", {"component": "audio_capture", "error": str(e)})
                time.sleep(0.1)
    
    def on_wake_word_detected(self, wake_word_info):
        """ウェイクワード検出コールバック"""
        stream_pos = self.get_stream_position()
        
        # デバッグ出力
        log_json("debug_wake_word_raw", {
            "wake_word_info": wake_word_info,
            "stream_position": stream_pos
        })
        
        event = AudioEvent(
            timestamp=time.time(),
            stream_position=stream_pos,
            event_type="wake_word",
            start=wake_word_info.get('timestamp_start', stream_pos - 1.5),
            end=wake_word_info.get('timestamp_end', stream_pos),
            metadata={
                "wake_word": wake_word_info['name'],
                "confidence": wake_word_info.get('confidence', 1.0)
            }
        )
        
        self.event_queue.put(event)
    
    def silence_detector_worker(self):
        """無音検出ワーカー"""
        chunk_duration = 0.1  # 100ms
        chunk_samples = int(chunk_duration * Config.SAMPLE_RATE)
        silence_chunks = 0
        silence_threshold_chunks = int(Config.SILENCE_DURATION / chunk_duration)
        
        last_check_position = 0
        is_in_speech = False
        speech_start = None
        
        while self.is_running:
            current_position = self.get_stream_position()
            
            # 新しいデータがある場合のみ処理
            if current_position > last_check_position + chunk_duration:
                with self.buffer_lock:
                    # 最新のチャンクを取得
                    if len(self.audio_buffer) >= chunk_samples:
                        chunk = np.array(list(self.audio_buffer))[-chunk_samples:]
                    else:
                        time.sleep(0.1)
                        continue
                
                # RMS計算
                rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                
                if rms < Config.SILENCE_THRESHOLD:
                    silence_chunks += 1
                    
                    if is_in_speech and silence_chunks >= silence_threshold_chunks:
                        # 音声終了イベント
                        event = AudioEvent(
                            timestamp=time.time(),
                            stream_position=current_position,
                            event_type="silence",
                            start=current_position - Config.SILENCE_DURATION,
                            end=current_position,
                            metadata={"after_speech": True}
                        )
                        self.event_queue.put(event)
                        
                        # 音声区間イベント
                        if speech_start is not None:
                            speech_event = AudioEvent(
                                timestamp=time.time(),
                                stream_position=current_position,
                                event_type="speech",
                                start=speech_start,
                                end=current_position - Config.SILENCE_DURATION,
                                metadata={"rms_avg": rms}
                            )
                            self.event_queue.put(speech_event)
                        
                        is_in_speech = False
                        speech_start = None
                else:
                    silence_chunks = 0
                    if not is_in_speech:
                        is_in_speech = True
                        speech_start = current_position
                
                last_check_position = current_position
            
            time.sleep(0.05)
    
    def event_processor_worker(self):
        """イベント処理ワーカー"""
        while self.is_running:
            try:
                event = self.event_queue.get(timeout=0.1)
                self.event_history.append(event)
                
                log_json(f"audio_event_{event.event_type}", {
                    "stream_position": event.stream_position,
                    "start": event.start,
                    "end": event.end,
                    "metadata": event.metadata
                })
                
                # セッション管理とトランスクリプションリクエスト生成
                if event.event_type == "wake_word":
                    session_id = f"session_{int(event.timestamp * 1000)}"
                    self.active_sessions[session_id] = {
                        "wake_word": event,
                        "start_time": event.timestamp,
                        "events": [event]
                    }
                    
                elif event.event_type == "silence" and event.metadata.get("after_speech"):
                    # アクティブなセッションを探す
                    for session_id, session in list(self.active_sessions.items()):
                        wake_end = session["wake_word"].end
                        
                        if wake_end < event.start:
                            # このセッションの音声が終了
                            
                            # 段階的な文字起こしリクエスト
                            audio_duration = event.start - wake_end
                            
                            # 1. リアルタイム（3秒）
                            if audio_duration >= 3:
                                self.transcribe_queue.put(TranscribeRequest(
                                    request_id=f"{session_id}_realtime",
                                    timestamp=time.time(),
                                    start=wake_end,
                                    end=min(wake_end + 3, event.start),
                                    priority="realtime"
                                ))
                            
                            # 2. 中精度（8秒）
                            if audio_duration >= 5:
                                self.transcribe_queue.put(TranscribeRequest(
                                    request_id=f"{session_id}_accurate",
                                    timestamp=time.time() + 0.1,
                                    start=wake_end,
                                    end=min(wake_end + 8, event.start),
                                    priority="accurate"
                                ))
                            
                            # 3. 最終版（全体）
                            self.transcribe_queue.put(TranscribeRequest(
                                request_id=f"{session_id}_final",
                                timestamp=time.time() + 0.2,
                                start=wake_end,
                                end=event.start,
                                priority="final"
                            ))
                            
                            # セッション終了
                            session["events"].append(event)
                            session["end_time"] = event.timestamp
                            del self.active_sessions[session_id]
                
            except queue.Empty:
                continue
            except Exception as e:
                log_json("error", {"component": "event_processor", "error": str(e)})
    
    def transcribe_worker(self):
        """文字起こしワーカー"""
        while self.is_running:
            try:
                request = self.transcribe_queue.get(timeout=0.1)
                
                # バッファから音声データを抽出
                audio_segment = self.extract_audio_segment(request.start, request.end)
                
                if audio_segment is None or len(audio_segment) < Config.SAMPLE_RATE * 0.5:
                    continue
                
                # 文字起こし実行
                result = self.whisper_processor.transcribe(
                    audio_segment,
                    timestamp_start=request.start,
                    wake_word_end_time=0  # すでに除外済み
                )
                
                if result:
                    log_json("transcription_result", {
                        "request_id": request.request_id,
                        "priority": request.priority,
                        "text": result.text,
                        "start": request.start,
                        "end": request.end,
                        "duration": request.end - request.start,
                        "processing_time_ms": result.processing_time_ms,
                        "segments": len(result.segments) if result.segments else 0
                    })
                
            except queue.Empty:
                continue
            except Exception as e:
                log_json("error", {"component": "transcribe_worker", "error": str(e)})
    
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
        
        # 要求範囲がバッファ内にあるか確認
        if end < buffer_start_time or start > current_position:
            return None
        
        # サンプル位置を計算
        start_sample = int(max(0, (start - buffer_start_time) * Config.SAMPLE_RATE))
        end_sample = int(min(len(buffer_array), (end - buffer_start_time) * Config.SAMPLE_RATE))
        
        if start_sample >= end_sample:
            return None
        
        return buffer_array[start_sample:end_sample]
    
    def run(self):
        """メインループ"""
        self.is_running = True
        
        try:
            while self.is_running:
                time.sleep(1)
                
                # 統計情報を定期的に出力
                if int(time.time()) % 30 == 0:
                    with self.buffer_lock:
                        buffer_size = len(self.audio_buffer) / Config.SAMPLE_RATE
                    
                    log_json("statistics", {
                        "buffer_size_seconds": buffer_size,
                        "stream_position": self.get_stream_position(),
                        "active_sessions": len(self.active_sessions),
                        "event_history_size": len(self.event_history),
                        "pending_transcriptions": self.transcribe_queue.qsize()
                    })
                
        except KeyboardInterrupt:
            pass
        
        self.stop()
    
    def stop(self):
        """終了処理"""
        log_json("system", {"status": "shutting_down"})
        self.is_running = False
        
        # スレッド終了を待つ
        for thread in self.threads:
            thread.join(timeout=1)
        
        # リソースクリーンアップ
        if hasattr(self, 'audio_recorder'):
            self.audio_recorder.cleanup()
        
        self.wake_detector.cleanup()
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