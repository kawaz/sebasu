import statistics
import time
from pathlib import Path

import soundfile as sf
from huggingface_hub import hf_hub_download
from style_bert_vits2.constants import Languages
from style_bert_vits2.nlp import bert_models
from style_bert_vits2.tts_model import TTSModel

from bench import OUT, TEXTS, duration

FILES = ["jvnv-F1-jp/jvnv-F1-jp_e160_s14000.safetensors", "jvnv-F1-jp/config.json", "jvnv-F1-jp/style_vectors.npy"]
start = time.perf_counter()
paths = [Path(hf_hub_download("litagin/style_bert_vits2_jvnv", name)) for name in FILES]
bert_models.load_model(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm").float()
bert_models.load_tokenizer(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")
model = TTSModel(model_path=paths[0], config_path=paths[1], style_vec_path=paths[2], device="cpu")
model.load()
print(f"style-bert load (including cached model fetching): {time.perf_counter() - start:.3f}s", flush=True)
for name, text in TEXTS.items():
    timings = []
    for trial in range(3):
        start = time.perf_counter()
        sr, audio = model.infer(text=text)
        timings.append(time.perf_counter() - start)
        print(f"style-bert {name} trial {trial + 1}: {timings[-1]:.3f}s", flush=True)
    path = OUT / f"style-bert-{name}.wav"
    sf.write(path, audio, sr)
    seconds = duration(path)
    median = statistics.median(timings)
    print(f"style-bert {name}: {median:.3f}s, audio {seconds:.3f}s, RTF {median / seconds:.3f}, trials {timings}", flush=True)
