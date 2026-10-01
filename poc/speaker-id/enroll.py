"""Create enrollment utterances or average their speaker embeddings."""
import argparse
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

VOICES = ("Kyoko", "Flo (日本語（日本）)", "Grandpa (日本語（日本）)")
ENROLL_TEXT = ("今日の夕食は何にしようかな。明日は早起きして散歩に出かけます。", "窓の外には青い空が広がっています。温かいお茶を飲みましょう。", "週末には公園へ行って、ゆっくり本を読むつもりです。")
TEST_TEXT = ("電気消して", "おはよう", "今日の天気は", "音楽かけて", "ちょっと待って", "ありがとう")


def audio(path):
    signal, sr = sf.read(path, always_2d=True)
    signal = signal.mean(axis=1)
    if sr != 16000:
        from math import gcd
        divisor = gcd(sr, 16000)
        signal = resample_poly(signal, 16000 // divisor, sr // divisor)
    return signal.astype('float32')


def encoder(model):
    start = time.perf_counter()
    if model == 'speechbrain':
        import torch
        from speechbrain.inference.speaker import EncoderClassifier
        instance = EncoderClassifier.from_hparams(source='speechbrain/spkrec-ecapa-voxceleb', savedir=str(Path(__file__).parent / '.models' / 'speechbrain'), run_opts={'device': 'cpu'})
        def embed(signal):
            with torch.inference_mode():
                return instance.encode_batch(torch.from_numpy(signal).unsqueeze(0)).flatten().numpy()
    elif model == 'wespeaker':
        import wespeaker
        instance = wespeaker.load_model('english')
        def embed(signal):
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav') as temporary:
                sf.write(temporary.name, signal, 16000)
                return np.asarray(instance.extract_embedding(temporary.name)).flatten()
    else:
        raise ValueError(f'unsupported model: {model}')
    return embed, time.perf_counter() - start


def generate(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for index, voice in enumerate(VOICES):
        for group, sentences in [('enroll', ENROLL_TEXT), ('test', TEST_TEXT)]:
            for number, text in enumerate(sentences):
                for rate in ([180, 150, 220] if group == 'test' else [180]):
                    path = directory / f'voice{index}-{group}{number}-r{rate}.wav'
                    if path.exists() and sf.info(path).frames >= 1600:
                        continue
                    intermediate = path.with_suffix('.aiff')
                    for attempt in range(3):
                        subprocess.run(['/usr/bin/say', '-v', voice, '-r', str(rate), '-o', str(intermediate), text], check=True)
                        try:
                            signal = audio(intermediate)
                        except (OSError, RuntimeError):
                            continue
                        if len(signal) >= 1600:
                            sf.write(path, signal, 16000, subtype='PCM_16')
                            intermediate.unlink()
                            break
                    else:
                        raise RuntimeError(f'failed to synthesize nonempty audio: {path}')


def enrollment(model, directory):
    embed, load_seconds = encoder(model)
    profiles = {}
    for index in range(len(VOICES)):
        vectors = [embed(audio(directory / f'voice{index}-enroll{n}-r180.wav')) for n in range(3)]
        vector = np.mean(vectors, axis=0)
        profiles[f'voice{index}'] = (vector / np.linalg.norm(vector)).tolist()
    path = directory / f'{model}-profiles.json'
    path.write_text(json.dumps({'model': model, 'voices': VOICES, 'profiles': profiles, 'load_seconds': load_seconds}, ensure_ascii=False))
    print(f'{model} load={load_seconds:.3f}s profiles={path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['speechbrain', 'wespeaker'], default='speechbrain')
    parser.add_argument('--directory', type=Path, default=Path(__file__).parent / 'audio')
    parser.add_argument('--generate', action='store_true')
    args = parser.parse_args()
    if args.generate:
        generate(args.directory)
    else:
        enrollment(args.model, args.directory)
