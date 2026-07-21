import time

from kalshi_bot.models import MarketSnapshot
from kalshi_bot.strategies import ArbitrageStrategy, FavoriteValueStrategy


def make_market(**overrides):
    defaults = dict(
        ticker="TEST-24DEC31",
        title="Test market",
        yes_bid=88,
        yes_ask=90,
        no_bid=8,
        no_ask=10,
        volume=1000,
        open_interest=500,
        close_ts=int(time.time()) + 3600,
    )
    defaults.update(overrides)
    return MarketSnapshot(**defaults)


def test_arbitrage_fires_when_combined_asks_below_100():
    market = make_market(yes_ask=45, no_ask=48)
    signal = ArbitrageStrategy().evaluate(market)
    assert signal is not None
    assert signal.strategy == "arbitrage"
    assert signal.side == "yes"
    assert signal.edge > 0


def test_arbitrage_skips_fair_pricing():
    market = make_market(yes_ask=52, no_ask=49)
    assert ArbitrageStrategy().evaluate(market) is None


def test_arbitrage_respects_fee_buffer():
    market = make_market(yes_ask=49, no_ask=49)  # 98 combined, only 2c gross
    assert ArbitrageStrategy().evaluate(market) is None


def test_favorite_value_buys_liquid_favorite():
    signal = FavoriteValueStrategy().evaluate(make_market())
    assert signal is not None
    assert signal.side == "yes"
    assert signal.price_cents == 90
    assert signal.est_win_prob > 0.90


def test_favorite_value_skips_illiquid():
    assert FavoriteValueStrategy().evaluate(make_market(volume=10)) is None


def test_favorite_value_skips_wide_spread():
    assert FavoriteValueStrategy().evaluate(make_market(yes_bid=80, yes_ask=90)) is None


def test_favorite_value_skips_far_dated():
    market = make_market(close_ts=int(time.time()) + 30 * 24 * 3600)
    assert FavoriteValueStrategy().evaluate(market) is None


def test_favorite_value_no_side():
    market = make_market(yes_bid=8, yes_ask=10, no_bid=88, no_ask=90)
    signal = FavoriteValueStrategy().evaluate(market)
    assert signal is not None
    assert signal.side == "no"
