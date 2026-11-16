"""シンプルなWhisper処理モジュール"""
import whisper
import numpy as np
import time
from loguru import logger
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from config import Config

@dataclass
class TranscriptionResult:
    """音声認識結果"""
    text: str
    timestamp_start: float
    timestamp_end: float
    duration: float
    processing_time_ms: int
    segments: List[Dict[str, Any]]  # Whisperのセグメント情報

class SimpleWhisperProcessor:
    """シンプルなWhisper処理クラス"""
    
    def __init__(self):
        logger.info(f"Whisperモデル'{Config.WHISPER_MODEL}'をロード中...")
        self.model = whisper.load_model(Config.WHISPER_MODEL)
        logger.info("モデルロード完了")
    
    def transcribe(self, audio_data: np.ndarray, 
                  timestamp_start: float,
                  wake_word_end_time: float = 0) -> Optional[TranscriptionResult]:
        """音声データを文字起こし"""
        
        start_time = time.time()
        
        try:
            # ウェイクワード部分をスキップ（wake_word_end_timeは0を渡さない）
            if wake_word_end_time > 0 and wake_word_end_time > timestamp_start:
                skip_samples = int((wake_word_end_time - timestamp_start) * Config.SAMPLE_RATE)
                if skip_samples < len(audio_data):
                    audio_data = audio_data[skip_samples:]
                    timestamp_start = wake_word_end_time
                else:
                    # 全て削除されてしまう場合はスキップ
                    return None
            
            # 音声の長さを計算
            duration = len(audio_data) / Config.SAMPLE_RATE
            
            # 音声が短すぎる場合はスキップ
            if duration < 0.5:
                return None
            
            # int16をfloat32に変換
            audio_float = audio_data.astype(np.float32) / 32768.0
            
            # Whisperで認識（セグメント情報も取得）
            result = self.model.transcribe(
                audio_float,
                language=Config.WHISPER_LANGUAGE,
                fp16=False,
                verbose=False
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # 結果を作成
            transcription_result = TranscriptionResult(
                text=result["text"].strip(),
                timestamp_start=timestamp_start,
                timestamp_end=timestamp_start + duration,
                duration=duration,
                processing_time_ms=processing_time_ms,
                segments=result.get("segments", [])
            )
            
            return transcription_result
            
        except Exception as e:
            logger.error(f"音声認識エラー: {e}")
            return None