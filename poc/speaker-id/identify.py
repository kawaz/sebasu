"""Compare test utterances against averaged voice profiles."""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from enroll import audio, encoder


def identify(model, directory, seconds, rate):
    metadata = json.loads((directory / f'{model}-profiles.json').read_text())
    profiles = {name: np.asarray(vector) for name, vector in metadata['profiles'].items()}
    embed, load_seconds = encoder(model)
    timings = []
    margins = []
    correct = 0
    count = 0
    print(f'model={model} duration={seconds or "full"} rate={rate} load={load_seconds:.3f}s')
    print('true utterance ' + ' '.join(profiles) + ' margin')
    for speaker in profiles:
        for number in range(6):
            signal = audio(directory / f'{speaker}-test{number}-r{rate}.wav')
            if seconds:
                signal = signal[:int(seconds * 16000)]
            if len(signal) < 1600:
                continue
            samples = []
            vectors = []
            for _ in range(3):
                start = time.perf_counter()
                vectors.append(embed(signal))
                samples.append(time.perf_counter() - start)
            timings.append(float(np.median(samples)))
            vector = vectors[-1] / np.linalg.norm(vectors[-1])
            similarities = {name: float(np.dot(vector, profile)) for name, profile in profiles.items()}
            other = max(score for name, score in similarities.items() if name != speaker)
            margin = similarities[speaker] - other
            margins.append(margin)
            correct += max(similarities, key=similarities.get) == speaker
            count += 1
            print(f'{speaker} {number} ' + ' '.join(f'{score:.3f}' for score in similarities.values()) + f' {margin:+.3f}')
    print(f'accuracy={correct}/{count} ({correct/count:.1%}); median_margin={np.median(margins):+.3f}; median_embedding_seconds={np.median(timings):.3f}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['speechbrain', 'wespeaker'], default='speechbrain')
    parser.add_argument('--directory', type=Path, default=Path(__file__).parent / 'audio')
    parser.add_argument('--seconds', type=float)
    parser.add_argument('--rate', type=int, choices=[150, 180, 220], default=180)
    args = parser.parse_args()
    identify(args.model, args.directory, args.seconds, args.rate)
