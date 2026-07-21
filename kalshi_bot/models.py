"""Core data models shared across strategies, risk, and execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketSnapshot:
    ticker: str
    title: str
    yes_bid: int  # cents
    yes_ask: int
    no_bid: int
    no_ask: int
    volume: int
    open_interest: int
    close_ts: int  # unix seconds until market close

    @property
    def mid_yes(self) -> float:
        return (self.yes_bid + self.yes_ask) / 2

    @property
    def spread(self) -> int:
        return self.yes_ask - self.yes_bid


@dataclass(frozen=True)
class TradeSignal:
    ticker: str
    side: str  # "yes" | "no"
    action: str  # "buy" | "sell"
    price_cents: int  # limit price
    edge: float  # estimated probability edge in our favor (0..1)
    est_win_prob: float  # our fair probability estimate for chosen side
    reason: str
    strategy: str


@dataclass
class Position:
    ticker: str
    side: str
    contracts: int
    avg_cost_cents: float

    @property
    def cost_basis_cents(self) -> float:
        return self.contracts * self.avg_cost_cents
