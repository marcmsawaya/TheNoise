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
```

## Going live (real money — be careful)

1. Create an API key at kalshi.com → Account → API Keys and download the RSA private key.
2. Set in `.env`: `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`, and `PAPER_TRADING=false`.
3. Start small: lower `MAX_ORDER_COST_CENTS` and `MAX_OPEN_EXPOSURE_CENTS` first.

## Tests

```bash
pytest
ruff check .
```
