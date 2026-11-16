#!/usr/bin/env python3
"""
VOICEVOXリアルタイム音声合成
ストリーミング再生で低レイテンシを実現
"""
import requests
import json
import pyaudio
import threading
import queue
import time
import io
import wave
import subprocess
import numpy as np

class VoiceVoxRealtimePlayer:
    def __init__(self, speaker_id=3, host='localhost', port=50021):
        self.base_url = f'http://{host}:{port}'
        self.speaker_id = speaker_id
        self.audio_queue = queue.Queue()
        self.is_playing = False
        
        # PyAudioの初期化
        self.p = pyaudio.PyAudio()
        
        # デフォルトのクエリを事前に取得（高速化のため）
        self._prepare_default_query()
        
    def _prepare_default_query(self):
        """デフォルトクエリを事前に準備（初回のレイテンシ削減）"""
        try:
            params = {'text': 'あ', 'speaker': self.speaker_id}
            response = requests.post(f'{self.base_url}/audio_query', params=params)
            self.default_query_template = response.json()
            print("✓ デフォルトクエリを準備しました")
        except:
            self.default_query_template = None
    
    def speak_streaming(self, text):
        """テキストを即座に音声再生（ストリーミング）"""
        start_time = time.time()
        
        # 音声クエリの生成（最適化版）
        params = {'text': text, 'speaker': self.speaker_id}
        
        # クエリ生成を高速化
        if self.default_query_template:
            audio_query = self.default_query_template.copy()
            # テキストに応じてアクセント句を更新
            query_response = requests.post(f'{self.base_url}/audio_query', params=params)
            audio_query = query_response.json()
        else:
            query_response = requests.post(f'{self.base_url}/audio_query', params=params)
            audio_query = query_response.json()
        
        # 高速化のためのパラメータ調整
        audio_query['speedScale'] = 1.1  # 少し速く
        audio_query['pauseLength'] = 0.3  # 句読点の間を短く
        audio_query['pauseLengthScale'] = 0.5  # 全体的な間を短く
        
        query_time = time.time() - start_time
        
        # 音声合成
        synthesis_start = time.time()
        synthesis_response = requests.post(
            f'{self.base_url}/synthesis',
            params={'speaker': self.speaker_id},
            json=audio_query,
            headers={'Content-Type': 'application/json'},
            stream=True  # ストリーミングレスポンス
        )
        
        # WAVデータを直接再生
        audio_data = synthesis_response.content
        synthesis_time = time.time() - synthesis_start
        
        # PyAudioで直接再生
        self._play_audio_direct(audio_data)
        
        total_time = time.time() - start_time
        print(f"レイテンシ: クエリ={query_time:.3f}秒, 合成={synthesis_time:.3f}秒, 合計={total_time:.3f}秒")
    
    def _play_audio_direct(self, audio_data):
        """WAVデータを直接再生（ファイル保存なし）"""
        # WAVデータをメモリ上で読み込み
        wav_file = wave.open(io.BytesIO(audio_data), 'rb')
        
        # ストリームを開く
        stream = self.p.open(
            format=self.p.get_format_from_width(wav_file.getsampwidth()),
            channels=wav_file.getnchannels(),
            rate=wav_file.getframerate(),
            output=True
        )
        
        # 音声データを再生
        data = wav_file.readframes(1024)
        while data:
            stream.write(data)
            data = wav_file.readframes(1024)
        
        # クリーンアップ
        stream.stop_stream()
        stream.close()
        wav_file.close()
    
    def speak_macos_direct(self, text):
        """macOS sayコマンドを使った超低レイテンシ版（比較用）"""
        start_time = time.time()
        subprocess.run(['say', '-v', 'Kyoko', text])
        total_time = time.time() - start_time
        print(f"macOS say レイテンシ: {total_time:.3f}秒")
    
    def cleanup(self):
        """リソースの解放"""
        self.p.terminate()

class VoiceVoxOptimized:
    """最適化されたVOICEVOX（バッチ処理対応）"""
    
    def __init__(self, speaker_id=3, host='localhost', port=50021):
        self.base_url = f'http://{host}:{port}'
        self.speaker_id = speaker_id
        
        # コネクションを再利用
        self.session = requests.Session()
        
    def speak_sentences(self, sentences):
        """複数の文を効率的に処理"""
        for sentence in sentences:
            if sentence.strip():
                self._speak_single(sentence)
    
    def _speak_single(self, text):
        """単一文の高速処理"""
        # クエリとシンセシスを一度のリクエストで処理
        # （VOICEVOX APIの制限により、実際は2回のリクエストが必要）
        
        # より短いタイムアウトで高速化
        params = {'text': text, 'speaker': self.speaker_id}
        
        # クエリ生成
        query_response = self.session.post(
            f'{self.base_url}/audio_query',
            params=params,
            timeout=1.0
        )
        audio_query = query_response.json()
        
        # 最適化パラメータ
        audio_query['speedScale'] = 1.2
        audio_query['pauseLength'] = 0.1
        
        # 音声合成
        synthesis_response = self.session.post(
            f'{self.base_url}/synthesis',
            params={'speaker': self.speaker_id},
            json=audio_query,
            headers={'Content-Type': 'application/json'},
            timeout=2.0
        )
        
        # macOSの場合、afplayで直接再生（パイプ使用）
        process = subprocess.Popen(
            ['afplay', '-'],
            stdin=subprocess.PIPE
        )
        process.communicate(input=synthesis_response.content)

def test_realtime():
    """リアルタイム性能のテスト"""
    print("=== VOICEVOXリアルタイムテスト ===\n")
    
    # VOICEVOXエンジンの確認
    try:
        response = requests.get('http://localhost:50021/version', timeout=0.5)
        print(f"VOICEVOX Engine: {response.text.strip()}\n")
    except:
        print("エラー: VOICEVOXエンジンが起動していません")
        return
    
    # リアルタイムプレイヤーの初期化
    player = VoiceVoxRealtimePlayer(speaker_id=3)  # ずんだもん
    
    # テストフレーズ
    test_phrases = [
        "こんにちは",
        "今日はいい天気ですね",
        "バサラさんの歌は最高なのだ",
        "リアルタイムで会話できるのだ"
    ]
    
    print("1. VOICEVOX ストリーミング版:")
    for phrase in test_phrases:
        print(f"\n「{phrase}」")
        player.speak_streaming(phrase)
    
    print("\n\n2. 比較: macOS sayコマンド（超低レイテンシ）:")
    for phrase in test_phrases:
        print(f"\n「{phrase}」")
        player.speak_macos_direct(phrase)
    
    # 対話モード
    print("\n\n=== 対話モード（qで終了）===")
    print("テキストを入力すると即座に読み上げます\n")
    
    optimized = VoiceVoxOptimized(speaker_id=3)
    
    while True:
        text = input("> ")
        if text.lower() == 'q':
            break
        
        if text.strip():
            start = time.time()
            optimized._speak_single(text)
            print(f"総レイテンシ: {time.time() - start:.3f}秒")
    
    player.cleanup()

if __name__ == "__main__":
    test_realtime()