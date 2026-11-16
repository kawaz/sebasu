#!/usr/bin/env python3
"""連続ウェイクワード対応版"""

import json
import sys
import time
import threading
from collections import deque
from typing import List, Dict, Any, Optional

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

class ContinuousVoiceAssistant:
    def __init__(self):
        Config.validate()
        
        # コンポーネント初期化
        self.wake_detector = create_wake_detector()
        self.audio_recorder = MultiLevelAudioRecorder()
        self.whisper_processor = SimpleWhisperProcessor()
        self.database = VoiceRequestDB(Config.DATABASE_PATH)
        
        # 状態管理
        self.is_running = False
        self.current_session = None
        self.session_lock = threading.Lock()
        
        # ウェイクワード検出履歴（録音中も含む）
        self.wake_word_history = deque(maxlen=10)
        
        # 処理中のセッション
        self.active_sessions = {}
    
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
            "sample_rate": Config.SAMPLE_RATE
        })
        
        return True
    
    def on_wake_word_detected(self, wake_word_info):
        """ウェイクワード検出（録音中も含む）"""
        # 検出履歴に追加
        detection_time = time.time()
        wake_word_info['detection_time'] = detection_time
        self.wake_word_history.append(wake_word_info)
        
        log_json("wake_word_detected", {
            "wake_word": wake_word_info['name'],
            "timestamp_start": wake_word_info.get('timestamp_start', 0),
            "timestamp_end": wake_word_info.get('timestamp_end', 0),
            "during_recording": bool(self.current_session)
        })
        
        with self.session_lock:
            # 既存セッションがある場合
            if self.current_session:
                # 既存セッションにウェイクワード情報を追加
                self.current_session['additional_wake_words'].append(wake_word_info)
                
                # 新しいセッションも開始（並行処理）
                new_session_id = f"{int(detection_time * 1000)}"
                new_session = {
                    "session_id": new_session_id,
                    "start_wake_word": wake_word_info,
                    "additional_wake_words": [],
                    "start_time": detection_time,
                    "overlaps_with": self.current_session["session_id"]
                }
                
                # バックグラウンドで新セッション開始
                threading.Thread(
                    target=self.process_session,
                    args=(new_session,),
                    daemon=True
                ).start()
            else:
                # 新規セッション開始
                session_id = f"{int(detection_time * 1000)}"
                self.current_session = {
                    "session_id": session_id,
                    "start_wake_word": wake_word_info,
                    "additional_wake_words": [],
                    "start_time": detection_time
                }
                
                # 録音開始
                self.audio_recorder.start_recording()
                
                # 処理開始
                threading.Thread(
                    target=self.process_session,
                    args=(self.current_session,),
                    daemon=True
                ).start()
    
    def process_session(self, session):
        """セッション処理"""
        session_id = session["session_id"]
        wake_word_end = session["start_wake_word"].get('timestamp_end', 0)
        
        log_json("session_start", {
            "session_id": session_id,
            "wake_word_end_timestamp": wake_word_end,
            "overlaps_with": session.get("overlaps_with")
        })
        
        # マルチレベル認識
        recognized_levels = {}
        start_time = time.time()
        
        while self.is_running:
            current_time = time.time()
            current_timestamp = self.audio_recorder.get_current_timestamp()
            
            # 録音時間チェック
            if current_time - start_time > 30:
                break
            
            # 各レベルのチャンクを確認
            chunks = self.audio_recorder.get_audio_chunks()
            
            for chunk in chunks:
                if chunk.level not in recognized_levels:
                    # 初回認識
                    result = self.process_chunk(chunk, session)
                    if result:
                        recognized_levels[chunk.level] = result
                        
                        # セッション内の追加ウェイクワード情報も含める
                        additional_wake_words = []
                        seen_wake_words = set()
                        for ww in session['additional_wake_words']:
                            # 重複チェック
                            ww_key = (ww['name'], ww['timestamp_start'], ww['timestamp_end'])
                            if ww_key not in seen_wake_words:
                                if ww['timestamp_start'] >= chunk.start_time and ww['timestamp_end'] <= chunk.end_time:
                                    additional_wake_words.append({
                                        "wake_word": ww['name'],
                                        "timestamp_start": ww['timestamp_start'],
                                        "timestamp_end": ww['timestamp_end']
                                    })
                                    seen_wake_words.add(ww_key)
                        
                        log_json("recognition_result", {
                            "session_id": session_id,
                            "level": chunk.level,
                            "text": result.text,
                            "timestamp_start": result.timestamp_start,
                            "timestamp_end": result.timestamp_end,
                            "duration": result.duration,
                            "processing_time_ms": result.processing_time_ms,
                            "additional_wake_words": additional_wake_words,
                            "segment_count": len(result.segments) if result.segments else 0
                        })
            
            # 無音検出
            if current_timestamp > wake_word_end + Config.INITIAL_SILENCE_IGNORE:
                audio_chunk = self.audio_recorder.read_chunk()
                if audio_chunk is not None and self.audio_recorder.detect_silence(audio_chunk):
                    log_json("silence_detected", {
                        "session_id": session_id,
                        "timestamp": current_timestamp
                    })
                    break
            
            time.sleep(0.1)
        
        # セッション終了処理
        with self.session_lock:
            if self.current_session and self.current_session["session_id"] == session_id:
                self.current_session = None
                self.audio_recorder.stop_recording()
        
        # 最終処理
        ultra_chunk = self.audio_recorder.get_ultra_chunk()
        if ultra_chunk and ultra_chunk.duration > 0.5:
            result = self.process_chunk(ultra_chunk, session)
            if result:
                # 全ての追加ウェイクワードを含める（重複除去）
                additional_wake_words = []
                seen_wake_words = set()
                for ww in session['additional_wake_words']:
                    ww_key = (ww['name'], ww['timestamp_start'], ww['timestamp_end'])
                    if ww_key not in seen_wake_words:
                        additional_wake_words.append({
                            "wake_word": ww['name'],
                            "timestamp_start": ww['timestamp_start'],
                            "timestamp_end": ww['timestamp_end']
                        })
                        seen_wake_words.add(ww_key)
                
                log_json("recognition_result", {
                    "session_id": session_id,
                    "level": "ultra",
                    "text": result.text,
                    "timestamp_start": result.timestamp_start,
                    "timestamp_end": result.timestamp_end,
                    "duration": result.duration,
                    "processing_time_ms": result.processing_time_ms,
                    "additional_wake_words": additional_wake_words,
                    "segment_count": len(result.segments) if result.segments else 0,
                    "interpretation_hints": self.generate_interpretation_hints(result, session)
                })
        
        log_json("session_end", {
            "session_id": session_id,
            "total_wake_words": 1 + len(session['additional_wake_words'])
        })
    
    def process_chunk(self, chunk, session):
        """音声チャンクを処理"""
        wake_word_end = session["start_wake_word"].get('timestamp_end', 0)
        
        # ウェイクワード部分を除外
        audio_to_process = chunk.audio
        process_start_time = chunk.start_time
        
        if wake_word_end > process_start_time:
            skip_duration = wake_word_end - process_start_time
            skip_samples = int(skip_duration * Config.SAMPLE_RATE)
            if skip_samples < len(audio_to_process):
                audio_to_process = audio_to_process[skip_samples:]
                process_start_time = wake_word_end
            else:
                return None
        
        return self.whisper_processor.transcribe(
            audio_to_process,
            timestamp_start=process_start_time,
            wake_word_end_time=wake_word_end
        )
    
    def generate_interpretation_hints(self, result, session):
        """解釈のヒントを生成"""
        hints = []
        
        # 追加ウェイクワードがある場合
        if session['additional_wake_words']:
            hints.append({
                "type": "multiple_commands_possible",
                "description": "録音中に追加のウェイクワードが検出されました",
                "wake_word_count": len(session['additional_wake_words'])
            })
            
            # セグメント情報から推測
            if result.segments:
                for i, segment in enumerate(result.segments):
                    for ww in session['additional_wake_words']:
                        if segment['start'] <= ww['timestamp_start'] - result.timestamp_start <= segment['end']:
                            hints.append({
                                "type": "wake_word_in_segment",
                                "segment_index": i,
                                "segment_text": segment['text'],
                                "wake_word": ww['name']
                            })
        
        return hints
    
    def run(self):
        """メインループ"""
        self.is_running = True
        
        try:
            while self.is_running:
                audio_chunk = self.audio_recorder.read_chunk()
                
                if audio_chunk is None:
                    time.sleep(0.01)
                    continue
                
                # ウェイクワード検出（常に実行）
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
    assistant = ContinuousVoiceAssistant()
    
    if not assistant.initialize():
        return 1
    
    assistant.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())