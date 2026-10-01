#!/usr/bin/env -S uv run --no-project --python 3.13
"""常駐モデルで音声認識から模擬操作、音声応答までつなぐ。"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import unidic
import unidic_lite
from llama_cpp import Llama
from silero_vad import get_speech_timestamps, load_silero_vad
from transformers import AutoTokenizer

unidic.DICDIR = unidic_lite.DICDIR
from kokoro import KPipeline

ROOT = Path(__file__).resolve().parent
POC = ROOT.parent
MODEL = POC / "llm-local/models/qwen3-4b-gguf/Qwen_Qwen3-4B-Q4_K_M.gguf"
TOKENIZER = POC / "llm-local/models/qwen3-4b-mlx"
TRANSCRIBE = POC / "speech-transcriber/transcribe"
TOOLS = [
    {"name": "light.set", "parameters": {"room": "string", "on": "boolean", "brightness": "integer (0-100, optional)"}},
    {"name": "aircon.set", "parameters": {"room": "string", "mode": "cool|heat|off", "temp": "number (optional for off)"}},
    {"name": "timer.set", "parameters": {"minutes": "number", "label": "string"}},
    {"name": "weather.get", "parameters": {"when": "string"}},
    {"name": "answer", "parameters": {"text": "string"}},
    {"name": "ask", "parameters": {"question": "string"}},
]
PROMPT = """あなたは日本語の音声アシスタントです。ユーザーの発話を解釈し、以下のツールを呼んでください。
ツール定義: {tools}
必ず JSON オブジェクトのみを返してください。形式: {{"calls":[{{"name":"ツール名","arguments":{{...}}}}]}}。
複数対象なら calls に複数のツール呼び出しを入れます。雑談や質問への直接回答には answer を使用します。家電操作で部屋が未指定のときや操作内容が曖昧なときは、推測して家電操作せず、必ず ask(question) で聞き返してください。部屋と操作内容が明確な場合は、確認を挟まず該当する家電操作ツールを呼んでください。現在時刻を知らない場合は時刻を捏造しないでください。""".format(tools=json.dumps(TOOLS, ensure_ascii=False))
RESULT = re.compile(r"\bfinal\s+(.+)$")


def timestamp(start, label, value=""):
    print(f"[t=+{time.perf_counter() - start:.3f}] {label}{value}", file=sys.stderr, flush=True)


def speech_present(wav, vad):
    audio, rate = sf.read(wav, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if rate != 16000:
        import torch
        audio = torch.nn.functional.interpolate(torch.from_numpy(audio)[None, None, :], size=round(len(audio) * 16000 / rate), mode="linear", align_corners=False).numpy().reshape(-1)
    return bool(get_speech_timestamps(audio, vad, sampling_rate=16000, min_silence_duration_ms=300, min_speech_duration_ms=100, speech_pad_ms=0))


def generate(model, tokenizer, utterance, start):
    messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": utterance}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    parts = []
    first = False
    for chunk in model.create_completion(prompt=prompt, stream=True, max_tokens=180, temperature=0):
        piece = chunk["choices"][0]["text"]
        if piece and not first:
            timestamp(start, "llm_first_token")
            first = True
        parts.append(piece)
    timestamp(start, "llm_done")
    raw = "".join(parts).strip()
    if raw.startswith("<think>\n\n</think>"):
        raw = raw[len("<think>\n\n</think>"):].strip()
    try:
        calls = json.loads(raw)["calls"]
        if not isinstance(calls, list) or not calls:
            raise ValueError("空のツール呼び出し")
        return calls
    except (KeyError, TypeError, ValueError) as exc:
        print(f"LLM の応答を解釈できません: {exc}; raw={raw!r}", file=sys.stderr)
        return [{"name": "ask", "arguments": {"question": "すみません、もう一度お願いします。"}}]


def execute(calls):
    responses = []
    for call in calls:
        name = call.get("name")
        arguments = call.get("arguments")
        if not isinstance(arguments, dict):
            responses.append("すみません、もう一度お願いします。")
            continue
        if name in ("light.set", "aircon.set"):
            room = arguments.get("room")
            if not isinstance(room, str) or not room.strip() or room.strip() in ("部屋", "全体", "どこか", "不明"):
                responses.append("どの部屋ですか？")
                continue
            if name == "light.set" and isinstance(arguments.get("on"), bool):
                print(f"MOCK {name} {json.dumps(arguments, ensure_ascii=False)}", flush=True)
                responses.append(f"{room}の電気を{'つけ' if arguments['on'] else '消し'}ました。")
            elif name == "aircon.set" and arguments.get("mode") in ("cool", "heat", "off"):
                print(f"MOCK {name} {json.dumps(arguments, ensure_ascii=False)}", flush=True)
                responses.append(f"{room}のエアコンを{'止め' if arguments['mode'] == 'off' else '設定し'}ました。")
            else:
                responses.append("設定を確認させてください。")
        elif name == "timer.set" and isinstance(arguments.get("minutes"), (int, float)):
            print(f"MOCK {name} {json.dumps(arguments, ensure_ascii=False)}", flush=True)
            responses.append(f"{arguments['minutes']}分のタイマーを設定しました。")
        elif name == "weather.get":
            print(f"MOCK {name} {json.dumps(arguments, ensure_ascii=False)}", flush=True)
            responses.append("天気情報にはまだ接続していません。")
        elif name in ("answer", "ask"):
            text = arguments.get("text" if name == "answer" else "question")
            responses.append(text if isinstance(text, str) and text.strip() else "もう一度お願いします。")
        else:
            responses.append("その操作にはまだ対応していません。")
    return " ".join(responses)


def synthesize(text, tts, path):
    if isinstance(tts, KPipeline):
        chunks = list(tts(text, voice="jf_alpha"))
        if not chunks:
            raise RuntimeError("音声合成の出力が空です")
        sf.write(path, np.concatenate([chunk.audio.numpy() for chunk in chunks]), 24000)
    else:
        assert tts.stdin is not None and tts.stdout is not None
        tts.stdin.write(json.dumps({"text": text, "path": str(path)}, ensure_ascii=False) + "\n")
        tts.stdin.flush()
        if tts.stdout.readline().strip() != "done":
            raise RuntimeError("Irodori 音声合成プロセスが失敗しました")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    input_mode = parser.add_mutually_exclusive_group(required=True)
    input_mode.add_argument("--wav", type=Path, help="音声ファイルを実時間で認識")
    input_mode.add_argument("--mic", action="store_true", help="マイクで 10 秒間認識")
    parser.add_argument("--tts", choices=("kokoro", "irodori"), default="kokoro")
    parser.add_argument("--no-play", action="store_true")
    args = parser.parse_args()
    if args.mic and args.no_play:
        parser.error("マイクモードでは再生を無効化しないでください")

    print("モデルをロードしています", file=sys.stderr, flush=True)
    model = Llama(model_path=str(MODEL), n_ctx=2048, n_gpu_layers=-1, verbose=False)
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER)
    vad = load_silero_vad(onnx=True)
    if args.tts == "kokoro":
        tts = KPipeline(lang_code="j")
        list(tts("準備できました。", voice="jf_alpha"))
    else:
        irodori = POC / "tts-irodori-voicevox/Irodori-TTS"
        tts = subprocess.Popen([str(irodori / ".venv/bin/python"), str(ROOT / "irodori_worker.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        assert tts.stdout is not None
        if tts.stdout.readline().strip() != "ready":
            raise RuntimeError("Irodori 音声合成プロセスを起動できません")
    print("ready", file=sys.stderr, flush=True)
    command = [str(TRANSCRIBE), "--mic" if args.mic else str(args.wav)]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1) as process:
        assert process.stdout is not None
        try:
            if args.wav and not speech_present(args.wav, vad):
                raise RuntimeError(f"Silero VAD は音声を検出しませんでした: {args.wav}")
            for line in process.stdout:
                match = RESULT.search(line)
                if not match:
                    if "microphoneAuthorization=" in line or "micStarted=" in line:
                        print(line.rstrip(), file=sys.stderr, flush=True)
                    continue
                start = time.perf_counter()
                utterance = match.group(1).strip()
                timestamp(start, "final: ", utterance)
                calls = generate(model, tokenizer, utterance, start)
                response = execute(calls)
                print(f"RESPONSE {response}", flush=True)
                output = ROOT / "response.wav"
                synthesize(response, tts, output)
                timestamp(start, "tts_done")
                if not args.no_play:
                    timestamp(start, "play_start")
                    subprocess.run(["afplay", str(output)], check=True)
                if args.wav:
                    break
        finally:
            if args.wav and process.poll() is None:
                process.terminate()
            try:
                _, errors = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _, errors = process.communicate()
            if errors:
                print(errors, file=sys.stderr, end="")
            if process.returncode not in (0, -15):
                raise RuntimeError(f"音声認識が終了しました (code={process.returncode})")


if __name__ == "__main__":
    main()
