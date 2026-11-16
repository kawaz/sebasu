#!/bin/bash
# VOICEVOX Engine 手動セットアップスクリプト

set -e

echo "=== VOICEVOX Engine セットアップ ==="

# アーキテクチャの確認
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    VOICEVOX_ARCH="arm64"
    echo "✓ Apple Silicon Mac を検出しました"
else
    VOICEVOX_ARCH="x64"
    echo "✓ Intel Mac を検出しました"
fi

VERSION="0.23.1"
FILENAME="voicevox_engine-macos-${VOICEVOX_ARCH}-${VERSION}.7z.001"
URL="https://github.com/VOICEVOX/voicevox_engine/releases/download/${VERSION}/${FILENAME}"

echo ""
echo "ダウンロードするファイル: $FILENAME"
echo "URL: $URL"
echo ""

# p7zipの確認とインストール
if ! command -v 7z &> /dev/null; then
    echo "p7zipがインストールされていません。インストールしますか？ (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        brew install p7zip
    else
        echo "The Unarchiverを使って手動で解凍してください："
        echo "brew install --cask the-unarchiver"
        exit 1
    fi
fi

# ダウンロード
if [ ! -f "$FILENAME" ]; then
    echo "ダウンロード中... (約1.4GB)"
    curl -L -o "$FILENAME" "$URL"
    echo "✓ ダウンロード完了"
else
    echo "✓ ファイルは既に存在します: $FILENAME"
fi

# 解凍
EXTRACT_DIR="voicevox_engine-macos-${VOICEVOX_ARCH}-${VERSION}"
if [ ! -d "$EXTRACT_DIR" ]; then
    echo "解凍中..."
    7z x "$FILENAME"
    echo "✓ 解凍完了"
else
    echo "✓ 既に解凍されています: $EXTRACT_DIR"
fi

# 実行権限の付与
chmod +x "$EXTRACT_DIR/run"
echo "✓ 実行権限を付与しました"

# シンボリックリンクの作成（オプション）
if [ ! -e "voicevox_engine" ]; then
    ln -s "$EXTRACT_DIR" voicevox_engine
    echo "✓ シンボリックリンクを作成しました: voicevox_engine"
fi

echo ""
echo "=== セットアップ完了！ ==="
echo ""
echo "VOICEVOXを起動するには："
echo "  cd voicevox_engine && ./run"
echo ""
echo "または直接："
echo "  ./$EXTRACT_DIR/run"
echo ""
echo "起動後、ブラウザで http://localhost:50021/docs にアクセスしてください。"