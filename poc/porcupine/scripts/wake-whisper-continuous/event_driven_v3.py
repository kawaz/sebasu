#!/usr/bin/env python3
"""イベント駆動型音声認識システム V3
- ウェイクワード検出は独立したマイク入力
- リングバッファは文字起こし専用
- リアルタイムマルチレベル認識を実装
"""

import json
import sys
import time
import threading
import queue
from collections import deque
from dataclasses import dataclass
from typing import Dict, Any, Optional, Set
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

@dataclass
class TranscribeRequest:
    """文字起こしリクエスト"""
    session_id: str
    level: str  # "short", "medium", "long", "final"
    start: float
    end: float
    timestamp: float

def log_json(event_type, data):
    """JSON形式でログ出力"""
    log_entry = {
        "timestamp": time.time(),
        "event": event_type,
        "data": data
    }
    print(json.dumps(log_entry, ensure_ascii=False))
    sys.stdout.flush()

class EventDrivenVoiceAssistantV3:
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
        
        # キュー
        self.event_queue = queue.Queue()
        self.transcribe_queue = queue.Queue()
        
        # 状態管理
        self.is_running = True
        self.active_sessions = {}
        self.transcription_results = {}  # セッションごとの認識結果を保持
        self.transcription_history = {}  # 認識結果の履歴（変化検出用）
        
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
        threading.Thread(target=self.transcribe_worker, daemon=True).start()
        threading.Thread(target=self.level_manager_worker, daemon=True).start()
        
        log_json("system", {
            "status": "ready",
            "buffer_duration_seconds": self.buffer_duration,
            "wake_frame_length": self.wake_detector.get_frame_length(),
            "levels": list(Config.BUFFER_LEVELS.keys())
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
        
        while self.is_running:
            try:
                # ウェイクワード用ストリームから直接読み取り
                audio_data = self.wake_stream.read(frame_length, exception_on_overflow=False)
                audio_frame = np.frombuffer(audio_data, dtype=np.int16)
                
                # ウェイクワード検出処理
                self.wake_detector.process_audio(audio_frame)
                
                frames_processed += 1
                    
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
                    
            except Exception as e:
                log_json("error", {"worker": "audio_buffer", "error": str(e)})
                time.sleep(0.1)
    
    def detect_silence(self, audio_chunk):
        """簡易無音検出"""
        if len(audio_chunk) == 0:
            return
        
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
        
        # アクティブセッションがある場合のみ無音検出
        if len(self.active_sessions) > 0 and rms < Config.SILENCE_THRESHOLD:
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
                
                # 環境ノイズが多い場合は無音検出を緩める（5秒間）
                if session["silence_count"] >= 50:  # 500msごとのチェックなので50回
                    event = AudioEvent(
                        timestamp=time.time(),
                        stream_position=current_time,
                        event_type="silence",
                        start=current_time - 5.0,
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
                "wake_word": wake_word_info['name'],
                "wake_word_type": wake_word_info.get('type', 'unknown')
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
                        "start_time": event.timestamp,
                        "last_level_check": {}  # 各レベルの最終チェック時刻
                    }
                    self.transcription_results[session_id] = {}
                    self.transcription_history[session_id] = {"texts": [], "no_change_count": 0}
                    
                    log_json("session_start", {
                        "session_id": session_id,
                        "wake_word": event.metadata["wake_word"]
                    })
                    
                elif event.event_type == "silence":
                    # セッション終了
                    session_id = event.metadata.get("session_id")
                    if session_id in self.active_sessions:
                        self.finalize_session(session_id)
                
            except queue.Empty:
                continue
            except Exception as e:
                log_json("error", {"worker": "event_processor", "error": str(e)})
    
    def level_manager_worker(self):
        """マルチレベル管理ワーカー"""
        log_json("worker", {"name": "level_manager", "status": "started"})
        
        while self.is_running:
            try:
                current_time = time.time()
                current_stream_pos = self.get_stream_position()
                
                # アクティブセッションのレベルチェック
                for session_id, session in list(self.active_sessions.items()):
                    wake_end = session["wake_word"].end
                    duration_since_wake = current_stream_pos - wake_end
                    
                    # 各レベルのチェック
                    for level, config in Config.BUFFER_LEVELS.items():
                        if level == "ultra":  # ultraは最終処理のみ
                            continue
                        
                        # このレベルの処理タイミングかチェック
                        level_duration = config['duration']
                        if duration_since_wake >= level_duration:
                            last_check = session["last_level_check"].get(level, 0)
                            
                            # オーバーラップを考慮した再処理間隔
                            min_interval = level_duration - config.get('overlap', 1.0)
                            if current_time - last_check >= min_interval:
                                # 文字起こしリクエストを作成
                                req = TranscribeRequest(
                                    session_id=session_id,
                                    level=level,
                                    start=wake_end,
                                    end=min(wake_end + level_duration, current_stream_pos),
                                    timestamp=current_time
                                )
                                self.transcribe_queue.put(req)
                                session["last_level_check"][level] = current_time
                
                time.sleep(0.5)  # 500msごとにチェック
                
            except Exception as e:
                log_json("error", {"worker": "level_manager", "error": str(e)})
                time.sleep(1)
    
    def transcribe_worker(self):
        """文字起こしワーカー"""
        log_json("worker", {"name": "transcribe", "status": "started"})
        
        while self.is_running:
            try:
                req = self.transcribe_queue.get(timeout=0.1)
                
                # バッファから音声データを抽出
                audio_segment = self.extract_audio_segment(req.start, req.end)
                
                if audio_segment is None or len(audio_segment) < Config.SAMPLE_RATE * 0.5:
                    continue
                
                log_json("transcription_start", {
                    "session_id": req.session_id,
                    "level": req.level,
                    "duration": req.end - req.start
                })
                
                # 文字起こし実行
                result = self.whisper_processor.transcribe(
                    audio_segment,
                    timestamp_start=req.start,
                    wake_word_end_time=0  # すでに除外済み
                )
                
                if result and result.text:
                    # 結果を保存
                    self.transcription_results[req.session_id][req.level] = {
                        "text": result.text,
                        "timestamp": req.timestamp,
                        "duration": result.duration,
                        "processing_time_ms": result.processing_time_ms
                    }
                    
                    log_json("transcription_result", {
                        "session_id": req.session_id,
                        "level": req.level,
                        "text": result.text,
                        "duration": result.duration,
                        "processing_time_ms": result.processing_time_ms
                    })
                    
                    # 認識結果の変化をチェック
                    self.check_transcription_change(req.session_id, result.text)
                
            except queue.Empty:
                continue
            except Exception as e:
                log_json("error", {"worker": "transcribe", "error": str(e)})
    
    def finalize_session(self, session_id: str):
        """セッションを終了して最終文字起こしを実行"""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        
        wake_end = session["wake_word"].end
        current_pos = self.get_stream_position()
        
        # 最終（ultra）レベルの文字起こし
        audio_segment = self.extract_audio_segment(wake_end, current_pos - 2.0)  # 無音部分を除外
        
        if audio_segment and len(audio_segment) > Config.SAMPLE_RATE * 0.5:
            log_json("transcription_start", {
                "session_id": session_id,
                "level": "ultra",
                "duration": current_pos - 2.0 - wake_end
            })
            
            result = self.whisper_processor.transcribe(
                audio_segment,
                timestamp_start=wake_end,
                wake_word_end_time=0
            )
            
            if result:
                log_json("transcription_result", {
                    "session_id": session_id,
                    "level": "ultra",
                    "text": result.text,
                    "duration": result.duration,
                    "processing_time_ms": result.processing_time_ms
                })
                
                # データベースに保存
                db_data = {
                    'wake_word': session["wake_word"].metadata["wake_word"],
                    'wake_word_type': session["wake_word"].metadata.get("wake_word_type", "unknown"),
                    'audio_duration_seconds': result.duration,
                    'transcribed_text': result.text,
                    'transcription_level': 'ultra',
                    'language': Config.WHISPER_LANGUAGE,
                    'processing_time_ms': result.processing_time_ms,
                    'timestamp_start': result.timestamp_start,
                    'timestamp_end': result.timestamp_end,
                    'session_id': session_id
                }
                self.database.insert_request(db_data)
        
        # 全レベルの結果サマリー
        results_summary = {}
        for level, result in self.transcription_results.get(session_id, {}).items():
            results_summary[level] = result["text"]
        
        log_json("session_end", {
            "session_id": session_id,
            "all_levels": results_summary
        })
        
        # セッションクリーンアップ
        del self.active_sessions[session_id]
        if session_id in self.transcription_results:
            del self.transcription_results[session_id]
        if session_id in self.transcription_history:
            del self.transcription_history[session_id]
    
    def check_transcription_change(self, session_id: str, new_text: str):
        """認識結果の変化をチェックしてセッション終了を判定"""
        if session_id not in self.transcription_history:
            return
        
        history = self.transcription_history[session_id]
        
        # テキストを正規化（空白や句読点を除去）
        normalized_text = new_text.strip().replace(" ", "").replace("、", "").replace("。", "")
        
        # 履歴の最後のテキストと比較
        if history["texts"]:
            last_text = history["texts"][-1].strip().replace(" ", "").replace("、", "").replace("。", "")
            
            # 同じ内容か、前の内容が含まれているか判定
            if normalized_text == last_text or last_text in normalized_text:
                history["no_change_count"] += 1
                
                log_json("transcription_unchanged", {
                    "session_id": session_id,
                    "no_change_count": history["no_change_count"],
                    "text": new_text
                })
                
                # 3回連続で同じ内容なら終了
                if history["no_change_count"] >= 3:
                    log_json("session_end_by_repetition", {
                        "session_id": session_id,
                        "final_text": new_text
                    })
                    
                    # セッション終了イベントを発行
                    event = AudioEvent(
                        timestamp=time.time(),
                        stream_position=self.get_stream_position(),
                        event_type="silence",  # 既存の終了処理を利用
                        start=self.get_stream_position() - 2.0,
                        end=self.get_stream_position(),
                        metadata={"session_id": session_id, "reason": "repetition"}
                    )
                    self.event_queue.put(event)
            else:
                # 新しい内容が追加された
                history["no_change_count"] = 0
                history["texts"].append(new_text)
                
                log_json("transcription_changed", {
                    "session_id": session_id,
                    "new_content": new_text
                })
        else:
            # 最初のテキスト
            history["texts"].append(new_text)
    
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
    assistant = EventDrivenVoiceAssistantV3()
    
    if not assistant.initialize():
        return 1
    
    assistant.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())