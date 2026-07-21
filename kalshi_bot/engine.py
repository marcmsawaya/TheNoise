"""Trading engine: scans markets, gathers signals, and executes with risk checks.

Runs in paper-trading mode by default; live mode requires explicit
PAPER_TRADING=false plus API credentials.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from .client import KalshiClient
from .config import BotConfig
from .models import MarketSnapshot, TradeSignal
from .risk import RiskManager
from .strategies import ALL_STRATEGIES, Strategy

log = logging.getLogger("kalshi_bot")


def _price_cents(m: dict, field: str) -> int:
    """Read a price field, supporting both cent ints and `*_dollars` strings."""
    if m.get(field) is not None:
        return int(m[field])
    dollars = m.get(f"{field}_dollars")
    return int(round(float(dollars) * 100)) if dollars is not None else 0


def _quantity(m: dict, field: str) -> int:
    """Read a quantity field, supporting both ints and `*_fp` decimal strings."""
    if m.get(field) is not None:
        return int(m[field])
    fp = m.get(f"{field}_fp")
    return int(float(fp)) if fp is not None else 0


def _close_ts(m: dict) -> int:
    if m.get("close_ts"):
        return int(m["close_ts"])
    close_time = m.get("close_time")
    if close_time:
        dt = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
        return int(dt.timestamp())
    return 0


def snapshot_from_api(m: dict) -> MarketSnapshot:
    return MarketSnapshot(
        ticker=m.get("ticker", ""),
        title=m.get("title", ""),
        yes_bid=_price_cents(m, "yes_bid"),
        yes_ask=_price_cents(m, "yes_ask"),
        no_bid=_price_cents(m, "no_bid"),
        no_ask=_price_cents(m, "no_ask"),
        volume=_quantity(m, "volume"),
        open_interest=_quantity(m, "open_interest"),
        close_ts=_close_ts(m),
    )


class TradingEngine:
    def __init__(self, config: BotConfig, client: KalshiClient | None = None):
        self.config = config
        self.client = client or KalshiClient(config)
        self.risk = RiskManager(config.risk)
        self.strategies: list[Strategy] = [cls() for cls in ALL_STRATEGIES]
        self.paper_cash_cents = config.paper_bankroll_cents
        self.trade_log: list[dict] = []

    # ---- bankroll ----

    def bankroll_cents(self) -> int:
        if self.config.paper_trading:
            return self.paper_cash_cents
        return self.client.get_balance()

    # ---- scanning ----

    def fetch_markets(self) -> list[dict]:
        markets: list[dict] = []
        for series in self.config.scan_series or [""]:
            params = {"series_ticker": series} if series else {}
            try:
                markets.extend(self.client.get_markets(**params))
            except Exception:
                log.exception("failed to fetch series %s", series or "<all>")
        return markets

    def scan(self) -> list[TradeSignal]:
        signals: list[TradeSignal] = []
        for raw in self.fetch_markets():
            snap = snapshot_from_api(raw)
            for strategy in self.strategies:
                signal = strategy.evaluate(snap)
                if signal:
                    signals.append(signal)
        # Best edges first; arbitrage always ranks above statistical edges.
        signals.sort(key=lambda s: (s.strategy != "arbitrage", -s.edge))
        return signals

    # ---- execution ----

    def execute(self, signal: TradeSignal) -> bool:
        decision = self.risk.check(signal, self.bankroll_cents())
        if not decision.approved:
            log.info("REJECTED %s %s: %s", signal.ticker, signal.side, decision.reason)
            return False

        cost = decision.contracts * signal.price_cents
        if self.config.paper_trading:
            self.paper_cash_cents -= cost
            log.info(
                "PAPER BUY %s x%d %s @ %dc (%s: %s)",
                signal.ticker, decision.contracts, signal.side.upper(),
                signal.price_cents, signal.strategy, signal.reason,
            )
        else:
            self.client.create_order(
                ticker=signal.ticker,
                side=signal.side,
                action=signal.action,
                count=decision.contracts,
                price_cents=signal.price_cents,
            )
            log.info(
                "LIVE BUY %s x%d %s @ %dc (%s)",
                signal.ticker, decision.contracts, signal.side.upper(),
                signal.price_cents, signal.strategy,
            )

        self.risk.record_fill(signal.ticker, signal.side, decision.contracts, signal.price_cents)
        self.trade_log.append(
            {
                "ts": time.time(),
                "ticker": signal.ticker,
                "side": signal.side,
                "contracts": decision.contracts,
                "price_cents": signal.price_cents,
                "strategy": signal.strategy,
                "edge": signal.edge,
                "paper": self.config.paper_trading,
            }
        )
        return True

    def run_once(self) -> int:
        signals = self.scan()
        log.info("scan complete: %d signals", len(signals))
        executed = 0
        for signal in signals[: self.config.risk.max_markets]:
            if self.execute(signal):
                executed += 1
        return executed

    def run_forever(self) -> None:
        mode = "PAPER" if self.config.paper_trading else "LIVE"
        log.info("starting engine in %s mode, bankroll %dc", mode, self.bankroll_cents())
        while True:
            try:
                self.run_once()
            except Exception:
                log.exception("scan cycle failed; retrying after backoff")
            time.sleep(self.config.poll_seconds)
