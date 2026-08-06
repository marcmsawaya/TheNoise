import json
from unittest.mock import MagicMock, patch

from kalshi_bot.advisor import Advisor, AdvisorConfig
from kalshi_bot.models import TradeSignal
from kalshi_bot.tracker import PerformanceTracker


def make_signal(**overrides):
    defaults = dict(
        ticker="TEST-1",
        side="yes",
        action="buy",
        price_cents=90,
        edge=0.03,
        est_win_prob=0.93,
        reason="test",
        strategy="favorite_value",
    )
    defaults.update(overrides)
    return TradeSignal(**defaults)


def test_quant_ranking_without_key():
    advisor = Advisor(AdvisorConfig(api_key=""))
    arb = make_signal(ticker="ARB-1", strategy="arbitrage", edge=0.05)
    fav = make_signal(ticker="FAV-1", edge=0.03)
    ranked = advisor.rank([fav, arb])
    assert ranked[0].signal.ticker == "ARB-1"
    assert ranked[0].verdict == "strong_buy"
    assert ranked[0].score == 100.0
    assert ranked[0].source == "quant"
    assert ranked[1].verdict == "buy"


def test_llm_ranking_with_mocked_api():
    advisor = Advisor(AdvisorConfig(api_key="test-key"))
    llm_response = MagicMock()
    llm_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        [
                            {
                                "ticker": "TEST-1",
                                "score": 82,
                                "verdict": "buy",
                                "rationale": "Liquid favorite with clear edge.",
                            }
                        ]
                    )
                }
            }
        ]
    }
    with patch("kalshi_bot.advisor.requests.post", return_value=llm_response):
        ranked = advisor.rank([make_signal()])
    assert ranked[0].score == 82
    assert ranked[0].source == "llm"
    assert ranked[0].rationale == "Liquid favorite with clear edge."


def test_llm_failure_falls_back_to_quant():
    advisor = Advisor(AdvisorConfig(api_key="test-key"))
    with patch("kalshi_bot.advisor.requests.post", side_effect=ConnectionError):
        ranked = advisor.rank([make_signal()])
    assert ranked[0].source == "quant"


def test_tracker_records_and_settles(tmp_path):
    tracker = PerformanceTracker(path=str(tmp_path / "history.json"))
    tracker.record_trade(
        {"ts": 1.0, "ticker": "T1", "side": "yes", "contracts": 10, "price_cents": 90}
    )
    tracker.record_trade(
        {"ts": 2.0, "ticker": "T2", "side": "no", "contracts": 5, "price_cents": 80}
    )
    tracker.record_settlement("T1", won=True)
    tracker.record_settlement("T2", won=False)
    stats = tracker.stats()
    assert stats["total_trades"] == 2
    assert stats["wins"] == 1
    assert stats["losses"] == 1
    assert stats["win_rate"] == 0.5
    assert stats["total_pnl_cents"] == 10 * 10 - 5 * 80  # +100 - 400
    assert stats["best_trade"]["ticker"] == "T1"

    # persistence round-trip
    reloaded = PerformanceTracker(path=str(tmp_path / "history.json"))
    assert reloaded.stats()["settled_trades"] == 2
