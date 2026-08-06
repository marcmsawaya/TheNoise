import json

from kalshi_bot.finetune.dataset import SettledMarket, market_to_example


def make_market(**overrides):
    defaults = dict(
        ticker="KXBTCD-TEST",
        title="Bitcoin above X?",
        result="yes",
        last_price_cents=80,
        volume=1000,
        open_interest=500,
        close_time="2026-08-06T02:00:00Z",
    )
    defaults.update(overrides)
    return SettledMarket(**defaults)


def test_yes_winner_labels_yes_side():
    ex = market_to_example(make_market(result="yes", last_price_cents=80))
    label = json.loads(ex["messages"][2]["content"])
    assert label["side"] == "yes"
    # bought YES at 80c, paid out 100c -> 25% return
    assert label["score"] == 25.0
    assert label["verdict"] == "buy"


def test_no_winner_labels_no_side():
    ex = market_to_example(make_market(result="no", last_price_cents=40))
    label = json.loads(ex["messages"][2]["content"])
    assert label["side"] == "no"
    # bought NO at 60c, paid out 100c -> ~66.7% return -> strong_buy
    assert label["verdict"] == "strong_buy"


def test_unusable_markets_skipped():
    assert market_to_example(make_market(last_price_cents=0)) is None
    assert market_to_example(make_market(last_price_cents=100)) is None
    assert market_to_example(make_market(volume=0)) is None


def test_example_is_valid_chat_format():
    ex = market_to_example(make_market())
    roles = [m["role"] for m in ex["messages"]]
    assert roles == ["system", "user", "assistant"]
    user = json.loads(ex["messages"][1]["content"])
    assert user["ticker"] == "KXBTCD-TEST"
    assert user["yes_price_cents"] + user["no_price_cents"] == 100
