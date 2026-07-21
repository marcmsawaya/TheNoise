import time
from unittest.mock import MagicMock

from kalshi_bot.config import BotConfig
from kalshi_bot.engine import TradingEngine, snapshot_from_api


def make_engine(markets):
    config = BotConfig()
    config.paper_trading = True
    config.scan_series = ["TEST"]
    client = MagicMock()
    client.get_markets.return_value = markets
    return TradingEngine(config, client=client)


ARB_MARKET = {
    "ticker": "ARB-1",
    "title": "Arb market",
    "yes_bid": 40,
    "yes_ask": 42,
    "no_bid": 48,
    "no_ask": 50,
    "volume": 100,
    "open_interest": 50,
    "close_ts": 0,
}

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


def test_snapshot_handles_missing_fields():
    snap = snapshot_from_api({"ticker": "X"})
    assert snap.ticker == "X"
    assert snap.yes_ask == 0


def test_snapshot_parses_dollar_and_fp_fields():
    snap = snapshot_from_api(
        {
            "ticker": "Y",
            "yes_bid_dollars": "0.8800",
            "yes_ask_dollars": "0.9000",
            "no_bid_dollars": "0.1000",
            "no_ask_dollars": "0.1200",
            "volume_fp": "1500.00",
            "open_interest_fp": "600.00",
            "close_time": "2026-07-21T17:00:00Z",
        }
    )
    assert snap.yes_bid == 88
    assert snap.yes_ask == 90
    assert snap.no_ask == 12
    assert snap.volume == 1500
    assert snap.open_interest == 600
    assert snap.close_ts == 1784653200


def test_scan_ranks_arbitrage_first():
    engine = make_engine([FAV_MARKET, ARB_MARKET])
    signals = engine.scan()
    assert len(signals) >= 2
    assert signals[0].strategy == "arbitrage"


def test_paper_execution_deducts_cash_and_logs():
    engine = make_engine([FAV_MARKET])
    start = engine.paper_cash_cents
    executed = engine.run_once()
    assert executed == 1
    assert engine.paper_cash_cents < start
    assert engine.trade_log[0]["paper"] is True
    engine.client.create_order.assert_not_called()


def test_live_mode_places_order():
    config = BotConfig()
    config.paper_trading = False
    config.scan_series = ["TEST"]
    client = MagicMock()
    client.get_markets.return_value = [FAV_MARKET]
    client.get_balance.return_value = 100_000
    engine = TradingEngine(config, client=client)
    executed = engine.run_once()
    assert executed == 1
    client.create_order.assert_called_once()
