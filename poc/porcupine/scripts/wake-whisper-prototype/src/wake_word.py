import pvporcupine
import numpy as np
from threading import Thread, Event
from queue import Queue
from loguru import logger
from typing import Optional, Callable

class WakeWordDetector:
    def __init__(self, access_key: str, keyword: str = "jarvis"):
        self.access_key = access_key
        self.keyword = keyword
        self.porcupine = None
        self._running = False
        self._detection_callback = None
        
    def initialize(self):
        """Initialize Porcupine wake word engine."""
        try:
            self.porcupine = pvporcupine.create(
                access_key=self.access_key,
                keywords=[self.keyword]
            )
            logger.info(f"Wake word detector initialized with keyword: {self.keyword}")
            logger.info(f"Sample rate: {self.porcupine.sample_rate}, Frame length: {self.porcupine.frame_length}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Porcupine: {e}")
            return False
    
    def process_audio(self, audio_frame: np.ndarray) -> bool:
        """Process audio frame and detect wake word."""
        if not self.porcupine:
            return False
        
        try:
            # Ensure audio frame is the correct length
            if len(audio_frame) != self.porcupine.frame_length:
                return False
            
            # Convert to int16 if needed
            if audio_frame.dtype != np.int16:
                audio_frame = (audio_frame * 32767).astype(np.int16)
            
            keyword_index = self.porcupine.process(audio_frame)
            
            if keyword_index >= 0:
                logger.info(f"Wake word '{self.keyword}' detected!")
                if self._detection_callback:
                    self._detection_callback(self.keyword)
                return True
                
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
        
        return False
    
    def set_detection_callback(self, callback: Callable[[str], None]):
        """Set callback function to be called when wake word is detected."""
        self._detection_callback = callback
    
    def get_frame_length(self) -> int:
        """Get the required frame length for Porcupine."""
        return self.porcupine.frame_length if self.porcupine else 512
    
    def get_sample_rate(self) -> int:
        """Get the required sample rate for Porcupine."""
        return self.porcupine.sample_rate if self.porcupine else 16000
    
    def cleanup(self):
        """Clean up Porcupine resources."""
        if self.porcupine:
            self.porcupine.delete()
            self.porcupine = None
            logger.info("Wake word detector cleaned up")