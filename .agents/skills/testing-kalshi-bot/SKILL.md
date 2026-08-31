---
name: testing-kalshi-bot
description: Test the kalshi_bot trading bot end-to-end against the live Kalshi API in paper mode. Use when verifying strategy, risk, API-client, or dashboard changes.
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
- Web dashboard: `python -m kalshi_bot dashboard` → http://127.0.0.1:8000 (run in background; UI auto-refreshes every 10s)

## Dashboard UI testing (record this)
- Good flow: load page → verify PAPER/STOPPED badges + $1000.00 bankroll → check live signals table has `KX...` tickers → click "Start bot" (top-right) → within one poll cycle expect RUNNING badge, trades in log, positions populated, bankroll + open exposure summing exactly to the starting bankroll → click "Stop bot" → badge back to STOPPED with state retained.
- The Start/Stop button drives a background thread running `engine.run_once()` every `POLL_SECONDS` (default 30s); first trades usually appear immediately after clicking Start.
- API endpoints for shell-side verification: `/api/status`, `/api/signals`, `/api/positions`, `/api/trades`.

## Gotchas / lessons
- The live API may return dollar-string fields (`yes_ask_dollars`, `volume_fp`, `close_time`) instead of integer-cent fields (`yes_ask`, `volume`, `close_ts`). If scans return zero signals, check `snapshot_from_api` parsing against a raw market JSON first — silent zeros look like "no opportunities".
- The default `/markets` page is dominated by zero-volume multivariate markets; scan specific liquid series via `SCAN_SERIES` (e.g. `KXBTCD,KXETHD,KXHIGHNY,KXMLBGAME`). Series tickers may change over time — verify a series has volume before relying on it.
- Good end-to-end assertions: (1) scan exits 0 with ≥1 signal at 1–99c; (2) after `once`, `paper_cash_cents == start − Σ(contracts × price)` exactly; (3) with tight `MAX_ORDER_COST_CENTS`/`MAX_OPEN_EXPOSURE_CENTS` env vars, excess signals log `REJECTED ...` reasons.
- Signal availability depends on market hours/liquidity; if zero signals at test time, verify parsing with a raw-fields probe before concluding the strategies are broken.
- Avoid committing `__pycache__` (use `git add` on specific paths, not `git add -A` after running tests).
- Shell-only CLI testing: no recording needed; collect command output as evidence.

## Dashboard / UI testing
- Start with `rm -f trade_history.json && python -m kalshi_bot dashboard` (background) and open http://127.0.0.1:8000 in Chrome; record the browser session.
- Good UI assertions: Best-trades panel sorted by descending score with verdict badges and non-empty rationales; Start bot → trades appear and bankroll + open exposure = starting bankroll cent-exact; Stop bot retains trade count/positions.
- Persistence check: after trades, `trade_history.json` should contain one record per trade (`status: open`) matching the UI trade log, and `GET /api/performance` counts should match (`win_rate` null until settlements).
- The AI ranking uses a quant fallback when `LLM_API_KEY` is unset (header says "ranked by quant model"). The real LLM path might only be testable with a key; unit tests mock it (`tests/test_advisor.py`). Delete stale `trade_history.json` before testing or counts will be off.
>>>>>>> Stashed changes

## Devin Secrets Needed
- None for paper mode. For live mode: `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH` (RSA private key file).
