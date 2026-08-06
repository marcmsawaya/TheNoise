"""LoRA fine-tune a small open model on the Kalshi trading dataset.

Runs on CPU with a small base model (default Qwen2.5-0.5B-Instruct); use a GPU
and a larger base for better quality. Requires the `finetune` extra:
`pip install -e ".[finetune]"`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("kalshi_bot")

DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


def train(
    dataset_path: str,
    output_dir: str = "kalshi-llm",
    base_model: str = DEFAULT_BASE_MODEL,
    epochs: float = 3.0,
    max_steps: int = -1,
    lr: float = 2e-4,
) -> str:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    rows = [json.loads(line) for line in Path(dataset_path).read_text().splitlines() if line]
    if not rows:
        raise ValueError(f"no training examples in {dataset_path}")
    log.info("loaded %d examples from %s", len(rows), dataset_path)

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype=torch.float32)

    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    def tokenize(row: dict) -> dict:
        text = tokenizer.apply_chat_template(row["messages"], tokenize=False)
        return tokenizer(text, truncation=True, max_length=1024)

    ds = Dataset.from_list(rows).map(tokenize, remove_columns=["messages"])

    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        max_steps=max_steps,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=lr,
        logging_steps=5,
        save_strategy="no",
        report_to=[],
        use_cpu=not torch.cuda.is_available(),
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )
    trainer.train()

    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    log.info("saved fine-tuned adapter + tokenizer to %s", output_dir)
    return output_dir
