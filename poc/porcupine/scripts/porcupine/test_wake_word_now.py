#!/usr/bin/env python3
"""
すぐに開始するウェイクワードテスト（5秒カウントダウン付き）
"""
import os
import sys
import time
from pathlib import Path
from porcupine_helper import create_porcupine_with_auto_model
import pvrecorder

def test_wake_word(ppn_path, wake_phrase, sensitivity=0.5, duration=30):
    """ウェイクワードのテスト（カウントダウン後自動開始）"""
    
    # APIキー確認
    access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
    if not access_key:
        raise ValueError("PICOVOICE_ACCESS_KEY環境変数が設定されていません")
    
    print(f"\n🎯 カスタムウェイクワード '{wake_phrase}' のテスト")
    print("=" * 60)
    print(f"ファイル: {ppn_path}")
    print(f"感度: {sensitivity}")
    print(f"テスト時間: {duration}秒")
    print("=" * 60)
    
    # Porcupine初期化（自動モデルダウンロード付き）
    print("\n初期化中...")
    porcupine = create_porcupine_with_auto_model(
        access_key=access_key,
        keyword_paths=[ppn_path],
        sensitivities=[sensitivity]
    )
    
    recorder = pvrecorder.PvRecorder(
        frame_length=porcupine.frame_length,
        device_index=-1
    )
    
    print("\n✅ 準備完了！")
    print("\n📢 5秒後にテストを開始します")
    print(f"「{wake_phrase}」と話す準備をしてください\n")
    
    # カウントダウン
    for i in range(5, 0, -1):
        print(f"開始まで {i}秒...", end='\r', flush=True)
        time.sleep(1)
    
    print(f"\n\n🎤 テスト開始！ '{wake_phrase}' と話してください")
    print("（検出されると画面に表示されます）")
    print(f"テストは{duration}秒間続きます。途中で終了: Ctrl+C\n")
    
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
                print(f"\n\n⏰ 時間制限 ({duration}秒) に達しました")
                break
            
            # 進行状況表示（5秒ごと）
            if int(elapsed) % 5 == 0 and elapsed - int(elapsed) < 0.1:
                remaining = duration - int(elapsed)
                if remaining > 0:
                    print(f"⏱️  残り{remaining}秒...", end='\r', flush=True)
            
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
                
                print(f"\n🎉 検出 #{detection_count}: '{wake_phrase}' "
                      f"@ {time.strftime('%H:%M:%S')}{interval_str}")
                print("   └─ 良い発音です！次も試してみてください\n")
                
                last_detection = detection_time
                
                # 連続検出防止
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n\n🛑 テスト中断")
    finally:
        recorder.stop()
        recorder.delete()
        porcupine.delete()
        
    # 結果サマリー
    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    print(f"テスト時間: {total_time:.1f}秒")
    print(f"検出回数: {detection_count}回")
    
    if detection_count > 0:
        print(f"平均検出間隔: {total_time/detection_count:.1f}秒")
        print(f"\n🎯 認識率の評価:")
        
        rate = detection_count / (total_time / 10)  # 10秒あたりの検出回数
        if rate >= 0.8:
            print("  → 😄 優秀！家族全員が使いやすいでしょう")
        elif rate >= 0.5:
            print("  → 😊 良好。感度を少し調整すると更に良くなるかも")
        elif rate >= 0.3:
            print("  → 🤔 まずまず。感度を上げてみてください")
        else:
            print("  → 😅 要改善。感度を上げるか、発音を調整してください")
            
        print("\n💡 ヒント:")
        if sensitivity < 0.7:
            print("  - 感度を上げてみてください (--sensitivity 0.7)")
        print("  - ゆっくりはっきりと発音してください")
        print("  - マイクとの距離を調整してください")
    else:
        print("\n⚠️  検出されませんでした")
        print("\n考えられる原因:")
        print("  1. マイクが正しく動作していない")
        print("  2. 発音が不明瞭")
        print(f"  3. 感度が低すぎる（現在: {sensitivity}）")
        print("  4. 周囲の騒音が多い")
        print("\n💡 対策:")
        print(f"  - 感度を上げて再テスト: --sensitivity 0.8")
        print("  - マイクの動作確認")
        print("  - より静かな環境で再テスト")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='カスタムウェイクワードテスト（5秒後自動開始）'
    )
    parser.add_argument(
        'ppn_file',
        help='ウェイクワードファイル（.ppn）のパス'
    )
    parser.add_argument(
        'wake_phrase',
        help='ウェイクワードのフレーズ（例: オッケーセバス）'
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
        default=30,
        help='テスト時間（秒）。0で無制限（デフォルト: 30）'
    )
    
    args = parser.parse_args()
    
    # 感度の範囲チェック
    if not 0.0 <= args.sensitivity <= 1.0:
        print("エラー: 感度は0.0から1.0の範囲で指定してください")
        return 1
    
    try:
        test_wake_word(
            args.ppn_file,
            args.wake_phrase,
            args.sensitivity,
            args.duration
        )
    except Exception as e:
        print(f"エラー: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())