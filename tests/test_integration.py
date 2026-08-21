from src.autonomy_router import AutonomyRouter
from src.market_data import MarketDataProvider
from src.risk_scorer import RiskScorer
from src.storage.sqlite_storage import SQLiteStorage
from src.trade_executor import TradeExecutor


def test_end_to_end_routing_and_logging():
    storage = SQLiteStorage(db_path="data/integration.sqlite3")
    provider = MarketDataProvider()
    scorer = RiskScorer(model_confidence=0.8)
    router = AutonomyRouter()
    executor = TradeExecutor(storage=storage)

    scenarios = [
        {"type": "hold", "symbol": "AAPL"},
        {"type": "buy", "symbol": "AAPL", "quantity": 100, "price": 150.0},
        {"type": "sell", "symbol": "AAPL", "quantity": 1000, "price": 152.0},
    ]

    results = []
    for action in scenarios:
        snapshot = provider.fetch(str(action.get("symbol", "AAPL")))
        assessment = scorer.score_action(action, snapshot)
        decision = router.route(assessment.risk_score)
        if decision.level == "confirm":
            executed = executor.execute(action, decision, approved=True)
        else:
            executed = executor.execute(action, decision)
        results.append(executed.status)

    assert results[0] == "EXECUTED"
    assert results[1] in {"CONFIRMED", "PENDING_CONFIRMATION"}
    assert results[2] == "QUEUED_FOR_REVIEW"
    assert len(storage.list_actions()) >= 3
