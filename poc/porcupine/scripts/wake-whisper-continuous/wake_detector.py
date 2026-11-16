"""Porcupineウェイクワード検出モジュール（改良版）"""
import pvporcupine
import numpy as np
from pathlib import Path
from loguru import logger
from typing import List, Dict, Optional, Callable
from config import Config
from porcupine_helper import create_porcupine_with_auto_model

class WakeWordDetector:
    def __init__(self):
        self.porcupine = None
        self.wake_words = []
        self.detection_callback = None
        self.audio_recorder = None  # タイムスタンプ取得用
        
    def initialize(self):
        """ウェイクワード検出器を初期化"""
        try:
            # 使用するウェイクワードを取得
            self.wake_words = Config.get_wake_words()
            
            if not self.wake_words:
                raise ValueError("使用可能なウェイクワードがありません")
            
            # Porcupineの初期化パラメータを準備
            keyword_paths = []
            keywords = []
            sensitivities = []
            
            for wake_word in self.wake_words:
                if wake_word['type'] == 'custom':
                    # カスタムppnファイル
                    keyword_paths.append(wake_word['path'])
                    sensitivities.append(Config.WAKE_SENSITIVITY)
                    logger.info(f"カスタムウェイクワード読み込み: {wake_word['name']}")
                else:
                    # ビルトインキーワード
                    keywords.append(wake_word['keyword'])
                    sensitivities.append(Config.WAKE_SENSITIVITY)
                    logger.info(f"ビルトインウェイクワード使用: {wake_word['name']}")
            
            # Porcupineインスタンスを作成
            if keyword_paths and keywords:
                # カスタムとビルトインの混在はサポートされていないので、ビルトインのみ使用
                logger.warning("カスタムppnファイルとビルトインキーワードの混在は未サポート。ビルトインキーワードのみ使用します。")
                self.porcupine = pvporcupine.create(
                    access_key=Config.PICOVOICE_ACCESS_KEY,
                    keywords=keywords,
                    sensitivities=sensitivities[len(keyword_paths):]
                )
                # カスタムppnを除外
                self.wake_words = [w for w in self.wake_words if w['type'] != 'custom']
            elif keyword_paths:
                # カスタムppnファイルを使用（言語に応じたモデルを自動取得）
                try:
                    # ヘルパーを使って適切な言語モデルでPorcupineを作成
                    self.porcupine = create_porcupine_with_auto_model(
                        access_key=Config.PICOVOICE_ACCESS_KEY,
                        keyword_paths=keyword_paths,
                        sensitivities=sensitivities
                    )
                except Exception as e:
                    logger.warning(f"カスタムppnファイルの読み込みに失敗: {e}")
                    logger.info("ビルトインキーワードにフォールバックします")
                    # ビルトインキーワードにフォールバック
                    self.wake_words = [w for w in Config.get_wake_words() if w['type'] == 'builtin']
                    if self.wake_words:
                        keywords = [w['keyword'] for w in self.wake_words]
                        sensitivities = [Config.WAKE_SENSITIVITY] * len(keywords)
                        self.porcupine = pvporcupine.create(
                            access_key=Config.PICOVOICE_ACCESS_KEY,
                            keywords=keywords,
                            sensitivities=sensitivities
                        )
            else:
                # ビルトインキーワードのみ
                self.porcupine = pvporcupine.create(
                    access_key=Config.PICOVOICE_ACCESS_KEY,
                    keywords=keywords,
                    sensitivities=sensitivities
                )
            
            logger.info(f"Porcupine初期化完了: "
                       f"サンプルレート={self.porcupine.sample_rate}Hz, "
                       f"フレーム長={self.porcupine.frame_length}")
            
            return True
            
        except Exception as e:
            logger.error(f"ウェイクワード検出器の初期化エラー: {e}")
            return False
    
    def process_audio(self, audio_frame: np.ndarray) -> Optional[Dict[str, str]]:
        """音声フレームを処理してウェイクワードを検出"""
        if not self.porcupine:
            return None
        
        try:
            # フレームサイズの確認
            if len(audio_frame) != self.porcupine.frame_length:
                return None
            
            # int16に変換（必要な場合）
            if audio_frame.dtype != np.int16:
                audio_frame = (audio_frame * 32767).astype(np.int16)
            
            # ウェイクワード検出
            keyword_index = self.porcupine.process(audio_frame)
            
            if keyword_index >= 0:
                # 検出されたウェイクワードの情報を取得
                detected_word = self.wake_words[keyword_index]
                
                # タイムスタンプ情報を追加
                if self.audio_recorder:
                    detected_word['timestamp_end'] = self.audio_recorder.get_current_timestamp()
                    detected_word['timestamp_start'] = max(0, detected_word['timestamp_end'] - 1.5)
                else:
                    detected_word['timestamp_start'] = 0
                    detected_word['timestamp_end'] = 0
                
                logger.info(f"ウェイクワード検出: {detected_word['name']} "
                           f"(タイプ: {detected_word['type']}, "
                           f"時間: {detected_word['timestamp_start']:.2f}-{detected_word['timestamp_end']:.2f})")
                
                # コールバックを呼び出し
                if self.detection_callback:
                    self.detection_callback(detected_word)
                
                return detected_word
                
        except Exception as e:
            logger.error(f"音声処理エラー: {e}")
        
        return None
    
    def set_detection_callback(self, callback: Callable[[Dict[str, str]], None]):
        """ウェイクワード検出時のコールバックを設定"""
        self.detection_callback = callback
    
    def set_audio_recorder(self, audio_recorder):
        """AudioRecorderの参照を設定（タイムスタンプ取得用）"""
        self.audio_recorder = audio_recorder
    
    def get_frame_length(self) -> int:
        """必要なフレーム長を取得"""
        return self.porcupine.frame_length if self.porcupine else 512
    
    def get_sample_rate(self) -> int:
        """必要なサンプルレートを取得"""
        return self.porcupine.sample_rate if self.porcupine else 16000
    
    def cleanup(self):
        """リソースをクリーンアップ"""
        if self.porcupine:
            self.porcupine.delete()
            self.porcupine = None
            logger.info("ウェイクワード検出器をクリーンアップしました")