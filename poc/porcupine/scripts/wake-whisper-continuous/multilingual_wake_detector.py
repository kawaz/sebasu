"""多言語対応ウェイクワード検出モジュール"""
import pvporcupine
import numpy as np
from pathlib import Path
from loguru import logger
from typing import List, Dict, Optional, Callable
from config import Config
from porcupine_helper import create_porcupine_with_auto_model, detect_language_from_ppn

class MultilingualWakeWordDetector:
    """複数言語のウェイクワードを同時に検出するクラス"""
    
    def __init__(self):
        self.detectors = {}  # {language: porcupine_instance}
        self.wake_words_by_lang = {}  # {language: [wake_words]}
        self.detection_callback = None
        self.audio_recorder = None  # タイムスタンプ取得用
        
    def initialize(self):
        """多言語ウェイクワード検出器を初期化"""
        try:
            # 使用するウェイクワードを取得
            all_wake_words = Config.get_wake_words()
            
            if not all_wake_words:
                raise ValueError("使用可能なウェイクワードがありません")
            
            # 言語別にグループ化
            wake_words_by_language = {}
            
            for wake_word in all_wake_words:
                if wake_word['type'] == 'custom':
                    # カスタムppnファイルから言語を検出
                    language = detect_language_from_ppn(wake_word['path'])
                    if language not in wake_words_by_language:
                        wake_words_by_language[language] = []
                    wake_words_by_language[language].append(wake_word)
                else:
                    # ビルトインキーワードは英語と仮定
                    if 'en' not in wake_words_by_language:
                        wake_words_by_language['en'] = []
                    wake_words_by_language['en'].append(wake_word)
            
            # 言語ごとにPorcupineインスタンスを作成
            for language, wake_words in wake_words_by_language.items():
                logger.info(f"言語 '{language}' 用の検出器を作成中...")
                
                keyword_paths = []
                keywords = []
                sensitivities = []
                
                for wake_word in wake_words:
                    if wake_word['type'] == 'custom':
                        keyword_paths.append(wake_word['path'])
                        sensitivities.append(Config.WAKE_SENSITIVITY)
                        logger.info(f"  - カスタム: {wake_word['name']}")
                    else:
                        keywords.append(wake_word['keyword'])
                        sensitivities.append(Config.WAKE_SENSITIVITY)
                        logger.info(f"  - ビルトイン: {wake_word['name']}")
                
                # Porcupineインスタンスを作成
                if keyword_paths and not keywords:
                    # カスタムppnのみ
                    detector = create_porcupine_with_auto_model(
                        access_key=Config.PICOVOICE_ACCESS_KEY,
                        keyword_paths=keyword_paths,
                        sensitivities=sensitivities
                    )
                elif keywords and not keyword_paths:
                    # ビルトインのみ
                    detector = pvporcupine.create(
                        access_key=Config.PICOVOICE_ACCESS_KEY,
                        keywords=keywords,
                        sensitivities=sensitivities
                    )
                else:
                    # 混在の場合はビルトインのみ使用
                    logger.warning(f"言語 '{language}': カスタムとビルトインの混在は未サポート。ビルトインのみ使用。")
                    detector = pvporcupine.create(
                        access_key=Config.PICOVOICE_ACCESS_KEY,
                        keywords=keywords,
                        sensitivities=sensitivities[len(keyword_paths):]
                    )
                    wake_words = [w for w in wake_words if w['type'] != 'custom']
                
                self.detectors[language] = detector
                self.wake_words_by_lang[language] = wake_words
                
                logger.info(f"言語 '{language}' 検出器初期化完了: {len(wake_words)}個のウェイクワード")
            
            logger.info(f"多言語検出器初期化完了: {len(self.detectors)}言語")
            return True
            
        except Exception as e:
            logger.error(f"多言語ウェイクワード検出器の初期化エラー: {e}")
            return False
    
    def process_audio(self, audio_frame: np.ndarray) -> Optional[Dict[str, str]]:
        """音声フレームを全ての言語検出器で処理"""
        if not self.detectors:
            return None
        
        try:
            # フレームサイズの確認（全ての検出器で同じはず）
            expected_frame_length = next(iter(self.detectors.values())).frame_length
            if len(audio_frame) != expected_frame_length:
                return None
            
            # int16に変換（必要な場合）
            if audio_frame.dtype != np.int16:
                audio_frame = (audio_frame * 32767).astype(np.int16)
            
            # 各言語の検出器で処理
            for language, detector in self.detectors.items():
                keyword_index = detector.process(audio_frame)
                
                if keyword_index >= 0:
                    # ウェイクワードが検出された
                    detected_word = self.wake_words_by_lang[language][keyword_index]
                    
                    # タイムスタンプ情報を追加（audio_recorderから取得）
                    if self.audio_recorder:
                        detected_word['timestamp_end'] = self.audio_recorder.get_current_timestamp()
                        # ウェイクワードの長さを推定（約1.5秒と仮定）
                        detected_word['timestamp_start'] = max(0, detected_word['timestamp_end'] - 1.5)
                    else:
                        detected_word['timestamp_start'] = 0
                        detected_word['timestamp_end'] = 0
                    
                    logger.info(f"ウェイクワード検出: {detected_word['name']} "
                               f"(言語: {language}, タイプ: {detected_word['type']}, "
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
        if self.detectors:
            return next(iter(self.detectors.values())).frame_length
        return 512
    
    def get_sample_rate(self) -> int:
        """必要なサンプルレートを取得"""
        if self.detectors:
            return next(iter(self.detectors.values())).sample_rate
        return 16000
    
    def get_supported_languages(self) -> List[str]:
        """サポートしている言語のリストを返す"""
        return list(self.detectors.keys())
    
    def get_all_wake_words(self) -> List[Dict[str, str]]:
        """全ての登録されたウェイクワードを返す"""
        all_words = []
        for wake_words in self.wake_words_by_lang.values():
            all_words.extend(wake_words)
        return all_words
    
    def cleanup(self):
        """リソースをクリーンアップ"""
        for language, detector in self.detectors.items():
            detector.delete()
            logger.info(f"言語 '{language}' の検出器をクリーンアップしました")
        self.detectors.clear()
        self.wake_words_by_lang.clear()