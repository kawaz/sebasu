#!/usr/bin/env python3
"""
vsay direct - VOICEVOXを直接利用する音声合成
元のvsayの実装
"""
import sys
import requests
import subprocess
import argparse
import json

def _emphasize_initial_moras(audio_query, num_moras=3, pitch_boost=0.1, length_scale=1.3):
    """先頭のnum_morasモーラを強調する（pitch上げ＋母音伸ばし）"""
    count = 0
    for ap in audio_query.get('accent_phrases', []):
        for mora in ap.get('moras', []):
            if count >= num_moras:
                return
            if mora.get('pitch', 0) > 0:
                mora['pitch'] += pitch_boost
            if mora.get('vowel_length') is not None:
                mora['vowel_length'] *= length_scale
            count += 1
        if count >= num_moras:
            return

def speak(text, speaker=3, speed=1.2, emphasis_moras=3, emphasis_pitch=0.1, emphasis_length=1.3):
    """VOICEVOXで即座に音声を再生"""
    try:
        # クエリ生成
        params = {'text': text, 'speaker': speaker}
        query_response = requests.post(
            'http://localhost:50021/audio_query',
            params=params,
            timeout=5.0
        )
        audio_query = query_response.json()
        
        # 高速化設定
        audio_query['speedScale'] = speed
        audio_query['pauseLength'] = 0.1
        audio_query['pauseLengthScale'] = 0.3
        # 話し出し前の無音を確保（オーディオデバイスのウェイクアップ対策）
        audio_query['prePhonemeLength'] = 0.5
        # 先頭数モーラを強調（pitchを上げ、母音を少し伸ばす）
        if emphasis_moras > 0:
            _emphasize_initial_moras(audio_query, num_moras=emphasis_moras, pitch_boost=emphasis_pitch, length_scale=emphasis_length)

        # 音声合成
        synthesis_response = requests.post(
            'http://localhost:50021/synthesis',
            params={'speaker': speaker},
            json=audio_query,
            headers={'Content-Type': 'application/json'},
            timeout=10.0
        )
        
        # 一時ファイル経由で再生（afplayはパイプ非対応）
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(synthesis_response.content)
            temp_path = f.name
        
        subprocess.run(['afplay', temp_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.unlink(temp_path)
        
    except requests.exceptions.ConnectionError:
        print("エラー: VOICEVOXエンジンが起動していません", file=sys.stderr)
        # VOICEVOXがインストールされているか確認
        from pathlib import Path
        if not Path("voicevox_engine").exists():
            # 標準入力が端末でない場合（パイプ等）は自動セットアップをスキップ
            if not sys.stdin.isatty():
                print("\nVOICEVOXがインストールされていません", file=sys.stderr)
                print("セットアップ: vsay engine setup", file=sys.stderr)
                print("起動: vsay engine start", file=sys.stderr)
                sys.exit(1)
            
            print("\nVOICEVOXがインストールされていません。セットアップしますか？ (y/N)", file=sys.stderr)
            response = input().strip().lower()
            if response in ['y', 'yes']:
                print("\nセットアップを実行します...", file=sys.stderr)
                subprocess.run(['uv', 'run', 'python', 'voicevox_manager.py', 'setup'])
                sys.exit(0)
            else:
                print("セットアップ: vsay engine setup", file=sys.stderr)
                print("起動: vsay engine start", file=sys.stderr)
                sys.exit(1)
        else:
            print("起動: vsay engine start", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)

def main(args):
    if not args.text:
        # 標準入力から読む
        text = sys.stdin.read().strip()
    else:
        text = ' '.join(args.text)
    
    if text:
        speak(text, args.speaker, args.rate, args.emphasis_moras, args.emphasis_pitch, args.emphasis_length)

def add_arguments(parser):
    parser.add_argument('text', nargs='*', help='読み上げるテキスト')
    parser.add_argument('--speaker', type=int, default=3, help='話者ID (デフォルト: 3=ずんだもん)')
    parser.add_argument('--rate', type=float, default=1.2, help='話速 (デフォルト: 1.2)')
    parser.add_argument('--emphasis-moras', type=int, default=3, help='先頭強調モーラ数 (0で無効, デフォルト: 3)')
    parser.add_argument('--emphasis-pitch', type=float, default=0.1, help='先頭強調pitch加算 (デフォルト: 0.1)')
    parser.add_argument('--emphasis-length', type=float, default=1.3, help='先頭強調母音倍率 (デフォルト: 1.3)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='VOICEVOXで音声合成（直接実行）')
    add_arguments(parser)
    args = parser.parse_args()
    main(args)