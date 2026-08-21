from src.autonomy_router import AutonomyRouter
from src.market_data import MarketSnapshot
from src.risk_scorer import RiskScorer
from src.storage.sqlite_storage import SQLiteStorage
from src.trade_executor import TradeExecutor


def test_trade_executor_handles_autonomous_and_confirmed_paths():
    storage = SQLiteStorage(db_path="data/test.sqlite3")
    executor = TradeExecutor(storage=storage)
    scorer = RiskScorer(model_confidence=0.7)
    router = AutonomyRouter()

    low_risk_action = {"type": "hold", "symbol": "AAPL"}
    assessment = scorer.score_action(low_risk_action, MarketSnapshot("AAPL", 150.0, 0.02, 148.0, 1.35, confidence=0.8))
    decision = router.route(assessment.risk_score)
    result = executor.execute(low_risk_action, decision, approved=True)
    assert result.status == "EXECUTED"

    high_risk_action = {"type": "sell", "symbol": "AAPL", "quantity": 1500, "price": 155.0}
    assessment = scorer.score_action(high_risk_action, MarketSnapshot("AAPL", 155.0, 0.03, 150.0, 3.33, confidence=0.6))
    decision = router.route(assessment.risk_score)
    result = executor.execute(high_risk_action, decision, approved=False)
    assert result.status == "QUEUED_FOR_REVIEW"
