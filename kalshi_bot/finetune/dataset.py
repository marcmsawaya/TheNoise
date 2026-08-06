"""Build a supervised fine-tuning dataset from settled Kalshi markets.

Each settled binary market becomes a chat-format training example: the model
sees the market's pre-settlement stats and must output the trade analysis JSON
used by the Advisor (score/verdict/rationale), labeled with what would actually
have been profitable given the settlement result.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger("kalshi_bot")

API_BASE = "https://api.elections.kalshi.com/trade-api/v2"

SYSTEM_PROMPT = (
    "You are a disciplined prediction-market trading analyst. Given a Kalshi "
    "binary market's stats, respond ONLY with JSON: "
    '{"score": float 0-100, "verdict": "strong_buy"|"buy"|"skip", '
    '"side": "yes"|"no", "rationale": str}'
)


@dataclass
class SettledMarket:
    ticker: str
    title: str
    result: str  # "yes" | "no"
    last_price_cents: int  # last traded YES price before settlement
    volume: int
    open_interest: int
    close_time: str


def _cents(m: dict, field: str) -> int:
    if m.get(field) is not None:
        return int(m[field])
    dollars = m.get(f"{field}_dollars")
    return int(round(float(dollars) * 100)) if dollars is not None else 0


def _qty(m: dict, field: str) -> int:
    if m.get(field) is not None:
        return int(m[field])
    fp = m.get(f"{field}_fp")
    return int(float(fp)) if fp is not None else 0


def fetch_settled_markets(series: list[str], per_series: int = 200) -> list[SettledMarket]:
    out: list[SettledMarket] = []
    for s in series:
        cursor = ""
        fetched = 0
        while fetched < per_series:
            params: dict = {
                "status": "settled",
                "series_ticker": s,
                "limit": min(200, per_series - fetched),
            }
            if cursor:
                params["cursor"] = cursor
            try:
                resp = requests.get(f"{API_BASE}/markets", params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                log.exception("failed to fetch settled markets for %s", s)
                break
            for m in data.get("markets", []):
                if m.get("result") not in ("yes", "no"):
                    continue
                out.append(
                    SettledMarket(
                        ticker=m.get("ticker", ""),
                        title=m.get("title", ""),
                        result=m["result"],
                        last_price_cents=_cents(m, "last_price"),
                        volume=_qty(m, "volume"),
                        open_interest=_qty(m, "open_interest"),
                        close_time=m.get("close_time", ""),
                    )
                )
            fetched += len(data.get("markets", []))
            cursor = data.get("cursor", "")
            if not cursor or not data.get("markets"):
                break
    return out


def market_to_example(m: SettledMarket) -> dict | None:
    """Turn one settled market into a chat training example, or None if unusable."""
    price = m.last_price_cents
    if price <= 0 or price >= 100 or m.volume <= 0:
        return None

    won_yes = m.result == "yes"
    # Profit per contract in cents if you bought each side at the last price.
    yes_profit = (100 - price) if won_yes else -price
    no_price = 100 - price
    no_profit = (100 - no_price) if not won_yes else -no_price
    side = "yes" if yes_profit >= no_profit else "no"
    side_price = price if side == "yes" else no_price
    side_profit = max(yes_profit, no_profit)

    # Score: how good buying the better side at that price turned out to be,
    # scaled by return on cost. Winners near even money score highest.
    roi = side_profit / side_price
    score = round(min(100.0, max(0.0, roi * 100)), 1)
    if score >= 60:
        verdict = "strong_buy"
    elif score >= 15:
        verdict = "buy"
    else:
        verdict = "skip"

    rationale = (
        f"{side.upper()} settled as the winner; at {side_price}c the market "
        f"{'underpriced' if verdict != 'skip' else 'fairly priced'} it "
        f"(return {roi:.0%} on cost, volume {m.volume})."
    )

    user = json.dumps(
        {
            "ticker": m.ticker,
            "title": m.title,
            "yes_price_cents": price,
            "no_price_cents": no_price,
            "volume": m.volume,
            "open_interest": m.open_interest,
            "close_time": m.close_time,
        }
    )
    assistant = json.dumps(
        {"score": score, "verdict": verdict, "side": side, "rationale": rationale}
    )
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def build_dataset(series: list[str], out_path: str, per_series: int = 200) -> int:
    markets = fetch_settled_markets(series, per_series)
    examples = [e for m in markets if (e := market_to_example(m)) is not None]
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for e in examples:
            f.write(json.dumps(e) + "\n")
    log.info(
        "wrote %d examples from %d settled markets to %s (%s)",
        len(examples), len(markets), out_path,
        datetime.now(timezone.utc).isoformat(),
    )
    return len(examples)
