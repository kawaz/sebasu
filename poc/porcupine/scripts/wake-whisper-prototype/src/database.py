import duckdb
from datetime import datetime
from pathlib import Path
from loguru import logger
from typing import Optional, Dict, Any

class VoiceRequestDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self._init_db()
    
    def _init_db(self):
        """Initialize database and create tables if they don't exist."""
        try:
            self.conn = duckdb.connect(str(self.db_path))
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS voice_requests (
                    id INTEGER PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    wake_word TEXT,
                    audio_duration_seconds REAL,
                    transcribed_text TEXT,
                    confidence REAL,
                    language TEXT,
                    audio_file_path TEXT,
                    processing_time_ms INTEGER
                )
            """)
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def insert_request(self, data: Dict[str, Any]) -> Optional[int]:
        """Insert a new voice request record."""
        try:
            cursor = self.conn.execute("""
                INSERT INTO voice_requests (
                    wake_word,
                    audio_duration_seconds,
                    transcribed_text,
                    confidence,
                    language,
                    audio_file_path,
                    processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """, (
                data.get('wake_word'),
                data.get('audio_duration_seconds'),
                data.get('transcribed_text'),
                data.get('confidence'),
                data.get('language'),
                data.get('audio_file_path'),
                data.get('processing_time_ms')
            ))
            
            result = cursor.fetchone()
            request_id = result[0] if result else None
            
            logger.info(f"Inserted voice request ID: {request_id}, text: {data.get('transcribed_text', '')[:50]}...")
            return request_id
            
        except Exception as e:
            logger.error(f"Failed to insert voice request: {e}")
            return None
    
    def get_recent_requests(self, limit: int = 10):
        """Get recent voice requests."""
        try:
            cursor = self.conn.execute("""
                SELECT * FROM voice_requests
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get recent requests: {e}")
            return []
    
    def get_stats(self):
        """Get database statistics."""
        try:
            cursor = self.conn.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    AVG(audio_duration_seconds) as avg_duration,
                    AVG(processing_time_ms) as avg_processing_time
                FROM voice_requests
            """)
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return None
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")