"""File-only, reproducible VAD and wake-word smoke test."""
from pathlib import Path
from time import perf_counter
import numpy as np
import soundfile as sf
import webrtcvad
from silero_vad import load_silero_vad, get_speech_timestamps
import sherpa_onnx

ROOT = Path(__file__).resolve().parent
RATE = 16000
speech, sr = sf.read(ROOT / 'ja.wav', dtype='float32')
assert sr == RATE
speech = speech.reshape(-1)
silence = np.zeros(RATE, dtype=np.float32)
# Separate two utterances by a 600 ms gap, with 1 s lead/trail.
inside = np.zeros(9600, dtype=np.float32)
raw = np.concatenate([silence, speech, inside, speech, silence])
reference = [(1., 1. + len(speech)/RATE), (1.6 + len(speech)/RATE, 1.6 + 2*len(speech)/RATE)]
model_file = next((ROOT / '.venv/lib').glob('python*/site-packages/silero_vad/data/silero_vad.onnx'))
for label, noise_level in [('clean', 0.), ('noise-minus-40db', 0.01)]:
    samples = raw.copy()
    if noise_level:
        samples += np.random.default_rng(42).normal(0, noise_level, len(samples)).astype(np.float32)
        samples = np.clip(samples, -1, 1)
    sf.write(ROOT / (label + '.wav'), samples, RATE)
    print(f'{label} duration={len(samples)/RATE:.3f}s reference={[(round(a,3),round(b,3)) for a,b in reference]}')
    t = perf_counter()
    model = load_silero_vad(onnx=True)
    started = perf_counter()
    stamps = get_speech_timestamps(samples, model, sampling_rate=RATE, min_silence_duration_ms=300, min_speech_duration_ms=100, speech_pad_ms=0)
    spans = [(s['start']/RATE, s['end']/RATE) for s in stamps]
    print(f'  silero: {spans}, processing={(perf_counter()-started)*1000:.1f}ms, init={(started-t)*1000:.1f}ms, chunk=32ms, end-hold=300ms')
    vad = webrtcvad.Vad(2)
    started = perf_counter()
    frame = 320
    pcm = (samples*32767).astype('<i2')
    flags = [vad.is_speech(pcm[k:k+frame].tobytes(), RATE) for k in range(0, len(pcm)-frame+1, frame)]
    spans=[]; active=None; silence_count=0
    # The WebRTC library emits frame booleans, not endpoints; this is explicit 300ms endpoint logic.
    for i, flag in enumerate(flags):
        if flag:
            if active is None: active=i*0.02
            silence_count=0
        elif active is not None:
            silence_count+=1
            if silence_count>=15:
                spans.append((active, (i-14)*0.02)); active=None; silence_count=0
    if active is not None: spans.append((active,len(flags)*0.02))
    print(f'  webrtcvad: {spans}, processing={(perf_counter()-started)*1000:.1f}ms, chunk=20ms, application-end-hold=300ms (library hangover additional)')
    t = perf_counter()
    config=sherpa_onnx.VadModelConfig(silero_vad=sherpa_onnx.SileroVadModelConfig(model=str(model_file), threshold=0.5, min_silence_duration=0.3, min_speech_duration=0.1, window_size=512), sample_rate=RATE, num_threads=1)
    detector=sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)
    started=perf_counter()
    for k in range(0,len(samples),512): detector.accept_waveform(samples[k:k+512])
    detector.flush()
    spans=[]
    while not detector.empty():
        item=detector.front
        spans.append((item.start/RATE, (item.start+len(item.samples))/RATE))
        detector.pop()
    print(f'  sherpa-onnx: {spans}, processing={(perf_counter()-started)*1000:.1f}ms, init={(started-t)*1000:.1f}ms, chunk=32ms, end-hold=300ms')
