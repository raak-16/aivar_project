import pandas as pd

from src.paper_trading import KronosPaperTrader
from src.predictor import ForecastSignal
from src.storage.sqlite_storage import SQLiteStorage
from src.strategy import TrendFollowingStrategy, get_strategy


def _signal(direction: str) -> ForecastSignal:
    return ForecastSignal("BTC-USD", direction, 0.02, 0.8, "test signal")


def test_bullish_kronos_signal_buys_fractional_position(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "paper.db"))
    result = KronosPaperTrader(storage).trade("BTC-USD", 50_000, _signal("bullish"))

    assert result.action == "BUY"
    assert result.cash == 75.0
    assert storage.get_paper_position("BTC-USD")["quantity"] == 0.0005


def test_bearish_kronos_signal_sells_existing_position(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "paper.db"))
    trader = KronosPaperTrader(storage)
    trader.trade("BTC-USD", 50_000, _signal("bullish"))
    result = trader.trade("BTC-USD", 50_000, _signal("bearish"))

    assert result.action == "SELL"
    assert result.cash == 87.5


def test_strategy_holds_when_kronos_confidence_is_too_low():
    close = pd.Series([100 + index * 0.1 for index in range(60)])
    history = pd.DataFrame({"close": close, "high": close + 0.2, "low": close - 0.2})
    weak_signal = ForecastSignal("BTC-USD", "bullish", 0.02, 0.3, "weak")

    decision = TrendFollowingStrategy().decide(history, weak_signal)

    assert decision.action == "HOLD"
    assert decision.regime in {"trending", "ranging"}


def test_strategy_registry_returns_each_supported_strategy():
    assert get_strategy("adaptive").key == "adaptive"
    assert get_strategy("mean_reversion").key == "mean_reversion"
