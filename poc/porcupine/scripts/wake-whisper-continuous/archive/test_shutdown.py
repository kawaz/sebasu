#!/usr/bin/env python3
"""シャットダウン処理のテスト"""

import time
import subprocess
import signal
import sys

def test_graceful_shutdown():
    """グレースフルシャットダウンのテスト"""
    print("グレースフルシャットダウンのテストを開始...")
    
    # プロトタイプを起動
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    print(f"プロセス起動: PID={proc.pid}")
    
    # 5秒待機（初期化完了を待つ）
    print("初期化を待機中...")
    time.sleep(5)
    
    # SIGINT（Ctrl+C）を送信
    print("SIGINTを送信...")
    proc.send_signal(signal.SIGINT)
    
    # 終了を待つ（最大10秒）
    try:
        stdout, stderr = proc.communicate(timeout=10)
        print(f"\nプロセス終了: リターンコード={proc.returncode}")
        
        # 出力を確認
        if "シャットダウン中..." in stdout or "シャットダウン中..." in stderr:
            print("✅ シャットダウンメッセージを確認")
        else:
            print("❌ シャットダウンメッセージが見つかりません")
        
        if "停止完了" in stderr:
            print("✅ 正常終了を確認")
        else:
            print("⚠️  正常終了メッセージが見つかりません")
        
        # エラーチェック
        if "Exception" in stderr or "Traceback" in stderr:
            print("❌ エラーが発生しました:")
            print(stderr)
        else:
            print("✅ エラーなし")
            
    except subprocess.TimeoutExpired:
        print("❌ タイムアウト: プロセスが終了しませんでした")
        proc.kill()
    
    print("\nテスト完了")

if __name__ == "__main__":
    test_graceful_shutdown()