import pyaudio
import numpy as np
from collections import deque
from threading import Lock
from loguru import logger
import time
from typing import Optional, Tuple

class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 512):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        self.recorded_frames = []
        self.lock = Lock()
        
        # Ring buffer for continuous audio
        self.buffer_duration = 2  # seconds
        buffer_size = int(self.sample_rate * self.buffer_duration / self.chunk_size)
        self.ring_buffer = deque(maxlen=buffer_size)
        
    def start_stream(self):
        """Start the audio input stream."""
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=None
            )
            logger.info(f"Audio stream started: {self.sample_rate}Hz, chunk size: {self.chunk_size}")
            return True
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            return False
    
    def read_chunk(self) -> Optional[np.ndarray]:
        """Read a chunk of audio data."""
        if not self.stream:
            return None
        
        try:
            data = self.stream.read(self.chunk_size, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            
            # Add to ring buffer
            with self.lock:
                self.ring_buffer.append(audio_chunk)
                
                # If recording, add to recorded frames
                if self.is_recording:
                    self.recorded_frames.append(audio_chunk)
            
            return audio_chunk
            
        except Exception as e:
            logger.error(f"Error reading audio chunk: {e}")
            return None
    
    def start_recording(self):
        """Start recording audio."""
        with self.lock:
            self.is_recording = True
            self.recorded_frames = []
            # Include buffered audio (last 2 seconds before wake word)
            self.recorded_frames.extend(list(self.ring_buffer))
        logger.info("Started recording")
    
    def stop_recording(self) -> Tuple[Optional[np.ndarray], float]:
        """Stop recording and return the recorded audio."""
        with self.lock:
            self.is_recording = False
            if not self.recorded_frames:
                return None, 0.0
            
            # Concatenate all frames
            audio_data = np.concatenate(self.recorded_frames)
            duration = len(audio_data) / self.sample_rate
            
            logger.info(f"Stopped recording. Duration: {duration:.2f}s")
            return audio_data, duration
    
    def is_silence(self, audio_chunk: np.ndarray, threshold: int = 500) -> bool:
        """Check if audio chunk is silence."""
        if audio_chunk is None or len(audio_chunk) == 0:
            return True
        
        # Calculate RMS (Root Mean Square)
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
        return rms < threshold
    
    def detect_silence_end(self, silence_duration: float = 1.5, 
                          silence_threshold: int = 500) -> bool:
        """Detect if there's been sufficient silence to end recording."""
        if not self.is_recording:
            return False
        
        # Check recent audio chunks for silence
        with self.lock:
            if len(self.recorded_frames) < int(silence_duration * self.sample_rate / self.chunk_size):
                return False
            
            # Check the last silence_duration seconds
            chunks_to_check = int(silence_duration * self.sample_rate / self.chunk_size)
            recent_chunks = self.recorded_frames[-chunks_to_check:]
            
            # All chunks must be silence
            for chunk in recent_chunks:
                if not self.is_silence(chunk, silence_threshold):
                    return False
            
        return True
    
    def get_recording_duration(self) -> float:
        """Get current recording duration in seconds."""
        with self.lock:
            if not self.recorded_frames:
                return 0.0
            total_samples = sum(len(frame) for frame in self.recorded_frames)
            return total_samples / self.sample_rate
    
    def stop_stream(self):
        """Stop the audio stream."""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        logger.info("Audio stream stopped")
    
    def cleanup(self):
        """Clean up audio resources."""
        self.stop_stream()
        self.audio.terminate()
        logger.info("Audio recorder cleaned up")