"""LLM advisor: ranks candidate trades and explains why they're the best.

Uses any OpenAI-compatible chat API when LLM_API_KEY is set; otherwise falls
back to a deterministic quantitative ranking so the app works without a key.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

import requests

from .models import TradeSignal

log = logging.getLogger("kalshi_bot")

SYSTEM_PROMPT = """You are a disciplined prediction-market trading analyst.
You are given candidate trades on Kalshi binary markets, each with a price
(cents, = implied probability) and an estimated edge. Rank the best trades.

Respond ONLY with a JSON array. Each element:
{"ticker": str, "score": float 0-100, "verdict": "strong_buy"|"buy"|"skip",
 "rationale": str (<= 30 words, concrete, no hedging)}

Favor: locked arbitrage, high liquidity, near expiry, tight spreads, larger edge.
Penalize: longshots, stale pricing, correlated concentration in one event."""


@dataclass
class AdvisorConfig:
    api_key: str = field(default_factory=lambda: os.environ.get("LLM_API_KEY", ""))
    api_base: str = field(
        default_factory=lambda: os.environ.get("LLM_API_BASE", "https://api.openai.com/v1")
    )
    model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "gpt-4o-mini"))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


@dataclass
class RankedTrade:
    signal: TradeSignal
    score: float
    verdict: str
    rationale: str
    source: str  # "llm" | "quant"

    def to_dict(self) -> dict:
        return {
            "ticker": self.signal.ticker,
            "side": self.signal.side,
            "price_cents": self.signal.price_cents,
            "edge": self.signal.edge,
            "strategy": self.signal.strategy,
            "score": round(self.score, 1),
            "verdict": self.verdict,
            "rationale": self.rationale,
            "source": self.source,
        }


class Advisor:
    def __init__(self, config: AdvisorConfig | None = None):
        self.config = config or AdvisorConfig()

    def rank(self, signals: list[TradeSignal]) -> list[RankedTrade]:
        if not signals:
            return []
        if self.config.enabled:
            try:
                return self._rank_llm(signals)
            except Exception:
                log.exception("LLM ranking failed; falling back to quant ranking")
        return self._rank_quant(signals)

    # ---- deterministic fallback ----

    def _rank_quant(self, signals: list[TradeSignal]) -> list[RankedTrade]:
        ranked = []
        for s in signals:
            score = min(100.0, s.edge * 1000)
            if s.strategy == "arbitrage":
                score = 100.0
                verdict = "strong_buy"
                rationale = "Locked arbitrage: combined YES+NO under $1 guarantees profit."
            else:
                verdict = "buy" if score >= 25 else "skip"
                rationale = (
                    f"{s.edge:.0%} estimated edge buying {s.side.upper()} at "
                    f"{s.price_cents}c on a liquid near-expiry favorite."
                )
            ranked.append(RankedTrade(s, score, verdict, rationale, "quant"))
        ranked.sort(key=lambda r: -r.score)
        return ranked

    # ---- LLM ranking ----

    def _rank_llm(self, signals: list[TradeSignal]) -> list[RankedTrade]:
        payload = [
            {
                "ticker": s.ticker,
                "side": s.side,
                "price_cents": s.price_cents,
                "edge": round(s.edge, 4),
                "strategy": s.strategy,
                "reason": s.reason,
            }
            for s in signals
        ]
        resp = requests.post(
            f"{self.config.api_base}/chat/completions",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            json={
                "model": self.config.model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        rankings = {r["ticker"]: r for r in json.loads(content)}
        by_ticker = {s.ticker: s for s in signals}
        ranked = [
            RankedTrade(
                by_ticker[t],
                float(r.get("score", 0)),
                str(r.get("verdict", "skip")),
                str(r.get("rationale", "")),
                "llm",
            )
            for t, r in rankings.items()
            if t in by_ticker
        ]
        ranked.sort(key=lambda r: -r.score)
        return ranked
