#!/usr/bin/env python3
"""
マルチセンサー環境適応システム
音・光・温度・人感センサーなどを統合した高度な環境認識
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
import numpy as np
from enum import Enum

class ActivityMode(str, Enum):
    """活動モード"""
    SLEEPING = "sleeping"          # 就寝中
    WAKING_UP = "waking_up"        # 起床中
    WORKING = "working"            # 作業中
    RELAXING = "relaxing"          # リラックス中
    COOKING = "cooking"            # 料理中
    WATCHING_TV = "watching_tv"    # TV視聴中
    PARTY = "party"                # パーティー
    AWAY = "away"                  # 外出中

@dataclass
class SensorData:
    """センサーデータ"""
    # 基本センサー
    noise_level_db: float          # 騒音レベル (dB)
    light_level_lux: float         # 照度 (lux)
    temperature_celsius: float     # 温度 (℃)
    humidity_percent: float        # 湿度 (%)
    
    # 追加センサー
    motion_detected: bool = False  # 人感センサー
    co2_ppm: Optional[float] = None  # CO2濃度
    presence_count: int = 0        # 人数（カメラやレーダーから）
    
    # 時刻情報
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class EnvironmentAnalyzer:
    """環境分析エンジン"""
    
    def analyze_activity(self, sensors: SensorData) -> ActivityMode:
        """センサーデータから活動モードを推定"""
        hour = sensors.timestamp.hour
        
        # 明るさベースの基本判定
        if sensors.light_level_lux < 1:  # ほぼ真っ暗
            if 22 <= hour or hour < 6:
                if not sensors.motion_detected:
                    return ActivityMode.SLEEPING
                else:
                    return ActivityMode.WAKING_UP
        
        # 明るさと音の組み合わせ
        if sensors.light_level_lux > 500:  # 明るい
            if sensors.noise_level_db > 65:
                if sensors.presence_count > 3:
                    return ActivityMode.PARTY
                else:
                    return ActivityMode.WATCHING_TV
            elif sensors.temperature_celsius > 25 and hour in range(10, 15):
                return ActivityMode.COOKING
            else:
                return ActivityMode.WORKING
        
        # 薄暗い（10-100 lux）
        elif 10 < sensors.light_level_lux < 100:
            if sensors.noise_level_db < 45:
                return ActivityMode.RELAXING
            elif sensors.noise_level_db > 60:
                return ActivityMode.WATCHING_TV
        
        # 人がいない
        if not sensors.motion_detected and sensors.presence_count == 0:
            return ActivityMode.AWAY
        
        return ActivityMode.RELAXING
    
    def get_context_hints(self, sensors: SensorData) -> Dict[str, Any]:
        """環境から文脈ヒントを生成"""
        hints = {}
        
        # 照明状態
        if sensors.light_level_lux < 1:
            hints['lighting'] = 'dark'
            hints['likely_sleeping'] = True
        elif sensors.light_level_lux < 50:
            hints['lighting'] = 'dim'
            hints['mood_lighting'] = True
        elif sensors.light_level_lux < 500:
            hints['lighting'] = 'normal'
        else:
            hints['lighting'] = 'bright'
        
        # 環境快適度
        if 20 <= sensors.temperature_celsius <= 26 and 40 <= sensors.humidity_percent <= 60:
            hints['comfort'] = 'optimal'
        elif sensors.temperature_celsius > 28:
            hints['comfort'] = 'too_hot'
        elif sensors.temperature_celsius < 18:
            hints['comfort'] = 'too_cold'
        
        # CO2レベル（眠気の指標）
        if sensors.co2_ppm:
            if sensors.co2_ppm > 2000:
                hints['air_quality'] = 'poor'
                hints['ventilation_needed'] = True
            elif sensors.co2_ppm > 1000:
                hints['air_quality'] = 'moderate'
        
        return hints

class AdaptiveVoiceController:
    """高度な音声制御"""
    
    def __init__(self):
        self.analyzer = EnvironmentAnalyzer()
    
    def calculate_voice_parameters(self, sensors: SensorData) -> Dict[str, float]:
        """センサーデータから音声パラメータを計算"""
        activity = self.analyzer.analyze_activity(sensors)
        context = self.analyzer.get_context_hints(sensors)
        
        params = {
            'volume': 1.0,
            'speed': 1.0,
            'pitch': 1.0,
            'tone': 'normal'  # normal, gentle, energetic, whisper
        }
        
        # アクティビティベースの調整
        if activity == ActivityMode.SLEEPING:
            params['volume'] = 0.0  # 無音
            params['tone'] = 'whisper'
        elif activity == ActivityMode.WAKING_UP:
            params['volume'] = 0.4
            params['speed'] = 0.9
            params['tone'] = 'gentle'
        elif activity == ActivityMode.PARTY:
            params['volume'] = 2.0
            params['speed'] = 1.1
            params['tone'] = 'energetic'
        elif activity == ActivityMode.WATCHING_TV:
            params['volume'] = 1.5
        elif activity == ActivityMode.WORKING:
            params['volume'] = 0.8
            params['tone'] = 'gentle'
        
        # 照明による微調整
        if sensors.light_level_lux < 10:  # とても暗い
            params['volume'] *= 0.5
            params['tone'] = 'whisper'
        elif sensors.light_level_lux < 50:  # 薄暗い
            params['volume'] *= 0.7
            params['tone'] = 'gentle'
        
        # 騒音レベルによる調整
        noise_factor = np.interp(
            sensors.noise_level_db,
            [30, 40, 50, 60, 70, 80],
            [0.7, 0.9, 1.0, 1.3, 1.6, 2.0]
        )
        params['volume'] *= noise_factor
        
        # 快適度による調整
        if context.get('comfort') == 'too_hot':
            params['speed'] *= 0.95  # 暑いときはゆっくり
        elif context.get('ventilation_needed'):
            params['volume'] *= 1.2  # 換気が必要なときは少し大きめに
        
        # 最終調整
        params['volume'] = max(0.0, min(2.5, params['volume']))
        params['speed'] = max(0.8, min(1.3, params['speed']))
        
        return params
    
    def generate_greeting(self, sensors: SensorData) -> str:
        """環境に応じた挨拶を生成"""
        activity = self.analyzer.analyze_activity(sensors)
        hour = sensors.timestamp.hour
        
        if activity == ActivityMode.SLEEPING:
            return ""  # 就寝中は無言
        elif activity == ActivityMode.WAKING_UP:
            return "おはようございます。良い朝ですね。"
        elif activity == ActivityMode.COOKING:
            return "お料理お疲れ様です。"
        elif activity == ActivityMode.PARTY:
            return "楽しそうですね！"
        elif sensors.light_level_lux < 10 and hour > 20:
            return "こんばんは。そろそろお休みの時間でしょうか。"
        else:
            return "こんにちは。"

# デモ関数
def demo_multi_sensor():
    """マルチセンサーのデモ"""
    controller = AdaptiveVoiceController()
    
    print("=== マルチセンサー環境適応デモ ===\n")
    
    # 様々なシナリオ
    scenarios = [
        {
            "name": "深夜の寝室（就寝中）",
            "sensors": SensorData(
                noise_level_db=35,
                light_level_lux=0.1,
                temperature_celsius=22,
                humidity_percent=50,
                motion_detected=False,
                timestamp=datetime(2024, 1, 1, 2, 0)
            )
        },
        {
            "name": "早朝の寝室（起床時）",
            "sensors": SensorData(
                noise_level_db=40,
                light_level_lux=5,
                temperature_celsius=20,
                humidity_percent=45,
                motion_detected=True,
                timestamp=datetime(2024, 1, 1, 6, 30)
            )
        },
        {
            "name": "昼間のリビング（TV視聴中）",
            "sensors": SensorData(
                noise_level_db=65,
                light_level_lux=300,
                temperature_celsius=24,
                humidity_percent=55,
                motion_detected=True,
                presence_count=2,
                timestamp=datetime(2024, 1, 1, 14, 0)
            )
        },
        {
            "name": "夜のリビング（ムード照明）",
            "sensors": SensorData(
                noise_level_db=45,
                light_level_lux=30,
                temperature_celsius=23,
                humidity_percent=50,
                motion_detected=True,
                timestamp=datetime(2024, 1, 1, 21, 0)
            )
        },
        {
            "name": "パーティー中",
            "sensors": SensorData(
                noise_level_db=75,
                light_level_lux=800,
                temperature_celsius=26,
                humidity_percent=65,
                motion_detected=True,
                presence_count=8,
                co2_ppm=1800,
                timestamp=datetime(2024, 1, 1, 20, 0)
            )
        }
    ]
    
    for scenario in scenarios:
        print(f"\n【{scenario['name']}】")
        sensors = scenario['sensors']
        
        # 活動モード分析
        activity = controller.analyzer.analyze_activity(sensors)
        context = controller.analyzer.get_context_hints(sensors)
        
        print(f"センサー値:")
        print(f"  照度: {sensors.light_level_lux:.1f} lux")
        print(f"  騒音: {sensors.noise_level_db:.1f} dB")
        print(f"  温度: {sensors.temperature_celsius:.1f}°C")
        print(f"  人数: {sensors.presence_count}人")
        
        print(f"\n推定状況:")
        print(f"  活動: {activity.value}")
        print(f"  照明: {context.get('lighting', 'unknown')}")
        print(f"  快適度: {context.get('comfort', 'normal')}")
        
        # 音声パラメータ
        params = controller.calculate_voice_parameters(sensors)
        greeting = controller.generate_greeting(sensors)
        
        print(f"\n音声設定:")
        print(f"  音量: {params['volume']:.1f}x")
        print(f"  速度: {params['speed']:.1f}x")
        print(f"  トーン: {params['tone']}")
        if greeting:
            print(f"  挨拶: 「{greeting}」")
        else:
            print(f"  挨拶: (無音)")

if __name__ == "__main__":
    demo_multi_sensor()