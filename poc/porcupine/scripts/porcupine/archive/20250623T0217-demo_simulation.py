#!/usr/bin/env python3
"""
Porcupineの動作をシミュレーションするデモ
APIキーなしで動作の雰囲気を体験できます
"""

import time
import numpy as np
import sounddevice as sd
from datetime import datetime

class PorcupineSimulator:
    """Porcupineの動作をシミュレート"""
    
    def __init__(self, keywords=["alexa", "computer", "jarvis"]):
        self.keywords = keywords
        self.sample_rate = 16000
        self.frame_length = 512  # Porcupineの標準フレーム長
        self.detection_history = []
        
    def process_audio_frame(self, audio_frame):
        """音声フレームを処理（シミュレーション）"""
        # 音量ベースの簡易検出
        energy = np.sqrt(np.mean(audio_frame**2))
        
        # ランダムな検出シミュレーション
        if energy > 0.02 and np.random.random() > 0.95:
            return np.random.randint(0, len(self.keywords))
        return -1
    
    def get_statistics(self):
        """統計情報を返す"""
        if not self.detection_history:
            return "検出なし"
        
        total = len(self.detection_history)
        keyword_counts = {}
        for kw in self.detection_history:
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        
        stats = f"総検出数: {total}\n"
        for kw, count in keyword_counts.items():
            stats += f"  {kw}: {count}回\n"
        return stats

def main():
    """メインデモ"""
    print("=== Picovoice Porcupine 動作シミュレーション ===\n")
    print("注: これは実際のPorcupineではなく、動作を模擬したデモです")
    print("実際のPorcupineは高精度なニューラルネットワークを使用します\n")
    
    # シミュレータ初期化
    keywords = ["alexa", "hey jarvis", "computer", "picovoice"]
    simulator = PorcupineSimulator(keywords)
    
    print(f"シミュレーション設定:")
    print(f"  サンプリングレート: {simulator.sample_rate}Hz")
    print(f"  フレーム長: {simulator.frame_length}サンプル")
    print(f"  検出対象: {', '.join(keywords)}")
    print("\n実際のPorcupineでは:")
    print("  - 97%以上の検出精度")
    print("  - 誤検出1回/10時間未満")
    print("  - レイテンシ<100ms")
    
    print(f"\n{'='*50}")
    print("マイクに向かって話してください (Ctrl+Cで終了)")
    print("大きめの声で話すと「検出」されやすくなります")
    print(f"{'='*50}\n")
    
    # 音声処理のコールバック
    audio_buffer = []
    last_detection_time = 0
    detection_cooldown = 2.0
    
    def audio_callback(indata, frames, time_info, status):
        nonlocal audio_buffer, last_detection_time
        
        if status:
            print(f"Audio error: {status}")
        
        # バッファに追加
        audio_buffer.extend(indata[:, 0])
        
        # フレーム単位で処理
        while len(audio_buffer) >= simulator.frame_length:
            # フレーム取り出し
            frame = np.array(audio_buffer[:simulator.frame_length])
            audio_buffer = audio_buffer[simulator.frame_length:]
            
            # 検出処理（シミュレーション）
            keyword_index = simulator.process_audio_frame(frame)
            
            current_time = time.time()
            if keyword_index >= 0 and (current_time - last_detection_time) > detection_cooldown:
                detected_keyword = keywords[keyword_index]
                simulator.detection_history.append(detected_keyword)
                last_detection_time = current_time
                
                # 検出表示
                print(f"\n{'🎯'*20}")
                print(f"ウェイクワード検出！（シミュレーション）")
                print(f"検出ワード: '{detected_keyword}'")
                print(f"時刻: {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'🎯'*20}\n")
                
                print("実際のPorcupineでは、この検出が")
                print("ニューラルネットワークによって")
                print("非常に高精度に行われます\n")
                
                print("検出後の処理例:")
                print("1. Whisperで音声認識開始")
                print("2. コマンドを解析")
                print("3. アクション実行\n")
                
                print("待機中...\n")
        
        # 音量表示
        volume = np.sqrt(np.mean(indata**2))
        if volume > 0.01:
            bar = '█' * int(volume * 100)
            print(f"\r音量: [{bar:<30}] {volume:.3f}", end="", flush=True)
    
    # オーディオストリーム開始
    try:
        with sd.InputStream(
            callback=audio_callback,
            channels=1,
            samplerate=simulator.sample_rate,
            blocksize=simulator.frame_length // 2
        ):
            start_time = time.time()
            
            while True:
                time.sleep(1)
                
                # 定期的な情報表示
                elapsed = int(time.time() - start_time)
                if elapsed > 0 and elapsed % 20 == 0:
                    print(f"\n\n--- {elapsed}秒経過 ---")
                    print(simulator.get_statistics())
                    
    except KeyboardInterrupt:
        print("\n\nシミュレーションを終了します...")
        
    # 最終統計
    print(f"\n=== 最終統計 ===")
    print(simulator.get_statistics())
    
    print("\n=== 実際のPorcupineを使うには ===")
    print("1. https://console.picovoice.ai/ でアカウント作成")
    print("2. APIキーを取得")
    print("3. export PICOVOICE_ACCESS_KEY='your-key'")
    print("4. uv run python test_with_key.py")
    
    print("\n実際のPorcupineの特徴:")
    print("✓ 完全ローカル動作（プライバシー保護）")
    print("✓ 高精度（97%以上）")
    print("✓ 低消費電力")
    print("✓ 17言語対応（日本語含む）")
    print("✓ カスタムウェイクワード作成可能")

if __name__ == "__main__":
    main()