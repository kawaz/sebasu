"""DuckDBデータベース管理モジュール"""
import duckdb
from datetime import datetime
from pathlib import Path
from loguru import logger
from typing import Optional, Dict, Any, List

class VoiceRequestDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self._init_db()
    
    def _init_db(self):
        """データベースとテーブルの初期化"""
        try:
            self.conn = duckdb.connect(str(self.db_path))
            
            # より詳細なテーブル構造
            self.conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS voice_requests_id_seq;
                CREATE TABLE IF NOT EXISTS voice_requests (
                    id INTEGER PRIMARY KEY DEFAULT nextval('voice_requests_id_seq'),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    wake_word TEXT,
                    wake_word_type TEXT,  -- builtin or custom
                    audio_duration_seconds REAL,
                    transcribed_text TEXT,
                    transcription_level TEXT,  -- short, medium, long, ultra
                    confidence REAL,
                    language TEXT,
                    processing_time_ms INTEGER,
                    worker_id INTEGER,  -- 処理したワーカーID
                    session_id TEXT     -- セッションID
                )
            """)
            
            # インデックス作成
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON voice_requests(timestamp)
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session 
                ON voice_requests(session_id)
            """)
            
            logger.info(f"データベース初期化完了: {self.db_path}")
            
        except Exception as e:
            logger.error(f"データベース初期化エラー: {e}")
            raise
    
    def insert_request(self, data: Dict[str, Any]) -> Optional[int]:
        """音声リクエストを挿入"""
        try:
            cursor = self.conn.execute("""
                INSERT INTO voice_requests (
                    wake_word,
                    wake_word_type,
                    audio_duration_seconds,
                    transcribed_text,
                    transcription_level,
                    confidence,
                    language,
                    processing_time_ms,
                    worker_id,
                    session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """, (
                data.get('wake_word'),
                data.get('wake_word_type'),
                data.get('audio_duration_seconds'),
                data.get('transcribed_text'),
                data.get('transcription_level'),
                data.get('confidence'),
                data.get('language'),
                data.get('processing_time_ms'),
                data.get('worker_id'),
                data.get('session_id')
            ))
            
            result = cursor.fetchone()
            request_id = result[0] if result else None
            
            logger.debug(f"音声リクエスト挿入: ID={request_id}, "
                        f"テキスト='{data.get('transcribed_text', '')[:30]}...'")
            
            return request_id
            
        except Exception as e:
            logger.error(f"音声リクエスト挿入エラー: {e}")
            return None
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """セッションの統計情報を取得"""
        try:
            cursor = self.conn.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    COUNT(DISTINCT wake_word) as unique_wake_words,
                    AVG(audio_duration_seconds) as avg_duration,
                    MAX(audio_duration_seconds) as max_duration,
                    MIN(audio_duration_seconds) as min_duration,
                    AVG(processing_time_ms) as avg_processing_time,
                    COUNT(DISTINCT transcription_level) as levels_used
                FROM voice_requests
                WHERE session_id = ?
            """, (session_id,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'total_requests': result[0],
                    'unique_wake_words': result[1],
                    'avg_duration': result[2],
                    'max_duration': result[3],
                    'min_duration': result[4],
                    'avg_processing_time': result[5],
                    'levels_used': result[6]
                }
            return {}
            
        except Exception as e:
            logger.error(f"統計情報取得エラー: {e}")
            return {}
    
    def get_recent_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """最近のリクエストを取得"""
        try:
            cursor = self.conn.execute("""
                SELECT 
                    id,
                    timestamp,
                    wake_word,
                    transcribed_text,
                    transcription_level,
                    audio_duration_seconds,
                    processing_time_ms
                FROM voice_requests
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'wake_word': row[2],
                    'transcribed_text': row[3],
                    'transcription_level': row[4],
                    'audio_duration_seconds': row[5],
                    'processing_time_ms': row[6]
                })
            
            return results
            
        except Exception as e:
            logger.error(f"最近のリクエスト取得エラー: {e}")
            return []
    
    def close(self):
        """データベース接続を閉じる"""
        if self.conn:
            self.conn.close()
            logger.info("データベース接続を閉じました")