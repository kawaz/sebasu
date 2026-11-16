#!/usr/bin/env python3
"""ウェイクワード + Whisper連続記録プロトタイプ"""

import signal
import sys
import time
import threading
import uuid
import os
from datetime import datetime
from loguru import logger

from config import Config
from wake_detector_auto import create_wake_detector
from audio_recorder import MultiLevelAudioRecorder
from whisper_processor import WhisperProcessor
from database import VoiceRequestDB

class VoiceAssistant:
    def __init__(self):
        # 設定の検証
        Config.validate()
        
        # ロギング設定
        logger.remove()
        logger.add(sys.stderr, level=Config.LOG_LEVEL)
        
        # セッションID
        self.session_id = str(uuid.uuid4())[:8]
        logger.info(f"セッション開始: {self.session_id}")
        
        # コンポーネント初期化
        self.wake_detector = create_wake_detector()
        self.audio_recorder = MultiLevelAudioRecorder()
        self.whisper_processor = WhisperProcessor()
        self.database = VoiceRequestDB(Config.DATABASE_PATH)
        
        # 状態管理
        self.is_running = False
        self.is_listening = False
        self.current_wake_word = None
        
        # スレッド
        self.result_processor_thread = None
        self.transcribe_thread = None
    
    def initialize(self):
        """全コンポーネントを初期化"""
        logger.info("Voice Assistant初期化中...")
        
        # ウェイクワード検出器
        if not self.wake_detector.initialize():
            logger.error("ウェイクワード検出器の初期化に失敗")
            return False
        
        # コールバック設定
        self.wake_detector.set_detection_callback(self.on_wake_word_detected)
        
        # AudioRecorderの参照を渡す（タイムスタンプ取得用）
        if hasattr(self.wake_detector, 'set_audio_recorder'):
            self.wake_detector.set_audio_recorder(self.audio_recorder)
        
        # 音声録音器
        if not self.audio_recorder.start_stream():
            logger.error("音声ストリームの開始に失敗")
            return False
        
        # Whisperプロセッサ
        self.whisper_processor.start()
        
        # 結果処理スレッドを開始
        self.result_processor_thread = threading.Thread(
            target=self.process_whisper_results,
            daemon=True
        )
        self.result_processor_thread.start()
        
        logger.info("Voice Assistant初期化完了")
        return True
    
    def on_wake_word_detected(self, wake_word_info):
        """ウェイクワード検出時の処理"""
        if self.is_listening:
            logger.info("既に聴取中です")
            return
        
        self.current_wake_word = wake_word_info
        self.is_listening = True
        
        # 音声録音開始
        self.audio_recorder.start_recording()
        
        # 音声フィードバック
        if Config.WAKE_SOUND_ENABLED:
            # macOSのsayコマンドで短い音を出す
            threading.Thread(
                target=lambda: os.system('afplay /System/Library/Sounds/Tink.aiff 2>/dev/null || echo -ne "\a"'),
                daemon=True
            ).start()
        
        # フィードバック表示
        print(f"\n{'='*60}")
        print(f"🎤 ウェイクワード検出: {wake_word_info['name']} "
              f"({wake_word_info['type']})")
        print(f"{'='*60}")
        
        # 音声処理スレッドを開始
        self.transcribe_thread = threading.Thread(target=self.handle_voice_input, daemon=True)
        self.transcribe_thread.start()
    
    def handle_voice_input(self):
        """音声入力を処理"""
        logger.info("音声入力処理開始")
        last_process_time = {level: 0 for level in Config.BUFFER_LEVELS}
        
        # ウェイクワードの終了時刻を取得
        wake_word_end_time = self.current_wake_word.get('timestamp_end', 0) if self.current_wake_word else 0
        silence_ignore_until = wake_word_end_time + Config.INITIAL_SILENCE_IGNORE
        
        logger.info(f"ウェイクワード終了時刻: {wake_word_end_time:.2f}秒, "
                   f"無音検出開始時刻: {silence_ignore_until:.2f}秒")
        
        while self.is_listening and self.is_running:
            current_time = time.time()
            current_timestamp = self.audio_recorder.get_current_timestamp()
            
            # 各レベルごとに適切な間隔で処理
            chunks = self.audio_recorder.get_audio_chunks()
            for chunk in chunks:
                # オーバーラップを考慮した処理間隔
                level_config = Config.BUFFER_LEVELS[chunk.level]
                process_interval = level_config['duration'] - level_config.get('overlap', 1.0)
                
                # 前回の処理から十分な時間が経過している場合のみ処理
                if current_time - last_process_time[chunk.level] >= process_interval:
                    # レベルごとに色分けして表示
                    color = level_config['color']
                    print(f"\n{color}■{chunk.level.upper()}: "
                          f"{chunk.duration:.1f}秒 処理中...\033[0m")
                    
                    # Whisperに送信（ウェイクワード情報も含める）
                    self.whisper_processor.submit_task(
                        audio_data=chunk.audio,
                        level=chunk.level,
                        duration=chunk.duration,
                        timestamp=chunk.timestamp,
                        wake_word_end_time=wake_word_end_time
                    )
                    
                    last_process_time[chunk.level] = current_time
            
            # 無音検出
            audio_chunk = self.audio_recorder.read_chunk()
            if audio_chunk is not None:
                # ウェイクワード後の無音無視期間中はスキップ
                if current_timestamp <= silence_ignore_until:
                    continue
                    
                # 無音検出（連続した無音時間をチェック）
                if self.audio_recorder.detect_silence(audio_chunk):
                    logger.info(f"無音を検出 - 録音終了 (現在時刻: {current_timestamp:.2f}秒)")
                    break
            
            # 最大録音時間チェック
            if self.audio_recorder.get_recording_duration() > 30:
                logger.info("最大録音時間に到達")
                break
            
            time.sleep(0.1)
        
        # 最終的なultraチャンクを処理
        ultra_chunk = self.audio_recorder.get_ultra_chunk()
        if ultra_chunk and ultra_chunk.duration > 0.5:
            color = Config.BUFFER_LEVELS['ultra']['color']
            print(f"\n{color}■ULTRA: {ultra_chunk.duration:.1f}秒 処理中...\033[0m")
            
            self.whisper_processor.submit_task(
                audio_data=ultra_chunk.audio,
                level='ultra',
                duration=ultra_chunk.duration,
                timestamp=ultra_chunk.timestamp
            )
        
        # 録音停止
        self.audio_recorder.stop_recording()
        self.is_listening = False
        
        print("\n" + "="*60 + "\n")
    
    def process_whisper_results(self):
        """Whisperの結果を処理するスレッド"""
        while self.is_running:
            results = self.whisper_processor.get_results()
            
            for result in results:
                if result.text:
                    # タイムスタンプ情報をログ
                    logger.debug(f"認識結果: '{result.text}' (タイムスタンプ: {result.timestamp:.2f}秒)")
                    
                    # データベースに保存
                    wake_word_name = self.current_wake_word['name'] if self.current_wake_word else None
                    db_data = {
                        'wake_word': wake_word_name,
                        'wake_word_type': self.current_wake_word['type'] if self.current_wake_word else None,
                        'audio_duration_seconds': result.duration,
                        'transcribed_text': result.text,
                        'transcription_level': result.level,
                        'confidence': None,
                        'language': result.language,
                        'processing_time_ms': result.processing_time_ms,
                        'worker_id': result.worker_id,
                        'session_id': self.session_id,
                        'timestamp_start': result.timestamp,
                        'timestamp_end': result.timestamp + result.duration
                    }
                    
                    request_id = self.database.insert_request(db_data)
                    
                    # 結果表示（タイムスタンプ付き）
                    color = Config.BUFFER_LEVELS[result.level]['color']
                    print(f"\n{color}[{result.level.upper()}] {result.text}\033[0m")
                    print(f"  ⏱️  {result.duration:.1f}秒 ({result.timestamp:.1f}-{result.timestamp + result.duration:.1f}秒) | "
                          f"処理: {result.processing_time_ms}ms | "
                          f"ワーカー: {result.worker_id} | "
                          f"ID: {request_id}")
            
            time.sleep(0.1)
    
    def run(self):
        """メインループ"""
        self.is_running = True
        
        # 使用可能なウェイクワードを表示
        print(f"\n🎤 Voice Assistant起動")
        print(f"セッションID: {self.session_id}")
        
        if hasattr(self.wake_detector, 'get_all_wake_words'):
            # 多言語検出器の場合
            print(f"\n多言語モード - サポート言語: {', '.join(self.wake_detector.get_supported_languages())}")
            wake_words = self.wake_detector.get_all_wake_words()
        else:
            # 通常の検出器の場合
            wake_words = Config.get_wake_words()
        
        print(f"\n使用可能なウェイクワード:")
        for ww in wake_words:
            print(f"  - {ww['name']} ({ww['type']})")
        print(f"\nCtrl+Cで終了\n")
        
        try:
            while self.is_running:
                audio_chunk = self.audio_recorder.read_chunk()
                
                if audio_chunk is None:
                    time.sleep(0.01)
                    continue
                
                # ウェイクワード検出（聴取中でない場合のみ）
                if not self.is_listening:
                    frame_length = self.wake_detector.get_frame_length()
                    if len(audio_chunk) == frame_length:
                        self.wake_detector.process_audio(audio_chunk)
                
        except KeyboardInterrupt:
            logger.info("キーボード割り込み")
        except Exception as e:
            logger.error(f"メインループエラー: {e}")
        
        self.stop()
    
    def stop(self):
        """終了処理"""
        logger.info("Voice Assistant停止中...")
        self.is_running = False
        
        # スレッドの終了を待つ
        if self.result_processor_thread and self.result_processor_thread.is_alive():
            logger.info("結果処理スレッドの終了を待機中...")
            self.result_processor_thread.join(timeout=2)
        if self.transcribe_thread and self.transcribe_thread.is_alive():
            logger.info("音声処理スレッドの終了を待機中...")
            self.transcribe_thread.join(timeout=2)
        
        # 統計情報を表示
        stats = self.database.get_session_stats(self.session_id)
        if stats and stats.get('total_requests', 0) > 0:
            print(f"\n📊 セッション統計:")
            print(f"  合計リクエスト数: {stats['total_requests']}")
            print(f"  使用ウェイクワード数: {stats['unique_wake_words']}")
            print(f"  平均音声長: {stats['avg_duration']:.1f}秒")
            print(f"  最長音声: {stats['max_duration']:.1f}秒")
            print(f"  平均処理時間: {stats['avg_processing_time']:.0f}ms")
            print(f"  使用レベル数: {stats['levels_used']}")
        
        # 最近のリクエストを表示
        recent = self.database.get_recent_requests(5)
        if recent:
            print(f"\n📝 最近の認識結果:")
            for req in recent:
                print(f"  [{req['transcription_level']}] {req['transcribed_text'][:50]}...")
        
        # クリーンアップ
        self.wake_detector.cleanup()
        self.audio_recorder.cleanup()
        self.whisper_processor.stop()
        self.database.close()
        
        logger.info("Voice Assistant停止完了")

def main():
    """メイン関数"""
    assistant = None
    
    # シグナルハンドラ設定
    def signal_handler(sig, frame):
        print("\n\nシャットダウン中...")
        if assistant:
            assistant.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Voice Assistantを起動
    assistant = VoiceAssistant()
    
    if not assistant.initialize():
        logger.error("初期化に失敗しました")
        return 1
    
    assistant.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
