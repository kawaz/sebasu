#!/usr/bin/env python3
"""
マクロス7の熱気バサラをVOICEVOXキャラクターが褒める
"""
import requests
import json
import time
import os

def generate_voice(text, speaker_id, output_name):
    """音声を生成して保存"""
    try:
        # 音声クエリの生成
        params = {'text': text, 'speaker': speaker_id}
        query_response = requests.post(
            'http://localhost:50021/audio_query',
            params=params
        )
        
        # 音声の合成
        synthesis_response = requests.post(
            'http://localhost:50021/synthesis',
            params={'speaker': speaker_id},
            json=query_response.json(),
            headers={'Content-Type': 'application/json'}
        )
        
        # 保存
        filename = f'outputs/{output_name}.wav'
        with open(filename, 'wb') as f:
            f.write(synthesis_response.content)
        
        print(f"✓ {output_name}: {filename}")
        return True
        
    except Exception as e:
        print(f"✗ {output_name}: エラー - {e}")
        return False

def main():
    # VOICEVOXが起動しているか確認
    try:
        response = requests.get('http://localhost:50021/version', timeout=1)
        print(f"VOICEVOX Engine: {response.text.strip()}")
    except:
        print("エラー: VOICEVOXエンジンが起動していません")
        print("別のターミナルで以下を実行してください:")
        print("(cd .worktrees/feature-tts-comparison/sandbox/tts-comparison && uv run python voicevox_manager.py start)")
        return
    
    print("\n=== 熱気バサラ賛歌 ===\n")
    
    # 各キャラクターのセリフ
    characters = [
        {
            'id': 3,
            'name': 'ずんだもん',
            'text': 'バサラさんは本当にすごいのだ！歌で戦争を止めようなんて、普通は考えつかないのだ。でも、バサラさんは自分の歌を信じて、最後まで歌い続けたのだ。俺の歌を聴けー！って叫ぶ姿がかっこいいのだ！'
        },
        {
            'id': 2,
            'name': '四国めたん',
            'text': 'バサラさんって、ほんまに熱い人やなぁ。ファイヤーボンバーのボーカルとして、戦場でも歌うなんて普通やないで。でも、その真っ直ぐな想いが、プロトデビルンにも届いたんやから、すごいことやと思うわ。'
        },
        {
            'id': 8,
            'name': '春日部つむぎ',
            'text': 'バサラさんの「俺の歌を聴けー！」って言葉、すごく印象的です。音楽には人の心を動かす力があるって、バサラさんが証明してくれました。トライアゲイン！プラネットダンス！最高です！'
        },
        {
            'id': 14,
            'name': '冥鳴ひまり',
            'text': 'バサラさんみたいに、自分の信念を曲げない人って素敵だと思います。歌バカって言われても、ひたすら歌い続ける姿勢は、アーティストの鑑ですね。ホーリーロンリーライト、私も歌ってみたいな。'
        },
        {
            'id': 1,
            'name': '四国めたん（あまあま）',
            'text': 'バサラさぁん、かっこええわぁ～。赤いバルキリーで戦場に飛び込んで、ミサイル撃たんと歌うなんて、ほんまにロマンチックやわ。スピーカーポッドから響く歌声で、みんなを救うなんて素敵すぎるぅ～。'
        }
    ]
    
    # 音声を生成
    for char in characters:
        print(f"\n{char['name']} (ID: {char['id']})")
        print(f"「{char['text']}」")
        
        output_name = f"basara_{char['name'].replace('（', '_').replace('）', '')}"
        generate_voice(char['text'], char['id'], output_name)
        
        time.sleep(0.5)  # API負荷軽減のため少し待つ
    
    print("\n=== 完了！ ===")
    print("生成された音声ファイルは outputs/ ディレクトリにあります")

if __name__ == "__main__":
    main()