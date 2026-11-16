#!/usr/bin/env python3
"""
VOICEVOXエンジンの自動セットアップスクリプト
"""
import os
import sys
import platform
import requests
import zipfile
import tarfile
import subprocess
from pathlib import Path
import json

def get_system_info():
    """システム情報を取得"""
    system = platform.system()
    machine = platform.machine()
    
    if system == 'Darwin':  # macOS
        if machine == 'arm64':
            return 'macos-arm64'
        else:
            return 'macos-x64'
    elif system == 'Linux':
        return 'linux-cpu'
    elif system == 'Windows':
        return 'windows-cpu'
    else:
        raise Exception(f"サポートされていないOS: {system}")

def get_latest_release_info():
    """GitHubから最新リリース情報を取得"""
    url = "https://api.github.com/repos/VOICEVOX/voicevox_engine/releases/latest"
    response = requests.get(url)
    
    if response.status_code != 200:
        raise Exception("リリース情報の取得に失敗しました")
    
    return response.json()

def download_file(url, dest_path):
    """ファイルをダウンロード"""
    print(f"ダウンロード中: {url}")
    
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(dest_path, 'wb') as f:
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    progress = downloaded / total_size * 100
                    print(f"\r進捗: {progress:.1f}%", end="", flush=True)
    
    print("\nダウンロード完了")

def extract_archive(archive_path, extract_to):
    """アーカイブを展開"""
    print(f"展開中: {archive_path}")
    
    if archive_path.suffix == '.zip':
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    elif archive_path.suffix in ['.gz', '.tar']:
        with tarfile.open(archive_path, 'r:gz') as tar_ref:
            tar_ref.extractall(extract_to)
    else:
        raise Exception(f"サポートされていないアーカイブ形式: {archive_path.suffix}")
    
    print("展開完了")

def setup_voicevox():
    """VOICEVOXエンジンをセットアップ"""
    print("=== VOICEVOX エンジン セットアップ ===")
    
    # システム情報を取得
    system_type = get_system_info()
    print(f"システム: {system_type}")
    
    # インストール先ディレクトリ
    install_dir = Path("./voicevox_engine")
    
    # 既にインストールされているか確認
    if install_dir.exists() and (install_dir / "run").exists():
        print(f"\nVOICEVOXエンジンは既にインストールされています: {install_dir}")
        response = input("再インストールしますか？ (y/N): ")
        if response.lower() != 'y':
            return install_dir
    
    # 最新リリース情報を取得
    print("\n最新リリース情報を取得中...")
    try:
        release_info = get_latest_release_info()
        version = release_info['tag_name']
        print(f"最新バージョン: {version}")
    except Exception as e:
        print(f"エラー: {e}")
        print("手動でダウンロードしてください:")
        print("https://github.com/VOICEVOX/voicevox_engine/releases")
        return None
    
    # 対応するアセットを探す
    asset_name = None
    download_url = None
    
    for asset in release_info['assets']:
        name = asset['name']
        if system_type in name and 'cpu' in name:
            asset_name = name
            download_url = asset['browser_download_url']
            break
    
    if not download_url:
        print(f"エラー: {system_type}用のアセットが見つかりません")
        print("利用可能なアセット:")
        for asset in release_info['assets']:
            print(f"  - {asset['name']}")
        return None
    
    print(f"ダウンロードするファイル: {asset_name}")
    
    # ダウンロード
    download_path = Path(f"./{asset_name}")
    try:
        download_file(download_url, download_path)
    except Exception as e:
        print(f"ダウンロードエラー: {e}")
        return None
    
    # 展開
    try:
        extract_archive(download_path, ".")
        
        # 展開されたディレクトリを探す
        extracted_dirs = [d for d in Path(".").iterdir() 
                         if d.is_dir() and 'voicevox_engine' in d.name]
        
        if extracted_dirs:
            # 最新のディレクトリをvoicevox_engineにリネーム
            extracted_dirs[0].rename(install_dir)
        
        # ダウンロードファイルを削除
        download_path.unlink()
        
    except Exception as e:
        print(f"展開エラー: {e}")
        return None
    
    # 実行権限を付与（Unix系の場合）
    if platform.system() in ['Darwin', 'Linux']:
        run_path = install_dir / "run"
        os.chmod(run_path, 0o755)
        print("実行権限を付与しました")
    
    print(f"\n✓ セットアップ完了: {install_dir}")
    
    # 起動テスト
    print("\n起動テストを実行しますか？")
    response = input("(y/N): ")
    if response.lower() == 'y':
        test_engine(install_dir)
    
    return install_dir

def test_engine(engine_path):
    """エンジンの起動テスト"""
    print("\nエンジンを起動中...")
    
    run_path = engine_path / "run"
    if platform.system() == 'Windows':
        run_path = engine_path / "run.exe"
    
    try:
        # エンジンを起動
        process = subprocess.Popen([str(run_path)])
        
        print("エンジンが起動しました")
        print("ブラウザで以下にアクセスして確認してください:")
        print("  http://localhost:50021/docs")
        print("\n終了するにはCtrl+Cを押してください")
        
        # 待機
        process.wait()
        
    except KeyboardInterrupt:
        print("\nエンジンを停止します...")
        process.terminate()
        process.wait()
        print("停止しました")
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    setup_voicevox()