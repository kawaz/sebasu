#!/usr/bin/env python3
"""
優先度・割り込み機能付きTTS APIサーバー
緊急音声の割り込み再生をサポート
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
from enum import Enum
import signal

# 優先度レベル
class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"  # 割り込み再生

# APIモデル定義
class TTSRequest(BaseModel):
    text: str
    speaker: int = 3
    speed: float = 1.2
    volume: float = 1.0  # 音量（0.0-2.0）
    priority: Priority = Priority.NORMAL
    resume_after_interrupt: bool = True  # 割り込み後に再開するか

class TTSResponse(BaseModel):
    message: str
    audio_length: Optional[float] = None
    priority: Optional[str] = None
    queue_position: Optional[int] = None
    interrupted: Optional[bool] = None

# グローバル設定
VOICEVOX_URL = "http://localhost:50021"
playback_queue = asyncio.PriorityQueue()  # 優先度付きキュー
current_playback: Optional[Dict[str, Any]] = None
current_process: Optional[asyncio.subprocess.Process] = None
interrupted_task: Optional[Dict[str, Any]] = None
task_counter = 0  # タスクの順序を保持するカウンター

async def playback_worker():
    """音声再生ワーカー（優先度順に再生）"""
    global current_playback, current_process, interrupted_task
    
    while True:
        try:
            # キューから次のタスクを取得（優先度順）
            priority_value, counter, task = await playback_queue.get()
            
            # 緊急タスクの場合は現在の再生を中断
            if task['priority'] == Priority.URGENT and current_process:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 緊急割り込み: {task['text'][:20]}...")
                
                # 現在の再生を中断
                if current_playback and current_playback.get('resume_after_interrupt'):
                    interrupted_task = current_playback.copy()
                    interrupted_task['position'] = 0  # TODO: 実際の再生位置を保存
                
                # プロセスを終了
                try:
                    current_process.terminate()
                    await current_process.wait()
                except:
                    pass
            
            current_playback = task
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 再生開始 [{task['priority']}]: {task['text'][:30]}...")
            
            # 音声を再生（音量調整付き）
            if task['volume'] != 1.0:
                # macOSの場合、afplayで音量調整
                volume_percent = int(task['volume'] * 100)
                current_process = await asyncio.create_subprocess_exec(
                    'afplay', '-v', str(volume_percent), task['temp_path'],
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
            else:
                current_process = await asyncio.create_subprocess_exec(
                    'afplay', task['temp_path'],
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
            
            await current_process.wait()
            
            # ファイルを削除
            try:
                os.unlink(task['temp_path'])
            except:
                pass
            
            current_playback = None
            current_process = None
            
            # 割り込み後の再開処理
            if task['priority'] == Priority.URGENT and interrupted_task:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 中断されたタスクを再開")
                # 中断されたタスクを高優先度でキューに戻す
                await add_to_queue(interrupted_task, priority_override=Priority.HIGH)
                interrupted_task = None
            
            playback_queue.task_done()
            
        except Exception as e:
            print(f"再生エラー: {e}")
            current_process = None

async def add_to_queue(task: Dict[str, Any], priority_override: Optional[Priority] = None):
    """タスクをキューに追加"""
    global task_counter
    
    priority = priority_override or task['priority']
    
    # 優先度を数値に変換（小さいほど高優先）
    priority_values = {
        Priority.URGENT: 0,
        Priority.HIGH: 1,
        Priority.NORMAL: 2,
        Priority.LOW: 3
    }
    
    task_counter += 1
    await playback_queue.put((
        priority_values[priority],
        task_counter,
        task
    ))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時の処理
    try:
        response = requests.get(f"{VOICEVOX_URL}/version")
        print(f"VOICEVOXエンジン接続成功: v{response.text.strip()}")
    except:
        print("警告: VOICEVOXエンジンに接続できません")
    
    # 再生ワーカーを起動
    worker_task = asyncio.create_task(playback_worker())
    
    yield
    
    # 終了時の処理
    worker_task.cancel()

app = FastAPI(
    title="Priority TTS API",
    description="優先度・割り込み機能付きVOICEVOX音声合成API",
    version="3.0.0",
    lifespan=lifespan
)

async def generate_speech(text: str, speaker: int, speed: float) -> bytes:
    """VOICEVOXで音声を生成"""
    async with aiohttp.ClientSession() as session:
        # 1. audio_query生成
        params = {'text': text, 'speaker': speaker}
        async with session.post(
            f"{VOICEVOX_URL}/audio_query",
            params=params
        ) as response:
            if response.status != 200:
                raise HTTPException(status_code=500, detail="音声クエリ生成に失敗")
            audio_query = await response.json()
        
        # 高速化設定
        audio_query['speedScale'] = speed
        audio_query['pauseLength'] = 0.1
        audio_query['pauseLengthScale'] = 0.3
        
        # 2. 音声合成
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
        "message": "Priority TTS API Server",
        "endpoints": {
            "/speak": "優先度付き音声再生",
            "/interrupt": "緊急割り込み再生",
            "/status": "再生状態の確認",
            "/docs": "APIドキュメント"
        },
        "queue_size": playback_queue.qsize(),
        "currently_playing": current_playback is not None,
        "priority_levels": ["low", "normal", "high", "urgent"]
    }

@app.post("/speak", response_model=TTSResponse)
async def speak(request: TTSRequest):
    """テキストを音声に変換して再生"""
    try:
        # 音声生成
        audio_data = await generate_speech(request.text, request.speaker, request.speed)
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        # 音声の長さを計算
        audio_length = (len(audio_data) - 44) / (44100 * 2)
        
        # タスク情報を作成
        task = {
            'text': request.text,
            'temp_path': temp_path,
            'speaker': request.speaker,
            'priority': request.priority,
            'volume': request.volume,
            'audio_length': audio_length,
            'resume_after_interrupt': request.resume_after_interrupt
        }
        
        # キューに追加
        await add_to_queue(task)
        
        return TTSResponse(
            message=f"キューに追加されました（優先度: {request.priority}）",
            audio_length=audio_length,
            priority=request.priority,
            queue_position=playback_queue.qsize()
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/interrupt", response_model=TTSResponse)
async def interrupt(request: TTSRequest):
    """緊急割り込み再生（最優先で再生）"""
    request.priority = Priority.URGENT
    request.volume = max(1.2, request.volume)  # 最低でも1.2倍の音量
    return await speak(request)

@app.get("/status")
async def get_status():
    """再生状態を取得"""
    queue_items = []
    # キューの中身を確認（実際には取り出さない）
    temp_list = []
    while not playback_queue.empty():
        item = await playback_queue.get()
        temp_list.append(item)
        queue_items.append({
            'priority': item[2]['priority'],
            'text': item[2]['text'][:30] + '...',
            'speaker': item[2]['speaker']
        })
    
    # キューに戻す
    for item in temp_list:
        await playback_queue.put(item)
    
    return {
        "currently_playing": {
            "text": current_playback['text'][:30] + '...' if current_playback else None,
            "priority": current_playback['priority'] if current_playback else None,
            "speaker": current_playback['speaker'] if current_playback else None
        } if current_playback else None,
        "queue_size": playback_queue.qsize(),
        "queue": queue_items,
        "has_interrupted_task": interrupted_task is not None
    }

@app.post("/stop")
async def stop_playback():
    """現在の再生を停止"""
    global current_process
    if current_process:
        try:
            current_process.terminate()
            await current_process.wait()
            return {"message": "再生を停止しました"}
        except:
            return {"message": "停止に失敗しました"}
    return {"message": "再生中の音声はありません"}

if __name__ == "__main__":
    print("Priority TTS API Server起動中...")
    print("API ドキュメント: http://localhost:8002/docs")
    print("\n優先度レベル:")
    print("  - low: 低優先度")
    print("  - normal: 通常（デフォルト）")
    print("  - high: 高優先度")
    print("  - urgent: 緊急（割り込み再生）")
    uvicorn.run(app, host="0.0.0.0", port=8002)