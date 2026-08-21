from src.trading_agents_adapter import TradingAgentsAdapter


class FakeGraph:
    def __init__(self, config, debug):
        self.config = config
        self.debug = debug
        self.propagate_args = None

    def propagate(self, symbol, trade_date, asset_type):
        self.propagate_args = (symbol, trade_date, asset_type)
        return (
            {
                "final_trade_decision": "HOLD",
                "trader_investment_plan": "Wait for confirmation.",
                "market_report": "Market report",
                "fundamentals_report": "Fundamentals report",
                "news_report": "News report",
                "sentiment_report": "Sentiment report",
            },
            {"action": "hold", "confidence": 0.7},
        )

    def save_reports(self, _state, _symbol):
        return "data/tradingagents/results/reports/BTC-USD"


def test_adapter_uses_mistral_and_returns_research(monkeypatch, tmp_path):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setenv("MISTRAL_DEEP_THINK_MODEL", "mistral-large-latest")
    adapter = TradingAgentsAdapter(tmp_path, graph_factory=FakeGraph)

    result = adapter.analyze("btc-usd", "2026-08-19")

    assert result["asset_type"] == "crypto"
    assert result["signal"]["action"] == "hold"
    assert result["final_trade_decision"] == "HOLD"
