"""Serve the fine-tuned model behind a minimal OpenAI-compatible API.

Point the bot at it with:
    LLM_API_KEY=local LLM_API_BASE=http://127.0.0.1:8001/v1 LLM_MODEL=kalshi-llm
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from pydantic import BaseModel

log = logging.getLogger("kalshi_bot")

DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "kalshi-llm"
    messages: list[ChatMessage]
    temperature: float = 0.2
    max_tokens: int = 512


def create_app(model_dir: str, base_model: str = DEFAULT_BASE_MODEL) -> FastAPI:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    base = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype=torch.float32)
    model = PeftModel.from_pretrained(base, model_dir)
    model.eval()

    app = FastAPI(title="Kalshi fine-tuned LLM")

    @app.post("/v1/chat/completions")
    def chat(req: ChatRequest) -> dict:
        prompt = tokenizer.apply_chat_template(
            [m.model_dump() for m in req.messages],
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=req.max_tokens,
                do_sample=req.temperature > 0,
                temperature=max(req.temperature, 0.01),
                pad_token_id=tokenizer.eos_token_id,
            )
        text = tokenizer.decode(
            output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        }

    return app


def serve(model_dir: str, host: str = "127.0.0.1", port: int = 8001) -> None:
    import uvicorn

    uvicorn.run(create_app(model_dir), host=host, port=port)
