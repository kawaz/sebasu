#!/usr/bin/env python3
"""
感情豊かなバサラ賛歌 - 各キャラクターの感情スタイルを使用
"""
import requests
import json
import time

def get_available_styles():
    """利用可能な話者とスタイルを取得"""
    response = requests.get('http://localhost:50021/speakers')
    speakers = response.json()
    
    print("=== 利用可能なスタイル ===")
    for speaker in speakers[:10]:  # 最初の10人
        print(f"\n{speaker['name']}:")
        for style in speaker['styles']:
            print(f"  - {style['name']} (ID: {style['id']})")
    
    return speakers

def apply_basara_accent(audio_query):
    """バサラさんのアクセントを中高型に調整"""
    # 「バサラさん」を探して調整
    for phrase in audio_query['accent_phrases']:
        moras = phrase['moras']
        # 5モーラの場合、バサラさんの可能性が高い
        if len(moras) >= 5:
            # 最初の5モーラをチェック
            if (moras[0]['text'] == 'バ' and 
                moras[1]['text'] == 'サ' and 
                moras[2]['text'] == 'ラ'):
                # 中高型に調整
                moras[0]['pitch'] = 5.0  # バ（低）
                moras[1]['pitch'] = 6.5  # サ（高）
                moras[2]['pitch'] = 6.5  # ラ（高）
                if len(moras) > 3:
                    moras[3]['pitch'] = 5.0  # さ（低）
                if len(moras) > 4:
                    moras[4]['pitch'] = 5.0  # ん（低）
    
    return audio_query

def generate_emotional_voice(text, style_id, style_name, output_name):
    """感情を込めた音声を生成"""
    try:
        # 音声クエリの生成
        params = {'text': text, 'speaker': style_id}
        query_response = requests.post(
            'http://localhost:50021/audio_query',
            params=params
        )
        audio_query = query_response.json()
        
        # バサラさんのアクセントを調整
        audio_query = apply_basara_accent(audio_query)
        
        # 感情に応じたパラメータ調整
        if '興奮' in style_name or 'ツンツン' in style_name:
            audio_query['speedScale'] = 1.1  # 少し速く
            audio_query['pitchScale'] = 1.05  # 少し高く
            audio_query['intonationScale'] = 1.5  # 抑揚強め
        elif 'ささやき' in style_name or 'ひそひそ' in style_name:
            audio_query['speedScale'] = 0.9  # ゆっくり
            audio_query['volumeScale'] = 0.7  # 音量控えめ
            audio_query['intonationScale'] = 0.8  # 抑揚弱め
        elif 'あまあま' in style_name:
            audio_query['speedScale'] = 0.95  # 少しゆっくり
            audio_query['intonationScale'] = 1.3  # 抑揚強め
        
        # 音声の合成
        synthesis_response = requests.post(
            'http://localhost:50021/synthesis',
            params={'speaker': style_id},
            json=audio_query,
            headers={'Content-Type': 'application/json'}
        )
        
        # 保存
        filename = f'outputs/{output_name}.wav'
        with open(filename, 'wb') as f:
            f.write(synthesis_response.content)
        
        print(f"✓ {style_name}: {filename}")
        return True
        
    except Exception as e:
        print(f"✗ {style_name}: エラー - {e}")
        return False

def main():
    # VOICEVOXエンジンの確認
    try:
        response = requests.get('http://localhost:50021/version', timeout=1)
        print(f"VOICEVOX Engine: {response.text.strip()}\n")
    except:
        print("エラー: VOICEVOXエンジンが起動していません")
        return
    
    # 利用可能なスタイルを確認
    speakers = get_available_styles()
    
    print("\n\n=== 感情豊かなバサラ賛歌 ===\n")
    
    # 各キャラクターの感情表現
    emotional_speeches = [
        {
            'style_id': 3,
            'style_name': 'ずんだもん（ノーマル）',
            'text': 'バサラさんは本当にすごいのだ！歌で戦争を止めようなんて、普通は考えつかないのだ！俺の歌を聴けー！って叫ぶ姿に、ずんだもんは感動したのだ！',
            'output': 'emotional_zundamon_normal'
        },
        {
            'style_id': 7,
            'style_name': 'ずんだもん（ささやき）',
            'text': 'バサラさんの歌は...本当に心に響くのだ...。あの優しい歌声で、プロトデビルンの心も溶かしたんだ...。すごいのだ...',
            'output': 'emotional_zundamon_whisper'
        },
        {
            'style_id': 2,
            'style_name': '四国めたん（ノーマル）',
            'text': 'バサラさんって、ほんまに熱い人やわ！ミサイルより歌を選ぶなんて、普通できひんで！その真っ直ぐな心が、みんなに勇気をくれるんや！',
            'output': 'emotional_metan_normal'
        },
        {
            'style_id': 0,
            'style_name': '四国めたん（あまあま）',
            'text': 'バサラさぁん、かっこええわぁ〜！赤いバルキリーで飛び回って、歌で世界を救うなんて、ほんまにロマンチックやわぁ〜！大好きやでぇ〜！',
            'output': 'emotional_metan_sweet'
        },
        {
            'style_id': 6,
            'style_name': '四国めたん（ツンツン）',
            'text': 'べ、別にバサラさんがすごいとか思ってへんし！でも...歌バカって言われても信念を曲げへんところは...ちょっとだけ認めたるわ！',
            'output': 'emotional_metan_tsun'
        },
        {
            'style_id': 8,
            'style_name': '春日部つむぎ（ノーマル）',
            'text': 'バサラさんの「俺の歌を聴けー！」という叫び、今でも心に残っています。音楽の力で平和を作れるって、バサラさんが教えてくれました！',
            'output': 'emotional_tsumugi_normal'
        },
        {
            'style_id': 14,
            'style_name': '冥鳴ひまり（ノーマル）',
            'text': 'バサラさんみたいに、自分の歌を信じ続けられる人って素敵です。戦場でも歌い続ける勇気...私も見習いたいな。トライアゲイン！',
            'output': 'emotional_himari_normal'
        },
        {
            'style_id': 16,
            'style_name': 'ナースロボ＿タイプＴ（ノーマル）',
            'text': 'バサラさんのバイタルサイン、異常ナシ。むしろ歌っている時の生体反応は最高値を記録。これが...情熱というものデスネ。素晴らしいデス。',
            'output': 'emotional_nurse_normal'
        },
        {
            'style_id': 52,
            'style_name': '雨晴はう（ノーマル）',
            'text': 'バサラさんって、すっごくかっこいいです！ファイヤーボンバーの曲、私も大好きで...プラネットダンス、一緒に歌いたいなぁ！',
            'output': 'emotional_hau_normal'
        },
        {
            'style_id': 11,
            'style_name': '玄野武宏（ノーマル・興奮気味に）',
            'text': 'バサラ！お前は最高だ！歌で戦争を止めるなんて、普通の奴には思いつかねぇ！その熱い魂、俺も見習わせてもらうぜ！',
            'output': 'emotional_takehiro_excited'
        }
    ]
    
    # 音声を生成
    for speech in emotional_speeches:
        print(f"\n{speech['style_name']}:")
        print(f"「{speech['text']}」")
        
        generate_emotional_voice(
            speech['text'],
            speech['style_id'],
            speech['style_name'],
            speech['output']
        )
        
        time.sleep(0.5)
    
    print("\n=== 完了！ ===")
    print("\n連続再生: for file in outputs/emotional_*.wav; do afplay \"$file\"; sleep 0.5; done")

if __name__ == "__main__":
    main()