"""Bot configuration loaded from environment variables / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


@dataclass
class RiskLimits:
    """Hard limits enforced by the RiskManager on every order."""

    max_order_cost_cents: int = field(default_factory=lambda: _env_int("MAX_ORDER_COST_CENTS", 2_000))
    max_position_contracts: int = field(default_factory=lambda: _env_int("MAX_POSITION_CONTRACTS", 100))
    max_open_exposure_cents: int = field(default_factory=lambda: _env_int("MAX_OPEN_EXPOSURE_CENTS", 10_000))
    max_daily_loss_cents: int = field(default_factory=lambda: _env_int("MAX_DAILY_LOSS_CENTS", 5_000))
    kelly_fraction: float = field(default_factory=lambda: _env_float("KELLY_FRACTION", 0.25))
    min_edge: float = field(default_factory=lambda: _env_float("MIN_EDGE", 0.02))
    max_markets: int = field(default_factory=lambda: _env_int("MAX_MARKETS", 5))


@dataclass
class BotConfig:
    api_base: str = field(
        default_factory=lambda: os.environ.get(
            "KALSHI_API_BASE", "https://api.elections.kalshi.com/trade-api/v2"
        )
    )
    api_key_id: str = field(default_factory=lambda: os.environ.get("KALSHI_API_KEY_ID", ""))
    private_key_path: str = field(
        default_factory=lambda: os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    )
    paper_trading: bool = field(
        default_factory=lambda: os.environ.get("PAPER_TRADING", "true").lower() != "false"
    )
    paper_bankroll_cents: int = field(
        default_factory=lambda: _env_int("PAPER_BANKROLL_CENTS", 100_000)
    )
    poll_seconds: float = field(default_factory=lambda: _env_float("POLL_SECONDS", 30.0))
    risk: RiskLimits = field(default_factory=RiskLimits)

    @property
    def live_enabled(self) -> bool:
        return not self.paper_trading and bool(self.api_key_id and self.private_key_path)
