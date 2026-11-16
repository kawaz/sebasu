#!/usr/bin/env python3
"""
簡易TTS APIサーバー
VOICEVOXをラップして、テキストを送ると即座に音声再生まで行うシンプルなAPI
"""
import asyncio
import tempfile
import os
import subprocess
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import requests
import uvicorn
import aiohttp
import aiofiles
from contextlib import asynccontextmanager

# APIモデル定義
class TTSRequest(BaseModel):
    text: str
    speaker: int = 3  # デフォルト: ずんだもん
    speed: float = 1.2
    play: bool = True  # 音声を再生するか（Falseの場合はファイルを返す）

class TTSResponse(BaseModel):
    message: str
    audio_length: Optional[float] = None

# グローバル設定
VOICEVOX_URL = "http://localhost:50021"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時にVOICEVOXの接続確認
    try:
        response = requests.get(f"{VOICEVOX_URL}/version")
        print(f"VOICEVOXエンジン接続成功: v{response.text.strip()}")
    except:
        print("警告: VOICEVOXエンジンに接続できません")
    yield

app = FastAPI(
    title="Simple TTS API", 
    description="VOICEVOXを使った簡易音声合成API",
    version="1.0.0",
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
        "message": "Simple TTS API Server",
        "endpoints": {
            "/speak": "テキストを音声に変換して再生",
            "/generate": "テキストを音声ファイルに変換",
            "/speakers": "利用可能な話者一覧",
            "/docs": "APIドキュメント"
        }
    }

@app.post("/speak", response_model=TTSResponse)
async def speak(request: TTSRequest):
    """テキストを音声に変換して即座に再生"""
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
            # バックグラウンドで再生
            subprocess.Popen(
                ['afplay', temp_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # 再生完了後にファイル削除するタスクをスケジュール
            asyncio.create_task(cleanup_after_play(temp_path, audio_length + 0.5))
            
            return TTSResponse(
                message="音声を再生中",
                audio_length=audio_length
            )
        else:
            # ファイルとして返す場合はクリーンアップしない
            return TTSResponse(
                message=f"音声ファイル生成完了: {temp_path}",
                audio_length=audio_length
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate")
async def generate(request: TTSRequest):
    """テキストを音声ファイルに変換して返す"""
    try:
        audio_data = await generate_speech(request.text, request.speaker, request.speed)
        
        # ストリーミングレスポンスとして返す
        import io
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename=speech.wav"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/speakers")
async def get_speakers():
    """利用可能な話者一覧を取得"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{VOICEVOX_URL}/speakers") as response:
                speakers = await response.json()
                # 見やすい形式に整形
                result = []
                for speaker in speakers[:10]:  # 最初の10人のみ
                    speaker_info = {
                        "name": speaker["name"],
                        "styles": [
                            {"id": style["id"], "name": style["name"]}
                            for style in speaker["styles"]
                        ]
                    }
                    result.append(speaker_info)
                return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def cleanup_after_play(filepath: str, delay: float):
    """指定時間後にファイルを削除"""
    await asyncio.sleep(delay)
    try:
        os.unlink(filepath)
    except:
        pass

if __name__ == "__main__":
    print("Simple TTS API Server起動中...")
    print("API ドキュメント: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)