import statistics
import time

import soundfile as sf
import unidic
import unidic_lite

unidic.DICDIR = unidic_lite.DICDIR
from kokoro import KPipeline

from bench import OUT, TEXTS, duration

start = time.perf_counter()
pipeline = KPipeline(lang_code="j")
print(f"kokoro pipeline initialization: {time.perf_counter() - start:.3f}s", flush=True)
start = time.perf_counter()
list(pipeline(TEXTS["short"], voice="jf_alpha"))
print(f"kokoro model and first inference initialization: {time.perf_counter() - start:.3f}s", flush=True)
for name, text in TEXTS.items():
    timings = []
    for trial in range(3):
        start = time.perf_counter()
        chunks = list(pipeline(text, voice="jf_alpha"))
        timings.append(time.perf_counter() - start)
        print(f"kokoro {name} trial {trial + 1}: {timings[-1]:.3f}s, chunks {len(chunks)}", flush=True)
    import numpy as np

    audio = np.concatenate([chunk.audio.numpy() for chunk in chunks])
    path = OUT / f"kokoro-{name}.wav"
    sf.write(path, audio, 24000)
    seconds = duration(path)
    median = statistics.median(timings)
    print(f"kokoro {name}: {median:.3f}s, audio {seconds:.3f}s, RTF {median / seconds:.3f}, trials {timings}", flush=True)
