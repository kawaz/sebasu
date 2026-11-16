"""マルチレベルバッファ音声録音モジュール"""
import pyaudio
import numpy as np
import time
from collections import deque
from threading import Lock
from loguru import logger
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from config import Config

@dataclass
class AudioChunk:
    """音声チャンクのデータクラス"""
    audio: np.ndarray
    timestamp: float
    start_time: float
    end_time: float
    duration: float
    level: str
    rms: float

class MultiLevelAudioRecorder:
    """マルチレベルバッファを持つ音声録音器"""
    
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        self.lock = Lock()
        
        # 設定
        self.sample_rate = Config.SAMPLE_RATE
        self.chunk_size = Config.CHUNK_SIZE
        
        # 連続録音バッファ（最大2分保持）
        self.max_duration = 120
        self.max_samples = int(self.max_duration * self.sample_rate)
        self.continuous_buffer = deque(maxlen=self.max_samples)
        self.recording_start_time = 0
        
        # マルチレベルバッファ
        self.level_buffers = {}
        for level, config in Config.BUFFER_LEVELS.items():
            buffer_size = int(config['duration'] * self.sample_rate)
            self.level_buffers[level] = deque(maxlen=buffer_size)
        
        # 無音検出
        self.silence_threshold = Config.SILENCE_THRESHOLD
        self.silence_duration = Config.SILENCE_DURATION
        self.silence_start = None
        
        # ウェイクワード検出前のプリバッファ（2秒）
        self.pre_buffer_duration = 2
        self.pre_buffer_size = int(self.pre_buffer_duration * self.sample_rate / self.chunk_size)
        self.pre_buffer = deque(maxlen=self.pre_buffer_size)
        
        # タイムスタンプ管理
        self.stream_start_time = None
        self.current_position = 0  # 現在のストリーム位置（サンプル数）
    
    def start_stream(self):
        """音声ストリームを開始"""
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            logger.info(f"音声ストリーム開始: {self.sample_rate}Hz, "
                       f"チャンクサイズ: {self.chunk_size}")
            self.stream_start_time = time.time()
            return True
            
        except Exception as e:
            logger.error(f"音声ストリーム開始エラー: {e}")
            return False
    
    def read_chunk(self) -> Optional[np.ndarray]:
        """音声チャンクを読み取り"""
        if not self.stream:
            return None
        
        try:
            data = self.stream.read(self.chunk_size, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            
            with self.lock:
                # プリバッファに追加
                self.pre_buffer.append(audio_chunk)
                
                # 録音中の場合
                if self.is_recording:
                    # 連続バッファに追加
                    self.continuous_buffer.extend(audio_chunk)
                    
                    # 各レベルバッファに追加
                    for level_buffer in self.level_buffers.values():
                        level_buffer.extend(audio_chunk)
            
            # ストリーム位置を更新
            self.current_position += len(audio_chunk)
            
            return audio_chunk
            
        except Exception as e:
            logger.error(f"音声チャンク読み取りエラー: {e}")
            return None
    
    def start_recording(self):
        """録音を開始（プリバッファを含む）"""
        with self.lock:
            self.is_recording = True
            self.recording_start_time = time.time()
            
            # プリバッファの内容を連続バッファとレベルバッファに追加
            for chunk in self.pre_buffer:
                self.continuous_buffer.extend(chunk)
                for level_buffer in self.level_buffers.values():
                    level_buffer.extend(chunk)
            
            logger.info("録音開始（プリバッファ含む）")
    
    def stop_recording(self):
        """録音を停止"""
        with self.lock:
            self.is_recording = False
            logger.info("録音停止")
    
    def get_audio_chunks(self) -> List[AudioChunk]:
        """現在のマルチレベル音声チャンクを取得"""
        chunks = []
        current_time = time.time()
        
        with self.lock:
            for level, buffer in self.level_buffers.items():
                if len(buffer) > 0:
                    audio_data = np.array(buffer)
                    duration = len(audio_data) / self.sample_rate
                    
                    # 各レベルの設定を確認
                    level_config = Config.BUFFER_LEVELS[level]
                    
                    # 十分な長さがある場合のみチャンクを作成
                    if duration >= level_config['duration'] * 0.9:  # 90%以上の長さ
                        rms = self._calculate_rms(audio_data)
                        
                        # タイムスタンプはストリーム開始からの秒数で統一
                        current_stream_time = self.get_current_timestamp()
                        chunk = AudioChunk(
                            audio=audio_data,
                            timestamp=current_stream_time,
                            start_time=current_stream_time - duration,
                            end_time=current_stream_time,
                            duration=duration,
                            level=level,
                            rms=rms
                        )
                        chunks.append(chunk)
        
        return chunks
    
    def get_ultra_chunk(self) -> Optional[AudioChunk]:
        """無音区切りの音声チャンク（ultra）を取得"""
        with self.lock:
            if len(self.continuous_buffer) > 0:
                audio_data = np.array(self.continuous_buffer)
                duration = len(audio_data) / self.sample_rate
                current_stream_time = self.get_current_timestamp()
                rms = self._calculate_rms(audio_data)
                
                # recording_start_timeもストリーム時間に変換
                recording_start_stream_time = (self.recording_start_time - self.stream_start_time) if self.stream_start_time else 0
                
                chunk = AudioChunk(
                    audio=audio_data,
                    timestamp=current_stream_time,
                    start_time=recording_start_stream_time,
                    end_time=current_stream_time,
                    duration=duration,
                    level='ultra',
                    rms=rms
                )
                
                # バッファをクリア
                self.continuous_buffer.clear()
                self.recording_start_time = time.time()
                
                return chunk
        
        return None
    
    def detect_silence(self, audio_chunk: np.ndarray) -> bool:
        """無音を検出"""
        if audio_chunk is None or len(audio_chunk) == 0:
            return True
        
        rms = self._calculate_rms(audio_chunk)
        is_silence = rms < self.silence_threshold
        
        current_time = time.time()
        
        if is_silence:
            if self.silence_start is None:
                self.silence_start = current_time
            elif current_time - self.silence_start >= self.silence_duration:
                logger.debug(f"{self.silence_duration}秒の無音を検出")
                return True
        else:
            self.silence_start = None
        
        return False
    
    def _calculate_rms(self, audio_data: np.ndarray) -> float:
        """RMS（Root Mean Square）を計算"""
        if len(audio_data) == 0:
            return 0.0
        return np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
    
    def get_recording_duration(self) -> float:
        """現在の録音時間を取得"""
        if not self.is_recording:
            return 0.0
        return time.time() - self.recording_start_time
    
    def cleanup(self):
        """リソースをクリーンアップ"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
        logger.info("音声録音器をクリーンアップしました")
    
    def get_current_timestamp(self) -> float:
        """現在のタイムスタンプを取得（秒）"""
        if not self.stream_start_time:
            return 0.0
        # サンプル位置から正確なタイムスタンプを計算
        return self.current_position / self.sample_rate
    
    def get_timestamp_at_position(self, sample_position: int) -> float:
        """特定のサンプル位置のタイムスタンプを取得（秒）"""
        return sample_position / self.sample_rate