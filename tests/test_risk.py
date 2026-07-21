from kalshi_bot.config import RiskLimits
from kalshi_bot.models import TradeSignal
from kalshi_bot.risk import RiskManager


def make_signal(**overrides):
    defaults = dict(
        ticker="TEST",
        side="yes",
        action="buy",
        price_cents=90,
        edge=0.06,
        est_win_prob=0.96,
        reason="test",
        strategy="favorite_value",
    )
    defaults.update(overrides)
    return TradeSignal(**defaults)


def test_kelly_sizing_positive_edge():
    rm = RiskManager(RiskLimits())
    contracts = rm.kelly_contracts(make_signal(), bankroll_cents=100_000)
    assert contracts > 0
    # full Kelly = (0.96-0.90)/(1-0.90) = 0.6; quarter-Kelly -> 15% of bankroll
    assert contracts * 90 <= 100_000 * 0.15


def test_kelly_zero_when_no_edge():
    rm = RiskManager(RiskLimits())
    signal = make_signal(est_win_prob=0.90)
    assert rm.kelly_contracts(signal, 100_000) == 0


def test_rejects_below_min_edge():
    rm = RiskManager(RiskLimits(min_edge=0.10))
    decision = rm.check(make_signal(edge=0.05), 100_000)
    assert not decision.approved


def test_order_cost_cap():
    limits = RiskLimits(max_order_cost_cents=500, kelly_fraction=1.0)
    rm = RiskManager(limits)
    decision = rm.check(make_signal(), 1_000_000)
    assert decision.approved
    assert decision.contracts * 90 <= 500


def test_daily_loss_halts_trading():
    rm = RiskManager(RiskLimits(max_daily_loss_cents=1000))
    rm.realized_pnl_today_cents = -1000
    decision = rm.check(make_signal(), 100_000)
    assert not decision.approved
    assert "halted" in decision.reason


def test_exposure_limit():
    limits = RiskLimits(max_open_exposure_cents=100)
    rm = RiskManager(limits)
    rm.record_fill("OTHER", "yes", 2, 50)
    decision = rm.check(make_signal(), 100_000)
    assert not decision.approved


def test_settlement_pnl():
    rm = RiskManager(RiskLimits())
    rm.record_fill("TEST", "yes", 10, 90)
    pnl = rm.record_settlement("TEST", won=True)
    assert pnl == 100
    assert rm.realized_pnl_today_cents == 100
