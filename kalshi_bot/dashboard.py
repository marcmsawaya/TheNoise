"""Web dashboard for the trading bot: live signals, positions, trades, controls."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .advisor import Advisor
from .config import BotConfig
from .engine import TradingEngine

log = logging.getLogger("kalshi_bot")

INDEX_HTML = (Path(__file__).parent / "static" / "index.html").read_text()


class BotRunner:
    """Runs the trading engine loop in a background thread."""

    def __init__(self, engine: TradingEngine):
        self.engine = engine
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_scan_ts: float | None = None
        self.last_signals: list[dict] = []

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def scan(self) -> list[dict]:
        signals = self.engine.scan()
        self.last_scan_ts = time.time()
        self.last_signals = [
            {
                "ticker": s.ticker,
                "side": s.side,
                "price_cents": s.price_cents,
                "edge": s.edge,
                "strategy": s.strategy,
                "reason": s.reason,
            }
            for s in signals
        ]
        return self.last_signals

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.engine.run_once()
                self.last_scan_ts = time.time()
            except Exception:
                log.exception("dashboard bot cycle failed")
            self._stop.wait(self.engine.config.poll_seconds)


def create_app(config: BotConfig | None = None) -> FastAPI:
    config = config or BotConfig()
    engine = TradingEngine(config)
    runner = BotRunner(engine)
    advisor = Advisor()
    app = FastAPI(title="Kalshi Bot Dashboard")
    app.state.engine = engine
    app.state.runner = runner
    app.state.advisor = advisor

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/api/status")
    def status() -> dict:
        risk = engine.risk
        return {
            "mode": "paper" if config.paper_trading else "live",
            "running": runner.running,
            "bankroll_cents": engine.bankroll_cents(),
            "open_exposure_cents": risk.open_exposure_cents(),
            "realized_pnl_today_cents": risk.realized_pnl_today_cents,
            "trades_executed": len(engine.trade_log),
            "last_scan_ts": runner.last_scan_ts,
            "poll_seconds": config.poll_seconds,
        }

    @app.get("/api/signals")
    def signals() -> dict:
        return {"signals": runner.scan()}

    @app.get("/api/positions")
    def positions() -> dict:
        return {
            "positions": [
                {
                    "ticker": p.ticker,
                    "side": p.side,
                    "contracts": p.contracts,
                    "avg_cost_cents": round(p.avg_cost_cents, 2),
                    "cost_basis_cents": round(p.cost_basis_cents, 2),
                }
                for p in engine.risk.positions.values()
            ]
        }

    @app.get("/api/trades")
    def trades() -> dict:
        return {"trades": engine.trade_log}

    @app.get("/api/best_trades")
    def best_trades() -> dict:
        ranked = advisor.rank(engine.scan())
        runner.last_scan_ts = time.time()
        return {
            "ai_enabled": advisor.config.enabled,
            "best_trades": [r.to_dict() for r in ranked],
        }

    @app.get("/api/performance")
    def performance() -> dict:
        return engine.tracker.stats()

    @app.post("/api/bot/start")
    def start_bot() -> dict:
        runner.start()
        return {"running": runner.running}

    @app.post("/api/bot/stop")
    def stop_bot() -> dict:
        runner.stop()
        return {"running": runner.running}

    return app


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
