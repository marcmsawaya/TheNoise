# TheNoise — Kalshi Trading Bot

A risk-managed trading bot for [Kalshi](https://kalshi.com) prediction markets.

> **Honest disclaimer:** no bot can guarantee winning trades. This bot targets
> the two most defensible edges on Kalshi — true arbitrage (YES + NO priced
> below $1) and the well-documented favorite-longshot bias — and wraps every
> order in strict risk controls. Trading involves risk; it defaults to
> **paper trading** and only goes live if you explicitly enable it.

## Strategies

1. **Arbitrage** (`kalshi_bot/strategies/arbitrage.py`): buys both YES and NO
   when combined asks are below 100¢ (after a fee buffer) — a locked-in profit
   regardless of outcome. Rare, but essentially riskless when it appears.
2. **Favorite value** (`kalshi_bot/strategies/favorite_value.py`): buys liquid,
   near-expiry favorites priced 85–97¢ with tight spreads, capturing the
   favorite-longshot bias (favorites are systematically slightly underpriced).
   High hit rate, small per-trade variance.

## Risk management

Every order passes through `RiskManager` (`kalshi_bot/risk.py`):

- **Fractional Kelly sizing** (default 25% Kelly) — bets scale with edge and shrink variance
- **Per-order cost cap**, **per-market position cap**, **total exposure cap**
- **Daily loss circuit breaker** — trading halts for the day after the loss limit
- **Minimum edge filter** — no trade unless estimated edge ≥ 2%

## Quick start

```bash
pip install -e ".[dev]"
cp .env.example .env

# List current signals (public data, no credentials needed)
python -m kalshi_bot scan

# Run one paper-trading cycle
python -m kalshi_bot once

# Continuous paper-trading loop
python -m kalshi_bot run

# Web dashboard (open http://127.0.0.1:8000)
python -m kalshi_bot dashboard
```

## Dashboard

`python -m kalshi_bot dashboard` starts a local web UI at http://127.0.0.1:8000 with:

- live signals rescanned from the Kalshi API
- bankroll, open exposure, realized P&L, and trade count
- open positions and full trade log
- a Start/Stop button that runs the trading loop in the background
- a **Best trades** panel ranking every signal with a score, verdict, and rationale
- a win-rate card backed by persistent trade history (`trade_history.json`)

## AI advisor

The Best-trades panel is ranked by a built-in quant model out of the box. Set
`LLM_API_KEY` (plus optional `LLM_API_BASE` / `LLM_MODEL` for any
OpenAI-compatible provider) in `.env` and the ranking is done by an LLM that
scores each candidate trade 0–100 with a short rationale. If the LLM call
fails, it falls back to the quant ranking automatically.

## Build your own trading LLM (fine-tuning)

Train a custom model on real settled Kalshi markets and plug it into the bot:

```bash
pip install -e ".[finetune]"                      # torch, transformers, peft, datasets
python -m kalshi_bot.finetune dataset              # settled markets -> finetune_data/train.jsonl
python -m kalshi_bot.finetune train                # LoRA fine-tune (default Qwen2.5-0.5B-Instruct)
python -m kalshi_bot.finetune serve                # OpenAI-compatible API on :8001
```

Then point the bot at your model in `.env`:

```dotenv
LLM_API_KEY=local
LLM_API_BASE=http://127.0.0.1:8001/v1
LLM_MODEL=kalshi-llm
```

Each settled market becomes a training example: market stats in, the
profitable side/score/verdict/rationale out. The default base model runs on
CPU; pass `--base-model` for a larger model on a GPU. More settled history =
better model — rerun `dataset` periodically and retrain.

## Performance tracking

Every executed trade is persisted to `trade_history.json` (configurable via
`TRADE_HISTORY_PATH`), so win rate and realized P&L survive restarts. Settle a
position programmatically with `TradingEngine.settle(ticker, won=True)`.

## Going live (real money — be careful)

1. Create an API key at kalshi.com → Account → API Keys and download the RSA private key.
2. Set in `.env`: `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`, and `PAPER_TRADING=false`.
3. Start small: lower `MAX_ORDER_COST_CENTS` and `MAX_OPEN_EXPOSURE_CENTS` first.

## Tests

```bash
pytest
ruff check .
```
