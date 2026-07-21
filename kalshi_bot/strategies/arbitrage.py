"""Riskless-style arbitrage: buy YES and NO when combined ask < 100c.

If yes_ask + no_ask < 100 (minus fees), buying both sides locks in a profit
regardless of outcome. This is the lowest-risk edge available on Kalshi and
appears briefly during volatile order flow.
"""

from __future__ import annotations

from ..models import MarketSnapshot, TradeSignal
from .base import Strategy

# Kalshi fee approximation: fees are maximized at p=0.5; use a conservative
# flat buffer in cents per contract pair.
FEE_BUFFER_CENTS = 3


class ArbitrageStrategy(Strategy):
    name = "arbitrage"

    def evaluate(self, market: MarketSnapshot) -> TradeSignal | None:
        if market.yes_ask <= 0 or market.no_ask <= 0:
            return None
        combined = market.yes_ask + market.no_ask
        profit = 100 - combined - FEE_BUFFER_CENTS
        if profit <= 0:
            return None
        # Signal the cheaper leg; the engine pairs it with the other leg.
        side = "yes" if market.yes_ask <= market.no_ask else "no"
        price = market.yes_ask if side == "yes" else market.no_ask
        return TradeSignal(
            ticker=market.ticker,
            side=side,
            action="buy",
            price_cents=price,
            edge=profit / 100,
            est_win_prob=1.0,
            reason=f"YES ask {market.yes_ask}c + NO ask {market.no_ask}c = {combined}c < 100c "
            f"(locked profit ~{profit}c/pair after fee buffer)",
            strategy=self.name,
        )
