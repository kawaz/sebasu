#!/usr/bin/env python3
"""日本語の家電操作・会話を同一条件で評価するローカル LLM ベンチマーク。"""
import argparse
import json
import time
from pathlib import Path

TOOLS = [
    {"name": "light.set", "parameters": {"room": "string", "on": "boolean", "brightness": "integer (0-100, optional)"}},
    {"name": "aircon.set", "parameters": {"room": "string", "mode": "cool|heat|off", "temp": "number (optional for off)"}},
    {"name": "timer.set", "parameters": {"minutes": "number", "label": "string"}},
    {"name": "weather.get", "parameters": {"when": "string"}},
    {"name": "answer", "parameters": {"text": "string"}},
]
PROMPT = """あなたは日本語の音声アシスタントです。ユーザーの発話を解釈し、以下のツールを呼んでください。
ツール定義: {tools}
必ず JSON オブジェクトのみを返してください。形式: {{"calls":[{{"name":"ツール名","arguments":{{...}}}}]}}。
複数対象なら calls に複数のツール呼び出しを入れます。雑談、質問への直接回答、または操作対象の部屋が不明で確認が必要なときは answer を使用して自然な日本語で応答します。部屋が不明な場合は推測せず聞き返してください。現在時刻を知らない場合は時刻を捏造しないでください。""".format(tools=json.dumps(TOOLS, ensure_ascii=False))
CASES = [
    ("リビングの電気消して", ["light.set"]),
    ("寝室のエアコン 26 度で冷房", ["aircon.set"]),
    ("10 分後にお茶って教えて", ["timer.set"]),
    ("明日の天気は", ["weather.get"]),
    ("おはよう", ["answer"]),
    ("電気つけて、あと少し暗めで", ["answer"]),
    ("エアコン止めて", ["answer"]),
    ("今何時", ["answer"]),
    ("ありがとう", ["answer"]),
    ("ダイニングとリビング両方消して", ["light.set", "light.set"]),
]


def evaluate(index, response):
    try:
        data = json.loads(response)
        calls = data["calls"]
        if not isinstance(calls, list) or not all(isinstance(c, dict) and isinstance(c.get("arguments"), dict) for c in calls):
            return False, False
        names = [c.get("name") for c in calls]
        if names != CASES[index][1]:
            return True, False
        args = [c["arguments"] for c in calls]
        if index == 0:
            valid = args[0].get("room") == "リビング" and args[0].get("on") is False
        elif index == 1:
            valid = args[0].get("room") == "寝室" and args[0].get("mode") == "cool" and args[0].get("temp") == 26
        elif index == 2:
            valid = args[0].get("minutes") == 10 and "お茶" in args[0].get("label", "")
        elif index == 3:
            valid = args[0].get("when", "").lower() in ("明日", "tomorrow")
        elif index in (5, 6):
            valid = "?" in args[0].get("text", "") or "？" in args[0].get("text", "") or "どの" in args[0].get("text", "")
        elif index == 9:
            valid = {a.get("room") for a in args} == {"ダイニング", "リビング"} and all(a.get("on") is False for a in args)
        else:
            valid = isinstance(args[0].get("text"), str) and bool(args[0]["text"].strip())
        return True, valid
    except (ValueError, KeyError, TypeError):
        return False, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=["mlx", "llama"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.runtime == "mlx":
        from mlx_lm import load, stream_generate
        from mlx_lm.sample_utils import make_sampler
        model, tokenizer = load(args.model)

        def generate(text):
            messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": text}]
            try:
                prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            except TypeError:
                prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            start = time.perf_counter()
            pieces = []
            first = None
            for result in stream_generate(model, tokenizer, prompt, max_tokens=180, sampler=make_sampler(temp=0)):
                if first is None:
                    first = time.perf_counter()
                pieces.append(result.text)
            end = time.perf_counter()
            return "".join(pieces).strip(), first - start if first else None, end - start
    else:
        from llama_cpp import Llama
        model = Llama(model_path=args.model, n_ctx=2048, n_gpu_layers=-1, verbose=False)
        if "qwen3" in args.model.lower():
            from transformers import AutoTokenizer
            sibling = Path(args.model).parent.parent / ("qwen3-8b-mlx" if "8b" in args.model.lower() else "qwen3-4b-mlx")
            tokenizer = AutoTokenizer.from_pretrained(sibling)

        def generate(text):
            messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": text}]
            start = time.perf_counter()
            if "qwen3" in args.model.lower():
                prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
                stream = model.create_completion(prompt=prompt, stream=True, max_tokens=180, temperature=0)
            else:
                stream = model.create_chat_completion(messages=messages, stream=True, max_tokens=180, temperature=0)
            first = None
            pieces = []
            for item in stream:
                delta = item["choices"][0]
                content = delta.get("text", "") if "qwen3" in args.model.lower() else delta["delta"].get("content", "")
                if content and first is None:
                    first = time.perf_counter()
                pieces.append(content)
            end = time.perf_counter()
            response = "".join(pieces).strip()
            if "qwen3" in args.model.lower() and response.startswith("<think>\n\n</think>"):
                response = response[len("<think>\n\n</think>"):].strip()
            return response, first - start if first else None, end - start

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as output:
        for iteration in range(args.repeat):
            for index, (utterance, _) in enumerate(CASES):
                response, ttft, total = generate(utterance)
                json_valid, correct = evaluate(index, response)
                row = {"runtime": args.runtime, "model": Path(args.model).name, "iteration": iteration, "index": index, "utterance": utterance, "response": response, "json_valid": json_valid, "correct": correct, "ttft_s": ttft, "total_s": total}
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                output.flush()
                print(json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
