#!/usr/bin/env python3
"""
カスタムウェイクワードテストツール
作成したカスタムウェイクワードの動作確認用
"""

import os
import sys
import time
import argparse
import pvporcupine
import pvrecorder
from pathlib import Path

class CustomWakeWordTester:
    def __init__(self, ppn_path, wake_phrase, sensitivity=0.5):
        self.ppn_path = ppn_path
        self.wake_phrase = wake_phrase
        self.sensitivity = sensitivity
        
        # APIキー確認
        self.access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
        if not self.access_key:
            raise ValueError("PICOVOICE_ACCESS_KEY環境変数が設定されていません")
        
        # ファイル存在確認
        if not Path(ppn_path).exists():
            raise FileNotFoundError(f"ウェイクワードファイルが見つかりません: {ppn_path}")
    
    def test(self, duration=60):
        """ウェイクワードのテスト実行"""
        print(f"カスタムウェイクワード '{self.wake_phrase}' のテスト")
        print("=" * 60)
        print(f"ファイル: {self.ppn_path}")
        print(f"感度: {self.sensitivity}")
        print(f"テスト時間: {duration}秒")
        print("=" * 60)
        
        # Porcupine初期化
        print("\n初期化中...")
        
        # 日本語ウェイクワードの場合、日本語モデルを明示的に指定
        model_path = None
        if "_ja_" in self.ppn_path:
            # 日本語モデルファイルのパスを確認
            ja_model_path = Path(__file__).parent / "porcupine_params_ja.pv"
            if ja_model_path.exists():
                model_path = str(ja_model_path)
                print(f"日本語モデルを使用: {model_path}")
            else:
                print("⚠️ 日本語モデルファイルが見つかりません")
        
        porcupine = pvporcupine.create(
            access_key=self.access_key,
            keyword_paths=[self.ppn_path],
            sensitivities=[self.sensitivity],
            model_path=model_path
        )
        
        recorder = pvrecorder.PvRecorder(
            frame_length=porcupine.frame_length,
            device_index=-1
        )
        
        print(f"✓ 準備完了！\n")
        print(f"🎤 '{self.wake_phrase}' と話してください...")
        print("終了: Ctrl+C\n")
        
        # 統計情報
        detection_count = 0
        start_time = time.time()
        last_detection = None
        
        recorder.start()
        
        try:
            while True:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # 時間制限チェック
                if duration > 0 and elapsed >= duration:
                    print(f"\n\n時間制限 ({duration}秒) に達しました")
                    break
                
                # 音声処理
                pcm = recorder.read()
                result = porcupine.process(pcm)
                
                if result >= 0:
                    detection_count += 1
                    detection_time = time.time()
                    
                    # 前回検出からの経過時間
                    if last_detection:
                        interval = detection_time - last_detection
                        interval_str = f" (前回から {interval:.1f}秒)"
                    else:
                        interval_str = ""
                    
                    print(f"\n✅ 検出 #{detection_count}: '{self.wake_phrase}' "
                          f"@ {time.strftime('%H:%M:%S')}{interval_str}")
                    
                    last_detection = detection_time
                    
                    # フィードバック
                    print("   └─ 良い発音です！")
                    
                    # 連続検出防止
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n\nテスト中断")
        finally:
            recorder.stop()
            recorder.delete()
            porcupine.delete()
            
        # 結果サマリー
        total_time = time.time() - start_time
        print("\n" + "=" * 60)
        print("📊 テスト結果")
        print("=" * 60)
        print(f"テスト時間: {total_time:.1f}秒")
        print(f"検出回数: {detection_count}回")
        if detection_count > 0:
            print(f"平均検出間隔: {total_time/detection_count:.1f}秒")
            print(f"\n認識率の目安:")
            if detection_count >= 8:
                print("  → 優秀！家族全員が使いやすいでしょう")
            elif detection_count >= 5:
                print("  → 良好。感度を少し上げても良いかもしれません")
            else:
                print("  → 要改善。感度を上げるか、発音を練習してください")
        else:
            print("\n⚠️ 検出されませんでした")
            print("以下を確認してください:")
            print("  1. マイクが正しく動作しているか")
            print("  2. 発音が明瞭か")
            print("  3. 感度設定（現在: {self.sensitivity}）")

def main():
    parser = argparse.ArgumentParser(
        description='カスタムウェイクワードのテストツール'
    )
    parser.add_argument(
        'ppn_file',
        help='ウェイクワードファイル（.ppn）のパス'
    )
    parser.add_argument(
        'wake_phrase',
        help='ウェイクワードのフレーズ（例: ねえハウス）'
    )
    parser.add_argument(
        '--sensitivity', '-s',
        type=float,
        default=0.5,
        help='検出感度 (0.0-1.0, デフォルト: 0.5)'
    )
    parser.add_argument(
        '--duration', '-d',
        type=int,
        default=60,
        help='テスト時間（秒）。0で無制限（デフォルト: 60）'
    )
    
    args = parser.parse_args()
    
    # 感度の範囲チェック
    if not 0.0 <= args.sensitivity <= 1.0:
        print("エラー: 感度は0.0から1.0の範囲で指定してください")
        return 1
    
    try:
        tester = CustomWakeWordTester(
            args.ppn_file,
            args.wake_phrase,
            args.sensitivity
        )
        tester.test(args.duration)
    except Exception as e:
        print(f"エラー: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())