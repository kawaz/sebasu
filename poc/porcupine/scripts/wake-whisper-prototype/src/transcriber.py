import whisper
import numpy as np
import time
from pathlib import Path
from loguru import logger
from typing import Optional, Dict, Any
import tempfile
import wave

class WhisperTranscriber:
    def __init__(self, model_name: str = "base", language: str = "ja"):
        self.model_name = model_name
        self.language = language
        self.model = None
        
    def initialize(self):
        """Initialize Whisper model."""
        try:
            logger.info(f"Loading Whisper model: {self.model_name}")
            self.model = whisper.load_model(self.model_name)
            logger.info(f"Whisper model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False
    
    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
        """Transcribe audio data to text."""
        if self.model is None:
            logger.error("Whisper model not initialized")
            return {"text": "", "error": "Model not initialized"}
        
        start_time = time.time()
        
        try:
            # Save audio data to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name
                
                # Write WAV file
                with wave.open(tmp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_data.tobytes())
                
                # Transcribe
                logger.info(f"Transcribing audio ({len(audio_data)/sample_rate:.2f}s)...")
                result = self.model.transcribe(
                    tmp_path,
                    language=self.language,
                    fp16=False  # Disable FP16 for CPU
                )
                
                processing_time = int((time.time() - start_time) * 1000)
                
                # Clean up temp file
                Path(tmp_path).unlink()
                
                # Extract relevant information
                transcription = {
                    "text": result["text"].strip(),
                    "language": result.get("language", self.language),
                    "segments": result.get("segments", []),
                    "processing_time_ms": processing_time
                }
                
                logger.info(f"Transcription complete: '{transcription['text'][:50]}...' ({processing_time}ms)")
                return transcription
                
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                "text": "",
                "error": str(e),
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }
    
    def save_audio(self, audio_data: np.ndarray, file_path: Path, 
                   sample_rate: int = 16000) -> bool:
        """Save audio data to file."""
        try:
            with wave.open(str(file_path), 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data.tobytes())
            
            logger.info(f"Audio saved to: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
            return False