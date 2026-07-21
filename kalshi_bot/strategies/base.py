from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import MarketSnapshot, TradeSignal


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def evaluate(self, market: MarketSnapshot) -> TradeSignal | None:
        """Return a signal if this market offers positive expected value, else None."""
