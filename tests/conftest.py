import pytest


@pytest.fixture(autouse=True)
def isolated_trade_history(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADE_HISTORY_PATH", str(tmp_path / "trade_history.json"))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
