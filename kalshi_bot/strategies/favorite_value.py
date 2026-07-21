"""Favorite-longshot value strategy.

Prediction markets systematically exhibit favorite-longshot bias: heavy
favorites (price 85-97c) are underpriced relative to their true win
probability, while longshots are overpriced. Buying liquid, near-expiry
favorites at a small premium to market price captures that bias with a
high hit rate and small per-trade variance.

Filters keep risk minimal:
- only liquid markets (volume / open interest floors)
- only tight spreads (wide spreads signal stale or uncertain pricing)
- only near-dated markets (less time for news to flip the outcome)
- never chases longshots
"""

from __future__ import annotations

import time

from ..models import MarketSnapshot, TradeSignal
from .base import Strategy

FAVORITE_MIN_CENTS = 85
FAVORITE_MAX_CENTS = 97
MAX_SPREAD_CENTS = 4
MIN_VOLUME = 500
MIN_OPEN_INTEREST = 200
MAX_HOURS_TO_CLOSE = 48
# Empirical favorite-longshot bias adjustment: favorites' true probability
# tends to exceed price by a few points.
BIAS_BOOST = 0.03


class FavoriteValueStrategy(Strategy):
    name = "favorite_value"

    def evaluate(self, market: MarketSnapshot) -> TradeSignal | None:
        if market.volume < MIN_VOLUME or market.open_interest < MIN_OPEN_INTEREST:
            return None
        if market.spread > MAX_SPREAD_CENTS or market.spread < 0:
            return None
        hours_to_close = (market.close_ts - time.time()) / 3600
        if not 0 < hours_to_close <= MAX_HOURS_TO_CLOSE:
            return None

        for side, ask in (("yes", market.yes_ask), ("no", market.no_ask)):
            if FAVORITE_MIN_CENTS <= ask <= FAVORITE_MAX_CENTS:
                implied = ask / 100
                est_prob = min(0.99, implied + BIAS_BOOST)
                edge = est_prob - implied
                if edge <= 0:
                    continue
                return TradeSignal(
                    ticker=market.ticker,
                    side=side,
                    action="buy",
                    price_cents=ask,
                    edge=edge,
                    est_win_prob=est_prob,
                    reason=f"Liquid near-dated favorite: {side.upper()} ask {ask}c, "
                    f"spread {market.spread}c, closes in {hours_to_close:.1f}h",
                    strategy=self.name,
                )
        return None
