#!/usr/bin/env python3
"""
キュー機能付きTTS APIサーバー
音声再生を順番に実行するバージョン
"""
import asyncio
import tempfile
import os
import subprocess
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import uvicorn
import aiohttp
from contextlib import asynccontextmanager
from datetime import datetime

# APIモデル定義
class TTSRequest(BaseModel):
    text: str
    speaker: int = 3
    speed: float = 1.2
    play: bool = True
    queue: bool = True  # キューを使うかどうか

class TTSResponse(BaseModel):
    message: str
    audio_length: Optional[float] = None
    queued: Optional[bool] = None
    queue_position: Optional[int] = None

# グローバル設定とキュー
VOICEVOX_URL = "http://localhost:50021"
playback_queue = asyncio.Queue()
current_playback = None

async def playback_worker():
    """音声再生ワーカー（キューから取り出して順番に再生）"""
    global current_playback
    while True:
        try:
            # キューから次の再生タスクを取得
            temp_path, audio_length, task_info = await playback_queue.get()
            current_playback = task_info
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 再生開始: {task_info}")
            
            # 音声を再生
            process = await asyncio.create_subprocess_exec(
                'afplay', temp_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await process.wait()
            
            # ファイルを削除
            try:
                os.unlink(temp_path)
            except:
                pass
            
            current_playback = None
            playback_queue.task_done()
            
        except Exception as e:
            print(f"再生エラー: {e}")

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
    title="Queue-enabled TTS API",
    description="キュー機能付きVOICEVOX音声合成API",
    version="2.0.0",
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
        "message": "Queue-enabled TTS API Server",
        "endpoints": {
            "/speak": "音声を再生（デフォルトはキュー使用）",
            "/status": "キューの状態を確認",
            "/docs": "APIドキュメント"
        },
        "queue_size": playback_queue.qsize(),
        "currently_playing": current_playback is not None
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
        
        if request.play:
            if request.queue:
                # キューに追加
                queue_position = playback_queue.qsize()
                await playback_queue.put((
                    temp_path,
                    audio_length,
                    f"{request.text[:20]}... (speaker={request.speaker})"
                ))
                
                return TTSResponse(
                    message="キューに追加されました",
                    audio_length=audio_length,
                    queued=True,
                    queue_position=queue_position
                )
            else:
                # 即座に再生（従来の動作）
                subprocess.Popen(
                    ['afplay', temp_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                asyncio.create_task(cleanup_after_play(temp_path, audio_length + 0.5))
                
                return TTSResponse(
                    message="音声を再生中（キューなし）",
                    audio_length=audio_length,
                    queued=False
                )
        else:
            return TTSResponse(
                message=f"音声ファイル生成完了: {temp_path}",
                audio_length=audio_length
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """キューの状態を取得"""
    return {
        "queue_size": playback_queue.qsize(),
        "currently_playing": current_playback,
        "is_playing": current_playback is not None
    }

async def cleanup_after_play(filepath: str, delay: float):
    """指定時間後にファイルを削除"""
    await asyncio.sleep(delay)
    try:
        os.unlink(filepath)
    except:
        pass

if __name__ == "__main__":
    print("Queue-enabled TTS API Server起動中...")
    print("API ドキュメント: http://localhost:8001/docs")
    uvicorn.run(app, host="0.0.0.0", port=8001)