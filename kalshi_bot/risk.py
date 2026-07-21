"""Risk manager: position sizing via fractional Kelly plus hard limits."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import RiskLimits
from .models import Position, TradeSignal


@dataclass
class RiskDecision:
    approved: bool
    contracts: int
    reason: str


@dataclass
class RiskManager:
    limits: RiskLimits
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl_today_cents: int = 0

    def kelly_contracts(self, signal: TradeSignal, bankroll_cents: int) -> int:
        """Fractional Kelly sizing for a binary contract bought at price p.

        Full Kelly stake fraction = (q - p) / (1 - p), where q is estimated
        win probability and p the price as a probability. We scale it down
        by limits.kelly_fraction to control variance.
        """
        p = signal.price_cents / 100
        q = signal.est_win_prob
        if p <= 0 or p >= 1 or q <= p:
            return 0
        stake_fraction = (q - p) / (1 - p) * self.limits.kelly_fraction
        stake_cents = bankroll_cents * stake_fraction
        return max(0, int(stake_cents // signal.price_cents))

    def open_exposure_cents(self) -> int:
        return int(sum(pos.cost_basis_cents for pos in self.positions.values()))

    def check(self, signal: TradeSignal, bankroll_cents: int) -> RiskDecision:
        if self.realized_pnl_today_cents <= -self.limits.max_daily_loss_cents:
            return RiskDecision(False, 0, "daily loss limit reached; trading halted")
        if signal.edge < self.limits.min_edge and signal.strategy != "arbitrage":
            return RiskDecision(False, 0, f"edge {signal.edge:.3f} below minimum {self.limits.min_edge}")

        contracts = self.kelly_contracts(signal, bankroll_cents)
        if contracts <= 0:
            return RiskDecision(False, 0, "Kelly sizing yields zero contracts")

        max_by_cost = self.limits.max_order_cost_cents // signal.price_cents
        contracts = min(contracts, max_by_cost)

        existing = self.positions.get(signal.ticker)
        held = existing.contracts if existing else 0
        contracts = min(contracts, self.limits.max_position_contracts - held)
        if contracts <= 0:
            return RiskDecision(False, 0, "per-market position limit reached")

        order_cost = contracts * signal.price_cents
        if self.open_exposure_cents() + order_cost > self.limits.max_open_exposure_cents:
            room = self.limits.max_open_exposure_cents - self.open_exposure_cents()
            contracts = max(0, room // signal.price_cents)
            if contracts <= 0:
                return RiskDecision(False, 0, "total exposure limit reached")

        return RiskDecision(True, contracts, f"approved {contracts} contracts")

    def record_fill(self, ticker: str, side: str, contracts: int, price_cents: int) -> None:
        pos = self.positions.get(ticker)
        if pos is None or pos.side != side:
            self.positions[ticker] = Position(ticker, side, contracts, float(price_cents))
            return
        total = pos.contracts + contracts
        pos.avg_cost_cents = (pos.cost_basis_cents + contracts * price_cents) / total
        pos.contracts = total

    def record_settlement(self, ticker: str, won: bool) -> int:
        """Settle a position and return realized PnL in cents."""
        pos = self.positions.pop(ticker, None)
        if pos is None:
            return 0
        payout = pos.contracts * 100 if won else 0
        pnl = int(payout - pos.cost_basis_cents)
        self.realized_pnl_today_cents += pnl
        return pnl
