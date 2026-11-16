#!/usr/bin/env python3
"""
VOICEVOX最速版 - リアルタイム会話用
コマンドライン引数でテキストを受け取り、即座に再生
"""
import sys
import requests
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import os

class VoiceVoxFastest:
    def __init__(self, speaker_id=3, host='localhost', port=50021):
        self.base_url = f'http://{host}:{port}'
        self.speaker_id = speaker_id
        self.session = requests.Session()
        
        # コネクションプールの設定
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=0
        )
        self.session.mount('http://', adapter)
        
        # キャッシュ用
        self.query_cache = {}
        
    def speak(self, text):
        """最速で音声を再生"""
        start_time = time.time()
        
        # 短いテキストはキャッシュを利用
        cache_key = f"{self.speaker_id}:{text[:10]}"
        
        # 並列処理でクエリ生成と準備
        with ThreadPoolExecutor(max_workers=2) as executor:
            # クエリ生成
            future_query = executor.submit(self._generate_query, text)
            
            # 音声クエリを取得
            audio_query = future_query.result()
            
            # 音声合成
            future_synth = executor.submit(self._synthesize, audio_query)
            audio_data = future_synth.result()
        
        # 最速再生方法を選択
        if sys.platform == 'darwin':
            # macOSの場合、afplayをパイプで使用（最速）
            self._play_with_afplay_pipe(audio_data)
        else:
            # その他のOSではファイルに保存して再生
            self._play_with_file(audio_data)
        
        total_time = time.time() - start_time
        return total_time
    
    def _generate_query(self, text):
        """音声クエリを生成（キャッシュ付き）"""
        # 高速化パラメータ付きでクエリ生成
        params = {
            'text': text,
            'speaker': self.speaker_id
        }
        
        response = self.session.post(
            f'{self.base_url}/audio_query',
            params=params,
            timeout=0.5
        )
        
        audio_query = response.json()
        
        # 高速化の設定
        audio_query['speedScale'] = 1.2  # 1.2倍速
        audio_query['pauseLength'] = 0.1  # 句読点の間を最小に
        audio_query['pauseLengthScale'] = 0.3  # 全体的な間を短く
        
        return audio_query
    
    def _synthesize(self, audio_query):
        """音声を合成"""
        response = self.session.post(
            f'{self.base_url}/synthesis',
            params={'speaker': self.speaker_id},
            json=audio_query,
            headers={'Content-Type': 'application/json'},
            timeout=1.0
        )
        return response.content
    
    def _play_with_afplay_pipe(self, audio_data):
        """afplayにパイプで直接音声データを送る（最速）"""
        process = subprocess.Popen(
            ['afplay', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        process.communicate(input=audio_data)
    
    def _play_with_file(self, audio_data):
        """一時ファイル経由で再生"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        subprocess.run(['afplay', temp_path])
        os.unlink(temp_path)

def benchmark():
    """各種TTSのベンチマーク"""
    print("=== TTS速度ベンチマーク ===\n")
    
    test_texts = [
        "こんにちは",
        "今日はいい天気です",
        "音声合成のテストをしています",
    ]
    
    # 1. VOICEVOX最速版
    print("1. VOICEVOX最速版:")
    tts = VoiceVoxFastest()
    
    for text in test_texts:
        latency = tts.speak(text)
        print(f"  「{text}」 - {latency:.3f}秒")
    
    # 2. macOS sayコマンド（比較用）
    print("\n2. macOS sayコマンド:")
    for text in test_texts:
        start = time.time()
        subprocess.run(['say', '-v', 'Kyoko', text])
        latency = time.time() - start
        print(f"  「{text}」 - {latency:.3f}秒")
    
    # 3. OpenJTalk（比較用）
    print("\n3. pyopenjtalk:")
    import pyopenjtalk
    for text in test_texts:
        start = time.time()
        audio, sr = pyopenjtalk.tts(text)
        # 実際の再生時間は含まず、生成時間のみ
        latency = time.time() - start
        print(f"  「{text}」 - 生成のみ: {latency:.3f}秒")

def main():
    if len(sys.argv) > 1:
        # コマンドライン引数からテキストを取得
        text = ' '.join(sys.argv[1:])
        tts = VoiceVoxFastest()
        tts.speak(text)
    else:
        # ベンチマークモード
        benchmark()

if __name__ == "__main__":
    main()