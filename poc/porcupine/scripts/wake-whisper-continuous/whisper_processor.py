"""Whisperマルチプロセス音声認識モジュール"""
import whisper
import numpy as np
import time
import multiprocessing as mp
import queue
import tempfile
import wave
from pathlib import Path
from loguru import logger
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from config import Config

@dataclass
class TranscriptionTask:
    """音声認識タスク"""
    audio_data: np.ndarray
    sample_rate: int
    level: str
    timestamp: float
    duration: float
    wake_word_end_time: float = 0  # ウェイクワード終了時刻

@dataclass
class TranscriptionResult:
    """音声認識結果"""
    text: str
    level: str
    duration: float
    processing_time_ms: int
    worker_id: int
    timestamp: float
    language: str

def whisper_worker(worker_id: int, task_queue: mp.Queue, result_queue: mp.Queue):
    """Whisperワーカープロセス"""
    # プロセスごとにモデルをロード
    logger.info(f"ワーカー{worker_id}: Whisperモデル'{Config.WHISPER_MODEL}'をロード中...")
    model = whisper.load_model(Config.WHISPER_MODEL)
    logger.info(f"ワーカー{worker_id}: モデルロード完了")
    
    while True:
        try:
            # タスクを取得（タイムアウト付き）
            task = task_queue.get(timeout=1)
            
            if task is None:  # 終了シグナル
                logger.info(f"ワーカー{worker_id}: 終了")
                break
            
            # 音声認識を実行
            start_time = time.time()
            
            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name
                
                # WAVファイルとして保存
                with wave.open(tmp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(task.sample_rate)
                    wav_file.writeframes(task.audio_data.tobytes())
                
                # Whisperで認識
                result = model.transcribe(
                    tmp_path,
                    language=Config.WHISPER_LANGUAGE,
                    fp16=False  # CPU用
                )
                
                # 一時ファイルを削除
                Path(tmp_path).unlink()
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # 結果を作成
            transcription_result = TranscriptionResult(
                text=result["text"].strip(),
                level=task.level,
                duration=task.duration,
                processing_time_ms=processing_time_ms,
                worker_id=worker_id,
                timestamp=task.timestamp,
                language=result.get("language", Config.WHISPER_LANGUAGE)
            )
            
            # 結果を送信
            result_queue.put(transcription_result)
            
            logger.debug(f"ワーカー{worker_id}: {task.level}レベル認識完了 "
                        f"({processing_time_ms}ms) - '{transcription_result.text[:30]}...'")
            
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"ワーカー{worker_id}: エラー - {e}")

class WhisperProcessor:
    """Whisperマルチプロセス処理管理"""
    
    def __init__(self):
        self.task_queue = None
        self.result_queue = None
        self.workers = []
        self.is_running = False
    
    def start(self):
        """ワーカープロセスを開始"""
        if self.is_running:
            return
        
        # キューを作成
        self.task_queue = mp.Queue(maxsize=100)
        self.result_queue = mp.Queue()
        
        # ワーカープロセスを起動
        for i in range(Config.NUM_WORKERS):
            worker = mp.Process(
                target=whisper_worker,
                args=(i, self.task_queue, self.result_queue)
            )
            worker.start()
            self.workers.append(worker)
        
        self.is_running = True
        logger.info(f"Whisperプロセッサ開始: {Config.NUM_WORKERS}ワーカー")
    
    def submit_task(self, audio_data: np.ndarray, level: str, 
                   duration: float, timestamp: float, wake_word_end_time: float = 0):
        """音声認識タスクを送信"""
        if not self.is_running:
            logger.warning("Whisperプロセッサが起動していません")
            return
        
        task = TranscriptionTask(
            audio_data=audio_data,
            sample_rate=Config.SAMPLE_RATE,
            level=level,
            timestamp=timestamp,
            duration=duration,
            wake_word_end_time=wake_word_end_time
        )
        
        try:
            self.task_queue.put(task, timeout=0.1)
            logger.debug(f"{level}レベルのタスクを送信")
        except queue.Full:
            logger.warning(f"タスクキューが満杯です。{level}レベルのタスクをスキップ")
    
    def get_results(self) -> list[TranscriptionResult]:
        """利用可能な結果を全て取得"""
        results = []
        
        while True:
            try:
                result = self.result_queue.get_nowait()
                results.append(result)
            except queue.Empty:
                break
        
        return results
    
    def stop(self):
        """ワーカープロセスを停止"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 終了シグナルを送信
        for _ in self.workers:
            try:
                self.task_queue.put(None, timeout=0.1)
            except:
                pass
        
        # ワーカーの終了を待つ
        for worker in self.workers:
            worker.join(timeout=2)
            if worker.is_alive():
                logger.warning(f"ワーカー{worker.pid}の強制終了")
                worker.terminate()
                worker.join(timeout=1)
        
        # キューをクリア
        try:
            self.task_queue.close()
            self.result_queue.close()
        except:
            pass
        
        self.workers.clear()
        logger.info("Whisperプロセッサを停止しました")