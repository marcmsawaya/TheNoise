---
name: testing-kalshi-bot
description: Test the kalshi_bot trading bot end-to-end against the live Kalshi API in paper mode. Use when verifying strategy, risk, or API-client changes.
---

# Testing kalshi_bot

## Setup
- `pip install --upgrade pip setuptools && pip install -e ".[dev]"` from repo root (old pip can't editable-install PEP 621 projects).
- No credentials needed for market data or paper trading; the public Kalshi API (`https://api.elections.kalshi.com/trade-api/v2`) works unauthenticated.
- Live trading requires `KALSHI_API_KEY_ID` + `KALSHI_PRIVATE_KEY_PATH` (RSA key) and `PAPER_TRADING=false`. Never live-test without the user's explicit approval and a funded account.

## Commands
- Unit tests: `python -m pytest -q` | Lint: `python -m ruff check .`
- Live signal scan: `python -m kalshi_bot scan`
- One paper cycle: `python -m kalshi_bot once` (logs `PAPER BUY ...` lines)

## Gotchas / lessons
- The live API may return dollar-string fields (`yes_ask_dollars`, `volume_fp`, `close_time`) instead of integer-cent fields (`yes_ask`, `volume`, `close_ts`). If scans return zero signals, check `snapshot_from_api` parsing against a raw market JSON first — silent zeros look like "no opportunities".
- The default `/markets` page is dominated by zero-volume multivariate markets; scan specific liquid series via `SCAN_SERIES` (e.g. `KXBTCD,KXETHD,KXHIGHNY,KXMLBGAME`). Series tickers may change over time — verify a series has volume before relying on it.
- Good end-to-end assertions: (1) scan exits 0 with ≥1 signal at 1–99c; (2) after `once`, `paper_cash_cents == start − Σ(contracts × price)` exactly; (3) with tight `MAX_ORDER_COST_CENTS`/`MAX_OPEN_EXPOSURE_CENTS` env vars, excess signals log `REJECTED ...` reasons.
- Signal availability depends on market hours/liquidity; if zero signals at test time, verify parsing with a raw-fields probe before concluding the strategies are broken.
- Shell-only app: no recording needed; collect command output as evidence.

## Devin Secrets Needed
- None for paper mode. For live mode: `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH` (RSA private key file).
