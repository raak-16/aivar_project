from src.market_data import MarketSnapshot
from src.risk_scorer import RiskScorer


def test_hold_action_is_low_risk():
    scorer = RiskScorer(model_confidence=0.75)
    action = {"type": "hold", "symbol": "AAPL"}
    assessment = scorer.score_action(action, MarketSnapshot("AAPL", 150.0, 0.02, 145.0, 3.45, confidence=0.8))
    assert assessment.decision == "autonomous"
    assert assessment.risk_score < 0.3


def test_buy_action_is_medium_risk():
    scorer = RiskScorer(model_confidence=0.75)
    action = {"type": "buy", "symbol": "AAPL", "quantity": 100, "price": 150.0}
    assessment = scorer.score_action(action, MarketSnapshot("AAPL", 150.0, 0.02, 148.0, 1.35, confidence=0.8))
    assert assessment.decision == "confirm"
    assert 0.3 <= assessment.risk_score <= 0.7


def test_sell_action_is_high_risk():
    scorer = RiskScorer(model_confidence=0.75)
    action = {"type": "sell", "symbol": "AAPL", "quantity": 1000, "price": 152.0}
    assessment = scorer.score_action(action, MarketSnapshot("AAPL", 152.0, 0.02, 150.0, 1.33, confidence=0.8))
    assert assessment.decision == "review"
    assert assessment.risk_score > 0.7


def test_risk_breakdown_is_human_readable():
    scorer = RiskScorer(model_confidence=0.75)
    action = {"type": "buy", "symbol": "AAPL", "quantity": 100, "price": 150.0}
    assessment = scorer.score_action(action, MarketSnapshot("AAPL", 150.0, 0.02, 148.0, 1.35, confidence=0.8))
    assert set(assessment.breakdown.keys()) == {"reversibility", "data_scope", "regulatory", "confidence"}
