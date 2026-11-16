import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Picovoice
    PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
    WAKE_WORD = os.getenv("WAKE_WORD", "jarvis")
    
    # Whisper
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
    WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "ja")
    
    # Recording
    SILENCE_THRESHOLD = int(os.getenv("SILENCE_THRESHOLD", "500"))
    SILENCE_DURATION_SECONDS = float(os.getenv("SILENCE_DURATION_SECONDS", "1.5"))
    MAX_RECORDING_SECONDS = int(os.getenv("MAX_RECORDING_SECONDS", "30"))
    
    # Database
    DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "data/voice_requests.db"))
    
    # Audio
    SAVE_AUDIO_FILES = os.getenv("SAVE_AUDIO_FILES", "false").lower() == "true"
    AUDIO_SAVE_PATH = Path(os.getenv("AUDIO_SAVE_PATH", "data/audio/"))
    
    # Audio settings
    SAMPLE_RATE = 16000
    CHUNK_SIZE = 512
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls):
        if not cls.PICOVOICE_ACCESS_KEY:
            raise ValueError("PICOVOICE_ACCESS_KEY is required. Please set it in .env file.")
        
        # Create directories if they don't exist
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if cls.SAVE_AUDIO_FILES:
            cls.AUDIO_SAVE_PATH.mkdir(parents=True, exist_ok=True)