#!/usr/bin/env python3
"""
環境音に適応する音量調整システム
マイクレベルをモニタリングして、騒音レベルに応じて音量を動的に調整
"""
import numpy as np
import sounddevice as sd
import asyncio
import time
from typing import Optional, Tuple
from dataclasses import dataclass
from collections import deque
import statistics

@dataclass
class EnvironmentStatus:
    """環境状態"""
    noise_level: float  # dB
    location: str = "unknown"  # bedroom, living_room, kitchen
    time_of_day: str = "day"  # morning, day, evening, night, late_night
    activity: str = "quiet"  # quiet, conversation, tv_on, kids_playing, party
    
    def get_recommended_volume(self) -> float:
        """推奨音量を計算"""
        # ベース音量
        base_volume = 1.0
        
        # 時間帯による調整
        time_factors = {
            "late_night": 0.5,  # 深夜
            "night": 0.7,       # 夜
            "morning": 0.8,     # 早朝
            "day": 1.0,         # 日中
            "evening": 0.9      # 夕方
        }
        base_volume *= time_factors.get(self.time_of_day, 1.0)
        
        # 場所による調整
        location_factors = {
            "bedroom": 0.8,     # 寝室は控えめ
            "living_room": 1.0, # リビングは標準
            "kitchen": 1.2      # キッチンは少し大きめ
        }
        base_volume *= location_factors.get(self.location, 1.0)
        
        # 騒音レベルによる動的調整
        # 40dB（静か）〜 80dB（騒がしい）を想定
        if self.noise_level < 40:
            noise_factor = 0.8
        elif self.noise_level < 50:
            noise_factor = 1.0
        elif self.noise_level < 60:
            noise_factor = 1.2
        elif self.noise_level < 70:
            noise_factor = 1.5
        else:
            noise_factor = 2.0
            
        # アクティビティによる調整
        activity_factors = {
            "quiet": 1.0,
            "conversation": 1.3,
            "tv_on": 1.4,
            "kids_playing": 1.6,
            "party": 2.0
        }
        base_volume *= activity_factors.get(self.activity, 1.0)
        
        # 最終的な音量（0.3〜2.5の範囲に制限）
        return max(0.3, min(2.5, base_volume * noise_factor))

class AdaptiveVolumeController:
    """適応型音量コントローラー"""
    
    def __init__(self, sample_rate=44100, block_size=1024):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.noise_history = deque(maxlen=100)  # 最新100サンプルを保持
        self.calibration_offset = 0.0
        self.is_monitoring = False
        
    def calculate_db(self, audio_data: np.ndarray) -> float:
        """音圧レベル（dB）を計算"""
        # RMS (Root Mean Square) を計算
        rms = np.sqrt(np.mean(audio_data**2))
        
        # dBに変換（基準値を0.00002とする）
        if rms > 0:
            db = 20 * np.log10(rms / 0.00002)
        else:
            db = -np.inf
            
        return db + self.calibration_offset
    
    def analyze_audio_pattern(self, audio_data: np.ndarray) -> str:
        """音声パターンを分析してアクティビティを推定"""
        # 簡易的な分析（実際はもっと高度な処理が必要）
        db = self.calculate_db(audio_data)
        
        # 周波数成分の分析（簡易版）
        fft = np.fft.rfft(audio_data)
        freqs = np.fft.rfftfreq(len(audio_data), 1/self.sample_rate)
        
        # 人の声の周波数帯域（85-255Hz）のパワー
        voice_band = np.where((freqs > 85) & (freqs < 255))[0]
        voice_power = np.mean(np.abs(fft[voice_band]))
        
        # TVやスピーカーの特徴的な周波数
        media_band = np.where((freqs > 100) & (freqs < 4000))[0]
        media_power = np.mean(np.abs(fft[media_band]))
        
        # パターン判定
        if db < 40:
            return "quiet"
        elif voice_power > media_power * 1.5:
            return "conversation"
        elif media_power > voice_power * 2:
            return "tv_on"
        elif db > 65 and voice_power > media_power:
            return "kids_playing"
        else:
            return "quiet"
    
    async def monitor_environment(self, duration: float = 5.0) -> EnvironmentStatus:
        """環境音をモニタリング"""
        print(f"環境音を{duration}秒間モニタリング中...")
        
        samples = []
        start_time = time.time()
        
        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"オーディオエラー: {status}")
            samples.append(indata.copy())
        
        # 録音開始
        with sd.InputStream(callback=audio_callback,
                          channels=1,
                          samplerate=self.sample_rate,
                          blocksize=self.block_size):
            await asyncio.sleep(duration)
        
        # 分析
        if samples:
            all_samples = np.concatenate(samples)
            avg_db = self.calculate_db(all_samples)
            activity = self.analyze_audio_pattern(all_samples)
            
            # 時間帯を判定
            hour = time.localtime().tm_hour
            if 0 <= hour < 6:
                time_of_day = "late_night"
            elif 6 <= hour < 9:
                time_of_day = "morning"
            elif 9 <= hour < 17:
                time_of_day = "day"
            elif 17 <= hour < 21:
                time_of_day = "evening"
            else:
                time_of_day = "night"
            
            return EnvironmentStatus(
                noise_level=avg_db,
                time_of_day=time_of_day,
                activity=activity
            )
        else:
            return EnvironmentStatus(noise_level=50.0)
    
    def calibrate(self, quiet_room_db: float = 30.0):
        """静かな部屋での校正"""
        print("校正中... 静かな環境で実行してください")
        # 実際の実装では現在の環境音を測定して校正値を設定
        self.calibration_offset = quiet_room_db - 30.0

async def demo_adaptive_volume():
    """適応型音量のデモ"""
    controller = AdaptiveVolumeController()
    
    print("=== 適応型音量調整デモ ===\n")
    
    # 様々な環境をシミュレート
    test_scenarios = [
        EnvironmentStatus(30, "bedroom", "late_night", "quiet"),
        EnvironmentStatus(45, "bedroom", "morning", "quiet"),
        EnvironmentStatus(55, "living_room", "day", "tv_on"),
        EnvironmentStatus(65, "living_room", "evening", "kids_playing"),
        EnvironmentStatus(75, "living_room", "day", "party"),
    ]
    
    for env in test_scenarios:
        volume = env.get_recommended_volume()
        print(f"環境: {env.location} / {env.time_of_day} / {env.activity}")
        print(f"  騒音レベル: {env.noise_level:.1f} dB")
        print(f"  推奨音量: {volume:.1f}x")
        print()
    
    # 実際の環境をモニタリング
    print("\n実際の環境音をモニタリングします...")
    try:
        current_env = await controller.monitor_environment(3.0)
        volume = current_env.get_recommended_volume()
        print(f"\n現在の環境:")
        print(f"  騒音レベル: {current_env.noise_level:.1f} dB")
        print(f"  アクティビティ: {current_env.activity}")
        print(f"  推奨音量: {volume:.1f}x")
    except Exception as e:
        print(f"マイク入力エラー: {e}")

if __name__ == "__main__":
    asyncio.run(demo_adaptive_volume())