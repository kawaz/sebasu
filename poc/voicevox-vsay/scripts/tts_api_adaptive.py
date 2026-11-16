#!/usr/bin/env python3
"""
環境適応型TTS APIサーバー
マイクからの環境音に基づいて音量を自動調整
"""
import asyncio
import tempfile
import os
import subprocess
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import uvicorn
import aiohttp
from contextlib import asynccontextmanager
from datetime import datetime
import numpy as np
import sounddevice as sd
import time

# APIモデル定義
class AdaptiveTTSRequest(BaseModel):
    text: str
    speaker: int = 3
    speed: float = 1.2
    adaptive: bool = True  # 適応型音量調整を使用するか
    volume_override: Optional[float] = None  # 手動で音量を指定
    location: Optional[str] = None  # bedroom, living_room, kitchen

class TTSResponse(BaseModel):
    message: str
    audio_length: Optional[float] = None
    volume_used: Optional[float] = None
    noise_level: Optional[float] = None
    environment: Optional[Dict[str, Any]] = None

# グローバル設定
VOICEVOX_URL = "http://localhost:50021"
current_noise_level = 50.0  # デフォルト騒音レベル
noise_monitor_task = None

async def monitor_noise_continuously():
    """継続的に環境音をモニタリング"""
    global current_noise_level
    
    print("環境音モニタリング開始...")
    buffer_size = 1024
    sample_rate = 44100
    
    def calculate_db(audio_data):
        rms = np.sqrt(np.mean(audio_data**2))
        if rms > 0:
            return 20 * np.log10(rms / 0.00002)
        return -np.inf
    
    try:
        while True:
            # 1秒間サンプリング
            recording = sd.rec(int(sample_rate * 0.5), 
                             samplerate=sample_rate, 
                             channels=1,
                             blocking=True)
            
            db = calculate_db(recording)
            if not np.isinf(db):
                current_noise_level = db
                
            await asyncio.sleep(0.5)  # 0.5秒ごとに更新
            
    except Exception as e:
        print(f"モニタリングエラー: {e}")

def get_adaptive_volume(noise_db: float, location: Optional[str] = None) -> float:
    """騒音レベルと場所に基づいて適切な音量を計算"""
    # 時間帯判定
    hour = time.localtime().tm_hour
    
    # ベース音量
    base_volume = 1.0
    
    # 時間帯による調整
    if 0 <= hour < 6:  # 深夜
        base_volume *= 0.5
    elif 6 <= hour < 9:  # 早朝
        base_volume *= 0.7
    elif 22 <= hour < 24:  # 夜
        base_volume *= 0.8
    
    # 場所による調整
    if location == "bedroom":
        base_volume *= 0.8
    elif location == "kitchen":
        base_volume *= 1.2
    
    # 騒音レベルによる調整
    if noise_db < 40:  # とても静か
        noise_factor = 0.8
    elif noise_db < 50:  # 静か
        noise_factor = 1.0
    elif noise_db < 60:  # 普通
        noise_factor = 1.3
    elif noise_db < 70:  # 騒がしい
        noise_factor = 1.6
    else:  # とても騒がしい
        noise_factor = 2.0
    
    # 最終音量（0.3〜2.5の範囲）
    final_volume = base_volume * noise_factor
    return max(0.3, min(2.5, final_volume))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時の処理
    try:
        response = requests.get(f"{VOICEVOX_URL}/version")
        print(f"VOICEVOXエンジン接続成功: v{response.text.strip()}")
    except:
        print("警告: VOICEVOXエンジンに接続できません")
    
    # 環境音モニタリングを開始
    global noise_monitor_task
    try:
        noise_monitor_task = asyncio.create_task(monitor_noise_continuously())
    except Exception as e:
        print(f"環境音モニタリングを開始できません: {e}")
    
    yield
    
    # 終了時の処理
    if noise_monitor_task:
        noise_monitor_task.cancel()

app = FastAPI(
    title="Adaptive TTS API",
    description="環境適応型VOICEVOX音声合成API",
    version="4.0.0",
    lifespan=lifespan
)

