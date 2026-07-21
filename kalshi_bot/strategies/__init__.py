from .arbitrage import ArbitrageStrategy
from .base import Strategy
from .favorite_value import FavoriteValueStrategy

ALL_STRATEGIES: list[type[Strategy]] = [ArbitrageStrategy, FavoriteValueStrategy]

__all__ = ["Strategy", "ArbitrageStrategy", "FavoriteValueStrategy", "ALL_STRATEGIES"]
