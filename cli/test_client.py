from __future__ import annotations

from typing import Dict

from src.autonomy_router import AutonomyRouter
from src.audit_logger import AuditLogger
from src.confirmation_handler import ConfirmationHandler
from src.market_data import MarketDataProvider
from src.risk_scorer import RiskScorer
from src.storage.sqlite_storage import SQLiteStorage
from src.trade_executor import TradeExecutor


SCENARIOS = {
    "1": {"type": "hold", "symbol": "AAPL"},
    "2": {"type": "buy", "symbol": "AAPL", "quantity": 100, "price": 150.0},
    "3": {"type": "sell", "symbol": "AAPL", "quantity": 1000, "price": 152.0},
    "4": {"type": "rebalance", "symbol": "AAPL", "portfolio": ["AAPL", "GOOGL", "MSFT"]},
}


def process_action(action: Dict[str, object], storage: SQLiteStorage, logger: AuditLogger) -> None:
    provider = MarketDataProvider()
    scorer = RiskScorer(model_confidence=0.8)
    router = AutonomyRouter()
    handler = ConfirmationHandler(storage=storage)
    executor = TradeExecutor(storage=storage, logger=logger)

    market_snapshot = provider.fetch(str(action.get("symbol", "AAPL")))
    assessment = scorer.score_action(action, market_snapshot)
    decision = router.route(assessment.risk_score)
    print(f"Risk score: {assessment.risk_score} -> {assessment.breakdown}")

    if decision.level == "autonomous":
        result = executor.execute(action, decision, approved=True)
    elif decision.level == "confirm":
        approved = handler.prompt(action, assessment.risk_score)
        result = executor.execute(action, decision, approved=approved)
    else:
        result = executor.execute(action, decision, approved=False)

    print(f"Result: {result.status} - {result.message}")


def main() -> None:
    storage = SQLiteStorage(db_path="data/local.db")
    logger = AuditLogger(log_path="audit.log")
    print("Graduated autonomy engine CLI")
    for key, scenario in SCENARIOS.items():
        print(f"{key}. {scenario}")
    selection = input("Choose scenario (1-4): ").strip()
    action = SCENARIOS.get(selection, SCENARIOS["2"])
    process_action(action, storage, logger)


if __name__ == "__main__":
    main()
