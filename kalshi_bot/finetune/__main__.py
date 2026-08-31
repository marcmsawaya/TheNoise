"""CLI: python -m kalshi_bot.finetune {dataset,train,serve}"""

from __future__ import annotations

import argparse
import logging

from ..config import BotConfig


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="kalshi_bot.finetune")
    sub = parser.add_subparsers(dest="command", required=True)

    p_data = sub.add_parser("dataset", help="build training data from settled Kalshi markets")
    p_data.add_argument("--out", default="finetune_data/train.jsonl")
    p_data.add_argument("--per-series", type=int, default=200)

    p_train = sub.add_parser("train", help="LoRA fine-tune a small open model")
    p_train.add_argument("--data", default="finetune_data/train.jsonl")
    p_train.add_argument("--out", default="kalshi-llm")
    p_train.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p_train.add_argument("--epochs", type=float, default=3.0)
    p_train.add_argument("--max-steps", type=int, default=-1)

    p_serve = sub.add_parser("serve", help="serve the fine-tuned model (OpenAI-compatible)")
    p_serve.add_argument("--model-dir", default="kalshi-llm")
    p_serve.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8001)

    args = parser.parse_args()

    if args.command == "dataset":
        from .dataset import build_dataset

        n = build_dataset(BotConfig().scan_series, args.out, args.per_series)
        print(f"wrote {n} examples to {args.out}")
        return 0

    if args.command == "train":
        from .train import train

        train(args.data, args.out, args.base_model, args.epochs, args.max_steps)
        return 0

    if args.command == "serve":
        from .serve import serve

        serve(args.model_dir, args.host, args.port)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
