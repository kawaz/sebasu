#!/usr/bin/env python3
"""
vsay デバッグ版 - 問題を特定
"""
import sys
import requests
import subprocess
import time

def debug_speak(text):
    print(f"[DEBUG] テキスト: {text}")
    
    try:
        # 1. クエリ生成
        print("[DEBUG] audio_query 送信中...")
        start = time.time()
        params = {'text': text, 'speaker': 3}
        query_response = requests.post(
            'http://localhost:50021/audio_query',
            params=params,
            timeout=5.0
        )
        print(f"[DEBUG] audio_query 完了: {time.time() - start:.3f}秒")
        
        audio_query = query_response.json()
        audio_query['speedScale'] = 1.2
        audio_query['pauseLength'] = 0.1
        audio_query['pauseLengthScale'] = 0.3
        
        # 2. 音声合成
        print("[DEBUG] synthesis 送信中...")
        start = time.time()
        synthesis_response = requests.post(
            'http://localhost:50021/synthesis',
            params={'speaker': 3},
            json=audio_query,
            headers={'Content-Type': 'application/json'},
            timeout=10.0
        )
        print(f"[DEBUG] synthesis 完了: {time.time() - start:.3f}秒")
        print(f"[DEBUG] 音声データサイズ: {len(synthesis_response.content)} bytes")
        
        # 3. 一時ファイルに保存してテスト
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(synthesis_response.content)
            temp_path = f.name
        print(f"[DEBUG] 一時ファイル: {temp_path}")
        
        # 4. afplayで再生
        print("[DEBUG] afplay 実行中...")
        result = subprocess.run(['afplay', temp_path], capture_output=True, text=True)
        print(f"[DEBUG] afplay 終了コード: {result.returncode}")
        if result.stderr:
            print(f"[DEBUG] afplay エラー: {result.stderr}")
        
        # 5. パイプでも試す
        print("[DEBUG] パイプ版も試す...")
        process = subprocess.Popen(
            ['afplay', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=synthesis_response.content)
        print(f"[DEBUG] パイプ版終了コード: {process.returncode}")
        if stderr:
            print(f"[DEBUG] パイプ版エラー: {stderr.decode()}")
        
        # 6. ファイルに保存
        with open('debug_output.wav', 'wb') as f:
            f.write(synthesis_response.content)
        print("[DEBUG] debug_output.wav に保存しました")
        
        # クリーンアップ
        import os
        os.unlink(temp_path)
        
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "テストです"
    debug_speak(text)