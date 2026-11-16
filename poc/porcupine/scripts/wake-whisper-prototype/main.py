#!/usr/bin/env python3

import signal
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from loguru import logger

from src.config import Config
from src.wake_word import WakeWordDetector
from src.audio_recorder import AudioRecorder
from src.transcriber import WhisperTranscriber
from src.database import VoiceRequestDB

class VoiceAssistant:
    def __init__(self):
        # Load configuration
        Config.validate()
        
        # Configure logging
        logger.remove()
        logger.add(sys.stderr, level=Config.LOG_LEVEL)
        logger.add("logs/voice_assistant_{time}.log", rotation="1 day", level=Config.LOG_LEVEL)
        
        # Initialize components
        self.wake_detector = WakeWordDetector(
            Config.PICOVOICE_ACCESS_KEY,
            Config.WAKE_WORD
        )
        self.audio_recorder = AudioRecorder(
            sample_rate=16000,
            chunk_size=512
        )
        self.transcriber = WhisperTranscriber(
            model_name=Config.WHISPER_MODEL,
            language=Config.WHISPER_LANGUAGE
        )
        self.database = VoiceRequestDB(Config.DATABASE_PATH)
        
        # State management
        self.is_running = False
        self.is_listening = False
        self.listen_start_time = None
        
        # Threading
        self.wake_thread = None
        self.transcribe_thread = None
        
    def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Voice Assistant...")
        
        # Initialize wake word detector
        if not self.wake_detector.initialize():
            logger.error("Failed to initialize wake word detector")
            return False
        
        # Set wake word detection callback
        self.wake_detector.set_detection_callback(self.on_wake_word_detected)
        
        # Initialize audio recorder
        if not self.audio_recorder.start_stream():
            logger.error("Failed to start audio stream")
            return False
        
        # Initialize Whisper
        if not self.transcriber.initialize():
            logger.error("Failed to initialize Whisper")
            return False
        
        logger.info("Voice Assistant initialized successfully")
        return True
    
    def on_wake_word_detected(self, wake_word: str):
        """Handle wake word detection."""
        if self.is_listening:
            logger.info("Already listening, ignoring wake word")
            return
        
        logger.info(f"Wake word detected: {wake_word}")
        self.is_listening = True
        self.listen_start_time = time.time()
        
        # Start recording
        self.audio_recorder.start_recording()
        
        # Start transcription thread
        self.transcribe_thread = threading.Thread(target=self.handle_voice_input)
        self.transcribe_thread.start()
    
    def handle_voice_input(self):
        """Handle voice input after wake word detection."""
        logger.info("Listening for voice input...")
        
        # Wait for voice input with silence detection
        while self.is_listening and self.is_running:
            # Check for maximum recording duration
            if time.time() - self.listen_start_time > Config.MAX_RECORDING_SECONDS:
                logger.info("Maximum recording duration reached")
                break
            
            # Check for silence
            if self.audio_recorder.detect_silence_end(
                Config.SILENCE_DURATION_SECONDS,
                Config.SILENCE_THRESHOLD
            ):
                logger.info("Silence detected, ending recording")
                break
            
            time.sleep(0.1)
        
        # Stop recording and get audio data
        audio_data, duration = self.audio_recorder.stop_recording()
        self.is_listening = False
        
        if audio_data is None or duration < 0.5:
            logger.warning("No valid audio recorded")
            return
        
        # Transcribe audio
        logger.info(f"Processing {duration:.2f}s of audio...")
        result = self.transcriber.transcribe(audio_data, sample_rate=16000)
        
        if result.get("text"):
            # Save to database
            audio_file_path = None
            if Config.SAVE_AUDIO_FILES:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                audio_file_path = Config.AUDIO_SAVE_PATH / f"audio_{timestamp}.wav"
                self.transcriber.save_audio(audio_data, audio_file_path)
            
            db_data = {
                "wake_word": Config.WAKE_WORD,
                "audio_duration_seconds": duration,
                "transcribed_text": result["text"],
                "confidence": None,  # Whisper doesn't provide confidence
                "language": result.get("language"),
                "audio_file_path": str(audio_file_path) if audio_file_path else None,
                "processing_time_ms": result.get("processing_time_ms")
            }
            
            request_id = self.database.insert_request(db_data)
            
            # Display result
            print(f"\n{'='*60}")
            print(f"🎤 Transcription: {result['text']}")
            print(f"⏱️  Duration: {duration:.2f}s | Processing: {result.get('processing_time_ms', 0)}ms")
            print(f"💾 Saved as request ID: {request_id}")
            print(f"{'='*60}\n")
        else:
            logger.warning("No text transcribed")
    
    def run(self):
        """Main loop."""
        self.is_running = True
        logger.info(f"Voice Assistant started. Say '{Config.WAKE_WORD}' to activate.")
        print(f"\n🎤 Listening for wake word: '{Config.WAKE_WORD}'")
        print("Press Ctrl+C to stop\n")
        
        # Start wake word detection in main thread
        try:
            while self.is_running:
                # Read audio chunk
                audio_chunk = self.audio_recorder.read_chunk()
                if audio_chunk is None:
                    time.sleep(0.01)
                    continue
                
                # Process for wake word detection if not currently listening
                if not self.is_listening:
                    # Ensure correct frame length for Porcupine
                    frame_length = self.wake_detector.get_frame_length()
                    if len(audio_chunk) == frame_length:
                        self.wake_detector.process_audio(audio_chunk)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        
        self.stop()
    
    def stop(self):
        """Stop the voice assistant."""
        logger.info("Stopping Voice Assistant...")
        self.is_running = False
        self.is_listening = False
        
        # Wait for threads to finish
        if self.transcribe_thread and self.transcribe_thread.is_alive():
            self.transcribe_thread.join(timeout=5)
        
        # Show statistics
        stats = self.database.get_stats()
        if stats:
            total, avg_duration, avg_processing = stats
            print(f"\n📊 Session Statistics:")
            print(f"   Total requests: {total}")
            if total > 0:
                print(f"   Average duration: {avg_duration:.2f}s")
                print(f"   Average processing time: {avg_processing:.0f}ms")
        
        # Cleanup
        self.wake_detector.cleanup()
        self.audio_recorder.cleanup()
        self.database.close()
        
        logger.info("Voice Assistant stopped")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\nShutting down...")
    sys.exit(0)

def main():
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run voice assistant
    assistant = VoiceAssistant()
    
    if not assistant.initialize():
        logger.error("Failed to initialize Voice Assistant")
        return 1
    
    assistant.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