async def generate_speech(text: str, speaker: int, speed: float) -> bytes:
    """VOICEVOXで音声を生成"""
    async with aiohttp.ClientSession() as session:
        params = {'text': text, 'speaker': speaker}
        async with session.post(
            f"{VOICEVOX_URL}/audio_query",
            params=params
        ) as response:
            if response.status != 200:
                raise HTTPException(status_code=500, detail="音声クエリ生成に失敗")
            audio_query = await response.json()
        
        audio_query['speedScale'] = speed
        audio_query['pauseLength'] = 0.1
        audio_query['pauseLengthScale'] = 0.3
        
        async with session.post(
            f"{VOICEVOX_URL}/synthesis",
            params={'speaker': speaker},
            json=audio_query,
            headers={'Content-Type': 'application/json'}
        ) as response:
            if response.status != 200:
                raise HTTPException(status_code=500, detail="音声合成に失敗")
            return await response.read()

@app.get("/")
async def root():
    """APIの基本情報"""
    return {
        "message": "Adaptive TTS API Server",
        "endpoints": {
            "/speak": "環境適応型音声再生",
            "/status": "現在の環境状態",
            "/docs": "APIドキュメント"
        },
        "current_noise_level": f"{current_noise_level:.1f} dB",
        "suggested_volume": get_adaptive_volume(current_noise_level)
    }

@app.post("/speak", response_model=TTSResponse)
async def speak(request: AdaptiveTTSRequest):
    """環境に適応した音量で音声を再生"""
    try:
        # 音声生成
        audio_data = await generate_speech(request.text, request.speaker, request.speed)
        
        # 音量決定
        if request.volume_override is not None:
            volume = request.volume_override
        elif request.adaptive:
            volume = get_adaptive_volume(current_noise_level, request.location)
        else:
            volume = 1.0
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        # 音声の長さを計算
        audio_length = (len(audio_data) - 44) / (44100 * 2)
        
        # 音声再生
        if volume != 1.0:
            volume_percent = int(volume * 100)
            subprocess.Popen(
                ['afplay', '-v', str(volume_percent), temp_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            subprocess.Popen(
                ['afplay', temp_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        # クリーンアップタスク
        asyncio.create_task(cleanup_after_play(temp_path, audio_length + 0.5))
        
        return TTSResponse(
            message=f"音声を再生中（音量: {volume:.1f}x）",
            audio_length=audio_length,
            volume_used=volume,
            noise_level=current_noise_level,
            environment={
                "time": datetime.now().strftime("%H:%M"),
                "location": request.location,
                "noise_db": current_noise_level,
                "adaptive": request.adaptive
            }
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """現在の環境状態を取得"""
    hour = time.localtime().tm_hour
    time_period = "late_night" if 0 <= hour < 6 else \
                  "morning" if 6 <= hour < 9 else \
                  "day" if 9 <= hour < 17 else \
                  "evening" if 17 <= hour < 22 else "night"
    
    return {
        "current_time": datetime.now().strftime("%H:%M:%S"),
        "time_period": time_period,
        "noise_level_db": current_noise_level,
        "noise_description": 
            "very_quiet" if current_noise_level < 40 else
            "quiet" if current_noise_level < 50 else
            "normal" if current_noise_level < 60 else
            "noisy" if current_noise_level < 70 else
            "very_noisy",
        "suggested_volumes": {
            "bedroom": get_adaptive_volume(current_noise_level, "bedroom"),
            "living_room": get_adaptive_volume(current_noise_level, "living_room"),
            "kitchen": get_adaptive_volume(current_noise_level, "kitchen")
        }
    }

async def cleanup_after_play(filepath: str, delay: float):
    """指定時間後にファイルを削除"""
    await asyncio.sleep(delay)
    try:
        os.unlink(filepath)
    except:
        pass

if __name__ == "__main__":
    print("Adaptive TTS API Server起動中...")
    print("環境音に基づいて音量を自動調整します")
    print("API ドキュメント: http://localhost:8003/docs")
    uvicorn.run(app, host="0.0.0.0", port=8003)