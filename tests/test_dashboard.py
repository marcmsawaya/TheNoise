import time
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from kalshi_bot.config import BotConfig
from kalshi_bot.dashboard import create_app

FAV_MARKET = {
    "ticker": "FAV-1",
    "title": "Favorite market",
    "yes_bid": 89,
    "yes_ask": 91,
    "no_bid": 9,
    "no_ask": 11,
    "volume": 2000,
    "open_interest": 800,
    "close_ts": int(time.time()) + 3600,
}


def make_client():
    config = BotConfig()
    config.paper_trading = True
    config.scan_series = ["TEST"]
    app = create_app(config)
    mock_kalshi = MagicMock()
    mock_kalshi.get_markets.return_value = [FAV_MARKET]
    app.state.engine.client = mock_kalshi
    return TestClient(app), config


def test_index_serves_dashboard():
    client, _ = make_client()
    page = client.get("/")
    assert page.status_code == 200
    assert "Kalshi Bot" in page.text


def test_status_positions_trades():
    client, config = make_client()
    status = client.get("/api/status").json()
    assert status["mode"] == "paper"
    assert status["running"] is False
    assert status["bankroll_cents"] == config.paper_bankroll_cents
    assert client.get("/api/positions").json() == {"positions": []}
    assert client.get("/api/trades").json() == {"trades": []}


def test_signals_endpoint_scans_markets():
    client, _ = make_client()
    signals = client.get("/api/signals").json()["signals"]
    assert len(signals) == 1
    assert signals[0]["ticker"] == "FAV-1"
    assert signals[0]["side"] == "yes"
    assert signals[0]["price_cents"] == 91


def test_best_trades_endpoint():
    client, _ = make_client()
    d = client.get("/api/best_trades").json()
    assert d["ai_enabled"] is False
    assert len(d["best_trades"]) == 1
    top = d["best_trades"][0]
    assert top["ticker"] == "FAV-1"
    assert top["verdict"] in ("strong_buy", "buy", "skip")
    assert top["rationale"]
    assert top["source"] == "quant"


def test_performance_endpoint():
    client, _ = make_client()
    stats = client.get("/api/performance").json()
    assert "win_rate" in stats
    assert "total_trades" in stats


def test_start_stop_bot():
    client, _ = make_client()
    assert client.post("/api/bot/start").json()["running"] is True
    client.post("/api/bot/stop")
    time.sleep(0.05)
    assert client.get("/api/status").json()["trades_executed"] >= 0
